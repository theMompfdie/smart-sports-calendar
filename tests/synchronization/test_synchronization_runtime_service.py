import logging
from unittest.mock import MagicMock, call

import pytest
from app.database.sync_runs_repository import SyncRunsRepository
from app.synchronization.synchronization_orchestrator import (
    SynchronizationOrchestrator,
    SynchronizationRunResult,
)
from app.synchronization.synchronization_runtime_service import (
    SynchronizationRuntimeService,
)


def create_service() -> tuple[
    SynchronizationRuntimeService,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    orchestrator = MagicMock(spec=SynchronizationOrchestrator)
    sync_runs_repository = MagicMock(spec=SyncRunsRepository)
    logger = MagicMock(spec=logging.Logger)

    service = SynchronizationRuntimeService(
        orchestrator=orchestrator,
        sync_runs_repository=sync_runs_repository,
        logger=logger,
    )

    return (
        service,
        orchestrator,
        sync_runs_repository,
        logger,
    )


def create_result(
    *,
    status: str = "completed",
    items_failed: int = 0,
) -> SynchronizationRunResult:
    return SynchronizationRunResult(
        sync_run_id=1,
        status=status,
        items_processed=21 + items_failed,
        items_created=1,
        items_updated=2,
        items_unchanged=3,
        items_cancelled=4,
        items_deleted=5,
        items_deferred=6,
        items_failed=items_failed,
    )


def test_run_recovers_interrupted_runs_before_synchronization() -> None:
    (
        service,
        orchestrator,
        sync_runs_repository,
        logger,
    ) = create_service()

    recovered_runs = [object(), object()]
    expected_result = create_result()

    sync_runs_repository.recover_running.return_value = recovered_runs
    orchestrator.synchronize.return_value = expected_result

    result = service.run(
        calendar_id="calendar-1",
        limit=100,
    )

    assert result is expected_result
    sync_runs_repository.recover_running.assert_called_once_with(
        run_type="calendar_sync",
        error_message=(
            "Interrupted synchronization run recovered during application startup."
        ),
    )
    orchestrator.synchronize.assert_called_once_with(
        calendar_id="calendar-1",
        limit=100,
    )
    logger.warning.assert_called_once_with(
        "Recovered %s interrupted synchronization run(s)",
        2,
    )


def test_run_performs_recovery_only_once() -> None:
    (
        service,
        orchestrator,
        sync_runs_repository,
        _,
    ) = create_service()

    sync_runs_repository.recover_running.return_value = []
    orchestrator.synchronize.return_value = create_result()

    service.run(
        calendar_id="calendar-1",
        limit=100,
    )
    service.run(
        calendar_id="calendar-1",
        limit=100,
    )

    sync_runs_repository.recover_running.assert_called_once_with(
        run_type="calendar_sync",
        error_message=(
            "Interrupted synchronization run recovered during application startup."
        ),
    )
    assert orchestrator.synchronize.call_args_list == [
        call(
            calendar_id="calendar-1",
            limit=100,
        ),
        call(
            calendar_id="calendar-1",
            limit=100,
        ),
    ]


def test_run_retries_recovery_after_recovery_failure() -> None:
    (
        service,
        orchestrator,
        sync_runs_repository,
        _,
    ) = create_service()

    sync_runs_repository.recover_running.side_effect = [
        RuntimeError("database unavailable"),
        [],
    ]
    orchestrator.synchronize.return_value = create_result()

    with pytest.raises(
        RuntimeError,
        match="database unavailable",
    ):
        service.run(
            calendar_id="calendar-1",
            limit=100,
        )

    result = service.run(
        calendar_id="calendar-1",
        limit=100,
    )

    assert result is not None
    assert sync_runs_repository.recover_running.call_count == 2
    orchestrator.synchronize.assert_called_once_with(
        calendar_id="calendar-1",
        limit=100,
    )


def test_run_releases_lock_after_recovery_failure() -> None:
    (
        service,
        orchestrator,
        sync_runs_repository,
        _,
    ) = create_service()

    sync_runs_repository.recover_running.side_effect = [
        RuntimeError("database unavailable"),
        [],
    ]
    orchestrator.synchronize.return_value = create_result()

    with pytest.raises(RuntimeError):
        service.run(
            calendar_id="calendar-1",
            limit=100,
        )

    result = service.run(
        calendar_id="calendar-1",
        limit=100,
    )

    assert result is not None


def test_run_releases_lock_after_synchronization_failure() -> None:
    (
        service,
        orchestrator,
        sync_runs_repository,
        _,
    ) = create_service()

    expected_result = create_result()

    sync_runs_repository.recover_running.return_value = []
    orchestrator.synchronize.side_effect = [
        RuntimeError("synchronization failed"),
        expected_result,
    ]

    with pytest.raises(
        RuntimeError,
        match="synchronization failed",
    ):
        service.run(
            calendar_id="calendar-1",
            limit=100,
        )

    result = service.run(
        calendar_id="calendar-1",
        limit=100,
    )

    assert result is expected_result
    sync_runs_repository.recover_running.assert_called_once()
    assert orchestrator.synchronize.call_count == 2


def test_run_skips_when_another_run_holds_lock() -> None:
    (
        service,
        orchestrator,
        sync_runs_repository,
        logger,
    ) = create_service()

    service._run_lock.acquire()

    try:
        result = service.run(
            calendar_id="calendar-1",
            limit=100,
        )
    finally:
        service._run_lock.release()

    assert result is None
    sync_runs_repository.recover_running.assert_not_called()
    orchestrator.synchronize.assert_not_called()
    logger.warning.assert_called_once_with(
        "Synchronization skipped because another run is active"
    )


def test_run_logs_started_and_completed_cycle() -> None:
    (
        service,
        orchestrator,
        sync_runs_repository,
        logger,
    ) = create_service()

    expected_result = create_result()

    sync_runs_repository.recover_running.return_value = []
    orchestrator.synchronize.return_value = expected_result

    sensitive_calendar_id = "sensitive-calendar-id"
    service.run(
        calendar_id=sensitive_calendar_id,
        limit=100,
    )

    assert logger.info.call_args_list == [
        call(
            "Synchronization cycle started with limit %s",
            100,
        ),
        call(
            (
                "Synchronization cycle completed: "
                "run_id=%s status=%s processed=%s created=%s "
                "updated=%s unchanged=%s cancelled=%s deleted=%s "
                "deferred=%s failed=%s"
            ),
            expected_result.sync_run_id,
            expected_result.status,
            expected_result.items_processed,
            expected_result.items_created,
            expected_result.items_updated,
            expected_result.items_unchanged,
            expected_result.items_cancelled,
            expected_result.items_deleted,
            expected_result.items_deferred,
            expected_result.items_failed,
        ),
    ]
    assert sensitive_calendar_id not in str(logger.method_calls)


def test_run_logs_all_counters_for_completed_cycle_with_errors() -> None:
    service, orchestrator, sync_runs_repository, logger = create_service()
    expected_result = create_result(
        status="completed_with_errors",
        items_failed=7,
    )
    sync_runs_repository.recover_running.return_value = []
    orchestrator.synchronize.return_value = expected_result

    service.run(calendar_id="calendar-1", limit=100)

    logger.info.assert_called_with(
        (
            "Synchronization cycle completed: "
            "run_id=%s status=%s processed=%s created=%s "
            "updated=%s unchanged=%s cancelled=%s deleted=%s "
            "deferred=%s failed=%s"
        ),
        1,
        "completed_with_errors",
        28,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
    )
