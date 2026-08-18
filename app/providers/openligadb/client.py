import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from app.config.settings import OpenLigaDBSettings
from app.providers.api_football.transport import HttpResponse, HttpTransport
from app.providers.openligadb.exceptions import (
    OpenLigaDBConfigurationError,
    OpenLigaDBRequestError,
    OpenLigaDBRetryableError,
    OpenLigaDBSchemaError,
)
from app.providers.openligadb.transport import (
    MAX_RESPONSE_BYTES,
    OpenLigaDBStdlibTransport,
)


@dataclass(frozen=True)
class OpenLigaDBResponse:
    payload: Sequence[Any]
    fetched_at_utc: datetime
    attempt_count: int


class OpenLigaDBClient:
    def __init__(
        self,
        settings: OpenLigaDBSettings,
        transport: HttpTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not settings.enabled:
            raise OpenLigaDBConfigurationError(
                "OpenLigaDB client requires enabled settings."
            )
        self._settings = settings
        self._transport = transport or OpenLigaDBStdlibTransport()
        self._sleep = sleep
        self._monotonic = monotonic
        self._clock = clock or (lambda: datetime.now(UTC))
        self._last_attempt_at: float | None = None

    def get(self, endpoint: str) -> OpenLigaDBResponse:
        if not endpoint.startswith("/") or "?" in endpoint or "#" in endpoint:
            raise OpenLigaDBRequestError(
                "OpenLigaDB endpoint must be an absolute path without a query."
            )
        response, attempts = self._request_with_retries(
            f"{self._settings.base_url}{endpoint}"
        )
        return self._parse_response(response, attempts)

    def _request_with_retries(self, url: str) -> tuple[HttpResponse, int]:
        for attempt in range(1, self._settings.max_attempts + 1):
            self._throttle()
            response: HttpResponse | None = None
            cause: BaseException | None = None
            try:
                response = self._transport.get(
                    url=url,
                    headers={"Accept": "application/json"},
                    connect_timeout_seconds=self._settings.connect_timeout_seconds,
                    read_timeout_seconds=self._settings.read_timeout_seconds,
                )
            except (OSError, TimeoutError) as error:
                cause = error
                failure: OpenLigaDBRequestError = OpenLigaDBRetryableError(
                    "OpenLigaDB could not be reached."
                )
            else:
                failure = self._http_error(response)
                if failure is None:
                    return response, attempt
            if (
                not isinstance(failure, OpenLigaDBRetryableError)
                or attempt == self._settings.max_attempts
            ):
                if cause is not None:
                    raise failure from cause
                raise failure
            self._sleep(self._retry_delay(response, attempt))
        raise AssertionError("Bounded OpenLigaDB retry loop did not terminate.")

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
    def _http_error(response: HttpResponse) -> OpenLigaDBRequestError | None:
        if response.status == 200:
            return None
        if response.status == 429 or 500 <= response.status <= 599:
            return OpenLigaDBRetryableError(
                f"OpenLigaDB returned HTTP {response.status}."
            )
        return OpenLigaDBRequestError(
            f"OpenLigaDB request failed with HTTP {response.status}."
        )

    def _parse_response(
        self, response: HttpResponse, attempts: int
    ) -> OpenLigaDBResponse:
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise OpenLigaDBSchemaError("Provider response exceeded the safe limit.")
        content_type = self._header(response.headers, "Content-Type")
        if content_type is None or "json" not in content_type.casefold():
            raise OpenLigaDBSchemaError("Provider returned an unexpected content type.")
        try:
            payload = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OpenLigaDBSchemaError("Provider returned malformed JSON.") from error
        if not isinstance(payload, list):
            raise OpenLigaDBSchemaError("Provider response root must be an array.")
        return OpenLigaDBResponse(
            payload=payload,
            fetched_at_utc=self._utc_now(),
            attempt_count=attempts,
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
                raise OpenLigaDBSchemaError(
                    "Provider returned invalid retry metadata."
                ) from error
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            seconds = (retry_at.astimezone(UTC) - self._utc_now()).total_seconds()
        return max(0.0, seconds)

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("OpenLigaDB clock must return an aware datetime.")
        return value.astimezone(UTC)

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str | None:
        expected = name.casefold()
        return next(
            (value for key, value in headers.items() if key.casefold() == expected),
            None,
        )
