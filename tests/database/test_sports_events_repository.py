import sqlite3
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
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
    SportsEventsRepository,
]:
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

    seasons_repository = SeasonsRepository(database_path)
    season = seasons_repository.upsert(
        competition_id=premier_league.id,
        season_key="2026_27",
        name="2026/27",
        start_date="2026-08-21",
        end_date="2027-05-30",
        is_current=True,
    )

    return (
        database_path,
        football.id,
        premier_league.id,
        season.id,
        SportsEventsRepository(database_path),
    )


def test_get_by_key_returns_none_for_unknown_event(
    tmp_path: Path,
) -> None:
    _, _, _, _, repository = create_repository(tmp_path)

    event = repository.get_by_key("unknown")

    assert event is None


def test_upsert_creates_sports_event(
    tmp_path: Path,
) -> None:
    (
        _,
        sport_id,
        competition_id,
        season_id,
        repository,
    ) = create_repository(tmp_path)

    event = repository.upsert(
        sport_id=sport_id,
        competition_id=competition_id,
        season_id=season_id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        stage="regular_season",
        round_name="Matchweek 1",
        sequence_number=1,
        start_time="2026-08-21T19:00:00+00:00",
        end_time="2026-08-21T21:00:00+00:00",
        timezone="Europe/London",
        venue_name="Emirates Stadium",
        city="London",
        country_code="GB",
        status="scheduled",
    )

    assert event.id > 0
    assert event.sport_id == sport_id
    assert event.competition_id == competition_id
    assert event.season_id == season_id
    assert event.parent_event_id is None
    assert event.event_key == ("premier_league_2026_27_arsenal_liverpool")
    assert event.event_type == "match"
    assert event.title == "Arsenal vs Liverpool"
    assert event.stage == "regular_season"
    assert event.round_name == "Matchweek 1"
    assert event.sequence_number == 1
    assert event.start_time == "2026-08-21T19:00:00+00:00"
    assert event.end_time == "2026-08-21T21:00:00+00:00"
    assert event.timezone == "Europe/London"
    assert event.venue_name == "Emirates Stadium"
    assert event.city == "London"
    assert event.country_code == "GB"
    assert event.status == "scheduled"
    assert event.source_updated_at is None
    assert event.first_seen_at
    assert event.last_seen_at
    assert event.cancelled_at is None
    assert event.deleted_at is None
    assert event.metadata is None
    assert event.created_at
    assert event.updated_at


def test_get_by_key_returns_existing_event(
    tmp_path: Path,
) -> None:
    (
        _,
        sport_id,
        competition_id,
        season_id,
        repository,
    ) = create_repository(tmp_path)

    created_event = repository.upsert(
        sport_id=sport_id,
        competition_id=competition_id,
        season_id=season_id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-21T19:00:00+00:00",
    )

    loaded_event = repository.get_by_key("premier_league_2026_27_arsenal_liverpool")

    assert loaded_event == created_event


def test_upsert_updates_existing_event_without_duplicate(
    tmp_path: Path,
) -> None:
    (
        database_path,
        sport_id,
        competition_id,
        season_id,
        repository,
    ) = create_repository(tmp_path)

    original_event = repository.upsert(
        sport_id=sport_id,
        competition_id=competition_id,
        season_id=season_id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-21T19:00:00+00:00",
        status="scheduled",
    )

    updated_event = repository.upsert(
        sport_id=sport_id,
        competition_id=competition_id,
        season_id=season_id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-22T16:30:00+00:00",
        timezone="Europe/London",
        venue_name="Emirates Stadium",
        status="scheduled",
        source_updated_at="2026-08-10T12:00:00+00:00",
    )

    with sqlite3.connect(database_path) as connection:
        event_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM sports_events
            WHERE event_key = ?
            """,
            ("premier_league_2026_27_arsenal_liverpool",),
        ).fetchone()

    assert event_count == (1,)
    assert updated_event.id == original_event.id
    assert updated_event.created_at == original_event.created_at
    assert updated_event.first_seen_at == original_event.first_seen_at
    assert updated_event.start_time == "2026-08-22T16:30:00+00:00"
    assert updated_event.timezone == "Europe/London"
    assert updated_event.venue_name == "Emirates Stadium"
    assert updated_event.status == "scheduled"
    assert updated_event.source_updated_at == "2026-08-10T12:00:00+00:00"


def test_upsert_serializes_and_loads_metadata(
    tmp_path: Path,
) -> None:
    (
        _,
        sport_id,
        competition_id,
        season_id,
        repository,
    ) = create_repository(tmp_path)

    event = repository.upsert(
        sport_id=sport_id,
        competition_id=competition_id,
        season_id=season_id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-21T19:00:00+00:00",
        metadata={
            "provider_id": 123456,
            "provider_status": "NS",
        },
    )

    assert event.metadata == {
        "provider_id": 123456,
        "provider_status": "NS",
    }


def test_upsert_supports_parent_event(
    tmp_path: Path,
) -> None:
    (
        _,
        sport_id,
        competition_id,
        season_id,
        repository,
    ) = create_repository(tmp_path)

    parent_event = repository.upsert(
        sport_id=sport_id,
        competition_id=competition_id,
        season_id=season_id,
        event_key="premier_league_2026_27_matchweek_1",
        event_type="round",
        title="Premier League Matchweek 1",
        start_time="2026-08-21T00:00:00+00:00",
    )

    match = repository.upsert(
        sport_id=sport_id,
        competition_id=competition_id,
        season_id=season_id,
        parent_event_id=parent_event.id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-21T19:00:00+00:00",
    )

    assert match.parent_event_id == parent_event.id


def test_upsert_can_mark_event_as_cancelled(
    tmp_path: Path,
) -> None:
    (
        _,
        sport_id,
        competition_id,
        season_id,
        repository,
    ) = create_repository(tmp_path)

    event = repository.upsert(
        sport_id=sport_id,
        competition_id=competition_id,
        season_id=season_id,
        event_key="premier_league_2026_27_arsenal_liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        start_time="2026-08-21T19:00:00+00:00",
        status="cancelled",
        cancelled_at="2026-08-20T10:00:00+00:00",
    )

    assert event.status == "cancelled"
    assert event.cancelled_at == "2026-08-20T10:00:00+00:00"


def test_upsert_rejects_unknown_sport(
    tmp_path: Path,
) -> None:
    _, _, _, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            sport_id=999999,
            event_key="unknown_sport_event",
            event_type="match",
            title="Unknown event",
            start_time="2026-08-21T19:00:00+00:00",
        )


def test_upsert_rejects_unknown_competition(
    tmp_path: Path,
) -> None:
    _, sport_id, _, _, repository = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            sport_id=sport_id,
            competition_id=999999,
            event_key="unknown_competition_event",
            event_type="match",
            title="Unknown competition event",
            start_time="2026-08-21T19:00:00+00:00",
        )


def test_upsert_rejects_unknown_season(
    tmp_path: Path,
) -> None:
    (
        _,
        sport_id,
        competition_id,
        _,
        repository,
    ) = create_repository(tmp_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            sport_id=sport_id,
            competition_id=competition_id,
            season_id=999999,
            event_key="unknown_season_event",
            event_type="match",
            title="Unknown season event",
            start_time="2026-08-21T19:00:00+00:00",
        )
