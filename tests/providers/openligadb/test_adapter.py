from app.providers.openligadb.adapter import OpenLigaDBCompetitionAdapter
from app.providers.openligadb.client import OpenLigaDBResponse
from app.providers.openligadb.profiles import DFB_POKAL_PROFILE

from tests.providers.openligadb.support import FETCHED_AT, payloads


class StubClient:
    def __init__(self) -> None:
        self._responses = [
            OpenLigaDBResponse(payload, FETCHED_AT, 1) for payload in payloads()
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
