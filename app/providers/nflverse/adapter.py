from app.providers.nflverse.client import NflverseClient
from app.providers.nflverse.models import NflverseSnapshot, parse_snapshot
from app.providers.nflverse.profiles import (
    NFL_2026_REGULAR_SEASON_PROFILE,
    NflverseCompetitionProfile,
)


class NflverseCompetitionAdapter:
    def __init__(
        self,
        client: NflverseClient,
        profile: NflverseCompetitionProfile = NFL_2026_REGULAR_SEASON_PROFILE,
    ) -> None:
        self._client = client
        self.profile = profile

    def fetch_snapshot(self) -> NflverseSnapshot:
        response = self._client.fetch_schedule()
        return parse_snapshot(
            response.body,
            profile=self.profile,
            fetched_at_utc=response.fetched_at_utc,
            request_attempts=response.attempt_count,
        )
