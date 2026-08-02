import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_participants_repository import (
    EventParticipantsRepository,
)
from app.database.participants_repository import ParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository


def create_repository(
    tmp_path: Path,
) -> tuple[
    Path,
    int,
    int,
    int,
    EventParticipantsRepository,
]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )

    competition = CompetitionsRepository(database_path).upsert(
        sport_id=sport.id,
        competition_key="premier_league",
        name="Premier League",
    )

    season = SeasonsRepository(database_path).upsert(
        competition_id=competition.id,
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-30",
        is_current=True,
    )

    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        competition_id=competition.id,
        season_id=season.id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-21T19:00:00+00:00",
    )

    participants_repository = ParticipantsRepository(database_path)

    arsenal = participants_repository.upsert(
        sport_id=sport.id,
        participant_key="arsenal",
        name="Arsenal",
        participant_type="team",
        country_code="GB",
    )

    liverpool = participants_repository.upsert(
        sport_id=sport.id,
        participant_key="liverpool",
        name="Liverpool",
        participant_type="team",
        country_code="GB",
    )

    return (
        database_path,
        event.id,
        arsenal.id,
        liverpool.id,
        EventParticipantsRepository(database_path),
    )


def test_get_returns_none_for_unknown_assignment(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    assignment = repository.get(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
    )

    assert assignment is None


def test_upsert_creates_event_participant(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    assignment = repository.upsert(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
        position_number=1,
        is_primary=True,
    )

    assert assignment.id > 0
    assert assignment.event_id == event_id
    assert assignment.participant_id == arsenal_id
    assert assignment.role == "home"
    assert assignment.position_number == 1
    assert assignment.is_primary is True
    assert assignment.metadata is None
    assert assignment.created_at
    assert assignment.updated_at


def test_get_returns_existing_assignment(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    created_assignment = repository.upsert(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
    )

    loaded_assignment = repository.get(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
    )

    assert loaded_assignment == created_assignment


def test_get_for_event_returns_participants_in_position_order(
    tmp_path: Path,
) -> None:
    (
        _,
        event_id,
        arsenal_id,
        liverpool_id,
        repository,
    ) = create_repository(tmp_path)

    repository.upsert(
        event_id=event_id,
        participant_id=liverpool_id,
        role="away",
        position_number=2,
    )
    repository.upsert(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
        position_number=1,
    )

    assignments = repository.get_for_event(event_id)

    assert len(assignments) == 2
    assert assignments[0].participant_id == arsenal_id
    assert assignments[0].role == "home"
    assert assignments[1].participant_id == liverpool_id
    assert assignments[1].role == "away"


def test_get_for_event_returns_empty_list_for_unknown_event(
    tmp_path: Path,
) -> None:
    _, _, _, _, repository = create_repository(tmp_path)

    assignments = repository.get_for_event(999999)

    assert assignments == []


def test_upsert_updates_existing_assignment_without_duplicate(
    tmp_path: Path,
) -> None:
    (
        database_path,
        event_id,
        arsenal_id,
        _,
        repository,
    ) = create_repository(tmp_path)

    original_assignment = repository.upsert(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
        position_number=1,
        is_primary=True,
    )

    updated_assignment = repository.upsert(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
        position_number=10,
        is_primary=False,
    )

    with sqlite3.connect(database_path) as connection:
        assignment_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM event_participants
            WHERE event_id = ?
              AND participant_id = ?
              AND role = ?
            """,
            (event_id, arsenal_id, "home"),
        ).fetchone()

    assert assignment_count == (1,)
    assert updated_assignment.id == original_assignment.id
    assert updated_assignment.created_at == original_assignment.created_at
    assert updated_assignment.position_number == 10
    assert updated_assignment.is_primary is False


def test_upsert_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    assignment = repository.upsert(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
        metadata={
            "provider_id": 42,
            "short_name": "ARS",
        },
    )

    assert assignment.metadata == {
        "provider_id": 42,
        "short_name": "ARS",
    }


def test_same_participant_can_have_different_roles(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    home_assignment = repository.upsert(
        event_id=event_id,
        participant_id=arsenal_id,
        role="home",
    )
    competitor_assignment = repository.upsert(
        event_id=event_id,
        participant_id=arsenal_id,
        role="competitor",
    )

    assignments = repository.get_for_event(event_id)

    assert len(assignments) == 2
    assert home_assignment.id != competitor_assignment.id
    assert {assignment.role for assignment in assignments} == {
        "home",
        "competitor",
    }


def test_upsert_rejects_unknown_event(
    tmp_path: Path,
) -> None:
    _, _, arsenal_id, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            event_id=999999,
            participant_id=arsenal_id,
            role="home",
        )


def test_upsert_rejects_unknown_participant(
    tmp_path: Path,
) -> None:
    _, event_id, _, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            event_id=event_id,
            participant_id=999999,
            role="away",
        )
