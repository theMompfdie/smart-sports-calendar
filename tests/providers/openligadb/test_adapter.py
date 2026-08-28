from app.providers.openligadb.adapter import OpenLigaDBCompetitionAdapter
from app.providers.openligadb.client import OpenLigaDBResponse
from app.providers.openligadb.profiles import (
    DFB_POKAL_PROFILE,
    SECOND_BUNDESLIGA_PROFILE,
)

from tests.providers.openligadb.support import (
    FETCHED_AT,
    payloads,
    second_bundesliga_payloads,
)


class StubClient:
    def __init__(self, provider_payloads=None) -> None:
        active_payloads = payloads() if provider_payloads is None else provider_payloads
        self._responses = [
            OpenLigaDBResponse(payload, FETCHED_AT, 1) for payload in active_payloads
        ]
        self.requests: list[str] = []

    def get(self, endpoint: str) -> OpenLigaDBResponse:
        self.requests.append(endpoint)
        return self._responses.pop(0)


def test_adapter_fetches_the_reviewed_dfb_pokal_scope() -> None:
    client = StubClient()
    adapter = OpenLigaDBCompetitionAdapter(client, DFB_POKAL_PROFILE)

    snapshot = adapter.fetch_snapshot()

    assert snapshot.league_id == 4945
    assert snapshot.request_attempts == 3
    assert client.requests == [
        "/getavailableleagues/2026",
        "/getavailablegroups/dfb/2026",
        "/getmatchdata/dfb/2026",
    ]


def test_adapter_fetches_the_reviewed_second_bundesliga_scope() -> None:
    client = StubClient(second_bundesliga_payloads())
    adapter = OpenLigaDBCompetitionAdapter(client, SECOND_BUNDESLIGA_PROFILE)

    snapshot = adapter.fetch_snapshot()

    assert snapshot.league_id == 4938
    assert len(snapshot.matches) == 306
    assert client.requests == [
        "/getavailableleagues/2026",
        "/getavailablegroups/bl2/2026",
        "/getmatchdata/bl2/2026",
    ]
