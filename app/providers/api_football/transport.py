from collections.abc import Mapping
from dataclasses import dataclass
from http.client import HTTPSConnection
from typing import Protocol
from urllib.parse import urlsplit


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse: ...


class StdlibHttpTransport:
    """Small HTTPS transport with separate connect and read timeouts."""

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        parsed_url = urlsplit(url)

        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise ValueError("Provider transport requires an HTTPS URL.")

        target = parsed_url.path or "/"
        if parsed_url.query:
            target = f"{target}?{parsed_url.query}"

        connection = HTTPSConnection(
            host=parsed_url.hostname,
            port=parsed_url.port,
            timeout=connect_timeout_seconds,
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
                body=response.read(),
            )
        finally:
            connection.close()
