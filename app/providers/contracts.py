from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol


class SourceConfigurationError(ValueError):
    """Source orchestration configuration is invalid or ambiguous."""


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
    participant_id: int
    role: str
    position_number: int


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
    metadata: dict[str, str] | None


@dataclass(frozen=True)
class NormalizedFixtureBatch:
    fixtures: tuple[NormalizedFixture, ...]
    competition_id: int
    season_id: int
    season_start_date: date
    season_end_date: date
    fetched_at_utc: datetime
    page_count: int
    request_attempts: int
    rate_limits: RateLimitSnapshot
