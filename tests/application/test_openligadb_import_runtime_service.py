import logging
from unittest.mock import MagicMock, call

import pytest
from app.application.api_football_import_orchestrator import ProviderImportRunResult
from app.application.openligadb_import_runtime_service import (
    OpenLigaDBImportRuntimeService,
)


def result() -> ProviderImportRunResult:
    return ProviderImportRunResult(
        sync_run_id=7,
        status="completed",
        observation_id="observation-7",
        items_processed=32,
        items_created=32,
        items_updated=0,
        items_unchanged=0,
        items_cancelled=0,
        items_deleted=0,
        items_deferred=0,
        items_failed=0,
    )


def runtime(orchestrator: MagicMock, repository: MagicMock):
    return OpenLigaDBImportRuntimeService(
        orchestrator=orchestrator,
        sync_runs_repository=repository,
        logger=logging.getLogger("test-openligadb-runtime"),
    )


def test_runtime_recovers_once_and_runs_the_dfb_pokal_job() -> None:
    orchestrator = MagicMock()
    orchestrator.job_key = "openligadb-dfb-pokal"
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


def test_runtime_releases_lock_after_isolated_provider_failure() -> None:
    orchestrator = MagicMock()
    orchestrator.job_key = "openligadb-dfb-pokal"
    orchestrator.import_current_competition.side_effect = [
        RuntimeError("provider unavailable"),
        result(),
    ]
    service = runtime(orchestrator, MagicMock())

    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.run()

    assert service.run() == result()
    assert orchestrator.import_current_competition.call_args_list == [call(), call()]


def test_runtime_skips_an_overlapping_cycle() -> None:
    orchestrator = MagicMock()
    orchestrator.job_key = "openligadb-dfb-pokal"
    service = runtime(orchestrator, MagicMock())
    assert service._lock.acquire(blocking=False)

    try:
        assert service.run() is None
    finally:
        service._lock.release()

    orchestrator.import_current_competition.assert_not_called()
