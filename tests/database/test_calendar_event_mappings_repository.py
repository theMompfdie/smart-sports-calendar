import sqlite3
from pathlib import Path
from uuid import UUID

import pytest
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.database import Database
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[int, CalendarEventMappingsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )

    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        event_key="premier_league_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-21T19:00:00+00:00",
    )

    return (
        event.id,
        CalendarEventMappingsRepository(database_path),
    )


def test_get_by_id_returns_none_for_unknown_mapping(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    mapping = repository.get_by_id(999999)

    assert mapping is None


def test_get_by_event_returns_none_for_unknown_mapping(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    mapping = repository.get_by_event(
        event_id=event_id,
        calendar_id="calendar-1",
    )

    assert mapping is None


def test_get_by_outlook_event_returns_none_for_unknown_mapping(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    mapping = repository.get_by_outlook_event(
        calendar_id="calendar-1",
        outlook_event_id="outlook-event-1",
    )

    assert mapping is None


def test_create_pending_creates_mapping(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
        content_hash="hash-1",
    )

    assert mapping.id > 0
    assert mapping.event_id == event_id
    assert mapping.calendar_id == "calendar-1"
    assert str(UUID(mapping.transaction_id)) == mapping.transaction_id
    assert mapping.outlook_event_id is None
    assert mapping.outlook_change_key is None
    assert mapping.content_hash == "hash-1"
    assert mapping.sync_status == "pending"
    assert mapping.sync_attempts == 0
    assert mapping.last_synced_at is None
    assert mapping.last_sync_error is None
    assert mapping.created_at
    assert mapping.updated_at


def test_get_by_event_returns_existing_mapping(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )

    loaded_mapping = repository.get_by_event(
        event_id=event_id,
        calendar_id="calendar-1",
    )

    assert loaded_mapping == created_mapping


def test_mark_synced_updates_mapping(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
        content_hash="old-hash",
    )

    synced_mapping = repository.mark_synced(
        mapping_id=created_mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key="change-key-1",
        content_hash="new-hash",
    )

    assert synced_mapping is not None
    assert synced_mapping.id == created_mapping.id
    assert synced_mapping.outlook_event_id == "outlook-event-1"
    assert synced_mapping.outlook_change_key == "change-key-1"
    assert synced_mapping.content_hash == "new-hash"
    assert synced_mapping.sync_status == "synced"
    assert synced_mapping.sync_attempts == 1
    assert synced_mapping.last_synced_at is not None
    assert synced_mapping.last_sync_error is None
    assert synced_mapping.created_at == created_mapping.created_at
    assert synced_mapping.updated_at >= created_mapping.updated_at


def test_get_by_outlook_event_returns_synced_mapping(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )
    synced_mapping = repository.mark_synced(
        mapping_id=created_mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key="change-key-1",
        content_hash="hash-1",
    )

    loaded_mapping = repository.get_by_outlook_event(
        calendar_id="calendar-1",
        outlook_event_id="outlook-event-1",
    )

    assert loaded_mapping == synced_mapping


def test_mark_failed_records_error_and_attempt(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )

    failed_mapping = repository.mark_failed(
        mapping_id=created_mapping.id,
        error_message="Microsoft Graph request failed",
    )

    assert failed_mapping is not None
    assert failed_mapping.sync_status == "failed"
    assert failed_mapping.sync_attempts == 1
    assert failed_mapping.last_sync_error == "Microsoft Graph request failed"
    assert failed_mapping.last_synced_at is None
    assert failed_mapping.transaction_id == created_mapping.transaction_id


def test_mark_pending_prepares_failed_mapping_for_retry(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )
    failed_mapping = repository.mark_failed(
        mapping_id=created_mapping.id,
        error_message="Temporary error",
    )

    assert failed_mapping is not None

    pending_mapping = repository.mark_pending(
        mapping_id=failed_mapping.id,
        content_hash="retry-hash",
    )

    assert pending_mapping is not None
    assert pending_mapping.sync_status == "pending"
    assert pending_mapping.sync_attempts == 1
    assert pending_mapping.content_hash == "retry-hash"
    assert pending_mapping.last_sync_error is None
    assert failed_mapping.transaction_id == created_mapping.transaction_id
    assert pending_mapping.transaction_id == created_mapping.transaction_id


def test_mark_delete_pending_updates_status(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )

    mapping = repository.mark_delete_pending(created_mapping.id)

    assert mapping is not None
    assert mapping.sync_status == "delete_pending"
    assert mapping.sync_attempts == 0


def test_mark_deleted_preserves_mapping_as_history(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )
    synced_mapping = repository.mark_synced(
        mapping_id=created_mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key="change-key-1",
        content_hash="hash-1",
    )

    assert synced_mapping is not None

    deleted_mapping = repository.mark_deleted(synced_mapping.id)

    assert deleted_mapping is not None
    assert deleted_mapping.sync_status == "deleted"
    assert deleted_mapping.sync_attempts == 2
    assert deleted_mapping.outlook_event_id == "outlook-event-1"
    assert deleted_mapping.outlook_change_key is None
    assert deleted_mapping.last_sync_error is None
    assert repository.get_by_id(synced_mapping.id) == deleted_mapping


def test_revive_deleted_preserves_mapping_and_transaction_identity(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)
    pending = repository.create_pending(event_id, "calendar-1")
    synced = repository.mark_synced(
        mapping_id=pending.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key="change-key-1",
        content_hash="hash-1",
    )
    assert synced is not None
    deleted = repository.mark_deleted(synced.id)
    assert deleted is not None

    revived = repository.revive_deleted(deleted.id)

    assert revived is not None
    assert revived.id == deleted.id
    assert revived.event_id == deleted.event_id
    assert revived.calendar_id == deleted.calendar_id
    assert revived.transaction_id == deleted.transaction_id
    assert revived.sync_status == "pending"
    assert revived.outlook_event_id is None
    assert revived.outlook_change_key is None
    assert revived.content_hash is None
    assert revived.last_sync_error is None


def test_get_by_status_returns_only_matching_mappings(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    pending_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )
    failed_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-2",
    )
    repository.mark_failed(
        mapping_id=failed_mapping.id,
        error_message="Temporary error",
    )

    mappings = repository.get_by_status("pending")

    assert mappings == [pending_mapping]


def test_create_pending_rejects_duplicate_event_and_calendar(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.create_pending(
            event_id=event_id,
            calendar_id="calendar-1",
        )


def test_mark_synced_rejects_duplicate_outlook_event(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    sport = SportsRepository(repository.database_path).upsert(
        sport_key="football",
        name="Football",
    )
    second_event = SportsEventsRepository(repository.database_path).upsert(
        sport_id=sport.id,
        event_key="premier_league_chelsea_manchester_city",
        event_type="match",
        title="Chelsea vs Manchester City",
        start_time="2026-08-22T16:30:00+00:00",
    )

    first_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )
    second_mapping = repository.create_pending(
        event_id=second_event.id,
        calendar_id="calendar-1",
    )

    repository.mark_synced(
        mapping_id=first_mapping.id,
        outlook_event_id="outlook-event-1",
        outlook_change_key=None,
        content_hash="hash-1",
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.mark_synced(
            mapping_id=second_mapping.id,
            outlook_event_id="outlook-event-1",
            outlook_change_key=None,
            content_hash="hash-2",
        )


def test_create_pending_rejects_unknown_event(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.create_pending(
            event_id=999999,
            calendar_id="calendar-1",
        )


def test_status_updates_return_none_for_unknown_mapping(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    assert repository.mark_pending(999999) is None
    assert (
        repository.mark_synced(
            mapping_id=999999,
            outlook_event_id="outlook-event-1",
            outlook_change_key=None,
            content_hash="hash-1",
        )
        is None
    )
    assert repository.mark_failed(999999, "error") is None
    assert repository.mark_delete_pending(999999) is None
    assert repository.mark_delete_failed(999999, "error") is None
    assert repository.mark_deleted(999999) is None
    assert repository.revive_deleted(999999) is None


def test_delete_removes_existing_mapping(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )

    deleted = repository.delete(created_mapping.id)

    assert deleted is True
    assert repository.get_by_id(created_mapping.id) is None


def test_delete_returns_false_for_unknown_mapping(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    deleted = repository.delete(999999)

    assert deleted is False


def test_mark_delete_failed_preserves_delete_pending_state(
    tmp_path: Path,
) -> None:
    event_id, repository = create_repository(tmp_path)

    created_mapping = repository.create_pending(
        event_id=event_id,
        calendar_id="calendar-1",
    )

    delete_pending_mapping = repository.mark_delete_pending(
        created_mapping.id,
    )

    assert delete_pending_mapping is not None
    assert delete_pending_mapping.sync_status == "delete_pending"

    failed_mapping = repository.mark_delete_failed(
        mapping_id=delete_pending_mapping.id,
        error_message="Microsoft Graph could not be reached.",
    )

    assert failed_mapping is not None
    assert failed_mapping.sync_status == "delete_pending"
    assert failed_mapping.sync_attempts == (delete_pending_mapping.sync_attempts + 1)
    assert failed_mapping.last_sync_error == ("Microsoft Graph could not be reached.")
