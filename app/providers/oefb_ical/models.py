import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from icalendar import Calendar
from icalendar.cal.component import Component

from app.providers.oefb_ical.exceptions import (
    OefbIcalIntegrityError,
    OefbIcalSchemaError,
)
from app.providers.oefb_ical.transport import ALLOWED_HOST

MAX_EVENT_COUNT = 256
UID_PATTERN = re.compile(r"^\d{7}$")
CALENDAR_PROPERTIES = frozenset(
    {
        "VERSION",
        "PRODID",
        "CALSCALE",
        "METHOD",
        "X-WR-CALNAME",
        "X-WR-CALDESC",
        "X-WR-TIMEZONE",
        "X-PUBLISHED-TTL",
        "REFRESH-INTERVAL",
    }
)
EVENT_PROPERTIES = frozenset(
    {
        "UID",
        "DTSTAMP",
        "DTSTART",
        "SUMMARY",
        "DESCRIPTION",
        "LOCATION",
        "URL",
        "X-HOMENR",
        "X-AWAYNR",
    }
)


@dataclass(frozen=True)
class OefbIcalEvent:
    uid: str
    dtstamp_utc: datetime
    kickoff_utc: datetime
    summary: str
    description: str
    location: str
    url: str
    home_provider_id: int
    away_provider_id: int


@dataclass(frozen=True)
class OefbIcalSnapshot:
    events: tuple[OefbIcalEvent, ...]
    fetched_at_utc: datetime
    request_attempts: int
    last_modified: str | None


def parse_snapshot(
    payload: bytes,
    *,
    fetched_at_utc: datetime,
    request_attempts: int,
    last_modified: str | None,
) -> OefbIcalSnapshot:
    if request_attempts <= 0:
        raise ValueError("request_attempts must be positive.")
    try:
        calendar = Calendar.from_ical(payload)
    except (ValueError, TypeError) as error:
        raise OefbIcalSchemaError(
            "Provider returned malformed iCalendar data."
        ) from error
    if calendar.name != "VCALENDAR" or getattr(calendar, "errors", ()):
        raise OefbIcalSchemaError("Provider returned an invalid calendar.")
    unknown_calendar_properties = set(calendar.keys()) - CALENDAR_PROPERTIES
    if unknown_calendar_properties:
        raise OefbIcalSchemaError("Provider calendar contains unsupported properties.")
    if str(calendar.get("VERSION", "")).strip() != "2.0":
        raise OefbIcalSchemaError("Provider calendar has an unsupported version.")
    if str(calendar.get("X-PUBLISHED-TTL", "")).strip().upper() != "PT6H":
        raise OefbIcalIntegrityError(
            "Provider calendar has an unexpected publication interval."
        )
    if any(component.name != "VEVENT" for component in calendar.subcomponents):
        raise OefbIcalSchemaError("Provider calendar contains unsupported components.")
    if not calendar.subcomponents or len(calendar.subcomponents) > MAX_EVENT_COUNT:
        raise OefbIcalIntegrityError(
            "Provider calendar contains an unsafe number of events."
        )
    events = tuple(_parse_event(component) for component in calendar.subcomponents)
    uids = [event.uid for event in events]
    if len(uids) != len(set(uids)):
        raise OefbIcalIntegrityError("Provider calendar contains duplicate UIDs.")
    return OefbIcalSnapshot(
        events=events,
        fetched_at_utc=_require_utc(fetched_at_utc, "fetched_at_utc"),
        request_attempts=request_attempts,
        last_modified=last_modified,
    )


def _parse_event(component: Component) -> OefbIcalEvent:
    if getattr(component, "errors", ()):
        raise OefbIcalSchemaError("Provider event contains parsing errors.")
    if set(component.keys()) - EVENT_PROPERTIES:
        raise OefbIcalSchemaError("Provider event contains unsupported properties.")
    required = EVENT_PROPERTIES
    if set(component.keys()) != required:
        raise OefbIcalSchemaError("Provider event is missing required properties.")
    uid = _required_text(component, "UID")
    if not UID_PATTERN.fullmatch(uid):
        raise OefbIcalIntegrityError("Provider event has an invalid UID.")
    dtstamp = _required_datetime(component, "DTSTAMP")
    kickoff = _required_datetime(component, "DTSTART")
    home_provider_id = _required_positive_integer(component, "X-HOMENR")
    away_provider_id = _required_positive_integer(component, "X-AWAYNR")
    if home_provider_id == away_provider_id:
        raise OefbIcalIntegrityError(
            "Provider event contains the same participant twice."
        )
    url = _required_text(component, "URL")
    parsed_url = urlsplit(url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != ALLOWED_HOST
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.fragment
    ):
        raise OefbIcalIntegrityError("Provider event has an unsafe official URL.")
    return OefbIcalEvent(
        uid=uid,
        dtstamp_utc=dtstamp,
        kickoff_utc=kickoff,
        summary=_required_text(component, "SUMMARY"),
        description=_required_text(component, "DESCRIPTION"),
        location=_required_text(component, "LOCATION"),
        url=url,
        home_provider_id=home_provider_id,
        away_provider_id=away_provider_id,
    )


def _required_text(component: Component, name: str) -> str:
    value = component.get(name)
    if value is None or isinstance(value, list):
        raise OefbIcalSchemaError("Provider event has an invalid property count.")
    text = str(value).strip()
    if not text:
        raise OefbIcalSchemaError("Provider event has a blank required property.")
    return text


def _required_datetime(component: Component, name: str) -> datetime:
    value = component.get(name)
    if value is None or isinstance(value, list):
        raise OefbIcalSchemaError("Provider event has an invalid property count.")
    try:
        decoded = component.decoded(name)
    except (KeyError, ValueError, TypeError) as error:
        raise OefbIcalSchemaError(
            "Provider event has an invalid date-time property."
        ) from error
    if not isinstance(decoded, datetime):
        raise OefbIcalSchemaError("Provider event date-time must include a time.")
    return _require_utc(decoded, name)


def _required_positive_integer(component: Component, name: str) -> int:
    text = _required_text(component, name)
    if not text.isascii() or not text.isdecimal():
        raise OefbIcalIntegrityError("Provider event has an invalid participant ID.")
    value = int(text)
    if value <= 0:
        raise OefbIcalIntegrityError("Provider event has an invalid participant ID.")
    return value


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise OefbIcalSchemaError(f"Provider {field_name} must be UTC.")
    return value.astimezone(UTC)
