import logging
from threading import Lock

from app.database.sync_runs_repository import SyncRunsRepository
from app.synchronization.synchronization_orchestrator import (
    SynchronizationOrchestrator,
    SynchronizationRunResult,
)


class SynchronizationRuntimeService:
    RUN_TYPE = "calendar_sync"
    RECOVERY_ERROR_MESSAGE = (
        "Interrupted synchronization run recovered during application startup."
    )

    def __init__(
        self,
        orchestrator: SynchronizationOrchestrator,
        sync_runs_repository: SyncRunsRepository,
        logger: logging.Logger,
    ) -> None:
        self._orchestrator = orchestrator
        self._sync_runs_repository = sync_runs_repository
        self._logger = logger
        self._run_lock = Lock()
        self._recovery_completed = False

    def run(
        self,
        calendar_id: str,
        limit: int,
    ) -> SynchronizationRunResult | None:
        if not self._run_lock.acquire(blocking=False):
            self._logger.warning(
                "Synchronization skipped because another run is active"
            )
            return None

        try:
            self._recover_interrupted_runs()

            self._logger.info(
                "Synchronization cycle started for calendar %s with limit %s",
                calendar_id,
                limit,
            )

            result = self._orchestrator.synchronize(
                calendar_id=calendar_id,
                limit=limit,
            )

            self._logger.info(
                (
                    "Synchronization cycle completed: "
                    "run_id=%s status=%s processed=%s failed=%s"
                ),
                result.sync_run_id,
                result.status,
                result.items_processed,
                result.items_failed,
            )

            return result
        finally:
            self._run_lock.release()

    def _recover_interrupted_runs(self) -> None:
        if self._recovery_completed:
            return

        recovered_runs = self._sync_runs_repository.recover_running(
            run_type=self.RUN_TYPE,
            error_message=self.RECOVERY_ERROR_MESSAGE,
        )

        self._recovery_completed = True

        if recovered_runs:
            self._logger.warning(
                "Recovered %s interrupted synchronization run(s)",
                len(recovered_runs),
            )
