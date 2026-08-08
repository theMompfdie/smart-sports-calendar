from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.providers.api_football.catalog_adapter import PREMIER_LEAGUE_ID
from app.providers.api_football.exceptions import ProviderIntegrityError
from app.providers.api_football.fixture_models import ApiFootballFixture, parse_fixture
from app.providers.api_football.models import ApiFootballCollection, RateLimitSnapshot


@dataclass(frozen=True)
class ApiFootballFixtureBatch:
    fixtures: tuple[ApiFootballFixture, ...]
    page_count: int
    fetched_at_utc: datetime
    rate_limits: RateLimitSnapshot
    request_attempts: int


class ApiFootballFixtureCollectionClient(Protocol):
    def get_all(
        self,
        endpoint: str,
        query: dict[str, str | int] | None = None,
    ) -> ApiFootballCollection: ...


class ApiFootballFixtureAdapter:
    def __init__(self, client: ApiFootballFixtureCollectionClient) -> None:
        self._client = client

    def fetch_premier_league_fixtures(
        self,
        season_year: int,
    ) -> tuple[ApiFootballFixture, ...]:
        return self.fetch_premier_league_fixture_batch(season_year).fixtures

    def fetch_premier_league_fixture_batch(
        self,
        season_year: int,
    ) -> ApiFootballFixtureBatch:
        collection = self._client.get_all(
            "/fixtures",
            query={
                "league": PREMIER_LEAGUE_ID,
                "season": season_year,
            },
        )
        fixtures = tuple(parse_fixture(item) for item in collection.items)

        for fixture in fixtures:
            if (
                fixture.competition_id != PREMIER_LEAGUE_ID
                or fixture.season_year != season_year
            ):
                raise ProviderIntegrityError(
                    "API-Football fixture does not match the requested Premier "
                    f"League season scope: fixture_id={fixture.external_id}."
                )

        external_ids = [fixture.external_id for fixture in fixtures]
        if len(external_ids) != len(set(external_ids)):
            raise ProviderIntegrityError(
                "API-Football fixture collection contains duplicate fixture IDs."
            )

        return ApiFootballFixtureBatch(
            fixtures=tuple(sorted(fixtures, key=lambda fixture: fixture.id)),
            page_count=collection.page_count,
            fetched_at_utc=collection.fetched_at_utc,
            rate_limits=collection.rate_limits,
            request_attempts=collection.request_attempts,
        )
