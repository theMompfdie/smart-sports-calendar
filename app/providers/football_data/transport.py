from collections.abc import Mapping
from http.client import HTTPSConnection
from urllib.parse import urlsplit

from app.providers.api_football.transport import HttpResponse

MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class FootballDataStdlibTransport:
    """HTTPS transport that bounds the provider body before JSON parsing."""

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("football-data.org transport requires an HTTPS URL.")
        target = parsed.path or "/"
        if parsed.query:
            target = f"{target}?{parsed.query}"
        connection = HTTPSConnection(
            parsed.hostname, parsed.port, timeout=connect_timeout_seconds
        )
        try:
            connection.connect()
            if connection.sock is None:
                raise OSError("HTTPS connection did not create a socket.")
            connection.sock.settimeout(read_timeout_seconds)
            connection.request("GET", target, headers=dict(headers))
            response = connection.getresponse()
            return HttpResponse(
                status=response.status,
                headers=dict(response.getheaders()),
                body=response.read(MAX_RESPONSE_BYTES + 1),
            )
        finally:
            connection.close()
