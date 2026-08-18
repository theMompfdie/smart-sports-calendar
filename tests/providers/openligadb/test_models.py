from copy import deepcopy
from datetime import timedelta

import pytest
from app.providers.openligadb.exceptions import (
    OpenLigaDBIntegrityError,
    OpenLigaDBSchemaError,
)
from app.providers.openligadb.models import parse_snapshot
from app.providers.openligadb.profiles import DFB_POKAL_PROFILE

from tests.providers.openligadb.support import FETCHED_AT, payloads


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
    with pytest.raises(OpenLigaDBIntegrityError, match="no DFB-Pokal"):
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
