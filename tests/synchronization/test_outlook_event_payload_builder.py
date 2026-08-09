from dataclasses import FrozenInstanceError, replace

import pytest
from app.database.competitions_repository import Competition
from app.database.event_results_repository import EventResult
from app.database.event_statistics_repository import EventStatistic
from app.database.participants_repository import Participant
from app.database.seasons_repository import Season
from app.database.sports_events_repository import SportsEvent
from app.database.sports_repository import Sport
from app.database.synchronization_query_repository import (
    SynchronizationEvent,
    SynchronizationParticipant,
)
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayloadBuilder,
    OutlookEventPresentation,
)

TIMESTAMP = "2026-08-01T10:00:00+00:00"


def make_sports_event(**overrides: object) -> SportsEvent:
    values = {
        "id": 10,
        "sport_id": 1,
        "competition_id": 2,
        "season_id": 3,
        "parent_event_id": 9,
        "event_key": "arsenal_liverpool",
        "event_type": "match",
        "title": "Arsenal vs Liverpool",
        "stage": "Regular season",
        "round_name": "Matchweek 1",
        "sequence_number": 1,
        "start_time": "2026-08-21T18:00:00+00:00",
        "end_time": "2026-08-21T20:00:00+00:00",
        "timezone": "Europe/London",
        "venue_name": "Emirates Stadium",
        "city": "London",
        "country_code": "GB",
        "status": "scheduled",
        "source_updated_at": None,
        "first_seen_at": TIMESTAMP,
        "last_seen_at": TIMESTAMP,
        "cancelled_at": None,
        "deleted_at": None,
        "metadata": None,
        "created_at": TIMESTAMP,
        "updated_at": TIMESTAMP,
    }
    values.update(overrides)
    return SportsEvent(**values)


def make_aggregate(
    *,
    event: SportsEvent | None = None,
    complete: bool = True,
    source_attribution: str | None = None,
) -> SynchronizationEvent:
    sport = Sport(1, "football", "Football", None, None, TIMESTAMP, TIMESTAMP)

    if not complete:
        return SynchronizationEvent(
            event=event
            or make_sports_event(
                competition_id=None,
                season_id=None,
                parent_event_id=None,
                stage=None,
                round_name=None,
                end_time=None,
                venue_name=None,
                city=None,
                country_code=None,
            ),
            sport=sport,
            competition=None,
            season=None,
            parent_event=None,
            participants=(),
            results=(),
            statistics=(),
            mapping=None,
            source_attribution=source_attribution,
        )

    competition = Competition(
        2,
        1,
        "premier_league",
        "Premier League",
        "PL",
        "GB",
        "league",
        None,
        TIMESTAMP,
        TIMESTAMP,
    )
    season = Season(
        3, 2, "2026_27", "2026/27", None, None, True, None, TIMESTAMP, TIMESTAMP
    )
    parent_event = make_sports_event(
        id=9,
        competition_id=2,
        season_id=3,
        parent_event_id=None,
        event_key="matchweek_1",
        event_type="round",
        title="Matchweek 1",
    )
    arsenal = Participant(
        4, 1, "arsenal", "team", "Arsenal", "ARS", "GB", None, TIMESTAMP, TIMESTAMP
    )
    liverpool = Participant(
        5,
        1,
        "liverpool",
        "team",
        "Liverpool",
        "LIV",
        "GB",
        None,
        TIMESTAMP,
        TIMESTAMP,
    )
    participants = (
        SynchronizationParticipant(liverpool, "away", 2, True, None),
        SynchronizationParticipant(arsenal, "home", 1, True, None),
    )
    results = (
        EventResult(2, 10, "score", 5, None, 1, 2, True, None, TIMESTAMP, TIMESTAMP),
        EventResult(1, 10, "score", 4, None, 2, 1, True, None, TIMESTAMP, TIMESTAMP),
    )
    statistics = (
        EventStatistic(
            2,
            10,
            5,
            None,
            "possession",
            "Possession",
            46,
            None,
            "percent",
            "full time",
            None,
            None,
            TIMESTAMP,
            TIMESTAMP,
        ),
        EventStatistic(
            1,
            10,
            4,
            None,
            "possession",
            "Possession",
            54,
            None,
            "percent",
            "full time",
            None,
            None,
            TIMESTAMP,
            TIMESTAMP,
        ),
    )
    return SynchronizationEvent(
        event=event or make_sports_event(),
        sport=sport,
        competition=competition,
        season=season,
        parent_event=parent_event,
        participants=participants,
        results=results,
        statistics=statistics,
        mapping=None,
        source_attribution=source_attribution,
    )


def test_build_maps_complete_event() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate())

    assert payload.subject == "Arsenal vs Liverpool"
    assert payload.start.date_time == "2026-08-21T19:00:00"
    assert payload.end is not None
    assert payload.end.date_time == "2026-08-21T21:00:00"
    assert payload.start.time_zone == "Europe/London"
    assert payload.location == "Emirates Stadium, London, GB"
    assert payload.categories == (
        "Football",
        "Premier League",
        "SMART Sports Calendar",
    )
    assert "- home: Arsenal" in payload.body
    assert payload.body.index("- home: Arsenal") < payload.body.index(
        "- away: Liverpool"
    )
    assert "- Arsenal: 2 (final)" in payload.body
    assert "- Arsenal – Possession: 54 percent (full time)" in payload.body


def test_build_adds_fallback_end_to_minimal_event() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate(complete=False))
    graph_payload = payload.to_graph_dict()

    assert payload.end is not None
    assert payload.end.date_time == "2026-08-21T21:00:00"
    assert payload.end.time_zone == "Europe/London"
    assert payload.location is None
    assert graph_payload["end"] == {
        "dateTime": "2026-08-21T21:00:00",
        "timeZone": "Europe/London",
    }
    assert "location" not in graph_payload
    assert "Competition:" not in payload.body
    assert "Participants:" not in payload.body


def test_build_appends_authoritative_source_attribution() -> None:
    attribution = "Football data provided by the Football-Data.org API"

    payload = OutlookEventPayloadBuilder().build(
        make_aggregate(source_attribution=attribution)
    )

    assert payload.body.endswith(f"\n\nSource: {attribution}")


def test_build_omits_missing_source_attribution() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate())

    assert "Source:" not in payload.body


def test_build_fallback_end_uses_absolute_duration_across_dst_change() -> None:
    event = make_sports_event(
        start_time="2026-10-25T00:30:00+00:00",
        end_time=None,
        timezone="Europe/London",
    )

    payload = OutlookEventPayloadBuilder().build(make_aggregate(event=event))

    assert payload.start.date_time == "2026-10-25T01:30:00"
    assert payload.end is not None
    assert payload.end.date_time == "2026-10-25T02:30:00"


def test_presentation_rejects_non_positive_default_duration() -> None:
    with pytest.raises(ValueError, match="Default duration minutes must be positive"):
        OutlookEventPresentation(default_duration_minutes=0)


def test_build_represents_cancelled_event_deterministically() -> None:
    event = make_sports_event(status="cancelled", cancelled_at=TIMESTAMP)
    payload = OutlookEventPayloadBuilder().build(make_aggregate(event=event))

    assert payload.subject == "[CANCELLED] Arsenal vs Liverpool"
    assert payload.show_as == "free"
    assert "Cancelled" in payload.categories
    assert payload.body.startswith("Status: Cancelled\n")


def test_build_is_deterministic_for_differently_ordered_collections() -> None:
    aggregate = make_aggregate()
    reordered = replace(
        aggregate,
        participants=tuple(reversed(aggregate.participants)),
        results=tuple(reversed(aggregate.results)),
        statistics=tuple(reversed(aggregate.statistics)),
    )
    builder = OutlookEventPayloadBuilder()

    assert builder.build(aggregate) == builder.build(reordered)
    assert (
        builder.build(aggregate).to_graph_dict()
        == builder.build(aggregate).to_graph_dict()
    )


def test_build_renders_event_level_result_and_statistic_without_participant() -> None:
    aggregate = replace(
        make_aggregate(),
        results=(
            EventResult(
                3,
                10,
                "aggregate_score",
                None,
                None,
                3,
                1,
                True,
                None,
                TIMESTAMP,
                TIMESTAMP,
            ),
        ),
        statistics=(
            EventStatistic(
                3,
                10,
                None,
                None,
                "attendance",
                "Attendance",
                60_000,
                None,
                None,
                None,
                None,
                None,
                TIMESTAMP,
                TIMESTAMP,
            ),
        ),
    )

    payload = OutlookEventPayloadBuilder().build(aggregate)

    assert "- aggregate_score: 3 (final)" in payload.body
    assert "- Attendance: 60000" in payload.body


def test_graph_serialization_uses_expected_microsoft_graph_shape() -> None:
    payload = OutlookEventPayloadBuilder(
        OutlookEventPresentation(
            categories=("Sports",),
            reminder_minutes_before_start=30,
            show_as="tentative",
        )
    ).build(make_aggregate())

    graph_payload = payload.to_graph_dict()

    assert graph_payload["body"]["contentType"] == "text"
    assert graph_payload["start"] == {
        "dateTime": "2026-08-21T19:00:00",
        "timeZone": "Europe/London",
    }
    assert graph_payload["location"] == {"displayName": "Emirates Stadium, London, GB"}
    assert graph_payload["isAllDay"] is False
    assert graph_payload["isReminderOn"] is True
    assert graph_payload["reminderMinutesBeforeStart"] == 30
    assert graph_payload["showAs"] == "tentative"


def test_payload_is_immutable() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate())

    with pytest.raises(FrozenInstanceError):
        payload.subject = "Changed"  # type: ignore[misc]
