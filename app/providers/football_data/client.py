import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlencode

from app.config.settings import FootballDataSettings
from app.providers.api_football.transport import (
    HttpResponse,
    HttpTransport,
)
from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.exceptions import (
    FootballDataConfigurationError,
    FootballDataRequestError,
    FootballDataRetryableError,
    FootballDataSchemaError,
)
from app.providers.football_data.transport import (
    MAX_RESPONSE_BYTES,
    FootballDataStdlibTransport,
)


@dataclass(frozen=True)
class FootballDataResponse:
    payload: Mapping[str, Any]
    headers: Mapping[str, str]
    fetched_at_utc: datetime
    attempt_count: int
    rate_limits: RateLimitSnapshot


class FootballDataClient:
    def __init__(
        self,
        settings: FootballDataSettings,
        transport: HttpTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not settings.enabled or not settings.api_key:
            raise FootballDataConfigurationError(
                "football-data.org client requires enabled settings and an API token."
            )
        self._settings = settings
        self._transport = transport or FootballDataStdlibTransport()
        self._sleep = sleep
        self._monotonic = monotonic
        self._clock = clock or (lambda: datetime.now(UTC))
        self._last_attempt_at: float | None = None

    def get(
        self,
        endpoint: str,
        query: Mapping[str, str | int] | None = None,
    ) -> FootballDataResponse:
        if not endpoint.startswith("/v4/") or "?" in endpoint or "#" in endpoint:
            raise FootballDataRequestError(
                "football-data.org endpoint must be an absolute v4 path."
            )
        for name in query or {}:
            if any(
                marker in name.casefold()
                for marker in ("key", "token", "secret", "auth")
            ):
                raise FootballDataRequestError(
                    "Provider credentials must not be sent in query parameters."
                )
        encoded = urlencode(sorted((query or {}).items()))
        url = f"{self._settings.base_url}{endpoint}"
        if encoded:
            url = f"{url}?{encoded}"
        response, attempts = self._request_with_retries(url)
        return self._parse_response(response, attempts)

    def _request_with_retries(self, url: str) -> tuple[HttpResponse, int]:
        for attempt in range(1, self._settings.max_attempts + 1):
            self._throttle()
            response: HttpResponse | None = None
            cause: BaseException | None = None
            try:
                response = self._transport.get(
                    url=url,
                    headers={
                        "Accept": "application/json",
                        "X-Auth-Token": self._settings.api_key,
                    },
                    connect_timeout_seconds=self._settings.connect_timeout_seconds,
                    read_timeout_seconds=self._settings.read_timeout_seconds,
                )
            except (OSError, TimeoutError) as error:
                cause = error
                failure: FootballDataRequestError = FootballDataRetryableError(
                    "football-data.org could not be reached."
                )
            else:
                failure = self._http_error(response)
                if failure is None:
                    return response, attempt
            if (
                not isinstance(failure, FootballDataRetryableError)
                or attempt == self._settings.max_attempts
            ):
                if cause is not None:
                    raise failure from cause
                raise failure
            self._sleep(self._retry_delay(response, attempt))
        raise AssertionError("Bounded football-data.org retry loop did not terminate.")

    def _throttle(self) -> None:
        now = self._monotonic()
        if self._last_attempt_at is not None:
            remaining = self._settings.minimum_request_interval_seconds - (
                now - self._last_attempt_at
            )
            if remaining > 0:
                self._sleep(remaining)
                now = self._monotonic()
        self._last_attempt_at = now

    @staticmethod
    def _http_error(response: HttpResponse) -> FootballDataRequestError | None:
        if response.status == 200:
            return None
        if response.status in {429} or 500 <= response.status <= 599:
            return FootballDataRetryableError(
                f"football-data.org returned HTTP {response.status}."
            )
        if response.status == 401:
            return FootballDataRequestError("football-data.org authentication failed.")
        if response.status == 403:
            return FootballDataRequestError("football-data.org access was forbidden.")
        return FootballDataRequestError(
            f"football-data.org request failed with HTTP {response.status}."
        )

    def _parse_response(
        self, response: HttpResponse, attempts: int
    ) -> FootballDataResponse:
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise FootballDataSchemaError("Provider response exceeded the safe limit.")
        content_type = self._header(response.headers, "Content-Type")
        if (
            content_type is None
            or content_type.split(";", 1)[0].strip() != "application/json"
        ):
            raise FootballDataSchemaError(
                "Provider returned an unexpected content type."
            )
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise FootballDataSchemaError(
                "Provider returned malformed JSON."
            ) from error
        if not isinstance(payload, dict):
            raise FootballDataSchemaError("Provider response root must be an object.")
        api_version = self._header(response.headers, "X-API-Version")
        if api_version != "v4":
            raise FootballDataSchemaError("Provider response is not API v4.")
        return FootballDataResponse(
            payload=payload,
            headers=response.headers,
            fetched_at_utc=self._utc_now(),
            attempt_count=attempts,
            rate_limits=self._rate_limits(response.headers),
        )

    def _retry_delay(self, response: HttpResponse | None, attempt: int) -> float:
        if response is not None:
            retry_after = self._retry_after(response.headers)
            if retry_after is not None:
                return min(retry_after, self._settings.retry_max_delay_seconds)
        return min(
            self._settings.retry_base_delay_seconds * (2 ** (attempt - 1)),
            self._settings.retry_max_delay_seconds,
        )

    def _rate_limits(self, headers: Mapping[str, str]) -> RateLimitSnapshot:
        return RateLimitSnapshot(
            daily_limit=None,
            daily_remaining=self._optional_non_negative_int(
                headers, "X-RequestsAvailable"
            ),
            minute_limit=self._settings.requests_per_minute,
            minute_remaining=None,
            retry_after_seconds=self._retry_after(headers),
        )

    def _retry_after(self, headers: Mapping[str, str]) -> float | None:
        value = self._header(headers, "Retry-After")
        if value is None:
            return None
        try:
            seconds = float(value)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError) as error:
                raise FootballDataSchemaError(
                    "Provider returned invalid retry metadata."
                ) from error
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            seconds = (retry_at.astimezone(UTC) - self._utc_now()).total_seconds()
        return max(0.0, seconds)

    def _optional_non_negative_int(
        self, headers: Mapping[str, str], name: str
    ) -> int | None:
        value = self._header(headers, name)
        if value is None:
            return None
        try:
            parsed = int(value)
        except ValueError as error:
            raise FootballDataSchemaError(
                "Provider returned invalid quota metadata."
            ) from error
        if parsed < 0:
            raise FootballDataSchemaError("Provider returned invalid quota metadata.")
        return parsed

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("football-data.org clock must return an aware datetime.")
        return value.astimezone(UTC)

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str | None:
        expected = name.casefold()
        return next(
            (value for key, value in headers.items() if key.casefold() == expected),
            None,
        )
