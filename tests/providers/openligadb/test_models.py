from copy import deepcopy
from datetime import timedelta

import pytest
from app.providers.openligadb.exceptions import (
    OpenLigaDBIntegrityError,
    OpenLigaDBSchemaError,
)
from app.providers.openligadb.models import parse_snapshot
from app.providers.openligadb.profiles import (
    DFB_POKAL_PROFILE,
    SECOND_BUNDESLIGA_PROFILE,
)

from tests.providers.openligadb.support import (
    FETCHED_AT,
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


def test_missing_timezone_remains_rejected_for_dfb_pokal() -> None:
    leagues, groups, matches = payloads()
    matches[0]["timeZoneID"] = ""

    with pytest.raises(OpenLigaDBIntegrityError, match="no permitted"):
        parse(leagues, groups, matches)
