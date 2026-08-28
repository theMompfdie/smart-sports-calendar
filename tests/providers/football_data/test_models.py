from copy import deepcopy
from datetime import timedelta

import pytest
from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.exceptions import (
    FootballDataError,
    FootballDataIntegrityError,
    FootballDataSchemaError,
)
from app.providers.football_data.models import parse_snapshot
from app.providers.football_data.profiles import (
    BUNDESLIGA_PROFILE,
    CHAMPIONSHIP_PROFILE,
    PREMIER_LEAGUE_PROFILE,
    FootballDataCompetitionProfile,
)
from app.providers.football_data.team_mappings import resolve_team_key

from tests.providers.football_data.support import FETCHED_AT, payloads, snapshot


def parse(
    competition,
    teams,
    matches,
    *,
    profile: FootballDataCompetitionProfile = PREMIER_LEAGUE_PROFILE,
    fetched_at=FETCHED_AT,
):
    return parse_snapshot(
        competition,
        teams,
        matches,
        profile=profile,
        expected_season_year=2026,
        fetched_at_utc=fetched_at,
        request_attempts=3,
        rate_limits=RateLimitSnapshot(None, None, 10, None, None),
    )


def test_complete_snapshot_is_sorted_and_typed() -> None:
    result = snapshot()

    assert result.competition_id == 2021
    assert result.season_id == 2502
    assert len(result.teams) == 20
    assert len(result.matches) == 380
    assert result.matches[0].status == "scheduled"
    assert result.matches[0].kickoff_utc.tzinfo is not None


def test_bundesliga_profile_parses_exact_complete_scope() -> None:
    result = snapshot(BUNDESLIGA_PROFILE)

    assert result.competition_id == 2002
    assert result.competition_code == "BL1"
    assert result.season_id == 2522
    assert len(result.teams) == 18
    assert len(result.matches) == 306
    assert {match.matchday for match in result.matches} == set(range(1, 35))


def test_championship_profile_parses_exact_regular_season_scope() -> None:
    result = snapshot(CHAMPIONSHIP_PROFILE)

    assert result.competition_id == 2016
    assert result.competition_code == "ELC"
    assert result.season_id == 2509
    assert len(result.teams) == 24
    assert len(result.matches) == 552
    assert {match.stage for match in result.matches} == {"REGULAR_SEASON"}
    assert {match.matchday for match in result.matches} == set(range(1, 47))


@pytest.mark.parametrize(
    ("provider_name", "expected"),
    [
        ("Arsenal FC", "arsenal"),
        ("Arsenal", "arsenal"),
        ("AFC Bournemouth", "bournemouth"),
        ("Hull City AFC", "hull_city"),
    ],
)
def test_reviewed_team_name_variants_resolve_deterministically(
    provider_name: str, expected: str
) -> None:
    assert resolve_team_key("premier_league", provider_name) == expected


@pytest.mark.parametrize(
    "declared,actual", [(379, 380), (380, 379), (381, 380), (0, 0)]
)
def test_incomplete_or_empty_snapshot_fails_closed(declared: int, actual: int) -> None:
    competition, teams, matches = payloads()
    matches["resultSet"]["count"] = declared
    matches["matches"] = matches["matches"][:actual]

    with pytest.raises(FootballDataError):
        parse(competition, teams, matches)


def test_duplicate_identity_and_pairing_fail_closed() -> None:
    competition, teams, matches = payloads()
    matches["matches"][1]["id"] = matches["matches"][0]["id"]

    with pytest.raises(FootballDataIntegrityError):
        parse(competition, teams, matches)

    competition, teams, matches = payloads()
    matches["matches"][1]["homeTeam"] = deepcopy(matches["matches"][0]["homeTeam"])
    matches["matches"][1]["awayTeam"] = deepcopy(matches["matches"][0]["awayTeam"])
    with pytest.raises(FootballDataIntegrityError):
        parse(competition, teams, matches)


def test_wrong_scope_unknown_status_and_non_utc_timestamp_fail_closed() -> None:
    competition, teams, matches = payloads()
    matches["matches"][0]["competition"]["id"] = 999
    with pytest.raises(FootballDataIntegrityError):
        parse(competition, teams, matches)

    competition, teams, matches = payloads()
    matches["matches"][0]["status"] = "UNKNOWN"
    with pytest.raises(FootballDataSchemaError):
        parse(competition, teams, matches)

    competition, teams, matches = payloads()
    matches["matches"][0]["utcDate"] = "2026-08-21T19:00:00"
    with pytest.raises(FootballDataSchemaError):
        parse(competition, teams, matches)


@pytest.mark.parametrize(
    ("provider_status", "canonical_status"),
    [
        ("SCHEDULED", "scheduled"),
        ("TIMED", "scheduled"),
        ("IN_PLAY", "live"),
        ("PAUSED", "live"),
        ("EXTRA_TIME", "live"),
        ("PENALTY_SHOOTOUT", "live"),
        ("FINISHED", "finished"),
        ("SUSPENDED", "suspended"),
        ("POSTPONED", "postponed"),
        ("CANCELLED", "cancelled"),
        ("AWARDED", "finished"),
    ],
)
def test_documented_lifecycle_statuses_map_explicitly(
    provider_status: str, canonical_status: str
) -> None:
    competition, teams, matches = payloads()
    matches["matches"][0]["status"] = provider_status

    result = parse(competition, teams, matches)

    assert result.matches[0].status == canonical_status


def test_stale_and_future_updated_snapshots_fail_closed() -> None:
    competition, teams, matches = payloads()
    with pytest.raises(FootballDataIntegrityError, match="stale"):
        parse(competition, teams, matches, fetched_at=FETCHED_AT + timedelta(days=70))

    competition, teams, matches = payloads()
    future = FETCHED_AT + timedelta(days=1)
    for match in matches["matches"]:
        match["lastUpdated"] = future.isoformat().replace("+00:00", "Z")
    with pytest.raises(FootballDataIntegrityError, match="future"):
        parse(competition, teams, matches)
