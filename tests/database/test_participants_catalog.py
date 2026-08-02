import sqlite3
from pathlib import Path

import pytest

from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.participants_catalog import initialize_participants_catalog
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository


def create_repositories(tmp_path: Path):
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    return database_path, sports, competitions, seasons, participants, memberships


def initialize(tmp_path: Path):
    repositories = create_repositories(tmp_path)
    _, sports, competitions, seasons, participants, memberships = repositories
    result = initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    return repositories, result


def test_catalog_creates_and_assigns_twenty_teams(tmp_path: Path) -> None:
    _, result = initialize(tmp_path)
    assert len(result.participants) == 20
    assert len(result.season_participants) == 20
    assert {item.participant_key for item in result.participants} >= {
        "arsenal",
        "coventry_city",
        "hull_city",
        "ipswich_town",
    }
    assert all(item.participant_type == "team" for item in result.participants)
    assert all(item.country_code == "GB-ENG" for item in result.participants)


def test_catalog_excludes_relegated_teams(tmp_path: Path) -> None:
    _, result = initialize(tmp_path)
    keys = {item.participant_key for item in result.participants}
    assert keys.isdisjoint({"burnley", "west_ham_united", "wolverhampton_wanderers"})


def test_catalog_can_run_repeatedly(tmp_path: Path) -> None:
    repositories, first = initialize(tmp_path)
    (
        database_path,
        sports,
        competitions,
        seasons,
        participants,
        memberships,
    ) = repositories
    second = initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    with sqlite3.connect(database_path) as connection:
        participant_count = connection.execute(
            "SELECT COUNT(*) FROM participants"
        ).fetchone()
        membership_count = connection.execute(
            "SELECT COUNT(*) FROM season_participants"
        ).fetchone()
    assert participant_count == (20,)
    assert membership_count == (20,)
    assert [item.id for item in second.participants] == [
        item.id for item in first.participants
    ]


def test_catalog_restores_participant_master_data(tmp_path: Path) -> None:
    repositories = create_repositories(tmp_path)
    _, sports, competitions, seasons, participants, memberships = repositories
    football = sports.get_by_key("football")
    assert football is not None
    participants.upsert(football.id, "arsenal", "individual", "Wrong")
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    arsenal = participants.get_by_key(football.id, "arsenal")
    assert arsenal is not None
    assert arsenal.name == "Arsenal"
    assert arsenal.participant_type == "team"
    assert arsenal.country_code == "GB-ENG"


def test_catalog_requires_current_season(tmp_path: Path) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    with pytest.raises(RuntimeError, match="Required season not found.*2026_27"):
        initialize_participants_catalog(
            ParticipantsRepository(database_path),
            SeasonParticipantsRepository(database_path),
            sports,
            competitions,
            SeasonsRepository(database_path),
        )
