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
        authority = f"https://login.microsoftonline.com/{tenant_id}"

        self._application = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=authority,
        )

    def get_access_token(self) -> str:
        result = self._application.acquire_token_for_client(
            scopes=[GRAPH_SCOPE],
        )

        access_token = result.get("access_token")

        if isinstance(access_token, str) and access_token:
            return access_token

        error = result.get("error_description") or result.get("error")
        raise GraphAuthenticationError(
            f"Microsoft Graph authentication failed: {error or 'unknown error'}"
        )
