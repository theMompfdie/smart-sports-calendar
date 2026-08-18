import logging
from threading import Lock

from app.application.api_football_import_orchestrator import ProviderImportRunResult
from app.application.openligadb_import_orchestrator import OpenLigaDBImportOrchestrator
from app.database.sync_runs_repository import SyncRunsRepository


class OpenLigaDBImportRuntimeService:
    RUN_TYPE = "provider_import"

    def __init__(
        self,
        orchestrator: OpenLigaDBImportOrchestrator,
        sync_runs_repository: SyncRunsRepository,
        logger: logging.Logger,
    ) -> None:
        self._orchestrator = orchestrator
        self._sync_runs_repository = sync_runs_repository
        self._logger = logger
        self._lock = Lock()
        self._recovered = False

    def run(self) -> ProviderImportRunResult | None:
        if not self._lock.acquire(blocking=False):
            self._logger.warning(
                "OpenLigaDB import skipped: run already active job_key=%s",
                self._orchestrator.job_key,
            )
            return None
        try:
            if not self._recovered:
                self._sync_runs_repository.recover_running(
                    run_type=self.RUN_TYPE,
                    error_message=(
                        "Interrupted provider import recovered during startup."
                    ),
                )
                self._recovered = True
            self._logger.info(
                "OpenLigaDB provider import cycle started: job_key=%s",
                self._orchestrator.job_key,
            )
            result = self._orchestrator.import_current_competition()
            self._logger.info(
                (
                    "OpenLigaDB provider import completed: job_key=%s run_id=%s "
                    "status=%s processed=%s created=%s updated=%s unchanged=%s "
                    "cancelled=%s deleted=%s deferred=%s failed=%s"
                ),
                self._orchestrator.job_key,
                result.sync_run_id,
                result.status,
                result.items_processed,
                result.items_created,
                result.items_updated,
                result.items_unchanged,
                result.items_cancelled,
                result.items_deleted,
                result.items_deferred,
                result.items_failed,
            )
            return result
        except Exception as error:
            self._logger.error(
                "OpenLigaDB provider import failed: job_key=%s category=%s",
                self._orchestrator.job_key,
                type(error).__name__,
            )
            raise
        finally:
            self._lock.release()
