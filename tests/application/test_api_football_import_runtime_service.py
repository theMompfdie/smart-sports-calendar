import logging
from unittest.mock import MagicMock

import pytest
from app.application.api_football_import_orchestrator import (
    ApiFootballImportOrchestrator,
    ProviderImportRunResult,
)
from app.application.api_football_import_runtime_service import (
    ApiFootballImportRuntimeService,
)
from app.database.sync_runs_repository import SyncRunsRepository


def create_result() -> ProviderImportRunResult:
    return ProviderImportRunResult(
        sync_run_id=1,
        status="completed",
        observation_id="observation-1",
        items_processed=6,
        items_created=1,
        items_updated=1,
        items_unchanged=1,
        items_cancelled=1,
        items_deleted=1,
        items_deferred=1,
        items_failed=0,
    )


def create_runtime() -> tuple[
    ApiFootballImportRuntimeService,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    orchestrator = MagicMock(spec=ApiFootballImportOrchestrator)
    runs = MagicMock(spec=SyncRunsRepository)
    logger = MagicMock(spec=logging.Logger)
    runs.recover_running.return_value = []
    orchestrator.import_current_premier_league.return_value = create_result()
    runtime = ApiFootballImportRuntimeService(
        orchestrator=orchestrator,
        sync_runs_repository=runs,
        logger=logger,
    )
    return runtime, orchestrator, runs, logger


def test_runtime_recovers_once_and_logs_completed_counters() -> None:
    runtime, orchestrator, runs, logger = create_runtime()

    first = runtime.run()
    second = runtime.run()

    assert first == create_result()
    assert second == create_result()
    runs.recover_running.assert_called_once_with(
        run_type="provider_import",
        error_message=(
            "Interrupted provider import recovered during application startup."
        ),
    )
    assert orchestrator.import_current_premier_league.call_count == 2
    assert logger.info.call_count == 4


def test_runtime_skips_overlapping_import_without_starting_another_run() -> None:
    runtime, orchestrator, _runs, logger = create_runtime()
    assert runtime._run_lock.acquire(blocking=False) is True
    try:
        result = runtime.run()
    finally:
        runtime._run_lock.release()

    assert result is None
    orchestrator.import_current_premier_league.assert_not_called()
    logger.warning.assert_called_once_with(
        "Provider import skipped because another run is active"
    )


def test_runtime_releases_lock_and_preserves_failure_category() -> None:
    runtime, orchestrator, _runs, logger = create_runtime()
    orchestrator.import_current_premier_league.side_effect = RuntimeError(
        "provider-secret"
    )

    with pytest.raises(RuntimeError, match="provider-secret"):
        runtime.run()

    logger.error.assert_called_once_with(
        "API-Football provider import cycle failed: category=%s",
        "RuntimeError",
    )
    assert "provider-secret" not in str(logger.method_calls)
    orchestrator.import_current_premier_league.side_effect = None
    orchestrator.import_current_premier_league.return_value = create_result()
    assert runtime.run() == create_result()
