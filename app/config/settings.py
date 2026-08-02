import os
from dataclasses import dataclass
from pathlib import Path


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
    )
