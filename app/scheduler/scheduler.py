import logging
from collections.abc import Callable
from threading import Event


class Scheduler:
    def __init__(
        self,
        interval_seconds: int,
        logger: logging.Logger,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("Scheduler interval must be greater than zero.")

        self.interval_seconds = interval_seconds
        self.logger = logger

    def run(
        self,
        task: Callable[[], None],
        stop_event: Event,
    ) -> None:
        self.logger.info(
            "Scheduler started with an interval of %s seconds",
            self.interval_seconds,
        )

        while not stop_event.is_set():
            try:
                task()
            except Exception:
                self.logger.exception("Scheduled task failed")

            stop_event.wait(self.interval_seconds)

        self.logger.info("Scheduler stopped")
