from dataclasses import dataclass
from enum import StrEnum

from app.database.calendar_event_mappings_repository import (
    CalendarEventMapping,
    CalendarEventMappingsRepository,
)
from app.database.synchronization_query_repository import SynchronizationEvent
from app.graph.client import GraphClient
from app.synchronization.content_hash import calculate_content_hash
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayload,
    OutlookEventPayloadBuilder,
)


class EventSynchronizationStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class EventSynchronizationResult:
    status: EventSynchronizationStatus
    event_id: int
    calendar_id: str
    outlook_event_id: str
    content_hash: str


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

        if event.status.casefold() == "cancelled":
            raise EventSynchronizationError(
                "Cancelled events are not processed by single-event synchronization."
            )

        try:
            payload = self._payload_builder.build(synchronization_event)
            content_hash = calculate_content_hash(payload)
        except Exception as error:
            raise EventSynchronizationError(
                f"Outlook payload preparation failed for event {event.id}."
            ) from error

        mapping = synchronization_event.mapping

        if mapping is None:
            return self._create_event(
                event_id=event.id,
                calendar_id=calendar_id,
                payload=payload,
                content_hash=content_hash,
            )

        self._validate_mapping(
            mapping=mapping,
            event_id=event.id,
            calendar_id=calendar_id,
        )

        if mapping.outlook_event_id is None:
            error = EventSynchronizationError(
                "Existing calendar mapping has no Outlook event ID: "
                f"mapping_id={mapping.id}"
            )
            self._record_failure(mapping, error)
            raise error

        if mapping.content_hash == content_hash:
            return EventSynchronizationResult(
                status=EventSynchronizationStatus.UNCHANGED,
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
        )

    def _create_event(
        self,
        event_id: int,
        calendar_id: str,
        payload: OutlookEventPayload,
        content_hash: str,
    ) -> EventSynchronizationResult:
        try:
            mapping = self._mappings_repository.create_pending(
                event_id=event_id,
                calendar_id=calendar_id,
            )
        except Exception as error:
            raise EventSynchronizationError(
                f"Pending calendar mapping could not be created for event {event_id}."
            ) from error

        try:
            event_reference = self._graph_client.create_event(
                calendar_id=calendar_id,
                payload=payload,
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
            status=EventSynchronizationStatus.UPDATED,
            event_id=mapping.event_id,
            calendar_id=calendar_id,
            outlook_event_id=event_reference.id,
            content_hash=content_hash,
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
