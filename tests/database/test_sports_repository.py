import sqlite3
from pathlib import Path

from app.database.database import Database
from app.database.sports_repository import SportsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[Path, SportsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    return database_path, SportsRepository(database_path)


def test_get_by_key_returns_none_for_unknown_sport(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sport = repository.get_by_key("unknown")

    assert sport is None


def test_upsert_creates_sport(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sport = repository.upsert(
        sport_key="football",
        name="Football",
        icon="⚽",
    )

    assert sport.id > 0
    assert sport.sport_key == "football"
    assert sport.name == "Football"
    assert sport.icon == "⚽"
    assert sport.metadata is None
    assert sport.created_at
    assert sport.updated_at


def test_get_by_key_returns_existing_sport(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    created_sport = repository.upsert(
        sport_key="football",
        name="Football",
    )

    loaded_sport = repository.get_by_key("football")

    assert loaded_sport == created_sport


def test_upsert_updates_existing_sport_without_duplicate(
    tmp_path: Path,
) -> None:
    database_path, repository = create_repository(tmp_path)

    original_sport = repository.upsert(
        sport_key="football",
        name="Football",
        icon=None,
    )

    updated_sport = repository.upsert(
        sport_key="football",
        name="Association Football",
        icon="⚽",
    )

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
    assert updated_sport.id == original_sport.id
    assert updated_sport.created_at == original_sport.created_at
    assert updated_sport.name == "Association Football"
    assert updated_sport.icon == "⚽"


def test_upsert_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    _, repository = create_repository(tmp_path)

    sport = repository.upsert(
        sport_key="football",
        name="Football",
        metadata={
            "category": "team_sport",
            "periods": 2,
            "uses_extra_time": True,
        },
    )

    assert sport.metadata == {
        "category": "team_sport",
        "periods": 2,
        "uses_extra_time": True,
    }
