import sqlite3
from pathlib import Path

import pytest

from app.database.database import Database
from app.database.participants_repository import ParticipantsRepository
from app.database.sports_repository import SportsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[Path, int, ParticipantsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    football = SportsRepository(database_path).upsert("football", "Football")
    return database_path, football.id, ParticipantsRepository(database_path)


def test_get_by_key_returns_none_for_unknown_participant(tmp_path: Path) -> None:
    _, sport_id, repository = create_repository(tmp_path)
    assert repository.get_by_key(sport_id, "unknown") is None


def test_upsert_creates_participant(tmp_path: Path) -> None:
    _, sport_id, repository = create_repository(tmp_path)
    participant = repository.upsert(
        sport_id=sport_id,
        participant_key="arsenal",
        participant_type="team",
        name="Arsenal",
        short_name="Arsenal",
        country_code="GB-ENG",
    )
    assert participant.id > 0
    assert participant.sport_id == sport_id
    assert participant.participant_key == "arsenal"
    assert participant.participant_type == "team"
    assert participant.name == "Arsenal"
    assert participant.short_name == "Arsenal"
    assert participant.country_code == "GB-ENG"
    assert participant.metadata is None


def test_upsert_updates_without_duplicate(tmp_path: Path) -> None:
    database_path, sport_id, repository = create_repository(tmp_path)
    original = repository.upsert(sport_id, "arsenal", "team", "Wrong")
    updated = repository.upsert(
        sport_id, "arsenal", "team", "Arsenal", "Arsenal", "GB-ENG"
    )
    with sqlite3.connect(database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM participants WHERE participant_key = ?",
            ("arsenal",),
        ).fetchone()
    assert count == (1,)
    assert updated.id == original.id
    assert updated.created_at == original.created_at
    assert updated.name == "Arsenal"


def test_upsert_serializes_and_loads_metadata(tmp_path: Path) -> None:
    _, sport_id, repository = create_repository(tmp_path)
    participant = repository.upsert(
        sport_id,
        "arsenal",
        "team",
        "Arsenal",
        metadata={"provider_name": "Arsenal FC"},
    )
    assert participant.metadata == {"provider_name": "Arsenal FC"}


def test_upsert_rejects_unknown_sport(tmp_path: Path) -> None:
    _, _, repository = create_repository(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(999999, "arsenal", "team", "Arsenal")
