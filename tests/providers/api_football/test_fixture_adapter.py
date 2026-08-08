import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass

import pytest
from app.config.settings import ApiFootballSettings
from app.providers.api_football.client import ApiFootballClient
from app.providers.api_football.exceptions import ProviderIntegrityError
from app.providers.api_football.fixture_adapter import ApiFootballFixtureAdapter
from app.providers.api_football.models import ApiFootballCollection
from app.providers.api_football.transport import HttpResponse

from tests.providers.api_football.catalog_test_support import (
    create_collection,
    load_envelope,
)


class StubCollectionClient:
    def __init__(self, collection: ApiFootballCollection) -> None:
        self.collection = collection
        self.requests: list[tuple[str, dict[str, str | int] | None]] = []

    def get_all(
        self,
        endpoint: str,
        query: dict[str, str | int] | None = None,
    ) -> ApiFootballCollection:
        self.requests.append((endpoint, query))
        return self.collection


@dataclass(frozen=True)
class RecordedRequest:
    url: str


class PageTransport:
    def __init__(self, *responses: HttpResponse) -> None:
        self.responses = list(responses)
        self.requests: list[RecordedRequest] = []

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        self.requests.append(RecordedRequest(url=url))
        return self.responses.pop(0)


def fixture_items() -> list[dict[str, object]]:
    return deepcopy(load_envelope("premier_league_fixtures.json")["response"])


def test_adapter_fetches_complete_deterministically_ordered_scope() -> None:
    items = list(reversed(fixture_items()))
    client = StubCollectionClient(create_collection(items))  # type: ignore[arg-type]

    fixtures = ApiFootballFixtureAdapter(client).fetch_premier_league_fixtures(2026)

    assert len(fixtures) == 10
    assert [fixture.id for fixture in fixtures] == sorted(
        fixture.id for fixture in fixtures
    )
    assert client.requests == [("/fixtures", {"league": 39, "season": 2026})]


def test_adapter_retrieves_all_fixture_pages_through_client() -> None:
    items = fixture_items()

    def response(page: int, page_items: list[dict[str, object]]) -> HttpResponse:
        return HttpResponse(
            status=200,
            headers={},
            body=json.dumps(
                {
                    "errors": [],
                    "results": len(page_items),
                    "paging": {"current": page, "total": 2},
                    "response": page_items,
                }
            ).encode(),
        )

    transport = PageTransport(response(1, items[:5]), response(2, items[5:]))
    client = ApiFootballClient(
        settings=ApiFootballSettings(enabled=True, api_key="provider-secret"),
        transport=transport,
        sleep=lambda _delay: None,
    )

    fixtures = ApiFootballFixtureAdapter(client).fetch_premier_league_fixtures(2026)

    assert len(fixtures) == 10
    assert len(transport.requests) == 2
    assert "page=1" in transport.requests[0].url
    assert "page=2" in transport.requests[1].url


def test_adapter_rejects_fixture_outside_requested_scope() -> None:
    items = fixture_items()
    items[0]["league"]["id"] = 40  # type: ignore[index]
    adapter = ApiFootballFixtureAdapter(
        StubCollectionClient(create_collection(items))  # type: ignore[arg-type]
    )

    with pytest.raises(ProviderIntegrityError, match="season scope"):
        adapter.fetch_premier_league_fixtures(2026)


def test_adapter_rejects_duplicate_fixture_ids() -> None:
    item = fixture_items()[0]
    adapter = ApiFootballFixtureAdapter(
        StubCollectionClient(create_collection([item, item]))  # type: ignore[list-item]
    )

    with pytest.raises(ProviderIntegrityError, match="duplicate fixture IDs"):
        adapter.fetch_premier_league_fixtures(2026)
