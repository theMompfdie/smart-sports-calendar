import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_repository import SportsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[Path, int, int, SeasonParticipantsRepository]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    football = SportsRepository(database_path).upsert("football", "Football")
    competition = CompetitionsRepository(database_path).upsert(
        football.id, "premier_league", "Premier League"
    )
    season = SeasonsRepository(database_path).upsert(
        competition.id, "2026_27", "2026/27"
    )
    participant = ParticipantsRepository(database_path).upsert(
        football.id, "arsenal", "team", "Arsenal"
    )
    return (
        database_path,
        season.id,
        participant.id,
        SeasonParticipantsRepository(database_path),
    )


def test_get_returns_none_for_unknown_membership(tmp_path: Path) -> None:
    _, season_id, participant_id, repository = create_repository(tmp_path)
    assert repository.get(season_id, participant_id + 1) is None


def test_upsert_creates_membership(tmp_path: Path) -> None:
    _, season_id, participant_id, repository = create_repository(tmp_path)
    membership = repository.upsert(season_id, participant_id)
    assert membership.id > 0
    assert membership.season_id == season_id
    assert membership.participant_id == participant_id


def test_upsert_does_not_create_duplicate(tmp_path: Path) -> None:
    database_path, season_id, participant_id, repository = create_repository(tmp_path)
    original = repository.upsert(season_id, participant_id)
    updated = repository.upsert(season_id, participant_id)
    with sqlite3.connect(database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM season_participants"
        ).fetchone()
    assert count == (1,)
    assert updated.id == original.id
    assert updated.created_at == original.created_at


def test_list_by_season_returns_memberships(tmp_path: Path) -> None:
    _, season_id, participant_id, repository = create_repository(tmp_path)
    repository.upsert(season_id, participant_id)
    assert [item.participant_id for item in repository.list_by_season(season_id)] == [
        participant_id
    ]


@pytest.mark.parametrize("season_id,participant_id", [(999999, 1), (1, 999999)])
def test_upsert_rejects_unknown_foreign_key(
    tmp_path: Path,
    season_id: int,
    participant_id: int,
) -> None:
    _, _, _, repository = create_repository(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(season_id, participant_id)
