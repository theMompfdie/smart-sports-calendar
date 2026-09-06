import json
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.oefb_ical_competition_service import register_oefb_ical_source
from app.application.oefb_ical_import_orchestrator import OefbIcalImportOrchestrator
from app.config.settings import OefbIcalSettings
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.fixture_import_repository import FixtureImportRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
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

from tests.catalog_support import CatalogInitializer

OBSERVED_AT = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class SnapshotService:
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
    competition = competitions.get_by_key(football.id, "oefb_cup")
    assert competition is not None
    season = seasons.get_by_key(competition.id, "2026_27")
    assert season is not None
    teams = [
        participants.get_by_key(football.id, key)
        for key in (
            "wiener_viktoria",
            "fac_wien",
            "fk_austria_wien",
            "sv_wienerberg_1921",
        )
    ]
    assert all(team is not None for team in teams)
    home, away, second_home, second_away = teams
    assert home is not None and away is not None
    assert second_home is not None and second_away is not None
    fixture = NormalizedFixture(
        external_id="oefb-event-1",
        sport_id=football.id,
        competition_id=competition.id,
        season_id=season.id,
        event_type="match",
        title=f"{home.name} vs {away.name}",
        participants=(
            NormalizedFixtureParticipant(home.id, "home", 1),
            NormalizedFixtureParticipant(away.id, "away", 2),
        ),
        kickoff_utc=datetime(2026, 8, 28, 18, 0, tzinfo=UTC),
        kickoff_confirmed=True,
        timezone="UTC",
        status="scheduled",
        stage="knockout",
        round_name="round-1",
        sequence_number=1,
        venue_name=None,
        city=None,
        source_updated_at=OBSERVED_AT,
        metadata={"official_url": "https://www.oefb.at/cup/Spiel/1"},
    )
    second = replace(
        fixture,
        external_id="oefb-event-2",
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
        season_start_date=date(2026, 7, 1),
        season_end_date=date(2027, 6, 30),
        fetched_at_utc=OBSERVED_AT,
        page_count=1,
        request_attempts=2,
        rate_limits=RateLimitSnapshot(None, None, None, None, None),
    )


def test_missing_fixture_in_later_partial_observation_is_preserved(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    database_path = tmp_path / "sports.db"
    initialize_test_catalog(database_path)
    settings = OefbIcalSettings(
        enabled=True,
        feed_url="https://www.fussballoesterreich.at/private.ics",
    )
    sources = DataSourcesRepository(database_path)
    register_oefb_ical_source(settings, sources)
    first_batch = create_batch(database_path)
    second_batch = replace(
        first_batch,
        fixtures=first_batch.fixtures[:1],
        fetched_at_utc=OBSERVED_AT + timedelta(minutes=5),
    )
    orchestrator = OefbIcalImportOrchestrator(
        competition_service=SnapshotService([first_batch, second_batch]),
        import_service=ApiFootballFixtureImportService(
            sources,
            FixtureImportRepository(database_path),
            source_key="oefb_ical",
        ),
        sync_runs_repository=SyncRunsRepository(database_path),
        data_sources_repository=sources,
        job_definition=SourceJobDefinition(
            job_key="oefb-ical-oefb-cup",
            source_key="oefb_ical",
            role=SourceRole.AUTHORITATIVE,
            scope=SourceScope("football", "oefb_cup", "2026_27"),
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
    assert metadata["scope_stage_kind"] is None
    assert metadata["scope_stage"] is None
    assert metadata["scope_round"] is None
    assert metadata["complete"] is False
    assert metadata["removal_eligible"] is False


def test_observation_identity_is_stable_for_reordered_fixtures(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    database_path = tmp_path / "sports.db"
    initialize_test_catalog(database_path)
    batch = create_batch(database_path)

    first = OefbIcalImportOrchestrator._scope(batch)
    second = OefbIcalImportOrchestrator._scope(
        replace(batch, fixtures=tuple(reversed(batch.fixtures)))
    )

    assert first.observation_id == second.observation_id
