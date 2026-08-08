from pathlib import Path

import pytest
from app.config.settings import load_settings
from app.providers.api_football.exceptions import ProviderConfigurationError


@pytest.fixture(autouse=True)
def configure_required_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("M365_TENANT_ID", "tenant-id")
    monkeypatch.setenv("M365_CLIENT_ID", "client-id")
    monkeypatch.setenv("M365_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("M365_USER_ID", "user-id")
    monkeypatch.setenv("OUTLOOK_CALENDAR_ID", "calendar-1")

    monkeypatch.delenv(
        "SYNCHRONIZATION_BATCH_LIMIT",
        raising=False,
    )
    monkeypatch.delenv(
        "HEARTBEAT_INTERVAL",
        raising=False,
    )
    for name in (
        "API_FOOTBALL_ENABLED",
        "API_FOOTBALL_API_KEY",
        "API_FOOTBALL_BASE_URL",
        "API_FOOTBALL_CONNECT_TIMEOUT_SECONDS",
        "API_FOOTBALL_READ_TIMEOUT_SECONDS",
        "API_FOOTBALL_MAX_ATTEMPTS",
        "API_FOOTBALL_RETRY_BASE_DELAY_SECONDS",
        "API_FOOTBALL_RETRY_MAX_DELAY_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_load_settings_loads_synchronization_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "OUTLOOK_CALENDAR_ID",
        "calendar-2",
    )
    monkeypatch.setenv(
        "SYNCHRONIZATION_BATCH_LIMIT",
        "250",
    )

    settings = load_settings()

    assert settings.outlook_calendar_id == "calendar-2"
    assert settings.synchronization_batch_limit == 250


def test_load_settings_uses_default_synchronization_batch_limit() -> None:
    settings = load_settings()

    assert settings.synchronization_batch_limit == 100


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
    ],
)
def test_load_settings_rejects_non_positive_batch_limit(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv(
        "SYNCHRONIZATION_BATCH_LIMIT",
        value,
    )

    with pytest.raises(
        ValueError,
        match=("SYNCHRONIZATION_BATCH_LIMIT must be greater than zero"),
    ):
        load_settings()


def test_load_settings_rejects_invalid_batch_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SYNCHRONIZATION_BATCH_LIMIT",
        "invalid",
    )

    with pytest.raises(
        ValueError,
        match="SYNCHRONIZATION_BATCH_LIMIT must be an integer",
    ):
        load_settings()


def test_load_settings_rejects_empty_outlook_calendar_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "OUTLOOK_CALENDAR_ID",
        "   ",
    )

    with pytest.raises(
        ValueError,
        match="OUTLOOK_CALENDAR_ID must be configured",
    ):
        load_settings()


def test_load_settings_uses_default_heartbeat_interval() -> None:
    settings = load_settings()

    assert settings.heartbeat_interval == 300


def test_load_settings_loads_custom_heartbeat_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "HEARTBEAT_INTERVAL",
        "600",
    )

    settings = load_settings()

    assert settings.heartbeat_interval == 600


def test_load_settings_loads_default_database_path() -> None:
    settings = load_settings()

    assert settings.database_path == Path("/data/sports.db")


def test_load_settings_disables_api_football_by_default() -> None:
    settings = load_settings()

    assert settings.api_football.enabled is False
    assert settings.api_football.api_key == ""
    assert settings.api_football.base_url == "https://v3.football.api-sports.io"
    assert settings.api_football.connect_timeout_seconds == 5.0
    assert settings.api_football.read_timeout_seconds == 30.0
    assert settings.api_football.max_attempts == 3


def test_load_settings_loads_api_football_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_FOOTBALL_ENABLED", "true")
    monkeypatch.setenv("API_FOOTBALL_API_KEY", "provider-secret")
    monkeypatch.setenv("API_FOOTBALL_BASE_URL", "https://provider.example/v3/")
    monkeypatch.setenv("API_FOOTBALL_CONNECT_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("API_FOOTBALL_READ_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("API_FOOTBALL_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("API_FOOTBALL_RETRY_BASE_DELAY_SECONDS", "0.5")
    monkeypatch.setenv("API_FOOTBALL_RETRY_MAX_DELAY_SECONDS", "8")

    settings = load_settings().api_football

    assert settings.enabled is True
    assert settings.api_key == "provider-secret"
    assert settings.base_url == "https://provider.example/v3"
    assert settings.connect_timeout_seconds == 2.5
    assert settings.read_timeout_seconds == 12.5
    assert settings.max_attempts == 4
    assert settings.retry_base_delay_seconds == 0.5
    assert settings.retry_max_delay_seconds == 8.0
    assert "provider-secret" not in repr(settings)


def test_load_settings_requires_api_key_when_provider_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_FOOTBALL_ENABLED", "true")

    with pytest.raises(
        ProviderConfigurationError,
        match="API_FOOTBALL_API_KEY must be configured",
    ):
        load_settings()


@pytest.mark.parametrize(
    "base_url",
    [
        "http://provider.example",
        "https://user:secret@provider.example",
        "https://provider.example?key=secret",
        "https://provider.example#fragment",
        "https://provider.example:invalid",
        "not-a-url",
    ],
)
def test_load_settings_rejects_unsafe_api_football_base_url(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    monkeypatch.setenv("API_FOOTBALL_BASE_URL", base_url)

    with pytest.raises(
        ProviderConfigurationError,
        match="API_FOOTBALL_BASE_URL must be an HTTPS URL",
    ):
        load_settings()


@pytest.mark.parametrize(
    "name,value",
    [
        ("API_FOOTBALL_CONNECT_TIMEOUT_SECONDS", "0"),
        ("API_FOOTBALL_READ_TIMEOUT_SECONDS", "-1"),
        ("API_FOOTBALL_READ_TIMEOUT_SECONDS", "nan"),
        ("API_FOOTBALL_READ_TIMEOUT_SECONDS", "inf"),
        ("API_FOOTBALL_RETRY_BASE_DELAY_SECONDS", "invalid"),
        ("API_FOOTBALL_RETRY_MAX_DELAY_SECONDS", "0"),
    ],
)
def test_load_settings_rejects_invalid_api_football_numeric_setting(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ProviderConfigurationError, match=name):
        load_settings()


def test_load_settings_rejects_excessive_api_football_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_FOOTBALL_MAX_ATTEMPTS", "11")

    with pytest.raises(
        ProviderConfigurationError,
        match="API_FOOTBALL_MAX_ATTEMPTS must not exceed 10",
    ):
        load_settings()


@pytest.mark.parametrize(
    "name,value",
    [
        ("API_FOOTBALL_ENABLED", "sometimes"),
        ("API_FOOTBALL_MAX_ATTEMPTS", "invalid"),
        ("API_FOOTBALL_MAX_ATTEMPTS", "0"),
    ],
)
def test_load_settings_classifies_invalid_provider_values_as_configuration_errors(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ProviderConfigurationError, match=name):
        load_settings()


def test_load_settings_rejects_retry_max_delay_below_base_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_FOOTBALL_RETRY_BASE_DELAY_SECONDS", "5")
    monkeypatch.setenv("API_FOOTBALL_RETRY_MAX_DELAY_SECONDS", "4")

    with pytest.raises(
        ProviderConfigurationError,
        match="API_FOOTBALL_RETRY_MAX_DELAY_SECONDS must be greater",
    ):
        load_settings()
