import json
from io import BytesIO
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import pytest
from app.graph.client import (
    CalendarNotFoundError,
    CalendarNotUniqueError,
    GraphClient,
    GraphClientError,
)


def create_client() -> GraphClient:
    token_provider = Mock()
    token_provider.get_access_token.return_value = "test-token"

    return GraphClient(
        base_url="https://graph.microsoft.com/v1.0",
        user_id="user@example.com",
        token_provider=token_provider,
    )


def test_find_calendar_by_name_returns_matching_calendar() -> None:
    client = create_client()

    with patch.object(
        client,
        "_get_json",
        return_value={
            "value": [
                {"id": "calendar-1", "name": "Personal"},
                {"id": "calendar-2", "name": "SMART Sports Calendar"},
            ]
        },
    ):
        calendar = client.find_calendar_by_name("SMART Sports Calendar")

    assert calendar.id == "calendar-2"
    assert calendar.name == "SMART Sports Calendar"


def test_find_calendar_by_name_raises_when_calendar_is_missing() -> None:
    client = create_client()

    with (
        patch.object(
            client,
            "_get_json",
            return_value={"value": []},
        ),
        pytest.raises(
            CalendarNotFoundError,
            match="SMART Sports Calendar",
        ),
    ):
        client.find_calendar_by_name("SMART Sports Calendar")


def test_find_calendar_by_name_raises_for_duplicate_names() -> None:
    client = create_client()

    with (
        patch.object(
            client,
            "_get_json",
            return_value={
                "value": [
                    {"id": "calendar-1", "name": "SMART Sports Calendar"},
                    {"id": "calendar-2", "name": "SMART Sports Calendar"},
                ]
            },
        ),
        pytest.raises(
            CalendarNotUniqueError,
            match="Multiple Outlook calendars",
        ),
    ):
        client.find_calendar_by_name("SMART Sports Calendar")


def test_find_calendar_by_name_follows_next_link() -> None:
    client = create_client()
    next_link = "https://graph.microsoft.com/v1.0/next-page"

    with patch.object(
        client,
        "_get_json",
        side_effect=[
            {
                "value": [{"id": "calendar-1", "name": "Personal"}],
                "@odata.nextLink": next_link,
            },
            {
                "value": [
                    {
                        "id": "calendar-2",
                        "name": "SMART Sports Calendar",
                    }
                ]
            },
        ],
    ) as get_json:
        calendar = client.find_calendar_by_name("SMART Sports Calendar")

    assert calendar.id == "calendar-2"
    assert get_json.call_count == 2
    get_json.assert_any_call(next_link)


def test_find_calendar_by_name_rejects_invalid_response() -> None:
    client = create_client()

    with (
        patch.object(
            client,
            "_get_json",
            return_value={"value": "not-a-list"},
        ),
        pytest.raises(
            GraphClientError,
            match="invalid calendar response",
        ),
    ):
        client.find_calendar_by_name("SMART Sports Calendar")


def test_get_json_converts_http_error() -> None:
    client = create_client()
    error = HTTPError(
        url="https://graph.microsoft.com/v1.0/test",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=None,
    )

    with (
        patch("app.graph.client.urlopen", side_effect=error),
        pytest.raises(
            GraphClientError,
            match="HTTP 403",
        ),
    ):
        client._get_json("https://graph.microsoft.com/v1.0/test")


def test_get_json_converts_network_error() -> None:
    client = create_client()

    with (
        patch(
            "app.graph.client.urlopen",
            side_effect=URLError("connection failed"),
        ),
        pytest.raises(
            GraphClientError,
            match="could not be reached",
        ),
    ):
        client._get_json("https://graph.microsoft.com/v1.0/test")


def test_get_json_rejects_non_object_json() -> None:
    client = create_client()
    response = Mock()
    response.__enter__ = Mock(return_value=BytesIO(json.dumps([]).encode()))
    response.__exit__ = Mock(return_value=None)

    with (
        patch("app.graph.client.urlopen", return_value=response),
        pytest.raises(
            GraphClientError,
            match="unexpected response",
        ),
    ):
        client._get_json("https://graph.microsoft.com/v1.0/test")
