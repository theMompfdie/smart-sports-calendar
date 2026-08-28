from datetime import UTC, datetime

from app.config.settings import OefbIcalSettings
from app.providers.api_football.transport import HttpResponse

FEED_URL = "https://www.fussballoesterreich.at/Calendar/opaque-test-token.ics"
FETCHED_AT = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
LAST_MODIFIED = "Fri, 28 Aug 2026 11:55:00 GMT"


def settings(**overrides: object) -> OefbIcalSettings:
    values: dict[str, object] = {
        "enabled": True,
        "feed_url": FEED_URL,
        "connect_timeout_seconds": 2.5,
        "read_timeout_seconds": 12.5,
        "max_attempts": 3,
        "retry_base_delay_seconds": 1.0,
        "retry_max_delay_seconds": 30.0,
        "minimum_poll_interval_seconds": 21600,
    }
    values.update(overrides)
    return OefbIcalSettings(**values)


def response(
    status: int = 200,
    *,
    body: bytes = b"calendar",
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    default_headers = {
        "Content-Type": "text/calendar; charset=utf-8",
        "Content-Length": str(len(body)),
        "Last-Modified": LAST_MODIFIED,
    }
    default_headers.update(headers or {})
    return HttpResponse(status=status, headers=default_headers, body=body)


def calendar_payload(
    *,
    event_count: int = 1,
    event_overrides: tuple[str, ...] = (),
    calendar_overrides: tuple[str, ...] = (),
) -> bytes:
    events: list[str] = []
    for index in range(event_count):
        uid = f"{1000000 + index}"
        properties = [
            f"UID:{uid}",
            "DTSTAMP:20260828T115500Z",
            "DTSTART:20260828T180000Z",
            f"SUMMARY:Home {index} - Away {index}",
            "DESCRIPTION:1. Runde",
            "LOCATION:Test Stadium",
            f"URL:https://www.fussballoesterreich.at/Spiel/{uid}",
            f"X-HOMENR:{2000 + index * 2}",
            f"X-AWAYNR:{2001 + index * 2}",
        ]
        if index == 0:
            properties.extend(event_overrides)
        events.extend(("BEGIN:VEVENT", *properties, "END:VEVENT"))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Synthetic ÖFB Contract Test//EN",
        "CALSCALE:GREGORIAN",
        "X-PUBLISHED-TTL:PT6H",
        *calendar_overrides,
        *events,
        "END:VCALENDAR",
        "",
    ]
    return "\r\n".join(lines).encode()
