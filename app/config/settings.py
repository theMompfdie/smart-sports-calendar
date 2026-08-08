import os
from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from urllib.parse import urlsplit

from app.providers.api_football.exceptions import ProviderConfigurationError


@dataclass(frozen=True)
class ApiFootballSettings:
    enabled: bool
    api_key: str = field(repr=False)
    base_url: str = "https://v3.football.api-sports.io"
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 30.0
    max_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 30.0
    import_interval_seconds: int = 3600


@dataclass(frozen=True)
class Settings:
    database_path: Path
    log_level: str
    heartbeat_interval: int
    m365_tenant_id: str
    m365_client_id: str
    m365_client_secret: str
    m365_user_id: str
    outlook_calendar_name: str
    outlook_calendar_id: str
    synchronization_batch_limit: int
    graph_base_url: str
    graph_startup_validation_enabled: bool
    api_football: ApiFootballSettings = field(
        default_factory=lambda: ApiFootballSettings(
            enabled=False,
            api_key="",
        )
    )


def get_required_environment_variable(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise ValueError(f"{name} must be configured.")

    return value


def get_boolean_environment_variable(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized_value = value.strip().lower()

    if normalized_value in {"1", "true", "yes", "on"}:
        return True

    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"{name} must be one of: true, false, 1, 0, yes, no, on, off.")


def get_positive_integer_environment_variable(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(name, str(default))

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return value


def get_positive_float_environment_variable(
    name: str,
    default: float,
) -> float:
    raw_value = os.getenv(name, str(default))

    try:
        value = float(raw_value)
    except ValueError as error:
        raise ProviderConfigurationError(f"{name} must be a number.") from error

    if not isfinite(value) or value <= 0:
        raise ProviderConfigurationError(f"{name} must be greater than zero.")

    return value


def load_api_football_settings() -> ApiFootballSettings:
    try:
        enabled = get_boolean_environment_variable(
            "API_FOOTBALL_ENABLED",
            default=False,
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    api_key = os.getenv("API_FOOTBALL_API_KEY", "").strip()

    if enabled and not api_key:
        raise ProviderConfigurationError(
            "API_FOOTBALL_API_KEY must be configured when API_FOOTBALL_ENABLED is true."
        )

    base_url = os.getenv(
        "API_FOOTBALL_BASE_URL",
        "https://v3.football.api-sports.io",
    ).rstrip("/")
    parsed_url = urlsplit(base_url)

    try:
        _ = parsed_url.port
    except ValueError as error:
        raise ProviderConfigurationError(
            "API_FOOTBALL_BASE_URL must be an HTTPS URL with a valid port and "
            "without credentials, query parameters, or fragments."
        ) from error

    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ProviderConfigurationError(
            "API_FOOTBALL_BASE_URL must be an HTTPS URL without credentials, "
            "query parameters, or fragments."
        )

    try:
        max_attempts = get_positive_integer_environment_variable(
            "API_FOOTBALL_MAX_ATTEMPTS",
            default=3,
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    if max_attempts > 10:
        raise ProviderConfigurationError(
            "API_FOOTBALL_MAX_ATTEMPTS must not exceed 10."
        )

    retry_base_delay_seconds = get_positive_float_environment_variable(
        "API_FOOTBALL_RETRY_BASE_DELAY_SECONDS",
        default=1.0,
    )
    retry_max_delay_seconds = get_positive_float_environment_variable(
        "API_FOOTBALL_RETRY_MAX_DELAY_SECONDS",
        default=30.0,
    )
    if retry_max_delay_seconds < retry_base_delay_seconds:
        raise ProviderConfigurationError(
            "API_FOOTBALL_RETRY_MAX_DELAY_SECONDS must be greater than or "
            "equal to API_FOOTBALL_RETRY_BASE_DELAY_SECONDS."
        )
    try:
        import_interval_seconds = get_positive_integer_environment_variable(
            "API_FOOTBALL_IMPORT_INTERVAL_SECONDS",
            default=3600,
        )
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error

    return ApiFootballSettings(
        enabled=enabled,
        api_key=api_key,
        base_url=base_url,
        connect_timeout_seconds=get_positive_float_environment_variable(
            "API_FOOTBALL_CONNECT_TIMEOUT_SECONDS",
            default=5.0,
        ),
        read_timeout_seconds=get_positive_float_environment_variable(
            "API_FOOTBALL_READ_TIMEOUT_SECONDS",
            default=30.0,
        ),
        max_attempts=max_attempts,
        retry_base_delay_seconds=retry_base_delay_seconds,
        retry_max_delay_seconds=retry_max_delay_seconds,
        import_interval_seconds=import_interval_seconds,
    )


def load_settings() -> Settings:
    return Settings(
        database_path=Path(
            os.getenv(
                "DATABASE_PATH",
                "/data/sports.db",
            )
        ),
        log_level=os.getenv(
            "LOG_LEVEL",
            "INFO",
        ).upper(),
        heartbeat_interval=get_positive_integer_environment_variable(
            "HEARTBEAT_INTERVAL",
            default=300,
        ),
        m365_tenant_id=get_required_environment_variable("M365_TENANT_ID"),
        m365_client_id=get_required_environment_variable("M365_CLIENT_ID"),
        m365_client_secret=get_required_environment_variable("M365_CLIENT_SECRET"),
        m365_user_id=get_required_environment_variable("M365_USER_ID"),
        outlook_calendar_name=os.getenv(
            "OUTLOOK_CALENDAR_NAME",
            "SMART Sports Calendar",
        ).strip(),
        outlook_calendar_id=get_required_environment_variable("OUTLOOK_CALENDAR_ID"),
        synchronization_batch_limit=(
            get_positive_integer_environment_variable(
                "SYNCHRONIZATION_BATCH_LIMIT",
                default=100,
            )
        ),
        graph_base_url=os.getenv(
            "GRAPH_BASE_URL",
            "https://graph.microsoft.com/v1.0",
        ).rstrip("/"),
        graph_startup_validation_enabled=(
            get_boolean_environment_variable(
                "GRAPH_STARTUP_VALIDATION_ENABLED",
                default=True,
            )
        ),
        api_football=load_api_football_settings(),
    )
