import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_results_repository import EventResultsRepository
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
    EventResultsRepository,
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
        EventResultsRepository(database_path),
    )


def test_get_by_id_returns_none_for_unknown_result(
    tmp_path: Path,
) -> None:
    _, _, _, _, repository = create_repository(tmp_path)

    result = repository.get_by_id(999999)

    assert result is None


def test_create_event_result(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    result = repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=arsenal_id,
        value_text="2",
        value_number=2,
        position_number=1,
        is_final=True,
    )

    assert result.id > 0
    assert result.event_id == event_id
    assert result.result_type == "score"
    assert result.participant_id == arsenal_id
    assert result.value_text == "2"
    assert result.value_number == 2
    assert result.position_number == 1
    assert result.is_final is True
    assert result.metadata is None
    assert result.created_at
    assert result.updated_at


def test_get_by_id_returns_existing_result(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    created_result = repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=arsenal_id,
        value_number=2,
    )

    loaded_result = repository.get_by_id(created_result.id)

    assert loaded_result == created_result


def test_get_for_event_returns_results_in_position_order(
    tmp_path: Path,
) -> None:
    (
        _,
        event_id,
        arsenal_id,
        liverpool_id,
        repository,
    ) = create_repository(tmp_path)

    repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=liverpool_id,
        value_number=1,
        position_number=2,
        is_final=True,
    )
    repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=arsenal_id,
        value_number=2,
        position_number=1,
        is_final=True,
    )

    results = repository.get_for_event(event_id)

    assert len(results) == 2
    assert results[0].participant_id == arsenal_id
    assert results[0].value_number == 2
    assert results[1].participant_id == liverpool_id
    assert results[1].value_number == 1


def test_get_for_event_returns_empty_list_for_unknown_event(
    tmp_path: Path,
) -> None:
    _, _, _, _, repository = create_repository(tmp_path)

    results = repository.get_for_event(999999)

    assert results == []


def test_create_supports_event_level_result_without_participant(
    tmp_path: Path,
) -> None:
    _, event_id, _, _, repository = create_repository(tmp_path)

    result = repository.create(
        event_id=event_id,
        result_type="full_time",
        value_text="2-1",
        is_final=True,
    )

    assert result.participant_id is None
    assert result.value_text == "2-1"
    assert result.value_number is None
    assert result.is_final is True


def test_create_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    result = repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=arsenal_id,
        value_number=2,
        metadata={
            "period": "full_time",
            "provider_status": "FT",
        },
    )

    assert result.metadata == {
        "period": "full_time",
        "provider_status": "FT",
    }


def test_create_allows_multiple_results_for_event(
    tmp_path: Path,
) -> None:
    (
        _,
        event_id,
        arsenal_id,
        liverpool_id,
        repository,
    ) = create_repository(tmp_path)

    arsenal_result = repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=arsenal_id,
        value_number=2,
    )
    liverpool_result = repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=liverpool_id,
        value_number=1,
    )

    results = repository.get_for_event(event_id)

    assert len(results) == 2
    assert arsenal_result.id != liverpool_result.id


def test_delete_for_event_removes_all_event_results(
    tmp_path: Path,
) -> None:
    (
        _,
        event_id,
        arsenal_id,
        liverpool_id,
        repository,
    ) = create_repository(tmp_path)

    repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=arsenal_id,
        value_number=2,
    )
    repository.create(
        event_id=event_id,
        result_type="score",
        participant_id=liverpool_id,
        value_number=1,
    )

    deleted_count = repository.delete_for_event(event_id)

    assert deleted_count == 2
    assert repository.get_for_event(event_id) == []


def test_delete_for_event_returns_zero_for_unknown_event(
    tmp_path: Path,
) -> None:
    _, _, _, _, repository = create_repository(tmp_path)

    deleted_count = repository.delete_for_event(999999)

    assert deleted_count == 0


def test_create_rejects_unknown_event(
    tmp_path: Path,
) -> None:
    _, _, arsenal_id, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.create(
            event_id=999999,
            result_type="score",
            participant_id=arsenal_id,
            value_number=2,
        )


def test_create_rejects_unknown_participant(
    tmp_path: Path,
) -> None:
    _, event_id, _, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.create(
            event_id=event_id,
            result_type="score",
            participant_id=999999,
            value_number=1,
        )
