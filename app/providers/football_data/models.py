from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.exceptions import (
    FootballDataIntegrityError,
    FootballDataSchemaError,
)
from app.providers.football_data.profiles import (
    PREMIER_LEAGUE_PROFILE,
    FootballDataCompetitionProfile,
)

PREMIER_LEAGUE_CODE = PREMIER_LEAGUE_PROFILE.external_code
PREMIER_LEAGUE_ID = PREMIER_LEAGUE_PROFILE.external_id
EXPECTED_TEAM_COUNT = PREMIER_LEAGUE_PROFILE.expected_team_count
EXPECTED_MATCH_COUNT = PREMIER_LEAGUE_PROFILE.expected_match_count

STATUS_MAPPING = {
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    "IN_PLAY": "live",
    "PAUSED": "live",
    "EXTRA_TIME": "live",
    "PENALTY_SHOOTOUT": "live",
    "FINISHED": "finished",
    "SUSPENDED": "suspended",
    "POSTPONED": "postponed",
    "CANCELLED": "cancelled",
    "AWARDED": "finished",
}


@dataclass(frozen=True)
class FootballDataTeam:
    id: int
    name: str
    short_name: str | None
    tla: str | None

    @property
    def external_id(self) -> str:
        return str(self.id)


@dataclass(frozen=True)
class FootballDataMatch:
    id: int
    competition_id: int
    season_id: int
    home_team_id: int
    away_team_id: int
    kickoff_utc: datetime
    status: str
    provider_status: str
    stage: str | None
    matchday: int | None
    source_updated_at: datetime

    @property
    def external_id(self) -> str:
        return str(self.id)


@dataclass(frozen=True)
class FootballDataSnapshot:
    competition_id: int
    competition_code: str
    season_id: int
    season_start_date: date
    season_end_date: date
    teams: tuple[FootballDataTeam, ...]
    matches: tuple[FootballDataMatch, ...]
    fetched_at_utc: datetime
    request_attempts: int
    rate_limits: RateLimitSnapshot
    page_count: int = 1


def parse_snapshot(
    competition_payload: Mapping[str, Any],
    teams_payload: Mapping[str, Any],
    matches_payload: Mapping[str, Any],
    *,
    profile: FootballDataCompetitionProfile,
    expected_season_year: int,
    fetched_at_utc: datetime,
    request_attempts: int,
    rate_limits: RateLimitSnapshot,
    page_count: int = 1,
) -> FootballDataSnapshot:
    competition_id = _positive_int(competition_payload, "id")
    competition_code = _string(competition_payload, "code")
    if (
        competition_id != profile.external_id
        or competition_code != profile.external_code
    ):
        raise FootballDataIntegrityError("Provider returned the wrong competition.")

    season_payload = _mapping(competition_payload, "currentSeason")
    season_id = _positive_int(season_payload, "id")
    if season_id != profile.external_season_id:
        raise FootballDataIntegrityError("Provider returned the wrong season identity.")
    season_start = _date(_string(season_payload, "startDate"))
    season_end = _date(_string(season_payload, "endDate"))
    if season_start.year != expected_season_year or season_end < season_start:
        raise FootballDataIntegrityError("Provider returned the wrong season scope.")

    teams = tuple(
        sorted(
            (
                _parse_team(_mapping_value(item))
                for item in _list(teams_payload, "teams")
            ),
            key=lambda team: team.id,
        )
    )
    team_ids = {team.id for team in teams}
    if (
        len(teams) != profile.expected_team_count
        or len(team_ids) != profile.expected_team_count
    ):
        raise FootballDataIntegrityError(
            f"{profile.competition_name} snapshot must contain exactly "
            f"{profile.expected_team_count} distinct teams."
        )

    result_set = _mapping(matches_payload, "resultSet")
    declared_count = _positive_int(result_set, "count")
    raw_matches = _list(matches_payload, "matches")
    if (
        declared_count != profile.expected_match_count
        or len(raw_matches) != profile.expected_match_count
    ):
        raise FootballDataIntegrityError(
            f"{profile.competition_name} snapshot must contain exactly "
            f"{profile.expected_match_count} matches."
        )
    matches = tuple(
        sorted(
            (
                _parse_match(
                    _mapping_value(item),
                    competition_id=competition_id,
                    season_id=season_id,
                    team_ids=team_ids,
                    expected_matchdays=profile.expected_matchdays,
                )
                for item in raw_matches
            ),
            key=lambda match: match.id,
        )
    )
    match_ids = {match.id for match in matches}
    if len(match_ids) != profile.expected_match_count:
        raise FootballDataIntegrityError("Provider returned duplicate match IDs.")

    _validate_schedule(matches, teams, profile=profile)
    _validate_freshness(
        matches,
        fetched_at_utc=fetched_at_utc,
        season_start=season_start,
        season_end=season_end,
    )
    return FootballDataSnapshot(
        competition_id=competition_id,
        competition_code=competition_code,
        season_id=season_id,
        season_start_date=season_start,
        season_end_date=season_end,
        teams=teams,
        matches=matches,
        fetched_at_utc=_require_utc(fetched_at_utc, "fetch timestamp"),
        request_attempts=request_attempts,
        rate_limits=rate_limits,
        page_count=page_count,
    )


def _parse_team(payload: Mapping[str, Any]) -> FootballDataTeam:
    return FootballDataTeam(
        id=_positive_int(payload, "id"),
        name=_string(payload, "name"),
        short_name=_optional_string(payload, "shortName"),
        tla=_optional_string(payload, "tla"),
    )


def _parse_match(
    payload: Mapping[str, Any],
    *,
    competition_id: int,
    season_id: int,
    team_ids: set[int],
    expected_matchdays: int,
) -> FootballDataMatch:
    if _positive_int(_mapping(payload, "competition"), "id") != competition_id:
        raise FootballDataIntegrityError("A match belongs to the wrong competition.")
    if _positive_int(_mapping(payload, "season"), "id") != season_id:
        raise FootballDataIntegrityError("A match belongs to the wrong season.")
    home_id = _positive_int(_mapping(payload, "homeTeam"), "id")
    away_id = _positive_int(_mapping(payload, "awayTeam"), "id")
    if home_id == away_id or home_id not in team_ids or away_id not in team_ids:
        raise FootballDataIntegrityError("A match contains invalid participants.")
    match_id = _positive_int(payload, "id")
    provider_status = _string(payload, "status")
    try:
        status = STATUS_MAPPING[provider_status]
    except KeyError:
        # Never include untrusted status content through exception chaining.
        raise FootballDataSchemaError(
            "Provider returned an unsupported match status "
            f"(competition_id={competition_id}, season_id={season_id}, "
            f"match_id={match_id})."
        ) from None
    stage = _optional_string(payload, "stage")
    matchday = _optional_positive_int(payload, "matchday")
    if stage != "REGULAR_SEASON":
        raise FootballDataIntegrityError("A match belongs to an unsupported stage.")
    if matchday is None or matchday > expected_matchdays:
        raise FootballDataIntegrityError("A match belongs to an invalid matchday.")
    return FootballDataMatch(
        id=match_id,
        competition_id=competition_id,
        season_id=season_id,
        home_team_id=home_id,
        away_team_id=away_id,
        kickoff_utc=_utc_datetime(_string(payload, "utcDate")),
        status=status,
        provider_status=provider_status,
        stage=stage,
        matchday=matchday,
        source_updated_at=_utc_datetime(_string(payload, "lastUpdated")),
    )


def _validate_schedule(
    matches: tuple[FootballDataMatch, ...],
    teams: tuple[FootballDataTeam, ...],
    *,
    profile: FootballDataCompetitionProfile,
) -> None:
    appearances = Counter[int]()
    pairings: set[tuple[int, int]] = set()
    matchday_counts = Counter[int]()
    matchday_participants: defaultdict[int, set[int]] = defaultdict(set)
    for match in matches:
        pairing = (match.home_team_id, match.away_team_id)
        if pairing in pairings:
            raise FootballDataIntegrityError(
                f"{profile.competition_name} snapshot contains a duplicate "
                "home/away pairing."
            )
        pairings.add(pairing)
        appearances.update(pairing)
        if match.matchday is None:
            raise FootballDataIntegrityError("A match has no matchday.")
        matchday_counts[match.matchday] += 1
        matchday_participants[match.matchday].update(pairing)
    expected_appearances = (len(teams) - 1) * 2
    if set(appearances) != {team.id for team in teams} or any(
        count != expected_appearances for count in appearances.values()
    ):
        raise FootballDataIntegrityError(
            f"{profile.competition_name} snapshot does not form a complete "
            "double round robin."
        )
    expected_matchdays = set(range(1, profile.expected_matchdays + 1))
    if set(matchday_counts) != expected_matchdays or any(
        count != profile.expected_team_count // 2 for count in matchday_counts.values()
    ):
        raise FootballDataIntegrityError(
            f"{profile.competition_name} snapshot has incomplete matchday counts."
        )
    team_ids = {team.id for team in teams}
    if any(
        matchday_participants[matchday] != team_ids for matchday in expected_matchdays
    ):
        raise FootballDataIntegrityError(
            f"{profile.competition_name} snapshot has invalid matchday participants."
        )


def _validate_freshness(
    matches: tuple[FootballDataMatch, ...],
    *,
    fetched_at_utc: datetime,
    season_start: date,
    season_end: date,
) -> None:
    fetched = _require_utc(fetched_at_utc, "fetch timestamp")
    latest_update = max(match.source_updated_at for match in matches)
    if latest_update > fetched + timedelta(minutes=5):
        raise FootballDataIntegrityError("Provider source update is in the future.")
    if fetched.date() < season_start:
        maximum_age = timedelta(days=60)
    elif fetched.date() <= season_end:
        maximum_age = timedelta(days=14)
    else:
        maximum_age = timedelta(days=30)
    if fetched - latest_update > maximum_age:
        raise FootballDataIntegrityError(
            "Provider snapshot is stale for its season phase."
        )


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    return _mapping_value(payload.get(key))


def _mapping_value(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise FootballDataSchemaError("Provider response has an invalid object field.")
    return value


def _list(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise FootballDataSchemaError("Provider response has an invalid collection.")
    return value


def _positive_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FootballDataSchemaError("Provider response has an invalid integer field.")
    return value


def _optional_positive_int(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FootballDataSchemaError("Provider response has an invalid integer field.")
    return value


def _string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FootballDataSchemaError("Provider response has an invalid string field.")
    return value.strip()


def _optional_string(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise FootballDataSchemaError("Provider response has an invalid string field.")
    return value.strip()


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise FootballDataSchemaError("Provider returned an invalid date.") from error


def _utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise FootballDataSchemaError(
            "Provider returned an invalid timestamp."
        ) from error
    return _require_utc(parsed, "provider timestamp")


def _require_utc(value: datetime, context: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise FootballDataSchemaError(f"{context} must be UTC.")
    return value.astimezone(UTC)
