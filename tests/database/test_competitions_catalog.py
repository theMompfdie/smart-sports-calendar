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


def test_initialize_competitions_catalog_creates_reviewed_competitions(
    tmp_path: Path,
) -> None:
    _, sports_repository, competitions_repository = create_repositories(tmp_path)

    competitions = initialize_competitions_catalog(
        repository=competitions_repository,
        sports_repository=sports_repository,
    )

    assert len(competitions) == 3

    by_key = {competition.competition_key: competition for competition in competitions}
    premier_league = by_key["premier_league"]
    bundesliga = by_key["bundesliga"]
    dfb_pokal = by_key["dfb_pokal"]
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
    assert bundesliga.sport_id == football.id
    assert bundesliga.name == "Bundesliga"
    assert bundesliga.short_name == "BL"
    assert bundesliga.country_code == "DE"
    assert bundesliga.competition_type == "league"
    assert bundesliga.metadata == {
        "region": "Germany",
        "calendar_category": "SMART | Germany",
    }
    assert dfb_pokal.sport_id == football.id
    assert dfb_pokal.name == "DFB-Pokal"
    assert dfb_pokal.short_name == "DFB"
    assert dfb_pokal.country_code == "DE"
    assert dfb_pokal.competition_type == "knockout_cup"
    assert dfb_pokal.metadata == {
        "region": "Germany",
        "calendar_category": "SMART | Germany",
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
    assert [item.id for item in second_result] == [item.id for item in first_result]
    assert [item.created_at for item in second_result] == [
        item.created_at for item in first_result
    ]


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

    bundesliga = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="bundesliga",
    )
    assert bundesliga is not None
    competitions_repository.upsert(
        sport_id=football.id,
        competition_key="bundesliga",
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

    restored_bundesliga = competitions_repository.get_by_key(
        sport_id=football.id,
        competition_key="bundesliga",
    )
    assert restored_bundesliga is not None
    assert restored_bundesliga.id == bundesliga.id
    assert restored_bundesliga.name == "Bundesliga"
    assert restored_bundesliga.short_name == "BL"
    assert restored_bundesliga.country_code == "DE"
    assert restored_bundesliga.competition_type == "league"
    assert restored_bundesliga.metadata == {
        "region": "Germany",
        "calendar_category": "SMART | Germany",
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
