from datetime import UTC, datetime

import pytest
from app.providers.api_football.transport import HttpResponse
from app.providers.nflverse.client import SCHEDULE_URL, NflverseClient
from app.providers.nflverse.exceptions import NflverseRequestError, NflverseSchemaError
from app.providers.nflverse.transport import MAX_RESPONSE_BYTES

from tests.providers.nflverse.support import csv_bytes


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls: list[str] = []

    def get(self, url, headers, connect_timeout_seconds, read_timeout_seconds):
        del headers, connect_timeout_seconds, read_timeout_seconds
        self.urls.append(url)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def response(status=200, headers=None, body=None):
    return HttpResponse(
        status,
        {"Content-Type": "application/octet-stream", **(headers or {})},
        csv_bytes() if body is None else body,
    )


def client(transport, **overrides):
    return NflverseClient(
        transport,
        sleep=lambda _: None,
        clock=lambda: datetime(2026, 8, 30, tzinfo=UTC),
        **overrides,
    )


def test_client_follows_only_approved_redirects() -> None:
    transport = Transport(
        [
            response(
                302,
                {"Location": "https://release-assets.githubusercontent.com/file.csv"},
            ),
            response(),
        ]
    )
    result = client(transport).fetch_schedule()
    assert transport.urls == [
        SCHEDULE_URL,
        "https://release-assets.githubusercontent.com/file.csv",
    ]
    assert result.attempt_count == 2


def test_client_rejects_redirect_outside_approved_hosts() -> None:
    transport = Transport(
        [response(302, {"Location": "https://example.test/file.csv"})]
    )
    with pytest.raises(NflverseRequestError, match="outside approved"):
        client(transport).fetch_schedule()


def test_client_retries_transient_failure() -> None:
    result = client(Transport([OSError("offline"), response()])).fetch_schedule()
    assert result.attempt_count == 2


@pytest.mark.parametrize("failure", [OSError("offline"), TimeoutError("timeout")])
def test_client_exhausts_transient_network_failures(failure: Exception) -> None:
    with pytest.raises(NflverseRequestError, match="could not be reached"):
        client(Transport([failure, failure]), max_attempts=2).fetch_schedule()


def test_client_exhausts_retryable_http_failure() -> None:
    with pytest.raises(NflverseRequestError, match="HTTP 503"):
        client(
            Transport([response(503), response(503)]), max_attempts=2
        ).fetch_schedule()


def test_client_enforces_redirect_limit() -> None:
    redirect = response(
        302, {"Location": "https://release-assets.githubusercontent.com/file.csv"}
    )
    with pytest.raises(NflverseRequestError, match="redirect limit"):
        client(Transport([redirect, redirect]), max_redirects=1).fetch_schedule()


@pytest.mark.parametrize(
    "provider_response,message",
    [
        (response(200, {"Content-Type": "text/html"}), "content type"),
        (response(200, body=b"\xff"), "UTF-8"),
        (response(200, body=b"x" * (MAX_RESPONSE_BYTES + 1)), "safe limit"),
        (response(404), "HTTP 404"),
    ],
)
def test_client_rejects_invalid_responses(provider_response, message: str) -> None:
    with pytest.raises((NflverseRequestError, NflverseSchemaError), match=message):
        client(Transport([provider_response])).fetch_schedule()
