from pathlib import Path

import pytest
from app.config.settings import load_settings


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
