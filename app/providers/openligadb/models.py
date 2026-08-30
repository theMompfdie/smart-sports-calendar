from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.providers.openligadb.exceptions import (
    OpenLigaDBIntegrityError,
    OpenLigaDBSchemaError,
)
from app.providers.openligadb.profiles import OpenLigaDBCompetitionProfile

PROVIDER_TIME_ZONE_ID = "W. Europe Standard Time"
PROVIDER_TIME_ZONE = ZoneInfo("Europe/Berlin")


@dataclass(frozen=True)
class OpenLigaDBTeam:
    id: int
    name: str
    short_name: str | None

    @property
    def external_id(self) -> str:
        return str(self.id)


@dataclass(frozen=True)
class OpenLigaDBMatch:
    id: int
    league_id: int
    league_season: int
    home_team_id: int
    away_team_id: int
    kickoff_utc: datetime
    status: str
    group_id: int
    group_order_id: int
    round_name: str
    source_updated_at: datetime

    @property
    def external_id(self) -> str:
        return str(self.id)


@dataclass(frozen=True)
class OpenLigaDBSnapshot:
    league_id: int
    league_shortcut: str
    league_season: int
    season_start_date: date
    season_end_date: date
    teams: tuple[OpenLigaDBTeam, ...]
    matches: tuple[OpenLigaDBMatch, ...]
    fetched_at_utc: datetime
    request_attempts: int


def parse_snapshot(
    leagues_payload: Sequence[Any],
    groups_payload: Sequence[Any],
    matches_payload: Sequence[Any],
    *,
    profile: OpenLigaDBCompetitionProfile,
    fetched_at_utc: datetime,
    request_attempts: int,
) -> OpenLigaDBSnapshot:
    _validate_league(leagues_payload, profile)
    groups = _validate_groups(groups_payload, profile)
    selected_group_orders = set(range(1, len(profile.round_capacities) + 1))
    selected_groups = {
        order: group
        for order, group in groups.items()
        if order in selected_group_orders
    }
    if not matches_payload:
        raise OpenLigaDBIntegrityError("Provider returned no configured fixtures.")

    teams_by_id: dict[int, OpenLigaDBTeam] = {}
    matches: list[OpenLigaDBMatch] = []
    match_ids: set[int] = set()
    round_counts = Counter[int]()
    participant_appearances = Counter[int]()
    round_participants: dict[int, set[int]] = {order: set() for order in groups}
    directed_pairings: set[tuple[int, int]] = set()
    for value in matches_payload:
        match_payload = _mapping_value(value)
        group_order = _positive_int(_mapping(match_payload, "group"), "groupOrderID")
        if group_order not in selected_group_orders:
            if group_order not in groups:
                raise OpenLigaDBIntegrityError(
                    "A fixture has an unknown or inconsistent round identity."
                )
            continue
        match = _parse_match(match_payload, profile=profile, groups=selected_groups)
        if match.id in match_ids:
            raise OpenLigaDBIntegrityError("Provider returned duplicate match IDs.")
        match_ids.add(match.id)
        round_counts[match.group_order_id] += 1
        if (
            round_counts[match.group_order_id]
            > profile.round_capacities[match.group_order_id - 1]
        ):
            raise OpenLigaDBIntegrityError(
                "A round exceeds the configured fixture capacity."
            )
        pairing = (match.home_team_id, match.away_team_id)
        if pairing in directed_pairings:
            raise OpenLigaDBIntegrityError(
                "Provider returned a duplicate directed pairing."
            )
        directed_pairings.add(pairing)
        participant_appearances.update(pairing)
        round_participants[match.group_order_id].update(pairing)
        for key in ("team1", "team2"):
            team = _parse_team(_mapping(match_payload, key))
            existing = teams_by_id.get(team.id)
            if existing is not None and existing != team:
                raise OpenLigaDBIntegrityError(
                    "Provider returned inconsistent participant identity."
                )
            teams_by_id[team.id] = team
        matches.append(match)

    if not matches:
        raise OpenLigaDBIntegrityError("Provider returned no configured fixtures.")
    fetched = _require_utc(fetched_at_utc, "fetch timestamp")
    latest_update = max(match.source_updated_at for match in matches)
    if latest_update > fetched + timedelta(minutes=5):
        raise OpenLigaDBIntegrityError("Provider source update is in the future.")
    if profile.require_complete_double_round_robin:
        _validate_complete_double_round_robin(
            profile,
            match_ids=match_ids,
            participant_ids=set(teams_by_id),
            participant_appearances=participant_appearances,
            round_counts=round_counts,
            round_participants=round_participants,
            directed_pairings=directed_pairings,
        )
    if profile.require_complete_group_double_round_robin:
        _validate_complete_group_double_round_robin(
            profile,
            match_ids=match_ids,
            participant_ids=set(teams_by_id),
            round_counts=round_counts,
            round_participants=round_participants,
            directed_pairings=directed_pairings,
        )
    return OpenLigaDBSnapshot(
        league_id=profile.league_id,
        league_shortcut=profile.league_shortcut,
        league_season=profile.league_season,
        season_start_date=profile.season_start_date,
        season_end_date=profile.season_end_date,
        teams=tuple(sorted(teams_by_id.values(), key=lambda team: team.id)),
        matches=tuple(sorted(matches, key=lambda match: match.id)),
        fetched_at_utc=fetched,
        request_attempts=request_attempts,
    )


def _validate_league(
    values: Sequence[Any], profile: OpenLigaDBCompetitionProfile
) -> None:
    candidates: list[Mapping[str, Any]] = []
    for value in values:
        league = _mapping_value(value)
        shortcut = league.get("leagueShortcut")
        if isinstance(shortcut, str) and shortcut.casefold() == profile.league_shortcut:
            candidates.append(league)
    if len(candidates) != 1:
        raise OpenLigaDBIntegrityError(
            "Provider did not return exactly one configured competition."
        )
    league = candidates[0]
    sport = _mapping(league, "sport")
    if (
        _positive_int(league, "leagueId") != profile.league_id
        or _season(league, "leagueSeason") != profile.league_season
        or _positive_int(sport, "sportId") != profile.sport_id
    ):
        raise OpenLigaDBIntegrityError("Provider returned the wrong competition.")
    _string(league, "leagueName")
    _string(sport, "sportName")


def _validate_groups(
    values: Sequence[Any], profile: OpenLigaDBCompetitionProfile
) -> dict[int, Mapping[str, Any]]:
    groups: dict[int, Mapping[str, Any]] = {}
    group_ids: set[int] = set()
    for value in values:
        group = _mapping_value(value)
        order = _positive_int(group, "groupOrderID")
        group_id = _positive_int(group, "groupID")
        _string(group, "groupName")
        if order in groups or group_id in group_ids:
            raise OpenLigaDBIntegrityError(
                "Provider returned duplicate round identity."
            )
        groups[order] = group
        group_ids.add(group_id)
    expected_orders = set(range(1, len(profile.round_capacities) + 1))
    groups_are_valid = (
        expected_orders.issubset(groups)
        if profile.allow_additional_groups
        else set(groups) == expected_orders
    )
    if not groups_are_valid:
        raise OpenLigaDBIntegrityError(
            "Provider returned an invalid configured round inventory."
        )
    return groups


def _parse_match(
    payload: Mapping[str, Any],
    *,
    profile: OpenLigaDBCompetitionProfile,
    groups: Mapping[int, Mapping[str, Any]],
) -> OpenLigaDBMatch:
    if (
        _positive_int(payload, "leagueId") != profile.league_id
        or _string(payload, "leagueShortcut").casefold() != profile.league_shortcut
        or _season(payload, "leagueSeason") != profile.league_season
    ):
        raise OpenLigaDBIntegrityError(
            "A fixture belongs to the wrong competition or season."
        )
    group = _mapping(payload, "group")
    group_id = _positive_int(group, "groupID")
    group_order_id = _positive_int(group, "groupOrderID")
    declared_group = groups.get(group_order_id)
    if (
        declared_group is None
        or _positive_int(declared_group, "groupID") != group_id
        or _string(declared_group, "groupName") != _string(group, "groupName")
    ):
        raise OpenLigaDBIntegrityError(
            "A fixture has an unknown or inconsistent round identity."
        )
    home_team_id = _positive_int(_mapping(payload, "team1"), "teamId")
    away_team_id = _positive_int(_mapping(payload, "team2"), "teamId")
    if home_team_id == away_team_id:
        raise OpenLigaDBIntegrityError("A fixture contains the same participant twice.")
    timezone_id = payload.get("timeZoneID")
    if timezone_id is None or timezone_id == "":
        if not profile.allow_missing_timezone_id:
            raise OpenLigaDBIntegrityError(
                "A fixture has no permitted provider timezone."
            )
    elif (
        not isinstance(timezone_id, str)
        or not timezone_id.strip()
        or timezone_id.strip() != timezone_id
    ):
        raise OpenLigaDBSchemaError(
            "Provider response has an invalid timezone string field."
        )
    elif timezone_id != PROVIDER_TIME_ZONE_ID:
        raise OpenLigaDBIntegrityError(
            "A fixture uses an unexpected provider timezone."
        )
    kickoff = _utc_datetime(payload, "matchDateTimeUTC")
    season_floor = datetime.combine(profile.season_start_date, datetime.min.time(), UTC)
    season_ceiling = datetime.combine(profile.season_end_date, datetime.max.time(), UTC)
    if not season_floor <= kickoff <= season_ceiling:
        raise OpenLigaDBIntegrityError(
            "A fixture kickoff falls outside the configured season."
        )
    return OpenLigaDBMatch(
        id=_positive_int(payload, "matchID"),
        league_id=profile.league_id,
        league_season=profile.league_season,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        kickoff_utc=kickoff,
        status="finished" if _boolean(payload, "matchIsFinished") else "scheduled",
        group_id=group_id,
        group_order_id=group_order_id,
        round_name=f"{profile.round_prefix}-{group_order_id}",
        source_updated_at=_provider_local_datetime(payload, "lastUpdateDateTime"),
    )


def _validate_complete_double_round_robin(
    profile: OpenLigaDBCompetitionProfile,
    *,
    match_ids: set[int],
    participant_ids: set[int],
    participant_appearances: Counter[int],
    round_counts: Counter[int],
    round_participants: Mapping[int, set[int]],
    directed_pairings: set[tuple[int, int]],
) -> None:
    expected_fixtures = profile.expected_fixture_count
    expected_participants = profile.expected_participant_count
    if expected_fixtures is None or expected_participants is None:
        raise OpenLigaDBIntegrityError(
            "Complete league profile has no configured cardinality."
        )
    if len(match_ids) != expected_fixtures:
        raise OpenLigaDBIntegrityError(
            f"Provider must return exactly {expected_fixtures} fixtures."
        )
    if len(participant_ids) != expected_participants:
        raise OpenLigaDBIntegrityError(
            f"Provider must return exactly {expected_participants} participants."
        )
    expected_round_appearances = expected_participants
    expected_total_appearances = (expected_participants - 1) * 2
    for order, capacity in enumerate(profile.round_capacities, start=1):
        if round_counts[order] != capacity:
            raise OpenLigaDBIntegrityError(
                "Provider returned an incomplete configured round."
            )
        if len(round_participants[order]) != expected_round_appearances:
            raise OpenLigaDBIntegrityError(
                "A configured round does not contain every participant."
            )
    if set(participant_appearances.values()) != {expected_total_appearances}:
        raise OpenLigaDBIntegrityError(
            "Participant appearances do not form a complete double round robin."
        )
    expected_pairings = {
        (home, away)
        for home in participant_ids
        for away in participant_ids
        if home != away
    }
    if directed_pairings != expected_pairings:
        raise OpenLigaDBIntegrityError(
            "Directed pairings do not form a complete double round robin."
        )


def _validate_complete_group_double_round_robin(
    profile: OpenLigaDBCompetitionProfile,
    *,
    match_ids: set[int],
    participant_ids: set[int],
    round_counts: Counter[int],
    round_participants: Mapping[int, set[int]],
    directed_pairings: set[tuple[int, int]],
) -> None:
    expected_fixtures = profile.expected_fixture_count
    expected_participants = profile.expected_participant_count
    if expected_fixtures is None or expected_participants is None:
        raise OpenLigaDBIntegrityError(
            "Complete grouped profile has no configured cardinality."
        )
    if len(match_ids) != expected_fixtures:
        raise OpenLigaDBIntegrityError(
            f"Provider must return exactly {expected_fixtures} fixtures."
        )
    if len(participant_ids) != expected_participants:
        raise OpenLigaDBIntegrityError(
            f"Provider must return exactly {expected_participants} participants."
        )

    participants_seen: set[int] = set()
    for order, capacity in enumerate(profile.round_capacities, start=1):
        if round_counts[order] != capacity:
            raise OpenLigaDBIntegrityError(
                "Provider returned an incomplete configured group."
            )
        group_participants = round_participants[order]
        if len(group_participants) != 4:
            raise OpenLigaDBIntegrityError(
                "A configured group must contain exactly four participants."
            )
        if participants_seen.intersection(group_participants):
            raise OpenLigaDBIntegrityError(
                "A participant appears in more than one configured group."
            )
        participants_seen.update(group_participants)
        expected_pairings = {
            (home, away)
            for home in group_participants
            for away in group_participants
            if home != away
        }
        actual_pairings = {
            pairing
            for pairing in directed_pairings
            if pairing[0] in group_participants and pairing[1] in group_participants
        }
        if actual_pairings != expected_pairings:
            raise OpenLigaDBIntegrityError(
                "A configured group is not a complete double round robin."
            )
    if participants_seen != participant_ids:
        raise OpenLigaDBIntegrityError(
            "Configured groups do not contain the exact participant set."
        )


def _parse_team(payload: Mapping[str, Any]) -> OpenLigaDBTeam:
    return OpenLigaDBTeam(
        id=_positive_int(payload, "teamId"),
        name=_string(payload, "teamName"),
        short_name=_optional_string(payload, "shortName"),
    )


def _mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    return _mapping_value(container.get(key))


def _mapping_value(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise OpenLigaDBSchemaError("Provider returned an invalid object field.")
    return value


def _positive_int(container: Mapping[str, Any], key: str) -> int:
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OpenLigaDBSchemaError("Provider response has an invalid integer field.")
    return value


def _season(container: Mapping[str, Any], key: str) -> int:
    value = container.get(key)
    if isinstance(value, bool):
        raise OpenLigaDBSchemaError("Provider returned an invalid season.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise OpenLigaDBSchemaError("Provider returned an invalid season.")


def _string(container: Mapping[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OpenLigaDBSchemaError("Provider response has an invalid string field.")
    return value.strip()


def _optional_string(container: Mapping[str, Any], key: str) -> str | None:
    value = container.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not value.strip():
        raise OpenLigaDBSchemaError(
            "Provider response has an invalid optional string field."
        )
    return value.strip()


def _boolean(container: Mapping[str, Any], key: str) -> bool:
    value = container.get(key)
    if not isinstance(value, bool):
        raise OpenLigaDBSchemaError("Provider response has an invalid boolean field.")
    return value


def _utc_datetime(container: Mapping[str, Any], key: str) -> datetime:
    value = _string(container, key)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OpenLigaDBSchemaError(
            "Provider response has an invalid datetime field."
        ) from error
    return _require_utc(parsed, "provider kickoff")


def _provider_local_datetime(container: Mapping[str, Any], key: str) -> datetime:
    value = _string(container, key)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise OpenLigaDBSchemaError(
            "Provider response has an invalid update datetime."
        ) from error
    if parsed.tzinfo is not None:
        raise OpenLigaDBSchemaError(
            "Provider update datetime unexpectedly contains a timezone."
        )
    return parsed.replace(tzinfo=PROVIDER_TIME_ZONE).astimezone(UTC)


def _require_utc(value: datetime, context: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise OpenLigaDBSchemaError(f"{context} must be UTC.")
    return value.astimezone(UTC)
