from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Protocol

from app.domain.competition_lifecycle import (
    CompetitionFormat,
    FixtureLeg,
    FixtureParticipantResolution,
    TournamentStageKind,
)


class SourceConfigurationError(ValueError):
    """Source orchestration configuration is invalid or ambiguous."""


class NormalizedFixtureContractError(ValueError):
    """Normalized fixture lifecycle or participant data is contradictory."""


class SourceRole(StrEnum):
    AUTHORITATIVE = "authoritative"
    BOOTSTRAP = "bootstrap"
    VERIFICATION = "verification"
    DISABLED = "disabled"

    @property
    def can_write_canonical(self) -> bool:
        return self is SourceRole.AUTHORITATIVE


@dataclass(frozen=True)
class SourceScope:
    sport_key: str
    competition_key: str
    season_key: str


@dataclass(frozen=True)
class SourceJobDefinition:
    job_key: str
    source_key: str
    role: SourceRole
    scope: SourceScope
    interval_seconds: int

    @property
    def enabled(self) -> bool:
        return self.role is not SourceRole.DISABLED


class SourceJobTask(Protocol):
    def __call__(self) -> object | None: ...


@dataclass(frozen=True)
class RateLimitSnapshot:
    daily_limit: int | None
    daily_remaining: int | None
    minute_limit: int | None
    minute_remaining: int | None
    retry_after_seconds: float | None


@dataclass(frozen=True)
class NormalizedFixtureParticipant:
    participant_id: int | None
    role: str
    position_number: int
    resolution: FixtureParticipantResolution = FixtureParticipantResolution.RESOLVED

    def __post_init__(self) -> None:
        try:
            resolution = FixtureParticipantResolution(self.resolution)
        except (TypeError, ValueError) as error:
            raise NormalizedFixtureContractError(
                f"Unknown fixture participant resolution: {self.resolution!r}."
            ) from error
        object.__setattr__(self, "resolution", resolution)
        if self.role not in {"home", "away"}:
            raise NormalizedFixtureContractError(
                "Fixture participant role must be home or away."
            )
        expected_position = 1 if self.role == "home" else 2
        if self.position_number != expected_position:
            raise NormalizedFixtureContractError(
                "Fixture participant position must match its home/away role."
            )
        if resolution is FixtureParticipantResolution.RESOLVED:
            if not isinstance(self.participant_id, int) or self.participant_id <= 0:
                raise NormalizedFixtureContractError(
                    "A resolved fixture participant requires a positive ID."
                )
        elif self.participant_id is not None:
            raise NormalizedFixtureContractError(
                "An unresolved fixture participant cannot reference a canonical ID."
            )

    @property
    def resolved(self) -> bool:
        return self.resolution is FixtureParticipantResolution.RESOLVED


@dataclass(frozen=True)
class NormalizedFixture:
    external_id: str
    sport_id: int
    competition_id: int
    season_id: int
    event_type: str
    title: str
    participants: tuple[NormalizedFixtureParticipant, ...]
    kickoff_utc: datetime | None
    kickoff_confirmed: bool
    timezone: str
    status: str
    stage: str | None
    round_name: str | None
    sequence_number: int | None
    venue_name: str | None
    city: str | None
    source_updated_at: datetime | None
    metadata: dict[str, Any] | None
    stage_kind: TournamentStageKind | None = None
    tie_key: str | None = None
    leg: FixtureLeg | None = None

    def __post_init__(self) -> None:
        stage_kind = self._parse_optional_enum(
            self.stage_kind,
            TournamentStageKind,
            "tournament stage kind",
        )
        leg = self._parse_optional_enum(self.leg, FixtureLeg, "fixture leg")
        object.__setattr__(self, "stage_kind", stage_kind)
        object.__setattr__(self, "leg", leg)
        self._validate_optional_identifier(self.stage, "stage")
        self._validate_optional_identifier(self.round_name, "round_name")
        self._validate_optional_identifier(self.tie_key, "tie_key")
        if stage_kind is not None and self.stage is None:
            raise NormalizedFixtureContractError(
                "A tournament stage kind requires a normalized stage identifier."
            )
        if leg in {FixtureLeg.FIRST, FixtureLeg.SECOND} and self.tie_key is None:
            raise NormalizedFixtureContractError(
                "A first or second leg requires a normalized tie key."
            )

    @property
    def participants_resolved(self) -> bool:
        return all(participant.resolved for participant in self.participants)

    @staticmethod
    def _parse_optional_enum(
        value: StrEnum | str | None,
        enum_type: type[StrEnum],
        field_name: str,
    ) -> StrEnum | None:
        if value is None:
            return None
        try:
            return enum_type(value)
        except (TypeError, ValueError) as error:
            raise NormalizedFixtureContractError(
                f"Unknown {field_name}: {value!r}."
            ) from error

    @staticmethod
    def _validate_optional_identifier(value: str | None, field_name: str) -> None:
        if value is not None and (
            not isinstance(value, str) or not value.strip() or value != value.strip()
        ):
            raise NormalizedFixtureContractError(
                f"Fixture {field_name} must be normalized non-blank text."
            )


@dataclass(frozen=True)
class NormalizedFixtureBatch:
    fixtures: tuple[NormalizedFixture, ...]
    competition_id: int
    competition_format: CompetitionFormat
    season_id: int
    season_start_date: date
    season_end_date: date
    fetched_at_utc: datetime
    page_count: int
    request_attempts: int
    rate_limits: RateLimitSnapshot
