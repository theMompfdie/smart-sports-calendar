from dataclasses import dataclass
from enum import StrEnum


class CompetitionLifecycleError(ValueError):
    """Competition lifecycle metadata is unknown or contradictory."""


class CompetitionFormat(StrEnum):
    LEAGUE = "league"
    KNOCKOUT_CUP = "knockout_cup"


class FixtureObservationScopeKind(StrEnum):
    PARTIAL = "partial"
    COMPLETE_SEASON = "complete_season"
    COMPLETE_STAGE = "complete_stage"
    COMPLETE_ROUND = "complete_round"


@dataclass(frozen=True)
class CompetitionLifecycleScope:
    competition_format: CompetitionFormat
    scope_kind: FixtureObservationScopeKind
    stage: str | None = None
    round_name: str | None = None

    def __post_init__(self) -> None:
        competition_format = self._parse_competition_format(self.competition_format)
        scope_kind = self._parse_scope_kind(self.scope_kind)
        object.__setattr__(self, "competition_format", competition_format)
        object.__setattr__(self, "scope_kind", scope_kind)

        self._validate_optional_identifier(self.stage, "stage")
        self._validate_optional_identifier(self.round_name, "round_name")

        if scope_kind is FixtureObservationScopeKind.COMPLETE_SEASON:
            if competition_format is not CompetitionFormat.LEAGUE:
                raise CompetitionLifecycleError(
                    "A complete-season scope currently requires league format."
                )
            if self.stage is not None or self.round_name is not None:
                raise CompetitionLifecycleError(
                    "A complete-season scope cannot declare a stage or round."
                )
        elif scope_kind is FixtureObservationScopeKind.COMPLETE_STAGE:
            if self.stage is None or self.round_name is not None:
                raise CompetitionLifecycleError(
                    "A complete-stage scope requires exactly one stage identifier."
                )
        elif scope_kind is FixtureObservationScopeKind.COMPLETE_ROUND:
            if competition_format is not CompetitionFormat.KNOCKOUT_CUP:
                raise CompetitionLifecycleError(
                    "A complete-round scope requires knockout/cup format."
                )
            if self.round_name is None:
                raise CompetitionLifecycleError(
                    "A complete-round scope requires a round identifier."
                )

    @property
    def complete(self) -> bool:
        return self.scope_kind is not FixtureObservationScopeKind.PARTIAL

    @property
    def removal_reconciliation_supported(self) -> bool:
        if self.competition_format is CompetitionFormat.LEAGUE:
            return self.scope_kind in {
                FixtureObservationScopeKind.COMPLETE_SEASON,
                FixtureObservationScopeKind.COMPLETE_STAGE,
            }
        return self.scope_kind in {
            FixtureObservationScopeKind.COMPLETE_STAGE,
            FixtureObservationScopeKind.COMPLETE_ROUND,
        }

    @staticmethod
    def _parse_competition_format(
        value: CompetitionFormat | str,
    ) -> CompetitionFormat:
        try:
            return CompetitionFormat(value)
        except (TypeError, ValueError) as error:
            raise CompetitionLifecycleError(
                f"Unknown competition format: {value!r}."
            ) from error

    @staticmethod
    def _parse_scope_kind(
        value: FixtureObservationScopeKind | str,
    ) -> FixtureObservationScopeKind:
        try:
            return FixtureObservationScopeKind(value)
        except (TypeError, ValueError) as error:
            raise CompetitionLifecycleError(
                f"Unknown fixture observation scope kind: {value!r}."
            ) from error

    @staticmethod
    def _validate_optional_identifier(value: str | None, field_name: str) -> None:
        if value is not None and (
            not isinstance(value, str) or not value.strip() or value != value.strip()
        ):
            raise CompetitionLifecycleError(
                f"Lifecycle scope {field_name} must be normalized non-blank text."
            )
