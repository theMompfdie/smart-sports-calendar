import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from app.providers.api_football.transport import HttpResponse, HttpTransport
from app.providers.nflverse.exceptions import (
    NflverseRequestError,
    NflverseRetryableError,
    NflverseSchemaError,
)
from app.providers.nflverse.transport import MAX_RESPONSE_BYTES, NflverseStdlibTransport

SCHEDULE_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
)
ALLOWED_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
)
ALLOWED_CONTENT_TYPES = frozenset(
    {"text/csv", "application/csv", "application/octet-stream"}
)


@dataclass(frozen=True)
class NflverseResponse:
    body: bytes
    fetched_at_utc: datetime
    attempt_count: int
    final_url: str


class NflverseClient:
    def __init__(
        self,
        transport: HttpTransport | None = None,
        *,
        max_attempts: int = 3,
        max_redirects: int = 3,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_attempts < 1 or max_redirects < 0:
            raise ValueError("nflverse retry and redirect bounds are invalid.")
        self._transport = transport or NflverseStdlibTransport()
        self._max_attempts = max_attempts
        self._max_redirects = max_redirects
        self._connect_timeout_seconds = connect_timeout_seconds
        self._read_timeout_seconds = read_timeout_seconds
        self._sleep = sleep
        self._clock = clock or (lambda: datetime.now(UTC))

    def fetch_schedule(self) -> NflverseResponse:
        url = SCHEDULE_URL
        attempts = 0
        redirects = 0
        while True:
            response: HttpResponse | None = None
            try:
                attempts += 1
                response = self._transport.get(
                    url,
                    {"Accept": "text/csv, application/octet-stream"},
                    self._connect_timeout_seconds,
                    self._read_timeout_seconds,
                )
            except (OSError, TimeoutError) as error:
                if attempts >= self._max_attempts:
                    raise NflverseRetryableError(
                        "nflverse could not be reached."
                    ) from error
                self._sleep(float(2 ** (attempts - 1)))
                continue
            if response.status in {301, 302, 303, 307, 308}:
                redirects += 1
                if redirects > self._max_redirects:
                    raise NflverseRequestError("nflverse exceeded the redirect limit.")
                location = self._header(response.headers, "Location")
                if location is None:
                    raise NflverseSchemaError("nflverse redirect has no location.")
                url = urljoin(url, location)
                self._validate_url(url)
                continue
            if response.status == 200:
                break
            if response.status == 429 or 500 <= response.status <= 599:
                if attempts >= self._max_attempts:
                    raise NflverseRetryableError(
                        f"nflverse returned HTTP {response.status}."
                    )
                self._sleep(float(2 ** (attempts - 1)))
                continue
            raise NflverseRequestError(f"nflverse returned HTTP {response.status}.")
        if len(response.body) > MAX_RESPONSE_BYTES:
            raise NflverseSchemaError("nflverse response exceeded the safe limit.")
        content_type = self._header(response.headers, "Content-Type")
        if (
            content_type is None
            or content_type.split(";", 1)[0].strip() not in ALLOWED_CONTENT_TYPES
        ):
            raise NflverseSchemaError("nflverse returned an unexpected content type.")
        try:
            response.body.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise NflverseSchemaError("nflverse returned non-UTF-8 CSV.") from error
        return NflverseResponse(response.body, self._utc_now(), attempts, url)

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
            raise NflverseRequestError("nflverse redirected outside approved hosts.")

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("nflverse clock must return an aware datetime.")
        return value.astimezone(UTC)

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str | None:
        expected = name.casefold()
        return next((v for k, v in headers.items() if k.casefold() == expected), None)
