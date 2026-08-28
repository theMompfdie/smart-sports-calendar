import json
from pathlib import Path

import pytest
from app.config.settings import load_settings
from app.providers.api_football.exceptions import ProviderConfigurationError
from app.providers.contracts import SourceConfigurationError, SourceRole


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
    monkeypatch.delenv(
        "INSTANCE_NAME",
        raising=False,
    )
    monkeypatch.delenv("SOURCE_JOBS_JSON", raising=False)
    for name in (
        "API_FOOTBALL_ENABLED",
        "API_FOOTBALL_API_KEY",
        "API_FOOTBALL_BASE_URL",
        "API_FOOTBALL_CONNECT_TIMEOUT_SECONDS",
        "API_FOOTBALL_READ_TIMEOUT_SECONDS",
        "API_FOOTBALL_MAX_ATTEMPTS",
        "API_FOOTBALL_RETRY_BASE_DELAY_SECONDS",
        "API_FOOTBALL_RETRY_MAX_DELAY_SECONDS",
        "API_FOOTBALL_IMPORT_INTERVAL_SECONDS",
        "FOOTBALL_DATA_ENABLED",
        "FOOTBALL_DATA_API_KEY",
        "FOOTBALL_DATA_BASE_URL",
        "FOOTBALL_DATA_CONNECT_TIMEOUT_SECONDS",
        "FOOTBALL_DATA_READ_TIMEOUT_SECONDS",
        "FOOTBALL_DATA_MAX_ATTEMPTS",
        "FOOTBALL_DATA_RETRY_BASE_DELAY_SECONDS",
        "FOOTBALL_DATA_RETRY_MAX_DELAY_SECONDS",
        "FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS",
        "FOOTBALL_DATA_REQUESTS_PER_MINUTE",
        "OPENLIGADB_ENABLED",
        "OPENLIGADB_BASE_URL",
        "OPENLIGADB_CONNECT_TIMEOUT_SECONDS",
        "OPENLIGADB_READ_TIMEOUT_SECONDS",
        "OPENLIGADB_MAX_ATTEMPTS",
        "OPENLIGADB_RETRY_BASE_DELAY_SECONDS",
        "OPENLIGADB_RETRY_MAX_DELAY_SECONDS",
        "OPENLIGADB_MINIMUM_REQUEST_INTERVAL_SECONDS",
        "OEFB_ICAL_ENABLED",
        "OEFB_ICAL_FEED_URL",
        "OEFB_ICAL_CONNECT_TIMEOUT_SECONDS",
        "OEFB_ICAL_READ_TIMEOUT_SECONDS",
        "OEFB_ICAL_MAX_ATTEMPTS",
        "OEFB_ICAL_RETRY_BASE_DELAY_SECONDS",
        "OEFB_ICAL_RETRY_MAX_DELAY_SECONDS",
        "OEFB_ICAL_MINIMUM_POLL_INTERVAL_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_load_settings_validates_football_data_authority_and_plan_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOOTBALL_DATA_ENABLED", "true")
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "secret-token")
    monkeypatch.setenv(
        "SOURCE_JOBS_JSON",
        json.dumps(
            [
                {
                    "job_key": "football-data-premier-league",
                    "source_key": "football_data",
                    "sport_key": "football",
                    "competition_key": "premier_league",
                    "season_key": "2026_27",
                    "role": "authoritative",
                    "interval_seconds": 3600,
                }
            ]
        ),
    )

    settings = load_settings()

    assert settings.football_data.enabled is True
    assert settings.football_data.api_key == "secret-token"
    assert settings.football_data.requests_per_minute == 10
    assert "secret-token" not in repr(settings.football_data)


def test_load_settings_rejects_football_data_rate_above_approved_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOOTBALL_DATA_REQUESTS_PER_MINUTE", "11")

    with pytest.raises(ProviderConfigurationError, match="plan limit"):
        load_settings()


def test_load_settings_validates_public_openligadb_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENLIGADB_ENABLED", "true")
    monkeypatch.setenv("OPENLIGADB_MINIMUM_REQUEST_INTERVAL_SECONDS", "2.5")

    settings = load_settings()

    assert settings.openligadb.enabled is True
    assert settings.openligadb.base_url == "https://api.openligadb.de"
    assert settings.openligadb.minimum_request_interval_seconds == 2.5


def test_load_settings_rejects_unsafe_openligadb_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENLIGADB_BASE_URL", "http://api.openligadb.de")

    with pytest.raises(ProviderConfigurationError, match="HTTPS URL"):
        load_settings()


def test_load_settings_validates_secret_oefb_ical_feed_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feed_url = "https://www.fussballoesterreich.at/Calendar/opaque-token.ics"
    monkeypatch.setenv("OEFB_ICAL_ENABLED", "true")
    monkeypatch.setenv("OEFB_ICAL_FEED_URL", feed_url)

    settings = load_settings().oefb_ical

    assert settings.enabled is True
    assert settings.feed_url == feed_url
    assert settings.minimum_poll_interval_seconds == 21600
    assert feed_url not in repr(settings)


def test_load_settings_requires_oefb_ical_feed_url_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OEFB_ICAL_ENABLED", "true")

    with pytest.raises(ProviderConfigurationError, match="OEFB_ICAL_FEED_URL"):
        load_settings()


@pytest.mark.parametrize(
    "feed_url",
    [
        "http://www.fussballoesterreich.at/Calendar/token.ics",
        "https://example.test/Calendar/token.ics",
        "https://user:secret@www.fussballoesterreich.at/Calendar/token.ics",
        "https://www.fussballoesterreich.at/Calendar/token.ics?secret=value",
        "https://www.fussballoesterreich.at/Calendar/token.ics#fragment",
        "https://www.fussballoesterreich.at/",
    ],
)
def test_load_settings_rejects_unsafe_oefb_ical_feed_url(
    monkeypatch: pytest.MonkeyPatch,
    feed_url: str,
) -> None:
    monkeypatch.setenv("OEFB_ICAL_FEED_URL", feed_url)

    with pytest.raises(ProviderConfigurationError, match="approved HTTPS ÖFB URL"):
        load_settings()


def test_load_settings_enforces_oefb_ical_polling_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OEFB_ICAL_MINIMUM_POLL_INTERVAL_SECONDS", "21599")

    with pytest.raises(ProviderConfigurationError, match="at least 21600"):
        load_settings()


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


def test_load_settings_uses_default_instance_name() -> None:
    settings = load_settings()

    assert settings.instance_name == "default"


def test_load_settings_loads_instance_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTANCE_NAME", "calendar-staging_1")

    settings = load_settings()

    assert settings.instance_name == "calendar-staging_1"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "Staging",
        "staging calendar",
        "staging.calendar",
        "-staging",
        "a" * 64,
    ],
)
def test_load_settings_rejects_invalid_instance_name(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("INSTANCE_NAME", value)

    with pytest.raises(ValueError, match="INSTANCE_NAME must start"):
        load_settings()


def test_load_settings_disables_api_football_by_default() -> None:
    settings = load_settings()

    assert settings.api_football.enabled is False
    assert settings.api_football.api_key == ""
    assert settings.api_football.base_url == "https://v3.football.api-sports.io"
    assert settings.api_football.connect_timeout_seconds == 5.0
    assert settings.api_football.read_timeout_seconds == 30.0
    assert settings.api_football.max_attempts == 3
    assert settings.api_football.import_interval_seconds == 3600


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
    monkeypatch.setenv("API_FOOTBALL_IMPORT_INTERVAL_SECONDS", "900")

    settings = load_settings().api_football

    assert settings.enabled is True
    assert settings.api_key == "provider-secret"
    assert settings.base_url == "https://provider.example/v3"
    assert settings.connect_timeout_seconds == 2.5
    assert settings.read_timeout_seconds == 12.5
    assert settings.max_attempts == 4
    assert settings.retry_base_delay_seconds == 0.5
    assert settings.retry_max_delay_seconds == 8.0
    assert settings.import_interval_seconds == 900
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
        ("API_FOOTBALL_IMPORT_INTERVAL_SECONDS", "0"),
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


def source_job(
    *,
    job_key: str,
    source_key: str,
    role: str,
    competition_key: str = "premier_league",
) -> dict[str, object]:
    return {
        "job_key": job_key,
        "source_key": source_key,
        "sport_key": "football",
        "competition_key": competition_key,
        "season_key": "2026_27",
        "role": role,
        "interval_seconds": 3600,
    }


def test_load_settings_loads_explicit_source_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SOURCE_JOBS_JSON",
        json.dumps(
            [
                source_job(
                    job_key="football-data-pl",
                    source_key="football_data",
                    role="authoritative",
                ),
                source_job(
                    job_key="api-football-pl-verification",
                    source_key="api_football",
                    role="verification",
                ),
            ]
        ),
    )

    jobs = load_settings().source_jobs

    assert [job.job_key for job in jobs] == [
        "football-data-pl",
        "api-football-pl-verification",
    ]
    assert jobs[0].role is SourceRole.AUTHORITATIVE
    assert jobs[1].role is SourceRole.VERIFICATION


@pytest.mark.parametrize(
    "payload,match",
    [
        ("{}", "JSON array"),
        ("not-json", "valid JSON"),
        (
            json.dumps(
                [
                    source_job(
                        job_key="one",
                        source_key="source_one",
                        role="verification",
                    )
                ]
            ),
            "exactly one authoritative",
        ),
        (
            json.dumps(
                [
                    source_job(
                        job_key="one",
                        source_key="source_one",
                        role="authoritative",
                    ),
                    source_job(
                        job_key="two",
                        source_key="source_two",
                        role="authoritative",
                    ),
                ]
            ),
            "exactly one authoritative",
        ),
        (
            json.dumps(
                [
                    source_job(
                        job_key="duplicate",
                        source_key="source_one",
                        role="authoritative",
                    ),
                    source_job(
                        job_key="duplicate",
                        source_key="source_two",
                        role="verification",
                    ),
                ]
            ),
            "job_key values must be unique",
        ),
    ],
)
def test_load_settings_rejects_invalid_source_authority(
    monkeypatch: pytest.MonkeyPatch,
    payload: str,
    match: str,
) -> None:
    monkeypatch.setenv("SOURCE_JOBS_JSON", payload)

    with pytest.raises(SourceConfigurationError, match=match):
        load_settings()
