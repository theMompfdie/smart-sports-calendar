from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Pagination:
    current: int
    total: int

    @property
    def has_next(self) -> bool:
        return self.current < self.total


@dataclass(frozen=True)
class RateLimitSnapshot:
    daily_limit: int | None
    daily_remaining: int | None
    minute_limit: int | None
    minute_remaining: int | None
    retry_after_seconds: float | None


@dataclass(frozen=True)
class FetchMetadata:
    fetched_at_utc: datetime
    request_id: str | None
    rate_limits: RateLimitSnapshot
    attempt_count: int = 1


@dataclass(frozen=True)
class ApiFootballPage:
    items: tuple[dict[str, Any], ...]
    pagination: Pagination
    metadata: FetchMetadata


@dataclass(frozen=True)
class ApiFootballCollection:
    items: tuple[dict[str, Any], ...]
    page_count: int
    fetched_at_utc: datetime
    rate_limits: RateLimitSnapshot
    request_attempts: int = 1
