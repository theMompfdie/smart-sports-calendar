from unittest.mock import Mock, patch

import pytest
from app.database.calendar_event_mappings_repository import (
    CalendarEventMapping,
    CalendarEventMappingsRepository,
)
from app.database.synchronization_query_repository import SynchronizationEvent
from app.graph.client import (
    GraphClient,
    OutlookEventNotFoundError,
    OutlookEventReference,
)
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
    transaction_id: str = "11111111-2222-4333-8444-555555555555",
    outlook_event_id: str | None = "outlook-event-1",
    outlook_change_key: str | None = "change-key-1",
    content_hash: str | None = "old-hash",
    sync_status: str = "synced",
    presentation_revision: int = 1,
    last_synced_presentation_revision: int = 0,
) -> CalendarEventMapping:
    return CalendarEventMapping(
        id=mapping_id,
        event_id=event_id,
        calendar_id=calendar_id,
        transaction_id=transaction_id,
        outlook_event_id=outlook_event_id,
        outlook_change_key=outlook_change_key,
        content_hash=content_hash,
        sync_status=sync_status,
        sync_attempts=1,
        last_synced_at="2026-08-01T12:00:00+00:00",
        last_sync_error=None,
        created_at="2026-08-01T11:00:00+00:00",
        updated_at="2026-08-01T12:00:00+00:00",
        presentation_revision=presentation_revision,
        last_synced_presentation_revision=last_synced_presentation_revision,
    )


def create_synchronization_event(
    *,
    event_id: int = 1,
    status: str = "scheduled",
    deleted_at: str | None = None,
    mapping: CalendarEventMapping | None = None,
) -> SynchronizationEvent:
    synchronization_event = Mock(spec=SynchronizationEvent)
    synchronization_event.event = Mock()
    synchronization_event.event.id = event_id
    synchronization_event.event.status = status
    synchronization_event.event.deleted_at = deleted_at
    synchronization_event.event.sync_revision = 1
    synchronization_event.mapping = mapping

    return synchronization_event


def test_synchronize_event_deletes_confirmed_removed_event() -> None:
    (
        synchronizer,
        _payload,
        payload_builder,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping()
    delete_pending = create_mapping(sync_status="delete_pending")
    deleted = create_mapping(sync_status="deleted")
    mappings_repository.mark_delete_pending.return_value = delete_pending
    mappings_repository.mark_deleted.return_value = deleted
    synchronization_event = create_synchronization_event(
        deleted_at="2026-08-08T16:00:00+00:00",
        mapping=mapping,
    )

    result = synchronizer.synchronize_event(
        synchronization_event=synchronization_event,
        calendar_id="calendar-1",
    )

    assert result.status is EventSynchronizationStatus.DELETED
    mappings_repository.mark_delete_pending.assert_called_once_with(mapping.id)
    graph_client.delete_event.assert_called_once_with(
        calendar_id="calendar-1",
        event_id="outlook-event-1",
    )
    mappings_repository.mark_deleted.assert_called_once_with(mapping_id=mapping.id)
    payload_builder.build.assert_not_called()


def test_synchronize_event_revives_deleted_mapping_for_reappeared_event() -> None:
    (
        synchronizer,
        payload,
        payload_builder,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    deleted = create_mapping(sync_status="deleted")
    revived = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="pending",
    )
    synchronized = create_mapping(content_hash="new-hash")
    mappings_repository.revive_deleted.return_value = revived
    graph_client.create_event.return_value = OutlookEventReference(id="outlook-event-1")
    mappings_repository.mark_synced.return_value = synchronized
    synchronization_event = create_synchronization_event(mapping=deleted)

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="new-hash",
    ):
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status is EventSynchronizationStatus.CREATED
    mappings_repository.revive_deleted.assert_called_once_with(deleted.id)
    payload_builder.build.assert_called_once_with(synchronization_event)
    graph_client.create_event.assert_called_once_with(
        calendar_id="calendar-1",
        payload=payload,
        transaction_id=deleted.transaction_id,
    )
    mappings_repository.mark_synced.assert_called_once_with(
        mapping_id=deleted.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key=None,
        content_hash="new-hash",
        event_revision=1,
        presentation_revision=1,
    )


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
    graph_client.create_event.return_value.id = "outlook-event-1"
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
        transaction_id=pending_mapping.transaction_id,
    )
    mappings_repository.mark_synced.assert_called_once_with(
        mapping_id=pending_mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key=None,
        content_hash="new-hash",
        event_revision=1,
        presentation_revision=1,
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
    mappings_repository.mark_checked.return_value = mapping

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
    mappings_repository.mark_checked.assert_called_once_with(
        mapping.id,
        event_revision=1,
        presentation_revision=1,
    )
    mappings_repository.mark_synced.assert_not_called()
    mappings_repository.mark_failed.assert_not_called()


def test_presentation_drift_with_equal_hash_is_checked_without_graph_update() -> None:
    synchronizer, _, _, graph_client, mappings_repository = create_synchronizer()
    mapping = create_mapping(
        content_hash="current-hash",
        presentation_revision=7,
        last_synced_presentation_revision=6,
    )
    synchronization_event = create_synchronization_event(mapping=mapping)
    mappings_repository.mark_checked.return_value = mapping

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="current-hash",
    ):
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status is EventSynchronizationStatus.UNCHANGED
    graph_client.create_event.assert_not_called()
    graph_client.update_event.assert_not_called()
    mappings_repository.mark_checked.assert_called_once_with(
        mapping.id,
        event_revision=1,
        presentation_revision=7,
    )


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
        event_revision=1,
        presentation_revision=1,
    )
    mappings_repository.mark_failed.assert_not_called()


def test_synchronize_event_skips_cancelled_event_without_mapping() -> None:
    (
        synchronizer,
        _,
        payload_builder,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    synchronization_event = create_synchronization_event(status="cancelled")

    result = synchronizer.synchronize_event(
        synchronization_event=synchronization_event,
        calendar_id="calendar-1",
    )

    assert result.status == EventSynchronizationStatus.CANCELLATION_SKIPPED
    assert result.event_id == 1
    assert result.calendar_id == "calendar-1"
    assert result.outlook_event_id is None
    assert result.content_hash is None

    payload_builder.build.assert_not_called()
    graph_client.create_event.assert_not_called()
    graph_client.update_event.assert_not_called()
    graph_client.delete_event.assert_not_called()
    mappings_repository.create_pending.assert_not_called()


def test_synchronize_event_updates_cancelled_event() -> None:
    (
        synchronizer,
        payload,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(content_hash="old-hash")
    synchronization_event = create_synchronization_event(
        status="cancelled",
        mapping=mapping,
    )

    graph_client.update_event.return_value = OutlookEventReference(id="outlook-event-1")
    mappings_repository.mark_synced.return_value = create_mapping(
        content_hash="cancelled-hash"
    )

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="cancelled-hash",
    ):
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status == EventSynchronizationStatus.CANCELLED
    assert result.event_id == 1
    assert result.outlook_event_id == "outlook-event-1"
    assert result.content_hash == "cancelled-hash"

    graph_client.update_event.assert_called_once_with(
        calendar_id="calendar-1",
        event_id="outlook-event-1",
        payload=payload,
    )
    mappings_repository.mark_synced.assert_called_once_with(
        mapping_id=mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key="change-key-1",
        content_hash="cancelled-hash",
        event_revision=1,
        presentation_revision=1,
    )


def test_synchronize_event_skips_unchanged_cancelled_event() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(content_hash="cancelled-hash")
    synchronization_event = create_synchronization_event(
        status="cancelled",
        mapping=mapping,
    )
    mappings_repository.mark_checked.return_value = mapping

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="cancelled-hash",
    ):
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status == EventSynchronizationStatus.CANCELLED
    assert result.outlook_event_id == "outlook-event-1"
    assert result.content_hash == "cancelled-hash"

    graph_client.update_event.assert_not_called()
    mappings_repository.mark_checked.assert_called_once_with(
        mapping.id,
        event_revision=1,
        presentation_revision=1,
    )
    mappings_repository.mark_synced.assert_not_called()
    mappings_repository.mark_failed.assert_not_called()


def test_synchronize_event_deletes_delete_pending_mapping() -> None:
    (
        synchronizer,
        _,
        payload_builder,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(sync_status="delete_pending")
    synchronization_event = create_synchronization_event(mapping=mapping)

    mappings_repository.mark_deleted.return_value = create_mapping(
        sync_status="deleted"
    )

    result = synchronizer.synchronize_event(
        synchronization_event=synchronization_event,
        calendar_id="calendar-1",
    )

    assert result.status == EventSynchronizationStatus.DELETED
    assert result.event_id == 1
    assert result.calendar_id == "calendar-1"
    assert result.outlook_event_id == "outlook-event-1"
    assert result.content_hash == mapping.content_hash

    graph_client.delete_event.assert_called_once_with(
        calendar_id="calendar-1",
        event_id="outlook-event-1",
    )
    mappings_repository.mark_deleted.assert_called_once_with(
        mapping_id=mapping.id,
    )
    payload_builder.build.assert_not_called()


def test_synchronize_event_treats_missing_outlook_event_as_deleted() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(sync_status="delete_pending")
    synchronization_event = create_synchronization_event(mapping=mapping)

    graph_client.delete_event.side_effect = OutlookEventNotFoundError(
        "Microsoft Graph Outlook event was not found."
    )
    mappings_repository.mark_deleted.return_value = create_mapping(
        sync_status="deleted"
    )

    result = synchronizer.synchronize_event(
        synchronization_event=synchronization_event,
        calendar_id="calendar-1",
    )

    assert result.status == EventSynchronizationStatus.DELETED
    mappings_repository.mark_deleted.assert_called_once_with(
        mapping_id=mapping.id,
    )
    mappings_repository.mark_delete_failed.assert_not_called()


def test_synchronize_event_records_failed_deletion() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(sync_status="delete_pending")
    synchronization_event = create_synchronization_event(mapping=mapping)

    graph_client.delete_event.side_effect = RuntimeError("Graph unavailable")
    mappings_repository.mark_delete_failed.return_value = create_mapping(
        sync_status="delete_pending"
    )

    with pytest.raises(
        EventSynchronizationError,
        match="Outlook event deletion failed for event 1",
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    mappings_repository.mark_delete_failed.assert_called_once_with(
        mapping_id=mapping.id,
        error_message="Graph unavailable",
    )
    mappings_repository.mark_deleted.assert_not_called()


def test_synchronize_event_rejects_delete_pending_mapping_without_event_id() -> None:
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
        sync_status="delete_pending",
    )
    synchronization_event = create_synchronization_event(mapping=mapping)

    mappings_repository.mark_delete_failed.return_value = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        sync_status="delete_pending",
    )

    with pytest.raises(
        EventSynchronizationError,
        match="Delete-pending calendar mapping has no Outlook event ID",
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    graph_client.delete_event.assert_not_called()
    mappings_repository.mark_delete_failed.assert_called_once_with(
        mapping_id=mapping.id,
        error_message=(
            "Delete-pending calendar mapping has no Outlook event ID: "
            f"mapping_id={mapping.id}"
        ),
    )


def test_synchronize_event_records_failed_deleted_state_persistence() -> None:
    (
        synchronizer,
        _,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()
    mapping = create_mapping(sync_status="delete_pending")
    synchronization_event = create_synchronization_event(mapping=mapping)

    mappings_repository.mark_deleted.side_effect = RuntimeError("database unavailable")
    mappings_repository.mark_delete_failed.return_value = create_mapping(
        sync_status="delete_pending"
    )

    with pytest.raises(
        EventSynchronizationError,
        match="Deleted calendar mapping could not be persisted",
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    graph_client.delete_event.assert_called_once()
    mappings_repository.mark_delete_failed.assert_called_once_with(
        mapping_id=mapping.id,
        error_message="database unavailable",
    )


def test_synchronize_event_wraps_payload_builder_error() -> None:
    (
        synchronizer,
        _,
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
    mappings_repository.create_pending.return_value = pending_mapping
    mappings_repository.mark_failed.return_value = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="failed",
    )
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
    mappings_repository.create_pending.assert_called_once_with(
        event_id=1,
        calendar_id="calendar-1",
    )
    mappings_repository.mark_failed.assert_called_once_with(
        mapping_id=pending_mapping.id,
        error_message="invalid event data",
    )


def test_synchronize_event_wraps_content_hash_error() -> None:
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
    mappings_repository.mark_failed.return_value = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="failed",
    )

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
    mappings_repository.create_pending.assert_called_once_with(
        event_id=1,
        calendar_id="calendar-1",
    )
    mappings_repository.mark_failed.assert_called_once_with(
        mapping_id=pending_mapping.id,
        error_message="invalid payload",
    )


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


def test_synchronize_event_rejects_non_retryable_mapping_without_outlook_event_id() -> (
    None
):
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
        sync_status="synced",
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
            match=(
                "Existing calendar mapping has no Outlook event ID "
                "and cannot be retried"
            ),
        ),
    ):
        synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    graph_client.create_event.assert_not_called()
    mappings_repository.create_pending.assert_not_called()
    mappings_repository.mark_pending.assert_not_called()
    mappings_repository.mark_failed.assert_called_once()


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


def test_synchronize_event_retries_failed_mapping_without_outlook_event_id() -> None:
    (
        synchronizer,
        payload,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()

    failed_mapping = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="failed",
    )
    pending_mapping = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="pending",
        transaction_id=failed_mapping.transaction_id,
    )
    synchronized_mapping = create_mapping(content_hash="new-hash")
    synchronization_event = create_synchronization_event(mapping=failed_mapping)

    mappings_repository.mark_pending.return_value = pending_mapping
    graph_client.create_event.return_value.id = "outlook-event-1"
    mappings_repository.mark_synced.return_value = synchronized_mapping

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="new-hash",
    ):
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status == EventSynchronizationStatus.CREATED
    assert result.outlook_event_id == "outlook-event-1"

    mappings_repository.create_pending.assert_not_called()
    mappings_repository.mark_pending.assert_called_once_with(
        mapping_id=failed_mapping.id,
    )
    graph_client.create_event.assert_called_once_with(
        calendar_id="calendar-1",
        payload=payload,
        transaction_id=failed_mapping.transaction_id,
    )
    mappings_repository.mark_synced.assert_called_once_with(
        mapping_id=failed_mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key=None,
        content_hash="new-hash",
        event_revision=1,
        presentation_revision=1,
    )


def test_synchronize_event_reuses_pending_mapping_without_outlook_event_id() -> None:
    (
        synchronizer,
        payload,
        _,
        graph_client,
        mappings_repository,
    ) = create_synchronizer()

    pending_mapping = create_mapping(
        outlook_event_id=None,
        outlook_change_key=None,
        content_hash=None,
        sync_status="pending",
    )
    synchronized_mapping = create_mapping(content_hash="new-hash")
    synchronization_event = create_synchronization_event(mapping=pending_mapping)

    graph_client.create_event.return_value.id = "outlook-event-1"
    mappings_repository.mark_synced.return_value = synchronized_mapping

    with patch(
        "app.synchronization.event_synchronizer.calculate_content_hash",
        return_value="new-hash",
    ):
        result = synchronizer.synchronize_event(
            synchronization_event=synchronization_event,
            calendar_id="calendar-1",
        )

    assert result.status == EventSynchronizationStatus.CREATED

    mappings_repository.create_pending.assert_not_called()
    mappings_repository.mark_pending.assert_not_called()
    graph_client.create_event.assert_called_once_with(
        calendar_id="calendar-1",
        payload=payload,
        transaction_id=pending_mapping.transaction_id,
    )
    mappings_repository.mark_synced.assert_called_once_with(
        mapping_id=pending_mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key=None,
        content_hash="new-hash",
        event_revision=1,
        presentation_revision=1,
    )
