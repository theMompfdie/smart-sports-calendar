from dataclasses import dataclass
from enum import StrEnum

from app.database.calendar_event_mappings_repository import (
    CalendarEventMapping,
    CalendarEventMappingsRepository,
)
from app.database.synchronization_query_repository import SynchronizationEvent
from app.graph.client import GraphClient, OutlookEventNotFoundError
from app.synchronization.content_hash import calculate_content_hash
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayload,
    OutlookEventPayloadBuilder,
)


class EventSynchronizationStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    CANCELLED = "cancelled"
    CANCELLATION_SKIPPED = "cancellation_skipped"
    DELETED = "deleted"


@dataclass(frozen=True)
class EventSynchronizationResult:
    status: EventSynchronizationStatus
    event_id: int
    calendar_id: str
    outlook_event_id: str | None
    content_hash: str | None


class EventSynchronizationError(RuntimeError):
    pass


class EventSynchronizer:
    def __init__(
        self,
        payload_builder: OutlookEventPayloadBuilder,
        graph_client: GraphClient,
        mappings_repository: CalendarEventMappingsRepository,
    ) -> None:
        self._payload_builder = payload_builder
        self._graph_client = graph_client
        self._mappings_repository = mappings_repository

    def synchronize_event(
        self,
        synchronization_event: SynchronizationEvent,
        calendar_id: str,
    ) -> EventSynchronizationResult:
        event = synchronization_event.event
        mapping = synchronization_event.mapping
        mapping_was_revived = False

        if mapping is not None:
            self._validate_mapping(
                mapping=mapping,
                event_id=event.id,
                calendar_id=calendar_id,
            )

        if event.deleted_at is not None:
            if mapping is None or mapping.sync_status == "deleted":
                return EventSynchronizationResult(
                    status=EventSynchronizationStatus.DELETED,
                    event_id=event.id,
                    calendar_id=calendar_id,
                    outlook_event_id=(
                        None if mapping is None else mapping.outlook_event_id
                    ),
                    content_hash=None if mapping is None else mapping.content_hash,
                )
            if mapping.outlook_event_id is None:
                deleted_mapping = self._mappings_repository.mark_deleted(mapping.id)
                if deleted_mapping is None:
                    raise EventSynchronizationError(
                        "Calendar mapping without an Outlook event could not be "
                        f"finalized as deleted: {mapping.id}"
                    )
                return EventSynchronizationResult(
                    status=EventSynchronizationStatus.DELETED,
                    event_id=event.id,
                    calendar_id=calendar_id,
                    outlook_event_id=None,
                    content_hash=mapping.content_hash,
                )
            if mapping.sync_status != "delete_pending":
                delete_pending = self._mappings_repository.mark_delete_pending(
                    mapping.id
                )
                if delete_pending is None:
                    raise EventSynchronizationError(
                        "Calendar mapping could not be marked for deletion: "
                        f"{mapping.id}"
                    )
                mapping = delete_pending
            return self._delete_event(
                mapping=mapping,
                calendar_id=calendar_id,
            )

        if mapping is not None and mapping.sync_status == "deleted":
            revived_mapping = self._mappings_repository.revive_deleted(mapping.id)
            if revived_mapping is None:
                raise EventSynchronizationError(
                    f"Deleted calendar mapping could not be revived: {mapping.id}"
                )
            mapping = revived_mapping
            mapping_was_revived = True

        if mapping is not None and mapping.sync_status == "delete_pending":
            return self._delete_event(
                mapping=mapping,
                calendar_id=calendar_id,
            )

        is_cancelled = event.status.casefold() == "cancelled"

        if is_cancelled and mapping is None:
            return EventSynchronizationResult(
                status=EventSynchronizationStatus.CANCELLATION_SKIPPED,
                event_id=event.id,
                calendar_id=calendar_id,
                outlook_event_id=None,
                content_hash=None,
            )

        try:
            payload = self._payload_builder.build(synchronization_event)
            content_hash = calculate_content_hash(payload)
        except Exception as error:
            raise EventSynchronizationError(
                f"Outlook payload preparation failed for event {event.id}."
            ) from error

        if mapping_was_revived:
            return self._create_event(
                event_id=event.id,
                calendar_id=calendar_id,
                payload=payload,
                content_hash=content_hash,
                mapping=mapping,
            )

        if mapping is None:
            return self._create_event(
                event_id=event.id,
                calendar_id=calendar_id,
                payload=payload,
                content_hash=content_hash,
            )

        if mapping.outlook_event_id is None:
            if mapping.sync_status not in {"pending", "failed"}:
                error = EventSynchronizationError(
                    "Existing calendar mapping has no Outlook event ID and "
                    "cannot be retried: "
                    f"mapping_id={mapping.id}, sync_status={mapping.sync_status}"
                )
                self._record_failure(mapping, error)
                raise error

            return self._create_event(
                event_id=event.id,
                calendar_id=calendar_id,
                payload=payload,
                content_hash=content_hash,
                mapping=mapping,
            )

        if mapping.content_hash == content_hash:
            return EventSynchronizationResult(
                status=(
                    EventSynchronizationStatus.CANCELLED
                    if is_cancelled
                    else EventSynchronizationStatus.UNCHANGED
                ),
                event_id=event.id,
                calendar_id=calendar_id,
                outlook_event_id=mapping.outlook_event_id,
                content_hash=content_hash,
            )

        return self._update_event(
            mapping=mapping,
            calendar_id=calendar_id,
            payload=payload,
            content_hash=content_hash,
            result_status=(
                EventSynchronizationStatus.CANCELLED
                if is_cancelled
                else EventSynchronizationStatus.UPDATED
            ),
        )

    def _create_event(
        self,
        event_id: int,
        calendar_id: str,
        payload: OutlookEventPayload,
        content_hash: str,
        mapping: CalendarEventMapping | None = None,
    ) -> EventSynchronizationResult:
        if mapping is None:
            try:
                mapping = self._mappings_repository.create_pending(
                    event_id=event_id,
                    calendar_id=calendar_id,
                )
            except Exception as error:
                raise EventSynchronizationError(
                    f"Pending calendar mapping could not be created for "
                    f"event {event_id}."
                ) from error
        elif mapping.sync_status == "failed":
            try:
                pending_mapping = self._mappings_repository.mark_pending(
                    mapping_id=mapping.id,
                )
            except Exception as error:
                raise EventSynchronizationError(
                    f"Calendar mapping could not be prepared for retry: {mapping.id}"
                ) from error

            if pending_mapping is None:
                raise EventSynchronizationError(
                    f"Calendar mapping disappeared before retry: {mapping.id}"
                )

            mapping = pending_mapping

        try:
            event_reference = self._graph_client.create_event(
                calendar_id=calendar_id,
                payload=payload,
                transaction_id=mapping.transaction_id,
            )

            synchronized_mapping = self._mappings_repository.mark_synced(
                mapping_id=mapping.id,
                outlook_event_id=event_reference.id,
                outlook_change_key=None,
                content_hash=content_hash,
            )

            if synchronized_mapping is None:
                raise EventSynchronizationError(
                    f"Calendar mapping disappeared during synchronization: {mapping.id}"
                )
        except Exception as error:
            self._record_failure(mapping, error)

            if isinstance(error, EventSynchronizationError):
                raise

            raise EventSynchronizationError(
                f"Outlook event creation failed for event {event_id}."
            ) from error

        return EventSynchronizationResult(
            status=EventSynchronizationStatus.CREATED,
            event_id=event_id,
            calendar_id=calendar_id,
            outlook_event_id=event_reference.id,
            content_hash=content_hash,
        )

    def _update_event(
        self,
        mapping: CalendarEventMapping,
        calendar_id: str,
        payload: OutlookEventPayload,
        content_hash: str,
        result_status: EventSynchronizationStatus = (
            EventSynchronizationStatus.UPDATED
        ),
    ) -> EventSynchronizationResult:
        outlook_event_id = mapping.outlook_event_id

        if outlook_event_id is None:
            raise EventSynchronizationError(
                "Cannot update an Outlook event without an event ID."
            )

        try:
            event_reference = self._graph_client.update_event(
                calendar_id=calendar_id,
                event_id=outlook_event_id,
                payload=payload,
            )

            if event_reference.id != outlook_event_id:
                raise EventSynchronizationError(
                    "Microsoft Graph returned a different event ID during update."
                )

            synchronized_mapping = self._mappings_repository.mark_synced(
                mapping_id=mapping.id,
                outlook_event_id=event_reference.id,
                outlook_change_key=mapping.outlook_change_key,
                content_hash=content_hash,
            )

            if synchronized_mapping is None:
                raise EventSynchronizationError(
                    f"Calendar mapping disappeared during synchronization: {mapping.id}"
                )
        except Exception as error:
            self._record_failure(mapping, error)

            if isinstance(error, EventSynchronizationError):
                raise

            raise EventSynchronizationError(
                f"Outlook event update failed for event {mapping.event_id}."
            ) from error

        return EventSynchronizationResult(
            status=result_status,
            event_id=mapping.event_id,
            calendar_id=calendar_id,
            outlook_event_id=event_reference.id,
            content_hash=content_hash,
        )

    def _delete_event(
        self,
        mapping: CalendarEventMapping,
        calendar_id: str,
    ) -> EventSynchronizationResult:
        outlook_event_id = mapping.outlook_event_id

        if outlook_event_id is None:
            error = EventSynchronizationError(
                "Delete-pending calendar mapping has no Outlook event ID: "
                f"mapping_id={mapping.id}"
            )
            self._record_delete_failure(mapping, error)
            raise error

        try:
            self._graph_client.delete_event(
                calendar_id=calendar_id,
                event_id=outlook_event_id,
            )
        except OutlookEventNotFoundError:
            pass
        except Exception as error:
            self._record_delete_failure(mapping, error)
            raise EventSynchronizationError(
                f"Outlook event deletion failed for event {mapping.event_id}."
            ) from error

        try:
            deleted_mapping = self._mappings_repository.mark_deleted(
                mapping_id=mapping.id,
            )
        except Exception as error:
            self._record_delete_failure(mapping, error)
            raise EventSynchronizationError(
                f"Deleted calendar mapping could not be persisted: {mapping.id}"
            ) from error

        if deleted_mapping is None:
            raise EventSynchronizationError(
                f"Calendar mapping disappeared during deletion: {mapping.id}"
            )

        return EventSynchronizationResult(
            status=EventSynchronizationStatus.DELETED,
            event_id=mapping.event_id,
            calendar_id=calendar_id,
            outlook_event_id=outlook_event_id,
            content_hash=mapping.content_hash,
        )

    def _validate_mapping(
        self,
        mapping: CalendarEventMapping,
        event_id: int,
        calendar_id: str,
    ) -> None:
        if mapping.event_id != event_id or mapping.calendar_id != calendar_id:
            raise EventSynchronizationError(
                "Calendar mapping does not belong to the requested event and calendar."
            )

    def _record_failure(
        self,
        mapping: CalendarEventMapping,
        error: Exception,
    ) -> None:
        failed_mapping = self._mappings_repository.mark_failed(
            mapping_id=mapping.id,
            error_message=str(error),
        )

        if failed_mapping is None:
            raise EventSynchronizationError(
                f"Failed calendar mapping could not be persisted: {mapping.id}"
            ) from error

    def _record_delete_failure(
        self,
        mapping: CalendarEventMapping,
        error: Exception,
    ) -> None:
        failed_mapping = self._mappings_repository.mark_delete_failed(
            mapping_id=mapping.id,
            error_message=str(error),
        )

        if failed_mapping is None:
            raise EventSynchronizationError(
                f"Failed calendar deletion could not be persisted: {mapping.id}"
            ) from error
