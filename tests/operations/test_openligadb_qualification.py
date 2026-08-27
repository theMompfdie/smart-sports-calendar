import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from app.operations import openligadb_qualification as qualification
from app.operations.openligadb_qualification import (
    SECOND_BUNDESLIGA_PROFILE,
    OpenLigaDBQualificationError,
    OpenLigaDBQualificationResponse,
    StdlibOpenLigaDBQualificationTransport,
    qualify_dfb_pokal,
    qualify_second_bundesliga,
    render_qualification_evidence,
)

OBSERVED_AT = datetime(2026, 8, 18, 18, 0, tzinfo=UTC)


class StubTransport:
    def __init__(self, responses: list[OpenLigaDBQualificationResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, path: str) -> OpenLigaDBQualificationResponse:
        self.calls.append(path)
        return self.responses.pop(0)


def response(payload: object) -> OpenLigaDBQualificationResponse:
    return OpenLigaDBQualificationResponse(
        status=200,
        headers={"Content-Type": "application/json; charset=utf-8"},
        body=json.dumps(payload).encode(),
    )


def league() -> dict[str, Any]:
    return {
        "leagueId": 4945,
        "leagueName": "DFB Pokal 2026/2027",
        "leagueShortcut": "dfb",
        "leagueSeason": "2026",
        "sport": {"sportId": 1, "sportName": "Fußball"},
    }


def groups() -> list[dict[str, Any]]:
    names = [
        "1. Runde",
        "2. Runde",
        "Achtelfinale",
        "Viertelfinale",
        "Halbfinale",
        "Endspiel",
    ]
    return [
        {
            "groupName": name,
            "groupOrderID": order,
            "groupID": 50848 + order,
        }
        for order, name in enumerate(names, start=1)
    ]


def fixture(index: int = 0) -> dict[str, Any]:
    return {
        "matchID": 81832 + index,
        "matchDateTime": "2026-08-21T18:00:00",
        "timeZoneID": "W. Europe Standard Time",
        "leagueId": 4945,
        "leagueName": "DFB Pokal 2026/2027",
        "leagueSeason": 2026,
        "leagueShortcut": "dfb",
        "matchDateTimeUTC": "2026-08-21T16:00:00Z",
        "group": groups()[0],
        "team1": {
            "teamId": 1000 + index * 2,
            "teamName": f"Home {index}",
            "shortName": f"H{index}",
            "teamIconUrl": "https://example.invalid/home.svg",
            "teamGroupName": None,
        },
        "team2": {
            "teamId": 1001 + index * 2,
            "teamName": f"Away {index}",
            "shortName": f"A{index}",
            "teamIconUrl": "https://example.invalid/away.svg",
            "teamGroupName": None,
        },
        "lastUpdateDateTime": "2026-07-05T11:29:56.773",
        "matchIsFinished": False,
        "matchResults": [],
        "goals": [],
        "location": None,
        "numberOfViewers": None,
    }


def valid_responses() -> list[OpenLigaDBQualificationResponse]:
    return [
        response([league()]),
        response(groups()),
        response([fixture(0), fixture(1)]),
    ]


def second_bundesliga_league() -> dict[str, Any]:
    return {
        "leagueId": 4938,
        "leagueName": "2. Fußball-Bundesliga 2026/2027",
        "leagueShortcut": "bl2",
        "leagueSeason": "2026",
        "sport": {"sportId": 1, "sportName": "Fußball"},
    }


def second_bundesliga_groups() -> list[dict[str, Any]]:
    return [
        {
            "groupName": f"{order}. Spieltag",
            "groupOrderID": order,
            "groupID": 60000 + order,
        }
        for order in range(1, 35)
    ]


def second_bundesliga_fixtures() -> list[dict[str, Any]]:
    team_ids = list(range(2000, 2018))
    rotation = team_ids.copy()
    first_half: list[list[tuple[int, int]]] = []
    for _ in range(17):
        first_half.append(
            [(rotation[index], rotation[-1 - index]) for index in range(9)]
        )
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
    second_half = [[(away, home) for home, away in matchday] for matchday in first_half]
    matchdays = [*first_half, *second_half]

    fixtures: list[dict[str, Any]] = []
    for matchday, pairings in enumerate(matchdays, start=1):
        for slot, (home_id, away_id) in enumerate(pairings):
            item = fixture((matchday - 1) * 9 + slot)
            item.update(
                matchID=90000 + (matchday - 1) * 9 + slot,
                leagueId=4938,
                leagueName="2. Fußball-Bundesliga 2026/2027",
                leagueShortcut="bl2",
                group=second_bundesliga_groups()[matchday - 1],
                matchDateTimeUTC="2026-08-07T18:30:00Z",
                lastUpdateDateTime="2026-08-16T15:26:22.460",
            )
            item["team1"].update(teamId=home_id, teamName=f"Team {home_id}")
            item["team2"].update(teamId=away_id, teamName=f"Team {away_id}")
            if len(fixtures) < 18:
                item["timeZoneID"] = ""
            fixtures.append(item)
    return fixtures


def valid_second_bundesliga_responses() -> list[OpenLigaDBQualificationResponse]:
    return [
        response([second_bundesliga_league()]),
        response(second_bundesliga_groups()),
        response(second_bundesliga_fixtures()),
    ]


def run_qualification(
    responses: list[OpenLigaDBQualificationResponse],
) -> tuple[qualification.OpenLigaDBQualificationEvidence, StubTransport]:
    transport = StubTransport(responses)
    evidence = qualify_dfb_pokal(transport=transport, clock=lambda: OBSERVED_AT)
    return evidence, transport


def test_qualification_collects_bounded_partial_evidence() -> None:
    evidence, transport = run_qualification(valid_responses())
    rendered = render_qualification_evidence(evidence)

    assert evidence.qualification_profile == "dfb-pokal"
    assert evidence.api_version == "v1"
    assert evidence.authoritative_scope == "partial"
    assert evidence.league_id == 4945
    assert evidence.league_shortcut == "dfb"
    assert evidence.league_season == 2026
    assert evidence.fixture_count == 2
    assert evidence.unique_fixture_ids == 2
    assert evidence.participant_count == 4
    assert evidence.request_count == 3
    assert evidence.status_counts == {"SCHEDULED": 2}
    assert evidence.rounds[0].normalized_round == "round-1"
    assert evidence.rounds[0].fixture_count == 2
    assert evidence.rounds[0].expected_fixture_capacity == 32
    assert evidence.rounds[-1].fixture_count == 0
    assert "81832" not in rendered
    assert "Home 0" not in rendered
    assert transport.calls == [
        "/getavailableleagues/2026",
        "/getavailablegroups/dfb/2026",
        "/getmatchdata/dfb/2026",
    ]


def test_second_bundesliga_qualification_proves_complete_season() -> None:
    transport = StubTransport(valid_second_bundesliga_responses())

    evidence = qualify_second_bundesliga(
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )
    rendered = render_qualification_evidence(evidence)

    assert evidence.qualification_profile == "2-bundesliga"
    assert evidence.authoritative_scope == "complete_season"
    assert evidence.league_id == 4938
    assert evidence.league_shortcut == "bl2"
    assert evidence.fixture_count == 306
    assert evidence.unique_fixture_ids == 306
    assert evidence.participant_count == 18
    assert evidence.missing_timezone_declarations == 18
    assert len(evidence.rounds) == 34
    assert {item.fixture_count for item in evidence.rounds} == {9}
    assert "90000" not in rendered
    assert "Team 2000" not in rendered
    assert transport.calls == [
        "/getavailableleagues/2026",
        "/getavailablegroups/bl2/2026",
        "/getmatchdata/bl2/2026",
    ]


def test_second_bundesliga_qualification_rejects_incomplete_season() -> None:
    fixtures = second_bundesliga_fixtures()
    fixtures.pop()
    responses = valid_second_bundesliga_responses()
    responses[2] = response(fixtures)

    with pytest.raises(OpenLigaDBQualificationError, match="exactly 306"):
        qualify_second_bundesliga(
            transport=StubTransport(responses),
            clock=lambda: OBSERVED_AT,
        )


def test_second_bundesliga_qualification_rejects_duplicate_pairing() -> None:
    fixtures = second_bundesliga_fixtures()
    fixtures[-1]["team1"] = deepcopy(fixtures[0]["team1"])
    fixtures[-1]["team2"] = deepcopy(fixtures[0]["team2"])
    responses = valid_second_bundesliga_responses()
    responses[2] = response(fixtures)

    with pytest.raises(OpenLigaDBQualificationError, match="directed pairing"):
        qualify_second_bundesliga(
            transport=StubTransport(responses),
            clock=lambda: OBSERVED_AT,
        )


def test_second_bundesliga_missing_timezone_exception_is_narrow() -> None:
    fixtures = second_bundesliga_fixtures()
    fixtures[0]["timeZoneID"] = "UTC"
    responses = valid_second_bundesliga_responses()
    responses[2] = response(fixtures)

    with pytest.raises(OpenLigaDBQualificationError, match="unexpected provider"):
        qualify_second_bundesliga(
            transport=StubTransport(responses),
            clock=lambda: OBSERVED_AT,
        )


def test_dfb_pokal_still_rejects_missing_timezone_declaration() -> None:
    item = fixture()
    item["timeZoneID"] = ""
    responses = valid_responses()
    responses[2] = response([item])

    with pytest.raises(OpenLigaDBQualificationError, match="timeZoneID"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item.update(leagueId=9999), "wrong competition"),
        (lambda item: item.update(leagueSeason="2025"), "wrong competition"),
        (lambda item: item.update(leagueShortcut="other"), "exactly one"),
        (lambda item: item["sport"].update(sportId=2), "wrong competition"),
    ],
)
def test_qualification_rejects_wrong_league_identity(
    mutation: Any, message: str
) -> None:
    item = league()
    mutation(item)
    responses = valid_responses()
    responses[0] = response([item])

    with pytest.raises(OpenLigaDBQualificationError, match=message):
        run_qualification(responses)


def test_qualification_rejects_duplicate_league_shortcut() -> None:
    responses = valid_responses()
    responses[0] = response([league(), league()])

    with pytest.raises(OpenLigaDBQualificationError, match="exactly one"):
        run_qualification(responses)


@pytest.mark.parametrize("missing_order", range(1, 7))
def test_qualification_rejects_incomplete_round_inventory(missing_order: int) -> None:
    responses = valid_responses()
    responses[1] = response(
        [item for item in groups() if item["groupOrderID"] != missing_order]
    )

    with pytest.raises(OpenLigaDBQualificationError, match="round inventory"):
        run_qualification(responses)


@pytest.mark.parametrize("duplicate_field", ["groupOrderID", "groupID"])
def test_qualification_rejects_duplicate_round_identity(duplicate_field: str) -> None:
    values = groups()
    values[1][duplicate_field] = values[0][duplicate_field]
    responses = valid_responses()
    responses[1] = response(values)

    with pytest.raises(OpenLigaDBQualificationError, match="duplicate round"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("leagueId", 9999, "wrong competition"),
        ("leagueSeason", 2025, "wrong competition"),
        ("leagueShortcut", "other", "wrong competition"),
        ("timeZoneID", "UTC", "unexpected provider timezone"),
        ("matchDateTimeUTC", "2025-08-21T16:00:00Z", "outside"),
        ("matchDateTimeUTC", "2026-08-21T16:00:00", "not UTC"),
        ("lastUpdateDateTime", "not-a-date", "update datetime"),
        ("matchIsFinished", "false", "boolean"),
    ],
)
def test_qualification_rejects_invalid_fixture_fields(
    field: str, value: object, message: str
) -> None:
    item = fixture()
    item[field] = value
    responses = valid_responses()
    responses[2] = response([item])

    with pytest.raises(OpenLigaDBQualificationError, match=message):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("groupID", 9999, "round identity"),
        ("groupOrderID", 7, "round identity"),
        ("groupName", "Other", "round name"),
    ],
)
def test_qualification_rejects_invalid_fixture_round(
    field: str, value: object, message: str
) -> None:
    item = fixture()
    item["group"][field] = value
    responses = valid_responses()
    responses[2] = response([item])

    with pytest.raises(OpenLigaDBQualificationError, match=message):
        run_qualification(responses)


def test_qualification_rejects_round_above_fixture_capacity() -> None:
    values = [fixture(index) for index in range(33)]
    responses = valid_responses()
    responses[2] = response(values)

    with pytest.raises(OpenLigaDBQualificationError, match="capacity"):
        run_qualification(responses)


def test_qualification_rejects_duplicate_fixture_id() -> None:
    item = fixture()
    responses = valid_responses()
    responses[2] = response([item, deepcopy(item)])

    with pytest.raises(OpenLigaDBQualificationError, match="duplicate fixture"):
        run_qualification(responses)


def test_qualification_rejects_duplicate_participants_within_fixture() -> None:
    item = fixture()
    item["team2"]["teamId"] = item["team1"]["teamId"]
    responses = valid_responses()
    responses[2] = response([item])

    with pytest.raises(OpenLigaDBQualificationError, match="same participant"):
        run_qualification(responses)


def test_qualification_accepts_empty_optional_team_short_name() -> None:
    item = fixture()
    item["team1"]["shortName"] = ""
    responses = valid_responses()
    responses[2] = response([item])

    evidence, _ = run_qualification(responses)

    assert evidence.fixture_count == 1


def test_qualification_rejects_empty_team_name() -> None:
    item = fixture()
    item["team1"]["teamName"] = ""
    responses = valid_responses()
    responses[2] = response([item])

    with pytest.raises(OpenLigaDBQualificationError, match="string field"):
        run_qualification(responses)


def test_qualification_rejects_empty_fixture_collection() -> None:
    responses = valid_responses()
    responses[2] = response([])

    with pytest.raises(OpenLigaDBQualificationError, match="no fixtures"):
        run_qualification(responses)


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        (replace(response([]), status=429), "HTTP 429"),
        (replace(response([]), headers={"Content-Type": "text/html"}), "non-JSON"),
        (replace(response([]), body=b"not-json"), "malformed JSON"),
        (response({"data": []}), "invalid JSON root"),
    ],
)
def test_qualification_rejects_invalid_http_response(
    replacement: OpenLigaDBQualificationResponse, message: str
) -> None:
    responses = valid_responses()
    responses[0] = replacement

    with pytest.raises(OpenLigaDBQualificationError, match=message):
        run_qualification(responses)


def test_qualification_rejects_non_utc_clock() -> None:
    transport = StubTransport(valid_responses())

    with pytest.raises(OpenLigaDBQualificationError, match="clock"):
        qualify_dfb_pokal(
            transport=transport,
            clock=lambda: datetime(2026, 8, 18, 20, 0),
        )


def test_qualification_rejects_future_source_update() -> None:
    item = fixture()
    item["lastUpdateDateTime"] = "2026-08-19T21:00:00"
    responses = valid_responses()
    responses[2] = response([item])

    with pytest.raises(OpenLigaDBQualificationError, match="future"):
        run_qualification(responses)


def test_transport_rejects_query_and_external_paths() -> None:
    transport = StdlibOpenLigaDBQualificationTransport()

    for path in ("https://example.test/data", "/getmatchdata?token=secret"):
        with pytest.raises(OpenLigaDBQualificationError, match="request path"):
            transport.get(path)


def test_main_prints_evidence(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    evidence, _ = run_qualification(valid_responses())
    monkeypatch.setattr(qualification, "qualify_dfb_pokal", lambda: evidence)

    assert qualification.main([]) == 0
    assert json.loads(capsys.readouterr().out)["league_id"] == 4945


def test_main_selects_second_bundesliga(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    transport = StubTransport(valid_second_bundesliga_responses())
    evidence = qualify_second_bundesliga(
        transport=transport,
        clock=lambda: OBSERVED_AT,
    )
    monkeypatch.setattr(qualification, "qualify_second_bundesliga", lambda: evidence)

    assert qualification.main(["--competition", SECOND_BUNDESLIGA_PROFILE.key]) == 0
    assert json.loads(capsys.readouterr().out)["league_id"] == 4938


def test_main_exits_cleanly_on_qualification_error(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    def fail() -> None:
        raise OpenLigaDBQualificationError("safe failure")

    monkeypatch.setattr(qualification, "qualify_dfb_pokal", fail)

    with pytest.raises(SystemExit) as captured:
        qualification.main([])

    assert captured.value.code == 1
    assert "OpenLigaDB qualification failed: safe failure" in capsys.readouterr().err
