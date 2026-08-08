import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from app.config.settings import ApiFootballSettings
from app.providers.api_football.client import ApiFootballClient
from app.providers.api_football.exceptions import (
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderConfigurationError,
    ProviderNetworkError,
    ProviderPaginationError,
    ProviderPartialFetchError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseSchemaError,
    ProviderServerError,
    ProviderTimeoutError,
)
from app.providers.api_football.transport import HttpResponse


@dataclass(frozen=True)
class RecordedRequest:
    url: str
    headers: Mapping[str, str]
    connect_timeout_seconds: float
    read_timeout_seconds: float


class StubTransport:
    def __init__(self, *results: HttpResponse | Exception) -> None:
        self._results = list(results)
        self.requests: list[RecordedRequest] = []

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        self.requests.append(
            RecordedRequest(
                url=url,
                headers=dict(headers),
                connect_timeout_seconds=connect_timeout_seconds,
                read_timeout_seconds=read_timeout_seconds,
            )
        )
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result

        return result


def create_settings(
    *,
    max_attempts: int = 3,
    retry_max_delay_seconds: float = 30.0,
) -> ApiFootballSettings:
    return ApiFootballSettings(
        enabled=True,
        api_key="provider-secret",
        connect_timeout_seconds=2.5,
        read_timeout_seconds=12.5,
        max_attempts=max_attempts,
        retry_base_delay_seconds=1.0,
        retry_max_delay_seconds=retry_max_delay_seconds,
    )


def create_response(
    *,
    status: int = 200,
    items: list[dict[str, Any]] | None = None,
    current: int = 1,
    total: int = 1,
    errors: dict[str, str] | list[object] | None = None,
    headers: Mapping[str, str] | None = None,
) -> HttpResponse:
    response_items = items or []
    return HttpResponse(
        status=status,
        headers=dict(headers or {}),
        body=json.dumps(
            {
                "errors": errors or [],
                "results": len(response_items),
                "paging": {"current": current, "total": total},
                "response": response_items,
            }
        ).encode(),
    )


def create_client(
    transport: StubTransport,
    *,
    max_attempts: int = 3,
    sleep: list[float] | None = None,
    now: datetime | None = None,
    retry_max_delay_seconds: float = 30.0,
) -> ApiFootballClient:
    delays = sleep if sleep is not None else []
    current_time = now or datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    return ApiFootballClient(
        settings=create_settings(
            max_attempts=max_attempts,
            retry_max_delay_seconds=retry_max_delay_seconds,
        ),
        transport=transport,
        sleep=delays.append,
        clock=lambda: current_time,
    )


def test_get_page_sends_secret_header_and_deterministic_query() -> None:
    transport = StubTransport(create_response(items=[{"fixture": {"id": 1}}]))
    client = create_client(transport)

    page = client.get_page(
        "/fixtures",
        query={"season": 2025, "league": 39},
    )

    request = transport.requests[0]
    assert request.headers == {
        "Accept": "application/json",
        "x-apisports-key": "provider-secret",
    }
    assert parse_qs(urlsplit(request.url).query) == {
        "league": ["39"],
        "page": ["1"],
        "season": ["2025"],
    }
    assert "provider-secret" not in request.url
    assert request.connect_timeout_seconds == 2.5
    assert request.read_timeout_seconds == 12.5
    assert page.items == ({"fixture": {"id": 1}},)


def test_get_page_parses_diagnostics_and_rate_limits_case_insensitively() -> None:
    now = datetime(2026, 8, 8, 14, 0, tzinfo=UTC)
    transport = StubTransport(
        create_response(
            headers={
                "X-Request-ID": "request-1",
                "X-RateLimit-Requests-Limit": "7500",
                "x-ratelimit-requests-remaining": "7499",
                "X-RateLimit-Limit": "300",
                "x-ratelimit-remaining": "299",
                "Retry-After": "4",
            }
        )
    )

    page = create_client(transport, now=now).get_page("/fixtures")

    assert page.metadata.fetched_at_utc == now
    assert page.metadata.request_id == "request-1"
    assert page.metadata.rate_limits.daily_limit == 7500
    assert page.metadata.rate_limits.daily_remaining == 7499
    assert page.metadata.rate_limits.minute_limit == 300
    assert page.metadata.rate_limits.minute_remaining == 299
    assert page.metadata.rate_limits.retry_after_seconds == 4.0


def test_get_all_traverses_every_page_and_combines_items() -> None:
    transport = StubTransport(
        create_response(items=[{"id": 1}], current=1, total=2),
        create_response(items=[{"id": 2}], current=2, total=2),
    )

    result = create_client(transport).get_all("/teams", query={"league": 39})

    assert result.items == ({"id": 1}, {"id": 2})
    assert result.page_count == 2
    assert [
        parse_qs(urlsplit(item.url).query)["page"] for item in transport.requests
    ] == [
        ["1"],
        ["2"],
    ]


def test_get_all_rejects_changed_pagination_total() -> None:
    transport = StubTransport(
        create_response(current=1, total=2),
        create_response(current=2, total=3),
    )

    with pytest.raises(
        ProviderPaginationError,
        match="pagination total changed",
    ):
        create_client(transport).get_all("/teams")


def test_get_all_classifies_failure_after_first_page_as_partial() -> None:
    transport = StubTransport(
        create_response(current=1, total=2),
        OSError("provider-secret network detail"),
    )

    with pytest.raises(
        ProviderPartialFetchError,
        match="after 1 completed page",
    ) as captured:
        create_client(transport, max_attempts=1).get_all("/teams")

    assert isinstance(captured.value.__cause__, ProviderNetworkError)
    assert "provider-secret" not in str(captured.value)
    assert "provider-secret" not in str(captured.value.__cause__)


@pytest.mark.parametrize(
    "status,error_type",
    [
        (401, ProviderAuthenticationError),
        (403, ProviderAuthorizationError),
        (429, ProviderRateLimitError),
        (499, ProviderTimeoutError),
        (500, ProviderServerError),
        (400, ProviderRequestError),
    ],
)
def test_get_page_classifies_http_failures(
    status: int,
    error_type: type[Exception],
) -> None:
    transport = StubTransport(create_response(status=status))

    with pytest.raises(error_type):
        create_client(transport, max_attempts=1).get_page("/fixtures")


@pytest.mark.parametrize(
    "errors,error_type",
    [
        ({"token": "Invalid API key authentication"}, ProviderAuthenticationError),
        ({"access": "Plan does not allow access"}, ProviderAuthorizationError),
        ({"rateLimit": "Daily quota exceeded"}, ProviderRateLimitError),
        ({"parameter": "Invalid league"}, ProviderRequestError),
    ],
)
def test_get_page_classifies_provider_errors_in_http_200_envelope(
    errors: dict[str, str],
    error_type: type[Exception],
) -> None:
    transport = StubTransport(create_response(errors=errors))

    with pytest.raises(error_type):
        create_client(transport).get_page("/fixtures")


def test_get_page_retries_timeout_with_bounded_exponential_delay() -> None:
    delays: list[float] = []
    transport = StubTransport(
        TimeoutError("provider-secret timeout detail"),
        TimeoutError("second timeout"),
        create_response(),
    )

    page = create_client(transport, sleep=delays).get_page("/fixtures")

    assert delays == [1.0, 2.0]
    assert len(transport.requests) == 3
    assert page.metadata.attempt_count == 3


def test_get_page_honors_and_caps_rate_limit_retry_after() -> None:
    delays: list[float] = []
    transport = StubTransport(
        create_response(status=429, headers={"Retry-After": "120"}),
        create_response(),
    )

    create_client(
        transport,
        sleep=delays,
        retry_max_delay_seconds=30,
    ).get_page("/fixtures")

    assert delays == [30]


def test_get_page_preserves_rate_limit_retry_guidance() -> None:
    transport = StubTransport(
        create_response(status=429, headers={"Retry-After": "12"}),
    )

    with pytest.raises(ProviderRateLimitError) as captured:
        create_client(transport, max_attempts=1).get_page("/fixtures")

    assert captured.value.retry_after_seconds == 12


@pytest.mark.parametrize(
    "retryable_failure",
    [
        OSError("temporary network failure"),
        create_response(status=500),
    ],
)
def test_get_page_retries_network_and_server_failures(
    retryable_failure: Exception | HttpResponse,
) -> None:
    delays: list[float] = []
    transport = StubTransport(retryable_failure, create_response())

    create_client(transport, sleep=delays).get_page("/fixtures")

    assert delays == [1.0]
    assert len(transport.requests) == 2


def test_get_page_does_not_retry_permanent_failure() -> None:
    delays: list[float] = []
    transport = StubTransport(create_response(status=401), create_response())

    with pytest.raises(ProviderAuthenticationError):
        create_client(transport, sleep=delays).get_page("/fixtures")

    assert delays == []
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "response,error_type",
    [
        (
            HttpResponse(status=200, headers={}, body=b"not-json"),
            ProviderResponseSchemaError,
        ),
        (
            HttpResponse(status=200, headers={}, body=b"[]"),
            ProviderResponseSchemaError,
        ),
        (
            HttpResponse(
                status=200,
                headers={},
                body=json.dumps(
                    {
                        "errors": [],
                        "results": 2,
                        "paging": {"current": 1, "total": 1},
                        "response": [{"id": 1}],
                    }
                ).encode(),
            ),
            ProviderResponseSchemaError,
        ),
        (
            HttpResponse(
                status=200,
                headers={},
                body=json.dumps(
                    {
                        "errors": [],
                        "results": 0,
                        "paging": {"current": 2, "total": 1},
                        "response": [],
                    }
                ).encode(),
            ),
            ProviderPaginationError,
        ),
    ],
)
def test_get_page_rejects_malformed_response(
    response: HttpResponse,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        create_client(StubTransport(response)).get_page("/fixtures")


def test_get_page_accepts_no_content_as_empty_page() -> None:
    response = HttpResponse(status=204, headers={}, body=b"")

    page = create_client(StubTransport(response)).get_page("/fixtures")

    assert page.items == ()
    assert page.pagination.current == 1
    assert page.pagination.total == 1


def test_get_page_rejects_unexpected_returned_page() -> None:
    transport = StubTransport(create_response(current=1, total=2))

    with pytest.raises(
        ProviderPaginationError,
        match="unexpected page number",
    ):
        create_client(transport).get_page("/fixtures", page=2)


def test_get_page_parses_http_date_retry_after() -> None:
    now = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    retry_at = now + timedelta(seconds=20)
    transport = StubTransport(
        create_response(
            headers={"Retry-After": retry_at.strftime("%a, %d %b %Y %H:%M:%S GMT")}
        )
    )

    page = create_client(transport, now=now).get_page("/fixtures")

    assert page.metadata.rate_limits.retry_after_seconds == 20


def test_get_page_rejects_secret_bearing_or_relative_endpoint() -> None:
    client = create_client(StubTransport(create_response()))

    with pytest.raises(ProviderRequestError):
        client.get_page("https://provider.example/fixtures?key=secret")


@pytest.mark.parametrize(
    "parameter_name",
    ["api_key", "token", "clientSecret", "Authorization"],
)
def test_get_page_rejects_secret_bearing_query_parameter(
    parameter_name: str,
) -> None:
    client = create_client(StubTransport(create_response()))

    with pytest.raises(
        ProviderRequestError,
        match="must not be sent in query parameters",
    ):
        client.get_page("/fixtures", query={parameter_name: "provider-secret"})


def test_client_rejects_disabled_settings() -> None:
    with pytest.raises(
        ProviderConfigurationError,
        match="requires enabled settings",
    ):
        ApiFootballClient(
            settings=ApiFootballSettings(enabled=False, api_key=""),
            transport=StubTransport(create_response()),
        )
