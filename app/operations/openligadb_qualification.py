import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from http.client import HTTPException, HTTPSConnection
from typing import Any, Protocol
from zoneinfo import ZoneInfo

API_HOST = "api.openligadb.de"
API_VERSION = "v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
PROVIDER_TIME_ZONE_ID = "W. Europe Standard Time"
PROVIDER_TIME_ZONE = ZoneInfo("Europe/Berlin")


class OpenLigaDBQualificationError(RuntimeError):
    """A bounded failure of the read-only OpenLigaDB qualification."""


@dataclass(frozen=True)
class OpenLigaDBQualificationProfile:
    key: str
    competition_name: str
    league_id: int
    league_shortcut: str
    league_season: int
    sport_id: int
    authoritative_scope: str
    season_start_date: date
    season_end_date: date
    group_capacities: tuple[int, ...]
    expected_fixture_count: int | None = None
    expected_participant_count: int | None = None
    included_group_orders: tuple[int, ...] | None = None
    require_complete_double_round_robin: bool = False
    require_complete_group_round_robin: bool = False
    require_complete_swiss_league_phase: bool = False
    allow_missing_timezone_id: bool = False

    def __post_init__(self) -> None:
        if not self.key or not self.competition_name or not self.league_shortcut:
            raise ValueError("Qualification profile identity is required.")
        if self.league_id <= 0 or self.league_season <= 0 or self.sport_id <= 0:
            raise ValueError("Qualification profile identifiers must be positive.")
        if self.authoritative_scope not in {"partial", "complete_season"}:
            raise ValueError("Qualification profile scope is unsupported.")
        if self.season_end_date < self.season_start_date:
            raise ValueError("Qualification profile season dates are invalid.")
        if not self.group_capacities or any(
            capacity <= 0 for capacity in self.group_capacities
        ):
            raise ValueError("Qualification profile group capacities are invalid.")
        included_group_orders = self.included_group_orders or tuple(
            range(1, len(self.group_capacities) + 1)
        )
        if len(set(included_group_orders)) != len(included_group_orders) or any(
            order < 1 or order > len(self.group_capacities)
            for order in included_group_orders
        ):
            raise ValueError("Qualification profile included groups are invalid.")
        completeness_modes = sum(
            (
                self.require_complete_double_round_robin,
                self.require_complete_group_round_robin,
                self.require_complete_swiss_league_phase,
            )
        )
        if completeness_modes > 1:
            raise ValueError("Qualification profile completeness modes conflict.")
        if self.require_complete_double_round_robin and (
            self.expected_fixture_count is None
            or self.expected_participant_count is None
            or self.expected_participant_count % 2
            or len(self.group_capacities) != (self.expected_participant_count - 1) * 2
            or set(self.group_capacities) != {self.expected_participant_count // 2}
            or self.expected_fixture_count
            != self.expected_participant_count * (self.expected_participant_count - 1)
        ):
            raise ValueError(
                "Qualification profile has invalid double-round-robin semantics."
            )
        if self.require_complete_group_round_robin and (
            self.expected_fixture_count is None
            or self.expected_participant_count is None
            or self.expected_participant_count % len(included_group_orders)
        ):
            raise ValueError(
                "Qualification profile has invalid grouped-round-robin semantics."
            )
        if self.require_complete_group_round_robin:
            participants_per_group = self.expected_participant_count // len(
                included_group_orders
            )
            expected_group_capacity = participants_per_group * (
                participants_per_group - 1
            )
            included_capacities = tuple(
                self.group_capacities[order - 1] for order in included_group_orders
            )
            if (
                set(included_capacities) != {expected_group_capacity}
                or sum(included_capacities) != self.expected_fixture_count
            ):
                raise ValueError(
                    "Qualification profile has invalid grouped-round-robin semantics."
                )
        if self.require_complete_swiss_league_phase:
            included_capacities = tuple(
                self.group_capacities[order - 1] for order in included_group_orders
            )
            if (
                self.expected_fixture_count is None
                or self.expected_participant_count is None
                or self.expected_participant_count % 2
                or set(included_capacities)
                != {self.expected_participant_count // 2}
                or sum(included_capacities) != self.expected_fixture_count
            ):
                raise ValueError(
                    "Qualification profile has invalid Swiss league-phase semantics."
                )


DFB_POKAL_PROFILE = OpenLigaDBQualificationProfile(
    key="dfb-pokal",
    competition_name="DFB-Pokal",
    league_id=4945,
    league_shortcut="dfb",
    league_season=2026,
    sport_id=1,
    authoritative_scope="partial",
    season_start_date=date(2026, 8, 21),
    season_end_date=date(2027, 5, 29),
    group_capacities=(32, 16, 8, 4, 2, 1),
    allow_missing_timezone_id=True,
)
SECOND_BUNDESLIGA_PROFILE = OpenLigaDBQualificationProfile(
    key="2-bundesliga",
    competition_name="2. Bundesliga",
    league_id=4938,
    league_shortcut="bl2",
    league_season=2026,
    sport_id=1,
    authoritative_scope="complete_season",
    season_start_date=date(2026, 8, 7),
    season_end_date=date(2027, 5, 23),
    group_capacities=(9,) * 34,
    expected_fixture_count=306,
    expected_participant_count=18,
    require_complete_double_round_robin=True,
    allow_missing_timezone_id=True,
)
NATIONS_LEAGUE_A_GROUP_PHASE_PROFILE = OpenLigaDBQualificationProfile(
    key="nations-league-a-group-phase",
    competition_name="UEFA Nations League A group phase",
    league_id=5978,
    league_shortcut="nla",
    league_season=2026,
    sport_id=1,
    authoritative_scope="partial",
    season_start_date=date(2026, 9, 24),
    season_end_date=date(2026, 11, 17),
    group_capacities=(12, 12, 12, 12, 4, 4, 2, 2),
    expected_fixture_count=48,
    expected_participant_count=16,
    included_group_orders=(1, 2, 3, 4),
    require_complete_group_round_robin=True,
)
CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE = OpenLigaDBQualificationProfile(
    key="champions-league-league-phase",
    competition_name="UEFA Champions League league phase",
    league_id=4946,
    league_shortcut="ucl",
    league_season=2026,
    sport_id=1,
    authoritative_scope="partial",
    season_start_date=date(2026, 9, 8),
    season_end_date=date(2027, 1, 27),
    group_capacities=(18,) * 8 + (16, 8, 8, 4, 4, 2, 2, 1),
    expected_fixture_count=144,
    expected_participant_count=36,
    included_group_orders=tuple(range(1, 9)),
    require_complete_swiss_league_phase=True,
)
QUALIFICATION_PROFILES = {
    profile.key: profile
    for profile in (
        DFB_POKAL_PROFILE,
        SECOND_BUNDESLIGA_PROFILE,
        NATIONS_LEAGUE_A_GROUP_PHASE_PROFILE,
        CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE,
    )
}


@dataclass(frozen=True)
class OpenLigaDBQualificationResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class OpenLigaDBQualificationTransport(Protocol):
    def get(self, path: str) -> OpenLigaDBQualificationResponse: ...


class StdlibOpenLigaDBQualificationTransport:
    """Small read-only HTTPS transport for OpenLigaDB's public JSON API."""

    def get(self, path: str) -> OpenLigaDBQualificationResponse:
        if not path.startswith("/") or "?" in path or "#" in path:
            raise OpenLigaDBQualificationError(
                "OpenLigaDB qualification received an invalid request path."
            )
        connection = HTTPSConnection(API_HOST, timeout=10.0)
        try:
            connection.request("GET", path, headers={"Accept": "application/json"})
            response = connection.getresponse()
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise OpenLigaDBQualificationError(
                    "Provider response exceeded the safe limit."
                )
            return OpenLigaDBQualificationResponse(
                status=response.status,
                headers=dict(response.getheaders()),
                body=body,
            )
        except OpenLigaDBQualificationError:
            raise
        except (HTTPException, OSError) as error:
            raise OpenLigaDBQualificationError("Provider request failed.") from error
        finally:
            connection.close()


@dataclass(frozen=True)
class OpenLigaDBRoundEvidence:
    group_id: int
    group_order_id: int
    provider_name: str
    normalized_round: str
    fixture_count: int
    expected_fixture_capacity: int


@dataclass(frozen=True)
class OpenLigaDBQualificationEvidence:
    qualification_profile: str
    observed_at_utc: str
    api_version: str
    authoritative_scope: str
    league_id: int
    league_name: str
    league_shortcut: str
    league_season: int
    sport_id: int
    sport_name: str
    source_fixture_count: int
    fixture_count: int
    unique_fixture_ids: int
    fixture_ids_sha256: str
    participant_count: int
    participant_ids_sha256: str
    request_count: int
    earliest_kickoff_utc: str
    latest_kickoff_utc: str
    latest_source_update_utc: str
    missing_timezone_declarations: int
    status_counts: dict[str, int]
    rounds: tuple[OpenLigaDBRoundEvidence, ...]


def qualify_openligadb(
    *,
    profile: OpenLigaDBQualificationProfile = DFB_POKAL_PROFILE,
    transport: OpenLigaDBQualificationTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> OpenLigaDBQualificationEvidence:
    active_transport = transport or StdlibOpenLigaDBQualificationTransport()
    active_clock = clock or (lambda: datetime.now(UTC))

    if QUALIFICATION_PROFILES.get(profile.key) != profile:
        raise OpenLigaDBQualificationError("Qualification profile is not approved.")

    leagues = _request_list(
        active_transport, f"/getavailableleagues/{profile.league_season}"
    )
    league = _select_league(leagues, profile)
    league_name = _string(league, "leagueName")
    sport = _mapping(league, "sport")
    sport_name = _string(sport, "sportName")

    raw_groups = _request_list(
        active_transport,
        f"/getavailablegroups/{profile.league_shortcut}/{profile.league_season}",
    )
    groups = _validate_groups(raw_groups, profile)

    raw_matches = _request_list(
        active_transport,
        f"/getmatchdata/{profile.league_shortcut}/{profile.league_season}",
    )
    if not raw_matches:
        raise OpenLigaDBQualificationError("Provider returned no fixtures.")

    source_fixture_ids: set[int] = set()
    fixture_ids: set[int] = set()
    participant_ids: set[int] = set()
    kickoffs: list[datetime] = []
    source_updates: list[datetime] = []
    status_counts: Counter[str] = Counter()
    group_fixture_counts: Counter[int] = Counter()
    participant_appearances: Counter[int] = Counter()
    group_participants: defaultdict[int, set[int]] = defaultdict(set)
    directed_pairings: set[tuple[int, int]] = set()
    undirected_pairings: set[frozenset[int]] = set()
    missing_timezone_declarations = 0
    included_group_orders = set(
        profile.included_group_orders or range(1, len(profile.group_capacities) + 1)
    )

    for raw_match in raw_matches:
        match = _mapping_value(raw_match)
        fixture_id = _positive_int(match, "matchID")
        if fixture_id in source_fixture_ids:
            raise OpenLigaDBQualificationError(
                "Provider returned a duplicate fixture ID."
            )
        source_fixture_ids.add(fixture_id)

        if (
            _positive_int(match, "leagueId") != profile.league_id
            or _string(match, "leagueShortcut").casefold() != profile.league_shortcut
            or _season(match, "leagueSeason") != profile.league_season
        ):
            raise OpenLigaDBQualificationError(
                "A fixture belongs to the wrong competition or season."
            )

        match_group = _mapping(match, "group")
        group_id = _positive_int(match_group, "groupID")
        group_order_id = _positive_int(match_group, "groupOrderID")
        declared_group = groups.get(group_order_id)
        if (
            declared_group is None
            or _positive_int(declared_group, "groupID") != group_id
        ):
            raise OpenLigaDBQualificationError(
                "A fixture has an unknown or inconsistent round identity."
            )
        if _string(match_group, "groupName") != _string(declared_group, "groupName"):
            raise OpenLigaDBQualificationError(
                "A fixture has an inconsistent round name."
            )
        if group_order_id not in included_group_orders:
            continue
        fixture_ids.add(fixture_id)
        group_fixture_counts[group_order_id] += 1
        if (
            group_fixture_counts[group_order_id]
            > profile.group_capacities[group_order_id - 1]
        ):
            raise OpenLigaDBQualificationError(
                "A group exceeds the configured fixture capacity."
            )

        team1_id = _team_id(match, "team1")
        team2_id = _team_id(match, "team2")
        if team1_id == team2_id:
            raise OpenLigaDBQualificationError(
                "A fixture contains the same participant twice."
            )
        participant_ids.update((team1_id, team2_id))
        participant_appearances.update((team1_id, team2_id))
        group_participants[group_order_id].update((team1_id, team2_id))
        pairing = (team1_id, team2_id)
        if pairing in directed_pairings:
            raise OpenLigaDBQualificationError(
                "Provider returned a duplicate directed pairing."
            )
        directed_pairings.add(pairing)
        undirected_pairing = frozenset(pairing)
        if (
            profile.require_complete_swiss_league_phase
            and undirected_pairing in undirected_pairings
        ):
            raise OpenLigaDBQualificationError(
                "Provider returned a duplicate opponent pairing."
            )
        undirected_pairings.add(undirected_pairing)

        timezone_id = match.get("timeZoneID")
        if timezone_id is None or timezone_id == "":
            if not profile.allow_missing_timezone_id:
                raise OpenLigaDBQualificationError(
                    "Provider response has an invalid timeZoneID string field."
                )
            missing_timezone_declarations += 1
        elif not isinstance(timezone_id, str) or timezone_id.strip() != timezone_id:
            raise OpenLigaDBQualificationError(
                "Provider response has an invalid timeZoneID string field."
            )
        elif timezone_id != PROVIDER_TIME_ZONE_ID:
            raise OpenLigaDBQualificationError(
                "A fixture uses an unexpected provider timezone."
            )
        kickoff = _utc_datetime(match, "matchDateTimeUTC")
        season_floor = datetime.combine(
            profile.season_start_date, datetime.min.time(), UTC
        )
        season_ceiling = datetime.combine(
            profile.season_end_date, datetime.max.time(), UTC
        )
        if not season_floor <= kickoff <= season_ceiling:
            raise OpenLigaDBQualificationError(
                "A fixture kickoff falls outside the qualification season."
            )
        kickoffs.append(kickoff)
        source_updates.append(_provider_local_datetime(match, "lastUpdateDateTime"))
        status_counts[
            "FINISHED" if _boolean(match, "matchIsFinished") else "SCHEDULED"
        ] += 1

    observed_at = active_clock()
    if observed_at.tzinfo is None or observed_at.utcoffset() != UTC.utcoffset(
        observed_at
    ):
        raise OpenLigaDBQualificationError("Qualification clock must return UTC.")
    observed_at = observed_at.astimezone(UTC)
    if max(source_updates) > observed_at + timedelta(minutes=5):
        raise OpenLigaDBQualificationError("Provider source update is in the future.")

    if profile.require_complete_double_round_robin:
        _validate_complete_double_round_robin(
            profile,
            fixture_count=len(fixture_ids),
            participant_ids=participant_ids,
            participant_appearances=participant_appearances,
            group_fixture_counts=group_fixture_counts,
            group_participants=group_participants,
            directed_pairings=directed_pairings,
        )
    if profile.require_complete_group_round_robin:
        _validate_complete_group_round_robin(
            profile,
            fixture_count=len(fixture_ids),
            participant_ids=participant_ids,
            participant_appearances=participant_appearances,
            group_fixture_counts=group_fixture_counts,
            group_participants=group_participants,
            directed_pairings=directed_pairings,
        )
    if profile.require_complete_swiss_league_phase:
        _validate_complete_swiss_league_phase(
            profile,
            fixture_count=len(fixture_ids),
            participant_ids=participant_ids,
            participant_appearances=participant_appearances,
            group_fixture_counts=group_fixture_counts,
            group_participants=group_participants,
            undirected_pairings=undirected_pairings,
        )

    rounds = tuple(
        OpenLigaDBRoundEvidence(
            group_id=_positive_int(group, "groupID"),
            group_order_id=order,
            provider_name=_string(group, "groupName"),
            normalized_round=f"round-{order}",
            fixture_count=group_fixture_counts[order],
            expected_fixture_capacity=profile.group_capacities[order - 1],
        )
        for order, group in sorted(groups.items())
    )
    return OpenLigaDBQualificationEvidence(
        qualification_profile=profile.key,
        observed_at_utc=observed_at.isoformat(),
        api_version=API_VERSION,
        authoritative_scope=profile.authoritative_scope,
        league_id=profile.league_id,
        league_name=league_name,
        league_shortcut=profile.league_shortcut,
        league_season=profile.league_season,
        sport_id=profile.sport_id,
        sport_name=sport_name,
        source_fixture_count=len(source_fixture_ids),
        fixture_count=len(fixture_ids),
        unique_fixture_ids=len(fixture_ids),
        fixture_ids_sha256=_ids_hash(fixture_ids),
        participant_count=len(participant_ids),
        participant_ids_sha256=_ids_hash(participant_ids),
        request_count=3,
        earliest_kickoff_utc=min(kickoffs).isoformat(),
        latest_kickoff_utc=max(kickoffs).isoformat(),
        latest_source_update_utc=max(source_updates).isoformat(),
        missing_timezone_declarations=missing_timezone_declarations,
        status_counts=dict(sorted(status_counts.items())),
        rounds=rounds,
    )


def qualify_dfb_pokal(
    *,
    transport: OpenLigaDBQualificationTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> OpenLigaDBQualificationEvidence:
    return qualify_openligadb(
        profile=DFB_POKAL_PROFILE,
        transport=transport,
        clock=clock,
    )


def qualify_second_bundesliga(
    *,
    transport: OpenLigaDBQualificationTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> OpenLigaDBQualificationEvidence:
    return qualify_openligadb(
        profile=SECOND_BUNDESLIGA_PROFILE,
        transport=transport,
        clock=clock,
    )


def qualify_nations_league_a_group_phase(
    *,
    transport: OpenLigaDBQualificationTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> OpenLigaDBQualificationEvidence:
    return qualify_openligadb(
        profile=NATIONS_LEAGUE_A_GROUP_PHASE_PROFILE,
        transport=transport,
        clock=clock,
    )


def qualify_champions_league_league_phase(
    *,
    transport: OpenLigaDBQualificationTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> OpenLigaDBQualificationEvidence:
    return qualify_openligadb(
        profile=CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE,
        transport=transport,
        clock=clock,
    )


def render_qualification_evidence(
    evidence: OpenLigaDBQualificationEvidence,
) -> str:
    return json.dumps(asdict(evidence), indent=2, sort_keys=True)


def _select_league(
    values: Sequence[object], profile: OpenLigaDBQualificationProfile
) -> Mapping[str, Any]:
    matches: list[Mapping[str, Any]] = []
    for value in values:
        league = _mapping_value(value)
        shortcut = league.get("leagueShortcut")
        if isinstance(shortcut, str) and shortcut.casefold() == profile.league_shortcut:
            matches.append(league)
    if len(matches) != 1:
        raise OpenLigaDBQualificationError(
            "Provider did not return exactly one configured league."
        )
    league = matches[0]
    sport = _mapping(league, "sport")
    if (
        _positive_int(league, "leagueId") != profile.league_id
        or _season(league, "leagueSeason") != profile.league_season
        or _positive_int(sport, "sportId") != profile.sport_id
    ):
        raise OpenLigaDBQualificationError("Provider returned the wrong competition.")
    return league


def _validate_groups(
    values: Sequence[object], profile: OpenLigaDBQualificationProfile
) -> dict[int, Mapping[str, Any]]:
    groups: dict[int, Mapping[str, Any]] = {}
    group_ids: set[int] = set()
    for value in values:
        group = _mapping_value(value)
        order = _positive_int(group, "groupOrderID")
        group_id = _positive_int(group, "groupID")
        _string(group, "groupName")
        if order in groups or group_id in group_ids:
            raise OpenLigaDBQualificationError(
                "Provider returned duplicate round identity."
            )
        groups[order] = group
        group_ids.add(group_id)
    if set(groups) != set(range(1, len(profile.group_capacities) + 1)):
        raise OpenLigaDBQualificationError(
            "Provider returned an invalid configured group/round inventory."
        )
    return groups


def _validate_complete_double_round_robin(
    profile: OpenLigaDBQualificationProfile,
    *,
    fixture_count: int,
    participant_ids: set[int],
    participant_appearances: Counter[int],
    group_fixture_counts: Counter[int],
    group_participants: Mapping[int, set[int]],
    directed_pairings: set[tuple[int, int]],
) -> None:
    if fixture_count != profile.expected_fixture_count:
        raise OpenLigaDBQualificationError(
            f"Expected exactly {profile.expected_fixture_count} fixtures."
        )
    if len(participant_ids) != profile.expected_participant_count:
        raise OpenLigaDBQualificationError(
            f"Expected exactly {profile.expected_participant_count} participants."
        )
    expected_appearances = len(profile.group_capacities)
    if set(participant_appearances) != participant_ids or any(
        count != expected_appearances for count in participant_appearances.values()
    ):
        raise OpenLigaDBQualificationError(
            "Provider returned an incomplete participant schedule."
        )
    if any(
        group_fixture_counts[order] != capacity
        or group_participants[order] != participant_ids
        for order, capacity in enumerate(profile.group_capacities, start=1)
    ):
        raise OpenLigaDBQualificationError(
            "Provider returned an incomplete matchday schedule."
        )
    if len(directed_pairings) != profile.expected_fixture_count:
        raise OpenLigaDBQualificationError(
            "Provider returned an incomplete directed-pairing schedule."
        )


def _validate_complete_group_round_robin(
    profile: OpenLigaDBQualificationProfile,
    *,
    fixture_count: int,
    participant_ids: set[int],
    participant_appearances: Counter[int],
    group_fixture_counts: Counter[int],
    group_participants: Mapping[int, set[int]],
    directed_pairings: set[tuple[int, int]],
) -> None:
    if fixture_count != profile.expected_fixture_count:
        raise OpenLigaDBQualificationError(
            f"Expected exactly {profile.expected_fixture_count} fixtures."
        )
    if len(participant_ids) != profile.expected_participant_count:
        raise OpenLigaDBQualificationError(
            f"Expected exactly {profile.expected_participant_count} participants."
        )
    included_group_orders = profile.included_group_orders or ()
    participants_per_group = profile.expected_participant_count // len(
        included_group_orders
    )
    expected_appearances = (participants_per_group - 1) * 2
    if set(participant_appearances) != participant_ids or any(
        count != expected_appearances for count in participant_appearances.values()
    ):
        raise OpenLigaDBQualificationError(
            "Provider returned an incomplete grouped participant schedule."
        )
    observed_participants: set[int] = set()
    for order in included_group_orders:
        participants = group_participants[order]
        if (
            group_fixture_counts[order] != profile.group_capacities[order - 1]
            or len(participants) != participants_per_group
            or observed_participants.intersection(participants)
        ):
            raise OpenLigaDBQualificationError(
                "Provider returned an invalid complete group boundary."
            )
        observed_participants.update(participants)
    if observed_participants != participant_ids:
        raise OpenLigaDBQualificationError(
            "Provider returned an invalid complete group boundary."
        )
    if len(directed_pairings) != profile.expected_fixture_count:
        raise OpenLigaDBQualificationError(
            "Provider returned an incomplete grouped pairing schedule."
        )


def _validate_complete_swiss_league_phase(
    profile: OpenLigaDBQualificationProfile,
    *,
    fixture_count: int,
    participant_ids: set[int],
    participant_appearances: Counter[int],
    group_fixture_counts: Counter[int],
    group_participants: Mapping[int, set[int]],
    undirected_pairings: set[frozenset[int]],
) -> None:
    if fixture_count != profile.expected_fixture_count:
        raise OpenLigaDBQualificationError(
            f"Expected exactly {profile.expected_fixture_count} fixtures."
        )
    if len(participant_ids) != profile.expected_participant_count:
        raise OpenLigaDBQualificationError(
            f"Expected exactly {profile.expected_participant_count} participants."
        )
    included_group_orders = profile.included_group_orders or ()
    expected_appearances = len(included_group_orders)
    if set(participant_appearances) != participant_ids or any(
        count != expected_appearances for count in participant_appearances.values()
    ):
        raise OpenLigaDBQualificationError(
            "Provider returned an incomplete league-phase participant schedule."
        )
    if any(
        group_fixture_counts[order] != profile.group_capacities[order - 1]
        or group_participants[order] != participant_ids
        for order in included_group_orders
    ):
        raise OpenLigaDBQualificationError(
            "Provider returned an incomplete league-phase matchday schedule."
        )
    if len(undirected_pairings) != profile.expected_fixture_count:
        raise OpenLigaDBQualificationError(
            "Provider returned repeated league-phase opponents."
        )


def _request_list(
    transport: OpenLigaDBQualificationTransport,
    path: str,
) -> list[object]:
    response = transport.get(path)
    if response.status != 200:
        raise OpenLigaDBQualificationError(f"Provider returned HTTP {response.status}.")
    content_type = next(
        (
            value
            for key, value in response.headers.items()
            if key.casefold() == "content-type"
        ),
        "",
    )
    if "json" not in content_type.casefold():
        raise OpenLigaDBQualificationError("Provider returned a non-JSON response.")
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OpenLigaDBQualificationError(
            "Provider returned malformed JSON."
        ) from error
    if not isinstance(payload, list):
        raise OpenLigaDBQualificationError("Provider returned an invalid JSON root.")
    return payload


def _mapping(container: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    return _mapping_value(container.get(key))


def _mapping_value(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise OpenLigaDBQualificationError("Provider returned an invalid object field.")
    return value


def _positive_int(container: Mapping[str, Any], key: str) -> int:
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OpenLigaDBQualificationError(
            "Provider response has an invalid integer field."
        )
    return value


def _season(container: Mapping[str, Any], key: str) -> int:
    value = container.get(key)
    if isinstance(value, bool):
        raise OpenLigaDBQualificationError("Provider returned an invalid season.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    raise OpenLigaDBQualificationError("Provider returned an invalid season.")


def _string(container: Mapping[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OpenLigaDBQualificationError(
            f"Provider response has an invalid {key} string field."
        )
    return value.strip()


def _boolean(container: Mapping[str, Any], key: str) -> bool:
    value = container.get(key)
    if not isinstance(value, bool):
        raise OpenLigaDBQualificationError(
            "Provider response has an invalid boolean field."
        )
    return value


def _team_id(match: Mapping[str, Any], key: str) -> int:
    team = _mapping(match, key)
    team_id = _positive_int(team, "teamId")
    _string(team, "teamName")
    return team_id


def _utc_datetime(container: Mapping[str, Any], key: str) -> datetime:
    value = _string(container, key)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OpenLigaDBQualificationError(
            "Provider response has an invalid datetime field."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise OpenLigaDBQualificationError("Provider datetime is not UTC.")
    return parsed


def _provider_local_datetime(container: Mapping[str, Any], key: str) -> datetime:
    value = _string(container, key)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise OpenLigaDBQualificationError(
            "Provider response has an invalid update datetime."
        ) from error
    if parsed.tzinfo is not None:
        raise OpenLigaDBQualificationError(
            "Provider update datetime unexpectedly contains a timezone."
        )
    return parsed.replace(tzinfo=PROVIDER_TIME_ZONE).astimezone(UTC)


def _ids_hash(values: set[int]) -> str:
    serialized = ",".join(str(value) for value in sorted(values)).encode()
    return hashlib.sha256(serialized).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Perform read-only OpenLigaDB calls and print bounded competition "
            "qualification evidence."
        )
    )
    parser.add_argument(
        "--competition",
        choices=tuple(QUALIFICATION_PROFILES),
        default=DFB_POKAL_PROFILE.key,
    )
    arguments = parser.parse_args(argv)
    try:
        if arguments.competition == DFB_POKAL_PROFILE.key:
            evidence = qualify_dfb_pokal()
        elif arguments.competition == SECOND_BUNDESLIGA_PROFILE.key:
            evidence = qualify_second_bundesliga()
        elif arguments.competition == NATIONS_LEAGUE_A_GROUP_PHASE_PROFILE.key:
            evidence = qualify_nations_league_a_group_phase()
        else:
            evidence = qualify_champions_league_league_phase()
    except OpenLigaDBQualificationError as error:
        parser.exit(status=1, message=f"OpenLigaDB qualification failed: {error}\n")
    print(render_qualification_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
