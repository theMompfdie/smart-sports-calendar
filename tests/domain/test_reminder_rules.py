from dataclasses import replace

import pytest
from app.domain.reminder_rules import (
    DEFAULT_REMINDER_TIMEZONE,
    EffectiveReminderPolicy,
    ReminderAction,
    ReminderRule,
    ReminderRuleConflictError,
    ReminderRuleError,
    ReminderRuleResolver,
    ReminderRuleSelector,
    ReminderRuleWrite,
    ReminderScope,
)

TIMESTAMP = "2026-09-01T10:00:00+00:00"


def rule(
    rule_id: int,
    scope: ReminderScope,
    *,
    competition_id: int | None = None,
    participant_id: int | None = None,
    event_id: int | None = None,
    action: ReminderAction | None = None,
    preferred: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
    quiet_start: str | None = None,
    quiet_end: str | None = None,
    timezone: str | None = None,
    is_active: bool = True,
) -> ReminderRule:
    return ReminderRule(
        id=rule_id,
        selector=ReminderRuleSelector(
            scope,
            competition_id=competition_id,
            participant_id=participant_id,
            event_id=event_id,
        ),
        action=action,
        preferred_lead_minutes=preferred,
        minimum_lead_minutes=minimum,
        maximum_lead_minutes=maximum,
        quiet_start=quiet_start,
        quiet_end=quiet_end,
        timezone=timezone,
        is_active=is_active,
        operator_note=None,
        deleted_at=None,
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )


def test_resolver_returns_compatibility_fallback_without_rules() -> None:
    policy = ReminderRuleResolver().resolve(())

    assert policy == EffectiveReminderPolicy(
        action=ReminderAction.ENABLE,
        preferred_lead_minutes=15,
        minimum_lead_minutes=0,
        maximum_lead_minutes=None,
        quiet_start=None,
        quiet_end=None,
        timezone=DEFAULT_REMINDER_TIMEZONE,
    )


def test_resolver_overlays_fixed_scope_order_field_by_field() -> None:
    policy = ReminderRuleResolver().resolve(
        (
            rule(
                1,
                ReminderScope.GLOBAL,
                action=ReminderAction.SUPPRESS,
                preferred=30,
            ),
            rule(
                2,
                ReminderScope.COMPETITION,
                competition_id=10,
                minimum=10,
                timezone="Europe/London",
            ),
            rule(
                3,
                ReminderScope.PARTICIPANT,
                participant_id=20,
                action=ReminderAction.ENABLE,
                preferred=60,
            ),
            rule(
                4,
                ReminderScope.EVENT,
                event_id=30,
                maximum=480,
                quiet_start="22:00",
                quiet_end="08:00",
                timezone="Europe/Vienna",
            ),
        )
    )

    assert policy == EffectiveReminderPolicy(
        action=ReminderAction.ENABLE,
        preferred_lead_minutes=60,
        minimum_lead_minutes=10,
        maximum_lead_minutes=480,
        quiet_start="22:00",
        quiet_end="08:00",
        timezone="Europe/Vienna",
    )


def test_resolver_rejects_unresolved_equal_participant_conflict() -> None:
    rules = (
        rule(1, ReminderScope.PARTICIPANT, participant_id=20, preferred=60),
        rule(2, ReminderScope.PARTICIPANT, participant_id=21, preferred=120),
    )

    with pytest.raises(ReminderRuleConflictError) as captured:
        ReminderRuleResolver().resolve(rules)

    assert captured.value.fields == ("preferred_lead_minutes",)


def test_more_specific_value_resolves_equal_precedence_conflict() -> None:
    rules = (
        rule(1, ReminderScope.PARTICIPANT, participant_id=20, preferred=60),
        rule(2, ReminderScope.PARTICIPANT, participant_id=21, preferred=120),
        rule(3, ReminderScope.EVENT, event_id=30, preferred=90),
    )

    assert ReminderRuleResolver().resolve(rules).preferred_lead_minutes == 90


def test_resolver_ignores_inactive_and_deleted_rules() -> None:
    inactive = rule(
        1,
        ReminderScope.GLOBAL,
        action=ReminderAction.SUPPRESS,
        is_active=False,
    )
    deleted = replace(inactive, id=2, deleted_at=TIMESTAMP)

    assert (
        ReminderRuleResolver().resolve((inactive, deleted)).action
        is ReminderAction.ENABLE
    )


@pytest.mark.parametrize(
    ("scope", "competition_id", "participant_id", "event_id"),
    [
        (ReminderScope.GLOBAL, 1, None, None),
        (ReminderScope.COMPETITION, None, None, None),
        (ReminderScope.PARTICIPANT, None, None, 1),
        (ReminderScope.COMPETITION_PARTICIPANT, 1, None, None),
        (ReminderScope.EVENT, None, 1, None),
    ],
)
def test_selector_rejects_invalid_scope_shapes(
    scope: ReminderScope,
    competition_id: int | None,
    participant_id: int | None,
    event_id: int | None,
) -> None:
    with pytest.raises(ReminderRuleError, match="Invalid canonical identifiers"):
        ReminderRuleSelector(
            scope,
            competition_id=competition_id,
            participant_id=participant_id,
            event_id=event_id,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"preferred_lead_minutes": -1},
        {"minimum_lead_minutes": 61, "preferred_lead_minutes": 60},
        {"preferred_lead_minutes": 60, "maximum_lead_minutes": 59},
        {"minimum_lead_minutes": 61, "maximum_lead_minutes": 60},
        {"quiet_start": "22:00"},
        {"quiet_start": "24:00", "quiet_end": "08:00"},
        {"timezone": "Invalid/Zone"},
        {"operator_note": " note", "action": ReminderAction.ENABLE},
    ],
)
def test_write_rejects_invalid_policy(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "selector": ReminderRuleSelector(ReminderScope.GLOBAL),
        "action": ReminderAction.ENABLE,
    }
    values.update(overrides)

    with pytest.raises(ReminderRuleError):
        ReminderRuleWrite(**values)  # type: ignore[arg-type]


def test_write_rejects_rule_without_policy_fields() -> None:
    with pytest.raises(ReminderRuleError, match="at least one policy field"):
        ReminderRuleWrite(ReminderRuleSelector(ReminderScope.GLOBAL))
