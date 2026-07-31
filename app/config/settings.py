import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    log_level: str
    heartbeat_interval: int


def load_settings() -> Settings:
    heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "300"))

    if heartbeat_interval <= 0:
        raise ValueError("HEARTBEAT_INTERVAL must be greater than zero.")

    return Settings(
        database_path=Path(os.getenv("DATABASE_PATH", "/data/sports.db")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        heartbeat_interval=heartbeat_interval,
    )
