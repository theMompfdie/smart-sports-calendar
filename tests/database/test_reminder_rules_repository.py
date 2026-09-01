import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.reminder_rules_repository import (
    ReminderRuleRepositoryError,
    ReminderRulesRepository,
    ReminderRuleTarget,
)
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.domain.reminder_rules import (
    ReminderAction,
    ReminderRuleWrite,
    ReminderScope,
)

NOW = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


@pytest.fixture
def reminder_scope(tmp_path: Path) -> dict[str, object]:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    events = SportsEventsRepository(database_path)
    event_participants = EventParticipantsRepository(database_path)

    football = sports.upsert("football", "Football", "⚽")
    american_football = sports.upsert("american_football", "American Football", "🏈")
    premier_league = competitions.upsert(
        football.id,
        "premier_league",
        "Premier League",
    )
    nfl = competitions.upsert(
        american_football.id,
        "nfl",
        "National Football League",
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
    new_england = participants.upsert(
        american_football.id,
        "new_england_patriots",
        "team",
        "New England Patriots",
    )
    event = events.upsert(
        sport_id=football.id,
        competition_id=premier_league.id,
        event_key="premier_league:manchester_united:liverpool",
        event_type="match",
        title="Manchester United vs Liverpool",
        start_time="2026-09-12T14:00:00+00:00",
    )
    event_participants.upsert(event.id, manchester.id, "home", 1)
    event_participants.upsert(event.id, liverpool.id, "away", 2)

    return {
        "database_path": database_path,
        "premier_league": premier_league,
        "nfl": nfl,
        "manchester": manchester,
        "liverpool": liverpool,
        "new_england": new_england,
        "event": event,
    }


def repository(scope: dict[str, object]) -> ReminderRulesRepository:
    return ReminderRulesRepository(
        scope["database_path"],  # type: ignore[arg-type]
        clock=lambda: NOW,
    )


def target(
    scope: ReminderScope,
    *,
    competition: str | None = None,
    participant: str | None = None,
    event: str | None = None,
) -> ReminderRuleTarget:
    return ReminderRuleTarget(
        scope,
        competition_key=competition,
        participant_key=participant,
        event_key=event,
    )


def test_resolves_required_operator_team_keys(
    reminder_scope: dict[str, object],
) -> None:
    rules = repository(reminder_scope)

    manchester = rules.resolve_target(
        target(ReminderScope.PARTICIPANT, participant="manchester_united")
    )
    new_england = rules.resolve_target(
        target(ReminderScope.PARTICIPANT, participant="new_england_patriots")
    )

    assert manchester.participant_id == reminder_scope["manchester"].id  # type: ignore[union-attr]
    assert new_england.participant_id == reminder_scope["new_england"].id  # type: ignore[union-attr]


def test_set_updates_one_current_natural_scope(
    reminder_scope: dict[str, object],
) -> None:
    rules = repository(reminder_scope)
    selector = rules.resolve_target(
        target(ReminderScope.PARTICIPANT, participant="manchester_united")
    )
    first = rules.set(
        ReminderRuleWrite(
            selector,
            action=ReminderAction.ENABLE,
            preferred_lead_minutes=60,
        )
    )
    second = rules.set(
        ReminderRuleWrite(
            selector,
            action=ReminderAction.ENABLE,
            preferred_lead_minutes=90,
        )
    )

    assert second.id == first.id
    assert second.preferred_lead_minutes == 90
    assert len(rules.list()) == 1


def test_rule_survives_repository_restart_and_concurrent_read(
    reminder_scope: dict[str, object],
) -> None:
    first_repository = repository(reminder_scope)
    selector = first_repository.resolve_target(target(ReminderScope.GLOBAL))
    first_repository.set(ReminderRuleWrite(selector, action=ReminderAction.SUPPRESS))

    second_repository = repository(reminder_scope)
    loaded = second_repository.get_current(selector)

    assert loaded is not None
    assert loaded.action is ReminderAction.SUPPRESS
    assert first_repository.list() == second_repository.list()


def test_disable_and_delete_preserve_auditable_state(
    reminder_scope: dict[str, object],
) -> None:
    rules = repository(reminder_scope)
    selector = rules.resolve_target(target(ReminderScope.GLOBAL))
    created = rules.set(ReminderRuleWrite(selector, action=ReminderAction.SUPPRESS))

    disabled = rules.disable(selector)
    deleted = rules.delete(selector)

    assert disabled.id == created.id
    assert disabled.is_active is False
    assert disabled.deleted_at is None
    assert deleted.id == created.id
    assert deleted.is_active is False
    assert deleted.deleted_at == NOW.isoformat()
    assert rules.get_current(selector) is None
    assert rules.list() == []
    assert rules.list(include_deleted=True) == [deleted]


def test_deleted_scope_can_be_created_again_without_destroying_history(
    reminder_scope: dict[str, object],
) -> None:
    rules = repository(reminder_scope)
    selector = rules.resolve_target(target(ReminderScope.GLOBAL))
    first = rules.set(ReminderRuleWrite(selector, action=ReminderAction.SUPPRESS))
    rules.delete(selector)

    second = rules.set(ReminderRuleWrite(selector, action=ReminderAction.ENABLE))

    assert second.id != first.id
    assert len(rules.list(include_deleted=True)) == 2


def test_conflicting_participant_rule_rolls_back_atomically(
    reminder_scope: dict[str, object],
) -> None:
    rules = repository(reminder_scope)
    manchester = rules.resolve_target(
        target(ReminderScope.PARTICIPANT, participant="manchester_united")
    )
    liverpool = rules.resolve_target(
        target(ReminderScope.PARTICIPANT, participant="liverpool")
    )
    rules.set(ReminderRuleWrite(manchester, preferred_lead_minutes=60))

    with pytest.raises(ReminderRuleRepositoryError, match="equal precedence"):
        rules.set(ReminderRuleWrite(liverpool, preferred_lead_minutes=120))

    assert rules.get_current(liverpool) is None
    assert len(rules.list()) == 1


def test_event_rule_can_resolve_participant_conflict(
    reminder_scope: dict[str, object],
) -> None:
    rules = repository(reminder_scope)
    event = rules.resolve_target(
        target(
            ReminderScope.EVENT,
            event="premier_league:manchester_united:liverpool",
        )
    )
    rules.set(ReminderRuleWrite(event, preferred_lead_minutes=90))
    for participant, lead in (("manchester_united", 60), ("liverpool", 120)):
        selector = rules.resolve_target(
            target(ReminderScope.PARTICIPANT, participant=participant)
        )
        rules.set(ReminderRuleWrite(selector, preferred_lead_minutes=lead))

    applicable = rules.applicable_rules(
        competition_id=reminder_scope["premier_league"].id,  # type: ignore[union-attr]
        participant_ids=(
            reminder_scope["manchester"].id,  # type: ignore[union-attr]
            reminder_scope["liverpool"].id,  # type: ignore[union-attr]
        ),
        event_id=reminder_scope["event"].id,  # type: ignore[union-attr]
    )

    assert {item.selector.scope for item in applicable} == {
        ReminderScope.PARTICIPANT,
        ReminderScope.EVENT,
    }


def test_invalid_inherited_range_rolls_back(reminder_scope: dict[str, object]) -> None:
    rules = repository(reminder_scope)
    global_selector = rules.resolve_target(target(ReminderScope.GLOBAL))
    participant_selector = rules.resolve_target(
        target(ReminderScope.PARTICIPANT, participant="manchester_united")
    )
    rules.set(
        ReminderRuleWrite(
            global_selector,
            preferred_lead_minutes=60,
            minimum_lead_minutes=60,
        )
    )

    with pytest.raises(ReminderRuleRepositoryError, match="maximum lead"):
        rules.set(ReminderRuleWrite(participant_selector, maximum_lead_minutes=30))

    assert rules.get_current(participant_selector) is None


def test_resolve_target_rejects_unknown_and_cross_sport_keys(
    reminder_scope: dict[str, object],
) -> None:
    rules = repository(reminder_scope)

    with pytest.raises(ReminderRuleRepositoryError, match="Unknown canonical"):
        rules.resolve_target(
            target(ReminderScope.PARTICIPANT, participant="unknown_team")
        )
    with pytest.raises(ReminderRuleRepositoryError, match="same sport"):
        rules.resolve_target(
            target(
                ReminderScope.COMPETITION_PARTICIPANT,
                competition="premier_league",
                participant="new_england_patriots",
            )
        )


def test_database_rejects_duplicate_current_natural_scope(
    reminder_scope: dict[str, object],
) -> None:
    database_path = reminder_scope["database_path"]
    timestamp = NOW.isoformat()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO reminder_rules (
                scope, action, is_active, created_at, updated_at
            ) VALUES ('global', 'enable', 1, ?, ?)
            """,
            (timestamp, timestamp),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO reminder_rules (
                    scope, action, is_active, created_at, updated_at
                ) VALUES ('global', 'suppress', 1, ?, ?)
                """,
                (timestamp, timestamp),
            )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("timezone", " Europe/Vienna"),
        ("operator_note", "x" * 501),
    ],
)
def test_database_rejects_non_normalized_runtime_text(
    reminder_scope: dict[str, object],
    column: str,
    value: str,
) -> None:
    database_path = reminder_scope["database_path"]
    timestamp = NOW.isoformat()
    with (
        sqlite3.connect(database_path) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute(
            f"""
            INSERT INTO reminder_rules (
                scope, {column}, is_active, created_at, updated_at
            ) VALUES ('global', ?, 1, ?, ?)
            """,
            (value, timestamp, timestamp),
        )
