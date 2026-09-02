from dataclasses import FrozenInstanceError, replace

import pytest
from app.database.competitions_catalog import (
    COMPETITION_CATALOG,
    CompetitionCatalogEntry,
)
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
from app.domain.competition_lifecycle import CompetitionFormat
from app.domain.operator_notice import OperatorNotice
from app.synchronization.outlook_event_payload_builder import (
    DEFAULT_OUTLOOK_GRAPH_TIME_ZONE,
    OutlookEventPayloadBuilder,
    OutlookEventPresentation,
)
from app.synchronization.outlook_html_event_body_renderer import (
    OutlookHtmlEventBodyRenderer,
    OutlookInlineImage,
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
    sport_key: str = "football",
    sport_name: str = "Football",
    sport_icon: str | None = "⚽",
    source_attribution: str | None = None,
    operator_notice: OperatorNotice | None = None,
) -> SynchronizationEvent:
    sport = Sport(1, sport_key, sport_name, sport_icon, None, TIMESTAMP, TIMESTAMP)

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
            operator_notice=operator_notice,
        )

    competition = Competition(
        2,
        1,
        "premier_league",
        "Premier League",
        "PL",
        "GB",
        CompetitionFormat.LEAGUE,
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
        operator_notice=operator_notice,
    )


def test_build_maps_complete_event() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate())

    assert payload.subject == "⚽ Arsenal vs Liverpool"
    assert payload.start.date_time == "2026-08-21T20:00:00"
    assert payload.end is not None
    assert payload.end.date_time == "2026-08-21T22:00:00"
    assert payload.start.time_zone == DEFAULT_OUTLOOK_GRAPH_TIME_ZONE
    assert payload.location == "Emirates Stadium, London, GB"
    assert payload.categories == ("Premier League",)
    assert ">home:</td>" in payload.body
    assert payload.body.index(">home:</td>") < payload.body.index(">away:</td>")
    assert ">Arsenal:</td>" in payload.body
    assert ">2 (final)</td>" in payload.body
    assert ">Arsenal – Possession:</td>" in payload.body
    assert ">54 percent (full time)</td>" in payload.body
    assert "2026-08-21T20:00+02:00 (Europe/Vienna)" in payload.body


def test_build_adds_fallback_end_to_minimal_event() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate(complete=False))
    graph_payload = payload.to_graph_dict()

    assert payload.end is not None
    assert payload.end.date_time == "2026-08-21T22:00:00"
    assert payload.end.time_zone == DEFAULT_OUTLOOK_GRAPH_TIME_ZONE
    assert payload.location is None
    assert graph_payload["end"] == {
        "dateTime": "2026-08-21T22:00:00",
        "timeZone": DEFAULT_OUTLOOK_GRAPH_TIME_ZONE,
    }
    assert "location" not in graph_payload
    assert ">Competition:</td>" not in payload.body
    assert ">Participants</h3>" not in payload.body
    assert ">Results</h3>" not in payload.body
    assert ">Statistics</h3>" not in payload.body
    assert payload.categories == ("SMART Sports Calendar",)


def test_body_renderer_rejects_unknown_display_time_zone() -> None:
    with pytest.raises(ValueError, match="Unknown body display time zone"):
        OutlookHtmlEventBodyRenderer("Invalid/Zone")


@pytest.mark.parametrize(
    "catalog_entry",
    COMPETITION_CATALOG,
    ids=lambda entry: entry.competition_key,
)
def test_build_uses_exact_competition_name_as_sole_category(
    catalog_entry: CompetitionCatalogEntry,
) -> None:
    aggregate = make_aggregate(
        sport_key=catalog_entry.sport_key,
        sport_name=(
            "American Football"
            if catalog_entry.sport_key == "american_football"
            else "Football"
        ),
        sport_icon=("🏈" if catalog_entry.sport_key == "american_football" else "⚽"),
    )
    assert aggregate.competition is not None
    competition = replace(
        aggregate.competition,
        competition_key=catalog_entry.competition_key,
        name=catalog_entry.name,
    )

    payload = OutlookEventPayloadBuilder().build(
        replace(aggregate, competition=competition)
    )

    assert payload.categories == (catalog_entry.name,)


def test_build_omits_subject_prefix_when_sport_icon_is_missing() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate(sport_icon=None))

    assert payload.subject == "Arsenal vs Liverpool"
    assert payload.categories == ("Premier League",)


def test_build_uses_three_hour_fallback_for_american_football() -> None:
    event = make_sports_event(
        start_time="2026-09-10T00:20:00+00:00",
        end_time=None,
        timezone="UTC",
    )

    payload = OutlookEventPayloadBuilder().build(
        make_aggregate(
            event=event,
            sport_key="american_football",
            sport_name="American Football",
            sport_icon="🏈",
        )
    )

    assert payload.subject == "🏈 Arsenal vs Liverpool"
    assert payload.end is not None
    assert payload.end.date_time == "2026-09-10T05:20:00"
    assert payload.end.time_zone == DEFAULT_OUTLOOK_GRAPH_TIME_ZONE


def test_build_prefers_explicit_end_for_american_football() -> None:
    event = make_sports_event(
        start_time="2026-09-10T00:20:00+00:00",
        end_time="2026-09-10T02:50:00+00:00",
        timezone="UTC",
    )

    payload = OutlookEventPayloadBuilder().build(
        make_aggregate(
            event=event,
            sport_key="american_football",
            sport_name="American Football",
            sport_icon="🏈",
        )
    )

    assert payload.end is not None
    assert payload.end.date_time == "2026-09-10T04:50:00"
    assert payload.end.time_zone == DEFAULT_OUTLOOK_GRAPH_TIME_ZONE


def test_build_appends_authoritative_source_attribution() -> None:
    attribution = "Football data provided by the Football-Data.org API"

    payload = OutlookEventPayloadBuilder().build(
        make_aggregate(source_attribution=attribution)
    )

    assert f"<strong>Source:</strong> {attribution}</p>" in payload.body
    assert payload.body.endswith("</div>")


def test_build_omits_missing_source_attribution() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate())

    assert "Source:" not in payload.body


def test_build_renders_operator_notice_before_source_attribution() -> None:
    notice = OperatorNotice("Subject to schedule changes.")
    payload = OutlookEventPayloadBuilder().build(
        make_aggregate(
            operator_notice=notice,
            source_attribution="Approved provider",
        )
    )

    assert "<strong>Notice:</strong> Subject to schedule changes.</p>" in payload.body
    assert payload.body.index("Notice:") < payload.body.index("Source:")


def test_build_omits_missing_operator_notice() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate())

    assert "Notice:" not in payload.body


def test_build_does_not_render_raw_provider_metadata_as_operator_notice() -> None:
    event = make_sports_event(
        metadata={"schedule_notice": "Unvalidated provider metadata"}
    )

    payload = OutlookEventPayloadBuilder().build(make_aggregate(event=event))

    assert "Unvalidated provider metadata" not in payload.body
    assert "Notice:" not in payload.body


def test_build_escapes_all_dynamic_html_values() -> None:
    aggregate = make_aggregate(
        event=make_sports_event(
            title='<script>alert("title")</script>',
            venue_name="<b>Unsafe stadium</b>",
        ),
        operator_notice=OperatorNotice("<em>Reviewed notice</em>"),
        source_attribution='<a href="https://invalid.example">Source</a>',
    )
    assert aggregate.competition is not None
    malicious_participant = replace(
        aggregate.participants[0],
        role="<away>",
        participant=replace(
            aggregate.participants[0].participant,
            name='<img src="invalid">',
        ),
    )
    malicious_result = replace(
        aggregate.results[0],
        value_number=None,
        value_text="<strong>one</strong>",
    )
    malicious_statistic = replace(
        aggregate.statistics[0],
        statistic_name='<img src="statistic">',
        value_number=None,
        value_text="<a>forty-six</a>",
    )
    aggregate = replace(
        aggregate,
        competition=replace(aggregate.competition, name="League & <Cup>"),
        participants=(malicious_participant, aggregate.participants[1]),
        results=(malicious_result, aggregate.results[1]),
        statistics=(malicious_statistic, aggregate.statistics[1]),
    )

    body = OutlookEventPayloadBuilder().build(aggregate).body

    assert "&lt;script&gt;alert(&quot;" in body
    assert "League &amp; &lt;Cup&gt;" in body
    assert "&lt;img src=&quot;" in body
    assert "&lt;strong&gt;one&lt;/strong&gt;" in body
    assert "&lt;a&gt;forty-six&lt;/a&gt;" in body
    assert "&lt;em&gt;Reviewed notice&lt;/em&gt;" in body
    assert "&lt;a href=&quot;" in body
    assert "<script" not in body
    assert "<img" not in body
    assert "<a href" not in body
    assert "<em>Reviewed" not in body


def test_build_fallback_end_uses_absolute_duration_across_dst_change() -> None:
    event = make_sports_event(
        start_time="2026-10-25T00:30:00+00:00",
        end_time=None,
        timezone="Europe/London",
    )

    payload = OutlookEventPayloadBuilder().build(make_aggregate(event=event))

    assert payload.start.date_time == "2026-10-25T02:30:00"
    assert payload.end is not None
    assert payload.end.date_time == "2026-10-25T03:30:00"


def test_american_football_fallback_uses_absolute_duration_across_dst() -> None:
    event = make_sports_event(
        start_time="2026-10-25T00:30:00+00:00",
        end_time=None,
        timezone="Europe/London",
    )

    payload = OutlookEventPayloadBuilder().build(
        make_aggregate(
            event=event,
            sport_key="american_football",
            sport_name="American Football",
            sport_icon="🏈",
        )
    )

    assert payload.start.date_time == "2026-10-25T02:30:00"
    assert payload.end is not None
    assert payload.end.date_time == "2026-10-25T04:30:00"


def test_build_converts_utc_source_to_vienna_in_summer_and_winter() -> None:
    builder = OutlookEventPayloadBuilder()

    summer = builder.build(
        make_aggregate(
            event=make_sports_event(
                start_time="2026-09-08T16:45:00+00:00",
                end_time="2026-09-08T18:45:00+00:00",
                timezone="UTC",
            )
        )
    )
    winter = builder.build(
        make_aggregate(
            event=make_sports_event(
                start_time="2026-11-25T17:45:00+00:00",
                end_time="2026-11-25T19:45:00+00:00",
                timezone="UTC",
            )
        )
    )

    assert summer.start.to_graph_dict() == {
        "dateTime": "2026-09-08T18:45:00",
        "timeZone": DEFAULT_OUTLOOK_GRAPH_TIME_ZONE,
    }
    assert summer.end is not None
    assert summer.end.date_time == "2026-09-08T20:45:00"
    assert winter.start.to_graph_dict() == {
        "dateTime": "2026-11-25T18:45:00",
        "timeZone": DEFAULT_OUTLOOK_GRAPH_TIME_ZONE,
    }
    assert winter.end is not None
    assert winter.end.date_time == "2026-11-25T20:45:00"


def test_presentation_rejects_non_positive_default_duration() -> None:
    with pytest.raises(ValueError, match="Default duration minutes must be positive"):
        OutlookEventPresentation(default_duration_minutes=0)


@pytest.mark.parametrize("time_zone", ["", " Europe/Vienna", "Invalid/Zone"])
def test_presentation_rejects_invalid_time_zone(time_zone: str) -> None:
    with pytest.raises(ValueError, match="Outlook presentation time zone"):
        OutlookEventPresentation(time_zone=time_zone)


@pytest.mark.parametrize("graph_time_zone", ["", " UTC", "UTC "])
def test_presentation_rejects_invalid_graph_time_zone(graph_time_zone: str) -> None:
    with pytest.raises(ValueError, match="Outlook Graph time zone"):
        OutlookEventPresentation(graph_time_zone=graph_time_zone)


@pytest.mark.parametrize("fallback_category", ["", " Calendar", "Calendar "])
def test_presentation_rejects_invalid_fallback_category(
    fallback_category: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="Fallback category must be normalized and non-empty",
    ):
        OutlookEventPresentation(fallback_category=fallback_category)


def test_presentation_rejects_non_positive_sport_duration() -> None:
    with pytest.raises(ValueError, match="Fallback duration minutes must be positive"):
        OutlookEventPresentation(
            fallback_duration_minutes_by_sport=(("american_football", 0),)
        )


def test_build_represents_cancelled_event_deterministically() -> None:
    event = make_sports_event(status="cancelled", cancelled_at=TIMESTAMP)
    payload = OutlookEventPayloadBuilder().build(make_aggregate(event=event))

    assert payload.subject == "[CANCELLED] ⚽ Arsenal vs Liverpool"
    assert payload.show_as == "free"
    assert payload.categories == ("Premier League",)
    assert ">Status:</td>" in payload.body
    assert ">Cancelled</td>" in payload.body


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

    assert ">aggregate_score:</td>" in payload.body
    assert ">3 (final)</td>" in payload.body
    assert ">Attendance:</td>" in payload.body
    assert ">60000</td>" in payload.body


def test_graph_serialization_uses_expected_microsoft_graph_shape() -> None:
    payload = OutlookEventPayloadBuilder(
        OutlookEventPresentation(
            reminder_minutes_before_start=30,
            show_as="tentative",
        )
    ).build(make_aggregate())

    graph_payload = payload.to_graph_dict()

    assert graph_payload["body"]["contentType"] == "html"
    assert graph_payload["start"] == {
        "dateTime": "2026-08-21T20:00:00",
        "timeZone": DEFAULT_OUTLOOK_GRAPH_TIME_ZONE,
    }
    assert graph_payload["location"] == {"displayName": "Emirates Stadium, London, GB"}
    assert graph_payload["isAllDay"] is False
    assert graph_payload["isReminderOn"] is True
    assert graph_payload["reminderMinutesBeforeStart"] == 30
    assert graph_payload["showAs"] == "tentative"


def test_build_renders_bounded_cid_images_without_changing_text_fallback() -> None:
    aggregate = make_aggregate()
    builder = OutlookEventPayloadBuilder()
    text_only = builder.build(aggregate)
    with_images = builder.build(
        aggregate,
        inline_images=(
            OutlookInlineImage("competition", "competition@example", "League"),
            OutlookInlineImage("home", "home@example", "Arsenal & Co"),
            OutlookInlineImage("away", "away@example", "Liverpool"),
            OutlookInlineImage("final", "final@example", "Final"),
        ),
    )

    assert "cid:" not in text_only.body
    assert with_images.body.count("<img ") == 4
    assert 'src="cid:competition@example"' in with_images.body
    assert 'src="cid:home@example"' in with_images.body
    assert 'alt="Arsenal &amp; Co"' in with_images.body
    assert 'alt="League" width="44" height="44"' in with_images.body
    assert "height:44px;max-height:44px" in with_images.body
    assert with_images.body.count('width="30" height="30"') == 3
    assert with_images.body.count("height:30px;max-height:30px") == 3
    assert with_images.body.count('src="cid:home@example"') == 1
    assert with_images.body.count('src="cid:away@example"') == 1


def test_build_centers_participant_logo_and_uses_it_as_header_fallback() -> None:
    payload = OutlookEventPayloadBuilder().build(
        make_aggregate(),
        inline_images=(
            OutlookInlineImage("home", "home@example", "Arsenal & Co"),
            OutlookInlineImage("away", "away@example", "Liverpool"),
        ),
    )

    assert payload.body.count('src="cid:home@example"') == 2
    assert payload.body.count('src="cid:away@example"') == 2
    assert payload.body.index('alt="Arsenal &amp; Co" width="44" height="44"') < (
        payload.body.index('alt="Liverpool" width="44" height="44"')
    )
    assert 'alt="Arsenal &amp; Co" width="30" height="30"' in payload.body
    assert 'alt="Liverpool" width="30" height="30"' in payload.body
    assert (
        '<table role="presentation" style="border-collapse:collapse;margin:0;">'
        in payload.body
    )
    assert "line-height:0;padding:0 8px 0 0;vertical-align:middle;" in payload.body
    assert 'padding:0;vertical-align:middle;">Arsenal</td>' in payload.body


def test_payload_is_immutable() -> None:
    payload = OutlookEventPayloadBuilder().build(make_aggregate())

    with pytest.raises(FrozenInstanceError):
        payload.subject = "Changed"  # type: ignore[misc]
