import json
from datetime import UTC, datetime

import pytest
from app.operations.oefb_ical_catalog_candidates import (
    OefbIcalCatalogCandidateError,
    observe_oefb_ical_catalog,
    render_catalog_candidates,
)
from app.providers.oefb_ical.models import parse_snapshot

from tests.providers.oefb_ical.support import LAST_MODIFIED, calendar_payload

OBSERVED_AT = datetime(2026, 8, 28, 14, 0, tzinfo=UTC)


def snapshot(*, event_count: int = 32, payload: bytes | None = None):
    return parse_snapshot(
        payload or calendar_payload(event_count=event_count),
        fetched_at_utc=OBSERVED_AT,
        request_attempts=1,
        last_modified=LAST_MODIFIED,
    )


def test_catalog_observation_outputs_64_consistent_candidates() -> None:
    evidence = observe_oefb_ical_catalog(snapshot())
    rendered = render_catalog_candidates(evidence)
    parsed = json.loads(rendered)

    assert evidence.competition_key == "oefb_cup"
    assert evidence.provider_competition_id == 232362
    assert evidence.current_event_count == 32
    assert evidence.participant_count == 64
    assert evidence.participants[0].provider_id == 2000
    assert evidence.participants[0].provider_name == "Home 0"
    assert evidence.participants[-1].provider_id == 2063
    assert parsed["season_key"] == "2026_27"
    assert "opaque-test-token" not in rendered
    assert "1000000" not in rendered
    assert LAST_MODIFIED not in rendered


def test_catalog_observation_excludes_historical_events() -> None:
    historical = (
        calendar_payload()
        .replace(
            b"DTSTART:20260828T180000Z",
            b"DTSTART:20250828T180000Z",
        )
        .replace(b"UID:1000000", b"UID:1999999")
    )
    current = calendar_payload(event_count=32)
    events = current.split(b"BEGIN:VEVENT", 1)[1].split(b"END:VCALENDAR", 1)[0]
    payload = historical.replace(b"END:VCALENDAR\r\n", b"")
    payload += b"BEGIN:VEVENT" + events + b"END:VCALENDAR\r\n"

    evidence = observe_oefb_ical_catalog(snapshot(payload=payload))

    assert evidence.current_event_count == 32
    assert evidence.participant_count == 64


def test_catalog_observation_rejects_incomplete_participant_set() -> None:
    with pytest.raises(OefbIcalCatalogCandidateError, match="exactly 64"):
        observe_oefb_ical_catalog(snapshot(event_count=31))


def test_catalog_observation_rejects_ambiguous_summary() -> None:
    payload = calendar_payload(event_count=32).replace(
        b"SUMMARY:Home 0 : Away 0",
        b"SUMMARY:Home 0 vs Away 0",
    )

    with pytest.raises(OefbIcalCatalogCandidateError, match="unambiguous"):
        observe_oefb_ical_catalog(snapshot(payload=payload))


def test_catalog_observation_rejects_name_change_for_stable_id() -> None:
    payload = calendar_payload(event_count=32).replace(
        b"X-HOMENR:2002",
        b"X-HOMENR:2000",
    )

    with pytest.raises(OefbIcalCatalogCandidateError, match="inconsistent names"):
        observe_oefb_ical_catalog(snapshot(payload=payload))


def test_catalog_observation_rejects_same_name_for_different_ids() -> None:
    payload = calendar_payload(event_count=32).replace(
        b"SUMMARY:Home 1 : Away 1",
        b"SUMMARY:Home 0 : Away 1",
    )

    with pytest.raises(OefbIcalCatalogCandidateError, match="inconsistent identities"):
        observe_oefb_ical_catalog(snapshot(payload=payload))


def test_catalog_observation_preserves_hyphens_inside_team_names() -> None:
    payload = calendar_payload(event_count=32).replace(
        b"SUMMARY:Home 0 : Away 0",
        b"SUMMARY:Home - United : Away 0",
    )

    evidence = observe_oefb_ical_catalog(snapshot(payload=payload))

    assert evidence.participants[0].provider_name == "Home - United"
