from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from app.domain.competition_lifecycle import FixtureObservationScopeKind
from app.providers.nflverse.exceptions import (
    NflverseIntegrityError,
    NflverseSchemaError,
)
from app.providers.nflverse.models import parse_snapshot
from app.providers.nflverse.profiles import NFL_2026_REGULAR_SEASON_PROFILE

from tests.providers.nflverse.support import csv_bytes, schedule_rows

FETCHED = datetime(2026, 8, 30, 14, 23, 2, tzinfo=UTC)


def parse(body: bytes):
    return parse_snapshot(
        body,
        profile=NFL_2026_REGULAR_SEASON_PROFILE,
        fetched_at_utc=FETCHED,
        request_attempts=2,
    )


def test_parse_snapshot_accepts_exact_reviewed_scope_and_converts_eastern_time() -> (
    None
):
    snapshot = parse(csv_bytes())

    assert len(snapshot.games) == 272
    assert len({game.game_id for game in snapshot.games}) == 272
    assert {game.week for game in snapshot.games} == set(range(1, 19))
    assert snapshot.request_attempts == 2
    september = next(game for game in snapshot.games if game.week == 1)
    january = next(game for game in snapshot.games if game.week == 18)
    assert september.kickoff_utc.hour == 0
    assert january.kickoff_utc.hour == 1
    assert (
        NFL_2026_REGULAR_SEASON_PROFILE.lifecycle_scope_kind
        is FixtureObservationScopeKind.PARTIAL
    )


@pytest.mark.parametrize(
    "mutation,message",
    [
        (lambda rows: rows.pop(), "game count"),
        (
            lambda rows: rows.__setitem__(
                1, {**rows[1], "game_id": rows[0]["game_id"]}
            ),
            "duplicate game",
        ),
        (
            lambda rows: rows.__setitem__(0, {**rows[0], "home_team": "XXX"}),
            "participants",
        ),
        (lambda rows: rows.__setitem__(0, {**rows[0], "week": "19"}), "week"),
    ],
)
def test_parse_snapshot_rejects_unsafe_scope(mutation, message: str) -> None:
    rows = schedule_rows()
    mutation(rows)
    with pytest.raises(NflverseIntegrityError, match=message):
        parse(csv_bytes(rows))


def test_parse_snapshot_rejects_missing_required_column() -> None:
    rows = schedule_rows()
    for row in rows:
        del row["gametime"]
    with pytest.raises(NflverseSchemaError, match="missing required"):
        parse(csv_bytes(rows))


def test_parse_snapshot_rejects_nonexistent_eastern_time() -> None:
    rows = schedule_rows()
    rows[0]["gameday"] = "2026-03-08"
    rows[0]["gametime"] = "02:30"
    with pytest.raises(NflverseSchemaError, match="ambiguous or nonexistent"):
        parse(csv_bytes(rows))


def test_parse_snapshot_filters_other_seasons_and_game_types() -> None:
    rows = schedule_rows()
    rows.extend(
        [
            {**rows[0], "game_id": "ignored-season", "season": "2025"},
            {**rows[0], "game_id": "ignored-post", "game_type": "POST"},
        ]
    )
    snapshot = parse(csv_bytes(rows))
    assert len(snapshot.games) == 272
    assert "ignored-season" not in {game.game_id for game in snapshot.games}
    assert "ignored-post" not in {game.game_id for game in snapshot.games}


@pytest.mark.parametrize("value", ["", "TBD", "25:00", "not-a-time"])
def test_parse_snapshot_rejects_unknown_or_invalid_kickoff(value: str) -> None:
    rows = schedule_rows()
    rows[0]["gametime"] = value
    with pytest.raises(NflverseSchemaError, match="gametime|invalid kickoff"):
        parse(csv_bytes(rows))


def test_parse_snapshot_rejects_malformed_csv() -> None:
    with pytest.raises(NflverseSchemaError, match="malformed CSV"):
        parse(csv_bytes() + b'\n"unterminated')


def test_game_identity_survives_a_flex_scheduling_change() -> None:
    original_rows = schedule_rows()
    flexed_rows = [dict(row) for row in original_rows]
    flexed_rows[0]["gameday"] = "2026-09-11"
    flexed_rows[0]["gametime"] = "21:00"
    original = {game.game_id: game for game in parse(csv_bytes(original_rows)).games}
    flexed = {game.game_id: game for game in parse(csv_bytes(flexed_rows)).games}
    game_id = original_rows[0]["game_id"]
    assert flexed[game_id].game_id == original[game_id].game_id
    assert flexed[game_id].kickoff_utc != original[game_id].kickoff_utc


def test_utc_kickoffs_present_correctly_in_europe_vienna() -> None:
    snapshot = parse(csv_bytes())
    vienna = ZoneInfo("Europe/Vienna")
    september = next(game for game in snapshot.games if game.week == 1)
    january = next(game for game in snapshot.games if game.week == 18)
    assert september.kickoff_utc.astimezone(vienna).hour == 2
    assert january.kickoff_utc.astimezone(vienna).hour == 2
