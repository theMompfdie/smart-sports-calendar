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
    graph_base_url: str


def get_required_environment_variable(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise ValueError(f"{name} must be configured.")

    return value


def load_settings() -> Settings:
    heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "300"))

    if heartbeat_interval <= 0:
        raise ValueError("HEARTBEAT_INTERVAL must be greater than zero.")

    return Settings(
        database_path=Path(os.getenv("DATABASE_PATH", "/data/sports.db")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        heartbeat_interval=heartbeat_interval,
        m365_tenant_id=get_required_environment_variable("M365_TENANT_ID"),
        m365_client_id=get_required_environment_variable("M365_CLIENT_ID"),
        m365_client_secret=get_required_environment_variable("M365_CLIENT_SECRET"),
        m365_user_id=get_required_environment_variable("M365_USER_ID"),
        outlook_calendar_name=os.getenv(
            "OUTLOOK_CALENDAR_NAME",
            "SMART Sports Calendar",
        ).strip(),
        graph_base_url=os.getenv(
            "GRAPH_BASE_URL",
            "https://graph.microsoft.com/v1.0",
        ).rstrip("/"),
    )
