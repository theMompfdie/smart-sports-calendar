"""Timezone-aware resolution of one effective reminder policy."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from app.domain.reminder_rules import EffectiveReminderPolicy, ReminderAction

_MICROSECONDS_PER_MINUTE = 60_000_000
_MAX_BOUNDARY_LOOKBACK_MINUTES = 24 * 60


class ReminderResolutionError(ValueError):
    """Raised when canonical event timing cannot be resolved safely."""


class ReminderResolutionReason(StrEnum):
    ENABLED = "enabled"
    QUIET_SHIFTED = "quiet_shifted"
    SUPPRESSED = "suppressed"
    OUTSIDE_BOUNDS = "outside_bounds"
    NON_INTEGER_LEAD = "non_integer_lead"
    CONFLICT = "conflict"
    INVALID = "invalid"


@dataclass(frozen=True)
class ResolvedReminder:
    is_reminder_on: bool
    minutes_before_start: int
    reason: ReminderResolutionReason
    timezone: str
    reminder_at: datetime | None = None
    conflict_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", ReminderResolutionReason(self.reason))
        if self.is_reminder_on:
            if self.minutes_before_start < 0:
                raise ReminderResolutionError(
                    "Enabled reminder lead must not be negative."
                )
            if self.reminder_at is None or self.reminder_at.utcoffset() is None:
                raise ReminderResolutionError(
                    "Enabled reminder instant must be timezone-aware."
                )
        elif self.minutes_before_start != 0 or self.reminder_at is not None:
            raise ReminderResolutionError(
                "Disabled reminders must use a zero lead and no instant."
            )

    @classmethod
    def disabled(
        cls,
        *,
        reason: ReminderResolutionReason,
        timezone: str,
        conflict_fields: tuple[str, ...] = (),
    ) -> "ResolvedReminder":
        return cls(
            is_reminder_on=False,
            minutes_before_start=0,
            reason=reason,
            timezone=timezone,
            conflict_fields=conflict_fields,
        )


class ReminderScheduleResolver:
    """Convert an effective policy and kickoff into one Graph-compatible lead."""

    def resolve(
        self,
        policy: EffectiveReminderPolicy,
        event_start: datetime,
    ) -> ResolvedReminder:
        if event_start.utcoffset() is None:
            raise ReminderResolutionError("Event start must be timezone-aware.")
        if policy.action is ReminderAction.SUPPRESS:
            return ResolvedReminder.disabled(
                reason=ReminderResolutionReason.SUPPRESSED,
                timezone=policy.timezone,
            )

        start_utc = event_start.astimezone(UTC)
        reminder_utc = start_utc - timedelta(minutes=policy.preferred_lead_minutes)
        reason = ReminderResolutionReason.ENABLED

        if (
            policy.quiet_start is not None
            and policy.quiet_end is not None
            and policy.quiet_start != policy.quiet_end
        ):
            zone = ZoneInfo(policy.timezone)
            candidate_local = reminder_utc.astimezone(zone)
            quiet_start = time.fromisoformat(policy.quiet_start)
            quiet_end = time.fromisoformat(policy.quiet_end)
            boundary_date = _quiet_boundary_date(
                candidate_local,
                quiet_start,
                quiet_end,
            )
            if boundary_date is not None:
                reminder_utc = _resolve_boundary(
                    datetime.combine(boundary_date, quiet_start),
                    zone,
                )
                reason = ReminderResolutionReason.QUIET_SHIFTED

        total_microseconds = _timedelta_microseconds(start_utc - reminder_utc)
        minutes, remainder = divmod(
            total_microseconds,
            _MICROSECONDS_PER_MINUTE,
        )
        if remainder != 0:
            return ResolvedReminder.disabled(
                reason=ReminderResolutionReason.NON_INTEGER_LEAD,
                timezone=policy.timezone,
            )
        if minutes < policy.minimum_lead_minutes or (
            policy.maximum_lead_minutes is not None
            and minutes > policy.maximum_lead_minutes
        ):
            return ResolvedReminder.disabled(
                reason=ReminderResolutionReason.OUTSIDE_BOUNDS,
                timezone=policy.timezone,
            )

        return ResolvedReminder(
            is_reminder_on=True,
            minutes_before_start=minutes,
            reason=reason,
            timezone=policy.timezone,
            reminder_at=reminder_utc,
        )


def _quiet_boundary_date(
    candidate_local: datetime,
    quiet_start: time,
    quiet_end: time,
) -> date | None:
    candidate_time = candidate_local.time().replace(tzinfo=None)
    if quiet_start < quiet_end:
        return (
            candidate_local.date() if quiet_start < candidate_time < quiet_end else None
        )
    if candidate_time > quiet_start:
        return candidate_local.date()
    if candidate_time < quiet_end:
        return candidate_local.date() - timedelta(days=1)
    return None


def _resolve_boundary(boundary: datetime, zone: ZoneInfo) -> datetime:
    current = boundary
    for _ in range(_MAX_BOUNDARY_LOOKBACK_MINUTES + 1):
        candidates = _valid_utc_instants(current, zone)
        if candidates:
            return min(candidates)
        current -= timedelta(minutes=1)
    raise ReminderResolutionError(
        "No valid local quiet boundary exists within the safe lookback window."
    )


def _valid_utc_instants(local_value: datetime, zone: ZoneInfo) -> tuple[datetime, ...]:
    candidates: set[datetime] = set()
    for fold in (0, 1):
        aware = local_value.replace(tzinfo=zone, fold=fold)
        candidate = aware.astimezone(UTC)
        round_trip = candidate.astimezone(zone)
        if round_trip.replace(tzinfo=None) == local_value and round_trip.fold == fold:
            candidates.add(candidate)
    return tuple(sorted(candidates))


def _timedelta_microseconds(value: timedelta) -> int:
    return (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds
