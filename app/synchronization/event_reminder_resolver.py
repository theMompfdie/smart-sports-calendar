"""Resolve current persisted reminder policy for a synchronization event."""

import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.database.reminder_rules_repository import ReminderRulesRepository
from app.database.synchronization_query_repository import SynchronizationEvent
from app.domain.reminder_rules import (
    DEFAULT_REMINDER_TIMEZONE,
    ReminderRuleConflictError,
    ReminderRuleError,
    ReminderRuleResolver,
)
from app.domain.reminder_schedule import (
    ReminderResolutionError,
    ReminderResolutionReason,
    ReminderScheduleResolver,
    ResolvedReminder,
)


class EventReminderResolver:
    """Read reminder rules for every build so live mutations need no restart."""

    def __init__(
        self,
        repository: ReminderRulesRepository,
        *,
        logger: logging.Logger | None = None,
        rule_resolver: ReminderRuleResolver | None = None,
        schedule_resolver: ReminderScheduleResolver | None = None,
    ) -> None:
        self._repository = repository
        self._logger = logger or logging.getLogger(__name__)
        self._rule_resolver = rule_resolver or ReminderRuleResolver()
        self._schedule_resolver = schedule_resolver or ReminderScheduleResolver()

    def resolve(self, synchronization_event: SynchronizationEvent) -> ResolvedReminder:
        event = synchronization_event.event
        try:
            rules = self._repository.applicable_rules(
                competition_id=event.competition_id,
                participant_ids=(
                    item.participant.id for item in synchronization_event.participants
                ),
                event_id=event.id,
            )
            policy = self._rule_resolver.resolve(rules)
        except ReminderRuleConflictError as error:
            self._logger.warning(
                "Reminder disabled for event_id=%s because equal-precedence "
                "policy fields conflict: %s",
                event.id,
                ",".join(error.fields),
            )
            return ResolvedReminder.disabled(
                reason=ReminderResolutionReason.CONFLICT,
                timezone=DEFAULT_REMINDER_TIMEZONE,
                conflict_fields=error.fields,
            )
        except ReminderRuleError:
            self._logger.warning(
                "Reminder disabled for event_id=%s because the effective "
                "policy is invalid.",
                event.id,
            )
            return ResolvedReminder.disabled(
                reason=ReminderResolutionReason.INVALID,
                timezone=DEFAULT_REMINDER_TIMEZONE,
            )

        return self._schedule_resolver.resolve(
            policy,
            _parse_event_start(event.start_time, event.timezone),
        )


def _parse_event_start(value: str, timezone: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ReminderResolutionError("Canonical event start is invalid.") from error

    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC)

    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise ReminderResolutionError("Canonical event timezone is unknown.") from error

    candidates: set[datetime] = set()
    for fold in (0, 1):
        aware = parsed.replace(tzinfo=zone, fold=fold)
        candidate = aware.astimezone(UTC)
        round_trip = candidate.astimezone(zone)
        if round_trip.replace(tzinfo=None) == parsed and round_trip.fold == fold:
            candidates.add(candidate)
    if not candidates:
        raise ReminderResolutionError(
            "Canonical local event start does not exist in its timezone."
        )
    return min(candidates)
