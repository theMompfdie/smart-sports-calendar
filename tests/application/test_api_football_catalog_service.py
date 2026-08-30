import sqlite3
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest
from app.application.api_football_catalog_service import ApiFootballCatalogService
from app.config.settings import ApiFootballSettings
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.participants_catalog import initialize_participants_catalog
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository
from app.providers.api_football.catalog_models import (
    ApiFootballLeague,
    ApiFootballSeason,
    ApiFootballTeam,
    parse_league,
    parse_team,
)
from app.providers.api_football.exceptions import (
    ProviderIntegrityError,
    ProviderResolutionError,
)
from app.providers.api_football.team_mappings import PREMIER_LEAGUE_TEAM_MAPPING

from tests.providers.api_football.catalog_test_support import load_envelope


@dataclass
class StaticCatalogAdapter:
    league: ApiFootballLeague
    teams: tuple[ApiFootballTeam, ...]

    def find_premier_league(self) -> ApiFootballLeague:
        return self.league

    def find_current_season(
        self,
        league: ApiFootballLeague,
    ) -> ApiFootballSeason:
        return tuple(season for season in league.seasons if season.is_current)[0]

    def fetch_teams(
        self,
        league_id: int,
        season_year: int,
    ) -> tuple[ApiFootballTeam, ...]:
        assert league_id == self.league.id
        assert season_year == 2026
        return self.teams


@dataclass(frozen=True)
class ServiceContext:
    database_path: Path
    service: ApiFootballCatalogService
    sports: SportsRepository
    competitions: CompetitionsRepository
    seasons: SeasonsRepository
    participants: ParticipantsRepository
    memberships: SeasonParticipantsRepository
    sources: DataSourcesRepository
    mappings: SourceMappingsRepository


def create_context(
    tmp_path: Path,
    *,
    teams: tuple[ApiFootballTeam, ...] | None = None,
    team_mapping: dict[str, str] | None = None,
) -> ServiceContext:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    mappings = SourceMappingsRepository(database_path)

    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    initialize_participants_catalog(
        participants,
        memberships,
        sports,
        competitions,
        seasons,
    )

    league = parse_league(load_envelope("premier_league.json")["response"][0])
    parsed_teams = tuple(
        parse_team(item)
        for item in load_envelope("premier_league_teams.json")["response"]
    )
    adapter = StaticCatalogAdapter(
        league=league,
        teams=teams if teams is not None else parsed_teams,
    )
    service = ApiFootballCatalogService(
        settings=ApiFootballSettings(enabled=True, api_key="provider-secret"),
        adapter=adapter,  # type: ignore[arg-type]
        sports_repository=sports,
        competitions_repository=competitions,
        seasons_repository=seasons,
        participants_repository=participants,
        season_participants_repository=memberships,
        data_sources_repository=sources,
        source_mappings_repository=mappings,
        team_mapping=(
            team_mapping if team_mapping is not None else PREMIER_LEAGUE_TEAM_MAPPING
        ),
    )

    return ServiceContext(
        database_path=database_path,
        service=service,
        sports=sports,
        competitions=competitions,
        seasons=seasons,
        participants=participants,
        memberships=memberships,
        sources=sources,
        mappings=mappings,
    )


def table_count(database_path: Path, table: str) -> int:
    with sqlite3.connect(database_path) as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_service_maps_provider_catalog_to_existing_canonical_rows(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    football = context.sports.get_by_key("football")
    assert football is not None
    competition_before = context.competitions.get_by_key(football.id, "premier_league")
    assert competition_before is not None
    participants_before = {
        key: context.participants.get_by_key(football.id, key)
        for key in PREMIER_LEAGUE_TEAM_MAPPING.values()
    }

    result = context.service.map_current_premier_league()

    assert result.data_source.source_key == "api_football"
    assert result.data_source.base_url == "https://v3.football.api-sports.io"
    assert result.data_source.metadata == {
        "api_version_family": "v3",
        "authentication": "x-apisports-key",
        "provider": "API-Football",
    }
    assert "provider-secret" not in str(result.data_source)
    assert result.competition.id == competition_before.id
    assert result.season.season_key == "2026_27"
    assert len(result.participants) == 20
    assert len(result.mappings) == 22
    assert {
        (mapping.object_type, mapping.external_id)
        for mapping in result.mappings
        if mapping.object_type in {"competition", "season"}
    } == {
        ("competition", "39"),
        ("season", "2026"),
    }
    assert {
        mapping.external_id
        for mapping in result.mappings
        if mapping.object_type == "participant"
    } == set(PREMIER_LEAGUE_TEAM_MAPPING)
    assert table_count(context.database_path, "data_sources") == 1
    assert table_count(context.database_path, "source_mappings") == 22
    assert table_count(context.database_path, "participants") == 188
    assert table_count(context.database_path, "season_participants") == 224
    assert all(
        participant is not None and result_participant.id == participant.id
        for result_participant, participant in zip(
            sorted(result.participants, key=lambda item: item.participant_key),
            sorted(
                participants_before.values(),
                key=lambda item: item.participant_key if item is not None else "",
            ),
            strict=True,
        )
    )


def test_service_is_idempotent_without_timestamp_churn(tmp_path: Path) -> None:
    context = create_context(tmp_path)

    first = context.service.map_current_premier_league()
    second = context.service.map_current_premier_league()

    assert second.data_source == first.data_source
    assert second.mappings == first.mappings
    assert table_count(context.database_path, "data_sources") == 1
    assert table_count(context.database_path, "source_mappings") == 22
    assert table_count(context.database_path, "participants") == 188
    assert table_count(context.database_path, "season_participants") == 224


def test_service_uses_external_ids_even_when_provider_names_change(
    tmp_path: Path,
) -> None:
    teams_payload = deepcopy(load_envelope("premier_league_teams.json")["response"])
    for index, item in enumerate(teams_payload):
        item["team"]["name"] = f"Provider Display Name {index}"
    teams = tuple(parse_team(item) for item in teams_payload)
    context = create_context(tmp_path, teams=teams)

    result = context.service.map_current_premier_league()

    arsenal_mapping = context.mappings.get_by_external_id(
        source_id=result.data_source.id,
        object_type="participant",
        external_id="42",
    )
    football = context.sports.get_by_key("football")
    assert football is not None
    arsenal = context.participants.get_by_key(football.id, "arsenal")
    assert arsenal is not None
    assert arsenal_mapping is not None
    assert arsenal_mapping.internal_id == arsenal.id
    assert arsenal_mapping.metadata["provider_name"] == "Provider Display Name 0"


def test_service_rejects_incomplete_team_collection_before_writing(
    tmp_path: Path,
) -> None:
    teams = tuple(
        parse_team(item)
        for item in load_envelope("premier_league_teams.json")["response"][:-1]
    )
    context = create_context(tmp_path, teams=teams)

    with pytest.raises(ProviderIntegrityError, match="missing_ids"):
        context.service.map_current_premier_league()

    assert table_count(context.database_path, "data_sources") == 0
    assert table_count(context.database_path, "source_mappings") == 0


def test_service_rejects_unknown_canonical_participant_before_writing(
    tmp_path: Path,
) -> None:
    mapping = dict(PREMIER_LEAGUE_TEAM_MAPPING)
    mapping["42"] = "unknown_team"
    context = create_context(tmp_path, team_mapping=mapping)

    with pytest.raises(ProviderResolutionError, match="unknown canonical participant"):
        context.service.map_current_premier_league()

    assert table_count(context.database_path, "data_sources") == 0
    assert table_count(context.database_path, "source_mappings") == 0


def test_service_rejects_incompatible_canonical_current_season(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    football = context.sports.get_by_key("football")
    assert football is not None
    competition = context.competitions.get_by_key(football.id, "premier_league")
    assert competition is not None
    context.seasons.upsert(
        competition_id=competition.id,
        season_key="2026_27",
        name="2026/27",
        start_date="2025-08-21",
        end_date="2027-05-30",
        is_current=True,
    )

    with pytest.raises(ProviderResolutionError, match="seasons are incompatible"):
        context.service.map_current_premier_league()


def test_service_rejects_missing_canonical_current_season(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    football = context.sports.get_by_key("football")
    assert football is not None
    competition = context.competitions.get_by_key(football.id, "premier_league")
    assert competition is not None
    context.seasons.upsert(
        competition_id=competition.id,
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-30",
        is_current=False,
    )

    with pytest.raises(ProviderResolutionError, match="exactly one current season"):
        context.service.map_current_premier_league()


def test_service_rejects_mapping_conflict_without_partial_team_mappings(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    source = context.sources.upsert(
        source_key="api_football",
        name="API-Football",
        base_url="https://v3.football.api-sports.io",
        metadata={
            "api_version_family": "v3",
            "authentication": "x-apisports-key",
            "provider": "API-Football",
        },
    )
    football = context.sports.get_by_key("football")
    assert football is not None
    wrong_competition = context.competitions.upsert(
        sport_id=football.id,
        competition_key="wrong_competition",
        name="Wrong Competition",
    )
    context.mappings.upsert(
        source_id=source.id,
        object_type="competition",
        internal_id=wrong_competition.id,
        external_id="39",
    )

    with pytest.raises(ProviderIntegrityError, match="external ID conflicts"):
        context.service.map_current_premier_league()

    assert context.mappings.get_for_source(source.id, "participant") == []
