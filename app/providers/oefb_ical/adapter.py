from typing import Protocol

from app.providers.oefb_ical.client import OefbIcalClient, OefbIcalResponse
from app.providers.oefb_ical.exceptions import OefbIcalSchemaError
from app.providers.oefb_ical.models import OefbIcalSnapshot, parse_snapshot


class OefbIcalClientProtocol(Protocol):
    def get(self, *, if_modified_since: str | None = None) -> OefbIcalResponse: ...


class OefbIcalSnapshotAdapter(Protocol):
    def fetch_snapshot(self) -> OefbIcalSnapshot: ...


class OefbIcalCompetitionAdapter:
    """Parses responses and reuses one validated identity on HTTP 304."""

    def __init__(self, client: OefbIcalClientProtocol) -> None:
        self._client = client
        self._last_modified: str | None = None
        self._last_snapshot: OefbIcalSnapshot | None = None

    def fetch_snapshot(self) -> OefbIcalSnapshot:
        response = self._client.get(if_modified_since=self._last_modified)
        if response.not_modified:
            if self._last_snapshot is None:
                raise OefbIcalSchemaError(
                    "Provider returned 304 before a validated snapshot existed."
                )
            return self._last_snapshot
        if response.payload is None:
            raise OefbIcalSchemaError("Provider returned no calendar payload.")
        snapshot = parse_snapshot(
            response.payload,
            fetched_at_utc=response.fetched_at_utc,
            request_attempts=response.attempt_count,
            last_modified=response.last_modified,
        )
        self._last_snapshot = snapshot
        self._last_modified = response.last_modified
        return snapshot


class OefbIcalCupAdapter(OefbIcalCompetitionAdapter):
    def __init__(self, client: OefbIcalClient) -> None:
        super().__init__(client)
