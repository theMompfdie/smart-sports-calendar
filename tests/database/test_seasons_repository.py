import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_repository import SportsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[Path, int, SeasonsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sports_repository = SportsRepository(database_path)
    football = sports_repository.upsert(
        sport_key="football",
        name="Football",
    )

    competitions_repository = CompetitionsRepository(database_path)
    premier_league = competitions_repository.upsert(
        sport_id=football.id,
        competition_key="premier_league",
        name="Premier League",
    )

    return (
        database_path,
        premier_league.id,
        SeasonsRepository(database_path),
    )


def test_get_by_key_returns_none_for_unknown_season(
    tmp_path: Path,
) -> None:
    _, competition_id, repository = create_repository(tmp_path)

    season = repository.get_by_key(
        competition_id=competition_id,
        season_key="unknown",
    )

    assert season is None


def test_upsert_creates_season(
    tmp_path: Path,
) -> None:
    _, competition_id, repository = create_repository(tmp_path)

    season = repository.upsert(
        competition_id=competition_id,
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-30",
        is_current=True,
    )

    assert season.id > 0
    assert season.competition_id == competition_id
    assert season.season_key == "2026_27"
    assert season.name == "2026/27"
    assert season.start_date == "2026-08-21"
    assert season.end_date == "2027-05-30"
    assert season.is_current is True
    assert season.metadata is None
    assert season.created_at
    assert season.updated_at


def test_get_by_key_returns_existing_season(
    tmp_path: Path,
) -> None:
    _, competition_id, repository = create_repository(tmp_path)

    created_season = repository.upsert(
        competition_id=competition_id,
        season_key="2026_27",
        name="2026/27",
    )

    loaded_season = repository.get_by_key(
        competition_id=competition_id,
        season_key="2026_27",
    )

    assert loaded_season == created_season


def test_get_current_for_competition_returns_only_current_seasons(
    tmp_path: Path,
) -> None:
    _, competition_id, repository = create_repository(tmp_path)
    repository.upsert(
        competition_id=competition_id,
        season_key="2025_26",
        name="2025/26",
        is_current=False,
    )
    current_season = repository.upsert(
        competition_id=competition_id,
        season_key="2026_27",
        name="2026/27",
        is_current=True,
    )

    seasons = repository.get_current_for_competition(competition_id)

    assert seasons == [current_season]


def test_upsert_updates_existing_season_without_duplicate(
    tmp_path: Path,
) -> None:
    database_path, competition_id, repository = create_repository(tmp_path)

    original_season = repository.upsert(
        competition_id=competition_id,
        season_key="2026_27",
        name="Incorrect name",
    )

    updated_season = repository.upsert(
        competition_id=competition_id,
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-30",
        is_current=True,
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
                competition_id,
                "2026_27",
            ),
        ).fetchone()

    assert season_count == (1,)
    assert updated_season.id == original_season.id
    assert updated_season.created_at == original_season.created_at
    assert updated_season.name == "2026/27"
    assert updated_season.start_date == "2026-08-21"
    assert updated_season.end_date == "2027-05-30"
    assert updated_season.is_current is True


def test_upsert_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    _, competition_id, repository = create_repository(tmp_path)

    season = repository.upsert(
        competition_id=competition_id,
        season_key="2026_27",
        name="2026/27",
        metadata={
            "provider_season": "2026-27",
            "calendar_category": "SMART | England",
        },
    )

    assert season.metadata == {
        "provider_season": "2026-27",
        "calendar_category": "SMART | England",
    }


def test_upsert_rejects_unknown_competition(
    tmp_path: Path,
) -> None:
    _, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            competition_id=999999,
            season_key="2026_27",
            name="2026/27",
        )
