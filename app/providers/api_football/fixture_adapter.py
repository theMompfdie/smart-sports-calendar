from typing import Protocol

from app.providers.api_football.catalog_adapter import PREMIER_LEAGUE_ID
from app.providers.api_football.exceptions import ProviderIntegrityError
from app.providers.api_football.fixture_models import ApiFootballFixture, parse_fixture
from app.providers.api_football.models import ApiFootballCollection


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

        return tuple(sorted(fixtures, key=lambda fixture: fixture.id))
