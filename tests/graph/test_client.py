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
    OutlookEventNotFoundError,
    OutlookEventReference,
)
from app.synchronization.outlook_event_payload_builder import (
    OutlookDateTime,
    OutlookEventPayload,
)

TRANSACTION_ID = "11111111-2222-4333-8444-555555555555"


def create_client() -> GraphClient:
    token_provider = Mock()
    token_provider.get_access_token.return_value = "test-token"

    return GraphClient(
        base_url="https://graph.microsoft.com/v1.0",
        user_id="user@example.com",
        token_provider=token_provider,
    )


def create_event_payload() -> OutlookEventPayload:
    return OutlookEventPayload(
        subject="Austria Wien – Rapid Wien",
        body="Status: scheduled\nSport: Football",
        start=OutlookDateTime(
            date_time="2026-08-21T19:00:00",
            time_zone="Europe/Vienna",
        ),
        end=OutlookDateTime(
            date_time="2026-08-21T21:00:00",
            time_zone="Europe/Vienna",
        ),
        location="Vienna",
        categories=(
            "Football",
            "Austrian Bundesliga",
            "SMART Sports Calendar",
        ),
        is_all_day=False,
        is_reminder_on=True,
        reminder_minutes_before_start=60,
        show_as="busy",
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


def test_create_event_sends_complete_payload_and_returns_reference() -> None:
    client = create_client()
    payload = create_event_payload()

    with patch.object(
        client,
        "_send_json",
        return_value={"id": "outlook-event-1"},
    ) as send_json:
        event = client.create_event(
            calendar_id="calendar/one",
            payload=payload,
            transaction_id=TRANSACTION_ID,
        )

    expected_payload = payload.to_graph_dict()
    expected_payload["transactionId"] = TRANSACTION_ID

    assert event == OutlookEventReference(id="outlook-event-1")
    send_json.assert_called_once_with(
        url=(
            "https://graph.microsoft.com/v1.0/"
            "users/user%40example.com/"
            "calendars/calendar%2Fone/events"
        ),
        method="POST",
        payload=expected_payload,
    )

    assert "transactionId" not in payload.to_graph_dict()


def test_update_event_sends_complete_payload_and_returns_reference() -> None:
    client = create_client()
    payload = create_event_payload()

    with patch.object(
        client,
        "_send_json",
        return_value={"id": "outlook-event-1"},
    ) as send_json:
        event = client.update_event(
            calendar_id="calendar/one",
            event_id="event/one",
            payload=payload,
        )

    assert event == OutlookEventReference(id="outlook-event-1")
    send_json.assert_called_once_with(
        url=(
            "https://graph.microsoft.com/v1.0/"
            "users/user%40example.com/"
            "calendars/calendar%2Fone/events/event%2Fone"
        ),
        method="PATCH",
        payload=payload.to_graph_dict(),
    )


def test_delete_event_sends_delete_request() -> None:
    client = create_client()

    with patch.object(client, "_send_empty") as send_empty:
        result = client.delete_event(
            calendar_id="calendar/one",
            event_id="event/one",
        )

    assert result is None
    send_empty.assert_called_once_with(
        url=(
            "https://graph.microsoft.com/v1.0/"
            "users/user%40example.com/"
            "calendars/calendar%2Fone/events/event%2Fone"
        ),
        method="DELETE",
    )


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"id": None},
        {"id": ""},
        {"id": 123},
    ],
)
def test_create_event_rejects_response_without_valid_event_id(
    response: dict[str, object],
) -> None:
    client = create_client()

    with (
        patch.object(
            client,
            "_send_json",
            return_value=response,
        ),
        pytest.raises(
            GraphClientError,
            match="without a valid ID",
        ),
    ):
        client.create_event(
            calendar_id="calendar-1",
            payload=create_event_payload(),
            transaction_id=TRANSACTION_ID,
        )


def test_update_event_rejects_response_without_valid_event_id() -> None:
    client = create_client()

    with (
        patch.object(
            client,
            "_send_json",
            return_value={},
        ),
        pytest.raises(
            GraphClientError,
            match="without a valid ID",
        ),
    ):
        client.update_event(
            calendar_id="calendar-1",
            event_id="event-1",
            payload=create_event_payload(),
        )


def test_create_event_builds_authenticated_json_request() -> None:
    client = create_client()
    payload = create_event_payload()
    response_body = BytesIO(json.dumps({"id": "outlook-event-1"}).encode("utf-8"))
    response = Mock()
    response.__enter__ = Mock(return_value=response_body)
    response.__exit__ = Mock(return_value=None)

    with patch(
        "app.graph.client.urlopen",
        return_value=response,
    ) as urlopen_mock:
        event = client.create_event(
            calendar_id="calendar-1",
            payload=payload,
            transaction_id=TRANSACTION_ID,
        )

    request = urlopen_mock.call_args.args[0]

    assert event.id == "outlook-event-1"
    assert request.method == "POST"
    assert request.full_url.endswith(
        "/users/user%40example.com/calendars/calendar-1/events"
    )
    assert request.get_header("Authorization") == "Bearer test-token"
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("Content-type") == "application/json"
    expected_payload = payload.to_graph_dict()
    expected_payload["transactionId"] = TRANSACTION_ID

    assert json.loads(request.data.decode("utf-8")) == expected_payload
    assert "transactionId" not in payload.to_graph_dict()
    urlopen_mock.assert_called_once_with(request, timeout=30)


def test_delete_event_accepts_empty_success_response() -> None:
    client = create_client()
    response_body = BytesIO(b"")
    response = Mock()
    response.__enter__ = Mock(return_value=response_body)
    response.__exit__ = Mock(return_value=None)

    with patch(
        "app.graph.client.urlopen",
        return_value=response,
    ) as urlopen_mock:
        result = client.delete_event(
            calendar_id="calendar-1",
            event_id="event-1",
        )

    request = urlopen_mock.call_args.args[0]

    assert result is None
    assert request.method == "DELETE"
    assert request.data is None
    assert request.full_url.endswith(
        "/users/user%40example.com/calendars/calendar-1/events/event-1"
    )
    urlopen_mock.assert_called_once_with(request, timeout=30)


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
    response.__enter__ = Mock(return_value=BytesIO(json.dumps([]).encode("utf-8")))
    response.__exit__ = Mock(return_value=None)

    with (
        patch("app.graph.client.urlopen", return_value=response),
        pytest.raises(
            GraphClientError,
            match="unexpected response",
        ),
    ):
        client._get_json("https://graph.microsoft.com/v1.0/test")


def test_create_event_converts_http_error() -> None:
    client = create_client()
    error = HTTPError(
        url="https://graph.microsoft.com/v1.0/test",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=None,
    )

    with (
        patch("app.graph.client.urlopen", side_effect=error),
        pytest.raises(
            GraphClientError,
            match="HTTP 400",
        ),
    ):
        client.create_event(
            calendar_id="calendar-1",
            payload=create_event_payload(),
            transaction_id=TRANSACTION_ID,
        )


def test_update_event_converts_network_error() -> None:
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
        client.update_event(
            calendar_id="calendar-1",
            event_id="event-1",
            payload=create_event_payload(),
        )


def test_delete_event_converts_not_found_error() -> None:
    client = create_client()
    error = HTTPError(
        url="https://graph.microsoft.com/v1.0/test",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=None,
    )

    with (
        patch("app.graph.client.urlopen", side_effect=error),
        pytest.raises(
            OutlookEventNotFoundError,
            match="Outlook event was not found",
        ),
    ):
        client.delete_event(
            calendar_id="calendar-1",
            event_id="event-1",
        )


def test_delete_event_converts_other_http_error() -> None:
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
        client.delete_event(
            calendar_id="calendar-1",
            event_id="event-1",
        )


def test_delete_event_converts_network_error() -> None:
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
        client.delete_event(
            calendar_id="calendar-1",
            event_id="event-1",
        )
