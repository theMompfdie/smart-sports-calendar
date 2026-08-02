import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.graph.authentication import GraphTokenProvider
from app.synchronization.outlook_event_payload_builder import OutlookEventPayload


class GraphClientError(RuntimeError):
    pass


class OutlookEventNotFoundError(GraphClientError):
    pass


class CalendarNotFoundError(GraphClientError):
    pass


class CalendarNotUniqueError(GraphClientError):
    pass


@dataclass(frozen=True)
class CalendarReference:
    id: str
    name: str


@dataclass(frozen=True)
class OutlookEventReference:
    id: str


class GraphClient:
    def __init__(
        self,
        base_url: str,
        user_id: str,
        token_provider: GraphTokenProvider,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_id = user_id
        self._token_provider = token_provider

    def find_calendar_by_name(self, calendar_name: str) -> CalendarReference:
        encoded_user_id = quote(self._user_id, safe="")
        next_url: str | None = (
            f"{self._base_url}/users/{encoded_user_id}/calendars?$select=id,name"
        )
        matches: list[CalendarReference] = []

        while next_url:
            response = self._get_json(next_url)
            calendars = response.get("value")

            if not isinstance(calendars, list):
                raise GraphClientError(
                    "Microsoft Graph returned an invalid calendar response."
                )

            for calendar in calendars:
                if not isinstance(calendar, dict):
                    continue

                calendar_id = calendar.get("id")
                name = calendar.get("name")

                if (
                    name == calendar_name
                    and isinstance(calendar_id, str)
                    and calendar_id
                ):
                    matches.append(
                        CalendarReference(
                            id=calendar_id,
                            name=name,
                        )
                    )

            next_link = response.get("@odata.nextLink")
            next_url = next_link if isinstance(next_link, str) else None

        if not matches:
            raise CalendarNotFoundError(f"Outlook calendar not found: {calendar_name}")

        if len(matches) > 1:
            raise CalendarNotUniqueError(
                f"Multiple Outlook calendars found with name: {calendar_name}"
            )

        return matches[0]

    def create_event(
        self,
        calendar_id: str,
        payload: OutlookEventPayload,
    ) -> OutlookEventReference:
        response = self._send_json(
            url=self._event_collection_url(calendar_id),
            method="POST",
            payload=payload.to_graph_dict(),
        )

        return self._parse_event_reference(response)

    def update_event(
        self,
        calendar_id: str,
        event_id: str,
        payload: OutlookEventPayload,
    ) -> OutlookEventReference:
        response = self._send_json(
            url=self._event_url(calendar_id, event_id),
            method="PATCH",
            payload=payload.to_graph_dict(),
        )

        return self._parse_event_reference(response)

    def delete_event(
        self,
        calendar_id: str,
        event_id: str,
    ) -> None:
        self._send_empty(
            url=self._event_url(calendar_id, event_id),
            method="DELETE",
        )

    def _event_collection_url(self, calendar_id: str) -> str:
        encoded_user_id = quote(self._user_id, safe="")
        encoded_calendar_id = quote(calendar_id, safe="")

        return (
            f"{self._base_url}/users/{encoded_user_id}"
            f"/calendars/{encoded_calendar_id}/events"
        )

    def _event_url(
        self,
        calendar_id: str,
        event_id: str,
    ) -> str:
        encoded_event_id = quote(event_id, safe="")

        return f"{self._event_collection_url(calendar_id)}/{encoded_event_id}"

    def _get_json(self, url: str) -> dict[str, object]:
        request = self._build_request(
            url=url,
            method="GET",
        )

        return self._execute_json_request(request)

    def _send_json(
        self,
        url: str,
        method: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        request = self._build_request(
            url=url,
            method=method,
            payload=payload,
        )

        return self._execute_json_request(request)

    def _send_empty(
        self,
        url: str,
        method: str,
    ) -> None:
        request = self._build_request(
            url=url,
            method=method,
        )

        try:
            with urlopen(request, timeout=30) as response:
                response.read()
        except HTTPError as error:
            if error.code == 404:
                raise OutlookEventNotFoundError(
                    "Microsoft Graph Outlook event was not found."
                ) from error

            raise GraphClientError(
                f"Microsoft Graph request failed with HTTP {error.code}."
            ) from error
        except URLError as error:
            raise GraphClientError("Microsoft Graph could not be reached.") from error

    def _build_request(
        self,
        url: str,
        method: str,
        payload: dict[str, object] | None = None,
    ) -> Request:
        access_token = self._token_provider.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        data: bytes | None = None

        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

        return Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )

    def _execute_json_request(
        self,
        request: Request,
    ) -> dict[str, object]:
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as error:
            raise GraphClientError(
                f"Microsoft Graph request failed with HTTP {error.code}."
            ) from error
        except URLError as error:
            raise GraphClientError("Microsoft Graph could not be reached.") from error
        except json.JSONDecodeError as error:
            raise GraphClientError("Microsoft Graph returned invalid JSON.") from error

        if not isinstance(payload, dict):
            raise GraphClientError("Microsoft Graph returned an unexpected response.")

        return payload

    @staticmethod
    def _parse_event_reference(
        response: dict[str, object],
    ) -> OutlookEventReference:
        event_id = response.get("id")

        if not isinstance(event_id, str) or not event_id:
            raise GraphClientError(
                "Microsoft Graph returned an event response without a valid ID."
            )

        return OutlookEventReference(id=event_id)
