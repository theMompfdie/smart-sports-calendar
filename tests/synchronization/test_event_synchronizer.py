from unittest.mock import Mock, patch

import pytest
from app.database.calendar_event_mappings_repository import (
    CalendarEventMapping,
    CalendarEventMappingsRepository,
)
from app.database.synchronization_query_repository import SynchronizationEvent
from app.graph.client import GraphClient, OutlookEventReference
from app.synchronization.event_synchronizer import (
    EventSynchronizationError,
    EventSynchronizationStatus,
    EventSynchronizer,
)
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayload,
    OutlookEventPayloadBuilder,
)


def create_mapping(
    *,
    mapping_id: int = 10,
    event_id: int = 1,
    calendar_id: str = "calendar-1",
    outlook_event_id: str | None = "outlook-event-1",
    outlook_change_key: str | None = "change-key-1",
    content_hash: str | None = "old-hash",
    sync_status: str = "synced",
) -> CalendarEventMapping:
    return CalendarEventMapping(
        id=mapping_id,
        event_id=event_id,
        calendar_id=calendar_id,
        outlook_event_id=outlook_event_id,
        outlook_change_key=outlook_change_key,
        content_hash=content_hash,
        sync_status=sync_status,
        sync_attempts=1,
        last_synced_at="2026-08-01T12:00:00+00:00",
        last_sync_error=None,
        created_at="2026-08-01T11:00:00+00:00",
        updated_at="2026-08-01T12:00:00+00:00",
    )


def create_synchronization_event(
    *,
    event_id: int = 1,
    status: str = "scheduled",
    mapping: CalendarEventMapping | None = None,
) -> SynchronizationEvent:
    synchronization_event = Mock(spec=SynchronizationEvent)
    synchronization_event.event = Mock()
    synchronization_event.event.id = event_id
    synchronization_event.event.status = status
    synchronization_event.mapping = mapping

    return synchronization_event


def create_synchronizer() -> tuple[
    EventSynchronizer,
    Mock,
    Mock,
    Mock,
    Mock,
]:
    payload = Mock(spec=OutlookEventPayload)
    payload_builder = Mock(spec=OutlookEventPayloadBuilder)
    payload_builder.build.return_value = payload

    graph_client = Mock(spec=GraphClient)
    mappings_repository = Mock(spec=CalendarEventMappingsRepository)

    synchronizer = EventSynchronizer(
        payload_builder=payload_builder,
        graph_client=graph_client,
        mappings_repository=mappings_repository,
    )

    return (
        synchronizer,
        payload,
        payload_builder,
        graph_client,
        mappings_repository,
    )


def test_synchronize_event_creates_event_without_existing_mapping() -> None:
    (
        synchronizer,
        payload,
        payload_builder,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    synchronization_event = create_synchronization_event()

    pending_mapping = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="pending",
    )
    synchronized_mapping = create_mapping(content_hash="new-hash")

    mappings_repository.create_pending.return_value = pending_mapping
    graph_client.create_event.return_value = OutlookEventReference(id="outlook-event-1")
    mappings_repository.mark_synced.return_value = synchronized_mapping

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="new-hash",
    ) as calculate_hash:
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status == EventSynchronizationStatus.CREATED
    assert result.event_id == 1
    assert result.calendar_id == "calendar-1"
    assert result.outlook_event_id == "outlook-event-1"
    assert result.content_hash == "new-hash"

    payload_builder.build.assert_called_once_with(synchronization_event)
    calculate_hash.assert_called_once_with(payload)
    mappings_repository.create_pending.assert_called_once_with(
        event_id=1,
        calendar_id="calendar-1",
    )
    graph_client.create_event.assert_called_once_with(
        calendar_id="calendar-1",
        payload=payload,
    )
    mappings_repository.mark_synced.assert_called_once_with(
        mapping_id=pending_mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key=None,
        content_hash="new-hash",
    )
    mappings_repository.mark_failed.assert_not_called()


def test_synchronize_event_returns_unchanged_for_equal_content_hash() -> None:
    (
        synchronizer,
        payload,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(content_hash="current-hash")
    synchronization_event = create_synchronization_event(mapping=mapping)

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="current-hash",
    ) as calculate_hash:
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status == EventSynchronizationStatus.UNCHANGED
    assert result.event_id == 1
    assert result.calendar_id == "calendar-1"
    assert result.outlook_event_id == "outlook-event-1"
    assert result.content_hash == "current-hash"

    calculate_hash.assert_called_once_with(payload)
    graph_client.create_event.assert_not_called()
    graph_client.update_event.assert_not_called()
    mappings_repository.create_pending.assert_not_called()
    mappings_repository.mark_synced.assert_not_called()
    mappings_repository.mark_failed.assert_not_called()


def test_synchronize_event_updates_changed_event() -> None:
    (
        synchronizer,
        payload,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(content_hash="old-hash")
    synchronization_event = create_synchronization_event(mapping=mapping)

    graph_client.update_event.return_value = OutlookEventReference(id="outlook-event-1")
    mappings_repository.mark_synced.return_value = create_mapping(
        content_hash="new-hash"
    )

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="new-hash",
    ):
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status == EventSynchronizationStatus.UPDATED
    assert result.event_id == 1
    assert result.calendar_id == "calendar-1"
    assert result.outlook_event_id == "outlook-event-1"
    assert result.content_hash == "new-hash"

    graph_client.update_event.assert_called_once_with(
        calendar_id="calendar-1",
        event_id="outlook-event-1",
        payload=payload,
    )
    mappings_repository.mark_synced.assert_called_once_with(
        mapping_id=mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key="change-key-1",
        content_hash="new-hash",
    )
    mappings_repository.mark_failed.assert_not_called()


def test_synchronize_event_rejects_cancelled_event() -> None:
    (
        synchronizer,
        _,
        payload_builder,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    synchronization_event = create_synchronization_event(status="cancelled")

    with pytest.raises(
        EventSynchronizationError,
        match="Cancelled events are not processed",
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    payload_builder.build.assert_not_called()
    graph_client.create_event.assert_not_called()
    graph_client.update_event.assert_not_called()
    mappings_repository.create_pending.assert_not_called()


def test_synchronize_event_wraps_payload_builder_error() -> None:
    (
        synchronizer,
        _,
        payload_builder,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    synchronization_event = create_synchronization_event()
    payload_builder.build.side_effect = ValueError("invalid event data")

    with pytest.raises(
        EventSynchronizationError,
        match="Outlook payload preparation failed for event 1",
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    graph_client.create_event.assert_not_called()
    graph_client.update_event.assert_not_called()
    mappings_repository.create_pending.assert_not_called()


def test_synchronize_event_wraps_content_hash_error() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    synchronization_event = create_synchronization_event()

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            side_effect=TypeError("invalid payload"),
        ),
        pytest.raises(
            EventSynchronizationError,
            match="Outlook payload preparation failed for event 1",
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    graph_client.create_event.assert_not_called()
    graph_client.update_event.assert_not_called()
    mappings_repository.create_pending.assert_not_called()


def test_synchronize_event_wraps_pending_mapping_creation_error() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    synchronization_event = create_synchronization_event()
    mappings_repository.create_pending.side_effect = RuntimeError(
        "database unavailable"
    )

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            return_value="new-hash",
        ),
        pytest.raises(
            EventSynchronizationError,
            match="Pending calendar mapping could not be created for event 1",
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    graph_client.create_event.assert_not_called()
    mappings_repository.mark_synced.assert_not_called()
    mappings_repository.mark_failed.assert_not_called()


def test_synchronize_event_records_failed_creation() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    synchronization_event = create_synchronization_event()
    pending_mapping = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="pending",
    )

    mappings_repository.create_pending.return_value = pending_mapping
    graph_client.create_event.side_effect = RuntimeError("Graph unavailable")
    mappings_repository.mark_failed.return_value = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="failed",
    )

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            return_value="new-hash",
        ),
        pytest.raises(
            EventSynchronizationError,
            match="Outlook event creation failed for event 1",
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    mappings_repository.mark_failed.assert_called_once_with(
        mapping_id=pending_mapping.id,
        error_message="Graph unavailable",
    )
    mappings_repository.mark_synced.assert_not_called()


def test_synchronize_event_records_failed_update() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(content_hash="old-hash")
    synchronization_event = create_synchronization_event(mapping=mapping)

    graph_client.update_event.side_effect = RuntimeError("Graph unavailable")
    mappings_repository.mark_failed.return_value = create_mapping(
        content_hash="old-hash",
        sync_status="failed",
    )

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            return_value="new-hash",
        ),
        pytest.raises(
            EventSynchronizationError,
            match="Outlook event update failed for event 1",
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    mappings_repository.mark_failed.assert_called_once_with(
        mapping_id=mapping.id,
        error_message="Graph unavailable",
    )
    mappings_repository.mark_synced.assert_not_called()


def test_synchronize_event_rejects_mapping_without_outlook_event_id() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash="old-hash",
        sync_status="pending",
    )
    synchronization_event = create_synchronization_event(mapping=mapping)

    mappings_repository.mark_failed.return_value = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash="old-hash",
        sync_status="failed",
    )

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            return_value="new-hash",
        ),
        pytest.raises(
            EventSynchronizationError,
            match="Existing calendar mapping has no Outlook event ID",
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    mappings_repository.mark_failed.assert_called_once_with(
        mapping_id=mapping.id,
        error_message=(
            "Existing calendar mapping has no Outlook event ID: "
            f"mapping_id={mapping.id}"
        ),
    )
    graph_client.update_event.assert_not_called()


@pytest.mark.parametrize(
    ("mapping_event_id", "mapping_calendar_id"),
    [
        (2, "calendar-1"),
        (1, "calendar-2"),
    ],
)
def test_synchronize_event_rejects_mapping_for_different_target(
    mapping_event_id: int,
    mapping_calendar_id: str,
) -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(
        event_id=mapping_event_id,
        calendar_id=mapping_calendar_id,
    )
    synchronization_event = create_synchronization_event(mapping=mapping)

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            return_value="new-hash",
        ),
        pytest.raises(
            EventSynchronizationError,
            match=(
                "Calendar mapping does not belong to the requested event and calendar"
            ),
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    graph_client.update_event.assert_not_called()
    mappings_repository.mark_synced.assert_not_called()
    mappings_repository.mark_failed.assert_not_called()


def test_synchronize_event_rejects_changed_event_id_from_graph_update() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(content_hash="old-hash")
    synchronization_event = create_synchronization_event(mapping=mapping)

    graph_client.update_event.return_value = OutlookEventReference(
        id="different-outlook-event"
    )
    mappings_repository.mark_failed.return_value = create_mapping(
        content_hash="old-hash",
        sync_status="failed",
    )

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            return_value="new-hash",
        ),
        pytest.raises(
            EventSynchronizationError,
            match="different event ID during update",
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    mappings_repository.mark_failed.assert_called_once_with(
        mapping_id=mapping.id,
        error_message=("Microsoft Graph returned a different event ID during update."),
    )
    mappings_repository.mark_synced.assert_not_called()


@pytest.mark.parametrize("operation", ["create", "update"])
def test_synchronize_event_rejects_disappearing_mapping(
    operation: str,
) -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()

    if operation == "create":
        mapping = create_mapping(
            outlook_event_id=None,
            outlook_change_key=None,
            content_hash=None,
            sync_status="pending",
        )
        synchronization_event = create_synchronization_event(mapping=None)
        mappings_repository.create_pending.return_value = mapping
        graph_client.create_event.return_value = OutlookEventReference(
            id="outlook-event-1"
        )
    else:
        mapping = create_mapping(content_hash="old-hash")
        synchronization_event = create_synchronization_event(mapping=mapping)
        graph_client.update_event.return_value = OutlookEventReference(
            id="outlook-event-1"
        )

    mappings_repository.mark_synced.return_value = None
    mappings_repository.mark_failed.return_value = create_mapping(sync_status="failed")

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            return_value="new-hash",
        ),
        pytest.raises(
            EventSynchronizationError,
            match="Calendar mapping disappeared during synchronization",
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    mappings_repository.mark_failed.assert_called_once()


def test_synchronize_event_raises_when_failure_cannot_be_persisted() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(content_hash="old-hash")
    synchronization_event = create_synchronization_event(mapping=mapping)

    graph_client.update_event.side_effect = RuntimeError("Graph unavailable")
    mappings_repository.mark_failed.return_value = None

    with (
        patch(
            "app.synchronization.event_synchronizer.calculate_content_hash",
            return_value="new-hash",
        ),
        pytest.raises(
            EventSynchronizationError,
            match="Failed calendar mapping could not be persisted",
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )
