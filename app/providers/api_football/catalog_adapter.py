from typing import Protocol

from app.providers.api_football.catalog_models import (
    ApiFootballLeague,
    ApiFootballSeason,
    ApiFootballTeam,
    parse_league,
    parse_team,
)
from app.providers.api_football.exceptions import (
    ProviderIntegrityError,
    ProviderResolutionError,
)
from app.providers.api_football.models import ApiFootballCollection

PREMIER_LEAGUE_ID = 39


class ApiFootballCollectionClient(Protocol):
    def get_all(
        self,
        endpoint: str,
        query: dict[str, str | int] | None = None,
    ) -> ApiFootballCollection: ...


class ApiFootballCatalogAdapter:
    def __init__(self, client: ApiFootballCollectionClient) -> None:
        self._client = client

    def find_premier_league(self) -> ApiFootballLeague:
        collection = self._client.get_all(
            "/leagues",
            query={"id": PREMIER_LEAGUE_ID},
        )
        matches = tuple(
            league
            for league in (parse_league(item) for item in collection.items)
            if league.id == PREMIER_LEAGUE_ID
        )

        if len(matches) != 1:
            raise ProviderResolutionError(
                "API-Football Premier League lookup must return exactly one match; "
                f"received {len(matches)}."
            )

        return matches[0]

    def find_current_season(
        self,
        league: ApiFootballLeague,
    ) -> ApiFootballSeason:
        matches = tuple(season for season in league.seasons if season.is_current)

        if len(matches) != 1:
            raise ProviderResolutionError(
                "API-Football Premier League must expose exactly one current season; "
                f"received {len(matches)}."
            )

        return matches[0]

    def fetch_teams(
        self,
        league_id: int,
        season_year: int,
    ) -> tuple[ApiFootballTeam, ...]:
        collection = self._client.get_all(
            "/teams",
            query={
                "league": league_id,
                "season": season_year,
            },
        )
        teams = tuple(parse_team(item) for item in collection.items)

        if not teams:
            raise ProviderResolutionError(
                "API-Football Premier League team lookup returned no teams."
            )

        external_ids = [team.external_id for team in teams]
        if len(external_ids) != len(set(external_ids)):
            raise ProviderIntegrityError(
                "API-Football Premier League team response contains duplicate IDs."
            )

        return teams
