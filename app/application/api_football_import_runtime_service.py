import logging
from threading import Lock

from app.application.api_football_import_orchestrator import (
    ApiFootballImportOrchestrator,
    ProviderImportRunResult,
)
from app.database.sync_runs_repository import SyncRunsRepository


class ApiFootballImportRuntimeService:
    RUN_TYPE = "provider_import"
    RECOVERY_ERROR_MESSAGE = (
        "Interrupted provider import recovered during application startup."
    )

    def __init__(
        self,
        orchestrator: ApiFootballImportOrchestrator,
        sync_runs_repository: SyncRunsRepository,
        logger: logging.Logger,
    ) -> None:
        self._orchestrator = orchestrator
        self._sync_runs_repository = sync_runs_repository
        self._logger = logger
        self._run_lock = Lock()
        self._recovery_completed = False

    def run(self) -> ProviderImportRunResult | None:
        if not self._run_lock.acquire(blocking=False):
            self._logger.warning(
                "Provider import skipped because another run is active"
            )
            return None

        try:
            self._recover_interrupted_runs()
            self._logger.info("API-Football provider import cycle started")
            result = self._orchestrator.import_current_premier_league()
            self._logger.info(
                (
                    "API-Football provider import cycle completed: "
                    "run_id=%s status=%s processed=%s created=%s updated=%s "
                    "unchanged=%s cancelled=%s deleted=%s deferred=%s failed=%s"
                ),
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
                "API-Football provider import cycle failed: category=%s",
                type(error).__name__,
            )
            raise
        finally:
            self._run_lock.release()

    def _recover_interrupted_runs(self) -> None:
        if self._recovery_completed:
            return
        recovered = self._sync_runs_repository.recover_running(
            run_type=self.RUN_TYPE,
            error_message=self.RECOVERY_ERROR_MESSAGE,
        )
        self._recovery_completed = True
        if recovered:
            self._logger.warning(
                "Recovered %s interrupted provider import run(s)",
                len(recovered),
            )
