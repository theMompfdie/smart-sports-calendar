import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.sports_repository import SportsRepository
from app.domain.competition_lifecycle import CompetitionFormat


def create_repository(
    tmp_path: Path,
) -> tuple[Path, int, CompetitionsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sports_repository = SportsRepository(database_path)
    football = sports_repository.upsert(
        sport_key="football",
        name="Football",
    )

    return (
        database_path,
        football.id,
        CompetitionsRepository(database_path),
    )


def test_get_by_key_returns_none_for_unknown_competition(
    tmp_path: Path,
) -> None:
    _, football_id, repository = create_repository(tmp_path)

    competition = repository.get_by_key(
        sport_id=football_id,
        competition_key="unknown",
    )

    assert competition is None


def test_upsert_creates_competition(
    tmp_path: Path,
) -> None:
    _, football_id, repository = create_repository(tmp_path)

    competition = repository.upsert(
        sport_id=football_id,
        competition_key="premier_league",
        name="Premier League",
        short_name="PL",
        country_code="GB-ENG",
        competition_type="league",
    )

    assert competition.id > 0
    assert competition.sport_id == football_id
    assert competition.competition_key == "premier_league"
    assert competition.name == "Premier League"
    assert competition.short_name == "PL"
    assert competition.country_code == "GB-ENG"
    assert competition.competition_type == "league"
    assert competition.competition_type is CompetitionFormat.LEAGUE
    assert competition.metadata is None
    assert competition.created_at
    assert competition.updated_at


def test_get_by_key_returns_existing_competition(
    tmp_path: Path,
) -> None:
    _, football_id, repository = create_repository(tmp_path)

    created_competition = repository.upsert(
        sport_id=football_id,
        competition_key="premier_league",
        name="Premier League",
    )

    loaded_competition = repository.get_by_key(
        sport_id=football_id,
        competition_key="premier_league",
    )

    assert loaded_competition == created_competition


def test_upsert_updates_existing_competition_without_duplicate(
    tmp_path: Path,
) -> None:
    database_path, football_id, repository = create_repository(tmp_path)

    original_competition = repository.upsert(
        sport_id=football_id,
        competition_key="premier_league",
        name="Incorrect name",
    )

    updated_competition = repository.upsert(
        sport_id=football_id,
        competition_key="premier_league",
        name="Premier League",
        short_name="PL",
        country_code="GB-ENG",
        competition_type="league",
    )

    with sqlite3.connect(database_path) as connection:
        competition_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM competitions
            WHERE sport_id = ?
              AND competition_key = ?
            """,
            (
                football_id,
                "premier_league",
            ),
        ).fetchone()

    assert competition_count == (1,)
    assert updated_competition.id == original_competition.id
    assert updated_competition.created_at == original_competition.created_at
    assert updated_competition.name == "Premier League"
    assert updated_competition.short_name == "PL"


def test_upsert_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    _, football_id, repository = create_repository(tmp_path)

    competition = repository.upsert(
        sport_id=football_id,
        competition_key="premier_league",
        name="Premier League",
        metadata={
            "region": "England",
            "calendar_category": "SMART | England",
        },
    )

    assert competition.metadata == {
        "region": "England",
        "calendar_category": "SMART | England",
    }


def test_upsert_rejects_unknown_sport(
    tmp_path: Path,
) -> None:
    _, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            sport_id=999999,
            competition_key="premier_league",
            name="Premier League",
        )


def test_upsert_rejects_unknown_competition_format(tmp_path: Path) -> None:
    _, football_id, repository = create_repository(tmp_path)

    with pytest.raises(ValueError, match="provider-specific"):
        repository.upsert(
            sport_id=football_id,
            competition_key="unknown_format",
            name="Unknown Format",
            competition_type="provider-specific",
        )


def test_loading_unknown_persisted_competition_format_fails_closed(
    tmp_path: Path,
) -> None:
    database_path, football_id, repository = create_repository(tmp_path)
    repository.upsert(
        sport_id=football_id,
        competition_key="unknown_format",
        name="Unknown Format",
        competition_type=CompetitionFormat.LEAGUE,
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE competitions
            SET competition_type = 'provider-specific'
            WHERE sport_id = ? AND competition_key = 'unknown_format'
            """,
            (football_id,),
        )

    with pytest.raises(ValueError, match="provider-specific"):
        repository.get_by_key(football_id, "unknown_format")
