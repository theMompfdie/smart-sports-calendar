from unittest.mock import MagicMock

import pytest
from app.application.source_registry import SourceRegistry
from app.providers.contracts import (
    SourceConfigurationError,
    SourceJobDefinition,
    SourceRole,
    SourceScope,
)


def definition(
    source_key: str,
    role: SourceRole = SourceRole.AUTHORITATIVE,
) -> SourceJobDefinition:
    return SourceJobDefinition(
        job_key=f"{source_key}-pl",
        source_key=source_key,
        role=role,
        scope=SourceScope("football", "premier_league", "2026_27"),
        interval_seconds=900,
    )


def test_registry_builds_independent_jobs_for_registered_sources() -> None:
    registry = SourceRegistry()
    first = MagicMock()
    second = MagicMock()
    registry.register(
        "first",
        first,
        supported_roles=frozenset({SourceRole.AUTHORITATIVE}),
        writes_canonical=True,
    )
    registry.register(
        "second",
        second,
        supported_roles=frozenset({SourceRole.VERIFICATION}),
        writes_canonical=False,
    )

    jobs = registry.build_scheduled_jobs(
        (
            definition("first"),
            definition("second", SourceRole.VERIFICATION),
        )
    )

    assert [job.job_key for job in jobs] == ["first-pl", "second-pl"]
    assert [job.interval_seconds for job in jobs] == [900, 900]
    jobs[0].task()
    jobs[1].task()
    first.assert_called_once_with()
    second.assert_called_once_with()


def test_registry_rejects_missing_adapter() -> None:
    with pytest.raises(SourceConfigurationError, match="No adapter is registered"):
        SourceRegistry().build_scheduled_jobs((definition("missing"),))


def test_registry_rejects_unsupported_writer_role() -> None:
    registry = SourceRegistry()
    registry.register(
        "verification-only",
        MagicMock(),
        supported_roles=frozenset({SourceRole.VERIFICATION}),
        writes_canonical=False,
    )

    with pytest.raises(SourceConfigurationError, match="does not support role"):
        registry.build_scheduled_jobs((definition("verification-only"),))


def test_registry_ignores_disabled_job_without_requiring_adapter() -> None:
    jobs = SourceRegistry().build_scheduled_jobs(
        (definition("future", SourceRole.DISABLED),)
    )

    assert jobs == ()


def test_registry_rejects_canonical_writes_for_verification_role() -> None:
    registry = SourceRegistry()

    with pytest.raises(
        SourceConfigurationError,
        match="cannot support non-authoritative",
    ):
        registry.register(
            "unsafe",
            MagicMock(),
            supported_roles=frozenset({SourceRole.VERIFICATION}),
            writes_canonical=True,
        )
