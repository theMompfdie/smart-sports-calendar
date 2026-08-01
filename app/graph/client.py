import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.graph.authentication import GraphTokenProvider


class GraphClientError(RuntimeError):
    pass


class CalendarNotFoundError(GraphClientError):
    pass


class CalendarNotUniqueError(GraphClientError):
    pass


@dataclass(frozen=True)
class CalendarReference:
    id: str
    name: str


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
            f"{self._base_url}/users/{encoded_user_id}/calendars"
            "?$select=id,name"
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
            raise CalendarNotFoundError(
                f"Outlook calendar not found: {calendar_name}"
            )

        if len(matches) > 1:
            raise CalendarNotUniqueError(
                f"Multiple Outlook calendars found with name: {calendar_name}"
            )

        return matches[0]

    def _get_json(self, url: str) -> dict[str, object]:
        access_token = self._token_provider.get_access_token()
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as error:
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