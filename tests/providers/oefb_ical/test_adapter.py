from collections.abc import Iterable

import pytest
from app.providers.oefb_ical.adapter import OefbIcalCompetitionAdapter
from app.providers.oefb_ical.client import OefbIcalResponse
from app.providers.oefb_ical.exceptions import OefbIcalSchemaError

from tests.providers.oefb_ical.support import (
    FETCHED_AT,
    LAST_MODIFIED,
    calendar_payload,
)


class StubClient:
    def __init__(self, responses: Iterable[OefbIcalResponse]) -> None:
        self._responses = iter(responses)
        self.conditional_values: list[str | None] = []

    def get(self, *, if_modified_since: str | None = None) -> OefbIcalResponse:
        self.conditional_values.append(if_modified_since)
        return next(self._responses)


def successful_response(payload: bytes | None = None) -> OefbIcalResponse:
    return OefbIcalResponse(
        payload=payload or calendar_payload(),
        fetched_at_utc=FETCHED_AT,
        attempt_count=2,
        last_modified=LAST_MODIFIED,
        not_modified=False,
    )


def not_modified_response() -> OefbIcalResponse:
    return OefbIcalResponse(
        payload=None,
        fetched_at_utc=FETCHED_AT,
        attempt_count=1,
        last_modified=LAST_MODIFIED,
        not_modified=True,
    )


def test_adapter_reuses_validated_snapshot_after_not_modified_response() -> None:
    client = StubClient((successful_response(), not_modified_response()))
    adapter = OefbIcalCompetitionAdapter(client)

    first = adapter.fetch_snapshot()
    second = adapter.fetch_snapshot()

    assert second is first
    assert client.conditional_values == [None, LAST_MODIFIED]


def test_adapter_rejects_not_modified_without_cached_snapshot() -> None:
    adapter = OefbIcalCompetitionAdapter(StubClient((not_modified_response(),)))

    with pytest.raises(OefbIcalSchemaError, match="before a validated snapshot"):
        adapter.fetch_snapshot()


def test_adapter_does_not_cache_last_modified_from_invalid_payload() -> None:
    client = StubClient((successful_response(b"invalid"), successful_response()))
    adapter = OefbIcalCompetitionAdapter(client)

    with pytest.raises(OefbIcalSchemaError):
        adapter.fetch_snapshot()
    adapter.fetch_snapshot()

    assert client.conditional_values == [None, None]
