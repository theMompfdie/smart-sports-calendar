import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from http.client import HTTPException, HTTPSConnection
from typing import Any, Protocol

from app.providers.football_data.competition_mappings import (
    BUNDESLIGA_MAPPING,
    PREMIER_LEAGUE_MAPPING,
)

API_HOST = "api.football-data.org"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MATCH_PAGE_LIMIT = 500
SUPPORTED_STATUSES = {
    "SCHEDULED",
    "TIMED",
    "IN_PLAY",
    "PAUSED",
    "EXTRA_TIME",
    "PENALTY_SHOOTOUT",
    "FINISHED",
    "SUSPENDED",
    "POSTPONED",
    "CANCELLED",
    "AWARDED",
}


class QualificationError(RuntimeError):
    """A secret-safe failure of the read-only provider qualification."""


@dataclass(frozen=True)
class FootballDataQualificationProfile:
    key: str
    competition_name: str
    competition_code: str
    competition_id: int
    expected_team_count: int
    expected_match_count: int
    expected_matchdays: int

    def __post_init__(self) -> None:
        if not self.key or not self.competition_name or not self.competition_code:
            raise ValueError("Qualification profile identity is required.")
        if self.competition_id <= 0 or self.expected_team_count <= 0:
            raise ValueError("Qualification profile counts must be positive.")
        if self.expected_team_count % 2:
            raise ValueError("Qualification profile requires an even team count.")
        if self.expected_matchdays != (self.expected_team_count - 1) * 2:
            raise ValueError("Qualification profile has invalid matchday semantics.")
        if self.expected_match_count != (
            self.expected_team_count * (self.expected_team_count - 1)
        ):
            raise ValueError("Qualification profile is not a double round robin.")


PREMIER_LEAGUE_PROFILE = FootballDataQualificationProfile(
    key="premier-league",
    competition_name="Premier League",
    competition_code=PREMIER_LEAGUE_MAPPING.external_code,
    competition_id=PREMIER_LEAGUE_MAPPING.external_id,
    expected_team_count=20,
    expected_match_count=380,
    expected_matchdays=38,
)
BUNDESLIGA_PROFILE = FootballDataQualificationProfile(
    key="bundesliga",
    competition_name="Bundesliga",
    competition_code=BUNDESLIGA_MAPPING.external_code,
    competition_id=BUNDESLIGA_MAPPING.external_id,
    expected_team_count=18,
    expected_match_count=306,
    expected_matchdays=34,
)
QUALIFICATION_PROFILES = {
    profile.key: profile for profile in (PREMIER_LEAGUE_PROFILE, BUNDESLIGA_PROFILE)
}


@dataclass(frozen=True)
class QualificationResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class QualificationTransport(Protocol):
    def get(self, path: str, api_key: str) -> QualificationResponse: ...


class StdlibQualificationTransport:
    def get(self, path: str, api_key: str) -> QualificationResponse:
        connection = HTTPSConnection(API_HOST, timeout=10.0)
        try:
            connection.request(
                "GET",
                path,
                headers={"Accept": "application/json", "X-Auth-Token": api_key},
            )
            response = connection.getresponse()
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise QualificationError("Provider response exceeded the safe limit.")
            return QualificationResponse(
                status=response.status,
                headers=dict(response.getheaders()),
                body=body,
            )
        except QualificationError:
            raise
        except (HTTPException, OSError) as error:
            raise QualificationError("Provider request failed.") from error
        finally:
            connection.close()


@dataclass(frozen=True)
class FootballDataQualificationEvidence:
    qualification_profile: str
    observed_at_utc: str
    api_version: str
    competition_id: int
    competition_code: str
    season_id: int
    season_start_date: str
    season_end_date: str
    team_count: int
    match_count: int
    unique_match_ids: int
    match_page_count: int
    request_count: int
    match_ids_sha256: str
    earliest_kickoff_utc: str
    latest_kickoff_utc: str
    latest_source_update_utc: str
    status_counts: dict[str, int]
    requests_available_minimum: int | None


def qualify_football_data(
    api_key: str,
    *,
    profile: FootballDataQualificationProfile = PREMIER_LEAGUE_PROFILE,
    season: int = 2026,
    transport: QualificationTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FootballDataQualificationEvidence:
    if not api_key.strip():
        raise QualificationError("FOOTBALL_DATA_API_KEY is required.")
    if season < 2000 or season > 2100:
        raise QualificationError("Season is outside the supported range.")
    if QUALIFICATION_PROFILES.get(profile.key) != profile:
        raise QualificationError("Qualification profile is not approved.")

    active_transport = transport or StdlibQualificationTransport()
    active_clock = clock or (lambda: datetime.now(UTC))
    headers: list[Mapping[str, str]] = []

    competition, response_headers = _request_json(
        active_transport,
        f"/v4/competitions/{profile.competition_code}",
        api_key,
    )
    headers.append(response_headers)
    competition_id = _positive_int(competition, "id")
    if (
        competition_id != profile.competition_id
        or competition.get("code") != profile.competition_code
    ):
        raise QualificationError("Provider returned the wrong competition.")

    current_season = _mapping(competition, "currentSeason")
    season_id = _positive_int(current_season, "id")
    start_date = _date(_string(current_season, "startDate"))
    end_date = _date(_string(current_season, "endDate"))
    if start_date.year != season or end_date < start_date:
        raise QualificationError("Provider current season does not match the request.")

    teams_payload, response_headers = _request_json(
        active_transport,
        f"/v4/competitions/{profile.competition_code}/teams?season={season}",
        api_key,
    )
    headers.append(response_headers)
    teams = _list(teams_payload, "teams")
    team_ids = {_positive_int(_mapping_value(team), "id") for team in teams}
    if (
        len(teams) != profile.expected_team_count
        or len(team_ids) != profile.expected_team_count
    ):
        raise QualificationError(
            f"Expected exactly {profile.expected_team_count} distinct "
            f"{profile.competition_name} teams."
        )

    matches, match_headers = _request_match_pages(
        active_transport,
        api_key=api_key,
        profile=profile,
        season=season,
    )
    headers.extend(match_headers)

    match_ids: set[int] = set()
    kickoffs: list[datetime] = []
    source_updates: list[datetime] = []
    statuses: Counter[str] = Counter()
    appearances: Counter[int] = Counter()
    pairings: set[tuple[int, int]] = set()
    matchday_participants: defaultdict[int, set[int]] = defaultdict(set)
    matchday_counts: Counter[int] = Counter()
    for raw_match in matches:
        match = _mapping_value(raw_match)
        match_id = _positive_int(match, "id")
        if match_id in match_ids:
            raise QualificationError("Provider returned a duplicate match ID.")
        match_ids.add(match_id)

        if _positive_int(_mapping(match, "competition"), "id") != competition_id:
            raise QualificationError("A match belongs to the wrong competition.")
        if _positive_int(_mapping(match, "season"), "id") != season_id:
            raise QualificationError("A match belongs to the wrong season.")

        home_id = _positive_int(_mapping(match, "homeTeam"), "id")
        away_id = _positive_int(_mapping(match, "awayTeam"), "id")
        if home_id == away_id or home_id not in team_ids or away_id not in team_ids:
            raise QualificationError("A match contains invalid participants.")
        pairing = (home_id, away_id)
        if pairing in pairings:
            raise QualificationError("Provider returned a duplicate home/away pairing.")
        pairings.add(pairing)
        appearances.update(pairing)

        if _string(match, "stage") != "REGULAR_SEASON":
            raise QualificationError("A match belongs to an unsupported stage.")
        matchday = _positive_int(match, "matchday")
        if matchday > profile.expected_matchdays:
            raise QualificationError("A match belongs to an invalid matchday.")
        matchday_counts[matchday] += 1
        matchday_participants[matchday].update(pairing)

        status = _string(match, "status")
        if status not in SUPPORTED_STATUSES:
            raise QualificationError("Provider returned an unsupported match status.")
        statuses[status] += 1
        kickoffs.append(_utc_datetime(_string(match, "utcDate")))
        source_updates.append(_utc_datetime(_string(match, "lastUpdated")))

    _validate_schedule(
        profile,
        team_ids=team_ids,
        appearances=appearances,
        matchday_counts=matchday_counts,
        matchday_participants=matchday_participants,
    )
    observed_at = _utc_now(active_clock)
    _validate_freshness(
        source_updates,
        observed_at=observed_at,
        season_start=start_date,
        season_end=end_date,
    )

    api_versions = {_header_value(item, "X-API-Version") for item in headers}
    if api_versions != {"v4"}:
        raise QualificationError("Provider API version is not consistently v4.")

    remaining = tuple(
        value
        for item in headers
        if (value := _optional_int_header(item, "X-RequestsAvailable")) is not None
    )
    return FootballDataQualificationEvidence(
        qualification_profile=profile.key,
        observed_at_utc=observed_at.isoformat(),
        api_version="v4",
        competition_id=competition_id,
        competition_code=profile.competition_code,
        season_id=season_id,
        season_start_date=start_date.isoformat(),
        season_end_date=end_date.isoformat(),
        team_count=len(team_ids),
        match_count=len(matches),
        unique_match_ids=len(match_ids),
        match_page_count=len(match_headers),
        request_count=len(headers),
        match_ids_sha256=_identity_fingerprint(match_ids),
        earliest_kickoff_utc=min(kickoffs).isoformat(),
        latest_kickoff_utc=max(kickoffs).isoformat(),
        latest_source_update_utc=max(source_updates).isoformat(),
        status_counts=dict(sorted(statuses.items())),
        requests_available_minimum=min(remaining) if remaining else None,
    )


def render_qualification_evidence(evidence: FootballDataQualificationEvidence) -> str:
    return json.dumps(asdict(evidence), indent=2, sort_keys=True)


def _request_match_pages(
    transport: QualificationTransport,
    *,
    api_key: str,
    profile: FootballDataQualificationProfile,
    season: int,
) -> tuple[list[Any], list[Mapping[str, str]]]:
    matches: list[Any] = []
    headers: list[Mapping[str, str]] = []
    while len(matches) < profile.expected_match_count:
        offset = len(matches)
        path = (
            f"/v4/competitions/{profile.competition_code}/matches"
            f"?season={season}&limit={MATCH_PAGE_LIMIT}"
        )
        if offset:
            path = f"{path}&offset={offset}"
        payload, response_headers = _request_json(transport, path, api_key)
        headers.append(response_headers)
        _validate_match_filters(
            payload,
            season=season,
            limit=MATCH_PAGE_LIMIT,
            offset=offset,
        )
        page = _list(payload, "matches")
        declared_count = _non_negative_int(_mapping(payload, "resultSet"), "count")
        if declared_count != len(page):
            raise QualificationError("Provider match result count is inconsistent.")
        if not page:
            raise QualificationError(
                "Provider returned an unexpected empty match page."
            )
        if len(page) > MATCH_PAGE_LIMIT:
            raise QualificationError(
                "Provider exceeded the requested match page limit."
            )
        if len(matches) + len(page) > profile.expected_match_count:
            raise QualificationError("Provider returned more matches than expected.")
        matches.extend(page)
        if len(page) < MATCH_PAGE_LIMIT:
            break

    if len(matches) != profile.expected_match_count:
        raise QualificationError(
            f"Expected a complete {profile.expected_match_count}-match "
            f"{profile.competition_name} season."
        )
    return matches, headers


def _validate_match_filters(
    payload: Mapping[str, Any],
    *,
    season: int,
    limit: int,
    offset: int,
) -> None:
    filters = _mapping(payload, "filters")
    response_season = filters.get("season")
    if isinstance(response_season, bool) or str(response_season) != str(season):
        raise QualificationError("Provider returned the wrong match season filter.")
    if _filter_int(filters, "limit", default=limit) != limit:
        raise QualificationError("Provider returned the wrong match limit filter.")
    if _filter_int(filters, "offset", default=0) != offset:
        raise QualificationError("Provider returned the wrong match offset filter.")


def _validate_schedule(
    profile: FootballDataQualificationProfile,
    *,
    team_ids: set[int],
    appearances: Counter[int],
    matchday_counts: Counter[int],
    matchday_participants: Mapping[int, set[int]],
) -> None:
    expected_matchdays = set(range(1, profile.expected_matchdays + 1))
    if set(appearances) != team_ids or any(
        count != profile.expected_matchdays for count in appearances.values()
    ):
        raise QualificationError(
            "Provider schedule is not a complete double round robin."
        )
    if set(matchday_counts) != expected_matchdays or any(
        count != profile.expected_team_count // 2 for count in matchday_counts.values()
    ):
        raise QualificationError("Provider schedule has incomplete matchday counts.")
    if any(
        matchday_participants[matchday] != team_ids for matchday in expected_matchdays
    ):
        raise QualificationError("Provider schedule has invalid matchday participants.")


def _validate_freshness(
    source_updates: list[datetime],
    *,
    observed_at: datetime,
    season_start: date,
    season_end: date,
) -> None:
    latest_update = max(source_updates)
    if latest_update > observed_at + timedelta(minutes=5):
        raise QualificationError("Provider source update is in the future.")
    if observed_at.date() < season_start:
        maximum_age = timedelta(days=60)
    elif observed_at.date() <= season_end:
        maximum_age = timedelta(days=14)
    else:
        maximum_age = timedelta(days=30)
    if observed_at - latest_update > maximum_age:
        raise QualificationError("Provider snapshot is stale for its season phase.")


def _request_json(
    transport: QualificationTransport,
    path: str,
    api_key: str,
) -> tuple[Mapping[str, Any], Mapping[str, str]]:
    response = transport.get(path, api_key)
    if response.status != 200:
        raise QualificationError(f"Provider returned HTTP {response.status}.")
    content_type = _header_value(response.headers, "Content-Type")
    if (
        content_type is None
        or content_type.split(";", 1)[0].strip() != "application/json"
    ):
        raise QualificationError("Provider returned an unexpected content type.")
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise QualificationError("Provider returned malformed JSON.") from error
    if not isinstance(payload, dict):
        raise QualificationError("Provider returned an invalid JSON root.")
    return payload, response.headers


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    return _mapping_value(payload.get(key))


def _mapping_value(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise QualificationError("Provider response has an invalid object field.")
    return value


def _list(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise QualificationError("Provider response has an invalid collection field.")
    return value


def _positive_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise QualificationError(
            f"Provider response has an invalid integer field: {key}."
        )
    return value


def _non_negative_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QualificationError(
            f"Provider response has an invalid integer field: {key}."
        )
    return value


def _filter_int(
    payload: Mapping[str, Any],
    key: str,
    *,
    default: int | None = None,
) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool):
        raise QualificationError(f"Provider returned an invalid {key} match filter.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise QualificationError(f"Provider returned an invalid {key} match filter.")


def _string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QualificationError("Provider response has an invalid string field.")
    return value.strip()


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise QualificationError("Provider response has an invalid date.") from error


def _utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise QualificationError(
            "Provider response has an invalid timestamp."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise QualificationError("Provider timestamp is not UTC.")
    return parsed.astimezone(UTC)


def _utc_now(clock: Callable[[], datetime]) -> datetime:
    observed_at = clock()
    if observed_at.tzinfo is None or observed_at.utcoffset() != UTC.utcoffset(
        observed_at
    ):
        raise QualificationError("Qualification clock must return UTC.")
    return observed_at.astimezone(UTC)


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    return next(
        (value for key, value in headers.items() if key.casefold() == expected), None
    )


def _optional_int_header(headers: Mapping[str, str], name: str) -> int | None:
    value = _header_value(headers, name)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise QualificationError(
            "Provider returned an invalid quota header."
        ) from error
    if parsed < 0:
        raise QualificationError("Provider returned an invalid quota header.")
    return parsed


def _identity_fingerprint(identifiers: set[int]) -> str:
    canonical = "\n".join(str(identifier) for identifier in sorted(identifiers))
    return hashlib.sha256(canonical.encode()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Perform read-only football-data.org calls and print only "
            "secret-safe competition qualification evidence."
        )
    )
    parser.add_argument(
        "--competition",
        choices=tuple(QUALIFICATION_PROFILES),
        default=PREMIER_LEAGUE_PROFILE.key,
    )
    parser.add_argument("--season", type=int, default=2026)
    arguments = parser.parse_args(argv)
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    try:
        evidence = qualify_football_data(
            api_key,
            profile=QUALIFICATION_PROFILES[arguments.competition],
            season=arguments.season,
        )
    except QualificationError as error:
        parser.exit(status=1, message=f"football-data qualification failed: {error}\n")
    print(render_qualification_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
