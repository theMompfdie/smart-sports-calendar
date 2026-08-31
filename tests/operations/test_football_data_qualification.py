import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from app.operations import football_data_qualification as qualification
from app.operations.football_data_qualification import (
    BUNDESLIGA_PROFILE,
    CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE,
    CHAMPIONSHIP_PROFILE,
    PREMIER_LEAGUE_PROFILE,
    FootballDataQualificationEvidence,
    FootballDataQualificationProfile,
    QualificationError,
    QualificationResponse,
    StdlibQualificationTransport,
    observe_football_data_participants,
    qualify_football_data,
    render_participant_evidence,
    render_qualification_evidence,
)

OBSERVED_AT = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)


class StubTransport:
    def __init__(self, responses: list[QualificationResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def get(self, path: str, api_key: str) -> QualificationResponse:
        self.calls.append((path, api_key))
        return self.responses.pop(0)


def response(payload: object, *, remaining: int = 9) -> QualificationResponse:
    return QualificationResponse(
        status=200,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-API-Version": "v4",
            "X-Authenticated-Client": "account-secret",
            "X-RequestsAvailable": str(remaining),
        },
        body=json.dumps(payload).encode(),
    )


def payload(item: QualificationResponse) -> dict[str, Any]:
    value = json.loads(item.body)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def with_payload(item: QualificationResponse, value: object) -> QualificationResponse:
    return replace(item, body=json.dumps(value).encode())


def schedule(
    team_ids: list[int],
    *,
    expected_matchdays: int,
) -> list[tuple[int, int, int]]:
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
    if expected_matchdays <= len(team_ids) - 1:
        return [fixture for fixture in first_leg if fixture[2] <= expected_matchdays]
    second_leg = [
        (away, home, matchday + len(team_ids) - 1) for home, away, matchday in first_leg
    ]
    return [*first_leg, *second_leg][: expected_matchdays * len(team_ids) // 2]


def valid_responses(
    profile: FootballDataQualificationProfile = PREMIER_LEAGUE_PROFILE,
    *,
    page_limit: int = 500,
    provider_honors_page_limit: bool = True,
) -> list[QualificationResponse]:
    team_ids = list(range(1, profile.expected_team_count + 1))
    if profile is PREMIER_LEAGUE_PROFILE:
        start_date, end_date = "2026-08-21", "2027-05-30"
    elif profile is CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE:
        start_date, end_date = "2026-09-08", "2027-01-27"
    else:
        start_date, end_date = "2026-08-28", "2027-05-22"
    competition = {
        "id": profile.competition_id,
        "code": profile.competition_code,
        "currentSeason": {
            "id": 2600 if profile is PREMIER_LEAGUE_PROFILE else 2700,
            "startDate": start_date,
            "endDate": end_date,
        },
    }
    teams = {
        "teams": [
            {"id": team_id, "name": f"team-secret-{team_id}"} for team_id in team_ids
        ]
    }
    matches = []
    kickoff = datetime(2026, 8, 21, 14, 0, tzinfo=UTC)
    for index, (home_id, away_id, matchday) in enumerate(
        schedule(team_ids, expected_matchdays=profile.expected_matchdays)
    ):
        matches.append(
            {
                "id": 10000 + index,
                "competition": {"id": profile.competition_id},
                "season": {"id": competition["currentSeason"]["id"]},
                "homeTeam": {"id": home_id},
                "awayTeam": {"id": away_id},
                "utcDate": (kickoff + timedelta(days=matchday - 1))
                .isoformat()
                .replace("+00:00", "Z"),
                "lastUpdated": "2026-08-16T10:00:00Z",
                "status": "TIMED",
                "stage": profile.match_stage_filter or "REGULAR_SEASON",
                "matchday": matchday,
            }
        )
    pages = []
    response_page_size = page_limit if provider_honors_page_limit else len(matches)
    for offset in range(0, len(matches), response_page_size):
        page = matches[offset : offset + response_page_size]
        filters: dict[str, object] = {
            "season": "2026",
            "limit": str(page_limit),
        }
        if offset:
            filters["offset"] = str(offset)
        if profile.match_stage_filter is not None:
            filters["stage"] = profile.match_stage_filter
        pages.append(
            response(
                {
                    "filters": filters,
                    "resultSet": {"count": len(page)},
                    "matches": page,
                },
                remaining=7 - len(pages),
            )
        )
    return [response(competition), response(teams, remaining=8), *pages]


def run_qualification(
    responses: list[QualificationResponse],
    *,
    profile: FootballDataQualificationProfile = PREMIER_LEAGUE_PROFILE,
    observed_at: datetime = OBSERVED_AT,
) -> FootballDataQualificationEvidence:
    return qualify_football_data(
        "provider-secret",
        profile=profile,
        transport=StubTransport(responses),
        clock=lambda: observed_at,
    )


def test_premier_league_profile_preserves_strict_qualification() -> None:
    transport = StubTransport(valid_responses())

    evidence = qualify_football_data(
        "provider-secret",
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )
    rendered = render_qualification_evidence(evidence)

    assert evidence.qualification_profile == "premier-league"
    assert evidence.team_count == 20
    assert evidence.match_count == 380
    assert evidence.unique_match_ids == 380
    assert evidence.match_ids_sha256 == (
        "1c713d8b46058c74ae88d10e34b4c409d2b428832242a7d9f71eba25cec76450"
    )
    assert evidence.team_ids_sha256 == (
        "7747a514fec0c8bbe73acdb5ef9e4ca3a6b9d2be346c2b97de3d0560fa2a415f"
    )
    assert evidence.latest_source_update_utc == "2026-08-16T10:00:00+00:00"
    assert evidence.status_counts == {"TIMED": 380}
    assert evidence.stage_counts == {"REGULAR_SEASON": 380}
    assert evidence.match_page_count == 1
    assert evidence.request_count == 3
    assert evidence.requests_available_minimum == 7
    assert "provider-secret" not in rendered
    assert "account-secret" not in rendered
    assert "team-secret" not in rendered
    assert '"10000"' not in rendered
    assert [call[0] for call in transport.calls] == [
        "/v4/competitions/PL",
        "/v4/competitions/PL/teams?season=2026",
        "/v4/competitions/PL/matches?season=2026&limit=500",
    ]


def test_bundesliga_profile_qualifies_exact_scope() -> None:
    transport = StubTransport(valid_responses(BUNDESLIGA_PROFILE))

    evidence = qualify_football_data(
        "provider-secret",
        profile=BUNDESLIGA_PROFILE,
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )

    assert evidence.qualification_profile == "bundesliga"
    assert evidence.competition_code == "BL1"
    assert evidence.competition_id == 2002
    assert evidence.team_count == 18
    assert evidence.match_count == 306
    assert evidence.unique_match_ids == 306
    assert evidence.status_counts == {"TIMED": 306}
    assert [call[0] for call in transport.calls] == [
        "/v4/competitions/BL1",
        "/v4/competitions/BL1/teams?season=2026",
        "/v4/competitions/BL1/matches?season=2026&limit=500",
    ]


def test_championship_profile_qualifies_complete_unpaged_regular_season() -> None:
    transport = StubTransport(
        valid_responses(
            CHAMPIONSHIP_PROFILE,
            provider_honors_page_limit=False,
        )
    )

    evidence = qualify_football_data(
        "provider-secret",
        profile=CHAMPIONSHIP_PROFILE,
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )

    assert evidence.qualification_profile == "championship"
    assert evidence.competition_code == "ELC"
    assert evidence.competition_id == 2016
    assert evidence.team_count == 24
    assert evidence.match_count == 552
    assert evidence.unique_match_ids == 552
    assert evidence.match_page_count == 1
    assert evidence.request_count == 3
    assert evidence.team_ids_sha256 == (
        "6ffdf1ff8cf67fa3895b85cb7d2281e3a63b951a380f1fd0b650537ccb50dfef"
    )
    assert evidence.stage_counts == {"REGULAR_SEASON": 552}
    assert [call[0] for call in transport.calls] == [
        "/v4/competitions/ELC",
        "/v4/competitions/ELC/teams?season=2026",
        ("/v4/competitions/ELC/matches?season=2026&limit=500&stage=REGULAR_SEASON"),
    ]


def test_championship_profile_supports_documented_match_pagination() -> None:
    transport = StubTransport(valid_responses(CHAMPIONSHIP_PROFILE))

    evidence = qualify_football_data(
        "provider-secret",
        profile=CHAMPIONSHIP_PROFILE,
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )

    assert evidence.match_count == 552
    assert evidence.match_page_count == 2
    assert evidence.request_count == 4
    assert [call[0] for call in transport.calls[-2:]] == [
        ("/v4/competitions/ELC/matches?season=2026&limit=500&stage=REGULAR_SEASON"),
        (
            "/v4/competitions/ELC/matches"
            "?season=2026&limit=500&stage=REGULAR_SEASON&offset=500"
        ),
    ]


def test_champions_league_profile_qualifies_exact_league_phase_scope() -> None:
    transport = StubTransport(valid_responses(CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE))

    evidence = qualify_football_data(
        "provider-secret",
        profile=CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE,
        transport=transport,
        clock=lambda: datetime(2026, 8, 30, 9, 0, tzinfo=UTC),
    )
    rendered = render_qualification_evidence(evidence)

    assert evidence.qualification_profile == "champions-league-league-phase"
    assert evidence.competition_code == "CL"
    assert evidence.competition_id == 2001
    assert evidence.team_count == 36
    assert evidence.match_count == 144
    assert evidence.unique_match_ids == 144
    assert evidence.stage_counts == {"LEAGUE_STAGE": 144}
    assert evidence.status_counts == {"TIMED": 144}
    assert evidence.match_page_count == 1
    assert evidence.request_count == 3
    assert "provider-secret" not in rendered
    assert "team-secret" not in rendered
    assert '"10000"' not in rendered
    assert [call[0] for call in transport.calls] == [
        "/v4/competitions/CL",
        "/v4/competitions/CL/teams?season=2026",
        ("/v4/competitions/CL/matches?season=2026&limit=500&stage=LEAGUE_STAGE"),
    ]


def test_champions_league_profile_rejects_incomplete_league_phase() -> None:
    responses = valid_responses(CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE)
    matches_payload = payload(responses[2])
    matches_payload["matches"].pop()
    matches_payload["resultSet"]["count"] = 143
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match="144-match"):
        run_qualification(
            responses,
            profile=CHAMPIONS_LEAGUE_LEAGUE_PHASE_PROFILE,
            observed_at=datetime(2026, 8, 30, 9, 0, tzinfo=UTC),
        )


@pytest.mark.parametrize("stage_echo", [None, ["REGULAR_SEASON"]])
def test_championship_profile_ignores_non_authoritative_stage_filter_echo(
    stage_echo: object,
) -> None:
    responses = valid_responses(CHAMPIONSHIP_PROFILE)
    matches_payload = payload(responses[2])
    if stage_echo is None:
        matches_payload["filters"].pop("stage")
    else:
        matches_payload["filters"]["stage"] = stage_echo
    responses[2] = with_payload(responses[2], matches_payload)

    evidence = run_qualification(responses, profile=CHAMPIONSHIP_PROFILE)

    assert evidence.match_count == 552
    assert evidence.stage_counts == {"REGULAR_SEASON": 552}


def test_bundesliga_participant_observation_is_curated_and_secret_safe() -> None:
    responses = valid_responses(BUNDESLIGA_PROFILE)
    teams_payload = payload(responses[1])
    for index, team in enumerate(teams_payload["teams"], start=1):
        team["name"] = f"Bundesliga Team {index:02d}"
        team["shortName"] = f"Team {index:02d}"
        team["tla"] = f"T{index:02d}"
    responses[1] = with_payload(responses[1], teams_payload)
    transport = StubTransport(responses[:2])

    evidence = observe_football_data_participants(
        "provider-secret",
        profile=BUNDESLIGA_PROFILE,
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )
    rendered = render_participant_evidence(evidence)

    assert evidence.qualification_profile == "bundesliga"
    assert evidence.competition_code == "BL1"
    assert evidence.competition_id == 2002
    assert evidence.team_count == 18
    assert evidence.request_count == 2
    assert evidence.participants[0].provider_name == "Bundesliga Team 01"
    assert evidence.participants[-1].provider_tla == "T18"
    assert "provider-secret" not in rendered
    assert "account-secret" not in rendered
    assert '"id"' not in rendered
    assert '"provider_id"' not in rendered
    assert [call[0] for call in transport.calls] == [
        "/v4/competitions/BL1",
        "/v4/competitions/BL1/teams?season=2026",
    ]


@pytest.mark.parametrize("duplicate_field", ["id", "name"])
def test_participant_observation_rejects_duplicate_team_identity(
    duplicate_field: str,
) -> None:
    responses = valid_responses(BUNDESLIGA_PROFILE)
    teams_payload = payload(responses[1])
    teams_payload["teams"][1][duplicate_field] = teams_payload["teams"][0][
        duplicate_field
    ]
    responses[1] = with_payload(responses[1], teams_payload)

    with pytest.raises(QualificationError, match="duplicate team identity"):
        observe_football_data_participants(
            "provider-secret",
            profile=BUNDESLIGA_PROFILE,
            transport=StubTransport(responses[:2]),
            clock=lambda: OBSERVED_AT,
        )


def test_participant_observation_rejects_incomplete_team_set() -> None:
    responses = valid_responses(BUNDESLIGA_PROFILE)
    teams_payload = payload(responses[1])
    teams_payload["teams"].pop()
    responses[1] = with_payload(responses[1], teams_payload)

    with pytest.raises(QualificationError, match="exactly 18 distinct"):
        observe_football_data_participants(
            "provider-secret",
            profile=BUNDESLIGA_PROFILE,
            transport=StubTransport(responses[:2]),
            clock=lambda: OBSERVED_AT,
        )


def test_qualification_rejects_unapproved_profile() -> None:
    profile = FootballDataQualificationProfile(
        key="unapproved",
        competition_name="Unapproved",
        competition_code="NOPE",
        competition_id=9999,
        expected_team_count=2,
        expected_match_count=2,
        expected_matchdays=2,
    )

    with pytest.raises(QualificationError, match="not approved"):
        qualify_football_data("provider-secret", profile=profile)


def test_qualification_collects_and_validates_multiple_match_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qualification, "MATCH_PAGE_LIMIT", 200)
    transport = StubTransport(valid_responses(BUNDESLIGA_PROFILE, page_limit=200))

    evidence = qualify_football_data(
        "provider-secret",
        profile=BUNDESLIGA_PROFILE,
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )

    assert evidence.match_page_count == 2
    assert evidence.request_count == 4
    assert [call[0] for call in transport.calls[-2:]] == [
        "/v4/competitions/BL1/matches?season=2026&limit=200",
        "/v4/competitions/BL1/matches?season=2026&limit=200&offset=200",
    ]


def test_qualification_rejects_pagination_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qualification, "MATCH_PAGE_LIMIT", 200)
    responses = valid_responses(BUNDESLIGA_PROFILE, page_limit=200)
    second_page = payload(responses[3])
    second_page["filters"]["offset"] = 199
    responses[3] = with_payload(responses[3], second_page)

    with pytest.raises(QualificationError, match="offset filter"):
        run_qualification(responses, profile=BUNDESLIGA_PROFILE)


def test_qualification_rejects_inconsistent_result_count() -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    matches_payload["resultSet"]["count"] = 379
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match="result count"):
        run_qualification(responses)


def test_qualification_accepts_missing_optional_limit_echo() -> None:
    responses = valid_responses(BUNDESLIGA_PROFILE)
    matches_payload = payload(responses[2])
    matches_payload["filters"].pop("limit")
    responses[2] = with_payload(responses[2], matches_payload)

    evidence = run_qualification(responses, profile=BUNDESLIGA_PROFILE)

    assert evidence.match_count == 306
    assert evidence.match_page_count == 1


def test_qualification_rejects_incomplete_season() -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    matches_payload["matches"].pop()
    matches_payload["resultSet"]["count"] = 379
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match="380-match"):
        run_qualification(responses)


def test_qualification_rejects_unexpected_empty_page() -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    matches_payload["matches"] = []
    matches_payload["resultSet"]["count"] = 0
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match="empty match page"):
        run_qualification(responses)


def test_qualification_rejects_wrong_competition_identity_before_more_calls() -> None:
    responses = valid_responses(BUNDESLIGA_PROFILE)
    competition = payload(responses[0])
    competition["id"] = 2021
    responses[0] = with_payload(responses[0], competition)
    transport = StubTransport(responses)

    with pytest.raises(QualificationError, match="wrong competition"):
        qualify_football_data(
            "provider-secret",
            profile=BUNDESLIGA_PROFILE,
            transport=transport,
            clock=lambda: OBSERVED_AT,
        )

    assert len(transport.calls) == 1


def test_qualification_rejects_wrong_season() -> None:
    responses = valid_responses()
    competition = payload(responses[0])
    competition["currentSeason"]["startDate"] = "2025-08-15"
    responses[0] = with_payload(responses[0], competition)

    with pytest.raises(QualificationError, match="current season"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("scope", "value", "message"),
    [
        ("competition", 9999, "wrong competition"),
        ("season", 9999, "wrong season"),
    ],
)
def test_qualification_rejects_wrong_match_identity(
    scope: str,
    value: int,
    message: str,
) -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    matches_payload["matches"][0][scope]["id"] = value
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match=message):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("season", "2025", "season filter"),
        ("limit", 499, "limit filter"),
        ("limit", "five hundred", "invalid limit"),
        ("offset", True, "invalid offset"),
    ],
)
def test_qualification_rejects_wrong_match_filter(
    field: str,
    value: object,
    message: str,
) -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    matches_payload["filters"][field] = value
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match=message):
        run_qualification(responses)


def test_qualification_rejects_duplicate_match_identity() -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    matches_payload["matches"][1]["id"] = matches_payload["matches"][0]["id"]
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match="duplicate match ID"):
        run_qualification(responses)


def test_qualification_rejects_invalid_participant() -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    matches_payload["matches"][0]["homeTeam"]["id"] = 9999
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match="invalid participants"):
        run_qualification(responses)


def test_qualification_rejects_duplicate_home_away_pairing() -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    first = matches_payload["matches"][0]
    second = matches_payload["matches"][1]
    second["homeTeam"] = first["homeTeam"]
    second["awayTeam"] = first["awayTeam"]
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match="home/away pairing"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("stage", "PLAYOFFS", "unsupported stage"),
        ("matchday", 39, "invalid matchday"),
        ("status", "UNKNOWN", "unsupported match status"),
        ("utcDate", "2026-08-21T14:00:00+02:00", "not UTC"),
    ],
)
def test_qualification_rejects_invalid_match_scope(
    field: str,
    value: object,
    message: str,
) -> None:
    responses = valid_responses()
    matches_payload = payload(responses[2])
    matches_payload["matches"][0][field] = value
    responses[2] = with_payload(responses[2], matches_payload)

    with pytest.raises(QualificationError, match=message):
        run_qualification(responses)


def test_qualification_rejects_stale_snapshot() -> None:
    responses = valid_responses()

    with pytest.raises(QualificationError, match="stale"):
        run_qualification(
            responses,
            observed_at=datetime(2026, 9, 1, 10, 1, tzinfo=UTC),
        )


def test_qualification_failure_never_contains_secret() -> None:
    responses = valid_responses()
    responses[0] = replace(responses[0], status=403, body=b"provider-secret")

    with pytest.raises(QualificationError) as captured:
        run_qualification(responses)

    assert "provider-secret" not in str(captured.value)


def test_stdlib_transport_sanitizes_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingConnection:
        def __init__(self, host: str, *, timeout: float) -> None:
            assert host == qualification.API_HOST
            assert timeout == 10.0

        def request(
            self,
            method: str,
            path: str,
            *,
            headers: dict[str, str],
        ) -> None:
            raise qualification.HTTPException(
                f"provider-secret leaked through {method} {path} {headers}"
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(qualification, "HTTPSConnection", FailingConnection)

    with pytest.raises(QualificationError, match="Provider request failed") as captured:
        StdlibQualificationTransport().get(
            "/v4/competitions/BL1?secret=url-secret",
            "provider-secret",
        )

    rendered_error = str(captured.value)
    assert "provider-secret" not in rendered_error
    assert "url-secret" not in rendered_error


def test_qualification_rejects_malformed_body_without_exposing_it() -> None:
    responses = valid_responses()
    responses[0] = replace(responses[0], body=b"provider-secret{")

    with pytest.raises(QualificationError, match="malformed JSON") as captured:
        run_qualification(responses)

    assert "provider-secret" not in str(captured.value)


def test_qualification_rejects_inconsistent_api_version() -> None:
    responses = valid_responses()
    responses[1] = replace(
        responses[1],
        headers={**responses[1].headers, "X-API-Version": "v3"},
    )

    with pytest.raises(QualificationError, match="consistently v4"):
        run_qualification(responses)


def test_render_qualification_evidence_is_stable() -> None:
    evidence = FootballDataQualificationEvidence(
        qualification_profile="bundesliga",
        observed_at_utc="2026-08-17T10:00:00+00:00",
        api_version="v4",
        competition_id=2002,
        competition_code="BL1",
        season_id=2700,
        season_start_date="2026-08-28",
        season_end_date="2027-05-22",
        team_count=18,
        match_count=306,
        unique_match_ids=306,
        match_page_count=1,
        request_count=3,
        match_ids_sha256=(
            "1c713d8b46058c74ae88d10e34b4c409d2b428832242a7d9f71eba25cec76450"
        ),
        team_ids_sha256=(
            "759b2095495ba759ec08b64452afb7af4122bbea66f8b3b435b5a20860150390"
        ),
        earliest_kickoff_utc="2026-08-28T18:30:00+00:00",
        latest_kickoff_utc="2027-05-22T13:30:00+00:00",
        latest_source_update_utc="2026-08-16T10:00:00+00:00",
        stage_counts={"REGULAR_SEASON": 306},
        status_counts={"TIMED": 306},
        requests_available_minimum=7,
    )

    rendered = json.loads(render_qualification_evidence(evidence))

    assert rendered["qualification_profile"] == "bundesliga"
    assert rendered["match_count"] == 306
    assert rendered["request_count"] == 3
