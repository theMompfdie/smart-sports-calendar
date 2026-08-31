from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.application.api_football_catalog_service import ApiFootballCatalogService
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.api_football_fixture_normalization_service import (
    ApiFootballFixtureNormalizationService,
    NormalizedFixtureBatch,
)
from app.application.api_football_import_orchestrator import (
    ApiFootballImportOrchestrator,
    ProviderImportOrchestrationError,
)
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.fixture_import_repository import (
    FixtureImportDecision,
    FixtureImportItemResult,
    FixtureImportResult,
)
from app.database.sync_runs_repository import SyncRun, SyncRunsRepository
from app.domain.competition_lifecycle import (
    CompetitionFormat,
    FixtureObservationScopeKind,
)
from app.providers.api_football.exceptions import ProviderRateLimitError
from app.providers.api_football.models import RateLimitSnapshot

FETCHED_AT = datetime(2026, 8, 8, 12, tzinfo=UTC)


def create_batch() -> NormalizedFixtureBatch:
    return NormalizedFixtureBatch(
        fixtures=(),
        competition_id=10,
        competition_format=CompetitionFormat.LEAGUE,
        season_id=20,
        season_start_date=date(2026, 8, 14),
        season_end_date=date(2027, 5, 24),
        fetched_at_utc=FETCHED_AT,
        page_count=2,
        request_attempts=3,
        rate_limits=RateLimitSnapshot(
            daily_limit=100,
            daily_remaining=91,
            minute_limit=10,
            minute_remaining=8,
            retry_after_seconds=4.0,
        ),
    )


def create_sync_run(
    *,
    status: str = "running",
    counters: dict[str, int] | None = None,
) -> SyncRun:
    values = counters or {
        "items_processed": 0,
        "items_created": 0,
        "items_updated": 0,
        "items_unchanged": 0,
        "items_cancelled": 0,
        "items_deleted": 0,
        "items_deferred": 0,
        "items_failed": 0,
    }
    return SyncRun(
        id=1,
        run_type="provider_import",
        source_id=1,
        started_at="2026-08-08T12:00:00+00:00",
        finished_at=(None if status == "running" else "2026-08-08T12:01:00+00:00"),
        status=status,
        error_message=None,
        metadata=None,
        **values,
    )


def create_orchestrator() -> tuple[
    ApiFootballImportOrchestrator,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
    MagicMock,
]:
    catalog = MagicMock(spec=ApiFootballCatalogService)
    normalization = MagicMock(spec=ApiFootballFixtureNormalizationService)
    importer = MagicMock(spec=ApiFootballFixtureImportService)
    sources = MagicMock(spec=DataSourcesRepository)
    runs = MagicMock(spec=SyncRunsRepository)
    source = MagicMock(id=1, is_active=True)
    sources.get_by_key.return_value = source
    runs.start.return_value = create_sync_run()
    return (
        ApiFootballImportOrchestrator(
            catalog_service=catalog,
            normalization_service=normalization,
            import_service=importer,
            data_sources_repository=sources,
            sync_runs_repository=runs,
        ),
        catalog,
        normalization,
        importer,
        sources,
        runs,
    )


def test_orchestrator_persists_scope_diagnostics_and_decision_counters() -> None:
    orchestrator, catalog, normalization, importer, _sources, runs = (
        create_orchestrator()
    )
    batch = create_batch()
    normalization.normalize_current_premier_league_batch.return_value = batch
    import_result = FixtureImportResult(
        items=(
            FixtureImportItemResult("1", 1, FixtureImportDecision.CREATE),
            FixtureImportItemResult("2", 2, FixtureImportDecision.UPDATE),
            FixtureImportItemResult("3", 3, FixtureImportDecision.SKIP),
            FixtureImportItemResult("4", 4, FixtureImportDecision.CANCEL),
            FixtureImportItemResult("5", 5, FixtureImportDecision.DELETE),
            FixtureImportItemResult("6", None, FixtureImportDecision.DEFER),
        )
    )
    importer.import_fixtures.return_value = import_result

    def complete(**kwargs: object) -> SyncRun:
        counters = {
            key: value for key, value in kwargs.items() if key.startswith("items_")
        }
        return create_sync_run(status="completed", counters=counters)

    runs.complete.side_effect = complete

    result = orchestrator.import_current_premier_league()

    catalog.map_current_premier_league.assert_called_once_with()
    normalization.normalize_current_premier_league_batch.assert_called_once_with()
    scope = importer.import_fixtures.call_args.args[1]
    assert scope.competition_id == 10
    assert scope.season_id == 20
    assert scope.window_start_utc == datetime(2026, 8, 14, tzinfo=UTC)
    assert scope.window_end_utc == datetime.max.replace(
        year=2027,
        month=5,
        day=24,
        tzinfo=UTC,
    )
    assert scope.authoritative is True
    assert scope.complete is True
    assert scope.lifecycle.scope_kind is FixtureObservationScopeKind.COMPLETE_SEASON
    assert scope.removal_eligible is True
    assert scope.filtered is False
    assert scope.observed_at_utc == FETCHED_AT
    assert scope.observation_id.startswith("api-football-")
    complete_call = runs.complete.call_args.kwargs
    assert complete_call["items_processed"] == 6
    assert complete_call["items_created"] == 1
    assert complete_call["items_updated"] == 1
    assert complete_call["items_unchanged"] == 1
    assert complete_call["items_cancelled"] == 1
    assert complete_call["items_deleted"] == 1
    assert complete_call["items_deferred"] == 1
    assert complete_call["items_failed"] == 0
    metadata = complete_call["metadata"]
    assert metadata["job_key"] == "api-football-legacy"
    assert metadata["source_key"] == "api_football"
    assert metadata["role"] == "authoritative"
    assert metadata["competition_key"] == "premier_league"
    assert metadata["season_key"] == "current"
    assert metadata["competition_format"] == "league"
    assert metadata["scope_kind"] == "complete_season"
    assert metadata["scope_stage_kind"] is None
    assert metadata["scope_stage"] is None
    assert metadata["scope_round"] is None
    assert metadata["removal_eligible"] is True
    assert metadata["request_attempts"] == 3
    assert metadata["rate_limits"]["daily_remaining"] == 91
    assert metadata["rate_limits"]["retry_after_seconds"] == 4.0
    assert metadata["observation_id"] == scope.observation_id
    assert result.status == "completed"
    assert result.items_deferred == 1
    runs.fail.assert_not_called()


def test_orchestrator_uses_deterministic_observation_id() -> None:
    first = ApiFootballImportOrchestrator._scope(create_batch())
    second = ApiFootballImportOrchestrator._scope(create_batch())

    assert second.observation_id == first.observation_id


def test_orchestrator_records_sanitized_failure_and_does_not_import() -> None:
    orchestrator, _catalog, normalization, importer, _sources, runs = (
        create_orchestrator()
    )
    normalization.normalize_current_premier_league_batch.side_effect = (
        ProviderRateLimitError(retry_after_seconds=15)
    )
    runs.fail.return_value = create_sync_run(status="failed")

    with pytest.raises(
        ProviderImportOrchestrationError,
        match="ProviderRateLimitError",
    ):
        orchestrator.import_current_premier_league()

    importer.import_fixtures.assert_not_called()
    failure = runs.fail.call_args.kwargs
    assert failure["items_failed"] == 1
    assert failure["error_message"] == (
        "Provider import failed with ProviderRateLimitError."
    )
    assert failure["metadata"]["error_category"] == "ProviderRateLimitError"
    assert failure["metadata"]["complete"] is False
    assert "provider-secret" not in str(failure)


def test_orchestrator_marks_run_failed_when_finalization_fails() -> None:
    orchestrator, _catalog, normalization, importer, _sources, runs = (
        create_orchestrator()
    )
    normalization.normalize_current_premier_league_batch.return_value = create_batch()
    importer.import_fixtures.return_value = FixtureImportResult(items=())
    runs.complete.side_effect = RuntimeError("database unavailable")
    runs.fail.return_value = create_sync_run(status="failed")

    with pytest.raises(
        ProviderImportOrchestrationError,
        match="RuntimeError",
    ):
        orchestrator.import_current_premier_league()

    runs.fail.assert_called_once()
    assert runs.fail.call_args.kwargs["items_failed"] == 1
    assert runs.fail.call_args.kwargs["metadata"]["error_category"] == "RuntimeError"


def test_orchestrator_rejects_inactive_source_without_starting_run() -> None:
    orchestrator, _catalog, _normalization, _importer, sources, runs = (
        create_orchestrator()
    )
    sources.get_by_key.return_value = MagicMock(id=1, is_active=False)

    with pytest.raises(Exception, match="Active API-Football"):
        orchestrator.import_current_premier_league()

    runs.start.assert_not_called()


def test_real_sqlite_run_reporting_is_separate_and_retryable(tmp_path: Path) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sources = DataSourcesRepository(database_path)
    sources.upsert(
        source_key="api_football",
        name="API-Football",
        is_active=True,
    )
    catalog = MagicMock(spec=ApiFootballCatalogService)
    normalization = MagicMock(spec=ApiFootballFixtureNormalizationService)
    normalization.normalize_current_premier_league_batch.return_value = create_batch()
    importer = MagicMock(spec=ApiFootballFixtureImportService)
    importer.import_fixtures.return_value = FixtureImportResult(
        items=(
            FixtureImportItemResult("1", 1, FixtureImportDecision.CREATE),
            FixtureImportItemResult("2", None, FixtureImportDecision.DEFER),
        )
    )
    runs = SyncRunsRepository(database_path)
    orchestrator = ApiFootballImportOrchestrator(
        catalog_service=catalog,
        normalization_service=normalization,
        import_service=importer,
        data_sources_repository=sources,
        sync_runs_repository=runs,
    )

    first = orchestrator.import_current_premier_league()
    second = orchestrator.import_current_premier_league()

    persisted = runs.get_recent(run_type="provider_import")
    assert len(persisted) == 2
    assert all(run.status == "completed" for run in persisted)
    assert first.observation_id == second.observation_id
    assert all(run.items_processed == 2 for run in persisted)
    assert all(run.items_created == 1 for run in persisted)
    assert all(run.items_deferred == 1 for run in persisted)
    assert runs.get_recent(run_type="calendar_sync") == []
