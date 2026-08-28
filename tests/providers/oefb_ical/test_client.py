from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

import pytest
from app.providers.api_football.transport import HttpResponse
from app.providers.oefb_ical.client import OefbIcalClient
from app.providers.oefb_ical.exceptions import (
    OefbIcalRequestError,
    OefbIcalRetryableError,
    OefbIcalSchemaError,
)
from app.providers.oefb_ical.transport import MAX_RESPONSE_BYTES

from tests.providers.oefb_ical.support import (
    FEED_URL,
    FETCHED_AT,
    LAST_MODIFIED,
    response,
    settings,
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
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_client_fetches_calendar_without_exposing_secret() -> None:
    transport = Transport([response(body=b"safe-calendar")])
    client = OefbIcalClient(
        settings(),
        transport=transport,
        clock=lambda: FETCHED_AT,
    )

    result = client.get()

    assert result.payload == b"safe-calendar"
    assert result.fetched_at_utc == FETCHED_AT
    assert result.last_modified == LAST_MODIFIED
    assert result.not_modified is False
    assert transport.requests == [Request(FEED_URL, {"Accept": "text/calendar"})]


def test_client_uses_conditional_request_and_accepts_304() -> None:
    transport = Transport([response(304, body=b"")])
    client = OefbIcalClient(settings(), transport=transport, clock=lambda: FETCHED_AT)

    result = client.get(if_modified_since=LAST_MODIFIED)

    assert result.payload is None
    assert result.not_modified is True
    assert result.last_modified == LAST_MODIFIED
    assert transport.requests[0].headers["If-Modified-Since"] == LAST_MODIFIED


def test_client_follows_only_safe_same_host_redirect() -> None:
    redirected = "https://www.fussballoesterreich.at/Calendar/replacement.ics"
    transport = Transport(
        [
            response(302, body=b"", headers={"Location": redirected}),
            response(body=b"safe-calendar"),
        ]
    )
    client = OefbIcalClient(settings(), transport=transport)

    result = client.get()

    assert result.payload == b"safe-calendar"
    assert [request.url for request in transport.requests] == [FEED_URL, redirected]


def test_client_rejects_cross_host_redirect_without_exposing_url() -> None:
    secret_redirect = "https://example.test/Calendar/secret-token.ics"
    transport = Transport(
        [response(302, body=b"", headers={"Location": secret_redirect})]
    )
    client = OefbIcalClient(settings(), transport=transport)

    with pytest.raises(OefbIcalRequestError) as error:
        client.get()

    assert FEED_URL not in str(error.value)
    assert secret_redirect not in str(error.value)


def test_client_retries_transient_failure_with_bounded_delay() -> None:
    transport = Transport(
        [response(429, headers={"Retry-After": "2"}), response(body=b"ok")]
    )
    sleeps: list[float] = []
    client = OefbIcalClient(settings(), transport=transport, sleep=sleeps.append)

    result = client.get()

    assert result.attempt_count == 2
    assert sleeps == [2.0]


@pytest.mark.parametrize(
    ("provider_response", "error"),
    [
        (response(404), OefbIcalRequestError),
        (response(500), OefbIcalRetryableError),
        (
            response(headers={"Content-Type": "text/html"}),
            OefbIcalSchemaError,
        ),
        (
            response(headers={"Content-Length": "999"}),
            OefbIcalSchemaError,
        ),
        (
            response(body=b"x" * (MAX_RESPONSE_BYTES + 1)),
            OefbIcalSchemaError,
        ),
    ],
)
def test_client_classifies_provider_failures(
    provider_response: HttpResponse,
    error: type[Exception],
) -> None:
    client = OefbIcalClient(
        settings(),
        transport=Transport([provider_response] * 3),
        sleep=lambda _: None,
    )

    with pytest.raises(error):
        client.get()


def test_client_rejects_invalid_http_metadata() -> None:
    client = OefbIcalClient(
        settings(),
        transport=Transport([response(headers={"Last-Modified": "not-an-http-date"})]),
    )

    with pytest.raises(OefbIcalSchemaError, match="HTTP date"):
        client.get()


def test_client_requires_aware_clock() -> None:
    client = OefbIcalClient(
        settings(),
        transport=Transport([response()]),
        clock=lambda: datetime(2026, 8, 28),
    )

    with pytest.raises(ValueError, match="aware datetime"):
        client.get()
