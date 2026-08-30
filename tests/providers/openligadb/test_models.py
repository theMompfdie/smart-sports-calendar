from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest
from app.providers.openligadb.exceptions import (
    OpenLigaDBIntegrityError,
    OpenLigaDBSchemaError,
)
from app.providers.openligadb.models import parse_snapshot
from app.providers.openligadb.profiles import (
    DFB_POKAL_PROFILE,
    NATIONS_LEAGUE_A_PROFILE,
    SECOND_BUNDESLIGA_PROFILE,
)

from tests.providers.openligadb.support import (
    FETCHED_AT,
    nations_league_a_payloads,
    payloads,
    second_bundesliga_payloads,
)


def parse(leagues, groups, matches, *, fetched_at=FETCHED_AT):
    return parse_snapshot(
        leagues,
        groups,
        matches,
        profile=DFB_POKAL_PROFILE,
        fetched_at_utc=fetched_at,
        request_attempts=3,
    )


def test_partial_snapshot_is_sorted_typed_and_excludes_logo_data() -> None:
    result = parse(*payloads())

    assert result.league_id == 4945
    assert result.league_season == 2026
    assert len(result.teams) == 2
    assert result.matches[0].round_name == "round-1"
    assert result.matches[0].status == "scheduled"
    assert result.matches[0].kickoff_utc.tzinfo is not None
    assert not hasattr(result.teams[0], "team_icon_url")


def test_empty_duplicate_and_wrong_scope_snapshots_fail_closed() -> None:
    leagues, groups, matches = payloads()
    with pytest.raises(OpenLigaDBIntegrityError, match="no configured"):
        parse(leagues, groups, [])

    leagues, groups, matches = payloads()
    matches.append(deepcopy(matches[0]))
    with pytest.raises(OpenLigaDBIntegrityError, match="duplicate match"):
        parse(leagues, groups, matches)

    leagues, groups, matches = payloads()
    matches[0]["leagueId"] = 999
    with pytest.raises(OpenLigaDBIntegrityError, match="wrong competition"):
        parse(leagues, groups, matches)


def test_round_identity_timezone_and_provider_types_fail_closed() -> None:
    leagues, groups, matches = payloads()
    matches[0]["group"]["groupID"] = 999
    with pytest.raises(OpenLigaDBIntegrityError, match="round identity"):
        parse(leagues, groups, matches)

    leagues, groups, matches = payloads()
    matches[0]["timeZoneID"] = "UTC"
    with pytest.raises(OpenLigaDBIntegrityError, match="timezone"):
        parse(leagues, groups, matches)

    leagues, groups, matches = payloads()
    matches[0]["matchIsFinished"] = 0
    with pytest.raises(OpenLigaDBSchemaError, match="boolean"):
        parse(leagues, groups, matches)


def test_finished_status_and_future_source_update_are_explicit() -> None:
    leagues, groups, matches = payloads()
    matches[0]["matchIsFinished"] = True
    assert parse(leagues, groups, matches).matches[0].status == "finished"

    leagues, groups, matches = payloads()
    future_local = (FETCHED_AT + timedelta(days=1)).replace(tzinfo=None)
    matches[0]["lastUpdateDateTime"] = future_local.isoformat()
    with pytest.raises(OpenLigaDBIntegrityError, match="future"):
        parse(leagues, groups, matches)


def test_second_bundesliga_complete_snapshot_and_timezone_exception() -> None:
    leagues, groups, matches = second_bundesliga_payloads()

    result = parse_snapshot(
        leagues,
        groups,
        matches,
        profile=SECOND_BUNDESLIGA_PROFILE,
        fetched_at_utc=FETCHED_AT,
        request_attempts=3,
    )

    assert len(result.matches) == 306
    assert len(result.teams) == 18
    assert result.matches[0].round_name == "matchday-1"


def test_second_bundesliga_incomplete_or_duplicate_pairing_fails_closed() -> None:
    leagues, groups, matches = second_bundesliga_payloads()
    with pytest.raises(OpenLigaDBIntegrityError, match="exactly 306"):
        parse_snapshot(
            leagues,
            groups,
            matches[:-1],
            profile=SECOND_BUNDESLIGA_PROFILE,
            fetched_at_utc=FETCHED_AT,
            request_attempts=3,
        )

    leagues, groups, matches = second_bundesliga_payloads()
    matches[-1]["team1"] = deepcopy(matches[0]["team1"])
    matches[-1]["team2"] = deepcopy(matches[0]["team2"])
    with pytest.raises(OpenLigaDBIntegrityError, match="directed pairing"):
        parse_snapshot(
            leagues,
            groups,
            matches,
            profile=SECOND_BUNDESLIGA_PROFILE,
            fetched_at_utc=FETCHED_AT,
            request_attempts=3,
        )


def test_nations_league_a_snapshot_is_exact_and_excludes_later_groups() -> None:
    leagues, groups, matches = nations_league_a_payloads(
        include_later_stage_fixture=True
    )

    result = parse_snapshot(
        leagues,
        groups,
        matches,
        profile=NATIONS_LEAGUE_A_PROFILE,
        fetched_at_utc=FETCHED_AT,
        request_attempts=3,
    )

    assert len(result.matches) == 48
    assert len(result.teams) == 16
    assert {match.group_order_id for match in result.matches} == {1, 2, 3, 4}
    assert {match.round_name for match in result.matches} == {
        "group-a-1",
        "group-a-2",
        "group-a-3",
        "group-a-4",
    }


def test_nations_league_a_incomplete_or_cross_group_snapshot_fails_closed() -> None:
    leagues, groups, matches = nations_league_a_payloads()
    with pytest.raises(OpenLigaDBIntegrityError, match="exactly 48"):
        parse_snapshot(
            leagues,
            groups,
            matches[:-1],
            profile=NATIONS_LEAGUE_A_PROFILE,
            fetched_at_utc=FETCHED_AT,
            request_attempts=3,
        )

    leagues, groups, matches = nations_league_a_payloads()
    matches[12]["team1"] = deepcopy(matches[0]["team1"])
    with pytest.raises(OpenLigaDBIntegrityError):
        parse_snapshot(
            leagues,
            groups,
            matches,
            profile=NATIONS_LEAGUE_A_PROFILE,
            fetched_at_utc=FETCHED_AT,
            request_attempts=3,
        )


def test_openligadb_profile_rejects_unsafe_lifecycle_combinations() -> None:
    with pytest.raises(ValueError, match="stage kind"):
        replace(NATIONS_LEAGUE_A_PROFILE, stage_kind=None)

    with pytest.raises(ValueError, match="two round-robin modes"):
        replace(
            NATIONS_LEAGUE_A_PROFILE,
            require_complete_double_round_robin=True,
        )

    with pytest.raises(ValueError, match="fixture and participant counts"):
        replace(
            NATIONS_LEAGUE_A_PROFILE,
            expected_fixture_count=None,
        )


@pytest.mark.parametrize("missing_timezone", [None, ""])
def test_dfb_pokal_accepts_missing_timezone_with_explicit_utc_kickoff(
    missing_timezone: object,
) -> None:
    leagues, groups, matches = payloads()
    matches[0]["timeZoneID"] = missing_timezone

    result = parse(leagues, groups, matches)

    assert result.matches[0].kickoff_utc.isoformat() == "2026-08-21T18:00:00+00:00"


def test_dfb_pokal_missing_timezone_still_requires_explicit_utc_kickoff() -> None:
    leagues, groups, matches = payloads()
    matches[0]["timeZoneID"] = None
    matches[0]["matchDateTimeUTC"] = "2026-08-21T16:00:00"

    with pytest.raises(OpenLigaDBSchemaError, match="must be UTC"):
        parse(leagues, groups, matches)


@pytest.mark.parametrize(
    "invalid_timezone",
    ["UTC", " W. Europe Standard Time", 42],
)
def test_dfb_pokal_rejects_unexpected_or_malformed_timezone(
    invalid_timezone: object,
) -> None:
    leagues, groups, matches = payloads()
    matches[0]["timeZoneID"] = invalid_timezone

    with pytest.raises((OpenLigaDBIntegrityError, OpenLigaDBSchemaError)):
        parse(leagues, groups, matches)
