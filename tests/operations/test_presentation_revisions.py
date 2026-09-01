import json
from pathlib import Path

from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.database import Database
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.operations.presentation_revisions import main


def test_invalidate_all_cli_queues_live_mappings(
    tmp_path: Path,
    capsys,
) -> None:
    database_path = tmp_path / "sports.db"
    Database(database_path).initialize()
    sport = SportsRepository(database_path).upsert("football", "Football")
    event = SportsEventsRepository(database_path).upsert(
        sport_id=sport.id,
        event_key="fixture-1",
        event_type="match",
        title="Home vs Away",
        start_time="2026-09-12T14:00:00+00:00",
    )
    mappings = CalendarEventMappingsRepository(database_path)
    mapping = mappings.create_pending(event.id, "calendar-1")
    assert mappings.mark_synced(
        mapping.id,
        outlook_event_id="outlook-1",
        outlook_change_key=None,
        content_hash="hash-1",
        event_revision=event.sync_revision,
    )

    result = main(
        [
            "--database",
            str(database_path),
            "--invalidate-all",
        ]
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {"affected_mappings": 1}
    refreshed = mappings.get_by_id(mapping.id)
    assert refreshed is not None
    assert refreshed.presentation_revision == 2
    assert refreshed.last_synced_presentation_revision == 1
