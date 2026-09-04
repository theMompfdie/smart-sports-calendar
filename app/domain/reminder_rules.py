"""Validated reminder-rule domain model and fixed-precedence inheritance."""

import re
from dataclasses import dataclass
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_REMINDER_TIMEZONE = "Europe/Vienna"
MAX_OPERATOR_NOTE_LENGTH = 500
_LOCAL_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class ReminderRuleError(ValueError):
    """Base class for safe reminder-rule validation failures."""


class ReminderRuleConflictError(ReminderRuleError):
    """Raised when equal-precedence rules contain conflicting values."""

    def __init__(self, fields: tuple[str, ...]) -> None:
        self.fields = fields
        super().__init__(
            "Conflicting reminder rule fields at equal precedence: " + ", ".join(fields)
        )


class ReminderScope(StrEnum):
    GLOBAL = "global"
    COMPETITION = "competition"
    PARTICIPANT = "participant"
    COMPETITION_PARTICIPANT = "competition_participant"
    EVENT = "event"


class ReminderAction(StrEnum):
    ENABLE = "enable"
    SUPPRESS = "suppress"


@dataclass(frozen=True)
class ReminderRuleSelector:
    scope: ReminderScope
    competition_id: int | None = None
    participant_id: int | None = None
    event_id: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", ReminderScope(self.scope))
        _validate_scope_shape(
            self.scope,
            self.competition_id,
            self.participant_id,
            self.event_id,
        )


@dataclass(frozen=True)
class ReminderRuleWrite:
    selector: ReminderRuleSelector
    action: ReminderAction | None = None
    preferred_lead_minutes: int | None = None
    minimum_lead_minutes: int | None = None
    maximum_lead_minutes: int | None = None
    quiet_start: str | None = None
    quiet_end: str | None = None
    timezone: str | None = None
    operator_note: str | None = None

    def __post_init__(self) -> None:
        if self.action is not None:
            object.__setattr__(self, "action", ReminderAction(self.action))
        _validate_policy_fields(
            action=self.action,
            preferred_lead_minutes=self.preferred_lead_minutes,
            minimum_lead_minutes=self.minimum_lead_minutes,
            maximum_lead_minutes=self.maximum_lead_minutes,
            quiet_start=self.quiet_start,
            quiet_end=self.quiet_end,
            timezone=self.timezone,
            operator_note=self.operator_note,
            require_policy=True,
        )


@dataclass(frozen=True)
class ReminderRule:
    id: int
    selector: ReminderRuleSelector
    action: ReminderAction | None
    preferred_lead_minutes: int | None
    minimum_lead_minutes: int | None
    maximum_lead_minutes: int | None
    quiet_start: str | None
    quiet_end: str | None
    timezone: str | None
    is_active: bool
    operator_note: str | None
    deleted_at: str | None
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if self.action is not None:
            object.__setattr__(self, "action", ReminderAction(self.action))
        _validate_policy_fields(
            action=self.action,
            preferred_lead_minutes=self.preferred_lead_minutes,
            minimum_lead_minutes=self.minimum_lead_minutes,
            maximum_lead_minutes=self.maximum_lead_minutes,
            quiet_start=self.quiet_start,
            quiet_end=self.quiet_end,
            timezone=self.timezone,
            operator_note=self.operator_note,
            require_policy=True,
        )
        if self.deleted_at is not None and self.is_active:
            raise ReminderRuleError("A deleted reminder rule cannot remain active.")


@dataclass(frozen=True)
class EffectiveReminderPolicy:
    action: ReminderAction
    preferred_lead_minutes: int
    minimum_lead_minutes: int
    maximum_lead_minutes: int | None
    quiet_start: str | None
    quiet_end: str | None
    timezone: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", ReminderAction(self.action))
        _validate_policy_fields(
            action=self.action,
            preferred_lead_minutes=self.preferred_lead_minutes,
            minimum_lead_minutes=self.minimum_lead_minutes,
            maximum_lead_minutes=self.maximum_lead_minutes,
            quiet_start=self.quiet_start,
            quiet_end=self.quiet_end,
            timezone=self.timezone,
            operator_note=None,
            require_policy=True,
        )


class ReminderRuleResolver:
    """Resolve active rules without calculating quiet-period reminder instants."""

    _FIELDS = (
        "action",
        "preferred_lead_minutes",
        "minimum_lead_minutes",
        "maximum_lead_minutes",
        "quiet_start",
        "quiet_end",
        "timezone",
    )
    _SCOPE_ORDER = (
        ReminderScope.GLOBAL,
        ReminderScope.COMPETITION,
        ReminderScope.PARTICIPANT,
        ReminderScope.COMPETITION_PARTICIPANT,
        ReminderScope.EVENT,
    )

    def resolve(self, rules: tuple[ReminderRule, ...]) -> EffectiveReminderPolicy:
        values: dict[str, object | None] = {
            "action": ReminderAction.ENABLE,
            "preferred_lead_minutes": 15,
            "minimum_lead_minutes": 0,
            "maximum_lead_minutes": None,
            "quiet_start": None,
            "quiet_end": None,
            "timezone": DEFAULT_REMINDER_TIMEZONE,
        }
        conflicts: set[str] = set()
        active_rules = tuple(
            rule for rule in rules if rule.is_active and rule.deleted_at is None
        )

        for scope in self._SCOPE_ORDER:
            scope_rules = tuple(
                rule for rule in active_rules if rule.selector.scope is scope
            )
            for field in self._FIELDS:
                candidates = {
                    getattr(rule, field)
                    for rule in scope_rules
                    if getattr(rule, field) is not None
                }
                if len(candidates) > 1:
                    conflicts.add(field)
                elif len(candidates) == 1:
                    values[field] = candidates.pop()
                    conflicts.discard(field)

        if conflicts:
            raise ReminderRuleConflictError(tuple(sorted(conflicts)))

        return EffectiveReminderPolicy(
            action=ReminderAction(values["action"]),
            preferred_lead_minutes=int(values["preferred_lead_minutes"]),
            minimum_lead_minutes=int(values["minimum_lead_minutes"]),
            maximum_lead_minutes=(
                None
                if values["maximum_lead_minutes"] is None
                else int(values["maximum_lead_minutes"])
            ),
            quiet_start=_optional_text(values["quiet_start"]),
            quiet_end=_optional_text(values["quiet_end"]),
            timezone=str(values["timezone"]),
        )


def _validate_scope_shape(
    scope: ReminderScope,
    competition_id: int | None,
    participant_id: int | None,
    event_id: int | None,
) -> None:
    present = (
        competition_id is not None,
        participant_id is not None,
        event_id is not None,
    )
    expected = {
        ReminderScope.GLOBAL: (False, False, False),
        ReminderScope.COMPETITION: (True, False, False),
        ReminderScope.PARTICIPANT: (False, True, False),
        ReminderScope.COMPETITION_PARTICIPANT: (True, True, False),
        ReminderScope.EVENT: (False, False, True),
    }[scope]
    if present != expected:
        raise ReminderRuleError(
            f"Invalid canonical identifiers for {scope.value} scope."
        )
    for identifier in (competition_id, participant_id, event_id):
        if identifier is not None and (
            isinstance(identifier, bool)
            or not isinstance(identifier, int)
            or identifier <= 0
        ):
            raise ReminderRuleError(
                "Canonical reminder rule identifiers must be positive integers."
            )


def _validate_policy_fields(
    *,
    action: ReminderAction | None,
    preferred_lead_minutes: int | None,
    minimum_lead_minutes: int | None,
    maximum_lead_minutes: int | None,
    quiet_start: str | None,
    quiet_end: str | None,
    timezone: str | None,
    operator_note: str | None,
    require_policy: bool,
) -> None:
    leads = {
        "preferred": preferred_lead_minutes,
        "minimum": minimum_lead_minutes,
        "maximum": maximum_lead_minutes,
    }
    for name, value in leads.items():
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            raise ReminderRuleError(
                f"Reminder {name} lead must be a non-negative integer."
            )
    if (
        minimum_lead_minutes is not None
        and preferred_lead_minutes is not None
        and minimum_lead_minutes > preferred_lead_minutes
    ):
        raise ReminderRuleError("Minimum lead must not exceed preferred lead.")
    if (
        preferred_lead_minutes is not None
        and maximum_lead_minutes is not None
        and preferred_lead_minutes > maximum_lead_minutes
    ):
        raise ReminderRuleError("Preferred lead must not exceed maximum lead.")
    if (
        minimum_lead_minutes is not None
        and maximum_lead_minutes is not None
        and minimum_lead_minutes > maximum_lead_minutes
    ):
        raise ReminderRuleError("Minimum lead must not exceed maximum lead.")
    if (quiet_start is None) != (quiet_end is None):
        raise ReminderRuleError("Quiet start and end must be configured together.")
    for name, value in (("start", quiet_start), ("end", quiet_end)):
        if value is not None and _LOCAL_TIME_PATTERN.fullmatch(value) is None:
            raise ReminderRuleError(f"Quiet {name} must use HH:MM in 24-hour time.")
    if timezone is not None:
        if not timezone or timezone != timezone.strip():
            raise ReminderRuleError(
                "Reminder timezone must be normalized and non-empty."
            )
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as error:
            raise ReminderRuleError(f"Unknown reminder timezone: {timezone}") from error
    if operator_note is not None and (
        not operator_note
        or operator_note != operator_note.strip()
        or len(operator_note) > MAX_OPERATOR_NOTE_LENGTH
    ):
        raise ReminderRuleError(
            "Operator note must be normalized, non-empty, and at most "
            f"{MAX_OPERATOR_NOTE_LENGTH} characters."
        )
    if require_policy and all(
        value is None
        for value in (
            action,
            preferred_lead_minutes,
            minimum_lead_minutes,
            maximum_lead_minutes,
            quiet_start,
            quiet_end,
            timezone,
        )
    ):
        raise ReminderRuleError(
            "A reminder rule must configure at least one policy field."
        )


def _optional_text(value: object | None) -> str | None:
    return None if value is None else str(value)
