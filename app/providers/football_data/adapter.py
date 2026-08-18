from collections.abc import Mapping
from typing import Protocol

from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.client import FootballDataClient, FootballDataResponse
from app.providers.football_data.models import FootballDataSnapshot, parse_snapshot
from app.providers.football_data.profiles import (
    PREMIER_LEAGUE_PROFILE,
    FootballDataCompetitionProfile,
)


class FootballDataClientProtocol(Protocol):
    def get(
        self,
        endpoint: str,
        query: Mapping[str, str | int] | None = None,
    ) -> FootballDataResponse: ...


class FootballDataSnapshotAdapter(Protocol):
    profile: FootballDataCompetitionProfile

    def fetch_snapshot(self, season_year: int) -> FootballDataSnapshot: ...


class FootballDataCompetitionAdapter:
    def __init__(
        self,
        client: FootballDataClientProtocol,
        profile: FootballDataCompetitionProfile,
    ) -> None:
        self._client = client
        self.profile = profile

    def fetch_snapshot(self, season_year: int) -> FootballDataSnapshot:
        code = self.profile.external_code
        competition = self._client.get(f"/v4/competitions/{code}")
        teams = self._client.get(
            f"/v4/competitions/{code}/teams", query={"season": season_year}
        )
        matches = self._client.get(
            f"/v4/competitions/{code}/matches",
            query={"limit": 500, "season": season_year},
        )
        remaining = tuple(
            value
            for response in (competition, teams, matches)
            if (value := response.rate_limits.daily_remaining) is not None
        )
        return parse_snapshot(
            competition.payload,
            teams.payload,
            matches.payload,
            profile=self.profile,
            expected_season_year=season_year,
            fetched_at_utc=max(
                response.fetched_at_utc for response in (competition, teams, matches)
            ),
            request_attempts=sum(
                response.attempt_count for response in (competition, teams, matches)
            ),
            rate_limits=RateLimitSnapshot(
                daily_limit=None,
                daily_remaining=min(remaining) if remaining else None,
                minute_limit=matches.rate_limits.minute_limit,
                minute_remaining=None,
                retry_after_seconds=matches.rate_limits.retry_after_seconds,
            ),
        )


class FootballDataPremierLeagueAdapter(FootballDataCompetitionAdapter):
    def __init__(self, client: FootballDataClient) -> None:
        super().__init__(client, PREMIER_LEAGUE_PROFILE)
