import sqlite3
from pathlib import Path

import pytest
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_participants_repository import (
    EventParticipantsRepository,
)
from app.database.event_results_repository import EventResultsRepository
from app.database.event_statistics_repository import (
    EventStatisticsRepository,
)
from app.database.participants_repository import ParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)


def create_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    return database_path


def test_get_by_event_id_returns_none_for_unknown_event(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)
    repository = SynchronizationQueryRepository(database_path)

    synchronization_event = repository.get_by_event_id(
        event_id=999999,
        calendar_id="calendar-1",
    )

    assert synchronization_event is None


def test_get_by_event_id_returns_complete_event_aggregate(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )
    competition = CompetitionsRepository(database_path).upsert(
        sport_id=sport.id,
        competition_key="premier_league",
        name="Premier League",
        country_code="GB",
    )
    season = SeasonsRepository(database_path).upsert(
        competition_id=competition.id,
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-30",
        is_current=True,
    )

    events_repository = SportsEventsRepository(database_path)
    parent_event = events_repository.upsert(
        sport_id=sport.id,
        competition_id=competition.id,
        season_id=season.id,
        event_key="premier_league_2026_27_matchweek_1",
        event_type="round",
        title="Premier League Matchweek 1",
        start_time="2026-08-21T00:00:00+00:00",
    )
    event = events_repository.upsert(
        sport_id=sport.id,
        competition_id=competition.id,
        season_id=season.id,
        parent_event_id=parent_event.id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-21T19:00:00+00:00",
        end_time="2026-08-21T21:00:00+00:00",
        timezone="Europe/London",
        venue_name="Emirates Stadium",
        status="scheduled",
        metadata={"provider_status": "NS"},
    )

    participants_repository = ParticipantsRepository(database_path)
    arsenal = participants_repository.upsert(
        sport_id=sport.id,
        participant_key="arsenal",
        participant_type="team",
        name="Arsenal",
        short_name="ARS",
        country_code="GB",
    )
    liverpool = participants_repository.upsert(
        sport_id=sport.id,
        participant_key="liverpool",
        participant_type="team",
        name="Liverpool",
        short_name="LIV",
        country_code="GB",
    )

    event_participants_repository = EventParticipantsRepository(database_path)
    event_participants_repository.upsert(
        event_id=event.id,
        participant_id=arsenal.id,
        role="home",
        position_number=1,
        is_primary=True,
        metadata={"side": "home"},
    )
    event_participants_repository.upsert(
        event_id=event.id,
        participant_id=liverpool.id,
        role="away",
        position_number=2,
        is_primary=True,
    )

    EventResultsRepository(database_path).create(
        event_id=event.id,
        result_type="score",
        participant_id=arsenal.id,
        value_number=2,
        position_number=1,
        is_final=True,
        metadata={"period": "full_time"},
    )
    EventStatisticsRepository(database_path).create(
        event_id=event.id,
        participant_id=arsenal.id,
        statistic_key="possession",
        statistic_name="Possession",
        value_number=54.5,
        unit="percent",
        period="full_time",
        recorded_at="2026-08-21T21:00:00+00:00",
        metadata={"provider_key": "ball_possession"},
    )

    mapping = CalendarEventMappingsRepository(database_path).create_pending(
        event_id=event.id,
        calendar_id="calendar-1",
        content_hash="content-hash-1",
    )

    repository = SynchronizationQueryRepository(database_path)

    synchronization_event = repository.get_by_event_id(
        event_id=event.id,
        calendar_id="calendar-1",
    )

    assert synchronization_event is not None
    assert synchronization_event.event == event
    assert synchronization_event.sport == sport
    assert synchronization_event.competition == competition
    assert synchronization_event.season == season
    assert synchronization_event.parent_event == parent_event
    assert synchronization_event.mapping == mapping

    assert len(synchronization_event.participants) == 2

    home_participant = synchronization_event.participants[0]
    assert home_participant.participant == arsenal
    assert home_participant.role == "home"
    assert home_participant.position_number == 1
    assert home_participant.is_primary is True
    assert home_participant.metadata == {"side": "home"}

    away_participant = synchronization_event.participants[1]
    assert away_participant.participant == liverpool
    assert away_participant.role == "away"
    assert away_participant.position_number == 2

    assert len(synchronization_event.results) == 1
    assert synchronization_event.results[0].participant_id == arsenal.id
    assert synchronization_event.results[0].value_number == 2
    assert synchronization_event.results[0].is_final is True
    assert synchronization_event.results[0].metadata == {"period": "full_time"}

    assert len(synchronization_event.statistics) == 1
    assert synchronization_event.statistics[0].statistic_key == "possession"
    assert synchronization_event.statistics[0].value_number == 54.5
    assert synchronization_event.statistics[0].metadata == {
        "provider_key": "ball_possession"
    }


def test_get_by_event_id_supports_missing_optional_relationships(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        event_key="standalone_event",
        event_type="match",
        title="Standalone event",
        start_time="2026-08-21T19:00:00+00:00",
    )

    repository = SynchronizationQueryRepository(database_path)

    synchronization_event = repository.get_by_event_id(
        event_id=event.id,
        calendar_id="calendar-1",
    )

    assert synchronization_event is not None
    assert synchronization_event.event == event
    assert synchronization_event.sport == sport
    assert synchronization_event.competition is None
    assert synchronization_event.season is None
    assert synchronization_event.parent_event is None
    assert synchronization_event.participants == ()
    assert synchronization_event.results == ()
    assert synchronization_event.statistics == ()
    assert synchronization_event.mapping is None


def test_get_by_event_id_selects_mapping_for_requested_calendar(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        event_key="multi_calendar_event",
        event_type="match",
        title="Multi-calendar event",
        start_time="2026-08-21T19:00:00+00:00",
    )

    mappings_repository = CalendarEventMappingsRepository(database_path)
    mappings_repository.create_pending(
        event_id=event.id,
        calendar_id="calendar-1",
        content_hash="calendar-1-hash",
    )
    expected_mapping = mappings_repository.create_pending(
        event_id=event.id,
        calendar_id="calendar-2",
        content_hash="calendar-2-hash",
    )

    repository = SynchronizationQueryRepository(database_path)

    synchronization_event = repository.get_by_event_id(
        event_id=event.id,
        calendar_id="calendar-2",
    )

    assert synchronization_event is not None
    assert synchronization_event.mapping == expected_mapping
    assert synchronization_event.mapping.calendar_id == "calendar-2"
    assert synchronization_event.mapping.content_hash == "calendar-2-hash"


def test_get_by_event_id_rejects_missing_required_sport(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        event_key="broken_event",
        event_type="match",
        title="Broken event",
        start_time="2026-08-21T19:00:00+00:00",
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            DELETE FROM sports
            WHERE id = ?
            """,
            (sport.id,),
        )

    repository = SynchronizationQueryRepository(database_path)

    with pytest.raises(
        RuntimeError,
        match=f"Sport missing for sports event: event_id={event.id}",
    ):
        repository.get_by_event_id(
            event_id=event.id,
            calendar_id="calendar-1",
        )


def test_get_candidates_selects_expected_synchronization_statuses(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )
    events_repository = SportsEventsRepository(database_path)
    mappings_repository = CalendarEventMappingsRepository(database_path)

    statuses = (
        "pending",
        "failed",
        "synced",
        "delete_pending",
        "deleted",
    )
    events_by_status = {}

    for position, status in enumerate(statuses, start=1):
        event = events_repository.upsert(
            sport_id=sport.id,
            event_key=f"event_{status}",
            event_type="match",
            title=f"Event {status}",
            start_time=f"2026-08-{position:02d}T19:00:00+00:00",
        )
        events_by_status[status] = event

        mapping = mappings_repository.create_pending(
            event_id=event.id,
            calendar_id="calendar-1",
            content_hash=f"hash-{status}",
        )

        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                UPDATE calendar_event_mappings
                SET sync_status = ?
                WHERE id = ?
                """,
                (status, mapping.id),
            )

    unmapped_event = events_repository.upsert(
        sport_id=sport.id,
        event_key="unmapped_event",
        event_type="match",
        title="Unmapped event",
        start_time="2026-08-10T19:00:00+00:00",
    )
    deleted_unmapped_event = events_repository.upsert(
        sport_id=sport.id,
        event_key="deleted_unmapped_event",
        event_type="match",
        title="Deleted unmapped event",
        start_time="2026-08-11T19:00:00+00:00",
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE sports_events
            SET deleted_at = ?
            WHERE id = ?
            """,
            (
                "2026-08-01T12:00:00+00:00",
                deleted_unmapped_event.id,
            ),
        )

    repository = SynchronizationQueryRepository(database_path)

    candidates = repository.get_candidates(calendar_id="calendar-1")
    candidate_ids = {candidate.event.id for candidate in candidates}

    assert events_by_status["pending"].id in candidate_ids
    assert events_by_status["failed"].id in candidate_ids
    assert events_by_status["synced"].id in candidate_ids
    assert events_by_status["delete_pending"].id in candidate_ids
    assert unmapped_event.id in candidate_ids

    assert events_by_status["deleted"].id not in candidate_ids
    assert deleted_unmapped_event.id not in candidate_ids


def test_get_candidates_isolates_mappings_by_calendar(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        event_key="calendar_isolation_event",
        event_type="match",
        title="Calendar isolation event",
        start_time="2026-08-21T19:00:00+00:00",
    )

    mappings_repository = CalendarEventMappingsRepository(database_path)
    calendar_1_mapping = mappings_repository.create_pending(
        event_id=event.id,
        calendar_id="calendar-1",
        content_hash="calendar-1-hash",
    )
    mappings_repository.create_pending(
        event_id=event.id,
        calendar_id="calendar-2",
        content_hash="calendar-2-hash",
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE calendar_event_mappings
            SET sync_status = 'deleted'
            WHERE id = ?
            """,
            (calendar_1_mapping.id,),
        )

    repository = SynchronizationQueryRepository(database_path)

    calendar_1_candidates = repository.get_candidates(
        calendar_id="calendar-1",
    )
    calendar_2_candidates = repository.get_candidates(
        calendar_id="calendar-2",
    )

    assert calendar_1_candidates == []

    assert len(calendar_2_candidates) == 1
    assert calendar_2_candidates[0].event == event
    assert calendar_2_candidates[0].mapping is not None
    assert calendar_2_candidates[0].mapping.calendar_id == "calendar-2"


def test_get_candidates_returns_stable_chronological_order(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)

    sport = SportsRepository(database_path).upsert(
        sport_key="football",
        name="Football",
    )
    events_repository = SportsEventsRepository(database_path)

    later_event = events_repository.upsert(
        sport_id=sport.id,
        event_key="later_event",
        event_type="match",
        title="Later event",
        start_time="2026-08-22T19:00:00+00:00",
    )
    first_equal_event = events_repository.upsert(
        sport_id=sport.id,
        event_key="first_equal_event",
        event_type="match",
        title="First equal event",
        start_time="2026-08-21T19:00:00+00:00",
    )
    second_equal_event = events_repository.upsert(
        sport_id=sport.id,
        event_key="second_equal_event",
        event_type="match",
        title="Second equal event",
        start_time="2026-08-21T19:00:00+00:00",
    )

    repository = SynchronizationQueryRepository(database_path)

    candidates = repository.get_candidates(calendar_id="calendar-1")

    assert [candidate.event.id for candidate in candidates] == [
        first_equal_event.id,
        second_equal_event.id,
        later_event.id,
    ]
