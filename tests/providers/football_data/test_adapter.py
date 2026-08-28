from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

import pytest
from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.adapter import (
    FootballDataCompetitionAdapter,
    FootballDataPremierLeagueAdapter,
)
from app.providers.football_data.client import FootballDataResponse
from app.providers.football_data.exceptions import FootballDataError
from app.providers.football_data.profiles import (
    BUNDESLIGA_PROFILE,
    CHAMPIONSHIP_PROFILE,
)

from tests.providers.football_data.support import FETCHED_AT, payloads


@dataclass(frozen=True)
class Request:
    endpoint: str
    query: Mapping[str, str | int] | None


class StubClient:
    def __init__(self, payloads: tuple[dict, ...]) -> None:
        self._responses = [self._response(payload) for payload in payloads]
        self.requests: list[Request] = []

    def get(
        self,
        endpoint: str,
        query: Mapping[str, str | int] | None = None,
    ) -> FootballDataResponse:
        self.requests.append(Request(endpoint, query))
        return self._responses.pop(0)

    @staticmethod
    def _response(payload: dict) -> FootballDataResponse:
        return FootballDataResponse(
            payload=payload,
            headers={"X-API-Version": "v4"},
            fetched_at_utc=FETCHED_AT,
            attempt_count=1,
            rate_limits=RateLimitSnapshot(None, 7, 10, None, None),
        )


def test_competition_adapter_uses_bundesliga_profile_scope() -> None:
    client = StubClient(payloads(BUNDESLIGA_PROFILE))
    adapter = FootballDataCompetitionAdapter(client, BUNDESLIGA_PROFILE)

    snapshot = adapter.fetch_snapshot(2026)

    assert snapshot.competition_id == 2002
    assert snapshot.season_id == 2522
    assert len(snapshot.teams) == 18
    assert len(snapshot.matches) == 306
    assert client.requests == [
        Request("/v4/competitions/BL1", None),
        Request("/v4/competitions/BL1/teams", {"season": 2026}),
        Request(
            "/v4/competitions/BL1/matches",
            {"limit": 500, "season": 2026},
        ),
    ]


def test_premier_league_adapter_preserves_existing_scope() -> None:
    client = StubClient(payloads())
    adapter = FootballDataPremierLeagueAdapter(client)

    snapshot = adapter.fetch_snapshot(2026)

    assert snapshot.competition_id == 2021
    assert snapshot.season_id == 2502
    assert len(snapshot.teams) == 20
    assert len(snapshot.matches) == 380
    assert client.requests[0] == Request("/v4/competitions/PL", None)


def test_championship_adapter_accepts_exact_complete_unpaged_response() -> None:
    competition, teams, matches = payloads(CHAMPIONSHIP_PROFILE)
    matches["filters"] = {"season": "2026", "limit": 500, "offset": 0}
    client = StubClient((competition, teams, matches))
    adapter = FootballDataCompetitionAdapter(client, CHAMPIONSHIP_PROFILE)

    snapshot = adapter.fetch_snapshot(2026)

    assert snapshot.competition_id == 2016
    assert snapshot.season_id == 2509
    assert len(snapshot.teams) == 24
    assert len(snapshot.matches) == 552
    assert snapshot.page_count == 1
    assert client.requests[-1] == Request(
        "/v4/competitions/ELC/matches",
        {"limit": 500, "season": 2026, "stage": "REGULAR_SEASON"},
    )


def test_championship_adapter_merges_documented_500_plus_52_pagination() -> None:
    competition, teams, matches = payloads(CHAMPIONSHIP_PROFILE)
    all_matches = deepcopy(matches["matches"])
    first_page = {
        "filters": {"season": 2026, "limit": 500, "offset": 0},
        "resultSet": {"count": 500},
        "matches": all_matches[:500],
    }
    second_page = {
        "filters": {"season": 2026, "limit": 500, "offset": 500},
        "resultSet": {"count": 52},
        "matches": all_matches[500:],
    }
    client = StubClient((competition, teams, first_page, second_page))
    adapter = FootballDataCompetitionAdapter(client, CHAMPIONSHIP_PROFILE)

    snapshot = adapter.fetch_snapshot(2026)

    assert len(snapshot.matches) == 552
    assert snapshot.page_count == 2
    assert snapshot.request_attempts == 4
    assert client.requests[-1] == Request(
        "/v4/competitions/ELC/matches",
        {
            "limit": 500,
            "offset": 500,
            "season": 2026,
            "stage": "REGULAR_SEASON",
        },
    )


@pytest.mark.parametrize(
    ("first_size", "second_size", "second_offset"),
    [(499, 53, 499), (500, 51, 500), (500, 52, 499)],
)
def test_championship_adapter_rejects_page_gaps_and_drift(
    first_size: int,
    second_size: int,
    second_offset: int,
) -> None:
    competition, teams, matches = payloads(CHAMPIONSHIP_PROFILE)
    all_matches = deepcopy(matches["matches"])
    first_page = {
        "filters": {"season": 2026, "limit": 500, "offset": 0},
        "resultSet": {"count": first_size},
        "matches": all_matches[:first_size],
    }
    second_page = {
        "filters": {"season": 2026, "limit": 500, "offset": second_offset},
        "resultSet": {"count": second_size},
        "matches": all_matches[500 : 500 + second_size],
    }
    client = StubClient((competition, teams, first_page, second_page))

    with pytest.raises(FootballDataError):
        FootballDataCompetitionAdapter(client, CHAMPIONSHIP_PROFILE).fetch_snapshot(
            2026
        )
