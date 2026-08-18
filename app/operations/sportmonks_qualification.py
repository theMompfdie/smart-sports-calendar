import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from http.client import HTTPException, HTTPSConnection
from typing import Any, Protocol

API_HOST = "api.sportmonks.com"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
FIXTURE_PAGE_LIMIT = 50
MAX_FIXTURE_PAGES = 20
DFB_POKAL_LEAGUE_ID = 109
DFB_POKAL_SEASON_NAME = "2026/2027"
_LEG_PATTERN = re.compile(r"^[1-9][0-9]*/[1-9][0-9]*$")


class SportmonksQualificationError(RuntimeError):
    """A secret-safe failure of the read-only Sportmonks qualification."""


@dataclass(frozen=True)
class SportmonksQualificationResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class SportmonksQualificationTransport(Protocol):
    def get(
        self,
        path: str,
        api_token: str,
    ) -> SportmonksQualificationResponse: ...


class StdlibSportmonksQualificationTransport:
    """Bounded HTTPS transport that keeps the API token out of request URLs."""

    def get(
        self,
        path: str,
        api_token: str,
    ) -> SportmonksQualificationResponse:
        if "api_token=" in path.casefold():
            raise SportmonksQualificationError(
                "Sportmonks qualification forbids tokens in request URLs."
            )
        connection = HTTPSConnection(API_HOST, timeout=10.0)
        try:
            connection.request(
                "GET",
                path,
                headers={
                    "Accept": "application/json",
                    "Authorization": api_token,
                },
            )
            response = connection.getresponse()
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise SportmonksQualificationError(
                    "Provider response exceeded the safe limit."
                )
            return SportmonksQualificationResponse(
                status=response.status,
                headers=dict(response.getheaders()),
                body=body,
            )
        except SportmonksQualificationError:
            raise
        except (HTTPException, OSError) as error:
            raise SportmonksQualificationError("Provider request failed.") from error
        finally:
            connection.close()


@dataclass(frozen=True)
class SportmonksRoundEvidence:
    stage_id: int
    stage_name: str
    round_id: int
    round_name: str
    fixture_count: int
    placeholder_fixture_count: int


@dataclass(frozen=True)
class SportmonksQualificationEvidence:
    qualification_profile: str
    observed_at_utc: str
    api_version: str
    authoritative_scope: str
    league_id: int
    league_name: str
    season_id: int
    season_name: str
    season_start_date: str
    season_end_date: str
    fixture_count: int
    unique_fixture_ids: int
    fixture_ids_sha256: str
    participant_count: int
    participant_ids_sha256: str
    fixture_page_count: int
    request_count: int
    earliest_kickoff_utc: str | None
    latest_kickoff_utc: str | None
    unscheduled_fixture_count: int
    placeholder_fixture_count: int
    placeholder_participant_count: int
    state_counts: dict[str, int]
    leg_counts: dict[str, int]
    rounds: tuple[SportmonksRoundEvidence, ...]
    rate_limit_remaining_minimum: int


def qualify_dfb_pokal(
    api_token: str,
    *,
    transport: SportmonksQualificationTransport | None = None,
    clock: Callable[[], datetime] | None = None,
) -> SportmonksQualificationEvidence:
    if not api_token.strip():
        raise SportmonksQualificationError("SPORTMONKS_API_TOKEN is required.")
    active_transport = transport or StdlibSportmonksQualificationTransport()
    active_clock = clock or (lambda: datetime.now(UTC))

    league_path = f"/v3/football/leagues/{DFB_POKAL_LEAGUE_ID}?include=currentSeason"
    league_payload = _request_json(active_transport, league_path, api_token)
    league = _mapping(league_payload, "data")
    if (
        _positive_int(league, "id") != DFB_POKAL_LEAGUE_ID
        or _positive_int(league, "sport_id") != 1
    ):
        raise SportmonksQualificationError("Provider returned the wrong competition.")
    if not _boolean(league, "active"):
        raise SportmonksQualificationError("Provider competition is not active.")
    league_name = _string(league, "name")

    season = _mapping(league, "currentseason")
    season_id = _positive_int(season, "id")
    if (
        _positive_int(season, "sport_id") != 1
        or _positive_int(season, "league_id") != DFB_POKAL_LEAGUE_ID
        or _string(season, "name") != DFB_POKAL_SEASON_NAME
        or not _boolean(season, "is_current")
    ):
        raise SportmonksQualificationError(
            "Provider current season does not match the requested DFB-Pokal scope."
        )
    if _boolean(season, "finished"):
        raise SportmonksQualificationError(
            "Provider current season is already finished."
        )
    season_start = _date(_string(season, "starting_at"))
    season_end = _date(_string(season, "ending_at"))
    if season_start.year != 2026 or season_end < season_start:
        raise SportmonksQualificationError(
            "Provider current season has an invalid date boundary."
        )

    fixtures, fixture_payloads = _request_fixture_pages(
        active_transport,
        api_token=api_token,
        season_id=season_id,
    )
    fixture_ids: set[int] = set()
    participant_ids: set[int] = set()
    kickoffs: list[datetime] = []
    state_counts: Counter[str] = Counter()
    leg_counts: Counter[str] = Counter()
    round_fixtures: defaultdict[tuple[int, str, int, str], int] = defaultdict(int)
    round_placeholders: Counter[tuple[int, str, int, str]] = Counter()
    placeholder_fixtures = 0
    placeholder_participants = 0
    unscheduled_fixtures = 0

    for raw_fixture in fixtures:
        fixture = _mapping_value(raw_fixture)
        fixture_id = _positive_int(fixture, "id")
        if fixture_id in fixture_ids:
            raise SportmonksQualificationError(
                "Provider returned a duplicate fixture ID across pages."
            )
        fixture_ids.add(fixture_id)
        if (
            _positive_int(fixture, "sport_id") != 1
            or _positive_int(fixture, "league_id") != DFB_POKAL_LEAGUE_ID
        ):
            raise SportmonksQualificationError(
                "A fixture belongs to the wrong competition."
            )
        if _positive_int(fixture, "season_id") != season_id:
            raise SportmonksQualificationError("A fixture belongs to the wrong season.")

        stage_id = _positive_int(fixture, "stage_id")
        round_id = _positive_int(fixture, "round_id")
        stage = _mapping(fixture, "stage")
        round_payload = _mapping(fixture, "round")
        if (
            _positive_int(stage, "id") != stage_id
            or _positive_int(stage, "league_id") != DFB_POKAL_LEAGUE_ID
            or _positive_int(stage, "season_id") != season_id
        ):
            raise SportmonksQualificationError(
                "A fixture has an inconsistent stage identity."
            )
        if (
            _positive_int(round_payload, "id") != round_id
            or _positive_int(round_payload, "league_id") != DFB_POKAL_LEAGUE_ID
            or _positive_int(round_payload, "season_id") != season_id
        ):
            raise SportmonksQualificationError(
                "A fixture has an inconsistent round identity."
            )
        stage_name = _string(stage, "name")
        round_name = _string(round_payload, "name")
        round_key = (stage_id, stage_name, round_id, round_name)
        round_fixtures[round_key] += 1

        fixture_placeholder = _boolean(fixture, "placeholder")
        if fixture_placeholder:
            placeholder_fixtures += 1
            round_placeholders[round_key] += 1
        participants = _list(fixture, "participants")
        locations: set[str] = set()
        fixture_participant_ids: set[int] = set()
        for raw_participant in participants:
            participant = _mapping_value(raw_participant)
            participant_id = _positive_int(participant, "id")
            location = _string(_mapping(participant, "meta"), "location")
            if location not in {"home", "away"} or location in locations:
                raise SportmonksQualificationError(
                    "A fixture has invalid participant locations."
                )
            locations.add(location)
            fixture_participant_ids.add(participant_id)
            participant_ids.add(participant_id)
            if _boolean(participant, "placeholder"):
                placeholder_participants += 1
        if locations != {"home", "away"} or len(fixture_participant_ids) != 2:
            raise SportmonksQualificationError(
                "A fixture must contain distinct home and away participants."
            )

        state = _mapping(fixture, "state")
        if _positive_int(state, "id") != _positive_int(fixture, "state_id"):
            raise SportmonksQualificationError(
                "A fixture has an inconsistent state identity."
            )
        state_counts[_string(state, "developer_name")] += 1
        leg = _string(fixture, "leg")
        if not _LEG_PATTERN.fullmatch(leg):
            raise SportmonksQualificationError("A fixture has an invalid leg value.")
        leg_counts[leg] += 1

        kickoff = _optional_utc_datetime(fixture, "starting_at")
        if kickoff is None:
            if not fixture_placeholder:
                raise SportmonksQualificationError(
                    "A non-placeholder fixture has no kickoff."
                )
            unscheduled_fixtures += 1
        else:
            if kickoff.date() < season_start or kickoff.date() > season_end:
                raise SportmonksQualificationError(
                    "A fixture kickoff is outside the season boundary."
                )
            kickoffs.append(kickoff)

    observed_at = _utc_now(active_clock)
    remaining = [
        _rate_limit_remaining(league_payload, expected_entity="League"),
        *(
            _rate_limit_remaining(payload, expected_entity="Fixture")
            for payload in fixture_payloads
        ),
    ]
    rounds = tuple(
        SportmonksRoundEvidence(
            stage_id=stage_id,
            stage_name=stage_name,
            round_id=round_id,
            round_name=round_name,
            fixture_count=count,
            placeholder_fixture_count=round_placeholders[key],
        )
        for key, count in sorted(round_fixtures.items())
        for stage_id, stage_name, round_id, round_name in (key,)
    )
    return SportmonksQualificationEvidence(
        qualification_profile="dfb-pokal",
        observed_at_utc=observed_at.isoformat(),
        api_version="v3",
        authoritative_scope="partial",
        league_id=DFB_POKAL_LEAGUE_ID,
        league_name=league_name,
        season_id=season_id,
        season_name=DFB_POKAL_SEASON_NAME,
        season_start_date=season_start.isoformat(),
        season_end_date=season_end.isoformat(),
        fixture_count=len(fixtures),
        unique_fixture_ids=len(fixture_ids),
        fixture_ids_sha256=_identity_fingerprint(fixture_ids),
        participant_count=len(participant_ids),
        participant_ids_sha256=_identity_fingerprint(participant_ids),
        fixture_page_count=len(fixture_payloads),
        request_count=1 + len(fixture_payloads),
        earliest_kickoff_utc=min(kickoffs).isoformat() if kickoffs else None,
        latest_kickoff_utc=max(kickoffs).isoformat() if kickoffs else None,
        unscheduled_fixture_count=unscheduled_fixtures,
        placeholder_fixture_count=placeholder_fixtures,
        placeholder_participant_count=placeholder_participants,
        state_counts=dict(sorted(state_counts.items())),
        leg_counts=dict(sorted(leg_counts.items())),
        rounds=rounds,
        rate_limit_remaining_minimum=min(remaining),
    )


def render_qualification_evidence(
    evidence: SportmonksQualificationEvidence,
) -> str:
    return json.dumps(asdict(evidence), indent=2, sort_keys=True)


def _request_fixture_pages(
    transport: SportmonksQualificationTransport,
    *,
    api_token: str,
    season_id: int,
) -> tuple[list[Any], list[Mapping[str, Any]]]:
    fixtures: list[Any] = []
    payloads: list[Mapping[str, Any]] = []
    page = 1
    while True:
        if page > MAX_FIXTURE_PAGES:
            raise SportmonksQualificationError(
                "Provider fixture pagination exceeded the safe page limit."
            )
        path = (
            f"/v3/football/fixtures/seasons/{season_id}"
            "?include=participants;stage;round;state"
            f"&per_page={FIXTURE_PAGE_LIMIT}&page={page}"
        )
        payload = _request_json(transport, path, api_token)
        payloads.append(payload)
        page_data = _list(payload, "data")
        pagination = _mapping(payload, "pagination")
        if _positive_int(pagination, "current_page") != page:
            raise SportmonksQualificationError(
                "Provider returned an inconsistent fixture page number."
            )
        if _positive_int(pagination, "per_page") != FIXTURE_PAGE_LIMIT:
            raise SportmonksQualificationError(
                "Provider returned an inconsistent fixture page size."
            )
        if _non_negative_int(pagination, "count") != len(page_data):
            raise SportmonksQualificationError(
                "Provider returned an inconsistent fixture page count."
            )
        has_more = _boolean(pagination, "has_more")
        if has_more and not page_data:
            raise SportmonksQualificationError(
                "Provider returned an empty fixture page with more data declared."
            )
        fixtures.extend(page_data)
        if not has_more:
            break
        page += 1
    if not fixtures:
        raise SportmonksQualificationError(
            "Provider returned no fixtures for the requested season."
        )
    return fixtures, payloads


def _request_json(
    transport: SportmonksQualificationTransport,
    path: str,
    api_token: str,
) -> Mapping[str, Any]:
    response = transport.get(path, api_token)
    if response.status != 200:
        raise SportmonksQualificationError(f"Provider returned HTTP {response.status}.")
    content_type = _header_value(response.headers, "Content-Type")
    if (
        content_type is None
        or content_type.split(";", 1)[0].strip() != "application/json"
    ):
        raise SportmonksQualificationError(
            "Provider returned an unexpected content type."
        )
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SportmonksQualificationError(
            "Provider returned malformed JSON."
        ) from error
    if not isinstance(payload, dict):
        raise SportmonksQualificationError("Provider returned an invalid JSON root.")
    if _string(payload, "timezone") != "UTC":
        raise SportmonksQualificationError("Provider response timezone is not UTC.")
    return payload


def _rate_limit_remaining(
    payload: Mapping[str, Any],
    *,
    expected_entity: str,
) -> int:
    rate_limit = _mapping(payload, "rate_limit")
    if _string(rate_limit, "requested_entity") != expected_entity:
        raise SportmonksQualificationError(
            "Provider returned the wrong rate-limit entity."
        )
    _non_negative_int(rate_limit, "resets_in_seconds")
    return _non_negative_int(rate_limit, "remaining")


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    return _mapping_value(payload.get(key))


def _mapping_value(value: object) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SportmonksQualificationError(
            "Provider response has an invalid object field."
        )
    return value


def _list(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise SportmonksQualificationError(
            "Provider response has an invalid collection field."
        )
    return value


def _positive_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SportmonksQualificationError(
            f"Provider response has an invalid integer field: {key}."
        )
    return value


def _non_negative_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SportmonksQualificationError(
            f"Provider response has an invalid integer field: {key}."
        )
    return value


def _string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SportmonksQualificationError(
            f"Provider response has an invalid string field: {key}."
        )
    return value.strip()


def _boolean(payload: Mapping[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise SportmonksQualificationError(
            f"Provider response has an invalid boolean field: {key}."
        )
    return value


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise SportmonksQualificationError(
            "Provider returned an invalid date."
        ) from error


def _optional_utc_datetime(
    payload: Mapping[str, Any],
    key: str,
) -> datetime | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SportmonksQualificationError(
            f"Provider response has an invalid timestamp field: {key}."
        )
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=UTC
        )
    except ValueError as error:
        raise SportmonksQualificationError(
            "Provider returned an invalid UTC timestamp."
        ) from error
    return parsed


def _utc_now(clock: Callable[[], datetime]) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise SportmonksQualificationError("Qualification clock must return UTC.")
    return value.astimezone(UTC)


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    expected = name.casefold()
    for key, value in headers.items():
        if key.casefold() == expected:
            return value
    return None


def _identity_fingerprint(identifiers: set[int]) -> str:
    canonical = "\n".join(str(identifier) for identifier in sorted(identifiers))
    return hashlib.sha256(canonical.encode()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Perform read-only Sportmonks calls and print only secret-safe "
            "DFB-Pokal qualification evidence."
        )
    )
    parser.parse_args(argv)
    api_token = os.environ.get("SPORTMONKS_API_TOKEN", "")
    try:
        evidence = qualify_dfb_pokal(api_token)
    except SportmonksQualificationError as error:
        parser.exit(status=1, message=f"Sportmonks qualification failed: {error}\n")
    print(render_qualification_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
