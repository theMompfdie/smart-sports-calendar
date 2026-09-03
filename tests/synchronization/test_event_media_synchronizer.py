from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import pytest
from app.database.calendar_event_mappings_repository import (
    CalendarEventMapping,
    CalendarEventMappingsRepository,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_asset_attachments_repository import (
    EventAssetAttachmentsRepository,
)
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.media_assets_repository import MediaAssetsRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.synchronization_query_repository import (
    SynchronizationEvent,
    SynchronizationQueryRepository,
)
from app.domain.media_assets import MediaOwnerType
from app.graph.client import OutlookAttachmentReference, OutlookEventReference
from app.media.asset_service import MediaAssetService
from app.media.event_asset_selector import EventAssetSelector
from app.synchronization.content_hash import calculate_content_hash
from app.synchronization.event_media_synchronizer import EventMediaSynchronizer
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayload,
    OutlookEventPayloadBuilder,
)
from app.synchronization.outlook_html_event_body_renderer import (
    OutlookHtmlEventBodyRenderer,
    OutlookInlineImage,
)
from PIL import Image


class RecordingGraph:
    def __init__(self) -> None:
        self.attachments: list[OutlookAttachmentReference] = []
        self.uploads: list[str] = []
        self.updates: list[OutlookEventPayload] = []
        self.deletions: list[str] = []
        self.list_error: Exception | None = None
        self.upload_error: Exception | None = None
        self.update_error: Exception | None = None
        self.list_calls = 0

    def list_event_attachments(
        self,
        calendar_id: str,
        event_id: str,
    ) -> tuple[OutlookAttachmentReference, ...]:
        self.list_calls += 1
        if self.list_error is not None:
            raise self.list_error
        return tuple(self.attachments)

    def create_inline_attachment(
        self,
        calendar_id: str,
        event_id: str,
        *,
        name: str,
        content_id: str,
        content: bytes,
    ) -> OutlookAttachmentReference:
        if self.upload_error is not None:
            raise self.upload_error
        reference = OutlookAttachmentReference(
            f"attachment-{len(self.uploads) + 1}",
            content_id,
            name,
        )
        self.uploads.append(content_id)
        self.attachments.append(reference)
        return reference

    def update_event(
        self, *, calendar_id: str, event_id: str, payload: OutlookEventPayload
    ) -> OutlookEventReference:
        if self.update_error is not None:
            raise self.update_error
        self.updates.append(payload)
        return OutlookEventReference(event_id)

    def delete_event_attachment(
        self,
        calendar_id: str,
        event_id: str,
        attachment_id: str,
    ) -> None:
        self.deletions.append(attachment_id)
        self.attachments = [
            attachment
            for attachment in self.attachments
            if attachment.id != attachment_id
        ]


@dataclass(frozen=True)
class Harness:
    event: SynchronizationEvent
    mapping: CalendarEventMapping
    assets: MediaAssetsRepository
    asset_service: MediaAssetService
    attachments: EventAssetAttachmentsRepository
    synchronizer: EventMediaSynchronizer
    graph: RecordingGraph
    home_key: str


def _import_home_asset(harness: Harness, source: Path, color: str):
    Image.new("RGBA", (60, 60), color).save(source, format="PNG")
    pending = harness.asset_service.import_asset(
        asset_key=harness.home_key,
        owner=harness.assets.resolve_owner(MediaOwnerType.PARTICIPANT, "home"),
        variant="logo",
        source_file=source,
        source_reference=f"synthetic-{color}",
        license_name="MIT",
        permission_reference=None,
        attribution=None,
    )
    return harness.asset_service.approve(pending.asset_key, pending.version, "operator")


def _harness(tmp_path: Path) -> Harness:
    database_path = tmp_path / "sports.db"
    media_root = tmp_path / "media"
    Database(database_path).initialize()
    sport = SportsRepository(database_path).upsert("football", "Football")
    competition = CompetitionsRepository(database_path).upsert(
        sport.id,
        "test_league",
        "Test League",
    )
    participants = ParticipantsRepository(database_path)
    home = participants.upsert(sport.id, "home", "team", "Home")
    away = participants.upsert(sport.id, "away", "team", "Away")
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        competition_id=competition.id,
        event_key="home-away",
        event_type="match",
        title="Home vs Away",
        stage="Regular season",
        start_time="2026-09-02T18:00:00+00:00",
        timezone="UTC",
        status="confirmed",
    )
    assignments = EventParticipantsRepository(database_path)
    assignments.upsert(event.id, home.id, "home", 1)
    assignments.upsert(event.id, away.id, "away", 2)
    mappings = CalendarEventMappingsRepository(database_path)
    pending_mapping = mappings.create_pending(event.id, "calendar-1")
    mapping = mappings.mark_synced(
        pending_mapping.id,
        "outlook-event-1",
        None,
        "a" * 64,
        event.sync_revision,
        pending_mapping.presentation_revision,
    )
    assert mapping is not None
    aggregate = SynchronizationQueryRepository(database_path).get_by_event_id(
        event.id,
        mapping.calendar_id,
    )
    assert aggregate is not None
    assets = MediaAssetsRepository(database_path)
    asset_service = MediaAssetService(assets, media_root)
    attachments = EventAssetAttachmentsRepository(database_path)
    graph = RecordingGraph()
    synchronizer = EventMediaSynchronizer(
        selector=EventAssetSelector(assets),
        asset_service=asset_service,
        attachments_repository=attachments,
        payload_builder=OutlookEventPayloadBuilder(),
        graph_client=graph,  # type: ignore[arg-type]
    )
    return Harness(
        aggregate,
        mapping,
        assets,
        asset_service,
        attachments,
        synchronizer,
        graph,
        "team.home.logo",
    )


class ChangedMediaRenderer(OutlookHtmlEventBodyRenderer):
    def render(
        self,
        synchronization_event: SynchronizationEvent,
        *,
        is_cancelled: bool,
        location: str | None,
        inline_images: tuple[OutlookInlineImage, ...] = (),
    ) -> str:
        body = super().render(
            synchronization_event,
            is_cancelled=is_cancelled,
            location=location,
            inline_images=inline_images,
        )
        return body + ("<!-- changed-media-template -->" if inline_images else "")


def _synchronize_current(harness: Harness, tmp_path: Path) -> None:
    # Rebuild the services and reload SQLite state to exercise restart recovery.
    database_path = tmp_path / "sports.db"
    builder = OutlookEventPayloadBuilder(body_renderer=ChangedMediaRenderer())
    media = EventMediaSynchronizer(
        selector=EventAssetSelector(harness.assets),
        asset_service=harness.asset_service,
        attachments_repository=EventAssetAttachmentsRepository(database_path),
        payload_builder=builder,
        graph_client=harness.graph,  # type: ignore[arg-type]
    )
    synchronizer = EventSynchronizer(
        builder,
        harness.graph,  # type: ignore[arg-type]
        CalendarEventMappingsRepository(database_path),
        media_synchronizer=media,
    )
    event = SynchronizationQueryRepository(database_path).get_by_event_id(
        harness.event.event.id, harness.mapping.calendar_id
    )
    assert event is not None
    synchronizer.synchronize_event(event, harness.mapping.calendar_id)


def _prepare_presentation_refresh(harness: Harness, tmp_path: Path) -> None:
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.synchronizer.reconcile(harness.event, harness.mapping)
    mappings = CalendarEventMappingsRepository(tmp_path / "sports.db")
    mapping = mappings.get_by_id(harness.mapping.id)
    assert mapping is not None
    assert mapping.outlook_event_id is not None
    core_hash = calculate_content_hash(
        OutlookEventPayloadBuilder().build(harness.event)
    )
    changed_hash = calculate_content_hash(
        OutlookEventPayloadBuilder(body_renderer=ChangedMediaRenderer()).build(
            harness.event
        )
    )
    assert core_hash == changed_hash
    mappings.mark_synced(
        mapping.id,
        mapping.outlook_event_id,
        mapping.outlook_change_key,
        core_hash,
        harness.event.event.sync_revision,
        mapping.presentation_revision,
    )
    assert mappings.invalidate_all_presentations() == 1


@pytest.mark.parametrize("remote_missing", [False, True])
def test_presentation_invalidation_refreshes_media_with_equal_core_hash(
    tmp_path: Path, remote_missing: bool
) -> None:
    harness = _harness(tmp_path)
    _prepare_presentation_refresh(harness, tmp_path)
    if remote_missing:
        harness.graph.attachments.clear()

    _synchronize_current(harness, tmp_path)

    assert len(harness.graph.updates) == 2
    assert "changed-media-template" in harness.graph.updates[-1].body
    assert len(harness.graph.uploads) == (2 if remote_missing else 1)
    assert len(harness.graph.attachments) == 1
    state = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert state.status == "synced"
    assert state.content_id == harness.graph.attachments[0].content_id
    assert harness.graph.updates[-1].body.count(f"cid:{state.content_id}") == 2
    mapping = CalendarEventMappingsRepository(tmp_path / "sports.db").get_by_id(
        harness.mapping.id
    )
    assert mapping is not None
    assert mapping.outlook_event_id == harness.mapping.outlook_event_id
    assert mapping.transaction_id == harness.mapping.transaction_id
    assert mapping.presentation_revision == mapping.last_synced_presentation_revision
    list_calls = harness.graph.list_calls

    _synchronize_current(harness, tmp_path)

    assert len(harness.graph.updates) == 2
    assert len(harness.graph.uploads) == (2 if remote_missing else 1)
    assert harness.graph.list_calls == list_calls
    assert harness.graph.deletions == []


@pytest.mark.parametrize("failure", ["list_error", "update_error"])
def test_presentation_media_refresh_survives_failure_and_restart(
    tmp_path: Path, failure: str
) -> None:
    harness = _harness(tmp_path)
    _prepare_presentation_refresh(harness, tmp_path)
    setattr(harness.graph, failure, RuntimeError("temporary media failure"))

    _synchronize_current(harness, tmp_path)

    assert (
        harness.attachments.list_for_mapping(harness.mapping.id)[0].status == "failed"
    )
    mapping = CalendarEventMappingsRepository(tmp_path / "sports.db").get_by_id(
        harness.mapping.id
    )
    assert mapping is not None
    assert mapping.presentation_revision == mapping.last_synced_presentation_revision
    setattr(harness.graph, failure, None)
    _synchronize_current(harness, tmp_path)
    assert (
        harness.attachments.list_for_mapping(harness.mapping.id)[0].status == "synced"
    )
    assert "changed-media-template" in harness.graph.updates[-1].body
    assert len(harness.graph.uploads) == 1
    calls = (len(harness.graph.updates), harness.graph.list_calls)
    _synchronize_current(harness, tmp_path)
    assert (len(harness.graph.updates), harness.graph.list_calls) == calls


def test_presentation_refresh_survives_interruption_after_core_acknowledgement(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _prepare_presentation_refresh(harness, tmp_path)
    with (
        patch.object(
            EventMediaSynchronizer, "reconcile", side_effect=KeyboardInterrupt
        ),
        pytest.raises(KeyboardInterrupt),
    ):
        _synchronize_current(harness, tmp_path)
    assert (
        harness.attachments.list_for_mapping(harness.mapping.id)[0].status == "failed"
    )
    _synchronize_current(harness, tmp_path)
    assert "changed-media-template" in harness.graph.updates[-1].body
    assert len(harness.graph.uploads) == 1


def test_presentation_invalidation_without_media_does_not_write_to_graph(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    mappings = CalendarEventMappingsRepository(tmp_path / "sports.db")
    mappings.mark_synced(
        harness.mapping.id,
        "outlook-event-1",
        None,
        calculate_content_hash(OutlookEventPayloadBuilder().build(harness.event)),
        harness.event.event.sync_revision,
        harness.mapping.presentation_revision,
    )
    mappings.invalidate_all_presentations()
    _synchronize_current(harness, tmp_path)
    assert harness.graph.updates == []
    assert harness.graph.uploads == []
    assert harness.graph.list_calls == 0


def test_media_reconciliation_is_idempotent_and_replaces_without_orphans(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")

    harness.synchronizer.reconcile(harness.event, harness.mapping)
    first = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert first.status == "synced"
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 1
    assert "cid:" in harness.graph.updates[0].body  # type: ignore[union-attr]

    harness.synchronizer.reconcile(harness.event, harness.mapping)
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 1

    _import_home_asset(harness, tmp_path / "replacement.png", "blue")
    harness.synchronizer.reconcile(harness.event, harness.mapping)
    replaced = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert replaced.status == "synced"
    assert replaced.outlook_attachment_id == "attachment-2"
    assert harness.graph.deletions == ["attachment-1"]
    assert [item.id for item in harness.graph.attachments] == ["attachment-2"]


def test_core_write_without_selected_media_does_not_add_redundant_patch(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)

    harness.synchronizer.reconcile(
        harness.event,
        harness.mapping,
        core_event_written=True,
    )

    assert harness.graph.uploads == []
    assert harness.graph.updates == []


def test_core_write_reuploads_synchronized_attachment_missing_from_outlook(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.synchronizer.reconcile(harness.event, harness.mapping)
    first = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert first.outlook_attachment_id == "attachment-1"

    harness.graph.attachments.clear()
    harness.synchronizer.reconcile(
        harness.event,
        harness.mapping,
        core_event_written=True,
    )

    recovered = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert recovered.status == "synced"
    assert recovered.outlook_attachment_id == "attachment-2"
    assert len(harness.graph.uploads) == 2
    assert len(harness.graph.attachments) == 1
    assert len(harness.graph.updates) == 2


def test_core_write_replaces_attachment_with_mismatched_remote_content_id(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.synchronizer.reconcile(harness.event, harness.mapping)
    harness.graph.attachments[0] = OutlookAttachmentReference(
        "attachment-1",
        "unexpected-content-id@example",
        "unexpected.png",
    )

    harness.synchronizer.reconcile(
        harness.event,
        harness.mapping,
        core_event_written=True,
    )

    recovered = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert recovered.status == "synced"
    assert recovered.outlook_attachment_id == "attachment-2"
    assert harness.graph.deletions == ["attachment-1"]
    assert [item.id for item in harness.graph.attachments] == ["attachment-2"]


def test_remote_attachment_audit_failure_remains_retryable(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.synchronizer.reconcile(harness.event, harness.mapping)
    harness.graph.list_error = RuntimeError("temporary attachment list failure")

    with pytest.raises(RuntimeError, match="temporary attachment list failure"):
        harness.synchronizer.reconcile(
            harness.event,
            harness.mapping,
            core_event_written=True,
        )

    failed = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert failed.status == "failed"
    assert failed.outlook_attachment_id == "attachment-1"
    harness.graph.list_error = None

    harness.synchronizer.reconcile(harness.event, harness.mapping)

    recovered = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert recovered.status == "synced"
    assert recovered.outlook_attachment_id == "attachment-1"
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 2


def test_upload_failure_keeps_text_event_and_persists_retryable_state(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.graph.upload_error = RuntimeError("secret-bearing provider failure")

    harness.synchronizer.reconcile(harness.event, harness.mapping)

    state = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert state.status == "failed"
    assert state.last_error == "RuntimeError"
    assert harness.graph.updates == []


def test_restart_recovers_uploaded_attachment_by_content_id(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    asset = _import_home_asset(harness, tmp_path / "first.png", "red")
    state = harness.attachments.reconcile_desired(
        harness.mapping.id,
        {"home": asset},
    )[0]
    prepared = harness.attachments.prepare_upload(state.id, asset)
    assert prepared.pending_content_id is not None
    harness.graph.attachments.append(
        OutlookAttachmentReference(
            "recovered-attachment",
            prepared.pending_content_id,
            "recovered.png",
        )
    )

    harness.synchronizer.reconcile(harness.event, harness.mapping)

    synchronized = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert synchronized.status == "synced"
    assert synchronized.outlook_attachment_id == "recovered-attachment"
    assert harness.graph.uploads == []
    assert len(harness.graph.updates) == 1


def test_body_patch_failure_reuses_uploaded_attachment_on_retry(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.graph.update_error = RuntimeError("temporary body failure")

    with pytest.raises(RuntimeError, match="temporary body failure"):
        harness.synchronizer.reconcile(harness.event, harness.mapping)

    failed = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert failed.status == "failed"
    assert failed.pending_outlook_attachment_id == "attachment-1"
    harness.graph.update_error = None
    harness.synchronizer.reconcile(harness.event, harness.mapping)

    synchronized = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert synchronized.status == "synced"
    assert synchronized.outlook_attachment_id == "attachment-1"
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 1


def test_failed_image_restore_after_core_write_remains_actionable(
    tmp_path: Path,
) -> None:
    harness = _harness(tmp_path)
    _import_home_asset(harness, tmp_path / "first.png", "red")
    harness.synchronizer.reconcile(harness.event, harness.mapping)
    harness.graph.update_error = RuntimeError("temporary restore failure")

    with pytest.raises(RuntimeError, match="temporary restore failure"):
        harness.synchronizer.reconcile(
            harness.event,
            harness.mapping,
            core_event_written=True,
        )

    failed = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert failed.status == "failed"
    harness.graph.update_error = None
    harness.synchronizer.reconcile(harness.event, harness.mapping)

    recovered = harness.attachments.list_for_mapping(harness.mapping.id)[0]
    assert recovered.status == "synced"
    assert len(harness.graph.uploads) == 1
    assert len(harness.graph.updates) == 2
