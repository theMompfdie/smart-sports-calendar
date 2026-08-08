from unittest.mock import MagicMock, patch

from app.providers.api_football.transport import StdlibHttpTransport


def test_stdlib_transport_applies_separate_connect_and_read_timeouts() -> None:
    connection = MagicMock()
    response = MagicMock()
    response.status = 200
    response.getheaders.return_value = [("Content-Type", "application/json")]
    response.read.return_value = b"{}"
    connection.getresponse.return_value = response

    with patch(
        "app.providers.api_football.transport.HTTPSConnection",
        return_value=connection,
    ) as connection_factory:
        result = StdlibHttpTransport().get(
            url="https://provider.example/fixtures?page=1",
            headers={"x-apisports-key": "provider-secret"},
            connect_timeout_seconds=2.5,
            read_timeout_seconds=12.5,
        )

    connection_factory.assert_called_once_with(
        host="provider.example",
        port=None,
        timeout=2.5,
    )
    connection.connect.assert_called_once_with()
    connection.sock.settimeout.assert_called_once_with(12.5)
    connection.request.assert_called_once_with(
        "GET",
        "/fixtures?page=1",
        headers={"x-apisports-key": "provider-secret"},
    )
    connection.close.assert_called_once_with()
    assert result.status == 200
    assert result.body == b"{}"


def test_stdlib_transport_rejects_non_https_url() -> None:
    transport = StdlibHttpTransport()

    try:
        transport.get(
            url="http://provider.example/fixtures",
            headers={},
            connect_timeout_seconds=2.5,
            read_timeout_seconds=12.5,
        )
    except ValueError as error:
        assert str(error) == "Provider transport requires an HTTPS URL."
    else:
        raise AssertionError("Expected non-HTTPS provider URL to be rejected.")
