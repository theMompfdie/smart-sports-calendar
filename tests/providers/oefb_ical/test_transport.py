from unittest.mock import MagicMock, patch

import pytest
from app.providers.oefb_ical.transport import (
    MAX_RESPONSE_BYTES,
    OefbIcalStdlibTransport,
)

from tests.providers.oefb_ical.support import FEED_URL


def test_transport_bounds_body_and_applies_separate_timeouts() -> None:
    connection = MagicMock()
    response = MagicMock()
    response.status = 200
    response.getheaders.return_value = [("Content-Type", "text/calendar")]
    response.read.return_value = b"calendar"
    connection.getresponse.return_value = response

    with patch(
        "app.providers.oefb_ical.transport.HTTPSConnection",
        return_value=connection,
    ) as connection_factory:
        result = OefbIcalStdlibTransport().get(
            FEED_URL,
            {"Accept": "text/calendar"},
            2.5,
            12.5,
        )

    connection_factory.assert_called_once_with(
        "www.fussballoesterreich.at", None, timeout=2.5
    )
    connection.sock.settimeout.assert_called_once_with(12.5)
    connection.request.assert_called_once_with(
        "GET",
        "/Calendar/opaque-test-token.ics",
        headers={"Accept": "text/calendar"},
    )
    response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
    connection.close.assert_called_once_with()
    assert result.body == b"calendar"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.fussballoesterreich.at/Calendar/token.ics",
        "https://example.test/Calendar/token.ics",
        "https://www.fussballoesterreich.at/Calendar/token.ics?secret=value",
        "https://www.fussballoesterreich.at/",
    ],
)
def test_transport_rejects_unsafe_url(url: str) -> None:
    with pytest.raises(ValueError, match="unsafe URL"):
        OefbIcalStdlibTransport().get(url, {}, 1, 1)
