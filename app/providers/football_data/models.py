from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.providers.contracts import RateLimitSnapshot
from app.providers.football_data.competition_mappings import PREMIER_LEAGUE_MAPPING
from app.providers.football_data.exceptions import (
    FootballDataIntegrityError,
    FootballDataSchemaError,
)

PREMIER_LEAGUE_CODE = PREMIER_LEAGUE_MAPPING.external_code
PREMIER_LEAGUE_ID = PREMIER_LEAGUE_MAPPING.external_id
EXPECTED_TEAM_COUNT = 20
EXPECTED_MATCH_COUNT = 380

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


def parse_snapshot(
    competition_payload: Mapping[str, Any],
    teams_payload: Mapping[str, Any],
    matches_payload: Mapping[str, Any],
    *,
    expected_season_year: int,
    fetched_at_utc: datetime,
    request_attempts: int,
    rate_limits: RateLimitSnapshot,
) -> FootballDataSnapshot:
    competition_id = _positive_int(competition_payload, "id")
    competition_code = _string(competition_payload, "code")
    if competition_id != PREMIER_LEAGUE_ID or competition_code != PREMIER_LEAGUE_CODE:
        raise FootballDataIntegrityError("Provider returned the wrong competition.")

    season_payload = _mapping(competition_payload, "currentSeason")
    season_id = _positive_int(season_payload, "id")
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
    if len(teams) != EXPECTED_TEAM_COUNT or len(team_ids) != EXPECTED_TEAM_COUNT:
        raise FootballDataIntegrityError(
            "Premier League snapshot must contain exactly 20 distinct teams."
        )

    result_set = _mapping(matches_payload, "resultSet")
    declared_count = _positive_int(result_set, "count")
    raw_matches = _list(matches_payload, "matches")
    if (
        declared_count != EXPECTED_MATCH_COUNT
        or len(raw_matches) != EXPECTED_MATCH_COUNT
    ):
        raise FootballDataIntegrityError(
            "Premier League snapshot must contain exactly 380 matches."
        )
    matches = tuple(
        sorted(
            (
                _parse_match(
                    _mapping_value(item),
                    competition_id=competition_id,
                    season_id=season_id,
                    team_ids=team_ids,
                )
                for item in raw_matches
            ),
            key=lambda match: match.id,
        )
    )
    match_ids = {match.id for match in matches}
    if len(match_ids) != EXPECTED_MATCH_COUNT:
        raise FootballDataIntegrityError("Provider returned duplicate match IDs.")

    _validate_schedule(matches, teams)
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
) -> FootballDataMatch:
    if _positive_int(_mapping(payload, "competition"), "id") != competition_id:
        raise FootballDataIntegrityError("A match belongs to the wrong competition.")
    if _positive_int(_mapping(payload, "season"), "id") != season_id:
        raise FootballDataIntegrityError("A match belongs to the wrong season.")
    home_id = _positive_int(_mapping(payload, "homeTeam"), "id")
    away_id = _positive_int(_mapping(payload, "awayTeam"), "id")
    if home_id == away_id or home_id not in team_ids or away_id not in team_ids:
        raise FootballDataIntegrityError("A match contains invalid participants.")
    provider_status = _string(payload, "status")
    try:
        status = STATUS_MAPPING[provider_status]
    except KeyError as error:
        raise FootballDataSchemaError(
            "Provider returned an unsupported match status."
        ) from error
    return FootballDataMatch(
        id=_positive_int(payload, "id"),
        competition_id=competition_id,
        season_id=season_id,
        home_team_id=home_id,
        away_team_id=away_id,
        kickoff_utc=_utc_datetime(_string(payload, "utcDate")),
        status=status,
        provider_status=provider_status,
        stage=_optional_string(payload, "stage"),
        matchday=_optional_positive_int(payload, "matchday"),
        source_updated_at=_utc_datetime(_string(payload, "lastUpdated")),
    )


def _validate_schedule(
    matches: tuple[FootballDataMatch, ...],
    teams: tuple[FootballDataTeam, ...],
) -> None:
    appearances = Counter[int]()
    pairings: set[tuple[int, int]] = set()
    for match in matches:
        pairing = (match.home_team_id, match.away_team_id)
        if pairing in pairings:
            raise FootballDataIntegrityError(
                "Premier League snapshot contains a duplicate home/away pairing."
            )
        pairings.add(pairing)
        appearances.update(pairing)
    expected_appearances = (len(teams) - 1) * 2
    if set(appearances) != {team.id for team in teams} or any(
        count != expected_appearances for count in appearances.values()
    ):
        raise FootballDataIntegrityError(
            "Premier League snapshot does not form a complete double round robin."
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
