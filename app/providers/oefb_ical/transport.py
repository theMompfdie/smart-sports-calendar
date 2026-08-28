from collections.abc import Mapping
from http.client import HTTPSConnection
from urllib.parse import urlsplit

from app.providers.api_football.transport import HttpResponse

ALLOWED_HOST = "www.fussballoesterreich.at"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class OefbIcalStdlibTransport:
    """HTTPS transport with an exact host and bounded response body."""

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != ALLOWED_HOST
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not parsed.path
            or parsed.path == "/"
        ):
            raise ValueError("ÖFB iCalendar transport rejected an unsafe URL.")
        connection = HTTPSConnection(
            ALLOWED_HOST,
            parsed.port,
            timeout=connect_timeout_seconds,
        )
        try:
            connection.connect()
            if connection.sock is None:
                raise OSError("HTTPS connection did not create a socket.")
            connection.sock.settimeout(read_timeout_seconds)
            connection.request("GET", parsed.path, headers=dict(headers))
            response = connection.getresponse()
            return HttpResponse(
                status=response.status,
                headers=dict(response.getheaders()),
                body=response.read(MAX_RESPONSE_BYTES + 1),
            )
        finally:
            connection.close()
