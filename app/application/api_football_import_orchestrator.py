from dataclasses import dataclass
from datetime import UTC, datetime, time
from hashlib import sha256

from app.application.api_football_catalog_service import ApiFootballCatalogService
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
    FixtureImportScope,
)
from app.application.api_football_fixture_normalization_service import (
    ApiFootballFixtureNormalizationService,
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
from app.providers.api_football.exceptions import ProviderResolutionError
from app.providers.contracts import (
    NormalizedFixtureBatch,
    SourceJobDefinition,
    SourceRole,
)


@dataclass(frozen=True)
class ProviderImportRunResult:
    sync_run_id: int
    status: str
    observation_id: str
    items_processed: int
    items_created: int
    items_updated: int
    items_unchanged: int
    items_cancelled: int
    items_deleted: int
    items_deferred: int
    items_failed: int


class ProviderImportOrchestrationError(RuntimeError):
    """A provider import could not be completed and reported safely."""


class ApiFootballImportOrchestrator:
    RUN_TYPE = "provider_import"

    def __init__(
        self,
        catalog_service: ApiFootballCatalogService,
        normalization_service: ApiFootballFixtureNormalizationService,
        import_service: ApiFootballFixtureImportService,
        data_sources_repository: DataSourcesRepository,
        sync_runs_repository: SyncRunsRepository,
        job_definition: SourceJobDefinition | None = None,
    ) -> None:
        self._catalog_service = catalog_service
        self._normalization_service = normalization_service
        self._import_service = import_service
        self._data_sources_repository = data_sources_repository
        self._sync_runs_repository = sync_runs_repository
        self._job_definition = job_definition

    def import_current_premier_league(self) -> ProviderImportRunResult:
        source = self._data_sources_repository.get_by_key("api_football")
        if source is None or not source.is_active:
            raise ProviderResolutionError(
                "Active API-Football data source must exist before import."
            )
        initial_metadata: dict[str, object] = {
            "operation": "premier_league_fixture_import",
            "source_key": "api_football",
            "job_key": (
                self._job_definition.job_key
                if self._job_definition is not None
                else "api-football-legacy"
            ),
            "role": self._role.value,
            "competition_key": (
                self._job_definition.scope.competition_key
                if self._job_definition is not None
                else "premier_league"
            ),
            "season_key": (
                self._job_definition.scope.season_key
                if self._job_definition is not None
                else "current"
            ),
            "complete": False,
            "filtered": False,
            "authoritative": self._role is SourceRole.AUTHORITATIVE,
        }
        try:
            sync_run = self._sync_runs_repository.start(
                run_type=self.RUN_TYPE,
                source_id=source.id,
                metadata=initial_metadata,
            )
        except Exception as error:
            raise ProviderImportOrchestrationError(
                "Provider import run could not be started."
            ) from error

        try:
            self._catalog_service.map_current_premier_league()
            batch = self._normalization_service.normalize_current_premier_league_batch()
            scope = self._scope(
                batch,
                authoritative=self._role is SourceRole.AUTHORITATIVE,
            )
            import_result = self._import_service.import_fixtures(
                batch.fixtures,
                scope,
            )
            counters = self._counters(import_result)
            metadata = self._metadata(batch, scope)
            completed = self._sync_runs_repository.complete(
                sync_run_id=sync_run.id,
                metadata=metadata,
                **counters,
            )
            if completed is None:
                raise ProviderImportOrchestrationError(
                    "Provider import run disappeared during finalization: "
                    f"{sync_run.id}"
                )
        except Exception as error:
            self._fail_run(sync_run, initial_metadata, error)
            if isinstance(error, ProviderImportOrchestrationError):
                raise
            raise ProviderImportOrchestrationError(
                f"Provider import failed with {type(error).__name__}."
            ) from error

        return self._to_result(completed, scope.observation_id)

    def _fail_run(
        self,
        sync_run: SyncRun,
        metadata: dict[str, object],
        error: Exception,
    ) -> None:
        failure_metadata = {
            **metadata,
            "error_category": type(error).__name__,
        }
        try:
            failed = self._sync_runs_repository.fail(
                sync_run_id=sync_run.id,
                error_message=(f"Provider import failed with {type(error).__name__}."),
                items_failed=1,
                metadata=failure_metadata,
            )
        except Exception as persistence_error:
            raise ProviderImportOrchestrationError(
                f"Failed provider import run could not be persisted: {sync_run.id}"
            ) from persistence_error
        if failed is None:
            raise ProviderImportOrchestrationError(
                f"Failed provider import run could not be persisted: {sync_run.id}"
            ) from error

    @staticmethod
    def _scope(
        batch: NormalizedFixtureBatch,
        *,
        authoritative: bool = True,
    ) -> FixtureImportScope:
        observed_at = batch.fetched_at_utc.astimezone(UTC)
        identity = ":".join(
            (
                "api_football",
                str(batch.competition_id),
                str(batch.season_id),
                observed_at.isoformat(),
                str(batch.page_count),
            )
        )
        observation_id = f"api-football-{sha256(identity.encode()).hexdigest()[:24]}"
        return FixtureImportScope(
            competition_id=batch.competition_id,
            season_id=batch.season_id,
            observation_id=observation_id,
            observed_at_utc=observed_at,
            lifecycle=CompetitionLifecycleScope(
                competition_format=batch.competition_format,
                scope_kind=FixtureObservationScopeKind.COMPLETE_SEASON,
            ),
            window_start_utc=datetime.combine(
                batch.season_start_date,
                time.min,
                tzinfo=UTC,
            ),
            window_end_utc=datetime.combine(
                batch.season_end_date,
                time.max,
                tzinfo=UTC,
            ),
            authoritative=authoritative,
            filtered=False,
        )

    @property
    def _role(self) -> SourceRole:
        if self._job_definition is None:
            return SourceRole.AUTHORITATIVE
        return self._job_definition.role

    @staticmethod
    def _counters(import_result: FixtureImportResult) -> dict[str, int]:
        return {
            "items_processed": len(import_result.items),
            "items_created": import_result.count(FixtureImportDecision.CREATE),
            "items_updated": import_result.count(FixtureImportDecision.UPDATE),
            "items_unchanged": import_result.count(FixtureImportDecision.SKIP),
            "items_cancelled": import_result.count(FixtureImportDecision.CANCEL),
            "items_deleted": import_result.count(FixtureImportDecision.DELETE),
            "items_deferred": import_result.count(FixtureImportDecision.DEFER),
            "items_failed": 0,
        }

    def _metadata(
        self,
        batch: NormalizedFixtureBatch,
        scope: FixtureImportScope,
    ) -> dict[str, object]:
        rate_limits = batch.rate_limits
        window_start = scope.window_start_utc
        window_end = scope.window_end_utc
        if window_start is None or window_end is None:
            raise ValueError("Provider import reporting requires a bounded UTC window.")
        return {
            "operation": "premier_league_fixture_import",
            "source_key": "api_football",
            "job_key": (
                self._job_definition.job_key
                if self._job_definition is not None
                else "api-football-legacy"
            ),
            "role": self._role.value,
            "competition_key": (
                self._job_definition.scope.competition_key
                if self._job_definition is not None
                else "premier_league"
            ),
            "season_key": (
                self._job_definition.scope.season_key
                if self._job_definition is not None
                else "current"
            ),
            "competition_id": scope.competition_id,
            "season_id": scope.season_id,
            "window_start_utc": window_start.isoformat(),
            "window_end_utc": window_end.isoformat(),
            "authoritative": scope.authoritative,
            "complete": scope.complete,
            "filtered": scope.filtered,
            "competition_format": scope.lifecycle.competition_format.value,
            "scope_kind": scope.lifecycle.scope_kind.value,
            "scope_stage_kind": (
                None
                if scope.lifecycle.stage_kind is None
                else scope.lifecycle.stage_kind.value
            ),
            "scope_stage": scope.lifecycle.stage,
            "scope_round": scope.lifecycle.round_name,
            "removal_eligible": scope.removal_eligible,
            "observation_id": scope.observation_id,
            "observed_at_utc": scope.observed_at_utc.isoformat(),
            "page_count": batch.page_count,
            "request_attempts": batch.request_attempts,
            "rate_limits": {
                "daily_limit": rate_limits.daily_limit,
                "daily_remaining": rate_limits.daily_remaining,
                "minute_limit": rate_limits.minute_limit,
                "minute_remaining": rate_limits.minute_remaining,
                "retry_after_seconds": rate_limits.retry_after_seconds,
            },
        }

    @staticmethod
    def _to_result(
        sync_run: SyncRun,
        observation_id: str,
    ) -> ProviderImportRunResult:
        return ProviderImportRunResult(
            sync_run_id=sync_run.id,
            status=sync_run.status,
            observation_id=observation_id,
            items_processed=sync_run.items_processed,
            items_created=sync_run.items_created,
            items_updated=sync_run.items_updated,
            items_unchanged=sync_run.items_unchanged,
            items_cancelled=sync_run.items_cancelled,
            items_deleted=sync_run.items_deleted,
            items_deferred=sync_run.items_deferred,
            items_failed=sync_run.items_failed,
        )
