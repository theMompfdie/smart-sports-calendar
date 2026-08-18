import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from app.config.settings import OpenLigaDBSettings
from app.providers.api_football.transport import HttpResponse
from app.providers.openligadb.client import OpenLigaDBClient
from app.providers.openligadb.exceptions import (
    OpenLigaDBRequestError,
    OpenLigaDBRetryableError,
    OpenLigaDBSchemaError,
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


def settings(**overrides) -> OpenLigaDBSettings:
    values = {
        "enabled": True,
        "minimum_request_interval_seconds": 1.0,
        "retry_base_delay_seconds": 1.0,
        "retry_max_delay_seconds": 30.0,
        "max_attempts": 3,
    }
    values.update(overrides)
    return OpenLigaDBSettings(**values)


def response(status: int = 200, *, headers=None, payload=None) -> HttpResponse:
    return HttpResponse(
        status=status,
        headers={"Content-Type": "application/json; charset=utf-8", **(headers or {})},
        body=json.dumps([] if payload is None else payload).encode(),
    )


def test_client_uses_public_endpoint_without_credentials() -> None:
    transport = Transport([response(payload=[{"matchID": 1}])])
    client = OpenLigaDBClient(
        settings(),
        transport=transport,
        monotonic=lambda: 0,
        clock=lambda: datetime(2026, 8, 18, tzinfo=UTC),
    )

    result = client.get("/getmatchdata/dfb/2026")

    assert result.payload == [{"matchID": 1}]
    assert transport.requests == [
        Request(
            "https://api.openligadb.de/getmatchdata/dfb/2026",
            {"Accept": "application/json"},
        )
    ]


def test_client_retries_transient_failure_with_bounded_spacing() -> None:
    transport = Transport([response(429, headers={"Retry-After": "2"}), response()])
    sleeps: list[float] = []
    monotonic_values = iter([0.0, 0.0, 1.0])
    client = OpenLigaDBClient(
        settings(),
        transport=transport,
        sleep=sleeps.append,
        monotonic=lambda: next(monotonic_values),
    )

    result = client.get("/getmatchdata/dfb/2026")

    assert result.attempt_count == 2
    assert sleeps == [2.0, 1.0]


@pytest.mark.parametrize(
    ("provider_response", "error"),
    [
        (response(404), OpenLigaDBRequestError),
        (response(500), OpenLigaDBRetryableError),
        (
            HttpResponse(200, {"Content-Type": "text/html"}, b"[]"),
            OpenLigaDBSchemaError,
        ),
        (
            HttpResponse(200, {"Content-Type": "application/json"}, b"{}"),
            OpenLigaDBSchemaError,
        ),
    ],
)
def test_client_classifies_provider_failures(
    provider_response: HttpResponse, error: type[Exception]
) -> None:
    client = OpenLigaDBClient(
        settings(),
        transport=Transport([provider_response] * 3),
        sleep=lambda _: None,
        monotonic=lambda: 0,
    )

    with pytest.raises(error):
        client.get("/getmatchdata/dfb/2026")
