import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_catalog import (
    initialize_competitions_catalog,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository


def create_repositories(
    tmp_path: Path,
) -> tuple[
    Path,
    SportsRepository,
    CompetitionsRepository,
    SeasonsRepository,
]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sports_repository = SportsRepository(database_path)
    competitions_repository = CompetitionsRepository(database_path)
    seasons_repository = SeasonsRepository(database_path)

    initialize_sports_catalog(sports_repository)
    initialize_competitions_catalog(
        repository=competitions_repository,
        sports_repository=sports_repository,
    )

    return (
        database_path,
        sports_repository,
        competitions_repository,
        seasons_repository,
    )


def test_initialize_seasons_catalog_creates_premier_league_season(
    tmp_path: Path,
) -> None:
    (
        _,
        sports_repository,
        competitions_repository,
        seasons_repository,
    ) = create_repositories(tmp_path)

    seasons = initialize_seasons_catalog(
        repository=seasons_repository,
        competitions_repository=competitions_repository,
        sports_repository=sports_repository,
    )

    assert len(seasons) == 1

    season = seasons[0]
    football = sports_repository.get_by_key("football")

    assert football is not None

    premier_league = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="premier_league",
    )

    assert premier_league is not None
    assert season.competition_id == premier_league.id
    assert season.season_key == "2026_27"
    assert season.name == "2026/27"
    assert season.start_date == "2026-08-21"
    assert season.end_date == "2027-05-30"
    assert season.is_current is True
    assert season.metadata is None


def test_initialize_seasons_catalog_can_run_repeatedly(
    tmp_path: Path,
) -> None:
    (
        database_path,
        sports_repository,
        competitions_repository,
        seasons_repository,
    ) = create_repositories(tmp_path)

    first_result = initialize_seasons_catalog(
        repository=seasons_repository,
        competitions_repository=competitions_repository,
        sports_repository=sports_repository,
    )
    second_result = initialize_seasons_catalog(
        repository=seasons_repository,
        competitions_repository=competitions_repository,
        sports_repository=sports_repository,
    )

    with sqlite3.connect(database_path) as connection:
        season_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM seasons
            WHERE competition_id = ?
              AND season_key = ?
            """,
            (
                first_result[0].competition_id,
                "2026_27",
            ),
        ).fetchone()

    assert season_count == (1,)
    assert second_result[0].id == first_result[0].id
    assert second_result[0].created_at == first_result[0].created_at


def test_initialize_seasons_catalog_restores_master_data(
    tmp_path: Path,
) -> None:
    (
        _,
        sports_repository,
        competitions_repository,
        seasons_repository,
    ) = create_repositories(tmp_path)

    football = sports_repository.get_by_key("football")

    assert football is not None

    premier_league = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="premier_league",
    )

    assert premier_league is not None

    seasons_repository.upsert(
        competition_id=premier_league.id,
        season_key="2026_27",
        name="Incorrect name",
        start_date=None,
        end_date=None,
        is_current=False,
        metadata={"incorrect": True},
    )

    initialize_seasons_catalog(
        repository=seasons_repository,
        competitions_repository=competitions_repository,
        sports_repository=sports_repository,
    )

    season = seasons_repository.get_by_key(
        competition_id=premier_league.id,
        season_key="2026_27",
    )

    assert season is not None
    assert season.name == "2026/27"
    assert season.start_date == "2026-08-21"
    assert season.end_date == "2027-05-30"
    assert season.is_current is True
    assert season.metadata is None


def test_initialize_seasons_catalog_requires_premier_league(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sports_repository = SportsRepository(database_path)
    initialize_sports_catalog(sports_repository)

    with pytest.raises(
        RuntimeError,
        match="Required competition not found.*premier_league",
    ):
        initialize_seasons_catalog(
            repository=SeasonsRepository(database_path),
            competitions_repository=CompetitionsRepository(database_path),
            sports_repository=sports_repository,
        )
