import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import pytest
from app.config.settings import ApiFootballSettings
from app.providers.api_football.catalog_adapter import ApiFootballCatalogAdapter
from app.providers.api_football.client import ApiFootballClient
from app.providers.api_football.exceptions import (
    ProviderIntegrityError,
    ProviderResolutionError,
)
from app.providers.api_football.models import ApiFootballCollection
from app.providers.api_football.transport import HttpResponse

from tests.providers.api_football.catalog_test_support import (
    create_collection,
    load_envelope,
)


class StubCollectionClient:
    def __init__(self, *collections: ApiFootballCollection) -> None:
        self._collections = list(collections)
        self.requests: list[tuple[str, dict[str, str | int] | None]] = []

    def get_unpaginated(
        self,
        endpoint: str,
        query: dict[str, str | int] | None = None,
    ) -> ApiFootballCollection:
        self.requests.append((endpoint, query))
        return self._collections.pop(0)


@dataclass(frozen=True)
class RecordedRequest:
    url: str


class PageTransport:
    def __init__(self, *responses: HttpResponse) -> None:
        self._responses = list(responses)
        self.requests: list[RecordedRequest] = []

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        self.requests.append(RecordedRequest(url=url))
        return self._responses.pop(0)


def league_collection() -> ApiFootballCollection:
    return create_collection(load_envelope("premier_league.json")["response"])


def team_collection() -> ApiFootballCollection:
    return create_collection(load_envelope("premier_league_teams.json")["response"])


def test_adapter_resolves_exact_premier_league_and_current_season() -> None:
    client = StubCollectionClient(league_collection())
    adapter = ApiFootballCatalogAdapter(client)

    league = adapter.find_premier_league()
    season = adapter.find_current_season(league)

    assert league.id == 39
    assert season.year == 2026
    assert client.requests == [("/leagues", {"id": 39})]


@pytest.mark.parametrize(
    "items", [[], [load_envelope("premier_league.json")["response"][0]] * 2]
)
def test_adapter_rejects_zero_or_multiple_competition_matches(
    items: list[dict[str, object]],
) -> None:
    adapter = ApiFootballCatalogAdapter(StubCollectionClient(create_collection(items)))

    with pytest.raises(ProviderResolutionError, match="exactly one match"):
        adapter.find_premier_league()


@pytest.mark.parametrize("current_values", [(False, False), (True, True)])
def test_adapter_rejects_zero_or_multiple_current_seasons(
    current_values: tuple[bool, bool],
) -> None:
    item = deepcopy(load_envelope("premier_league.json")["response"][0])
    for season, current in zip(item["seasons"], current_values, strict=True):
        season["current"] = current
    adapter = ApiFootballCatalogAdapter(StubCollectionClient(create_collection([item])))

    league = adapter.find_premier_league()

    with pytest.raises(ProviderResolutionError, match="exactly one current season"):
        adapter.find_current_season(league)


def test_adapter_fetches_complete_typed_team_collection() -> None:
    client = StubCollectionClient(team_collection())
    adapter = ApiFootballCatalogAdapter(client)

    teams = adapter.fetch_teams(league_id=39, season_year=2026)

    assert len(teams) == 20
    assert teams[0].external_id == "42"
    assert client.requests == [("/teams", {"league": 39, "season": 2026})]


def test_adapter_omits_page_for_unpaginated_catalog_requests() -> None:
    league_items = load_envelope("premier_league.json")["response"]
    team_items = load_envelope("premier_league_teams.json")["response"]

    def response(items: list[dict[str, object]]) -> HttpResponse:
        return HttpResponse(
            status=200,
            headers={},
            body=json.dumps(
                {
                    "errors": [],
                    "results": len(items),
                    "paging": {"current": 1, "total": 1},
                    "response": items,
                }
            ).encode(),
        )

    transport = PageTransport(
        response(league_items),
        response(team_items),
    )
    client = ApiFootballClient(
        settings=ApiFootballSettings(enabled=True, api_key="provider-secret"),
        transport=transport,
        sleep=lambda _delay: None,
    )

    adapter = ApiFootballCatalogAdapter(client)
    league = adapter.find_premier_league()
    teams = adapter.fetch_teams(
        league_id=39,
        season_year=2026,
    )

    assert league.id == 39
    assert len(teams) == 20
    assert len(transport.requests) == 2
    assert parse_qs(urlsplit(transport.requests[0].url).query) == {"id": ["39"]}
    assert parse_qs(urlsplit(transport.requests[1].url).query) == {
        "league": ["39"],
        "season": ["2026"],
    }


def test_adapter_rejects_empty_team_collection() -> None:
    adapter = ApiFootballCatalogAdapter(StubCollectionClient(create_collection([])))

    with pytest.raises(ProviderResolutionError, match="returned no teams"):
        adapter.fetch_teams(league_id=39, season_year=2026)


def test_adapter_rejects_duplicate_team_ids() -> None:
    items = load_envelope("premier_league_teams.json")["response"]
    adapter = ApiFootballCatalogAdapter(
        StubCollectionClient(create_collection([items[0], items[0]]))
    )

    with pytest.raises(ProviderIntegrityError, match="duplicate IDs"):
        adapter.fetch_teams(league_id=39, season_year=2026)
