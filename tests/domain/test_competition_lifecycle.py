import pytest
from app.domain.competition_lifecycle import (
    CompetitionFormat,
    CompetitionLifecycleError,
    CompetitionLifecycleScope,
    FixtureObservationScopeKind,
)


@pytest.mark.parametrize(
    ("scope", "complete", "removal_supported"),
    [
        (
            CompetitionLifecycleScope(
                CompetitionFormat.LEAGUE,
                FixtureObservationScopeKind.PARTIAL,
            ),
            False,
            False,
        ),
        (
            CompetitionLifecycleScope(
                CompetitionFormat.LEAGUE,
                FixtureObservationScopeKind.COMPLETE_SEASON,
            ),
            True,
            True,
        ),
        (
            CompetitionLifecycleScope(
                CompetitionFormat.LEAGUE,
                FixtureObservationScopeKind.COMPLETE_STAGE,
                stage="REGULAR_SEASON",
            ),
            True,
            True,
        ),
        (
            CompetitionLifecycleScope(
                CompetitionFormat.KNOCKOUT_CUP,
                FixtureObservationScopeKind.COMPLETE_STAGE,
                stage="group_stage",
            ),
            True,
            True,
        ),
        (
            CompetitionLifecycleScope(
                CompetitionFormat.KNOCKOUT_CUP,
                FixtureObservationScopeKind.COMPLETE_ROUND,
                stage="knockout",
                round_name="round_of_16",
            ),
            True,
            True,
        ),
    ],
)
def test_scope_reports_completeness_and_current_removal_support(
    scope: CompetitionLifecycleScope,
    complete: bool,
    removal_supported: bool,
) -> None:
    assert scope.complete is complete
    assert scope.removal_reconciliation_supported is removal_supported


@pytest.mark.parametrize(
    ("competition_format", "scope_kind", "stage", "round_name", "message"),
    [
        (
            CompetitionFormat.KNOCKOUT_CUP,
            FixtureObservationScopeKind.COMPLETE_SEASON,
            None,
            None,
            "complete-season.*league",
        ),
        (
            CompetitionFormat.KNOCKOUT_CUP,
            FixtureObservationScopeKind.COMPLETE_STAGE,
            None,
            None,
            "exactly one stage",
        ),
        (
            CompetitionFormat.KNOCKOUT_CUP,
            FixtureObservationScopeKind.COMPLETE_ROUND,
            None,
            None,
            "round identifier",
        ),
    ],
)
def test_scope_rejects_contradictory_complete_scope(
    competition_format: CompetitionFormat,
    scope_kind: FixtureObservationScopeKind,
    stage: str | None,
    round_name: str | None,
    message: str,
) -> None:
    with pytest.raises(CompetitionLifecycleError, match=message):
        CompetitionLifecycleScope(
            competition_format=competition_format,
            scope_kind=scope_kind,
            stage=stage,
            round_name=round_name,
        )


def test_scope_rejects_unknown_values_and_non_normalized_identifiers() -> None:
    with pytest.raises(CompetitionLifecycleError, match="Unknown competition format"):
        CompetitionLifecycleScope(  # type: ignore[arg-type]
            "provider-specific",
            FixtureObservationScopeKind.PARTIAL,
        )

    with pytest.raises(CompetitionLifecycleError, match="Unknown fixture observation"):
        CompetitionLifecycleScope(  # type: ignore[arg-type]
            CompetitionFormat.LEAGUE,
            "provider-specific",
        )

    with pytest.raises(CompetitionLifecycleError, match="normalized non-blank"):
        CompetitionLifecycleScope(
            CompetitionFormat.KNOCKOUT_CUP,
            FixtureObservationScopeKind.COMPLETE_ROUND,
            round_name=" round_of_16 ",
        )
