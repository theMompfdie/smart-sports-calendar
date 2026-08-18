from typing import Protocol

from app.providers.openligadb.client import OpenLigaDBClient, OpenLigaDBResponse
from app.providers.openligadb.models import OpenLigaDBSnapshot, parse_snapshot
from app.providers.openligadb.profiles import (
    DFB_POKAL_PROFILE,
    OpenLigaDBCompetitionProfile,
)


class OpenLigaDBClientProtocol(Protocol):
    def get(self, endpoint: str) -> OpenLigaDBResponse: ...


class OpenLigaDBSnapshotAdapter(Protocol):
    profile: OpenLigaDBCompetitionProfile

    def fetch_snapshot(self) -> OpenLigaDBSnapshot: ...


class OpenLigaDBCompetitionAdapter:
    def __init__(
        self,
        client: OpenLigaDBClientProtocol,
        profile: OpenLigaDBCompetitionProfile,
    ) -> None:
        self._client = client
        self.profile = profile

    def fetch_snapshot(self) -> OpenLigaDBSnapshot:
        season = self.profile.league_season
        shortcut = self.profile.league_shortcut
        leagues = self._client.get(f"/getavailableleagues/{season}")
        groups = self._client.get(f"/getavailablegroups/{shortcut}/{season}")
        matches = self._client.get(f"/getmatchdata/{shortcut}/{season}")
        responses = (leagues, groups, matches)
        return parse_snapshot(
            leagues.payload,
            groups.payload,
            matches.payload,
            profile=self.profile,
            fetched_at_utc=max(response.fetched_at_utc for response in responses),
            request_attempts=sum(response.attempt_count for response in responses),
        )


class OpenLigaDBDFBPokalAdapter(OpenLigaDBCompetitionAdapter):
    def __init__(self, client: OpenLigaDBClient) -> None:
        super().__init__(client, DFB_POKAL_PROFILE)
