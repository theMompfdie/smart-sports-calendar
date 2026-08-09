from dataclasses import dataclass

from app.database.sync_runs_repository import SyncRun, SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.synchronization.event_synchronizer import (
    EventSynchronizationStatus,
    EventSynchronizer,
)


@dataclass(frozen=True)
class SynchronizationRunResult:
    sync_run_id: int
    status: str
    items_processed: int
    items_created: int
    items_updated: int
    items_unchanged: int
    items_cancelled: int
    items_deleted: int
    items_deferred: int
    items_failed: int


@dataclass
class _SynchronizationCounters:
    items_processed: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_unchanged: int = 0
    items_cancelled: int = 0
    items_deleted: int = 0
    items_failed: int = 0

    def record(self, status: EventSynchronizationStatus) -> None:
        self.items_processed += 1

        if status == EventSynchronizationStatus.CREATED:
            self.items_created += 1
        elif status == EventSynchronizationStatus.UPDATED:
            self.items_updated += 1
        elif status == EventSynchronizationStatus.UNCHANGED:
            self.items_unchanged += 1
        elif status in {
            EventSynchronizationStatus.CANCELLED,
            EventSynchronizationStatus.CANCELLATION_SKIPPED,
        }:
            self.items_cancelled += 1
        elif status == EventSynchronizationStatus.DELETED:
            self.items_deleted += 1
        else:
            raise SynchronizationOrchestrationError(
                f"Unsupported synchronization status: {status}"
            )

    def record_failure(self) -> None:
        self.items_processed += 1
        self.items_failed += 1

    def as_repository_arguments(self) -> dict[str, int]:
        return {
            "items_processed": self.items_processed,
            "items_created": self.items_created,
            "items_updated": self.items_updated,
            "items_unchanged": self.items_unchanged,
            "items_cancelled": self.items_cancelled,
            "items_deleted": self.items_deleted,
            "items_failed": self.items_failed,
        }


class SynchronizationOrchestrationError(RuntimeError):
    pass


class SynchronizationOrchestrator:
    RUN_TYPE = "calendar_sync"

    def __init__(
        self,
        query_repository: SynchronizationQueryRepository,
        event_synchronizer: EventSynchronizer,
        sync_runs_repository: SyncRunsRepository,
    ) -> None:
        self._query_repository = query_repository
        self._event_synchronizer = event_synchronizer
        self._sync_runs_repository = sync_runs_repository

    def synchronize(
        self,
        calendar_id: str,
        limit: int,
    ) -> SynchronizationRunResult:
        if not calendar_id.strip():
            raise ValueError("Calendar ID must not be empty.")

        if limit <= 0:
            raise ValueError("Synchronization batch limit must be positive.")

        metadata = {
            "calendar_id": calendar_id,
            "limit": limit,
        }

        try:
            sync_run = self._sync_runs_repository.start(
                run_type=self.RUN_TYPE,
                metadata=metadata,
            )
        except Exception as error:
            raise SynchronizationOrchestrationError(
                "Synchronization run could not be started."
            ) from error

        counters = _SynchronizationCounters()

        try:
            candidates = self._query_repository.get_candidates(
                calendar_id=calendar_id,
                limit=limit,
            )
        except Exception as error:
            self._fail_run(
                sync_run=sync_run,
                counters=counters,
                metadata=metadata,
                error=error,
            )
            raise SynchronizationOrchestrationError(
                f"Synchronization candidates could not be loaded for run {sync_run.id}."
            ) from error

        for candidate in candidates:
            try:
                result = self._event_synchronizer.synchronize_event(
                    synchronization_event=candidate,
                    calendar_id=calendar_id,
                )
                counters.record(result.status)
            except Exception:
                counters.record_failure()

        try:
            completed_run = self._sync_runs_repository.complete(
                sync_run_id=sync_run.id,
                metadata=metadata,
                **counters.as_repository_arguments(),
            )
        except Exception as error:
            self._fail_run(
                sync_run=sync_run,
                counters=counters,
                metadata=metadata,
                error=error,
            )
            raise SynchronizationOrchestrationError(
                f"Synchronization run could not be finalized: {sync_run.id}"
            ) from error

        if completed_run is None:
            error = SynchronizationOrchestrationError(
                f"Synchronization run disappeared during finalization: {sync_run.id}"
            )
            self._fail_run(
                sync_run=sync_run,
                counters=counters,
                metadata=metadata,
                error=error,
            )
            raise error

        return self._to_result(completed_run)

    def _fail_run(
        self,
        sync_run: SyncRun,
        counters: _SynchronizationCounters,
        metadata: dict[str, object],
        error: Exception,
    ) -> None:
        try:
            failed_run = self._sync_runs_repository.fail(
                sync_run_id=sync_run.id,
                error_message=str(error),
                metadata=metadata,
                **counters.as_repository_arguments(),
            )
        except Exception as persistence_error:
            raise SynchronizationOrchestrationError(
                f"Failed synchronization run could not be persisted: {sync_run.id}"
            ) from persistence_error

        if failed_run is None:
            raise SynchronizationOrchestrationError(
                f"Failed synchronization run could not be persisted: {sync_run.id}"
            ) from error

    @staticmethod
    def _to_result(sync_run: SyncRun) -> SynchronizationRunResult:
        return SynchronizationRunResult(
            sync_run_id=sync_run.id,
            status=sync_run.status,
            items_processed=sync_run.items_processed,
            items_created=sync_run.items_created,
            items_updated=sync_run.items_updated,
            items_unchanged=sync_run.items_unchanged,
            items_cancelled=sync_run.items_cancelled,
            items_deleted=sync_run.items_deleted,
            items_deferred=sync_run.items_deferred,
            items_failed=sync_run.items_failed,
        )
