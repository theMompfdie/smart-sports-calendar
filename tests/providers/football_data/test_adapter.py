from collections.abc import Mapping
from dataclasses import dataclass

from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.adapter import (
    FootballDataCompetitionAdapter,
    FootballDataPremierLeagueAdapter,
)
from app.providers.football_data.client import FootballDataResponse
from app.providers.football_data.profiles import BUNDESLIGA_PROFILE

from tests.providers.football_data.support import FETCHED_AT, payloads


@dataclass(frozen=True)
class Request:
    endpoint: str
    query: Mapping[str, str | int] | None


class StubClient:
    def __init__(self, payloads: tuple[dict, dict, dict]) -> None:
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
