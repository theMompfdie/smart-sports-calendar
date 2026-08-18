import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from http.client import HTTPException, HTTPSConnection
from typing import Any, Protocol
from zoneinfo import ZoneInfo

API_HOST = "api.openligadb.de"
API_VERSION = "v1"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
DFB_POKAL_LEAGUE_ID = 4945
DFB_POKAL_SHORTCUT = "dfb"
DFB_POKAL_SEASON = 2026
DFB_POKAL_SPORT_ID = 1
DFB_POKAL_GROUP_COUNT = 6
DFB_POKAL_GROUP_CAPACITIES = {1: 32, 2: 16, 3: 8, 4: 4, 5: 2, 6: 1}
PROVIDER_TIME_ZONE_ID = "W. Europe Standard Time"
PROVIDER_TIME_ZONE = ZoneInfo("Europe/Berlin")


class OpenLigaDBQualificationError(RuntimeError):
    """A bounded failure of the read-only OpenLigaDB qualification."""


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
    fixture_count: int
    unique_fixture_ids: int
    fixture_ids_sha256: str
    participant_count: int
    participant_ids_sha256: str
    request_count: int
    earliest_kickoff_utc: str
    latest_kickoff_utc: str
    latest_source_update_utc: str
    status_counts: dict[str, int]
    rounds: tuple[OpenLigaDBRoundEvidence, ...]


def qualify_dfb_pokal(
    *,
    transport: OpenLigaDBQualificationTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> OpenLigaDBQualificationEvidence:
    active_transport = transport or StdlibOpenLigaDBQualificationTransport()
    active_clock = clock or (lambda: datetime.now(UTC))

    leagues = _request_list(
        active_transport, f"/getavailableleagues/{DFB_POKAL_SEASON}"
    )
    league = _select_league(leagues)
    league_name = _string(league, "leagueName")
    sport = _mapping(league, "sport")
    sport_name = _string(sport, "sportName")

    raw_groups = _request_list(
        active_transport,
        f"/getavailablegroups/{DFB_POKAL_SHORTCUT}/{DFB_POKAL_SEASON}",
    )
    groups = _validate_groups(raw_groups)

    raw_matches = _request_list(
        active_transport,
        f"/getmatchdata/{DFB_POKAL_SHORTCUT}/{DFB_POKAL_SEASON}",
    )
    if not raw_matches:
        raise OpenLigaDBQualificationError("Provider returned no fixtures.")

    fixture_ids: set[int] = set()
    participant_ids: set[int] = set()
    kickoffs: list[datetime] = []
    source_updates: list[datetime] = []
    status_counts: Counter[str] = Counter()
    group_fixture_counts: Counter[int] = Counter()

    for raw_match in raw_matches:
        match = _mapping_value(raw_match)
        fixture_id = _positive_int(match, "matchID")
        if fixture_id in fixture_ids:
            raise OpenLigaDBQualificationError(
                "Provider returned a duplicate fixture ID."
            )
        fixture_ids.add(fixture_id)

        if (
            _positive_int(match, "leagueId") != DFB_POKAL_LEAGUE_ID
            or _string(match, "leagueShortcut").casefold() != DFB_POKAL_SHORTCUT
            or _season(match, "leagueSeason") != DFB_POKAL_SEASON
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
        group_fixture_counts[group_order_id] += 1
        if (
            group_fixture_counts[group_order_id]
            > DFB_POKAL_GROUP_CAPACITIES[group_order_id]
        ):
            raise OpenLigaDBQualificationError(
                "A round exceeds the DFB-Pokal fixture capacity."
            )

        team1_id = _team_id(match, "team1")
        team2_id = _team_id(match, "team2")
        if team1_id == team2_id:
            raise OpenLigaDBQualificationError(
                "A fixture contains the same participant twice."
            )
        participant_ids.update((team1_id, team2_id))

        if _string(match, "timeZoneID") != PROVIDER_TIME_ZONE_ID:
            raise OpenLigaDBQualificationError(
                "A fixture uses an unexpected provider timezone."
            )
        kickoff = _utc_datetime(match, "matchDateTimeUTC")
        if (
            not datetime(2026, 8, 1, tzinfo=UTC)
            <= kickoff
            < datetime(2027, 6, 30, tzinfo=UTC)
        ):
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

    rounds = tuple(
        OpenLigaDBRoundEvidence(
            group_id=_positive_int(group, "groupID"),
            group_order_id=order,
            provider_name=_string(group, "groupName"),
            normalized_round=f"round-{order}",
            fixture_count=group_fixture_counts[order],
            expected_fixture_capacity=DFB_POKAL_GROUP_CAPACITIES[order],
        )
        for order, group in sorted(groups.items())
    )
    return OpenLigaDBQualificationEvidence(
        qualification_profile="dfb-pokal",
        observed_at_utc=observed_at.isoformat(),
        api_version=API_VERSION,
        authoritative_scope="partial",
        league_id=DFB_POKAL_LEAGUE_ID,
        league_name=league_name,
        league_shortcut=DFB_POKAL_SHORTCUT,
        league_season=DFB_POKAL_SEASON,
        sport_id=DFB_POKAL_SPORT_ID,
        sport_name=sport_name,
        fixture_count=len(fixture_ids),
        unique_fixture_ids=len(fixture_ids),
        fixture_ids_sha256=_ids_hash(fixture_ids),
        participant_count=len(participant_ids),
        participant_ids_sha256=_ids_hash(participant_ids),
        request_count=3,
        earliest_kickoff_utc=min(kickoffs).isoformat(),
        latest_kickoff_utc=max(kickoffs).isoformat(),
        latest_source_update_utc=max(source_updates).isoformat(),
        status_counts=dict(sorted(status_counts.items())),
        rounds=rounds,
    )


def render_qualification_evidence(
    evidence: OpenLigaDBQualificationEvidence,
) -> str:
    return json.dumps(asdict(evidence), indent=2, sort_keys=True)


def _select_league(values: Sequence[object]) -> Mapping[str, Any]:
    matches: list[Mapping[str, Any]] = []
    for value in values:
        league = _mapping_value(value)
        shortcut = league.get("leagueShortcut")
        if isinstance(shortcut, str) and shortcut.casefold() == DFB_POKAL_SHORTCUT:
            matches.append(league)
    if len(matches) != 1:
        raise OpenLigaDBQualificationError(
            "Provider did not return exactly one DFB-Pokal league."
        )
    league = matches[0]
    sport = _mapping(league, "sport")
    if (
        _positive_int(league, "leagueId") != DFB_POKAL_LEAGUE_ID
        or _season(league, "leagueSeason") != DFB_POKAL_SEASON
        or _positive_int(sport, "sportId") != DFB_POKAL_SPORT_ID
    ):
        raise OpenLigaDBQualificationError("Provider returned the wrong competition.")
    return league


def _validate_groups(values: Sequence[object]) -> dict[int, Mapping[str, Any]]:
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
    if set(groups) != set(range(1, DFB_POKAL_GROUP_COUNT + 1)):
        raise OpenLigaDBQualificationError(
            "Provider returned an invalid DFB-Pokal round inventory."
        )
    return groups


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
            "Provider response has an invalid string field."
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
            "Perform read-only OpenLigaDB calls and print bounded DFB-Pokal "
            "qualification evidence."
        )
    )
    parser.parse_args(argv)
    try:
        evidence = qualify_dfb_pokal()
    except OpenLigaDBQualificationError as error:
        parser.exit(status=1, message=f"OpenLigaDB qualification failed: {error}\n")
    print(render_qualification_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
