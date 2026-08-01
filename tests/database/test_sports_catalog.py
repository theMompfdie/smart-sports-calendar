import sqlite3
from pathlib import Path

from app.database.database import Database
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[Path, SportsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    return database_path, SportsRepository(database_path)


def test_initialize_sports_catalog_creates_football(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sports = initialize_sports_catalog(repository)

    assert len(sports) == 1

    football = sports[0]

    assert football.sport_key == "football"
    assert football.name == "Football"
    assert football.icon == "⚽"
    assert football.metadata == {
        "category": "team_sport",
    }


def test_initialize_sports_catalog_can_run_repeatedly(
    tmp_path: Path,
) -> None:
    database_path, repository = create_repository(tmp_path)

    first_result = initialize_sports_catalog(repository)
    second_result = initialize_sports_catalog(repository)

    with sqlite3.connect(database_path) as connection:
        sport_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM sports
            WHERE sport_key = ?
            """,
            ("football",),
        ).fetchone()

    assert sport_count == (1,)
    assert second_result[0].id == first_result[0].id


def test_initialize_sports_catalog_restores_master_data(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    repository.upsert(
        sport_key="football",
        name="Incorrect name",
        icon=None,
        metadata=None,
    )

    initialize_sports_catalog(repository)

    football = repository.get_by_key("football")

    assert football is not None
    assert football.name == "Football"
    assert football.icon == "⚽"
    assert football.metadata == {
        "category": "team_sport",
    }
