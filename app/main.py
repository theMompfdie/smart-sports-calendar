import logging
import time
from datetime import UTC, datetime

from app.config.settings import load_settings
from app.database.database import Database


def configure_logging(log_level: str) -> logging.Logger:
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    return logging.getLogger("smart-sports-calendar")


def main() -> None:
    settings = load_settings()
    logger = configure_logging(settings.log_level)

    database = Database(settings.database_path)
    database.initialize()
    database.record_startup()

    logger.info("SMART Sports Calendar container started")
    logger.info("Database path: %s", settings.database_path)

    while True:
        logger.info(
            "Heartbeat: %s",
            datetime.now(UTC).isoformat(),
        )

        time.sleep(settings.heartbeat_interval)


if __name__ == "__main__":
    main()
