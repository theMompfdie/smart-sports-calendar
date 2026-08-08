import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.providers.api_football.models import (
    ApiFootballCollection,
    RateLimitSnapshot,
)

FIXTURES_DIRECTORY = Path(__file__).parents[2] / "fixtures" / "api_football"


def load_envelope(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIRECTORY / name).read_text(encoding="utf-8"))


def create_collection(items: list[dict[str, Any]]) -> ApiFootballCollection:
    return ApiFootballCollection(
        items=tuple(items),
        page_count=1,
        fetched_at_utc=datetime(2026, 8, 8, tzinfo=UTC),
        rate_limits=RateLimitSnapshot(
            daily_limit=7500,
            daily_remaining=7499,
            minute_limit=300,
            minute_remaining=299,
            retry_after_seconds=None,
        ),
    )
