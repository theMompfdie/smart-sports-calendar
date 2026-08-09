from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.client import FootballDataClient
from app.providers.football_data.models import FootballDataSnapshot, parse_snapshot


class FootballDataPremierLeagueAdapter:
    def __init__(self, client: FootballDataClient) -> None:
        self._client = client

    def fetch_snapshot(self, season_year: int) -> FootballDataSnapshot:
        competition = self._client.get("/v4/competitions/PL")
        teams = self._client.get(
            "/v4/competitions/PL/teams", query={"season": season_year}
        )
        matches = self._client.get(
            "/v4/competitions/PL/matches",
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
