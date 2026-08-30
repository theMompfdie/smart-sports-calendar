from datetime import UTC, datetime

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
