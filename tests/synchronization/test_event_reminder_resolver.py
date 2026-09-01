import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.reminder_rules_repository import (
    ReminderRulesRepository,
    ReminderRuleTarget,
)
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.synchronization_query_repository import (
    SynchronizationEvent,
    SynchronizationQueryRepository,
)
from app.domain.reminder_rules import (
    ReminderAction,
    ReminderRuleWrite,
    ReminderScope,
)
from app.domain.reminder_schedule import ReminderResolutionReason
from app.synchronization.event_reminder_resolver import EventReminderResolver
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder


@dataclass(frozen=True)
class ReminderHarness:
    database_path: Path
    rules: ReminderRulesRepository
    events: SportsEventsRepository
    event_participants: EventParticipantsRepository
    query: SynchronizationQueryRepository
    event_id: int
    football_id: int
    competition_id: int
    manchester_id: int
    liverpool_id: int

    def synchronization_event(self) -> SynchronizationEvent:
        result = self.query.get_by_event_id(self.event_id, "calendar-1")
        assert result is not None
        return result


@pytest.fixture
def reminder_harness(tmp_path: Path) -> ReminderHarness:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    events = SportsEventsRepository(database_path)
    event_participants = EventParticipantsRepository(database_path)

    football = sports.upsert("football", "Football", "⚽")
    competition = competitions.upsert(
        football.id,
        "premier_league",
        "Premier League",
    )
    manchester = participants.upsert(
        football.id,
        "manchester_united",
        "team",
        "Manchester United",
    )
    liverpool = participants.upsert(
        football.id,
        "liverpool",
        "team",
        "Liverpool",
    )
    event = events.upsert(
        sport_id=football.id,
        competition_id=competition.id,
        event_key="premier_league:manchester_united:liverpool",
        event_type="match",
        title="Manchester United vs Liverpool",
        start_time="2026-09-02T00:20:00+00:00",
    )
    event_participants.upsert(event.id, manchester.id, "home", 1)

    return ReminderHarness(
        database_path=database_path,
        rules=ReminderRulesRepository(database_path),
        events=events,
        event_participants=event_participants,
        query=SynchronizationQueryRepository(database_path),
        event_id=event.id,
        football_id=football.id,
        competition_id=competition.id,
        manchester_id=manchester.id,
        liverpool_id=liverpool.id,
    )


def set_participant_rule(
    harness: ReminderHarness,
    participant_key: str,
    preferred: int,
    *,
    quiet: bool = False,
) -> None:
    selector = harness.rules.resolve_target(
        ReminderRuleTarget(
            ReminderScope.PARTICIPANT,
            participant_key=participant_key,
        )
    )
    harness.rules.set(
        ReminderRuleWrite(
            selector,
            action=ReminderAction.ENABLE,
            preferred_lead_minutes=preferred,
            minimum_lead_minutes=60 if quiet else 0,
            maximum_lead_minutes=480 if quiet else None,
            quiet_start="22:00" if quiet else None,
            quiet_end="08:00" if quiet else None,
            timezone="Europe/Vienna" if quiet else None,
        )
    )


def test_same_resolver_observes_live_rule_changes_and_builds_graph_fields(
    reminder_harness: ReminderHarness,
) -> None:
    resolver = EventReminderResolver(reminder_harness.rules)
    builder = OutlookEventPayloadBuilder(reminder_resolver=resolver)
    synchronization_event = reminder_harness.synchronization_event()

    fallback = builder.build(synchronization_event).to_graph_dict()
    assert fallback["isReminderOn"] is True
    assert fallback["reminderMinutesBeforeStart"] == 15

    global_selector = reminder_harness.rules.resolve_target(
        ReminderRuleTarget(ReminderScope.GLOBAL)
    )
    reminder_harness.rules.set(
        ReminderRuleWrite(global_selector, action=ReminderAction.SUPPRESS)
    )
    suppressed = builder.build(synchronization_event).to_graph_dict()
    assert suppressed["isReminderOn"] is False
    assert suppressed["reminderMinutesBeforeStart"] == 0

    set_participant_rule(
        reminder_harness,
        "manchester_united",
        60,
        quiet=True,
    )
    shifted = resolver.resolve(synchronization_event)
    assert shifted.is_reminder_on is True
    assert shifted.minutes_before_start == 260
    assert shifted.reason is ReminderResolutionReason.QUIET_SHIFTED


def test_resolver_recomputes_after_canonical_kickoff_change(
    reminder_harness: ReminderHarness,
) -> None:
    set_participant_rule(
        reminder_harness,
        "manchester_united",
        60,
        quiet=True,
    )
    resolver = EventReminderResolver(reminder_harness.rules)
    before = resolver.resolve(reminder_harness.synchronization_event())

    reminder_harness.events.upsert(
        sport_id=reminder_harness.football_id,
        competition_id=reminder_harness.competition_id,
        event_key="premier_league:manchester_united:liverpool",
        event_type="match",
        title="Manchester United vs Liverpool",
        start_time="2026-09-02T17:00:00+00:00",
    )
    after = resolver.resolve(reminder_harness.synchronization_event())

    assert before.minutes_before_start == 260
    assert after.minutes_before_start == 60
    assert after.reason is ReminderResolutionReason.ENABLED


def test_future_equal_participant_conflict_disables_reminder_safely(
    reminder_harness: ReminderHarness,
    caplog: pytest.LogCaptureFixture,
) -> None:
    set_participant_rule(reminder_harness, "manchester_united", 60)
    set_participant_rule(reminder_harness, "liverpool", 120)
    reminder_harness.event_participants.upsert(
        reminder_harness.event_id,
        reminder_harness.liverpool_id,
        "away",
        2,
    )
    resolver = EventReminderResolver(reminder_harness.rules)

    with caplog.at_level(logging.WARNING):
        result = resolver.resolve(reminder_harness.synchronization_event())

    assert result.is_reminder_on is False
    assert result.minutes_before_start == 0
    assert result.reason is ReminderResolutionReason.CONFLICT
    assert result.conflict_fields == ("preferred_lead_minutes",)
    assert "event_id=" in caplog.text
    assert "Manchester United vs Liverpool" not in caplog.text


def test_invalid_persisted_policy_disables_reminder_without_leaking_value(
    reminder_harness: ReminderHarness,
    caplog: pytest.LogCaptureFixture,
) -> None:
    invalid_timezone = "Private/Invalid-Timezone"
    timestamp = "2026-09-01T10:00:00+00:00"
    with sqlite3.connect(reminder_harness.database_path) as connection:
        connection.execute(
            """
            INSERT INTO reminder_rules (
                scope, timezone, is_active, created_at, updated_at
            ) VALUES ('global', ?, 1, ?, ?)
            """,
            (invalid_timezone, timestamp, timestamp),
        )

    with caplog.at_level(logging.WARNING):
        result = EventReminderResolver(reminder_harness.rules).resolve(
            reminder_harness.synchronization_event()
        )

    assert result.is_reminder_on is False
    assert result.reason is ReminderResolutionReason.INVALID
    assert invalid_timezone not in caplog.text
