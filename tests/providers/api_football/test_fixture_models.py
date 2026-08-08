from copy import deepcopy
from datetime import UTC, datetime

import pytest
from app.providers.api_football.exceptions import (
    ProviderIntegrityError,
    ProviderResponseSchemaError,
    UnsupportedProviderValueError,
)
from app.providers.api_football.fixture_models import (
    ProviderFixtureStatus,
    parse_fixture,
)

from tests.providers.api_football.catalog_test_support import load_envelope


def fixture_payload(index: int = 0) -> dict[str, object]:
    return deepcopy(load_envelope("premier_league_fixtures.json")["response"][index])


def test_parse_fixture_returns_typed_utc_fixture() -> None:
    fixture = parse_fixture(fixture_payload())

    assert fixture.external_id == "900001"
    assert fixture.competition_id == 39
    assert fixture.season_year == 2026
    assert fixture.kickoff_utc == datetime(2026, 8, 21, 14, tzinfo=UTC)
    assert fixture.kickoff_confirmed is True
    assert fixture.status is ProviderFixtureStatus.SCHEDULED
    assert [(item.external_id, item.role) for item in fixture.participants] == [
        ("42", "home"),
        ("66", "away"),
    ]
    assert fixture.stage == "Regular Season"
    assert fixture.sequence_number == 1


def test_tbd_fixture_does_not_fabricate_midnight_kickoff() -> None:
    fixture = parse_fixture(fixture_payload(1))

    assert fixture.provider_status_code == "TBD"
    assert fixture.kickoff_utc is None
    assert fixture.kickoff_confirmed is False


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("TBD", ProviderFixtureStatus.SCHEDULED),
        ("NS", ProviderFixtureStatus.SCHEDULED),
        ("1H", ProviderFixtureStatus.LIVE),
        ("HT", ProviderFixtureStatus.LIVE),
        ("2H", ProviderFixtureStatus.LIVE),
        ("ET", ProviderFixtureStatus.LIVE),
        ("BT", ProviderFixtureStatus.LIVE),
        ("P", ProviderFixtureStatus.LIVE),
        ("INT", ProviderFixtureStatus.LIVE),
        ("LIVE", ProviderFixtureStatus.LIVE),
        ("FT", ProviderFixtureStatus.FINISHED),
        ("AET", ProviderFixtureStatus.FINISHED),
        ("PEN", ProviderFixtureStatus.FINISHED),
        ("PST", ProviderFixtureStatus.POSTPONED),
        ("CANC", ProviderFixtureStatus.CANCELLED),
        ("SUSP", ProviderFixtureStatus.SUSPENDED),
        ("ABD", ProviderFixtureStatus.ABANDONED),
        ("AWD", ProviderFixtureStatus.NOT_PLAYED),
        ("WO", ProviderFixtureStatus.NOT_PLAYED),
    ],
)
def test_fixture_status_mapping_is_explicit(
    code: str,
    expected: ProviderFixtureStatus,
) -> None:
    payload = fixture_payload()
    payload["fixture"]["status"]["short"] = code  # type: ignore[index]

    assert parse_fixture(payload).status is expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "path",
    [
        ("fixture", "id"),
        ("league", "id"),
        ("league", "season"),
        ("teams", "home", "id"),
        ("teams", "away", "id"),
    ],
)
def test_fixture_rejects_missing_stable_identifiers(path: tuple[str, ...]) -> None:
    payload = fixture_payload()
    target = payload
    for part in path[:-1]:
        target = target[part]  # type: ignore[assignment,index]
    del target[path[-1]]  # type: ignore[arg-type]

    with pytest.raises(ProviderResponseSchemaError):
        parse_fixture(payload)  # type: ignore[arg-type]


def test_fixture_rejects_unknown_status() -> None:
    payload = fixture_payload()
    payload["fixture"]["status"]["short"] = "UNKNOWN"  # type: ignore[index]

    with pytest.raises(UnsupportedProviderValueError, match="UNKNOWN"):
        parse_fixture(payload)  # type: ignore[arg-type]


def test_fixture_rejects_naive_kickoff() -> None:
    payload = fixture_payload()
    payload["fixture"]["timestamp"] = None  # type: ignore[index]
    payload["fixture"]["date"] = "2026-08-21T14:00:00"  # type: ignore[index]

    with pytest.raises(ProviderResponseSchemaError, match="explicit timezone"):
        parse_fixture(payload)  # type: ignore[arg-type]


def test_fixture_normalizes_equivalent_offset_to_utc() -> None:
    payload = fixture_payload()
    payload["fixture"]["date"] = "2026-08-21T16:00:00+02:00"  # type: ignore[index]

    fixture = parse_fixture(payload)  # type: ignore[arg-type]

    assert fixture.kickoff_utc == datetime(2026, 8, 21, 14, tzinfo=UTC)


def test_fixture_normalizes_allowlisted_optional_fields() -> None:
    fixture = parse_fixture(fixture_payload())

    assert fixture.venue_name == "Emirates Stadium"
    assert fixture.venue_city == "London"
    assert fixture.source_updated_at == datetime(2026, 8, 8, 12, tzinfo=UTC)


def test_fixture_rejects_naive_provider_update_timestamp() -> None:
    payload = fixture_payload()
    payload["fixture"]["updated"] = "2026-08-08T12:00:00"  # type: ignore[index]

    with pytest.raises(ProviderResponseSchemaError, match="explicit timezone"):
        parse_fixture(payload)  # type: ignore[arg-type]


def test_fixture_rejects_conflicting_date_and_timestamp() -> None:
    payload = fixture_payload()
    payload["fixture"]["date"] = "2026-08-21T15:00:00+00:00"  # type: ignore[index]

    with pytest.raises(ProviderIntegrityError, match="different instants"):
        parse_fixture(payload)  # type: ignore[arg-type]


def test_fixture_rejects_same_home_and_away_team() -> None:
    payload = fixture_payload()
    payload["teams"]["away"]["id"] = 42  # type: ignore[index]

    with pytest.raises(ProviderIntegrityError, match="must be distinct"):
        parse_fixture(payload)  # type: ignore[arg-type]
