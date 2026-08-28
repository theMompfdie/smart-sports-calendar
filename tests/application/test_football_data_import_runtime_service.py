import logging
from unittest.mock import MagicMock, call

import pytest
from app.application.api_football_import_orchestrator import ProviderImportRunResult
from app.application.football_data_import_runtime_service import (
    FootballDataImportRuntimeService,
)


def result() -> ProviderImportRunResult:
    return ProviderImportRunResult(
        sync_run_id=7,
        status="completed",
        observation_id="observation-7",
        items_processed=306,
        items_created=306,
        items_updated=0,
        items_unchanged=0,
        items_cancelled=0,
        items_deleted=0,
        items_deferred=0,
        items_failed=0,
    )


def runtime(orchestrator: MagicMock, repository: MagicMock):
    return FootballDataImportRuntimeService(
        orchestrator=orchestrator,
        sync_runs_repository=repository,
        logger=logging.getLogger("test-football-data-runtime"),
    )


def test_runtime_recovers_once_and_runs_its_competition_job() -> None:
    orchestrator = MagicMock()
    orchestrator.job_key = "football-data-bundesliga"
    orchestrator.import_current_competition.return_value = result()
    repository = MagicMock()
    service = runtime(orchestrator, repository)

    assert service.run() == result()
    assert service.run() == result()

    repository.recover_running.assert_called_once_with(
        run_type="provider_import",
        error_message="Interrupted provider import recovered during startup.",
    )
    assert orchestrator.import_current_competition.call_count == 2


def test_runtime_can_retry_after_an_isolated_competition_failure() -> None:
    orchestrator = MagicMock()
    orchestrator.job_key = "football-data-bundesliga"
    orchestrator.import_current_competition.side_effect = [
        RuntimeError("provider unavailable"),
        result(),
    ]
    service = runtime(orchestrator, MagicMock())

    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.run()

    assert service.run() == result()
    assert orchestrator.import_current_competition.call_args_list == [call(), call()]


def test_runtime_skips_only_its_own_overlapping_cycle() -> None:
    orchestrator = MagicMock()
    orchestrator.job_key = "football-data-bundesliga"
    service = runtime(orchestrator, MagicMock())
    assert service._lock.acquire(blocking=False)

    try:
        assert service.run() is None
    finally:
        service._lock.release()

    orchestrator.import_current_competition.assert_not_called()
