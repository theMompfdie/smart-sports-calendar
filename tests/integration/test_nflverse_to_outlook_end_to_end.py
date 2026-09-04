import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.api_football_import_orchestrator import (
    ProviderImportOrchestrationError,
)
from app.application.nflverse_competition_service import (
    NflverseCompetitionService,
    register_nflverse_source,
)
from app.application.nflverse_import_orchestrator import NflverseImportOrchestrator
from app.config.settings import NflverseSettings
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.fixture_import_repository import FixtureImportRepository
from app.database.participants_catalog import initialize_participants_catalog
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.source_assignments_repository import (
    SourceAssignmentsRepository,
    SourceAssignmentWrite,
)
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.graph.client import GraphClientError
from app.providers.contracts import SourceJobDefinition, SourceRole, SourceScope
from app.providers.nflverse.models import parse_snapshot
from app.providers.nflverse.profiles import NFL_2026_REGULAR_SEASON_PROFILE
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import (
    DEFAULT_OUTLOOK_GRAPH_TIME_ZONE,
    OutlookEventPayloadBuilder,
    OutlookEventPresentation,
)
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator
from app.synchronization.synchronization_runtime_service import (
    SynchronizationRuntimeService,
)

from tests.integration.provider_outlook_support import (
    CapturedGraphOperation,
    RecordingGraphClient,
)
from tests.providers.nflverse.support import csv_bytes, schedule_rows

CALENDAR_ID = "nfl-test-calendar"
OBSERVED_AT = datetime(2026, 8, 30, 12, tzinfo=UTC)
VIENNA = ZoneInfo("Europe/Vienna")


class MutableNflverseAdapter:
    profile = NFL_2026_REGULAR_SEASON_PROFILE

    def __init__(self) -> None:
        self.rows = schedule_rows()
        self.observed_at = OBSERVED_AT

    def fetch_snapshot(self):
        return parse_snapshot(
            csv_bytes(self.rows),
            profile=self.profile,
            fetched_at_utc=self.observed_at,
            request_attempts=1,
        )


@dataclass
class NflverseOutlookHarness:
    database_path: Path
    provider: NflverseImportOrchestrator
    calendar: SynchronizationOrchestrator
    adapter: MutableNflverseAdapter
    graph: RecordingGraphClient
    runs: SyncRunsRepository
    source_mappings: SourceMappingsRepository
    calendar_mappings: CalendarEventMappingsRepository
    source_id: int

    @classmethod
    def create(
        cls,
        database_path: Path,
        payload_builder: OutlookEventPayloadBuilder | None = None,
    ) -> "NflverseOutlookHarness":
        Database(database_path).initialize()
        sports = SportsRepository(database_path)
        competitions = CompetitionsRepository(database_path)
        seasons = SeasonsRepository(database_path)
        participants = ParticipantsRepository(database_path)
        memberships = SeasonParticipantsRepository(database_path)
        sources = DataSourcesRepository(database_path)
        source_mappings = SourceMappingsRepository(database_path)
        calendar_mappings = CalendarEventMappingsRepository(database_path)
        runs = SyncRunsRepository(database_path)
        initialize_sports_catalog(sports)
        initialize_competitions_catalog(competitions, sports)
        initialize_seasons_catalog(seasons, competitions, sports)
        initialize_participants_catalog(
            participants, memberships, sports, competitions, seasons
        )
        settings = NflverseSettings(enabled=True)
        source = register_nflverse_source(settings, sources)
        adapter = MutableNflverseAdapter()
        service = NflverseCompetitionService(
            adapter,
            sports,
            competitions,
            seasons,
            participants,
            settings=settings,
            season_participants_repository=memberships,
            data_sources_repository=sources,
            source_mappings_repository=source_mappings,
        )
        american_football = sports.get_by_key("american_football")
        assert american_football is not None
        competition = competitions.get_by_key(american_football.id, "nfl")
        assert competition is not None
        season = seasons.get_by_key(competition.id, "2026")
        assert season is not None
        job = SourceJobDefinition(
            job_key="nflverse-nfl-2026",
            source_key="nflverse",
            role=SourceRole.AUTHORITATIVE,
            scope=SourceScope("american_football", "nfl", "2026"),
            interval_seconds=21600,
        )
        SourceAssignmentsRepository(database_path).synchronize(
            (
                SourceAssignmentWrite(
                    job_key=job.job_key,
                    source_id=source.id,
                    competition_id=competition.id,
                    season_id=season.id,
                    role=job.role,
                    interval_seconds=job.interval_seconds,
                ),
            )
        )
        provider = NflverseImportOrchestrator(
            competition_service=service,
            import_service=ApiFootballFixtureImportService(
                sources,
                FixtureImportRepository(database_path),
                source_key="nflverse",
            ),
            sync_runs_repository=runs,
            data_sources_repository=sources,
            job_definition=job,
        )
        graph = RecordingGraphClient()
        calendar = SynchronizationOrchestrator(
            query_repository=SynchronizationQueryRepository(database_path),
            event_synchronizer=EventSynchronizer(
                payload_builder or OutlookEventPayloadBuilder(),
                graph,  # type: ignore[arg-type]
                calendar_mappings,
            ),
            sync_runs_repository=runs,
        )
        return cls(
            database_path,
            provider,
            calendar,
            adapter,
            graph,
            runs,
            source_mappings,
            calendar_mappings,
            source.id,
        )

    def synchronize_all(self, limit: int = 100):
        batches = []
        remaining = self.table_count("sports_events")
        while remaining > 0:
            result = self.calendar.synchronize(CALENDAR_ID, limit)
            batches.append(result)
            remaining -= result.items_processed
        return tuple(batches)

    def table_count(self, table: str) -> int:
        if table not in {
            "sports_events",
            "calendar_event_mappings",
            "source_mappings",
        }:
            raise ValueError("Unsupported integration-test table.")
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        assert row is not None
        return int(row[0])

    def calendar_mapping_for_game(self, game_id: str):
        source_mapping = self.source_mappings.get_by_external_id(
            self.source_id, "event", game_id
        )
        assert source_mapping is not None
        mapping = self.calendar_mappings.get_by_event(
            source_mapping.internal_id, CALENDAR_ID
        )
        assert mapping is not None
        return mapping


def graph_body(operation: CapturedGraphOperation) -> str:
    assert operation.payload is not None
    body = operation.payload["body"]
    assert isinstance(body, dict)
    content = body["content"]
    assert isinstance(content, str)
    return content


def graph_subject(operation: CapturedGraphOperation) -> str:
    assert operation.payload is not None
    subject = operation.payload["subject"]
    assert isinstance(subject, str)
    return subject


def graph_categories(operation: CapturedGraphOperation) -> tuple[str, ...]:
    assert operation.payload is not None
    categories = operation.payload["categories"]
    assert isinstance(categories, list)
    assert all(isinstance(category, str) for category in categories)
    return tuple(categories)


def graph_start(operation: CapturedGraphOperation) -> datetime:
    assert operation.payload is not None
    start = operation.payload["start"]
    assert isinstance(start, dict)
    date_time = start["dateTime"]
    time_zone = start["timeZone"]
    assert isinstance(date_time, str)
    assert isinstance(time_zone, str)
    assert time_zone == DEFAULT_OUTLOOK_GRAPH_TIME_ZONE
    return datetime.fromisoformat(date_time).replace(tzinfo=VIENNA)


def graph_end(operation: CapturedGraphOperation) -> datetime:
    assert operation.payload is not None
    end = operation.payload["end"]
    assert isinstance(end, dict)
    date_time = end["dateTime"]
    time_zone = end["timeZone"]
    assert isinstance(date_time, str)
    assert isinstance(time_zone, str)
    assert time_zone == DEFAULT_OUTLOOK_GRAPH_TIME_ZONE
    return datetime.fromisoformat(date_time).replace(tzinfo=VIENNA)


def test_nfl_snapshot_synchronizes_272_events_and_is_idempotent(
    tmp_path: Path,
) -> None:
    harness = NflverseOutlookHarness.create(tmp_path / "nfl.db")

    first_import = harness.provider.import_current_competition()
    first_sync = harness.synchronize_all(limit=100)
    first_operation_count = len(harness.graph.operations)

    assert first_import.items_created == 272
    assert [batch.items_created for batch in first_sync] == [100, 100, 72]
    assert all(batch.items_failed == 0 for batch in first_sync)
    assert harness.table_count("sports_events") == 272
    assert harness.table_count("calendar_event_mappings") == 272
    assert len(harness.graph.events) == 272
    assert first_operation_count == 272
    assert {operation.method for operation in harness.graph.operations} == {"POST"}
    assert all(
        graph_subject(operation).startswith("🏈 ")
        for operation in harness.graph.operations
    )
    assert all(
        graph_categories(operation) == ("National Football League",)
        for operation in harness.graph.operations
    )
    assert all(
        "Schedule data provided by nflverse under CC BY 4.0" in graph_body(operation)
        for operation in harness.graph.operations
    )
    assert all(
        "Subject to NFL flex scheduling." in graph_body(operation)
        for operation in harness.graph.operations
    )
    assert all(
        graph_end(operation) - graph_start(operation) == timedelta(hours=3)
        for operation in harness.graph.operations
    )

    vienna_starts = [
        graph_start(operation).astimezone(VIENNA)
        for operation in harness.graph.operations
    ]
    summer = next(start for start in vienna_starts if start.month == 9)
    winter = next(start for start in vienna_starts if start.month == 11)
    assert summer.utcoffset() == timedelta(hours=2)
    assert winter.utcoffset() == timedelta(hours=1)

    harness.adapter.observed_at += timedelta(hours=6)
    unchanged_import = harness.provider.import_current_competition()
    unchanged_sync = harness.calendar.synchronize(CALENDAR_ID, 500)

    assert unchanged_import.items_unchanged == 272
    assert unchanged_sync.items_unchanged == 272
    assert len(harness.graph.operations) == first_operation_count


def test_three_hour_duration_updates_existing_events_without_duplicates(
    tmp_path: Path,
) -> None:
    legacy_builder = OutlookEventPayloadBuilder(
        OutlookEventPresentation(fallback_duration_minutes_by_sport=())
    )
    harness = NflverseOutlookHarness.create(
        tmp_path / "nfl-duration-upgrade.db",
        payload_builder=legacy_builder,
    )
    harness.provider.import_current_competition()
    harness.synchronize_all()
    original_outlook_ids = set(harness.graph.events)
    original_operation_count = len(harness.graph.operations)

    harness.calendar = SynchronizationOrchestrator(
        query_repository=SynchronizationQueryRepository(harness.database_path),
        event_synchronizer=EventSynchronizer(
            OutlookEventPayloadBuilder(),
            harness.graph,  # type: ignore[arg-type]
            harness.calendar_mappings,
        ),
        sync_runs_repository=harness.runs,
    )
    changed = harness.calendar.synchronize(CALENDAR_ID, 500)
    duration_updates = harness.graph.operations[original_operation_count:]

    assert changed.items_created == 0
    assert changed.items_updated == 272
    assert set(harness.graph.events) == original_outlook_ids
    assert {operation.method for operation in duration_updates} == {"PATCH"}
    assert all(
        graph_end(operation) - graph_start(operation) == timedelta(hours=3)
        for operation in duration_updates
    )

    operation_count_after_update = len(harness.graph.operations)
    unchanged = harness.calendar.synchronize(CALENDAR_ID, 500)

    assert unchanged.items_unchanged == 272
    assert unchanged.items_created == 0
    assert unchanged.items_updated == 0
    assert len(harness.graph.operations) == operation_count_after_update


def test_changed_operator_notice_updates_one_stable_outlook_event(
    tmp_path: Path,
) -> None:
    harness = NflverseOutlookHarness.create(tmp_path / "nfl-notice.db")
    harness.provider.import_current_competition()
    harness.synchronize_all()
    game_id = harness.adapter.rows[0]["game_id"]
    before = harness.calendar_mapping_for_game(game_id)
    operation_count = len(harness.graph.operations)
    with sqlite3.connect(harness.database_path) as connection:
        row = connection.execute(
            "SELECT metadata_json FROM sports_events WHERE id = ?",
            (before.event_id,),
        ).fetchone()
        assert row is not None
        metadata = json.loads(row[0])
        metadata["operator_notice"] = "Schedule time confirmed."
        connection.execute(
            "UPDATE sports_events SET metadata_json = ? WHERE id = ?",
            (json.dumps(metadata, sort_keys=True), before.event_id),
        )

    changed_sync = harness.calendar.synchronize(CALENDAR_ID, 500)
    after = harness.calendar_mapping_for_game(game_id)

    assert changed_sync.items_updated == 1
    assert changed_sync.items_unchanged == 271
    assert len(harness.graph.operations) == operation_count + 1
    operation = harness.graph.operations[-1]
    assert operation.method == "PATCH"
    assert operation.event_id == before.outlook_event_id
    assert "Schedule time confirmed." in graph_body(operation)
    assert after.outlook_event_id == before.outlook_event_id
    assert after.transaction_id == before.transaction_id


def test_nfl_flex_change_updates_one_stable_outlook_event(tmp_path: Path) -> None:
    harness = NflverseOutlookHarness.create(tmp_path / "nfl-flex.db")
    harness.provider.import_current_competition()
    harness.synchronize_all()
    game_id = harness.adapter.rows[0]["game_id"]
    before = harness.calendar_mapping_for_game(game_id)
    assert before.outlook_event_id is not None
    previous_payload = harness.graph.events[before.outlook_event_id]
    harness.adapter.rows[0]["gametime"] = "20:30"
    harness.adapter.observed_at += timedelta(hours=6)

    changed_import = harness.provider.import_current_competition()
    changed_sync = harness.calendar.synchronize(CALENDAR_ID, 500)
    after = harness.calendar_mapping_for_game(game_id)

    assert changed_import.items_updated == 1
    assert changed_import.items_unchanged == 271
    assert changed_sync.items_updated == 1
    assert changed_sync.items_unchanged == 271
    assert harness.graph.operations[-1].method == "PATCH"
    assert harness.graph.operations[-1].event_id == before.outlook_event_id
    assert after.outlook_event_id == before.outlook_event_id
    assert after.transaction_id == before.transaction_id
    after_outlook_event_id = after.outlook_event_id
    assert after_outlook_event_id is not None
    assert harness.table_count("sports_events") == 272
    assert len(harness.graph.events) == 272
    assert harness.graph.events[after_outlook_event_id] != previous_payload


def test_rejected_nfl_observation_preserves_sqlite_and_graph_state(
    tmp_path: Path,
) -> None:
    harness = NflverseOutlookHarness.create(tmp_path / "nfl-rejected.db")
    harness.provider.import_current_competition()
    harness.synchronize_all()
    operation_count = len(harness.graph.operations)
    graph_events = dict(harness.graph.events)
    harness.adapter.rows.pop()
    harness.adapter.observed_at += timedelta(hours=6)

    with pytest.raises(ProviderImportOrchestrationError):
        harness.provider.import_current_competition()
    unchanged_sync = harness.calendar.synchronize(CALENDAR_ID, 500)

    assert unchanged_sync.items_unchanged == 272
    assert unchanged_sync.items_cancelled == 0
    assert unchanged_sync.items_deleted == 0
    assert harness.table_count("sports_events") == 272
    assert harness.table_count("calendar_event_mappings") == 272
    assert harness.graph.events == graph_events
    assert len(harness.graph.operations) == operation_count


def test_graph_failure_and_interrupted_run_recover_without_duplicates(
    tmp_path: Path,
) -> None:
    harness = NflverseOutlookHarness.create(tmp_path / "nfl-recovery.db")
    harness.provider.import_current_competition()
    interrupted = harness.runs.start(
        run_type="calendar_sync",
        metadata={"calendar_id": CALENDAR_ID, "limit": 100},
    )
    harness.graph.create_failure = GraphClientError("Mocked Graph unavailable.")
    failed_sync = harness.calendar.synchronize(CALENDAR_ID, 1)
    with sqlite3.connect(harness.database_path) as connection:
        row = connection.execute(
            """
            SELECT transaction_id FROM calendar_event_mappings
            WHERE sync_status = 'failed'
            """
        ).fetchone()
    assert row is not None
    failed_transaction_id = str(row[0])

    runtime = SynchronizationRuntimeService(
        orchestrator=harness.calendar,
        sync_runs_repository=harness.runs,
        logger=MagicMock(spec=logging.Logger),
    )
    first_recovery_batch = runtime.run(CALENDAR_ID, 100)
    assert first_recovery_batch is not None
    remaining_batches = (
        harness.calendar.synchronize(CALENDAR_ID, 100),
        harness.calendar.synchronize(CALENDAR_ID, 100),
    )

    recovered = harness.runs.get_by_id(interrupted.id)
    assert recovered is not None
    assert recovered.status == "failed"
    assert failed_sync.status == "completed_with_errors"
    assert failed_sync.items_failed == 1
    assert first_recovery_batch.items_created == 100
    assert [batch.items_created for batch in remaining_batches] == [100, 72]
    assert harness.table_count("sports_events") == 272
    assert harness.table_count("calendar_event_mappings") == 272
    assert len(harness.graph.events) == 272
    assert [operation.method for operation in harness.graph.operations].count(
        "POST"
    ) == 273
    retried = next(
        mapping
        for mapping in harness.calendar_mappings.get_by_status("synced")
        if mapping.transaction_id == failed_transaction_id
    )
    assert retried.sync_status == "synced"
    assert retried.outlook_event_id is not None
