from unittest.mock import Mock, patch

import pytest
from app.graph.authentication import (
    GRAPH_SCOPE,
    GraphAuthenticationError,
    GraphTokenProvider,
)


@patch("app.graph.authentication.ConfidentialClientApplication")
def test_provider_does_not_initialize_msal_during_construction(
    application_class: Mock,
) -> None:
    GraphTokenProvider(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
    )

    application_class.assert_not_called()


@patch("app.graph.authentication.ConfidentialClientApplication")
def test_get_access_token_returns_token(application_class: Mock) -> None:
    application = application_class.return_value
    application.acquire_token_for_client.return_value = {
        "access_token": "test-access-token"
    }

    provider = GraphTokenProvider(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
    )

    token = provider.get_access_token()

    assert token == "test-access-token"
    application_class.assert_called_once_with(
        client_id="test-client",
        client_credential="test-secret",
        authority="https://login.microsoftonline.com/test-tenant",
    )
    application.acquire_token_for_client.assert_called_once_with(
        scopes=[GRAPH_SCOPE],
    )


@patch("app.graph.authentication.ConfidentialClientApplication")
def test_get_access_token_raises_understandable_error(
    application_class: Mock,
) -> None:
    application = application_class.return_value
    application.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "The client secret is invalid.",
    }

    provider = GraphTokenProvider(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
    )

    with pytest.raises(
        GraphAuthenticationError,
        match="The client secret is invalid",
    ):
        provider.get_access_token()
