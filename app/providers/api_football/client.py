import json
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from app.config.settings import ApiFootballSettings
from app.providers.api_football.exceptions import (
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderConfigurationError,
    ProviderError,
    ProviderNetworkError,
    ProviderPaginationError,
    ProviderPartialFetchError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseSchemaError,
    ProviderServerError,
    ProviderTimeoutError,
    RetryableProviderError,
)
from app.providers.api_football.models import (
    ApiFootballCollection,
    ApiFootballPage,
    FetchMetadata,
    Pagination,
    RateLimitSnapshot,
)
from app.providers.api_football.transport import (
    HttpResponse,
    HttpTransport,
    StdlibHttpTransport,
)

QueryValue = str | int


class ApiFootballClient:
    def __init__(
        self,
        settings: ApiFootballSettings,
        transport: HttpTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not settings.enabled:
            raise ProviderConfigurationError(
                "API-Football client requires enabled settings."
            )
        if not settings.api_key:
            raise ProviderConfigurationError(
                "API-Football client requires a configured API key."
            )

        self._settings = settings
        self._transport = transport or StdlibHttpTransport()
        self._sleep = sleep
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_page(
        self,
        endpoint: str,
        query: Mapping[str, QueryValue] | None = None,
        page: int = 1,
    ) -> ApiFootballPage:
        if not endpoint.startswith("/") or "?" in endpoint or "#" in endpoint:
            raise ProviderRequestError(
                "API-Football endpoint must be an absolute path without a query."
            )
        if page <= 0:
            raise ProviderPaginationError(
                "API-Football page number must be greater than zero."
            )

        for parameter_name in query or {}:
            normalized_name = parameter_name.casefold()
            if any(
                secret_marker in normalized_name
                for secret_marker in ("key", "token", "secret", "auth")
            ):
                raise ProviderRequestError(
                    "API-Football credentials must not be sent in query parameters."
                )

        parameters = dict(query or {})
        parameters["page"] = page
        encoded_query = urlencode(
            sorted(parameters.items()),
            doseq=False,
        )
        url = f"{self._settings.base_url}{endpoint}?{encoded_query}"
        response, attempt_count = self._request_with_retries(url)

        return self._parse_page(
            response=response,
            requested_page=page,
            attempt_count=attempt_count,
        )

    def get_all(
        self,
        endpoint: str,
        query: Mapping[str, QueryValue] | None = None,
    ) -> ApiFootballCollection:
        first_page = self.get_page(endpoint, query=query, page=1)
        items = list(first_page.items)
        expected_total = first_page.pagination.total
        last_page = first_page
        request_attempts = first_page.metadata.attempt_count

        for page_number in range(2, expected_total + 1):
            try:
                page = self.get_page(
                    endpoint,
                    query=query,
                    page=page_number,
                )
            except ProviderPaginationError:
                raise
            except ProviderError as error:
                raise ProviderPartialFetchError(
                    "API-Football collection fetch failed after "
                    f"{page_number - 1} completed page(s)."
                ) from error

            if page.pagination.total != expected_total:
                raise ProviderPaginationError(
                    "API-Football pagination total changed during traversal."
                )

            items.extend(page.items)
            last_page = page
            request_attempts += page.metadata.attempt_count

        return ApiFootballCollection(
            items=tuple(items),
            page_count=expected_total,
            fetched_at_utc=first_page.metadata.fetched_at_utc,
            rate_limits=last_page.metadata.rate_limits,
            request_attempts=request_attempts,
        )

    def _request_with_retries(self, url: str) -> tuple[HttpResponse, int]:
        for attempt in range(1, self._settings.max_attempts + 1):
            try:
                response = self._transport.get(
                    url=url,
                    headers={
                        "Accept": "application/json",
                        "x-apisports-key": self._settings.api_key,
                    },
                    connect_timeout_seconds=(self._settings.connect_timeout_seconds),
                    read_timeout_seconds=self._settings.read_timeout_seconds,
                )
                error = self._classify_http_error(response)
                if error is None:
                    return response, attempt
            except TimeoutError:
                error = ProviderTimeoutError("API-Football request timed out.")
            except OSError:
                error = ProviderNetworkError("API-Football could not be reached.")

            if (
                not isinstance(error, RetryableProviderError)
                or attempt == self._settings.max_attempts
            ):
                raise error

            self._sleep(self._retry_delay(error, attempt))

        raise AssertionError("Bounded API-Football retry loop did not terminate.")

    def _classify_http_error(
        self,
        response: HttpResponse,
    ) -> ProviderError | None:
        if response.status in {200, 204}:
            return None
        if response.status == 401:
            return ProviderAuthenticationError("API-Football authentication failed.")
        if response.status == 403:
            return ProviderAuthorizationError(
                "API-Football access was forbidden by the credential or plan."
            )
        if response.status == 429:
            return ProviderRateLimitError(
                retry_after_seconds=self._parse_retry_after(response.headers),
            )
        if response.status == 499:
            return ProviderTimeoutError("API-Football reported a request timeout.")
        if 500 <= response.status <= 599:
            return ProviderServerError(f"API-Football returned HTTP {response.status}.")

        return ProviderRequestError(
            f"API-Football request failed with HTTP {response.status}."
        )

    def _parse_page(
        self,
        response: HttpResponse,
        requested_page: int,
        attempt_count: int,
    ) -> ApiFootballPage:
        metadata = FetchMetadata(
            fetched_at_utc=self._utc_now(),
            request_id=self._header(response.headers, "x-request-id"),
            rate_limits=self._parse_rate_limits(response.headers),
            attempt_count=attempt_count,
        )

        if response.status == 204:
            return ApiFootballPage(
                items=(),
                pagination=Pagination(
                    current=requested_page,
                    total=requested_page,
                ),
                metadata=metadata,
            )

        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderResponseSchemaError(
                "API-Football returned invalid JSON."
            ) from error

        if not isinstance(payload, dict):
            raise ProviderResponseSchemaError(
                "API-Football response envelope must be an object."
            )

        provider_errors = payload.get("errors")
        if not isinstance(provider_errors, (dict, list)):
            raise ProviderResponseSchemaError(
                "API-Football response has invalid errors metadata."
            )
        if provider_errors:
            raise self._classify_envelope_error(
                provider_errors=provider_errors,
                retry_after_seconds=metadata.rate_limits.retry_after_seconds,
            )

        results = payload.get("results")
        items = payload.get("response")
        paging = payload.get("paging")

        if not isinstance(results, int) or isinstance(results, bool) or results < 0:
            raise ProviderResponseSchemaError(
                "API-Football response has invalid results metadata."
            )
        if not isinstance(items, list) or not all(
            isinstance(item, dict) for item in items
        ):
            raise ProviderResponseSchemaError(
                "API-Football response items must be objects."
            )
        if results != len(items):
            raise ProviderResponseSchemaError(
                "API-Football result count does not match response items."
            )
        if not isinstance(paging, dict):
            raise ProviderPaginationError(
                "API-Football response is missing pagination metadata."
            )

        current = paging.get("current")
        total = paging.get("total")
        if (
            not isinstance(current, int)
            or isinstance(current, bool)
            or not isinstance(total, int)
            or isinstance(total, bool)
            or current <= 0
            or total <= 0
            or current > total
        ):
            raise ProviderPaginationError(
                "API-Football response has invalid pagination metadata."
            )
        if current != requested_page:
            raise ProviderPaginationError(
                "API-Football returned an unexpected page number."
            )

        return ApiFootballPage(
            items=tuple(items),
            pagination=Pagination(current=current, total=total),
            metadata=metadata,
        )

    def _classify_envelope_error(
        self,
        provider_errors: dict[object, object] | list[object],
        retry_after_seconds: float | None,
    ) -> ProviderError:
        error_text = str(provider_errors).casefold()

        if "rate" in error_text or "quota" in error_text:
            return ProviderRateLimitError(retry_after_seconds)
        if "auth" in error_text or "api key" in error_text:
            return ProviderAuthenticationError(
                "API-Football response reported an authentication failure."
            )
        if "forbidden" in error_text or "plan" in error_text or "access" in error_text:
            return ProviderAuthorizationError(
                "API-Football response reported an authorization failure."
            )

        return ProviderRequestError(
            "API-Football response reported a provider request error."
        )

    def _parse_rate_limits(
        self,
        headers: Mapping[str, str],
    ) -> RateLimitSnapshot:
        return RateLimitSnapshot(
            daily_limit=self._optional_non_negative_header_integer(
                headers,
                "x-ratelimit-requests-limit",
            ),
            daily_remaining=self._optional_non_negative_header_integer(
                headers,
                "x-ratelimit-requests-remaining",
            ),
            minute_limit=self._optional_non_negative_header_integer(
                headers,
                "x-ratelimit-limit",
            ),
            minute_remaining=self._optional_non_negative_header_integer(
                headers,
                "x-ratelimit-remaining",
            ),
            retry_after_seconds=self._parse_retry_after(headers),
        )

    def _optional_non_negative_header_integer(
        self,
        headers: Mapping[str, str],
        name: str,
    ) -> int | None:
        value = self._header(headers, name)
        if value is None:
            return None

        try:
            parsed_value = int(value)
        except ValueError as error:
            raise ProviderResponseSchemaError(
                f"API-Football returned invalid {name} metadata."
            ) from error

        if parsed_value < 0:
            raise ProviderResponseSchemaError(
                f"API-Football returned invalid {name} metadata."
            )

        return parsed_value

    def _parse_retry_after(
        self,
        headers: Mapping[str, str],
    ) -> float | None:
        value = self._header(headers, "retry-after")
        if value is None:
            return None

        try:
            seconds = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError) as error:
                raise ProviderResponseSchemaError(
                    "API-Football returned invalid retry-after metadata."
                ) from error

            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            seconds = (retry_at.astimezone(UTC) - self._utc_now()).total_seconds()

        if seconds < 0:
            return 0.0

        return seconds

    def _retry_delay(
        self,
        error: RetryableProviderError,
        attempt: int,
    ) -> float:
        if (
            isinstance(error, ProviderRateLimitError)
            and error.retry_after_seconds is not None
        ):
            return min(
                error.retry_after_seconds,
                self._settings.retry_max_delay_seconds,
            )

        exponential_delay = self._settings.retry_base_delay_seconds * (
            2 ** (attempt - 1)
        )
        return min(
            exponential_delay,
            self._settings.retry_max_delay_seconds,
        )

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("API-Football clock must return an aware datetime.")

        return value.astimezone(UTC)

    @staticmethod
    def _header(
        headers: Mapping[str, str],
        name: str,
    ) -> str | None:
        normalized_name = name.casefold()
        for header_name, value in headers.items():
            if header_name.casefold() == normalized_name:
                return value

        return None
