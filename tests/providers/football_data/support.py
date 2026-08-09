from datetime import UTC, datetime, timedelta
from typing import Any

from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.models import FootballDataSnapshot, parse_snapshot
from app.providers.football_data.team_mappings import PREMIER_LEAGUE_TEAM_NAME_MAPPING

FETCHED_AT = datetime(2026, 8, 9, 12, tzinfo=UTC)
SOURCE_UPDATED_AT = datetime(2026, 7, 9, 1, 25, tzinfo=UTC)


def payloads() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    teams = [
        {
            "id": 100 + index,
            "name": name,
            "shortName": name.removesuffix(" FC"),
            "tla": f"T{index:02d}",
        }
        for index, name in enumerate(PREMIER_LEAGUE_TEAM_NAME_MAPPING, start=1)
    ]
    matches: list[dict[str, Any]] = []
    match_id = 1000
    kickoff = datetime(2026, 8, 21, 19, tzinfo=UTC)
    for home in teams:
        for away in teams:
            if home["id"] == away["id"]:
                continue
            matches.append(
                {
                    "id": match_id,
                    "competition": {"id": 2021},
                    "season": {"id": 2502},
                    "utcDate": kickoff.isoformat().replace("+00:00", "Z"),
                    "status": "SCHEDULED",
                    "matchday": ((match_id - 1000) % 38) + 1,
                    "stage": "REGULAR_SEASON",
                    "lastUpdated": SOURCE_UPDATED_AT.isoformat().replace("+00:00", "Z"),
                    "homeTeam": {"id": home["id"]},
                    "awayTeam": {"id": away["id"]},
                }
            )
            match_id += 1
            kickoff += timedelta(hours=12)
    return (
        {
            "id": 2021,
            "code": "PL",
            "currentSeason": {
                "id": 2502,
                "startDate": "2026-08-21",
                "endDate": "2027-05-30",
            },
        },
        {"teams": teams},
        {"resultSet": {"count": len(matches)}, "matches": matches},
    )


def snapshot() -> FootballDataSnapshot:
    competition, teams, matches = payloads()
    return parse_snapshot(
        competition,
        teams,
        matches,
        expected_season_year=2026,
        fetched_at_utc=FETCHED_AT,
        request_attempts=3,
        rate_limits=RateLimitSnapshot(None, None, 10, None, None),
    )
