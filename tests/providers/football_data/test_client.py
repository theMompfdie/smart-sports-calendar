import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from app.config.settings import FootballDataSettings
from app.providers.api_football.transport import HttpResponse
from app.providers.football_data.client import FootballDataClient
from app.providers.football_data.exceptions import (
    FootballDataRequestError,
    FootballDataRetryableError,
    FootballDataSchemaError,
)


@dataclass(frozen=True)
class Request:
    url: str
    headers: Mapping[str, str]


class Transport:
    def __init__(self, responses: list[HttpResponse | Exception]) -> None:
        self.responses = responses
        self.requests: list[Request] = []

    def get(self, url, headers, connect_timeout_seconds, read_timeout_seconds):
        del connect_timeout_seconds, read_timeout_seconds
        self.requests.append(Request(url, headers))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def settings(**overrides) -> FootballDataSettings:
    values = {
        "enabled": True,
        "api_key": "provider-secret",
        "minimum_request_interval_seconds": 6.0,
        "requests_per_minute": 10,
        "retry_base_delay_seconds": 1.0,
        "retry_max_delay_seconds": 30.0,
        "max_attempts": 3,
    }
    values.update(overrides)
    return FootballDataSettings(**values)


def response(status: int = 200, *, headers=None, payload=None) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers={
            "Content-Type": "application/json",
            "X-API-Version": "v4",
            **(headers or {}),
        },
        body=json.dumps(payload or {"id": 2021}).encode(),
    )


def test_client_keeps_token_in_header_and_parses_safe_metadata() -> None:
    transport = Transport([response(headers={"X-RequestsAvailable": "9"})])
    client = FootballDataClient(
        settings(),
        transport=transport,
        sleep=lambda _: None,
        monotonic=lambda: 0,
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )

    result = client.get("/v4/competitions/PL", {"season": 2026})

    assert "provider-secret" not in transport.requests[0].url
    assert transport.requests[0].headers["X-Auth-Token"] == "provider-secret"
    assert result.rate_limits.daily_remaining == 9
    assert result.rate_limits.minute_limit == 10


def test_client_retries_429_and_enforces_request_spacing() -> None:
    transport = Transport([response(429, headers={"Retry-After": "2"}), response()])
    sleeps: list[float] = []
    monotonic_values = iter([0.0, 0.0, 6.0])
    client = FootballDataClient(
        settings(),
        transport=transport,
        sleep=sleeps.append,
        monotonic=lambda: next(monotonic_values),
        clock=lambda: datetime(2026, 8, 9, tzinfo=UTC),
    )

    result = client.get("/v4/competitions/PL")

    assert result.attempt_count == 2
    assert sleeps == [2.0, 6.0]


@pytest.mark.parametrize(
    "provider_response,error",
    [
        (response(401), FootballDataRequestError),
        (response(500), FootballDataRetryableError),
        (
            HttpResponse(
                200, {"Content-Type": "text/html", "X-API-Version": "v4"}, b"{}"
            ),
            FootballDataSchemaError,
        ),
        (
            HttpResponse(
                200, {"Content-Type": "application/json", "X-API-Version": "v3"}, b"{}"
            ),
            FootballDataSchemaError,
        ),
    ],
)
def test_client_classifies_failures_without_leaking_secrets(
    provider_response: HttpResponse, error: type[Exception]
) -> None:
    transport = Transport([provider_response] * 3)
    client = FootballDataClient(
        settings(),
        transport=transport,
        sleep=lambda _: None,
        monotonic=lambda: 0,
    )

    with pytest.raises(error) as captured:
        client.get("/v4/competitions/PL")

    assert "provider-secret" not in str(captured.value)
