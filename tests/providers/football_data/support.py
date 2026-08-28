from datetime import UTC, datetime, timedelta
from typing import Any

from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.models import FootballDataSnapshot, parse_snapshot
from app.providers.football_data.profiles import (
    BUNDESLIGA_PROFILE,
    CHAMPIONSHIP_PROFILE,
    PREMIER_LEAGUE_PROFILE,
    FootballDataCompetitionProfile,
)
from app.providers.football_data.team_mappings import (
    BUNDESLIGA_TEAM_NAME_MAPPING,
    CHAMPIONSHIP_TEAM_NAME_MAPPING,
    PREMIER_LEAGUE_TEAM_NAME_MAPPING,
)

FETCHED_AT = datetime(2026, 8, 9, 12, tzinfo=UTC)
SOURCE_UPDATED_AT = datetime(2026, 7, 9, 1, 25, tzinfo=UTC)


def _schedule(team_ids: list[int]) -> list[tuple[int, int, int]]:
    rotation = list(team_ids)
    first_leg: list[tuple[int, int, int]] = []
    for round_index in range(len(team_ids) - 1):
        for pair_index in range(len(team_ids) // 2):
            home = rotation[pair_index]
            away = rotation[-pair_index - 1]
            if (round_index + pair_index) % 2:
                home, away = away, home
            first_leg.append((home, away, round_index + 1))
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
    return [
        *first_leg,
        *(
            (away, home, matchday + len(team_ids) - 1)
            for home, away, matchday in first_leg
        ),
    ]


def payloads(
    profile: FootballDataCompetitionProfile = PREMIER_LEAGUE_PROFILE,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    team_mapping = {
        PREMIER_LEAGUE_PROFILE.competition_key: PREMIER_LEAGUE_TEAM_NAME_MAPPING,
        BUNDESLIGA_PROFILE.competition_key: BUNDESLIGA_TEAM_NAME_MAPPING,
        CHAMPIONSHIP_PROFILE.competition_key: CHAMPIONSHIP_TEAM_NAME_MAPPING,
    }[profile.competition_key]
    provider_id_base = {
        PREMIER_LEAGUE_PROFILE.competition_key: 100,
        BUNDESLIGA_PROFILE.competition_key: 1000,
        CHAMPIONSHIP_PROFILE.competition_key: 2000,
    }[profile.competition_key]
    teams = [
        {
            "id": provider_id_base + index,
            "name": name,
            "shortName": name.removesuffix(" FC"),
            "tla": f"T{index:02d}",
        }
        for index, name in enumerate(team_mapping, start=1)
    ]
    matches: list[dict[str, Any]] = []
    match_id = {
        PREMIER_LEAGUE_PROFILE.competition_key: 1000,
        BUNDESLIGA_PROFILE.competition_key: 2000,
        CHAMPIONSHIP_PROFILE.competition_key: 3000,
    }[profile.competition_key]
    start_date, end_date = {
        PREMIER_LEAGUE_PROFILE.competition_key: ("2026-08-21", "2027-05-30"),
        BUNDESLIGA_PROFILE.competition_key: ("2026-08-28", "2027-05-22"),
        CHAMPIONSHIP_PROFILE.competition_key: ("2026-08-14", "2027-05-01"),
    }[profile.competition_key]
    kickoff = datetime.fromisoformat(f"{start_date}T19:00:00+00:00")
    kickoff_step = (
        timedelta(hours=8)
        if profile.competition_key == CHAMPIONSHIP_PROFILE.competition_key
        else timedelta(hours=12)
    )
    teams_by_id = {team["id"]: team for team in teams}
    for home_id, away_id, matchday in _schedule(list(teams_by_id)):
        matches.append(
            {
                "id": match_id,
                "competition": {"id": profile.external_id},
                "season": {"id": profile.external_season_id},
                "utcDate": kickoff.isoformat().replace("+00:00", "Z"),
                "status": "SCHEDULED",
                "matchday": matchday,
                "stage": "REGULAR_SEASON",
                "lastUpdated": SOURCE_UPDATED_AT.isoformat().replace("+00:00", "Z"),
                "homeTeam": {"id": home_id},
                "awayTeam": {"id": away_id},
            }
        )
        match_id += 1
        kickoff += kickoff_step
    return (
        {
            "id": profile.external_id,
            "code": profile.external_code,
            "currentSeason": {
                "id": profile.external_season_id,
                "startDate": start_date,
                "endDate": end_date,
            },
        },
        {"teams": teams},
        {"resultSet": {"count": len(matches)}, "matches": matches},
    )


def snapshot(
    profile: FootballDataCompetitionProfile = PREMIER_LEAGUE_PROFILE,
) -> FootballDataSnapshot:
    competition, teams, matches = payloads(profile)
    return parse_snapshot(
        competition,
        teams,
        matches,
        profile=profile,
        expected_season_year=2026,
        fetched_at_utc=FETCHED_AT,
        request_attempts=3,
        rate_limits=RateLimitSnapshot(None, None, 10, None, None),
    )
