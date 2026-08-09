from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.providers.contracts import RateLimitSnapshot


@dataclass(frozen=True)
class Pagination:
    current: int
    total: int

    @property
    def has_next(self) -> bool:
        return self.current < self.total


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
