from datetime import UTC, datetime, time
from hashlib import sha256

from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
    FixtureImportScope,
)
from app.application.api_football_import_orchestrator import (
    ProviderImportOrchestrationError,
    ProviderImportRunResult,
)
from app.application.football_data_premier_league_service import (
    FOOTBALL_DATA_SOURCE_KEY,
    FootballDataCompetitionService,
)
from app.database.data_sources_repository import DataSourcesRepository
from app.database.fixture_import_repository import (
    FixtureImportDecision,
    FixtureImportResult,
)
from app.database.sync_runs_repository import SyncRun, SyncRunsRepository
from app.domain.competition_lifecycle import (
    CompetitionLifecycleScope,
    FixtureObservationScopeKind,
)
from app.providers.contracts import (
    NormalizedFixtureBatch,
    SourceJobDefinition,
    SourceRole,
)
from app.providers.football_data.exceptions import FootballDataResolutionError


class FootballDataImportOrchestrator:
    RUN_TYPE = "provider_import"

    def __init__(
        self,
        competition_service: FootballDataCompetitionService,
        import_service: ApiFootballFixtureImportService,
        sync_runs_repository: SyncRunsRepository,
        data_sources_repository: DataSourcesRepository,
        job_definition: SourceJobDefinition,
    ) -> None:
        if job_definition.source_key != FOOTBALL_DATA_SOURCE_KEY:
            raise ValueError("football-data.org orchestrator received the wrong job.")
        if job_definition.role is not SourceRole.AUTHORITATIVE:
            raise ValueError("football-data.org release adapter must be authoritative.")
        self._competition_service = competition_service
        self._import_service = import_service
        self._sync_runs_repository = sync_runs_repository
        self._data_sources_repository = data_sources_repository
        self._job_definition = job_definition

    @property
    def job_key(self) -> str:
        return self._job_definition.job_key

    def import_current_competition(self) -> ProviderImportRunResult:
        metadata = self._base_metadata(complete=False)
        source = self._data_sources_repository.get_by_key(FOOTBALL_DATA_SOURCE_KEY)
        if source is None or not source.is_active:
            raise FootballDataResolutionError(
                "Active football-data.org source must exist before import."
            )
        try:
            run = self._sync_runs_repository.start(
                run_type=self.RUN_TYPE,
                source_id=source.id,
                metadata=metadata,
            )
        except Exception as error:
            raise ProviderImportOrchestrationError(
                "Provider import run could not be started."
            ) from error
        try:
            batch = self._competition_service.fetch_normalized_snapshot()
            scope = self._scope(batch)
            result = self._import_service.import_fixtures(batch.fixtures, scope)
            completed = self._sync_runs_repository.complete(
                sync_run_id=run.id,
                metadata=self._metadata(batch, scope),
                **self._counters(result),
            )
            if completed is None:
                raise ProviderImportOrchestrationError(
                    "Provider import run disappeared during finalization."
                )
        except Exception as error:
            self._fail_run(run, metadata, error)
            if isinstance(error, ProviderImportOrchestrationError):
                raise
            raise ProviderImportOrchestrationError(
                f"Provider import failed with {type(error).__name__}."
            ) from error
        return ProviderImportRunResult(
            sync_run_id=completed.id,
            status=completed.status,
            observation_id=scope.observation_id,
            items_processed=completed.items_processed,
            items_created=completed.items_created,
            items_updated=completed.items_updated,
            items_unchanged=completed.items_unchanged,
            items_cancelled=completed.items_cancelled,
            items_deleted=completed.items_deleted,
            items_deferred=completed.items_deferred,
            items_failed=completed.items_failed,
        )

    def _base_metadata(self, *, complete: bool) -> dict[str, object]:
        job = self._job_definition
        return {
            "operation": "competition_fixture_import",
            "source_key": FOOTBALL_DATA_SOURCE_KEY,
            "job_key": job.job_key,
            "role": job.role.value,
            "competition_key": job.scope.competition_key,
            "season_key": job.scope.season_key,
            "authoritative": True,
            "complete": complete,
            "filtered": False,
        }

    def import_current_premier_league(self) -> ProviderImportRunResult:
        """Backward-compatible entry point for the original release adapter."""
        return self.import_current_competition()

    @staticmethod
    def _scope(batch: NormalizedFixtureBatch) -> FixtureImportScope:
        observed_at = batch.fetched_at_utc.astimezone(UTC)
        fingerprint = sha256(
            "\n".join(fixture.external_id for fixture in batch.fixtures).encode()
        ).hexdigest()[:16]
        identity = ":".join(
            (
                FOOTBALL_DATA_SOURCE_KEY,
                str(batch.competition_id),
                str(batch.season_id),
                observed_at.isoformat(),
                fingerprint,
            )
        )
        return FixtureImportScope(
            competition_id=batch.competition_id,
            season_id=batch.season_id,
            observation_id=f"football-data-{sha256(identity.encode()).hexdigest()[:24]}",
            observed_at_utc=observed_at,
            lifecycle=CompetitionLifecycleScope(
                competition_format=batch.competition_format,
                scope_kind=FixtureObservationScopeKind.COMPLETE_SEASON,
            ),
            window_start_utc=datetime.combine(
                batch.season_start_date, time.min, tzinfo=UTC
            ),
            window_end_utc=datetime.combine(
                batch.season_end_date, time.max, tzinfo=UTC
            ),
            authoritative=True,
            filtered=False,
        )

    def _metadata(
        self, batch: NormalizedFixtureBatch, scope: FixtureImportScope
    ) -> dict[str, object]:
        metadata = self._base_metadata(complete=True)
        metadata.update(
            {
                "competition_id": scope.competition_id,
                "season_id": scope.season_id,
                "window_start_utc": scope.window_start_utc.isoformat()
                if scope.window_start_utc
                else None,
                "window_end_utc": scope.window_end_utc.isoformat()
                if scope.window_end_utc
                else None,
                "observation_id": scope.observation_id,
                "observed_at_utc": scope.observed_at_utc.isoformat(),
                "competition_format": scope.lifecycle.competition_format.value,
                "scope_kind": scope.lifecycle.scope_kind.value,
                "scope_stage": scope.lifecycle.stage,
                "scope_round": scope.lifecycle.round_name,
                "removal_eligible": scope.removal_eligible,
                "page_count": batch.page_count,
                "request_attempts": batch.request_attempts,
                "rate_limits": {
                    "daily_limit": batch.rate_limits.daily_limit,
                    "daily_remaining": batch.rate_limits.daily_remaining,
                    "minute_limit": batch.rate_limits.minute_limit,
                    "minute_remaining": batch.rate_limits.minute_remaining,
                    "retry_after_seconds": batch.rate_limits.retry_after_seconds,
                },
            }
        )
        return metadata

    @staticmethod
    def _counters(result: FixtureImportResult) -> dict[str, int]:
        return {
            "items_processed": len(result.items),
            "items_created": result.count(FixtureImportDecision.CREATE),
            "items_updated": result.count(FixtureImportDecision.UPDATE),
            "items_unchanged": result.count(FixtureImportDecision.SKIP),
            "items_cancelled": result.count(FixtureImportDecision.CANCEL),
            "items_deleted": result.count(FixtureImportDecision.DELETE),
            "items_deferred": result.count(FixtureImportDecision.DEFER),
            "items_failed": 0,
        }

    def _fail_run(
        self, run: SyncRun, metadata: dict[str, object], error: Exception
    ) -> None:
        try:
            failed = self._sync_runs_repository.fail(
                sync_run_id=run.id,
                error_message=f"Provider import failed with {type(error).__name__}.",
                items_failed=1,
                metadata={**metadata, "error_category": type(error).__name__},
            )
        except Exception as persistence_error:
            raise ProviderImportOrchestrationError(
                "Failed provider import run could not be persisted."
            ) from persistence_error
        if failed is None:
            raise FootballDataResolutionError(
                "Failed provider import run could not be persisted."
            )
