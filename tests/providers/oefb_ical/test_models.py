from datetime import UTC, datetime, timedelta

import pytest
from app.providers.oefb_ical.exceptions import (
    OefbIcalIntegrityError,
    OefbIcalSchemaError,
)
from app.providers.oefb_ical.models import MAX_EVENT_COUNT, parse_snapshot

from tests.providers.oefb_ical.support import (
    FETCHED_AT,
    LAST_MODIFIED,
    calendar_payload,
)


def parse(payload: bytes):
    return parse_snapshot(
        payload,
        fetched_at_utc=FETCHED_AT,
        request_attempts=2,
        last_modified=LAST_MODIFIED,
    )


def test_parser_accepts_qualified_synthetic_calendar() -> None:
    snapshot = parse(calendar_payload())

    assert snapshot.fetched_at_utc == FETCHED_AT
    assert snapshot.request_attempts == 2
    assert snapshot.last_modified == LAST_MODIFIED
    assert len(snapshot.events) == 1
    event = snapshot.events[0]
    assert event.uid == "1000000"
    assert event.kickoff_utc == datetime(2026, 8, 28, 18, 0, tzinfo=UTC)
    assert event.dtstamp_utc == datetime(2026, 8, 28, 11, 55, tzinfo=UTC)
    assert event.duration == timedelta(hours=2)
    assert event.home_provider_id == 2000
    assert event.away_provider_id == 2001
    assert event.home_provider_code == "H00"
    assert event.away_provider_code == "A00"
    assert event.provider_category == "UNIQA ÖFB Cup"
    assert event.description == "1. Runde"


def test_parser_rejects_duplicate_uid() -> None:
    payload = calendar_payload(event_count=2).replace(b"UID:1000001", b"UID:1000000")

    with pytest.raises(OefbIcalIntegrityError, match="duplicate UIDs"):
        parse(payload)


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        (b"UID:1000000", b"UID:not-numeric", "invalid UID"),
        (b"DTSTART:20260828T180000Z", b"DTSTART:20260828T180000", "must be UTC"),
        (b"X-AWAYNR:2001", b"X-AWAYNR:2000", "same participant"),
        (b"X-HOMENR:2000", b"X-HOMENR:not-numeric", "participant ID"),
        (
            b"URL:https://www.oefb.at/cup/Spiel/1000000?synthetic=true",
            b"URL:https://example.test/Spiel/1000000",
            "unsafe official URL",
        ),
    ],
)
def test_parser_rejects_invalid_identity_or_time(
    old: bytes,
    new: bytes,
    match: str,
) -> None:
    with pytest.raises((OefbIcalIntegrityError, OefbIcalSchemaError), match=match):
        parse(calendar_payload().replace(old, new))


@pytest.mark.parametrize(
    "extra_property",
    [
        "RRULE:FREQ=DAILY",
        "RECURRENCE-ID:20260828T180000Z",
        "STATUS:CANCELLED",
        "SEQUENCE:1",
        "X-UNKNOWN:value",
    ],
)
def test_parser_rejects_unsupported_event_properties(extra_property: str) -> None:
    with pytest.raises(OefbIcalSchemaError, match="unsupported properties"):
        parse(calendar_payload(event_overrides=(extra_property,)))


def test_parser_rejects_missing_required_property() -> None:
    payload = calendar_payload().replace(b"LOCATION:Test Stadium\r\n", b"")

    with pytest.raises(OefbIcalSchemaError, match="missing required"):
        parse(payload)


@pytest.mark.parametrize(
    "duration",
    ["PT0S", "P2D"],
)
def test_parser_rejects_unsafe_duration(duration: str) -> None:
    payload = calendar_payload().replace(
        b"DURATION:PT2H", f"DURATION:{duration}".encode()
    )

    with pytest.raises(OefbIcalIntegrityError, match="unsafe duration"):
        parse(payload)


def test_parser_rejects_oversized_auxiliary_property() -> None:
    payload = calendar_payload().replace(
        b"X-HOMEABC:H00",
        f"X-HOMEABC:{'A' * 129}".encode(),
    )

    with pytest.raises(OefbIcalIntegrityError, match="unsafe auxiliary"):
        parse(payload)


def test_parser_accepts_blank_unused_provider_codes() -> None:
    payload = (
        calendar_payload()
        .replace(b"X-HOMEABC:H00", b"X-HOMEABC:")
        .replace(b"X-AWAYABC:A00", b"X-AWAYABC:")
    )

    event = parse(payload).events[0]

    assert event.home_provider_code is None
    assert event.away_provider_code is None


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "https://www.oefb.at:444/cup/Spiel/1000000",
        "https://www.oefb.at/oefb/Spiel/1000000",
        "https://user@www.oefb.at/cup/Spiel/1000000",
        "https://www.oefb.at/cup/Spiel/1000000#fragment",
    ],
)
def test_parser_rejects_unsafe_official_url_shape(unsafe_url: str) -> None:
    payload = calendar_payload().replace(
        b"URL:https://www.oefb.at/cup/Spiel/1000000?synthetic=true",
        f"URL:{unsafe_url}".encode(),
    )

    with pytest.raises(OefbIcalIntegrityError, match="unsafe official URL"):
        parse(payload)


def test_parser_rejects_unexpected_publication_ttl() -> None:
    payload = calendar_payload().replace(
        b"X-PUBLISHED-TTL:PT6H", b"X-PUBLISHED-TTL:PT1H"
    )

    with pytest.raises(OefbIcalIntegrityError, match="publication interval"):
        parse(payload)


def test_parser_rejects_empty_or_oversized_calendar() -> None:
    with pytest.raises(OefbIcalIntegrityError, match="number of events"):
        parse(calendar_payload(event_count=0))
    with pytest.raises(OefbIcalIntegrityError, match="number of events"):
        parse(calendar_payload(event_count=MAX_EVENT_COUNT + 1))


def test_parser_rejects_unsupported_calendar_component() -> None:
    payload = calendar_payload().replace(
        b"END:VCALENDAR",
        b"BEGIN:VTODO\r\nUID:todo\r\nEND:VTODO\r\nEND:VCALENDAR",
    )

    with pytest.raises(OefbIcalSchemaError, match="unsupported components"):
        parse(payload)
