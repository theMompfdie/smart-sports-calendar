from collections.abc import Mapping
from typing import Any, Protocol

from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.client import FootballDataClient, FootballDataResponse
from app.providers.football_data.exceptions import (
    FootballDataIntegrityError,
    FootballDataSchemaError,
)
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
    MATCH_PAGE_LIMIT = 500

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
        match_responses, matches_payload = self._fetch_match_pages(
            code=code,
            season_year=season_year,
        )
        responses = (competition, teams, *match_responses)
        remaining = tuple(
            value
            for response in responses
            if (value := response.rate_limits.daily_remaining) is not None
        )
        return parse_snapshot(
            competition.payload,
            teams.payload,
            matches_payload,
            profile=self.profile,
            expected_season_year=season_year,
            fetched_at_utc=max(response.fetched_at_utc for response in responses),
            request_attempts=sum(response.attempt_count for response in responses),
            rate_limits=RateLimitSnapshot(
                daily_limit=None,
                daily_remaining=min(remaining) if remaining else None,
                minute_limit=match_responses[-1].rate_limits.minute_limit,
                minute_remaining=None,
                retry_after_seconds=(
                    match_responses[-1].rate_limits.retry_after_seconds
                ),
            ),
            page_count=len(match_responses),
        )

    def _fetch_match_pages(
        self,
        *,
        code: str,
        season_year: int,
    ) -> tuple[tuple[FootballDataResponse, ...], Mapping[str, Any]]:
        query: dict[str, str | int] = {
            "limit": self.MATCH_PAGE_LIMIT,
            "season": season_year,
        }
        if self.profile.match_stage_filter is not None:
            query["stage"] = self.profile.match_stage_filter
        endpoint = f"/v4/competitions/{code}/matches"
        first = self._client.get(endpoint, query=query)

        if self.profile.expected_match_count <= self.MATCH_PAGE_LIMIT:
            return (first,), first.payload

        first_matches = self._validated_match_page(
            first.payload,
            season_year=season_year,
            offset=0,
        )
        if len(first_matches) == self.profile.expected_match_count:
            return (first,), first.payload
        if len(first_matches) != self.MATCH_PAGE_LIMIT:
            raise FootballDataIntegrityError(
                f"{self.profile.competition_name} first match page must contain "
                f"exactly {self.MATCH_PAGE_LIMIT} items or the complete "
                f"{self.profile.expected_match_count}-match snapshot."
            )

        second_query = {**query, "offset": self.MATCH_PAGE_LIMIT}
        second = self._client.get(endpoint, query=second_query)
        second_matches = self._validated_match_page(
            second.payload,
            season_year=season_year,
            offset=self.MATCH_PAGE_LIMIT,
        )
        expected_remainder = self.profile.expected_match_count - self.MATCH_PAGE_LIMIT
        if len(second_matches) != expected_remainder:
            raise FootballDataIntegrityError(
                f"{self.profile.competition_name} final match page must contain "
                f"exactly {expected_remainder} items."
            )

        merged = dict(first.payload)
        merged["resultSet"] = {"count": self.profile.expected_match_count}
        merged["matches"] = [*first_matches, *second_matches]
        return (first, second), merged

    def _validated_match_page(
        self,
        payload: Mapping[str, Any],
        *,
        season_year: int,
        offset: int,
    ) -> list[Any]:
        result_set = payload.get("resultSet")
        matches = payload.get("matches")
        filters = payload.get("filters")
        if not isinstance(result_set, dict) or not isinstance(matches, list):
            raise FootballDataSchemaError(
                "Provider match page has an invalid result collection."
            )
        count = result_set.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise FootballDataSchemaError(
                "Provider match page has an invalid result count."
            )
        if count != len(matches):
            raise FootballDataIntegrityError(
                "Provider match page result count is inconsistent."
            )
        if not isinstance(filters, dict):
            raise FootballDataSchemaError(
                "Provider match page has invalid filter metadata."
            )
        if str(filters.get("season")) != str(season_year):
            raise FootballDataIntegrityError(
                "Provider returned the wrong match season filter."
            )
        if self._filter_int(filters, "limit", self.MATCH_PAGE_LIMIT) != (
            self.MATCH_PAGE_LIMIT
        ):
            raise FootballDataIntegrityError(
                "Provider returned the wrong match limit filter."
            )
        if self._filter_int(filters, "offset", 0) != offset:
            raise FootballDataIntegrityError(
                "Provider returned the wrong match offset filter."
            )
        return matches

    @staticmethod
    def _filter_int(payload: Mapping[str, Any], key: str, default: int) -> int:
        value = payload.get(key, default)
        if isinstance(value, bool):
            raise FootballDataSchemaError(
                f"Provider returned an invalid {key} match filter."
            )
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isascii() and value.isdecimal():
            return int(value)
        raise FootballDataSchemaError(
            f"Provider returned an invalid {key} match filter."
        )


class FootballDataPremierLeagueAdapter(FootballDataCompetitionAdapter):
    def __init__(self, client: FootballDataClient) -> None:
        super().__init__(client, PREMIER_LEAGUE_PROFILE)
