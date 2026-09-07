import sqlite3
from pathlib import Path

import pytest
from app.application.football_data_premier_league_service import (
    FootballDataCompetitionService,
)
from app.config.settings import FootballDataSettings
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_repository import SportsRepository
from app.domain.competition_lifecycle import CompetitionFormat
from app.providers.football_data.profiles import (
    BUNDESLIGA_PROFILE,
    CHAMPIONSHIP_PROFILE,
    PREMIER_LEAGUE_PROFILE,
    FootballDataCompetitionProfile,
)

from tests.catalog_support import CatalogInitializer
from tests.providers.football_data.support import snapshot


class SnapshotAdapter:
    def __init__(self, profile: FootballDataCompetitionProfile) -> None:
        self.profile = profile
        self._snapshot = snapshot(profile)

    def fetch_snapshot(self, season_year: int):
        assert season_year == 2026
        return self._snapshot


def create_service(
    tmp_path: Path,
    profile: FootballDataCompetitionProfile,
    *,
    initialize_test_catalog: CatalogInitializer,
) -> tuple[FootballDataCompetitionService, Path]:
    database_path = tmp_path / "sports.db"
    initialize_test_catalog(database_path)
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    return (
        FootballDataCompetitionService(
            settings=FootballDataSettings(enabled=True, api_key="test-token"),
            adapter=SnapshotAdapter(profile),
            sports_repository=sports,
            competitions_repository=competitions,
            seasons_repository=seasons,
            participants_repository=participants,
            season_participants_repository=memberships,
            data_sources_repository=DataSourcesRepository(database_path),
            source_mappings_repository=SourceMappingsRepository(database_path),
            profile=profile,
        ),
        database_path,
    )


@pytest.mark.parametrize(
    ("profile", "expected_fixtures", "expected_mappings"),
    [
        (PREMIER_LEAGUE_PROFILE, 380, 22),
        (BUNDESLIGA_PROFILE, 306, 20),
        (CHAMPIONSHIP_PROFILE, 552, 26),
    ],
)
def test_service_normalizes_reviewed_competition_profile(
    tmp_path: Path,
    profile: FootballDataCompetitionProfile,
    expected_fixtures: int,
    expected_mappings: int,
    *,
    initialize_test_catalog: CatalogInitializer,
) -> None:
    service, database_path = create_service(
        tmp_path, profile, initialize_test_catalog=initialize_test_catalog
    )

    batch = service.fetch_normalized_snapshot()

    assert len(batch.fixtures) == expected_fixtures
    assert batch.competition_format is CompetitionFormat.LEAGUE
    assert batch.page_count == 1
    with sqlite3.connect(database_path) as connection:
        mapping_count = connection.execute(
            "SELECT COUNT(*) FROM source_mappings"
        ).fetchone()
        mapping_types = connection.execute(
            "SELECT DISTINCT object_type FROM source_mappings ORDER BY object_type"
        ).fetchall()
    assert mapping_count == (expected_mappings,)
    assert mapping_types == [("competition",), ("participant",), ("season",)]


def test_service_rejects_adapter_for_another_competition(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    _, database_path = create_service(
        tmp_path,
        PREMIER_LEAGUE_PROFILE,
        initialize_test_catalog=initialize_test_catalog,
    )

    with pytest.raises(ValueError, match="profiles differ"):
        FootballDataCompetitionService(
            settings=FootballDataSettings(enabled=True, api_key="test-token"),
            adapter=SnapshotAdapter(BUNDESLIGA_PROFILE),
            sports_repository=SportsRepository(database_path),
            competitions_repository=CompetitionsRepository(database_path),
            seasons_repository=SeasonsRepository(database_path),
            participants_repository=ParticipantsRepository(database_path),
            season_participants_repository=SeasonParticipantsRepository(database_path),
            data_sources_repository=DataSourcesRepository(database_path),
            source_mappings_repository=SourceMappingsRepository(database_path),
            profile=PREMIER_LEAGUE_PROFILE,
        )
