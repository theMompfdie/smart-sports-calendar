import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_catalog import (
    initialize_competitions_catalog,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository


def create_repositories(
    tmp_path: Path,
) -> tuple[Path, SportsRepository, CompetitionsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sports_repository = SportsRepository(database_path)
    competitions_repository = CompetitionsRepository(database_path)

    initialize_sports_catalog(sports_repository)

    return (
        database_path,
        sports_repository,
        competitions_repository,
    )


def test_initialize_competitions_catalog_creates_premier_league(
    tmp_path: Path,
) -> None:
    _, sports_repository, competitions_repository = create_repositories(tmp_path)

    competitions = initialize_competitions_catalog(
        repository=competitions_repository,
        sports_repository=sports_repository,
    )

    assert len(competitions) == 1

    premier_league = competitions[0]
    football = sports_repository.get_by_key("football")

    assert football is not None
    assert premier_league.sport_id == football.id
    assert premier_league.competition_key == "premier_league"
    assert premier_league.name == "Premier League"
    assert premier_league.short_name == "PL"
    assert premier_league.country_code == "GB-ENG"
    assert premier_league.competition_type == "league"
    assert premier_league.metadata == {
        "region": "England",
        "calendar_category": "SMART | England",
    }


def test_initialize_competitions_catalog_can_run_repeatedly(
    tmp_path: Path,
) -> None:
    database_path, sports_repository, competitions_repository = create_repositories(
        tmp_path
    )

    first_result = initialize_competitions_catalog(
        repository=competitions_repository,
        sports_repository=sports_repository,
    )
    second_result = initialize_competitions_catalog(
        repository=competitions_repository,
        sports_repository=sports_repository,
    )

    with sqlite3.connect(database_path) as connection:
        competition_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM competitions
            WHERE competition_key = ?
            """,
            ("premier_league",),
        ).fetchone()

    assert competition_count == (1,)
    assert second_result[0].id == first_result[0].id
    assert second_result[0].created_at == first_result[0].created_at


def test_initialize_competitions_catalog_restores_master_data(
    tmp_path: Path,
) -> None:
    _, sports_repository, competitions_repository = create_repositories(tmp_path)

    football = sports_repository.get_by_key("football")

    assert football is not None

    competitions_repository.upsert(
        sport_id=football.id,
        competition_key="premier_league",
        name="Incorrect name",
        short_name=None,
        country_code=None,
        competition_type=None,
        metadata=None,
    )

    initialize_competitions_catalog(
        repository=competitions_repository,
        sports_repository=sports_repository,
    )

    premier_league = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="premier_league",
    )

    assert premier_league is not None
    assert premier_league.name == "Premier League"
    assert premier_league.short_name == "PL"
    assert premier_league.country_code == "GB-ENG"
    assert premier_league.competition_type == "league"
    assert premier_league.metadata == {
        "region": "England",
        "calendar_category": "SMART | England",
    }


def test_initialize_competitions_catalog_requires_football(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    with pytest.raises(
        RuntimeError,
        match="Required sport not found.*football",
    ):
        initialize_competitions_catalog(
            repository=CompetitionsRepository(database_path),
            sports_repository=SportsRepository(database_path),
        )
