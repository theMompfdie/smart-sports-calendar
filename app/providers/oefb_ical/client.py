import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

from app.config.settings import OefbIcalSettings
from app.providers.api_football.transport import HttpResponse, HttpTransport
from app.providers.oefb_ical.exceptions import (
    OefbIcalConfigurationError,
    OefbIcalRequestError,
    OefbIcalRetryableError,
    OefbIcalSchemaError,
)
from app.providers.oefb_ical.transport import (
    ALLOWED_HOST,
    MAX_RESPONSE_BYTES,
    OefbIcalStdlibTransport,
)

MAX_REDIRECTS = 3
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


@dataclass(frozen=True)
class OefbIcalResponse:
    payload: bytes | None
    fetched_at_utc: datetime
    attempt_count: int
    last_modified: str | None
    not_modified: bool


class OefbIcalClient:
    def __init__(
        self,
        settings: OefbIcalSettings,
        transport: HttpTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not settings.enabled or not settings.feed_url:
            raise OefbIcalConfigurationError(
                "ÖFB iCalendar client requires enabled settings."
            )
        self._settings = settings
        self._transport = transport or OefbIcalStdlibTransport()
        self._sleep = sleep
        self._clock = clock or (lambda: datetime.now(UTC))

    def get(self, *, if_modified_since: str | None = None) -> OefbIcalResponse:
        headers = {"Accept": "text/calendar"}
        if if_modified_since is not None:
            self._parse_http_date(if_modified_since)
            headers["If-Modified-Since"] = if_modified_since
        response, attempts = self._request_with_retries(headers)
        if response.status == 304:
            if if_modified_since is None:
                raise OefbIcalSchemaError(
                    "Provider returned 304 without a validated conditional request."
                )
            return OefbIcalResponse(
                payload=None,
                fetched_at_utc=self._utc_now(),
                attempt_count=attempts,
                last_modified=if_modified_since,
                not_modified=True,
            )
        return self._parse_response(response, attempts)

    def _request_with_retries(
        self, headers: Mapping[str, str]
    ) -> tuple[HttpResponse, int]:
        for attempt in range(1, self._settings.max_attempts + 1):
            response: HttpResponse | None = None
            cause: BaseException | None = None
            try:
                response = self._request_following_safe_redirects(headers)
            except (OSError, TimeoutError) as error:
                cause = error
                failure: OefbIcalRequestError = OefbIcalRetryableError(
                    "ÖFB iCalendar provider could not be reached."
                )
            else:
                failure = self._http_error(response)
                if failure is None:
                    return response, attempt
            if (
                not isinstance(failure, OefbIcalRetryableError)
                or attempt == self._settings.max_attempts
            ):
                if cause is not None:
                    raise failure from cause
                raise failure
            self._sleep(self._retry_delay(response, attempt))
        raise AssertionError("Bounded ÖFB iCalendar retry loop did not terminate.")

    def _request_following_safe_redirects(
        self, headers: Mapping[str, str]
    ) -> HttpResponse:
        url = self._settings.feed_url
        for redirect_count in range(MAX_REDIRECTS + 1):
            self._validate_url(url)
            response = self._transport.get(
                url=url,
                headers=headers,
                connect_timeout_seconds=self._settings.connect_timeout_seconds,
                read_timeout_seconds=self._settings.read_timeout_seconds,
            )
            if response.status not in REDIRECT_STATUSES:
                return response
            location = self._header(response.headers, "Location")
            if location is None or redirect_count == MAX_REDIRECTS:
                raise OefbIcalRequestError(
                    "ÖFB iCalendar provider returned an invalid redirect chain."
                )
            url = urljoin(url, location)
        raise AssertionError("Bounded ÖFB iCalendar redirect loop did not terminate.")

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlsplit(url)
        try:
            port = parsed.port
        except ValueError as error:
            raise OefbIcalRequestError(
                "ÖFB iCalendar provider returned an unsafe redirect."
            ) from error
        if (
            parsed.scheme != "https"
            or parsed.hostname != ALLOWED_HOST
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not parsed.path
            or parsed.path == "/"
        ):
            raise OefbIcalRequestError(
                "ÖFB iCalendar provider returned an unsafe redirect."
            )

    @staticmethod
    def _http_error(response: HttpResponse) -> OefbIcalRequestError | None:
        if response.status in (200, 304):
            return None
        if response.status == 429 or 500 <= response.status <= 599:
            return OefbIcalRetryableError(
                f"ÖFB iCalendar provider returned HTTP {response.status}."
            )
        return OefbIcalRequestError(
            f"ÖFB iCalendar request failed with HTTP {response.status}."
        )

    def _parse_response(
        self, response: HttpResponse, attempts: int
    ) -> OefbIcalResponse:
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise OefbIcalSchemaError("Provider response exceeded the safe limit.")
        content_length = self._header(response.headers, "Content-Length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError as error:
                raise OefbIcalSchemaError(
                    "Provider returned an invalid content length."
                ) from error
            if declared_length != len(response.body):
                raise OefbIcalSchemaError(
                    "Provider response length did not match its metadata."
                )
        content_type = self._header(response.headers, "Content-Type")
        if content_type is None or content_type.split(";", 1)[0].strip().casefold() != (
            "text/calendar"
        ):
            raise OefbIcalSchemaError("Provider returned an unexpected content type.")
        last_modified = self._header(response.headers, "Last-Modified")
        if last_modified is not None:
            self._parse_http_date(last_modified)
        return OefbIcalResponse(
            payload=response.body,
            fetched_at_utc=self._utc_now(),
            attempt_count=attempts,
            last_modified=last_modified,
            not_modified=False,
        )

    def _retry_delay(self, response: HttpResponse | None, attempt: int) -> float:
        if response is not None:
            retry_after = self._header(response.headers, "Retry-After")
            if retry_after is not None:
                try:
                    seconds = float(retry_after)
                except ValueError:
                    seconds = (
                        self._parse_http_date(retry_after) - self._utc_now()
                    ).total_seconds()
                return min(max(0.0, seconds), self._settings.retry_max_delay_seconds)
        return min(
            self._settings.retry_base_delay_seconds * (2 ** (attempt - 1)),
            self._settings.retry_max_delay_seconds,
        )

    @staticmethod
    def _parse_http_date(value: str) -> datetime:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError) as error:
            raise OefbIcalSchemaError(
                "Provider returned invalid HTTP date metadata."
            ) from error
        if parsed.tzinfo is None:
            raise OefbIcalSchemaError("Provider returned invalid HTTP date metadata.")
        return parsed.astimezone(UTC)

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("ÖFB iCalendar clock must return an aware datetime.")
        return value.astimezone(UTC)

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str | None:
        expected = name.casefold()
        return next(
            (value for key, value in headers.items() if key.casefold() == expected),
            None,
        )
