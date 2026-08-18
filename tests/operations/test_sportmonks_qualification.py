import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from app.operations import sportmonks_qualification as qualification
from app.operations.sportmonks_qualification import (
    SportmonksQualificationError,
    SportmonksQualificationResponse,
    StdlibSportmonksQualificationTransport,
    qualify_dfb_pokal,
    render_qualification_evidence,
)

OBSERVED_AT = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)
SEASON_ID = 26001
STAGE_ID = 77001
ROUND_ID = 88001


class StubTransport:
    def __init__(self, responses: list[SportmonksQualificationResponse]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def get(
        self,
        path: str,
        api_token: str,
    ) -> SportmonksQualificationResponse:
        self.calls.append((path, api_token))
        return self.responses.pop(0)


def response(
    data: object,
    *,
    entity: str,
    remaining: int = 1999,
    pagination: dict[str, object] | None = None,
) -> SportmonksQualificationResponse:
    payload: dict[str, object] = {
        "data": data,
        "rate_limit": {
            "resets_in_seconds": 3600,
            "remaining": remaining,
            "requested_entity": entity,
        },
        "timezone": "UTC",
        "subscription": [{"plans": [{"plan": "account-secret"}]}],
    }
    if pagination is not None:
        payload["pagination"] = pagination
    return SportmonksQualificationResponse(
        status=200,
        headers={"Content-Type": "application/json; charset=utf-8"},
        body=json.dumps(payload).encode(),
    )


def league_response() -> SportmonksQualificationResponse:
    return response(
        {
            "id": 109,
            "sport_id": 1,
            "name": "DFB Pokal",
            "active": True,
            "currentseason": {
                "id": SEASON_ID,
                "sport_id": 1,
                "league_id": 109,
                "name": "2026/2027",
                "finished": False,
                "pending": False,
                "is_current": True,
                "starting_at": "2026-08-21",
                "ending_at": "2027-05-29",
            },
        },
        entity="League",
    )


def fixture(
    index: int,
    *,
    placeholder: bool = False,
    starting_at: str | None = None,
) -> dict[str, Any]:
    return {
        "id": 900000 + index,
        "sport_id": 1,
        "league_id": 109,
        "season_id": SEASON_ID,
        "stage_id": STAGE_ID,
        "round_id": ROUND_ID,
        "state_id": 1,
        "name": f"Team {index * 2 + 1} vs Team {index * 2 + 2}",
        "starting_at": starting_at or f"2026-08-{21 + index:02d} 18:00:00",
        "leg": "1/1",
        "placeholder": placeholder,
        "stage": {
            "id": STAGE_ID,
            "league_id": 109,
            "season_id": SEASON_ID,
            "name": "DFB Pokal",
        },
        "round": {
            "id": ROUND_ID,
            "league_id": 109,
            "season_id": SEASON_ID,
            "name": "1st Round",
        },
        "state": {"id": 1, "developer_name": "NS"},
        "participants": [
            {
                "id": 10000 + index * 2,
                "name": f"Team {index * 2 + 1}",
                "placeholder": placeholder,
                "meta": {"location": "home"},
            },
            {
                "id": 10001 + index * 2,
                "name": f"Team {index * 2 + 2}",
                "placeholder": False,
                "meta": {"location": "away"},
            },
        ],
    }


def fixtures_response(
    fixtures: list[dict[str, Any]],
    *,
    page: int = 1,
    has_more: bool = False,
    remaining: int = 1998,
) -> SportmonksQualificationResponse:
    return response(
        fixtures,
        entity="Fixture",
        remaining=remaining,
        pagination={
            "count": len(fixtures),
            "per_page": qualification.FIXTURE_PAGE_LIMIT,
            "current_page": page,
            "next_page": (
                f"https://api.sportmonks.com/v3/football/fixtures?page={page + 1}"
                if has_more
                else None
            ),
            "has_more": has_more,
        },
    )


def valid_responses() -> list[SportmonksQualificationResponse]:
    return [league_response(), fixtures_response([fixture(0), fixture(1)])]


def payload(item: SportmonksQualificationResponse) -> dict[str, Any]:
    parsed = json.loads(item.body)
    assert isinstance(parsed, dict)
    return parsed


def with_payload(
    item: SportmonksQualificationResponse,
    value: dict[str, Any],
) -> SportmonksQualificationResponse:
    return replace(item, body=json.dumps(value).encode())


def run_qualification(
    responses: list[SportmonksQualificationResponse],
) -> tuple[qualification.SportmonksQualificationEvidence, StubTransport]:
    transport = StubTransport(responses)
    evidence = qualify_dfb_pokal(
        "provider-secret",
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )
    return evidence, transport


def test_qualification_collects_secret_safe_partial_evidence() -> None:
    evidence, transport = run_qualification(valid_responses())
    rendered = render_qualification_evidence(evidence)

    assert evidence.qualification_profile == "dfb-pokal"
    assert evidence.api_version == "v3"
    assert evidence.authoritative_scope == "partial"
    assert evidence.league_id == 109
    assert evidence.season_id == SEASON_ID
    assert evidence.fixture_count == 2
    assert evidence.unique_fixture_ids == 2
    assert evidence.participant_count == 4
    assert evidence.fixture_page_count == 1
    assert evidence.request_count == 2
    assert evidence.state_counts == {"NS": 2}
    assert evidence.leg_counts == {"1/1": 2}
    assert evidence.rounds[0].fixture_count == 2
    assert evidence.rate_limit_remaining_minimum == 1998
    assert "provider-secret" not in rendered
    assert "account-secret" not in rendered
    assert "900000" not in rendered
    assert transport.calls == [
        (
            "/v3/football/leagues/109?include=currentSeason",
            "provider-secret",
        ),
        (
            f"/v3/football/fixtures/seasons/{SEASON_ID}"
            "?include=participants;stage;round;state&per_page=50&page=1",
            "provider-secret",
        ),
    ]


def test_qualification_collects_multiple_fixture_pages() -> None:
    responses = [
        league_response(),
        fixtures_response([fixture(0)], has_more=True),
        fixtures_response([fixture(1)], page=2, remaining=1997),
    ]

    evidence, transport = run_qualification(responses)

    assert evidence.fixture_count == 2
    assert evidence.fixture_page_count == 2
    assert evidence.request_count == 3
    assert transport.calls[-1][0].endswith("&per_page=50&page=2")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", 110, "wrong competition"),
        ("sport_id", 2, "wrong competition"),
        ("active", False, "not active"),
    ],
)
def test_qualification_rejects_invalid_league(
    field: str,
    value: object,
    message: str,
) -> None:
    responses = valid_responses()
    league_payload = payload(responses[0])
    league_payload["data"][field] = value
    responses[0] = with_payload(responses[0], league_payload)

    with pytest.raises(SportmonksQualificationError, match=message):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("league_id", 110),
        ("name", "2025/2026"),
        ("is_current", False),
    ],
)
def test_qualification_rejects_wrong_current_season(
    field: str,
    value: object,
) -> None:
    responses = valid_responses()
    league_payload = payload(responses[0])
    league_payload["data"]["currentseason"][field] = value
    responses[0] = with_payload(responses[0], league_payload)

    with pytest.raises(SportmonksQualificationError, match="current season"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("league_id", 110, "wrong competition"),
        ("season_id", 99999, "wrong season"),
        ("round_id", None, "invalid integer field"),
    ],
)
def test_qualification_rejects_wrong_fixture_scope(
    field: str,
    value: object,
    message: str,
) -> None:
    responses = valid_responses()
    fixtures_payload = payload(responses[1])
    fixtures_payload["data"][0][field] = value
    responses[1] = with_payload(responses[1], fixtures_payload)

    with pytest.raises(SportmonksQualificationError, match=message):
        run_qualification(responses)


@pytest.mark.parametrize("relation", ["stage", "round"])
def test_qualification_rejects_inconsistent_lifecycle_identity(
    relation: str,
) -> None:
    responses = valid_responses()
    fixtures_payload = payload(responses[1])
    fixtures_payload["data"][0][relation]["id"] = 99999
    responses[1] = with_payload(responses[1], fixtures_payload)

    with pytest.raises(SportmonksQualificationError, match=f"inconsistent {relation}"):
        run_qualification(responses)


def test_qualification_accepts_explicit_placeholder_without_kickoff() -> None:
    responses = [
        league_response(),
        fixtures_response([fixture(0, placeholder=True, starting_at=None)]),
    ]
    fixtures_payload = payload(responses[1])
    fixtures_payload["data"][0]["starting_at"] = None
    responses[1] = with_payload(responses[1], fixtures_payload)

    evidence, _ = run_qualification(responses)

    assert evidence.placeholder_fixture_count == 1
    assert evidence.placeholder_participant_count == 1
    assert evidence.unscheduled_fixture_count == 1
    assert evidence.earliest_kickoff_utc is None


def test_qualification_rejects_unscheduled_non_placeholder_fixture() -> None:
    responses = valid_responses()
    fixtures_payload = payload(responses[1])
    fixtures_payload["data"][0]["starting_at"] = None
    responses[1] = with_payload(responses[1], fixtures_payload)

    with pytest.raises(SportmonksQualificationError, match="has no kickoff"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("participants", 1, "meta", "location", "home"), "locations"),
        (("participants", 1, "id", None, 10000), "distinct home and away"),
        (("leg", None, None, None, "first"), "invalid leg"),
    ],
)
def test_qualification_rejects_invalid_participant_or_leg(
    mutation: tuple[str, int | None, str | None, str | None, object],
    message: str,
) -> None:
    responses = valid_responses()
    fixtures_payload = payload(responses[1])
    target = fixtures_payload["data"][0]
    root, index, child, grandchild, value = mutation
    if index is None:
        target[root] = value
    elif grandchild is None:
        target[root][index][child] = value
    else:
        target[root][index][child][grandchild] = value
    responses[1] = with_payload(responses[1], fixtures_payload)

    with pytest.raises(SportmonksQualificationError, match=message):
        run_qualification(responses)


def test_qualification_rejects_duplicate_fixture_across_pages() -> None:
    repeated = fixture(0)
    responses = [
        league_response(),
        fixtures_response([repeated], has_more=True),
        fixtures_response([deepcopy(repeated)], page=2),
    ]

    with pytest.raises(SportmonksQualificationError, match="duplicate fixture ID"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("current_page", 2, "page number"),
        ("per_page", 49, "page size"),
        ("count", 3, "page count"),
    ],
)
def test_qualification_rejects_invalid_pagination(
    field: str,
    value: object,
    message: str,
) -> None:
    responses = valid_responses()
    fixtures_payload = payload(responses[1])
    fixtures_payload["pagination"][field] = value
    responses[1] = with_payload(responses[1], fixtures_payload)

    with pytest.raises(SportmonksQualificationError, match=message):
        run_qualification(responses)


def test_qualification_rejects_empty_fixture_scope() -> None:
    responses = [league_response(), fixtures_response([])]

    with pytest.raises(SportmonksQualificationError, match="no fixtures"):
        run_qualification(responses)


def test_qualification_rejects_empty_intermediate_page() -> None:
    responses = [league_response(), fixtures_response([], has_more=True)]

    with pytest.raises(SportmonksQualificationError, match="empty fixture page"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        (0, "timezone", "Europe/Berlin", "timezone"),
        (0, "requested_entity", "Fixture", "rate-limit entity"),
        (1, "remaining", -1, "invalid integer field"),
    ],
)
def test_qualification_rejects_invalid_response_metadata(
    target: int,
    field: str,
    value: object,
    message: str,
) -> None:
    responses = valid_responses()
    item_payload = payload(responses[target])
    if field == "timezone":
        item_payload[field] = value
    else:
        item_payload["rate_limit"][field] = value
    responses[target] = with_payload(responses[target], item_payload)

    with pytest.raises(SportmonksQualificationError, match=message):
        run_qualification(responses)


def test_qualification_failure_never_contains_secret_payload() -> None:
    responses = valid_responses()
    responses[0] = replace(
        responses[0],
        status=403,
        body=b"provider-secret account-secret",
    )

    with pytest.raises(SportmonksQualificationError) as captured:
        run_qualification(responses)

    assert "provider-secret" not in str(captured.value)
    assert "account-secret" not in str(captured.value)


def test_stdlib_transport_uses_header_and_sanitizes_failure(
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
            assert "api_token" not in path
            assert headers["Authorization"] == "provider-secret"
            raise qualification.HTTPException(
                f"provider-secret leaked through {method} {path} {headers}"
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(qualification, "HTTPSConnection", FailingConnection)

    with pytest.raises(
        SportmonksQualificationError,
        match="Provider request failed",
    ) as captured:
        StdlibSportmonksQualificationTransport().get(
            "/v3/football/leagues/109",
            "provider-secret",
        )

    assert "provider-secret" not in str(captured.value)


def test_stdlib_transport_rejects_token_query_parameter_before_network() -> None:
    with pytest.raises(SportmonksQualificationError, match="forbids tokens"):
        StdlibSportmonksQualificationTransport().get(
            "/v3/football/leagues/109?api_token=provider-secret",
            "provider-secret",
        )
