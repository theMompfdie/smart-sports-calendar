import time
from datetime import UTC, datetime

from app.config.settings import load_settings
from app.database.database import Database
from app.logging.logger import configure_logging


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
