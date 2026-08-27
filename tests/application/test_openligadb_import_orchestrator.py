import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.openligadb_competition_service import register_openligadb_source
from app.application.openligadb_import_orchestrator import (
    OpenLigaDBImportOrchestrator,
)
from app.config.settings import OpenLigaDBSettings
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.fixture_import_repository import FixtureImportRepository
from app.database.participants_catalog import initialize_participants_catalog
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.domain.competition_lifecycle import CompetitionFormat
from app.providers.contracts import (
    NormalizedFixture,
    NormalizedFixtureBatch,
    NormalizedFixtureParticipant,
    RateLimitSnapshot,
    SourceJobDefinition,
    SourceRole,
    SourceScope,
)
from app.providers.openligadb.profiles import DFB_POKAL_PROFILE

OBSERVED_AT = datetime(2026, 8, 18, 20, 0, tzinfo=UTC)


class SnapshotService:
    profile = DFB_POKAL_PROFILE

    def __init__(self, batches: list[NormalizedFixtureBatch]) -> None:
        self._batches = batches

    def fetch_normalized_snapshot(self) -> NormalizedFixtureBatch:
        return self._batches.pop(0)


def create_batch(database_path: Path) -> NormalizedFixtureBatch:
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    football = sports.get_by_key("football")
    assert football is not None
    competition = competitions.get_by_key(football.id, "dfb_pokal")
    assert competition is not None
    season = seasons.get_by_key(competition.id, "2026_27")
    assert season is not None
    home = participants.get_by_key(football.id, "sc_st_toenis")
    away = participants.get_by_key(football.id, "eintracht_frankfurt")
    second_home = participants.get_by_key(football.id, "vfl_osnabrueck")
    second_away = participants.get_by_key(football.id, "fc_bayern_muenchen")
    assert home is not None and away is not None
    assert second_home is not None and second_away is not None
    fixture = NormalizedFixture(
        external_id="7001",
        sport_id=football.id,
        competition_id=competition.id,
        season_id=season.id,
        event_type="match",
        title=f"{home.name} vs {away.name}",
        participants=(
            NormalizedFixtureParticipant(home.id, "home", 1),
            NormalizedFixtureParticipant(away.id, "away", 2),
        ),
        kickoff_utc=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
        kickoff_confirmed=True,
        timezone="UTC",
        status="scheduled",
        stage="knockout",
        round_name="round-1",
        sequence_number=1,
        venue_name=None,
        city=None,
        source_updated_at=datetime(2026, 8, 17, 6, 0, tzinfo=UTC),
        metadata={"provider_group_id": "101"},
    )
    second = replace(
        fixture,
        external_id="7002",
        title=f"{second_home.name} vs {second_away.name}",
        participants=(
            NormalizedFixtureParticipant(second_home.id, "home", 1),
            NormalizedFixtureParticipant(second_away.id, "away", 2),
        ),
        kickoff_utc=fixture.kickoff_utc + timedelta(hours=1),
    )
    return NormalizedFixtureBatch(
        fixtures=(fixture, second),
        competition_id=competition.id,
        competition_format=CompetitionFormat.KNOCKOUT_CUP,
        season_id=season.id,
        season_start_date=datetime(2026, 8, 21).date(),
        season_end_date=datetime(2027, 5, 29).date(),
        fetched_at_utc=OBSERVED_AT,
        page_count=1,
        request_attempts=3,
        rate_limits=RateLimitSnapshot(None, None, None, None, None),
    )


def test_missing_fixture_in_later_partial_observation_is_preserved(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    settings = OpenLigaDBSettings(enabled=True)
    sources = DataSourcesRepository(database_path)
    register_openligadb_source(settings, sources)
    first_batch = create_batch(database_path)
    second_batch = replace(
        first_batch,
        fixtures=first_batch.fixtures[:1],
        fetched_at_utc=OBSERVED_AT + timedelta(minutes=5),
    )
    orchestrator = OpenLigaDBImportOrchestrator(
        competition_service=SnapshotService([first_batch, second_batch]),
        import_service=ApiFootballFixtureImportService(
            sources,
            FixtureImportRepository(database_path),
            source_key="openligadb",
        ),
        sync_runs_repository=SyncRunsRepository(database_path),
        data_sources_repository=sources,
        job_definition=SourceJobDefinition(
            job_key="openligadb-dfb-pokal",
            source_key="openligadb",
            role=SourceRole.AUTHORITATIVE,
            scope=SourceScope("football", "dfb_pokal", "2026_27"),
            interval_seconds=21600,
        ),
    )

    first = orchestrator.import_current_competition()
    second = orchestrator.import_current_competition()

    assert first.items_created == 2
    assert second.items_unchanged == 1
    assert second.items_cancelled == 0
    assert second.items_deleted == 0
    with sqlite3.connect(database_path) as connection:
        events = connection.execute(
            "SELECT status, deleted_at FROM sports_events ORDER BY id"
        ).fetchall()
        metadata_json = connection.execute(
            "SELECT metadata_json FROM sync_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert events == [("scheduled", None), ("scheduled", None)]
    assert metadata_json is not None
    metadata = json.loads(metadata_json[0])
    assert metadata["authoritative_scope"] == "partial"
    assert metadata["scope_kind"] == "partial"
    assert metadata["complete"] is False
    assert metadata["removal_eligible"] is False
