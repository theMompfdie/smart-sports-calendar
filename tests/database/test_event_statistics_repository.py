import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_statistics_repository import (
    EventStatisticsRepository,
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
    EventStatisticsRepository,
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
        EventStatisticsRepository(database_path),
    )


def test_get_by_id_returns_none_for_unknown_statistic(
    tmp_path: Path,
) -> None:
    _, _, _, _, repository = create_repository(tmp_path)

    statistic = repository.get_by_id(999999)

    assert statistic is None


def test_create_event_statistic(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    statistic = repository.create(
        event_id=event_id,
        participant_id=arsenal_id,
        statistic_key="possession",
        statistic_name="Possession",
        value_number=58,
        unit="percent",
        period="full_time",
        recorded_at="2026-08-21T20:50:00+00:00",
    )

    assert statistic.id > 0
    assert statistic.event_id == event_id
    assert statistic.participant_id == arsenal_id
    assert statistic.source_id is None
    assert statistic.statistic_key == "possession"
    assert statistic.statistic_name == "Possession"
    assert statistic.value_number == 58
    assert statistic.value_text is None
    assert statistic.unit == "percent"
    assert statistic.period == "full_time"
    assert statistic.recorded_at == "2026-08-21T20:50:00+00:00"
    assert statistic.metadata is None
    assert statistic.created_at
    assert statistic.updated_at


def test_get_by_id_returns_existing_statistic(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    created_statistic = repository.create(
        event_id=event_id,
        participant_id=arsenal_id,
        statistic_key="shots_on_target",
        value_number=7,
    )

    loaded_statistic = repository.get_by_id(created_statistic.id)

    assert loaded_statistic == created_statistic


def test_get_for_event_returns_statistics_in_defined_order(
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
        participant_id=liverpool_id,
        statistic_key="possession",
        value_number=42,
    )
    repository.create(
        event_id=event_id,
        participant_id=arsenal_id,
        statistic_key="shots_on_target",
        value_number=7,
    )
    repository.create(
        event_id=event_id,
        participant_id=arsenal_id,
        statistic_key="possession",
        value_number=58,
    )
    repository.create(
        event_id=event_id,
        statistic_key="attendance",
        value_number=60260,
    )

    statistics = repository.get_for_event(event_id)

    assert len(statistics) == 4
    assert statistics[0].participant_id == arsenal_id
    assert statistics[0].statistic_key == "possession"
    assert statistics[1].participant_id == arsenal_id
    assert statistics[1].statistic_key == "shots_on_target"
    assert statistics[2].participant_id == liverpool_id
    assert statistics[2].statistic_key == "possession"
    assert statistics[3].participant_id is None
    assert statistics[3].statistic_key == "attendance"


def test_get_for_event_returns_empty_list_for_unknown_event(
    tmp_path: Path,
) -> None:
    _, _, _, _, repository = create_repository(tmp_path)

    statistics = repository.get_for_event(999999)

    assert statistics == []


def test_create_supports_event_level_statistic_without_participant(
    tmp_path: Path,
) -> None:
    _, event_id, _, _, repository = create_repository(tmp_path)

    statistic = repository.create(
        event_id=event_id,
        statistic_key="attendance",
        statistic_name="Attendance",
        value_number=60260,
        unit="spectators",
    )

    assert statistic.participant_id is None
    assert statistic.statistic_key == "attendance"
    assert statistic.value_number == 60260
    assert statistic.unit == "spectators"


def test_create_supports_text_value(
    tmp_path: Path,
) -> None:
    _, event_id, _, _, repository = create_repository(tmp_path)

    statistic = repository.create(
        event_id=event_id,
        statistic_key="weather",
        statistic_name="Weather",
        value_text="Partly cloudy",
    )

    assert statistic.value_number is None
    assert statistic.value_text == "Partly cloudy"


def test_create_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    statistic = repository.create(
        event_id=event_id,
        participant_id=arsenal_id,
        statistic_key="possession",
        value_number=58,
        metadata={
            "provider_key": "ball_possession",
            "verified": True,
        },
    )

    assert statistic.metadata == {
        "provider_key": "ball_possession",
        "verified": True,
    }


def test_create_allows_multiple_statistics_for_event(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    possession = repository.create(
        event_id=event_id,
        participant_id=arsenal_id,
        statistic_key="possession",
        value_number=58,
    )
    shots = repository.create(
        event_id=event_id,
        participant_id=arsenal_id,
        statistic_key="shots_on_target",
        value_number=7,
    )

    statistics = repository.get_for_event(event_id)

    assert len(statistics) == 2
    assert possession.id != shots.id


def test_delete_for_event_removes_all_event_statistics(
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
        participant_id=arsenal_id,
        statistic_key="possession",
        value_number=58,
    )
    repository.create(
        event_id=event_id,
        participant_id=liverpool_id,
        statistic_key="possession",
        value_number=42,
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
            participant_id=arsenal_id,
            statistic_key="possession",
            value_number=58,
        )


def test_create_rejects_unknown_participant(
    tmp_path: Path,
) -> None:
    _, event_id, _, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.create(
            event_id=event_id,
            participant_id=999999,
            statistic_key="possession",
            value_number=58,
        )


def test_create_rejects_unknown_source(
    tmp_path: Path,
) -> None:
    _, event_id, arsenal_id, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.create(
            event_id=event_id,
            participant_id=arsenal_id,
            source_id=999999,
            statistic_key="possession",
            value_number=58,
        )
