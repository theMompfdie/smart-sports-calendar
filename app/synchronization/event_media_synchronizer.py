"""Optional, restart-safe Outlook inline-media reconciliation."""

import logging

from app.database.calendar_event_mappings_repository import CalendarEventMapping
from app.database.event_asset_attachments_repository import (
    AppliedAttachment,
    EventAssetAttachment,
    EventAssetAttachmentsRepository,
)
from app.database.media_assets_repository import MediaAsset
from app.database.synchronization_query_repository import SynchronizationEvent
from app.graph.client import (
    GraphClient,
    OutlookAttachmentNotFoundError,
    OutlookAttachmentReference,
)
from app.media.asset_service import MediaAssetService
from app.media.event_asset_selector import EventAssetSelector
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayloadBuilder,
)
from app.synchronization.outlook_html_event_body_renderer import OutlookInlineImage


class EventMediaSynchronizationError(RuntimeError):
    pass


class EventMediaSynchronizer:
    """Converge optional event media without changing core event sync state."""

    def __init__(
        self,
        *,
        selector: EventAssetSelector,
        asset_service: MediaAssetService,
        attachments_repository: EventAssetAttachmentsRepository,
        payload_builder: OutlookEventPayloadBuilder,
        graph_client: GraphClient,
        logger: logging.Logger | None = None,
    ) -> None:
        self._selector = selector
        self._asset_service = asset_service
        self._attachments = attachments_repository
        self._payload_builder = payload_builder
        self._graph = graph_client
        self._logger = logger or logging.getLogger(__name__)

    def reconcile(
        self,
        synchronization_event: SynchronizationEvent,
        mapping: CalendarEventMapping,
        *,
        core_event_written: bool = False,
    ) -> None:
        outlook_event_id = mapping.outlook_event_id
        if outlook_event_id is None or mapping.sync_status == "deleted":
            return
        if core_event_written:
            self._attachments.mark_body_refresh_required(mapping.id)
        existing = self._attachments.list_for_mapping(mapping.id)
        existing = self._cleanup_obsolete(
            mapping.calendar_id,
            outlook_event_id,
            existing,
        )
        if any(
            state.obsolete_outlook_attachment_id is not None for state in existing
        ):
            return
        desired = self._selector.select(synchronization_event)
        states = self._attachments.reconcile_desired(mapping.id, desired)
        states = self._cleanup_obsolete(
            mapping.calendar_id,
            outlook_event_id,
            states,
        )
        desired_by_id = {asset.id: asset for asset in desired.values()}
        prepared = self._prepare_uploads(states, desired_by_id)
        recovered = self._recover_pending(
            mapping.calendar_id,
            outlook_event_id,
            prepared,
        )
        self._upload_pending(
            mapping.calendar_id,
            outlook_event_id,
            recovered,
            desired_by_id,
        )
        states = self._attachments.list_for_mapping(mapping.id)
        if not states:
            return
        applied = self._effective_attachments(states)
        if (
            not core_event_written
            and not self._body_transition_required(states, applied)
        ):
            return

        images = self._build_inline_images(synchronization_event, applied)
        payload = self._payload_builder.build(
            synchronization_event,
            inline_images=images,
        )
        try:
            reference = self._graph.update_event(
                calendar_id=mapping.calendar_id,
                event_id=outlook_event_id,
                payload=payload,
            )
            if reference.id != outlook_event_id:
                raise EventMediaSynchronizationError(
                    "Microsoft Graph returned a different event ID during "
                    "media update."
                )
        except Exception as error:
            for state in states:
                target = applied[state.slot]
                target_id = None if target is None else target.outlook_attachment_id
                if core_event_written or target_id != state.outlook_attachment_id:
                    self._record_failure(state, error)
            raise
        states = self._attachments.apply_body(mapping.id, applied)
        self._cleanup_obsolete(mapping.calendar_id, outlook_event_id, states)

    def mark_event_deleted(self, mapping_id: int) -> None:
        self._attachments.mark_event_deleted(mapping_id)

    def _cleanup_obsolete(
        self,
        calendar_id: str,
        outlook_event_id: str,
        states: list[EventAssetAttachment],
    ) -> list[EventAssetAttachment]:
        for state in states:
            obsolete_id = state.obsolete_outlook_attachment_id
            if obsolete_id is None:
                continue
            try:
                self._graph.delete_event_attachment(
                    calendar_id,
                    outlook_event_id,
                    obsolete_id,
                )
            except OutlookAttachmentNotFoundError:
                pass
            except Exception as error:
                self._record_failure(state, error)
                continue
            self._attachments.mark_cleanup_complete(state.id)
        if not states:
            return states
        return self._attachments.list_for_mapping(
            states[0].calendar_event_mapping_id
        )

    def _prepare_uploads(
        self,
        states: list[EventAssetAttachment],
        desired_by_id: dict[int, MediaAsset],
    ) -> list[EventAssetAttachment]:
        for state in states:
            if (
                state.desired_asset_id is None
                or state.desired_sha256 == state.synchronized_sha256
                or state.pending_outlook_attachment_id is not None
                or state.obsolete_outlook_attachment_id is not None
            ):
                continue
            asset = desired_by_id.get(state.desired_asset_id)
            if asset is None:
                self._attachments.mark_failed(
                    state.id,
                    "Selected media asset disappeared before upload.",
                )
                continue
            self._attachments.prepare_upload(state.id, asset)
        if not states:
            return states
        return self._attachments.list_for_mapping(states[0].calendar_event_mapping_id)

    def _recover_pending(
        self,
        calendar_id: str,
        outlook_event_id: str,
        states: list[EventAssetAttachment],
    ) -> list[EventAssetAttachment]:
        pending = [
            state
            for state in states
            if state.pending_content_id is not None
            and state.pending_outlook_attachment_id is None
        ]
        if not pending:
            return states
        try:
            remote = self._graph.list_event_attachments(calendar_id, outlook_event_id)
        except Exception as error:
            for state in pending:
                self._record_failure(state, error)
            return self._attachments.list_for_mapping(
                pending[0].calendar_event_mapping_id
            )
        by_content_id: dict[str, list[OutlookAttachmentReference]] = {}
        for attachment in remote:
            if attachment.content_id is not None:
                by_content_id.setdefault(attachment.content_id, []).append(attachment)
        for state in pending:
            matches = by_content_id.get(state.pending_content_id or "", [])
            if len(matches) == 1:
                self._attachments.mark_uploaded(state.id, matches[0].id)
            elif len(matches) > 1:
                self._attachments.mark_failed(
                    state.id,
                    "Multiple Outlook attachments share the pending content ID.",
                )
        return self._attachments.list_for_mapping(pending[0].calendar_event_mapping_id)

    def _upload_pending(
        self,
        calendar_id: str,
        outlook_event_id: str,
        states: list[EventAssetAttachment],
        desired_by_id: dict[int, MediaAsset],
    ) -> None:
        for state in states:
            if (
                state.pending_asset_id is None
                or state.pending_content_id is None
                or state.pending_outlook_attachment_id is not None
                or state.obsolete_outlook_attachment_id is not None
                or state.status == "failed"
            ):
                continue
            asset = desired_by_id.get(state.pending_asset_id)
            if asset is None or asset.sha256 != state.pending_sha256:
                self._attachments.mark_failed(
                    state.id,
                    "Pending media asset is no longer selected.",
                )
                continue
            try:
                self._attachments.mark_attempt(state.id)
                content = self._asset_service.read_active_content(asset)
                uploaded = self._graph.create_inline_attachment(
                    calendar_id,
                    outlook_event_id,
                    name=f"ssc-{state.slot}-{asset.sha256[:12]}.png",
                    content_id=state.pending_content_id,
                    content=content,
                )
                self._attachments.mark_uploaded(state.id, uploaded.id)
            except Exception as error:
                self._record_failure(state, error)

    @staticmethod
    def _effective_attachments(
        states: list[EventAssetAttachment],
    ) -> dict[str, AppliedAttachment | None]:
        effective: dict[str, AppliedAttachment | None] = {}
        for state in states:
            target: AppliedAttachment | None = None
            if (
                state.desired_sha256 is not None
                and state.pending_sha256 == state.desired_sha256
                and state.pending_asset_id is not None
                and state.pending_content_id is not None
                and state.pending_outlook_attachment_id is not None
            ):
                target = AppliedAttachment(
                    asset_id=state.pending_asset_id,
                    sha256=state.pending_sha256,
                    content_id=state.pending_content_id,
                    outlook_attachment_id=state.pending_outlook_attachment_id,
                )
            elif (
                state.desired_sha256 is not None
                and state.synchronized_asset_id is not None
                and state.synchronized_sha256 is not None
                and state.content_id is not None
                and state.outlook_attachment_id is not None
            ):
                target = AppliedAttachment(
                    asset_id=state.synchronized_asset_id,
                    sha256=state.synchronized_sha256,
                    content_id=state.content_id,
                    outlook_attachment_id=state.outlook_attachment_id,
                )
            effective[state.slot] = target
        return effective

    @staticmethod
    def _body_transition_required(
        states: list[EventAssetAttachment],
        applied: dict[str, AppliedAttachment | None],
    ) -> bool:
        for state in states:
            if state.status == "failed" and state.outlook_attachment_id is not None:
                return True
            target = applied[state.slot]
            target_id = None if target is None else target.outlook_attachment_id
            if target_id != state.outlook_attachment_id:
                return True
        return False

    @staticmethod
    def _build_inline_images(
        event: SynchronizationEvent,
        applied: dict[str, AppliedAttachment | None],
    ) -> tuple[OutlookInlineImage, ...]:
        participant_names = {
            participant.role: participant.participant.name
            for participant in event.participants
            if participant.role in {"home", "away"}
        }
        labels = {
            "competition": (
                event.competition.name
                if event.competition is not None
                else event.sport.name
            ),
            "home": participant_names.get("home", "Home participant"),
            "away": participant_names.get("away", "Away participant"),
            "final": "Final",
        }
        return tuple(
            OutlookInlineImage(slot, target.content_id, labels[slot])
            for slot, target in applied.items()
            if target is not None
        )

    def _record_failure(
        self,
        state: EventAssetAttachment,
        error: Exception,
    ) -> None:
        failure_class = type(error).__name__
        self._attachments.mark_failed(state.id, failure_class)
        self._logger.warning(
            "Optional Outlook media synchronization failed: slot=%s failure=%s",
            state.slot,
            failure_class,
        )
