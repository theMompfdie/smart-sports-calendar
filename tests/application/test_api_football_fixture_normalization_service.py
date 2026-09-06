import sqlite3
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest
from app.application.api_football_catalog_service import register_api_football_source
from app.application.api_football_fixture_normalization_service import (
    ApiFootballFixtureNormalizationService,
)
from app.config.settings import ApiFootballSettings
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_repository import SportsRepository
from app.providers.api_football.exceptions import ProviderResolutionError
from app.providers.api_football.fixture_adapter import ApiFootballFixtureAdapter
from app.providers.api_football.models import ApiFootballCollection
from app.providers.api_football.team_mappings import PREMIER_LEAGUE_TEAM_MAPPING

from tests.catalog_support import CatalogInitializer
from tests.providers.api_football.catalog_test_support import (
    create_collection,
    load_envelope,
)


@dataclass
class StaticFixtureClient:
    collection: ApiFootballCollection

    def get_all(
        self,
        endpoint: str,
        query: dict[str, str | int] | None = None,
    ) -> ApiFootballCollection:
        assert endpoint == "/fixtures"
        assert query == {"league": 39, "season": 2026}
        return self.collection


@dataclass(frozen=True)
class ServiceContext:
    database_path: Path
    service: ApiFootballFixtureNormalizationService
    source_id: int
    competition_id: int
    season_id: int
    mappings: SourceMappingsRepository


def create_context(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> ServiceContext:
    database_path = tmp_path / "sports.db"
    initialize_test_catalog(database_path)
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    mappings = SourceMappingsRepository(database_path)

    source = register_api_football_source(
        settings=ApiFootballSettings(enabled=True, api_key="provider-secret"),
        repository=sources,
    )
    football = sports.get_by_key("football")
    assert football is not None
    competition = competitions.get_by_key(football.id, "premier_league")
    assert competition is not None
    season = seasons.get_by_key(competition.id, "2026_27")
    assert season is not None
    mappings.upsert(source.id, "competition", competition.id, "39")
    mappings.upsert(source.id, "season", season.id, "2026")
    for external_id, participant_key in PREMIER_LEAGUE_TEAM_MAPPING.items():
        participant = participants.get_by_key(football.id, participant_key)
        assert participant is not None
        mappings.upsert(source.id, "participant", participant.id, external_id)

    items = deepcopy(load_envelope("premier_league_fixtures.json")["response"])
    adapter = ApiFootballFixtureAdapter(StaticFixtureClient(create_collection(items)))
    return ServiceContext(
        database_path=database_path,
        service=ApiFootballFixtureNormalizationService(
            adapter=adapter,
            sports_repository=sports,
            competitions_repository=competitions,
            seasons_repository=seasons,
            participants_repository=participants,
            data_sources_repository=sources,
            source_mappings_repository=mappings,
        ),
        source_id=source.id,
        competition_id=competition.id,
        season_id=season.id,
        mappings=mappings,
    )


def test_service_normalizes_mapped_fixtures_without_persistence(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    context = create_context(tmp_path, initialize_test_catalog=initialize_test_catalog)

    fixtures = context.service.normalize_current_premier_league()

    assert len(fixtures) == 10
    first = fixtures[0]
    assert first.external_id == "900001"
    assert first.competition_id == context.competition_id
    assert first.season_id == context.season_id
    assert first.event_type == "match"
    assert first.title == "Arsenal vs Aston Villa"
    assert [(item.role, item.position_number) for item in first.participants] == [
        ("home", 1),
        ("away", 2),
    ]
    assert first.timezone == "UTC"
    assert first.metadata is None

    tbd = fixtures[1]
    assert tbd.kickoff_utc is None
    assert tbd.kickoff_confirmed is False

    assert {fixture.status for fixture in fixtures} == {
        "scheduled",
        "live",
        "finished",
        "postponed",
        "cancelled",
        "suspended",
        "abandoned",
    }
    assert fixtures[-1].metadata == {
        "provider_status_code": "WO",
        "provider_status_reason": "Walkover",
    }
    with sqlite3.connect(context.database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sports_events").fetchone() == (
            0,
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM event_participants"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM source_mappings WHERE object_type = 'event'"
        ).fetchone() == (0,)


def test_service_is_deterministic_and_uses_canonical_names(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    context = create_context(tmp_path, initialize_test_catalog=initialize_test_catalog)

    first = context.service.normalize_current_premier_league()
    second = context.service.normalize_current_premier_league()

    assert second == first
    assert first[0].title == "Arsenal vs Aston Villa"
    assert "Provider" not in first[0].title


def test_service_rejects_missing_participant_mapping(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    context = create_context(tmp_path, initialize_test_catalog=initialize_test_catalog)
    assert context.mappings.delete(context.source_id, "participant", "42") is True

    with pytest.raises(ProviderResolutionError, match="no canonical source mapping"):
        context.service.normalize_current_premier_league()


def test_service_rejects_conflicting_scope_mapping(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    context = create_context(tmp_path, initialize_test_catalog=initialize_test_catalog)
    assert context.mappings.delete(context.source_id, "competition", "39") is True
    context.mappings.upsert(context.source_id, "competition", 999999, "39")

    with pytest.raises(ProviderResolutionError, match="missing or conflicting"):
        context.service.normalize_current_premier_league()
