from dataclasses import dataclass

from app.providers.contracts import (
    SourceConfigurationError,
    SourceJobDefinition,
    SourceJobTask,
    SourceRole,
)
from app.scheduler.scheduler import ScheduledJob


@dataclass(frozen=True)
class RegisteredSource:
    source_key: str
    task: SourceJobTask
    supported_roles: frozenset[SourceRole]
    writes_canonical: bool


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[str, RegisteredSource] = {}

    def register(
        self,
        source_key: str,
        task: SourceJobTask,
        *,
        supported_roles: frozenset[SourceRole],
        writes_canonical: bool,
    ) -> None:
        if not source_key.strip():
            raise ValueError("source_key must not be empty")
        if source_key in self._sources:
            raise SourceConfigurationError(
                f"Source adapter is already registered: {source_key}."
            )
        if not supported_roles or SourceRole.DISABLED in supported_roles:
            raise ValueError("A source adapter must declare active supported roles.")
        non_authoritative = supported_roles - {SourceRole.AUTHORITATIVE}
        if writes_canonical and non_authoritative:
            raise SourceConfigurationError(
                "A canonical-writing adapter cannot support non-authoritative roles."
            )
        if not writes_canonical and SourceRole.AUTHORITATIVE in supported_roles:
            raise SourceConfigurationError(
                "An authoritative adapter must declare canonical write capability."
            )
        self._sources[source_key] = RegisteredSource(
            source_key=source_key,
            task=task,
            supported_roles=supported_roles,
            writes_canonical=writes_canonical,
        )

    def build_scheduled_jobs(
        self,
        definitions: tuple[SourceJobDefinition, ...],
    ) -> tuple[ScheduledJob, ...]:
        jobs: list[ScheduledJob] = []
        for definition in definitions:
            if not definition.enabled:
                continue
            registered = self._sources.get(definition.source_key)
            if registered is None:
                raise SourceConfigurationError(
                    "No adapter is registered for configured source: "
                    f"{definition.source_key}."
                )
            if definition.role not in registered.supported_roles:
                raise SourceConfigurationError(
                    f"Source {definition.source_key} does not support role "
                    f"{definition.role.value}."
                )
            jobs.append(
                ScheduledJob(
                    job_key=definition.job_key,
                    interval_seconds=definition.interval_seconds,
                    task=registered.task,
                )
            )
        return tuple(jobs)
