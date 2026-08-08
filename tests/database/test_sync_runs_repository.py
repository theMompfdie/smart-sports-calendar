import sqlite3
from pathlib import Path

import pytest
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.sync_runs_repository import SyncRunsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[int, SyncRunsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    source = DataSourcesRepository(database_path).upsert(
        source_key="football_data",
        name="football-data.org",
        base_url="https://api.football-data.org/v4",
    )

    return source.id, SyncRunsRepository(database_path)


def test_get_by_id_returns_none_for_unknown_run(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sync_run = repository.get_by_id(999999)

    assert sync_run is None


def test_start_creates_running_sync_run(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="full_sync",
    )

    assert sync_run.id > 0
    assert sync_run.run_type == "full_sync"
    assert sync_run.source_id is None
    assert sync_run.started_at
    assert sync_run.finished_at is None
    assert sync_run.status == "running"
    assert sync_run.items_processed == 0
    assert sync_run.items_created == 0
    assert sync_run.items_updated == 0
    assert sync_run.items_unchanged == 0
    assert sync_run.items_cancelled == 0
    assert sync_run.items_deleted == 0
    assert sync_run.items_deferred == 0
    assert sync_run.items_failed == 0
    assert sync_run.error_message is None
    assert sync_run.metadata is None


def test_start_creates_provider_import_with_metadata(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="provider_import",
        source_id=source_id,
        metadata={
            "competition": "PL",
            "season": "2026",
        },
    )

    assert sync_run.run_type == "provider_import"
    assert sync_run.source_id == source_id
    assert sync_run.metadata == {
        "competition": "PL",
        "season": "2026",
    }


def test_start_rejects_unknown_source(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.start(
            run_type="import",
            source_id=999999,
        )


def test_start_rejects_unknown_run_type(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.start(
            run_type="unknown",
        )


def test_update_progress_updates_running_sync_run(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="import",
        source_id=source_id,
    )

    updated_run = repository.update_progress(
        sync_run_id=sync_run.id,
        items_processed=10,
        items_created=4,
        items_updated=3,
        items_unchanged=1,
        items_cancelled=2,
        items_deleted=1,
        items_failed=2,
    )

    assert updated_run is not None
    assert updated_run.status == "running"
    assert updated_run.finished_at is None
    assert updated_run.items_processed == 10
    assert updated_run.items_created == 4
    assert updated_run.items_updated == 3
    assert updated_run.items_unchanged == 1
    assert updated_run.items_cancelled == 2
    assert updated_run.items_deleted == 1
    assert updated_run.items_failed == 2


def test_update_progress_returns_none_for_unknown_run(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    updated_run = repository.update_progress(
        sync_run_id=999999,
        items_processed=1,
        items_created=1,
        items_updated=0,
        items_deleted=0,
        items_failed=0,
    )

    assert updated_run is None


def test_update_progress_rejects_negative_counters(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="calendar_sync",
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.update_progress(
            sync_run_id=sync_run.id,
            items_processed=-1,
            items_created=0,
            items_updated=0,
            items_deleted=0,
            items_failed=0,
        )


def test_complete_marks_run_as_completed(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="import",
        source_id=source_id,
    )

    completed_run = repository.complete(
        sync_run_id=sync_run.id,
        items_processed=10,
        items_created=4,
        items_updated=5,
        items_unchanged=2,
        items_cancelled=1,
        items_deleted=1,
        items_failed=0,
        metadata={"request_count": 3},
    )

    assert completed_run is not None
    assert completed_run.status == "completed"
    assert completed_run.finished_at is not None
    assert completed_run.finished_at >= completed_run.started_at
    assert completed_run.items_processed == 10
    assert completed_run.items_created == 4
    assert completed_run.items_updated == 5
    assert completed_run.items_unchanged == 2
    assert completed_run.items_cancelled == 1
    assert completed_run.items_deleted == 1
    assert completed_run.items_failed == 0
    assert completed_run.error_message is None
    assert completed_run.metadata == {"request_count": 3}


def test_complete_marks_run_as_completed_with_errors(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="calendar_sync",
    )

    completed_run = repository.complete(
        sync_run_id=sync_run.id,
        items_processed=10,
        items_created=5,
        items_updated=3,
        items_deleted=0,
        items_failed=2,
    )

    assert completed_run is not None
    assert completed_run.status == "completed_with_errors"
    assert completed_run.finished_at is not None
    assert completed_run.items_failed == 2
    assert completed_run.error_message is None


def test_fail_marks_run_as_failed(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="import",
        source_id=source_id,
    )

    failed_run = repository.fail(
        sync_run_id=sync_run.id,
        error_message="Provider request failed",
        items_processed=5,
        items_created=2,
        items_updated=1,
        items_unchanged=1,
        items_cancelled=1,
        items_deleted=0,
        items_failed=2,
        metadata={"http_status": 503},
    )

    assert failed_run is not None
    assert failed_run.status == "failed"
    assert failed_run.finished_at is not None
    assert failed_run.items_processed == 5
    assert failed_run.items_created == 2
    assert failed_run.items_updated == 1
    assert failed_run.items_unchanged == 1
    assert failed_run.items_cancelled == 1
    assert failed_run.items_deleted == 0
    assert failed_run.items_failed == 2
    assert failed_run.error_message == "Provider request failed"
    assert failed_run.metadata == {"http_status": 503}


def test_completed_run_cannot_be_updated_again(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="full_sync",
    )
    completed_run = repository.complete(
        sync_run_id=sync_run.id,
        items_processed=1,
        items_created=1,
        items_updated=0,
        items_deleted=0,
        items_failed=0,
    )

    assert completed_run is not None

    updated_run = repository.update_progress(
        sync_run_id=sync_run.id,
        items_processed=2,
        items_created=2,
        items_updated=0,
        items_deleted=0,
        items_failed=0,
    )
    second_completion = repository.complete(
        sync_run_id=sync_run.id,
        items_processed=2,
        items_created=2,
        items_updated=0,
        items_deleted=0,
        items_failed=0,
    )
    failed_run = repository.fail(
        sync_run_id=sync_run.id,
        error_message="Late failure",
    )

    assert updated_run is None
    assert second_completion is None
    assert failed_run is None
    assert repository.get_by_id(sync_run.id) == completed_run


def test_get_by_status_returns_only_matching_runs(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    running_run = repository.start(
        run_type="calendar_sync",
    )
    failed_run = repository.start(
        run_type="full_sync",
    )
    repository.fail(
        sync_run_id=failed_run.id,
        error_message="Synchronization failed",
    )

    sync_runs = repository.get_by_status("running")

    assert sync_runs == [running_run]


def test_get_recent_returns_runs_in_reverse_creation_order(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    first_run = repository.start(
        run_type="calendar_sync",
    )
    second_run = repository.start(
        run_type="full_sync",
    )
    third_run = repository.start(
        run_type="calendar_sync",
    )

    sync_runs = repository.get_recent(limit=2)

    assert sync_runs == [
        third_run,
        second_run,
    ]
    assert first_run not in sync_runs


def test_get_recent_can_filter_by_run_type(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    repository.start(
        run_type="calendar_sync",
    )
    expected_run = repository.start(
        run_type="full_sync",
    )

    sync_runs = repository.get_recent(
        run_type="full_sync",
    )

    assert sync_runs == [expected_run]


def test_get_recent_can_filter_by_source(
    tmp_path: Path,
) -> None:
    source_id, repository = create_repository(tmp_path)

    provider_run = repository.start(
        run_type="import",
        source_id=source_id,
    )
    repository.start(
        run_type="full_sync",
    )

    sync_runs = repository.get_recent(
        source_id=source_id,
    )

    assert sync_runs == [provider_run]


def test_get_recent_rejects_non_positive_limit(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    with pytest.raises(
        ValueError,
        match="limit must be greater than zero",
    ):
        repository.get_recent(limit=0)


def test_finish_methods_return_none_for_unknown_run(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    completed_run = repository.complete(
        sync_run_id=999999,
        items_processed=0,
        items_created=0,
        items_updated=0,
        items_deleted=0,
        items_failed=0,
    )
    failed_run = repository.fail(
        sync_run_id=999999,
        error_message="Unknown run",
    )

    assert completed_run is None
    assert failed_run is None


def test_delete_removes_existing_run(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="full_sync",
    )

    deleted = repository.delete(sync_run.id)

    assert deleted is True
    assert repository.get_by_id(sync_run.id) is None


def test_delete_returns_false_for_unknown_run(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    deleted = repository.delete(999999)

    assert deleted is False


def test_recover_running_marks_matching_runs_as_failed(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    first_run = repository.start(
        run_type="calendar_sync",
        metadata={"calendar_id": "calendar-1"},
    )
    second_run = repository.start(
        run_type="calendar_sync",
        metadata={"calendar_id": "calendar-2"},
    )

    repository.update_progress(
        sync_run_id=first_run.id,
        items_processed=3,
        items_created=1,
        items_updated=1,
        items_unchanged=1,
        items_cancelled=0,
        items_deleted=0,
        items_failed=0,
    )

    recovered_runs = repository.recover_running(
        run_type="calendar_sync",
        error_message="Interrupted synchronization run recovered.",
    )

    assert [run.id for run in recovered_runs] == [
        first_run.id,
        second_run.id,
    ]

    recovered_first_run = recovered_runs[0]

    assert recovered_first_run.status == "failed"
    assert recovered_first_run.finished_at is not None
    assert recovered_first_run.error_message == (
        "Interrupted synchronization run recovered."
    )
    assert recovered_first_run.items_processed == 3
    assert recovered_first_run.items_created == 1
    assert recovered_first_run.items_updated == 1
    assert recovered_first_run.items_unchanged == 1
    assert recovered_first_run.metadata == {
        "calendar_id": "calendar-1",
    }


def test_recover_running_does_not_modify_other_or_terminal_runs(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    other_run = repository.start(
        run_type="provider_import",
    )
    completed_run = repository.start(
        run_type="calendar_sync",
    )
    failed_run = repository.start(
        run_type="calendar_sync",
    )

    completed_run = repository.complete(
        sync_run_id=completed_run.id,
        items_processed=1,
        items_created=1,
        items_updated=0,
        items_deleted=0,
        items_failed=0,
    )
    failed_run = repository.fail(
        sync_run_id=failed_run.id,
        error_message="Existing failure",
    )

    recovered_runs = repository.recover_running(
        run_type="calendar_sync",
        error_message="Interrupted synchronization run recovered.",
    )

    assert recovered_runs == []
    assert repository.get_by_id(other_run.id) == other_run
    assert repository.get_by_id(completed_run.id) == completed_run
    assert repository.get_by_id(failed_run.id) == failed_run


def test_recover_running_is_idempotent(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sync_run = repository.start(
        run_type="calendar_sync",
    )

    first_recovery = repository.recover_running(
        run_type="calendar_sync",
        error_message="Interrupted synchronization run recovered.",
    )
    second_recovery = repository.recover_running(
        run_type="calendar_sync",
        error_message="Interrupted synchronization run recovered.",
    )

    assert [run.id for run in first_recovery] == [sync_run.id]
    assert second_recovery == []


@pytest.mark.parametrize(
    ("run_type", "error_message", "expected_message"),
    [
        ("", "Recovery failure", "run_type must not be empty"),
        ("calendar_sync", "", "error_message must not be empty"),
    ],
)
def test_recover_running_rejects_empty_arguments(
    tmp_path: Path,
    run_type: str,
    error_message: str,
    expected_message: str,
) -> None:
    _, repository = create_repository(tmp_path)

    with pytest.raises(ValueError, match=expected_message):
        repository.recover_running(
            run_type=run_type,
            error_message=error_message,
        )
