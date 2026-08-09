import json
from pathlib import Path

import pytest
from app.application.football_data_premier_league_service import (
    register_football_data_source,
)
from app.config.settings import FootballDataSettings
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.source_assignments_repository import (
    SourceAssignmentsRepository,
    SourceAssignmentWrite,
)
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.operations.staging_evidence import (
    collect_staging_evidence,
    main,
    render_staging_evidence,
)
from app.providers.contracts import SourceRole


def create_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "sports.db"
    database = Database(database_path)
    database.initialize()
    database.record_startup()
    return database_path


def test_collect_staging_evidence_returns_only_safe_operational_fields(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)
    repository = SyncRunsRepository(database_path)

    completed = repository.start(
        run_type="provider_import",
        metadata={"api_key": "provider-secret", "calendar_id": "calendar-secret"},
    )
    repository.complete(
        completed.id,
        items_processed=8,
        items_created=5,
        items_updated=1,
        items_unchanged=2,
        items_deleted=0,
        items_failed=0,
        metadata={"authorization": "Bearer graph-secret"},
    )
    failed = repository.start(run_type="calendar_sync")
    repository.fail(
        failed.id,
        error_message="request exposed-secret failed",
        metadata={"url": "https://example.invalid/?token=secret-value"},
    )

    evidence = collect_staging_evidence(database_path)
    rendered = render_staging_evidence(evidence)
    payload = json.loads(rendered)

    assert payload["database_quick_check"] == "ok"
    assert payload["schema_version"] == "007_create_source_assignments"
    assert payload["startup_records"] == 1
    assert payload["sports_events"] == 0
    assert payload["active_authorities"] == []
    assert payload["fixture_scopes"] == []
    assert payload["calendar_mappings_by_status"] == {}
    assert [run["run_type"] for run in payload["recent_runs"]] == [
        "calendar_sync",
        "provider_import",
    ]
    assert payload["recent_runs"][1]["items_created"] == 5
    assert "provider-secret" not in rendered
    assert "calendar-secret" not in rendered
    assert "graph-secret" not in rendered
    assert "exposed-secret" not in rendered
    assert "secret-value" not in rendered
    assert "metadata" not in rendered
    assert "error_message" not in rendered


def test_collect_staging_evidence_reports_safe_authoritative_fixture_scope(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)

    football = sports.get_by_key("football")
    assert football is not None
    premier_league = competitions.get_by_key(football.id, "premier_league")
    assert premier_league is not None
    current_seasons = seasons.get_current_for_competition(premier_league.id)
    assert len(current_seasons) == 1
    season = current_seasons[0]
    source = register_football_data_source(
        FootballDataSettings(enabled=True, api_key="provider-secret"),
        sources,
    )
    SourceAssignmentsRepository(database_path).synchronize(
        (
            SourceAssignmentWrite(
                job_key="football-data-premier-league",
                source_id=source.id,
                competition_id=premier_league.id,
                season_id=season.id,
                role=SourceRole.AUTHORITATIVE,
                interval_seconds=3600,
            ),
        )
    )
    event = SportsEventsRepository(database_path).upsert(
        sport_id=football.id,
        competition_id=premier_league.id,
        season_id=season.id,
        event_key="football-data:provider-match-secret",
        event_type="match",
        title="Secret Home vs Secret Away",
        start_time="2026-08-21T19:00:00+00:00",
        status="scheduled",
        source_updated_at="2026-07-09T01:25:00+00:00",
        metadata={"raw_provider_secret": "fixture-metadata-secret"},
    )
    SourceMappingsRepository(database_path).upsert(
        source_id=source.id,
        object_type="event",
        internal_id=event.id,
        external_id="provider-match-secret",
        source_url="https://example.invalid/secret-fixture-url",
        metadata={"raw": "mapping-metadata-secret"},
    )

    rendered = render_staging_evidence(collect_staging_evidence(database_path))
    payload = json.loads(rendered)

    assert payload["active_authorities"] == [
        {
            "competition_key": "premier_league",
            "interval_seconds": 3600,
            "role": "authoritative",
            "season_key": "2026_27",
            "source_key": "football_data",
            "sport_key": "football",
        }
    ]
    assert payload["fixture_scopes"] == [
        {
            "competition_key": "premier_league",
            "earliest_start_utc": "2026-08-21T19:00:00+00:00",
            "fixtures_active": 1,
            "fixtures_deleted": 0,
            "fixtures_total": 1,
            "latest_source_update_utc": "2026-07-09T01:25:00+00:00",
            "latest_start_utc": "2026-08-21T19:00:00+00:00",
            "season_key": "2026_27",
            "source_event_mappings": 1,
            "source_key": "football_data",
            "status_counts": {"scheduled": 1},
        }
    ]
    for excluded_value in (
        "provider-secret",
        "provider-match-secret",
        "Secret Home",
        "Secret Away",
        "fixture-metadata-secret",
        "secret-fixture-url",
        "mapping-metadata-secret",
        "api.football-data.org",
    ):
        assert excluded_value not in rendered


def test_collect_staging_evidence_is_read_only(tmp_path: Path) -> None:
    database_path = create_database(tmp_path)

    first = collect_staging_evidence(database_path)
    second = collect_staging_evidence(database_path)

    assert first == second


def test_collect_staging_evidence_rejects_invalid_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        collect_staging_evidence(tmp_path / "missing.db")

    database_path = create_database(tmp_path)
    with pytest.raises(ValueError, match="limit must be greater than zero"):
        collect_staging_evidence(database_path, limit=0)


def test_main_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database_path = create_database(tmp_path)

    result = main(["--database", str(database_path), "--limit", "1"])

    assert result == 0
    assert json.loads(capsys.readouterr().out)["database_quick_check"] == "ok"
