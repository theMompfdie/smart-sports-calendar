import logging
from threading import Event
from unittest.mock import MagicMock

from app.scheduler.scheduler import Scheduler


def test_scheduler_stops_responsively_when_task_requests_shutdown() -> None:
    stop_event = Event()
    logger = MagicMock(spec=logging.Logger)
    scheduler = Scheduler(interval_seconds=3600, logger=logger)
    calls = 0

    def task() -> None:
        nonlocal calls
        calls += 1
        stop_event.set()

    scheduler.run(task=task, stop_event=stop_event)

    assert calls == 1
    logger.info.assert_any_call(
        "Scheduler started with an interval of %s seconds",
        3600,
    )
    logger.info.assert_any_call("Scheduler stopped")


def test_scheduler_contains_task_failure_and_waits_for_shutdown() -> None:
    stop_event = Event()
    logger = MagicMock(spec=logging.Logger)
    scheduler = Scheduler(interval_seconds=1, logger=logger)
    calls = 0

    def task() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("failed")
        stop_event.set()

    scheduler.run(task=task, stop_event=stop_event)

    assert calls == 2
    logger.exception.assert_called_once_with("Scheduled task failed")
