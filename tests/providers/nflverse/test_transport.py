from unittest.mock import MagicMock, patch

import pytest
from app.providers.nflverse.transport import MAX_RESPONSE_BYTES, NflverseStdlibTransport


def test_transport_bounds_body_and_applies_timeouts() -> None:
    connection = MagicMock()
    response = MagicMock(status=200)
    response.getheaders.return_value = [("Content-Type", "text/csv")]
    response.read.return_value = b"csv"
    connection.getresponse.return_value = response
    with patch(
        "app.providers.nflverse.transport.HTTPSConnection", return_value=connection
    ):
        result = NflverseStdlibTransport().get("https://github.com/file.csv", {}, 2, 9)
    connection.sock.settimeout.assert_called_once_with(9)
    response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
    assert result.body == b"csv"


def test_transport_requires_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        NflverseStdlibTransport().get("http://example.test", {}, 1, 1)
