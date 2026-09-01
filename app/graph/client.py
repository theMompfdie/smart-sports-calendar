import base64
import json
import math
import time
from collections.abc import Callable
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


class OutlookAttachmentNotFoundError(GraphClientError):
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


@dataclass(frozen=True)
class OutlookAttachmentReference:
    id: str
    content_id: str | None = None
    name: str | None = None


class GraphClient:
    def __init__(
        self,
        base_url: str,
        user_id: str,
        token_provider: GraphTokenProvider,
        *,
        attachment_max_attempts: int = 3,
        maximum_retry_after_seconds: int = 30,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if attachment_max_attempts < 1:
            raise ValueError("Attachment maximum attempts must be positive.")
        if maximum_retry_after_seconds < 0:
            raise ValueError("Maximum Retry-After must not be negative.")
        self._base_url = base_url.rstrip("/")
        self._user_id = user_id
        self._token_provider = token_provider
        self._attachment_max_attempts = attachment_max_attempts
        self._maximum_retry_after_seconds = maximum_retry_after_seconds
        self._sleeper = sleeper

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
                    isinstance(name, str)
                    and name == calendar_name
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
        transaction_id: str,
    ) -> OutlookEventReference:
        graph_payload = payload.to_graph_dict()
        graph_payload["transactionId"] = transaction_id

        response = self._send_json(
            url=self._event_collection_url(calendar_id),
            method="POST",
            payload=graph_payload,
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

    def create_inline_attachment(
        self,
        calendar_id: str,
        event_id: str,
        *,
        name: str,
        content_id: str,
        content: bytes,
        content_type: str = "image/png",
    ) -> OutlookAttachmentReference:
        if not name or name != name.strip() or len(name) > 255:
            raise ValueError("Attachment name is invalid.")
        if not content_id or content_id != content_id.strip() or len(content_id) > 255:
            raise ValueError("Attachment content ID is invalid.")
        if content_type != "image/png":
            raise ValueError("Inline media attachments must use PNG.")
        if not content or len(content) >= 3_000_000:
            raise ValueError("Inline attachment must be smaller than 3 MB.")
        payload: dict[str, object] = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": name,
            "contentType": content_type,
            "contentId": content_id,
            "isInline": True,
            "contentBytes": base64.b64encode(content).decode("ascii"),
        }
        response = self._send_attachment_json(
            url=self._attachment_collection_url(calendar_id, event_id),
            method="POST",
            payload=payload,
        )
        return self._parse_attachment_reference(response)

    def list_event_attachments(
        self,
        calendar_id: str,
        event_id: str,
        *,
        maximum_pages: int = 10,
    ) -> tuple[OutlookAttachmentReference, ...]:
        if maximum_pages < 1:
            raise ValueError("Attachment page limit must be positive.")
        next_url: str | None = (
            f"{self._attachment_collection_url(calendar_id, event_id)}"
            "?$select=id,name,contentId,isInline"
        )
        attachments: list[OutlookAttachmentReference] = []
        pages = 0
        while next_url is not None:
            pages += 1
            if pages > maximum_pages:
                raise GraphClientError(
                    "Microsoft Graph attachment paging exceeded limit."
                )
            response = self._get_attachment_json(next_url)
            values = response.get("value")
            if not isinstance(values, list):
                raise GraphClientError(
                    "Microsoft Graph returned an invalid attachment response."
                )
            for value in values:
                if not isinstance(value, dict):
                    continue
                attachment_id = value.get("id")
                if not isinstance(attachment_id, str) or not attachment_id:
                    continue
                content_id = value.get("contentId")
                name = value.get("name")
                attachments.append(
                    OutlookAttachmentReference(
                        id=attachment_id,
                        content_id=content_id if isinstance(content_id, str) else None,
                        name=name if isinstance(name, str) else None,
                    )
                )
            link = response.get("@odata.nextLink")
            next_url = link if isinstance(link, str) and link else None
        return tuple(attachments)

    def delete_event_attachment(
        self,
        calendar_id: str,
        event_id: str,
        attachment_id: str,
    ) -> None:
        encoded_attachment_id = quote(attachment_id, safe="")
        url = (
            f"{self._attachment_collection_url(calendar_id, event_id)}"
            f"/{encoded_attachment_id}"
        )
        self._send_attachment_empty(url=url, method="DELETE")

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

    def _attachment_collection_url(self, calendar_id: str, event_id: str) -> str:
        return f"{self._event_url(calendar_id, event_id)}/attachments"

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

    def _get_attachment_json(self, url: str) -> dict[str, object]:
        return self._execute_attachment_json(
            lambda: self._build_request(url=url, method="GET")
        )

    def _send_attachment_json(
        self,
        *,
        url: str,
        method: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return self._execute_attachment_json(
            lambda: self._build_request(url=url, method=method, payload=payload)
        )

    def _send_attachment_empty(self, *, url: str, method: str) -> None:
        for attempt in range(1, self._attachment_max_attempts + 1):
            request = self._build_request(url=url, method=method)
            try:
                with urlopen(request, timeout=30) as response:
                    response.read()
                return
            except HTTPError as error:
                if error.code == 404:
                    raise OutlookAttachmentNotFoundError(
                        "Microsoft Graph Outlook attachment was not found."
                    ) from error
                if not self._retry_attachment(error, attempt):
                    raise GraphClientError(
                        f"Microsoft Graph request failed with HTTP {error.code}."
                    ) from error
            except URLError as error:
                raise GraphClientError(
                    "Microsoft Graph could not be reached."
                ) from error

    def _execute_attachment_json(
        self,
        request_factory: Callable[[], Request],
    ) -> dict[str, object]:
        for attempt in range(1, self._attachment_max_attempts + 1):
            try:
                with urlopen(request_factory(), timeout=30) as response:
                    payload = json.load(response)
            except HTTPError as error:
                if self._retry_attachment(error, attempt):
                    continue
                raise GraphClientError(
                    f"Microsoft Graph request failed with HTTP {error.code}."
                ) from error
            except URLError as error:
                raise GraphClientError(
                    "Microsoft Graph could not be reached."
                ) from error
            except json.JSONDecodeError as error:
                raise GraphClientError(
                    "Microsoft Graph returned invalid JSON."
                ) from error
            if not isinstance(payload, dict):
                raise GraphClientError(
                    "Microsoft Graph returned an unexpected response."
                )
            return payload
        raise GraphClientError("Microsoft Graph attachment retry limit was exhausted.")

    def _retry_attachment(self, error: HTTPError, attempt: int) -> bool:
        if error.code not in {429, 503, 504}:
            return False
        if attempt >= self._attachment_max_attempts:
            return False
        retry_after = error.headers.get("Retry-After") if error.headers else None
        try:
            requested_delay = (
                float(retry_after) if retry_after is not None else 2 ** (attempt - 1)
            )
        except ValueError:
            requested_delay = 2 ** (attempt - 1)
        if not math.isfinite(requested_delay):
            requested_delay = 2 ** (attempt - 1)
        delay = min(max(requested_delay, 0), self._maximum_retry_after_seconds)
        self._sleeper(delay)
        return True

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

    @staticmethod
    def _parse_attachment_reference(
        response: dict[str, object],
    ) -> OutlookAttachmentReference:
        attachment_id = response.get("id")
        if not isinstance(attachment_id, str) or not attachment_id:
            raise GraphClientError(
                "Microsoft Graph returned an attachment without a valid ID."
            )
        content_id = response.get("contentId")
        name = response.get("name")
        return OutlookAttachmentReference(
            id=attachment_id,
            content_id=content_id if isinstance(content_id, str) else None,
            name=name if isinstance(name, str) else None,
        )
