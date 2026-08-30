import csv
import io
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from app.providers.nflverse.exceptions import (
    NflverseIntegrityError,
    NflverseSchemaError,
)
from app.providers.nflverse.profiles import NflverseCompetitionProfile
from app.providers.nflverse.team_mappings import NFLVERSE_TEAM_MAPPING

EASTERN = ZoneInfo("America/New_York")
REQUIRED_COLUMNS = frozenset(
    {
        "game_id",
        "season",
        "game_type",
        "week",
        "gameday",
        "gametime",
        "away_team",
        "home_team",
    }
)


@dataclass(frozen=True)
class NflverseGame:
    game_id: str
    week: int
    home_team: str
    away_team: str
    kickoff_utc: datetime
    espn: str | None
    old_game_id: str | None
    gsis: str | None


@dataclass(frozen=True)
class NflverseSnapshot:
    games: tuple[NflverseGame, ...]
    fetched_at_utc: datetime
    request_attempts: int


def parse_snapshot(
    body: bytes,
    *,
    profile: NflverseCompetitionProfile,
    fetched_at_utc: datetime,
    request_attempts: int,
) -> NflverseSnapshot:
    try:
        reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig"), newline=""))
    except UnicodeDecodeError as error:
        raise NflverseSchemaError("nflverse returned non-UTF-8 CSV.") from error
    if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
        raise NflverseSchemaError("nflverse CSV is missing required columns.")
    games: list[NflverseGame] = []
    for row in reader:
        season = _integer(row, "season")
        game_type = _text(row, "game_type")
        if season != profile.season or game_type != profile.game_type:
            continue
        games.append(_parse_game(row, profile))
    _validate_games(games, profile)
    fetched = _require_utc(fetched_at_utc)
    return NflverseSnapshot(
        tuple(sorted(games, key=lambda game: game.game_id)), fetched, request_attempts
    )


def _parse_game(
    row: dict[str, str | None], profile: NflverseCompetitionProfile
) -> NflverseGame:
    week = _integer(row, "week")
    if week not in profile.expected_weeks:
        raise NflverseIntegrityError(
            "nflverse returned an invalid regular-season week."
        )
    home = _text(row, "home_team")
    away = _text(row, "away_team")
    if (
        home == away
        or home not in NFLVERSE_TEAM_MAPPING
        or away not in NFLVERSE_TEAM_MAPPING
    ):
        raise NflverseIntegrityError(
            "nflverse returned unknown or invalid participants."
        )
    kickoff = _eastern_kickoff(_text(row, "gameday"), _text(row, "gametime"))
    if not (
        profile.season_start_date
        <= kickoff.astimezone(EASTERN).date()
        <= profile.season_end_date
    ):
        raise NflverseIntegrityError("nflverse kickoff is outside the approved season.")
    return NflverseGame(
        game_id=_text(row, "game_id"),
        week=week,
        home_team=home,
        away_team=away,
        kickoff_utc=kickoff,
        espn=_optional_text(row, "espn"),
        old_game_id=_optional_text(row, "old_game_id"),
        gsis=_optional_text(row, "gsis"),
    )


def _validate_games(
    games: list[NflverseGame], profile: NflverseCompetitionProfile
) -> None:
    if len(games) != profile.expected_game_count:
        raise NflverseIntegrityError("nflverse snapshot has the wrong game count.")
    ids = [game.game_id for game in games]
    if len(set(ids)) != len(ids):
        raise NflverseIntegrityError("nflverse returned duplicate game IDs.")
    directed_pairings = {(game.home_team, game.away_team) for game in games}
    if len(directed_pairings) != len(games):
        raise NflverseIntegrityError("nflverse returned a duplicate directed pairing.")
    teams = {team for game in games for team in (game.home_team, game.away_team)}
    if len(teams) != profile.expected_team_count or teams != set(NFLVERSE_TEAM_MAPPING):
        raise NflverseIntegrityError(
            "nflverse team scope differs from the reviewed mapping."
        )
    if {game.week for game in games} != set(profile.expected_weeks):
        raise NflverseIntegrityError(
            "nflverse snapshot does not cover weeks 1 through 18."
        )
    appearances = Counter(
        team for game in games for team in (game.home_team, game.away_team)
    )
    if any(count != 17 for count in appearances.values()):
        raise NflverseIntegrityError("nflverse team appearance counts are invalid.")


def _eastern_kickoff(day: str, clock: str) -> datetime:
    try:
        naive = datetime.combine(
            date.fromisoformat(day), datetime.strptime(clock, "%H:%M").time()
        )
    except ValueError as error:
        raise NflverseSchemaError("nflverse returned an invalid kickoff.") from error
    candidates = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=EASTERN, fold=fold)
        if aware.astimezone(UTC).astimezone(EASTERN).replace(tzinfo=None) == naive:
            candidates.append(aware.astimezone(UTC))
    if len(set(candidates)) != 1:
        raise NflverseSchemaError("nflverse kickoff is ambiguous or nonexistent.")
    return candidates[0]


def _text(row: dict[str, str | None], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise NflverseSchemaError(f"nflverse CSV has an invalid {key} value.")
    return value.strip()


def _optional_text(row: dict[str, str | None], key: str) -> str | None:
    value = row.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _integer(row: dict[str, str | None], key: str) -> int:
    value = _text(row, key)
    if not value.isascii() or not value.isdecimal():
        raise NflverseSchemaError(f"nflverse CSV has an invalid {key} value.")
    return int(value)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise NflverseSchemaError("nflverse fetch timestamp must be timezone-aware.")
    return value.astimezone(UTC)
