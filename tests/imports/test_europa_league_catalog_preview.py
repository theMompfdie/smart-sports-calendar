"""Real catalog preview with synthetic fixtures, without live provider data."""

import json
import sqlite3
from pathlib import Path

from app.application.manual_preview_service import (
    ManualPreviewService,
    parse_preview_configuration,
)
from app.database.manual_preview_repository import ManualPreviewRepository


def test_uel_catalog_allows_manual_preview_and_rejects_foreign_participant(
    tmp_path, initialize_test_catalog
):
    database = tmp_path / "uel.db"
    initialize_test_catalog(database)
    example = Path(__file__).resolve().parents[2] / (
        "docs/examples/manual-import/uefa-conference-league-initial.json"
    )
    raw = json.loads(example.read_bytes())
    raw["scope"].update(competition_key="uefa_europa_league", season_key="2026_27")
    raw["boundaries"] = raw["boundaries"][:1]
    raw["fixtures"] = raw["fixtures"][:1]
    raw["fixtures"][0]["home"]["participant_key"] = "bayer_04_leverkusen"
    raw["fixtures"][0]["away"]["participant_key"] = "ac_milan"
    configuration = parse_preview_configuration(
        json.dumps(
            {
                "instance_ref": "test-staging",
                "namespace": raw["namespace"],
                "scope": {
                    key: raw["scope"][key]
                    for key in ("sport_key", "competition_key", "season_key")
                },
                "competition_format": "hybrid_tournament",
                "boundaries": raw["boundaries"],
            }
        ).encode()
    )
    service = ManualPreviewService(ManualPreviewRepository(database))
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT COUNT(*) FROM sports_events").fetchone()
    accepted = service.preview(json.dumps(raw).encode(), configuration)
    assert accepted.accepted, accepted.to_dict()
    raw["fixtures"][0]["away"]["participant_key"] = "arsenal"
    rejected = service.preview(json.dumps(raw).encode(), configuration)
    assert not rejected.accepted
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM sports_events").fetchone()
            == before
        )
