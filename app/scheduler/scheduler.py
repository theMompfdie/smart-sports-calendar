import logging
from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from time import monotonic


@dataclass(frozen=True)
class ScheduledJob:
    job_key: str
    interval_seconds: int
    task: Callable[[], object | None]


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

    def run_jobs(
        self,
        jobs: tuple[ScheduledJob, ...],
        stop_event: Event,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if not jobs:
            self.run(task=lambda: None, stop_event=stop_event)
            return
        if len({job.job_key for job in jobs}) != len(jobs):
            raise ValueError("Scheduled job keys must be unique.")
        if any(job.interval_seconds <= 0 for job in jobs):
            raise ValueError("Scheduled job intervals must be greater than zero.")

        next_runs = {job.job_key: clock() for job in jobs}
        self.logger.info("Scheduler started with %s isolated job(s)", len(jobs))
        while not stop_event.is_set():
            now = clock()
            for job in jobs:
                if now < next_runs[job.job_key]:
                    continue
                try:
                    job.task()
                except Exception:
                    self.logger.exception(
                        "Scheduled job failed: job_key=%s",
                        job.job_key,
                    )
                finally:
                    next_runs[job.job_key] = clock() + job.interval_seconds
            wait_seconds = max(0.0, min(next_runs.values()) - clock())
            stop_event.wait(wait_seconds)
        self.logger.info("Scheduler stopped")
