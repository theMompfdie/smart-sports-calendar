from unittest.mock import MagicMock, call

import pytest
from app.database.sync_runs_repository import SyncRun, SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.synchronization.event_synchronizer import (
    EventSynchronizationResult,
    EventSynchronizationStatus,
    EventSynchronizer,
)
from app.synchronization.synchronization_orchestrator import (
    SynchronizationOrchestrationError,
    SynchronizationOrchestrator,
)


def create_sync_run(
    *,
    status: str = "running",
    items_processed: int = 0,
    items_created: int = 0,
    items_updated: int = 0,
    items_unchanged: int = 0,
    items_cancelled: int = 0,
    items_deleted: int = 0,
    items_failed: int = 0,
    error_message: str | None = None,
) -> SyncRun:
    return SyncRun(
        id=1,
        run_type="calendar_sync",
        source_id=None,
        started_at="2026-08-02T10:00:00+00:00",
        finished_at=(None if status == "running" else "2026-08-02T10:01:00+00:00"),
        status=status,
        items_processed=items_processed,
        items_created=items_created,
        items_updated=items_updated,
        items_unchanged=items_unchanged,
        items_cancelled=items_cancelled,
        items_deleted=items_deleted,
        items_failed=items_failed,
        error_message=error_message,
        metadata={
            "calendar_id": "calendar-1",
            "limit": 100,
        },
    )


def create_event_result(
    status: EventSynchronizationStatus,
    event_id: int,
) -> EventSynchronizationResult:
    return EventSynchronizationResult(
        status=status,
        event_id=event_id,
        calendar_id="calendar-1",
        outlook_event_id=f"outlook-event-{event_id}",
        content_hash=f"content-hash-{event_id}",
    )


def create_orchestrator() -> tuple[
    SynchronizationOrchestrator,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    query_repository = MagicMock(spec=SynchronizationQueryRepository)
    event_synchronizer = MagicMock(spec=EventSynchronizer)
    sync_runs_repository = MagicMock(spec=SyncRunsRepository)

    sync_runs_repository.start.return_value = create_sync_run()

    orchestrator = SynchronizationOrchestrator(
        query_repository=query_repository,
        event_synchronizer=event_synchronizer,
        sync_runs_repository=sync_runs_repository,
    )

    return (
        orchestrator,
        query_repository,
        event_synchronizer,
        sync_runs_repository,
    )


@pytest.mark.parametrize("calendar_id", ["", "   "])
def test_synchronize_rejects_empty_calendar_id(
    calendar_id: str,
) -> None:
    (
        orchestrator,
        query_repository,
        event_synchronizer,
        sync_runs_repository,
    ) = create_orchestrator()

    with pytest.raises(
        ValueError,
        match="Calendar ID must not be empty",
    ):
        orchestrator.synchronize(
            calendar_id=calendar_id,
            limit=100,
        )

    sync_runs_repository.start.assert_not_called()
    query_repository.get_candidates.assert_not_called()
    event_synchronizer.synchronize_event.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1])
def test_synchronize_rejects_non_positive_limit(
    limit: int,
) -> None:
    (
        orchestrator,
        query_repository,
        event_synchronizer,
        sync_runs_repository,
    ) = create_orchestrator()

    with pytest.raises(
        ValueError,
        match="Synchronization batch limit must be positive",
    ):
        orchestrator.synchronize(
            calendar_id="calendar-1",
            limit=limit,
        )

    sync_runs_repository.start.assert_not_called()
    query_repository.get_candidates.assert_not_called()
    event_synchronizer.synchronize_event.assert_not_called()


def test_synchronize_processes_and_counts_all_supported_statuses() -> None:
    (
        orchestrator,
        query_repository,
        event_synchronizer,
        sync_runs_repository,
    ) = create_orchestrator()

    candidates = [object() for _ in range(6)]
    query_repository.get_candidates.return_value = candidates

    event_synchronizer.synchronize_event.side_effect = [
        create_event_result(EventSynchronizationStatus.CREATED, 1),
        create_event_result(EventSynchronizationStatus.UPDATED, 2),
        create_event_result(EventSynchronizationStatus.UNCHANGED, 3),
        create_event_result(EventSynchronizationStatus.CANCELLED, 4),
        create_event_result(
            EventSynchronizationStatus.CANCELLATION_SKIPPED,
            5,
        ),
        create_event_result(EventSynchronizationStatus.DELETED, 6),
    ]

    sync_runs_repository.complete.return_value = create_sync_run(
        status="completed",
        items_processed=6,
        items_created=1,
        items_updated=1,
        items_unchanged=1,
        items_cancelled=2,
        items_deleted=1,
    )

    result = orchestrator.synchronize(
        calendar_id="calendar-1",
        limit=100,
    )

    assert result.sync_run_id == 1
    assert result.status == "completed"
    assert result.items_processed == 6
    assert result.items_created == 1
    assert result.items_updated == 1
    assert result.items_unchanged == 1
    assert result.items_cancelled == 2
    assert result.items_deleted == 1
    assert result.items_failed == 0

    sync_runs_repository.start.assert_called_once_with(
        run_type="calendar_sync",
        metadata={
            "calendar_id": "calendar-1",
            "limit": 100,
        },
    )
    query_repository.get_candidates.assert_called_once_with(
        calendar_id="calendar-1",
        limit=100,
    )
    assert event_synchronizer.synchronize_event.call_args_list == [
        call(
            synchronization_event=candidate,
            calendar_id="calendar-1",
        )
        for candidate in candidates
    ]
    sync_runs_repository.complete.assert_called_once_with(
        sync_run_id=1,
        metadata={
            "calendar_id": "calendar-1",
            "limit": 100,
        },
        items_processed=6,
        items_created=1,
        items_updated=1,
        items_unchanged=1,
        items_cancelled=2,
        items_deleted=1,
        items_failed=0,
    )
    sync_runs_repository.fail.assert_not_called()


def test_synchronize_isolates_event_failure_and_continues() -> None:
    (
        orchestrator,
        query_repository,
        event_synchronizer,
        sync_runs_repository,
    ) = create_orchestrator()

    candidates = [object(), object(), object()]
    query_repository.get_candidates.return_value = candidates

    event_synchronizer.synchronize_event.side_effect = [
        create_event_result(EventSynchronizationStatus.CREATED, 1),
        RuntimeError("Graph unavailable"),
        create_event_result(EventSynchronizationStatus.UPDATED, 3),
    ]

    sync_runs_repository.complete.return_value = create_sync_run(
        status="completed_with_errors",
        items_processed=3,
        items_created=1,
        items_updated=1,
        items_failed=1,
    )

    result = orchestrator.synchronize(
        calendar_id="calendar-1",
        limit=100,
    )

    assert result.status == "completed_with_errors"
    assert result.items_processed == 3
    assert result.items_created == 1
    assert result.items_updated == 1
    assert result.items_failed == 1

    assert event_synchronizer.synchronize_event.call_count == 3
    sync_runs_repository.complete.assert_called_once_with(
        sync_run_id=1,
        metadata={
            "calendar_id": "calendar-1",
            "limit": 100,
        },
        items_processed=3,
        items_created=1,
        items_updated=1,
        items_unchanged=0,
        items_cancelled=0,
        items_deleted=0,
        items_failed=1,
    )
    sync_runs_repository.fail.assert_not_called()


def test_synchronize_completes_empty_run() -> None:
    (
        orchestrator,
        query_repository,
        event_synchronizer,
        sync_runs_repository,
    ) = create_orchestrator()

    query_repository.get_candidates.return_value = []
    sync_runs_repository.complete.return_value = create_sync_run(
        status="completed",
    )

    result = orchestrator.synchronize(
        calendar_id="calendar-1",
        limit=25,
    )

    assert result.status == "completed"
    assert result.items_processed == 0
    assert result.items_created == 0
    assert result.items_updated == 0
    assert result.items_unchanged == 0
    assert result.items_cancelled == 0
    assert result.items_deleted == 0
    assert result.items_failed == 0

    event_synchronizer.synchronize_event.assert_not_called()
    sync_runs_repository.complete.assert_called_once_with(
        sync_run_id=1,
        metadata={
            "calendar_id": "calendar-1",
            "limit": 25,
        },
        items_processed=0,
        items_created=0,
        items_updated=0,
        items_unchanged=0,
        items_cancelled=0,
        items_deleted=0,
        items_failed=0,
    )


def test_synchronize_wraps_run_start_failure() -> None:
    (
        orchestrator,
        query_repository,
        event_synchronizer,
        sync_runs_repository,
    ) = create_orchestrator()

    sync_runs_repository.start.side_effect = RuntimeError("database unavailable")

    with pytest.raises(
        SynchronizationOrchestrationError,
        match="Synchronization run could not be started",
    ):
        orchestrator.synchronize(
            calendar_id="calendar-1",
            limit=100,
        )

    query_repository.get_candidates.assert_not_called()
    event_synchronizer.synchronize_event.assert_not_called()
    sync_runs_repository.complete.assert_not_called()
    sync_runs_repository.fail.assert_not_called()


def test_synchronize_fails_run_when_candidates_cannot_be_loaded() -> None:
    (
        orchestrator,
        query_repository,
        event_synchronizer,
        sync_runs_repository,
    ) = create_orchestrator()

    query_repository.get_candidates.side_effect = RuntimeError("database unavailable")
    sync_runs_repository.fail.return_value = create_sync_run(
        status="failed",
        error_message="database unavailable",
    )

    with pytest.raises(
        SynchronizationOrchestrationError,
        match="Synchronization candidates could not be loaded for run 1",
    ):
        orchestrator.synchronize(
            calendar_id="calendar-1",
            limit=100,
        )

    event_synchronizer.synchronize_event.assert_not_called()
    sync_runs_repository.complete.assert_not_called()
    sync_runs_repository.fail.assert_called_once_with(
        sync_run_id=1,
        error_message="database unavailable",
        metadata={
            "calendar_id": "calendar-1",
            "limit": 100,
        },
        items_processed=0,
        items_created=0,
        items_updated=0,
        items_unchanged=0,
        items_cancelled=0,
        items_deleted=0,
        items_failed=0,
    )


def test_synchronize_fails_run_when_finalization_raises() -> None:
    (
        orchestrator,
        query_repository,
        _,
        sync_runs_repository,
    ) = create_orchestrator()

    query_repository.get_candidates.return_value = []
    sync_runs_repository.complete.side_effect = RuntimeError("database unavailable")
    sync_runs_repository.fail.return_value = create_sync_run(
        status="failed",
        error_message="database unavailable",
    )

    with pytest.raises(
        SynchronizationOrchestrationError,
        match="Synchronization run could not be finalized: 1",
    ):
        orchestrator.synchronize(
            calendar_id="calendar-1",
            limit=100,
        )

    sync_runs_repository.fail.assert_called_once_with(
        sync_run_id=1,
        error_message="database unavailable",
        metadata={
            "calendar_id": "calendar-1",
            "limit": 100,
        },
        items_processed=0,
        items_created=0,
        items_updated=0,
        items_unchanged=0,
        items_cancelled=0,
        items_deleted=0,
        items_failed=0,
    )


def test_synchronize_rejects_disappearing_run_during_finalization() -> None:
    (
        orchestrator,
        query_repository,
        _,
        sync_runs_repository,
    ) = create_orchestrator()

    query_repository.get_candidates.return_value = []
    sync_runs_repository.complete.return_value = None
    sync_runs_repository.fail.return_value = create_sync_run(
        status="failed",
        error_message=("Synchronization run disappeared during finalization: 1"),
    )

    with pytest.raises(
        SynchronizationOrchestrationError,
        match="Synchronization run disappeared during finalization: 1",
    ):
        orchestrator.synchronize(
            calendar_id="calendar-1",
            limit=100,
        )

    sync_runs_repository.fail.assert_called_once_with(
        sync_run_id=1,
        error_message=("Synchronization run disappeared during finalization: 1"),
        metadata={
            "calendar_id": "calendar-1",
            "limit": 100,
        },
        items_processed=0,
        items_created=0,
        items_updated=0,
        items_unchanged=0,
        items_cancelled=0,
        items_deleted=0,
        items_failed=0,
    )


@pytest.mark.parametrize(
    "failure_result",
    [
        None,
        RuntimeError("database unavailable"),
    ],
)
def test_synchronize_raises_when_failed_run_cannot_be_persisted(
    failure_result: SyncRun | Exception | None,
) -> None:
    (
        orchestrator,
        query_repository,
        _,
        sync_runs_repository,
    ) = create_orchestrator()

    query_repository.get_candidates.side_effect = RuntimeError("query failed")

    if isinstance(failure_result, Exception):
        sync_runs_repository.fail.side_effect = failure_result
    else:
        sync_runs_repository.fail.return_value = failure_result

    with pytest.raises(
        SynchronizationOrchestrationError,
        match="Failed synchronization run could not be persisted: 1",
    ):
        orchestrator.synchronize(
            calendar_id="calendar-1",
            limit=100,
        )

    sync_runs_repository.complete.assert_not_called()
