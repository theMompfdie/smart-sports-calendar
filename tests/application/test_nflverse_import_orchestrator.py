import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.api_football_import_orchestrator import (
    ProviderImportOrchestrationError,
)
from app.application.nflverse_competition_service import (
    NflverseCompetitionService,
    register_nflverse_source,
)
from app.application.nflverse_import_orchestrator import NflverseImportOrchestrator
from app.config.settings import NflverseSettings
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.fixture_import_repository import FixtureImportRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.providers.contracts import SourceJobDefinition, SourceRole, SourceScope
from app.providers.nflverse.models import parse_snapshot
from app.providers.nflverse.profiles import NFL_2026_REGULAR_SEASON_PROFILE

from tests.catalog_support import CatalogInitializer
from tests.providers.nflverse.support import csv_bytes, schedule_rows

OBSERVED_AT = datetime(2026, 8, 30, 12, tzinfo=UTC)


class MutableAdapter:
    profile = NFL_2026_REGULAR_SEASON_PROFILE

    def __init__(self) -> None:
        self.rows = schedule_rows()
        self.observed_at = OBSERVED_AT

    def fetch_snapshot(self):
        return parse_snapshot(
            csv_bytes(self.rows),
            profile=self.profile,
            fetched_at_utc=self.observed_at,
            request_attempts=1,
        )


def build_orchestrator(
    database_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> tuple[NflverseImportOrchestrator, MutableAdapter, SyncRunsRepository]:
    initialize_test_catalog(database_path)
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    mappings = SourceMappingsRepository(database_path)
    settings = NflverseSettings(enabled=True)
    register_nflverse_source(settings, sources)
    adapter = MutableAdapter()
    service = NflverseCompetitionService(
        adapter,
        sports,
        competitions,
        seasons,
        participants,
        settings=settings,
        season_participants_repository=memberships,
        data_sources_repository=sources,
        source_mappings_repository=mappings,
    )
    runs = SyncRunsRepository(database_path)
    orchestrator = NflverseImportOrchestrator(
        competition_service=service,
        import_service=ApiFootballFixtureImportService(
            sources,
            FixtureImportRepository(database_path),
            source_key="nflverse",
        ),
        sync_runs_repository=runs,
        data_sources_repository=sources,
        job_definition=SourceJobDefinition(
            job_key="nflverse-nfl-2026",
            source_key="nflverse",
            role=SourceRole.AUTHORITATIVE,
            scope=SourceScope("american_football", "nfl", "2026"),
            interval_seconds=21600,
        ),
    )
    return orchestrator, adapter, runs


def event_state(database_path: Path) -> list[tuple[str, str, str | None, str | None]]:
    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            """
            SELECT event_key, start_time, cancelled_at, deleted_at
            FROM sports_events ORDER BY event_key
            """
        ).fetchall()


def test_import_creates_272_fixtures_then_skips_unchanged_snapshot(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    database_path = tmp_path / "sports.db"
    orchestrator, adapter, runs = build_orchestrator(
        database_path, initialize_test_catalog=initialize_test_catalog
    )

    first = orchestrator.import_current_competition()
    adapter.observed_at += timedelta(hours=6)
    second = orchestrator.import_current_competition()

    assert first.items_created == 272
    assert first.items_cancelled == first.items_deleted == 0
    assert second.items_unchanged == 272
    assert second.items_updated == second.items_cancelled == second.items_deleted == 0
    assert len(event_state(database_path)) == 272
    latest = runs.get_by_id(second.sync_run_id)
    assert latest is not None
    assert latest.metadata is not None
    assert latest.metadata["complete"] is False
    assert latest.metadata["authoritative_scope"] == "partial"
    assert latest.metadata["removal_eligible"] is False
    with sqlite3.connect(database_path) as connection:
        source = connection.execute(
            "SELECT metadata_json FROM data_sources WHERE source_key = 'nflverse'"
        ).fetchone()
        mapping_counts = connection.execute(
            """
            SELECT object_type, COUNT(*) FROM source_mappings
            WHERE source_id = (
                SELECT id FROM data_sources WHERE source_key = 'nflverse'
            )
            GROUP BY object_type ORDER BY object_type
            """
        ).fetchall()
    assert source is not None and "CC-BY-4.0" in source[0]
    assert mapping_counts == [
        ("competition", 1),
        ("event", 272),
        ("participant", 32),
        ("season", 1),
    ]


def test_flex_change_updates_stable_game_without_duplicate(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    database_path = tmp_path / "sports.db"
    orchestrator, adapter, _ = build_orchestrator(
        database_path, initialize_test_catalog=initialize_test_catalog
    )
    first = orchestrator.import_current_competition()
    target_id = adapter.rows[0]["game_id"]
    adapter.rows[0]["gametime"] = "20:30"
    adapter.observed_at += timedelta(hours=6)

    second = orchestrator.import_current_competition()

    assert first.items_created == 272
    assert second.items_updated == 1
    assert second.items_unchanged == 271
    events = event_state(database_path)
    assert len(events) == 272
    changed = next(event for event in events if event[0].endswith(target_id))
    assert changed[1].endswith("00:30:00+00:00")


def test_invalid_partial_observation_preserves_last_known_good_state(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    database_path = tmp_path / "sports.db"
    orchestrator, adapter, runs = build_orchestrator(
        database_path, initialize_test_catalog=initialize_test_catalog
    )
    first = orchestrator.import_current_competition()
    before = event_state(database_path)
    adapter.rows.pop()
    adapter.observed_at += timedelta(hours=6)

    with pytest.raises(ProviderImportOrchestrationError):
        orchestrator.import_current_competition()

    assert first.items_created == 272
    assert event_state(database_path) == before
    failed = runs.get_by_status("failed")
    assert len(failed) == 1
    assert failed[0].metadata is not None
    assert failed[0].metadata["complete"] is False
    assert failed[0].metadata["removal_eligible"] is False
