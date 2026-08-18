import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
    FixtureImportScope,
)
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.data_sources_repository import DataSourcesRepository
from app.database.fixture_import_repository import (
    FixtureImportDecision,
    FixtureImportRepository,
)
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.domain.competition_lifecycle import (
    CompetitionFormat,
    CompetitionLifecycleScope,
    FixtureObservationScopeKind,
)
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.application.test_api_football_fixture_normalization_service import (
    create_context,
)
from tests.integration.provider_outlook_support import RecordingGraphClient

CALENDAR_ID = "cup-reconciliation-calendar"
OBSERVED_AT = datetime(2026, 8, 8, 12, tzinfo=UTC)


def complete_round_scope(
    competition_id: int,
    season_id: int,
    observation_id: str,
    observed_at_utc: datetime,
) -> FixtureImportScope:
    return FixtureImportScope(
        competition_id=competition_id,
        season_id=season_id,
        observation_id=observation_id,
        observed_at_utc=observed_at_utc,
        lifecycle=CompetitionLifecycleScope(
            competition_format=CompetitionFormat.KNOCKOUT_CUP,
            scope_kind=FixtureObservationScopeKind.COMPLETE_ROUND,
            stage="knockout",
            round_name="round_of_16",
        ),
        authoritative=True,
    )


def test_bounded_cup_removal_rolls_back_and_reappears_in_outlook(
    tmp_path: Path,
) -> None:
    context = create_context(tmp_path)
    with sqlite3.connect(context.database_path) as connection:
        connection.execute(
            "UPDATE competitions SET competition_type = ? WHERE id = ?",
            (CompetitionFormat.KNOCKOUT_CUP.value, context.competition_id),
        )
    normalized = tuple(
        fixture
        for fixture in context.service.normalize_current_premier_league()
        if fixture.kickoff_confirmed
    )
    round_of_16 = tuple(
        replace(fixture, stage="knockout", round_name="round_of_16")
        for fixture in normalized[:2]
    )
    other_stage = replace(normalized[2], stage="qualifying", round_name="round_of_16")
    quarterfinal = replace(normalized[3], stage="knockout", round_name="quarterfinal")
    importer = ApiFootballFixtureImportService(
        DataSourcesRepository(context.database_path),
        FixtureImportRepository(context.database_path),
    )
    importer.import_fixtures(
        (*round_of_16, other_stage, quarterfinal),
        FixtureImportScope(
            competition_id=context.competition_id,
            season_id=context.season_id,
            observation_id="cup-initial",
            observed_at_utc=OBSERVED_AT,
            lifecycle=CompetitionLifecycleScope(
                competition_format=CompetitionFormat.KNOCKOUT_CUP,
                scope_kind=FixtureObservationScopeKind.PARTIAL,
            ),
            authoritative=True,
        ),
    )
    graph = RecordingGraphClient()
    calendar_mappings = CalendarEventMappingsRepository(context.database_path)
    calendar = SynchronizationOrchestrator(
        SynchronizationQueryRepository(context.database_path),
        EventSynchronizer(
            OutlookEventPayloadBuilder(),
            graph,  # type: ignore[arg-type]
            calendar_mappings,
        ),
        SyncRunsRepository(context.database_path),
    )
    initial_sync = calendar.synchronize(CALENDAR_ID, 100)
    assert initial_sync.items_created == 4
    missing = round_of_16[0]
    source_mapping = context.mappings.get_by_external_id(
        context.source_id, "event", missing.external_id
    )
    assert source_mapping is not None
    initial_calendar_mapping = calendar_mappings.get_by_event(
        source_mapping.internal_id, CALENDAR_ID
    )
    assert initial_calendar_mapping is not None

    first_absence = importer.import_fixtures(
        round_of_16[1:],
        complete_round_scope(
            context.competition_id,
            context.season_id,
            "cup-missing-1",
            OBSERVED_AT.replace(hour=13),
        ),
    )
    with sqlite3.connect(context.database_path) as connection:
        connection.executescript(
            """
            CREATE TRIGGER fail_cup_removal
            BEFORE UPDATE OF deleted_at ON sports_events
            WHEN NEW.deleted_at IS NOT NULL
            BEGIN
                SELECT RAISE(ABORT, 'forced cup removal failure');
            END;
            """
        )
    second_scope = complete_round_scope(
        context.competition_id,
        context.season_id,
        "cup-missing-2",
        OBSERVED_AT.replace(hour=14),
    )

    with pytest.raises(sqlite3.IntegrityError, match="forced cup removal failure"):
        importer.import_fixtures(round_of_16[1:], second_scope)

    missing_event = SportsEventsRepository(context.database_path).get_by_id(
        source_mapping.internal_id
    )
    assert missing_event is not None
    assert first_absence.count(FixtureImportDecision.DELETE) == 0
    assert missing_event.deleted_at is None
    with sqlite3.connect(context.database_path) as connection:
        state = connection.execute(
            """
            SELECT missing_observation_count, last_observation_id
            FROM fixture_reconciliation_state
            WHERE source_id = ? AND event_id = ?
            """,
            (context.source_id, source_mapping.internal_id),
        ).fetchone()
        assert state == (1, "cup-missing-1")
        connection.execute("DROP TRIGGER fail_cup_removal")

    second_absence = importer.import_fixtures(round_of_16[1:], second_scope)
    deletion_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert second_absence.count(FixtureImportDecision.DELETE) == 1
    assert deletion_sync.items_deleted == 1
    assert [operation.method for operation in graph.operations] == [
        "POST",
        "POST",
        "POST",
        "POST",
        "DELETE",
    ]
    for outside_scope in (other_stage, quarterfinal):
        outside_mapping = context.mappings.get_by_external_id(
            context.source_id, "event", outside_scope.external_id
        )
        assert outside_mapping is not None
        outside_event = SportsEventsRepository(context.database_path).get_by_id(
            outside_mapping.internal_id
        )
        assert outside_event is not None
        assert outside_event.deleted_at is None
        persisted_calendar_mapping = calendar_mappings.get_by_event(
            outside_event.id, CALENDAR_ID
        )
        assert persisted_calendar_mapping is not None
        assert persisted_calendar_mapping.sync_status == "synced"

    reappeared = importer.import_fixtures(
        round_of_16,
        complete_round_scope(
            context.competition_id,
            context.season_id,
            "cup-reappeared",
            OBSERVED_AT.replace(hour=15),
        ),
    )
    reappearance_sync = calendar.synchronize(CALENDAR_ID, 100)
    restored_event = SportsEventsRepository(context.database_path).get_by_id(
        source_mapping.internal_id
    )
    restored_mapping = calendar_mappings.get_by_event(
        source_mapping.internal_id, CALENDAR_ID
    )

    assert reappeared.count(FixtureImportDecision.UPDATE) == 1
    assert reappearance_sync.items_created == 1
    assert restored_event is not None
    assert restored_event.deleted_at is None
    assert restored_mapping is not None
    assert restored_mapping.id == initial_calendar_mapping.id
    assert restored_mapping.transaction_id == initial_calendar_mapping.transaction_id
    assert (
        restored_mapping.outlook_event_id == initial_calendar_mapping.outlook_event_id
    )
    assert [operation.method for operation in graph.operations] == [
        "POST",
        "POST",
        "POST",
        "POST",
        "DELETE",
        "POST",
    ]
    with sqlite3.connect(context.database_path) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM fixture_reconciliation_state"
            ).fetchone()[0]
            == 0
        )
