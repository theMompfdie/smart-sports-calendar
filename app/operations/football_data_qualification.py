import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from http.client import HTTPSConnection
from typing import Any, Protocol

API_HOST = "api.football-data.org"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
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
        except OSError as error:
            raise QualificationError("Provider request failed.") from error
        finally:
            connection.close()


@dataclass(frozen=True)
class FootballDataQualificationEvidence:
    api_version: str
    competition_id: int
    competition_code: str
    season_id: int
    season_start_date: str
    season_end_date: str
    team_count: int
    match_count: int
    unique_match_ids: int
    match_ids_sha256: str
    earliest_kickoff_utc: str
    latest_kickoff_utc: str
    latest_source_update_utc: str
    status_counts: dict[str, int]
    requests_available_minimum: int | None


def qualify_football_data(
    api_key: str,
    *,
    season: int = 2026,
    transport: QualificationTransport | None = None,
) -> FootballDataQualificationEvidence:
    if not api_key.strip():
        raise QualificationError("FOOTBALL_DATA_API_KEY is required.")
    if season < 2000 or season > 2100:
        raise QualificationError("Season is outside the supported range.")

    active_transport = transport or StdlibQualificationTransport()
    paths = (
        "/v4/competitions/PL",
        f"/v4/competitions/PL/teams?season={season}",
        f"/v4/competitions/PL/matches?season={season}&limit=500",
    )
    responses = tuple(_request_json(active_transport, path, api_key) for path in paths)
    competition, teams_payload, matches_payload = (item[0] for item in responses)
    headers = tuple(item[1] for item in responses)

    competition_id = _positive_int(competition, "id")
    if competition.get("code") != "PL":
        raise QualificationError("Competition code is not PL.")

    current_season = _mapping(competition, "currentSeason")
    season_id = _positive_int(current_season, "id")
    start_date = _string(current_season, "startDate")
    end_date = _string(current_season, "endDate")
    if not start_date.startswith(f"{season}-"):
        raise QualificationError("Provider current season does not match the request.")

    teams = _list(teams_payload, "teams")
    team_ids = {_positive_int(_mapping_value(team), "id") for team in teams}
    if len(teams) != 20 or len(team_ids) != 20:
        raise QualificationError("Expected exactly 20 distinct Premier League teams.")

    matches = _list(matches_payload, "matches")
    result_set = _mapping(matches_payload, "resultSet")
    declared_count = _positive_int(result_set, "count")
    if declared_count != 380 or len(matches) != 380:
        raise QualificationError("Expected a complete 380-match Premier League season.")

    match_ids: set[int] = set()
    kickoffs: list[datetime] = []
    source_updates: list[datetime] = []
    statuses: Counter[str] = Counter()
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

        status = _string(match, "status")
        if status not in SUPPORTED_STATUSES:
            raise QualificationError("Provider returned an unsupported match status.")
        statuses[status] += 1
        kickoffs.append(_utc_datetime(_string(match, "utcDate")))
        source_updates.append(_utc_datetime(_string(match, "lastUpdated")))

    api_versions = {_header_value(item, "X-API-Version") for item in headers}
    if api_versions != {"v4"}:
        raise QualificationError("Provider API version is not consistently v4.")

    remaining = tuple(
        value
        for item in headers
        if (value := _optional_int_header(item, "X-RequestsAvailable")) is not None
    )
    return FootballDataQualificationEvidence(
        api_version="v4",
        competition_id=competition_id,
        competition_code="PL",
        season_id=season_id,
        season_start_date=start_date,
        season_end_date=end_date,
        team_count=len(team_ids),
        match_count=len(matches),
        unique_match_ids=len(match_ids),
        match_ids_sha256=_identity_fingerprint(match_ids),
        earliest_kickoff_utc=min(kickoffs).isoformat(),
        latest_kickoff_utc=max(kickoffs).isoformat(),
        latest_source_update_utc=max(source_updates).isoformat(),
        status_counts=dict(sorted(statuses.items())),
        requests_available_minimum=min(remaining) if remaining else None,
    )


def render_qualification_evidence(evidence: FootballDataQualificationEvidence) -> str:
    return json.dumps(asdict(evidence), indent=2, sort_keys=True)


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
        raise QualificationError("Provider response has an invalid integer field.")
    return value


def _string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QualificationError("Provider response has an invalid string field.")
    return value


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
            "Perform three read-only football-data.org calls and print only "
            "secret-safe Premier League qualification evidence."
        )
    )
    parser.add_argument("--season", type=int, default=2026)
    arguments = parser.parse_args(argv)
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    try:
        evidence = qualify_football_data(api_key, season=arguments.season)
    except QualificationError as error:
        parser.exit(status=1, message=f"football-data qualification failed: {error}\n")
    print(render_qualification_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
