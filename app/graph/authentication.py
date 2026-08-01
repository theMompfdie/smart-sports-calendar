from msal import ConfidentialClientApplication

GRAPH_SCOPE = "https://graph.microsoft.com/.default"


class GraphAuthenticationError(RuntimeError):
    pass


class GraphTokenProvider:
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        self._authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._client_id = client_id
        self._client_secret = client_secret
        self._application: ConfidentialClientApplication | None = None

    def get_access_token(self) -> str:
        application = self._get_application()
        result = application.acquire_token_for_client(
            scopes=[GRAPH_SCOPE],
        )

        access_token = result.get("access_token")

        if isinstance(access_token, str) and access_token:
            return access_token

        error = result.get("error_description") or result.get("error")
        raise GraphAuthenticationError(
            f"Microsoft Graph authentication failed: {error or 'unknown error'}"
        )

    def _get_application(self) -> ConfidentialClientApplication:
        if self._application is None:
            self._application = ConfidentialClientApplication(
                client_id=self._client_id,
                client_credential=self._client_secret,
                authority=self._authority,
            )

        return self._application
