from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from app.domain.reminder_rules import EffectiveReminderPolicy, ReminderAction
from app.domain.reminder_schedule import (
    ReminderResolutionError,
    ReminderResolutionReason,
    ReminderScheduleResolver,
)

VIENNA = ZoneInfo("Europe/Vienna")


def policy(**overrides: object) -> EffectiveReminderPolicy:
    values = {
        "action": ReminderAction.ENABLE,
        "preferred_lead_minutes": 60,
        "minimum_lead_minutes": 60,
        "maximum_lead_minutes": 480,
        "quiet_start": "22:00",
        "quiet_end": "08:00",
        "timezone": "Europe/Vienna",
    }
    values.update(overrides)
    return EffectiveReminderPolicy(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("event_start", "expected_lead", "reason"),
    [
        (
            datetime.fromisoformat("2026-09-01T19:00:00+02:00"),
            60,
            ReminderResolutionReason.ENABLED,
        ),
        (
            datetime.fromisoformat("2026-09-01T22:25:00+02:00"),
            60,
            ReminderResolutionReason.ENABLED,
        ),
        (
            datetime.fromisoformat("2026-09-02T00:25:00+02:00"),
            145,
            ReminderResolutionReason.QUIET_SHIFTED,
        ),
        (
            datetime.fromisoformat("2026-09-02T02:20:00+02:00"),
            260,
            ReminderResolutionReason.QUIET_SHIFTED,
        ),
    ],
)
def test_resolves_required_vienna_examples(
    event_start: datetime,
    expected_lead: int,
    reason: ReminderResolutionReason,
) -> None:
    result = ReminderScheduleResolver().resolve(policy(), event_start)

    assert result.is_reminder_on is True
    assert result.minutes_before_start == expected_lead
    assert result.reason is reason


def test_disables_required_nfl_example_outside_maximum() -> None:
    result = ReminderScheduleResolver().resolve(
        policy(),
        datetime.fromisoformat("2026-09-02T06:30:00+02:00"),
    )

    assert result.is_reminder_on is False
    assert result.minutes_before_start == 0
    assert result.reason is ReminderResolutionReason.OUTSIDE_BOUNDS


@pytest.mark.parametrize(
    ("event_start", "expected_boundary_utc"),
    [
        (
            datetime(2026, 1, 15, 1, 20, tzinfo=UTC),
            datetime(2026, 1, 14, 21, 0, tzinfo=UTC),
        ),
        (
            datetime(2026, 7, 15, 0, 20, tzinfo=UTC),
            datetime(2026, 7, 14, 20, 0, tzinfo=UTC),
        ),
    ],
)
def test_winter_and_summer_use_vienna_local_boundaries(
    event_start: datetime,
    expected_boundary_utc: datetime,
) -> None:
    result = ReminderScheduleResolver().resolve(policy(), event_start)

    assert result.reminder_at == expected_boundary_utc
    assert result.minutes_before_start == 260


def test_nonexistent_spring_boundary_uses_latest_valid_local_minute() -> None:
    result = ReminderScheduleResolver().resolve(
        policy(
            preferred_lead_minutes=30,
            minimum_lead_minutes=0,
            maximum_lead_minutes=180,
            quiet_start="02:30",
        ),
        datetime(2026, 3, 29, 4, 0, tzinfo=VIENNA),
    )

    assert result.reason is ReminderResolutionReason.QUIET_SHIFTED
    assert result.reminder_at == datetime(2026, 3, 29, 0, 59, tzinfo=UTC)
    assert result.reminder_at.astimezone(VIENNA).isoformat() == (
        "2026-03-29T01:59:00+01:00"
    )
    assert result.minutes_before_start == 61


def test_ambiguous_autumn_boundary_uses_earlier_absolute_instant() -> None:
    result = ReminderScheduleResolver().resolve(
        policy(
            preferred_lead_minutes=30,
            minimum_lead_minutes=0,
            maximum_lead_minutes=180,
            quiet_start="02:30",
        ),
        datetime(2026, 10, 25, 4, 0, tzinfo=VIENNA),
    )

    assert result.reason is ReminderResolutionReason.QUIET_SHIFTED
    assert result.reminder_at == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert result.reminder_at.astimezone(VIENNA).fold == 0
    assert result.minutes_before_start == 150


@pytest.mark.parametrize(
    "event_start",
    [
        datetime.fromisoformat("2026-09-01T23:00:00+02:00"),
        datetime.fromisoformat("2026-09-01T09:00:00+02:00"),
    ],
)
def test_exact_quiet_boundaries_are_allowed(event_start: datetime) -> None:
    result = ReminderScheduleResolver().resolve(policy(), event_start)

    assert result.reason is ReminderResolutionReason.ENABLED
    assert result.minutes_before_start == 60


def test_equal_quiet_boundaries_mean_no_quiet_period() -> None:
    result = ReminderScheduleResolver().resolve(
        policy(quiet_start="22:00", quiet_end="22:00"),
        datetime.fromisoformat("2026-09-02T02:20:00+02:00"),
    )

    assert result.reason is ReminderResolutionReason.ENABLED
    assert result.minutes_before_start == 60


def test_inclusive_lead_limits_accept_exact_preferred_lead() -> None:
    result = ReminderScheduleResolver().resolve(
        policy(
            minimum_lead_minutes=60,
            maximum_lead_minutes=60,
            quiet_start=None,
            quiet_end=None,
        ),
        datetime.fromisoformat("2026-09-01T19:00:00+02:00"),
    )

    assert result.is_reminder_on is True
    assert result.minutes_before_start == 60


def test_fractional_boundary_lead_fails_quiet() -> None:
    result = ReminderScheduleResolver().resolve(
        policy(),
        datetime.fromisoformat("2026-09-02T00:25:30+02:00"),
    )

    assert result.is_reminder_on is False
    assert result.reason is ReminderResolutionReason.NON_INTEGER_LEAD


def test_suppressed_policy_does_not_schedule_a_reminder() -> None:
    result = ReminderScheduleResolver().resolve(
        policy(action=ReminderAction.SUPPRESS),
        datetime.fromisoformat("2026-09-01T19:00:00+02:00"),
    )

    assert result.is_reminder_on is False
    assert result.reason is ReminderResolutionReason.SUPPRESSED


def test_naive_event_start_is_rejected() -> None:
    with pytest.raises(ReminderResolutionError, match="timezone-aware"):
        ReminderScheduleResolver().resolve(
            policy(),
            datetime(2026, 9, 1, 19, 0),
        )
