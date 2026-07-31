import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "/data/sports.db"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "300"))


logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("smart-sports-calendar")


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS system_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            INSERT INTO system_status (started_at, status)
            VALUES (?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                "started",
            ),
        )

        connection.commit()


def main() -> None:
    initialize_database()

    logger.info("SMART Sports Calendar container started")
    logger.info("Database path: %s", DATABASE_PATH)

    while True:
        logger.info(
            "Heartbeat: %s",
            datetime.now(timezone.utc).isoformat(),
        )
        time.sleep(HEARTBEAT_INTERVAL)


if __name__ == "__main__":
    main()