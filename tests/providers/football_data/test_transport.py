from unittest.mock import MagicMock, patch

import pytest
from app.providers.football_data.transport import (
    MAX_RESPONSE_BYTES,
    FootballDataStdlibTransport,
)


def test_transport_bounds_body_and_applies_separate_timeouts() -> None:
    connection = MagicMock()
    response = MagicMock()
    response.status = 200
    response.getheaders.return_value = [("Content-Type", "application/json")]
    response.read.return_value = b"{}"
    connection.getresponse.return_value = response

    with patch(
        "app.providers.football_data.transport.HTTPSConnection",
        return_value=connection,
    ) as connection_factory:
        result = FootballDataStdlibTransport().get(
            "https://api.football-data.org/v4/competitions/PL?season=2026",
            {"X-Auth-Token": "provider-secret"},
            2.5,
            12.5,
        )

    connection_factory.assert_called_once_with(
        "api.football-data.org", None, timeout=2.5
    )
    connection.sock.settimeout.assert_called_once_with(12.5)
    connection.request.assert_called_once_with(
        "GET",
        "/v4/competitions/PL?season=2026",
        headers={"X-Auth-Token": "provider-secret"},
    )
    response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
    connection.close.assert_called_once_with()
    assert result.body == b"{}"


def test_transport_rejects_non_https_url() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        FootballDataStdlibTransport().get("http://example.test", {}, 1, 1)
