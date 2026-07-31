import signal
from datetime import UTC, datetime
from threading import Event
from types import FrameType

from app.config.settings import load_settings
from app.database.database import Database
from app.logging.logger import configure_logging
from app.scheduler.scheduler import Scheduler


def main() -> None:
    settings = load_settings()
    logger = configure_logging(settings.log_level)
    stop_event = Event()

    def handle_shutdown(
        signum: int,
        _frame: FrameType | None,
    ) -> None:
        signal_name = signal.Signals(signum).name
        logger.info("Shutdown signal received: %s", signal_name)
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    database = Database(settings.database_path)
    database.initialize()
    database.record_startup()

    logger.info("SMART Sports Calendar container started")
    logger.info("Database path: %s", settings.database_path)

    scheduler = Scheduler(
        interval_seconds=settings.heartbeat_interval,
        logger=logger,
    )

    def heartbeat() -> None:
        logger.info(
            "Heartbeat: %s",
            datetime.now(UTC).isoformat(),
        )

    scheduler.run(
        task=heartbeat,
        stop_event=stop_event,
    )

    logger.info("SMART Sports Calendar container stopped")


if __name__ == "__main__":
    main()
