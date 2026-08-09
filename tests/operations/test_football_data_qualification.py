import json
from dataclasses import replace

import pytest
from app.operations.football_data_qualification import (
    FootballDataQualificationEvidence,
    QualificationError,
    QualificationResponse,
    qualify_football_data,
    render_qualification_evidence,
)


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
            "X-RequestsAvailable": str(remaining),
        },
        body=json.dumps(payload).encode(),
    )


def valid_responses() -> list[QualificationResponse]:
    team_ids = list(range(1, 21))
    competition = {
        "id": 2021,
        "code": "PL",
        "currentSeason": {
            "id": 2600,
            "startDate": "2026-08-15",
            "endDate": "2027-05-23",
        },
    }
    teams = {"teams": [{"id": team_id} for team_id in team_ids]}
    matches = []
    for index in range(380):
        matches.append(
            {
                "id": 10000 + index,
                "competition": {"id": 2021},
                "season": {"id": 2600},
                "homeTeam": {"id": team_ids[index % 20]},
                "awayTeam": {"id": team_ids[(index + 1) % 20]},
                "utcDate": f"2026-08-{15 + index % 10:02d}T14:00:00Z",
                "lastUpdated": "2026-08-09T10:00:00Z",
                "status": "TIMED",
            }
        )
    return [
        response(competition),
        response(teams, remaining=8),
        response({"resultSet": {"count": 380}, "matches": matches}, remaining=7),
    ]


def test_qualification_returns_only_safe_aggregate_evidence() -> None:
    transport = StubTransport(valid_responses())

    evidence = qualify_football_data("provider-secret", transport=transport)
    rendered = render_qualification_evidence(evidence)

    assert evidence.team_count == 20
    assert evidence.match_count == 380
    assert evidence.unique_match_ids == 380
    assert evidence.status_counts == {"TIMED": 380}
    assert evidence.requests_available_minimum == 7
    assert "provider-secret" not in rendered
    assert [call[0] for call in transport.calls] == [
        "/v4/competitions/PL",
        "/v4/competitions/PL/teams?season=2026",
        "/v4/competitions/PL/matches?season=2026&limit=500",
    ]


def test_qualification_rejects_incomplete_season() -> None:
    responses = valid_responses()
    payload = json.loads(responses[2].body)
    payload["matches"].pop()
    responses[2] = response(payload)

    with pytest.raises(QualificationError, match="380-match"):
        qualify_football_data("provider-secret", transport=StubTransport(responses))


def test_qualification_rejects_duplicate_match_identity() -> None:
    responses = valid_responses()
    payload = json.loads(responses[2].body)
    payload["matches"][1]["id"] = payload["matches"][0]["id"]
    responses[2] = response(payload)

    with pytest.raises(QualificationError, match="duplicate match ID"):
        qualify_football_data("provider-secret", transport=StubTransport(responses))


def test_qualification_rejects_non_utc_timestamp() -> None:
    responses = valid_responses()
    payload = json.loads(responses[2].body)
    payload["matches"][0]["utcDate"] = "2026-08-15T14:00:00+02:00"
    responses[2] = response(payload)

    with pytest.raises(QualificationError, match="not UTC"):
        qualify_football_data("provider-secret", transport=StubTransport(responses))


def test_qualification_failure_never_contains_secret() -> None:
    responses = valid_responses()
    responses[0] = replace(responses[0], status=403, body=b"provider-secret")

    with pytest.raises(QualificationError) as captured:
        qualify_football_data("provider-secret", transport=StubTransport(responses))

    assert "provider-secret" not in str(captured.value)


def test_render_qualification_evidence_is_stable() -> None:
    evidence = FootballDataQualificationEvidence(
        api_version="v4",
        competition_id=2021,
        competition_code="PL",
        season_id=2600,
        season_start_date="2026-08-15",
        season_end_date="2027-05-23",
        team_count=20,
        match_count=380,
        unique_match_ids=380,
        earliest_kickoff_utc="2026-08-15T14:00:00+00:00",
        latest_kickoff_utc="2027-05-23T15:00:00+00:00",
        status_counts={"TIMED": 380},
        requests_available_minimum=7,
    )

    assert json.loads(render_qualification_evidence(evidence))["match_count"] == 380
