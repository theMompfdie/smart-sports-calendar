import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.api_football_import_orchestrator import (
    ProviderImportOrchestrationError,
)
from app.application.openligadb_competition_service import (
    OPENLIGADB_ATTRIBUTION,
    OpenLigaDBDFBPokalService,
    register_openligadb_source,
)
from app.application.openligadb_import_orchestrator import (
    OpenLigaDBImportOrchestrator,
)
from app.config.settings import OpenLigaDBSettings
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.fixture_import_repository import FixtureImportRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.source_assignments_repository import (
    SourceAssignmentsRepository,
    SourceAssignmentWrite,
)
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.providers.contracts import SourceJobDefinition, SourceRole, SourceScope
from app.providers.openligadb.exceptions import OpenLigaDBIntegrityError
from app.providers.openligadb.models import parse_snapshot
from app.providers.openligadb.profiles import DFB_POKAL_PROFILE
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.catalog_support import CatalogInitializer
from tests.integration.provider_outlook_support import RecordingGraphClient
from tests.providers.openligadb.support import FETCHED_AT, payloads

CALENDAR_ID = "dfb-pokal-staging-calendar"


class SnapshotAdapter:
    profile = DFB_POKAL_PROFILE

    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.snapshot = parse_snapshot(
            *payloads(),
            profile=DFB_POKAL_PROFILE,
            fetched_at_utc=FETCHED_AT,
            request_attempts=3,
        )

    def fetch_snapshot(self):
        if self.failure is not None:
            raise self.failure
        return self.snapshot


def create_harness(database_path, *, initialize_test_catalog: CatalogInitializer):
    initialize_test_catalog(database_path)
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    source_mappings = SourceMappingsRepository(database_path)
    runs = SyncRunsRepository(database_path)
    settings = OpenLigaDBSettings(enabled=True)
    source = register_openligadb_source(settings, sources)
    adapter = SnapshotAdapter()
    service = OpenLigaDBDFBPokalService(
        settings=settings,
        adapter=adapter,
        sports_repository=sports,
        competitions_repository=competitions,
        seasons_repository=seasons,
        participants_repository=participants,
        season_participants_repository=memberships,
        data_sources_repository=sources,
        source_mappings_repository=source_mappings,
    )
    football = sports.get_by_key("football")
    assert football is not None
    competition = competitions.get_by_key(football.id, "dfb_pokal")
    assert competition is not None
    season = seasons.get_by_key(competition.id, "2026_27")
    assert season is not None
    job = SourceJobDefinition(
        job_key="openligadb-dfb-pokal",
        source_key="openligadb",
        role=SourceRole.AUTHORITATIVE,
        scope=SourceScope("football", "dfb_pokal", "2026_27"),
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
    provider = OpenLigaDBImportOrchestrator(
        competition_service=service,
        import_service=ApiFootballFixtureImportService(
            sources,
            FixtureImportRepository(database_path),
            source_key="openligadb",
        ),
        sync_runs_repository=runs,
        data_sources_repository=sources,
        job_definition=job,
    )
    graph = RecordingGraphClient()
    calendar = SynchronizationOrchestrator(
        query_repository=SynchronizationQueryRepository(database_path),
        event_synchronizer=EventSynchronizer(
            OutlookEventPayloadBuilder(),
            graph,  # type: ignore[arg-type]
            CalendarEventMappingsRepository(database_path),
        ),
        sync_runs_repository=runs,
    )
    return provider, calendar, adapter, graph


def test_dfb_pokal_import_is_idempotent_and_renders_openligadb_attribution(
    tmp_path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    provider, calendar, adapter, graph = create_harness(
        tmp_path / "openligadb-dfb-pokal.db",
        initialize_test_catalog=initialize_test_catalog,
    )

    first_import = provider.import_current_competition()
    first_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert first_import.items_created == 1
    assert first_import.items_cancelled == 0
    assert first_import.items_deleted == 0
    assert first_sync.items_created == 1
    assert len(graph.operations) == 1
    payload = graph.operations[0].payload
    assert payload is not None
    assert payload["subject"] == "⚽ SC St. Tönis vs Eintracht Frankfurt"
    assert payload["categories"] == ["DFB-Pokal"]
    body = payload["body"]
    assert isinstance(body, dict)
    assert OPENLIGADB_ATTRIBUTION in body["content"]
    assert ">round-1</td>" in body["content"]

    second_import = provider.import_current_competition()
    second_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert second_import.items_unchanged == 1
    assert second_sync.items_unchanged == 1
    assert len(graph.operations) == 1

    match = adapter.snapshot.matches[0]
    adapter.snapshot = replace(
        adapter.snapshot,
        matches=(
            replace(
                match,
                kickoff_utc=match.kickoff_utc + timedelta(hours=2),
                source_updated_at=match.source_updated_at + timedelta(days=1),
            ),
        ),
        fetched_at_utc=adapter.snapshot.fetched_at_utc + timedelta(minutes=5),
    )

    corrected_import = provider.import_current_competition()
    corrected_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert corrected_import.items_updated == 1
    assert corrected_sync.items_updated == 1
    assert graph.operations[-1].method == "PATCH"


def test_dfb_pokal_restart_and_provider_failure_preserve_outlook_identity(
    tmp_path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    database_path = tmp_path / "openligadb-dfb-pokal-recovery.db"
    provider, calendar, _, graph = create_harness(
        database_path, initialize_test_catalog=initialize_test_catalog
    )

    assert provider.import_current_competition().items_created == 1
    assert calendar.synchronize(CALENDAR_ID, 100).items_created == 1
    assert len(graph.operations) == 1

    restarted_provider, restarted_calendar, restarted_adapter, restarted_graph = (
        create_harness(database_path, initialize_test_catalog=initialize_test_catalog)
    )
    assert restarted_provider.import_current_competition().items_unchanged == 1
    assert restarted_calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 1
    assert restarted_graph.operations == []

    restarted_adapter.failure = RuntimeError("simulated provider outage")
    with pytest.raises(
        ProviderImportOrchestrationError,
        match="Provider import failed with RuntimeError",
    ):
        restarted_provider.import_current_competition()

    assert restarted_calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 1
    assert restarted_graph.operations == []

    restarted_adapter.failure = None
    assert restarted_provider.import_current_competition().items_unchanged == 1
    assert restarted_calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 1
    assert restarted_graph.operations == []

    provider_runs = SyncRunsRepository(database_path).get_recent(
        run_type="provider_import"
    )
    assert [run.status for run in provider_runs[:3]] == [
        "completed",
        "failed",
        "completed",
    ]


def test_jeddeloh_alias_changes_preserve_import_and_outlook_identity(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    database_path = tmp_path / "jeddeloh-alias.db"
    provider, calendar, adapter, graph = create_harness(
        database_path, initialize_test_catalog=initialize_test_catalog
    )
    sources = DataSourcesRepository(database_path)
    source = sources.get_by_key("openligadb")
    assert source is not None
    football = SportsRepository(database_path).get_by_key("football")
    assert football is not None
    participant = ParticipantsRepository(database_path).get_by_key(
        football.id, "ssv_jeddeloh"
    )
    assert participant is not None
    mappings = SourceMappingsRepository(database_path)
    participant_mapping_id = None
    event_id = None

    def observe(name: str, team_id: int = 4762) -> None:
        leagues, groups, matches = payloads()
        matches[0]["team1"].update(teamId=team_id, teamName=name)
        adapter.snapshot = parse_snapshot(
            leagues,
            groups,
            matches,
            profile=DFB_POKAL_PROFILE,
            fetched_at_utc=FETCHED_AT,
            request_attempts=1,
        )

    for index, name in enumerate(("SSV Jeddeloh II", "SSV Jeddeloh 2", "SSV Jeddeloh")):
        observe(name)
        imported = provider.import_current_competition()
        synchronized = calendar.synchronize(CALENDAR_ID, 100)
        assert imported.items_created == (1 if index == 0 else 0)
        assert imported.items_unchanged == (0 if index == 0 else 1)
        assert imported.items_cancelled == imported.items_deleted == 0
        assert synchronized.items_created == (1 if index == 0 else 0)
        assert synchronized.items_unchanged == (0 if index == 0 else 1)
        assert len(graph.operations) == 1
        mapping = mappings.get_by_external_id(source.id, "participant", "4762")
        fixture = mappings.get_by_external_id(source.id, "event", "7001")
        assert mapping is not None and fixture is not None
        assert mapping.internal_id == participant.id
        if index == 0:
            participant_mapping_id = mapping.id
            event_id = fixture.internal_id
        assert mapping.id == participant_mapping_id
        assert fixture.internal_id == event_id

    def persisted_state() -> dict[str, list[tuple]]:
        tables = (
            "participants",
            "source_mappings",
            "sports_events",
            "event_participants",
            "calendar_event_mappings",
            "source_assignments",
        )
        with closing(sqlite3.connect(database_path)) as connection:
            return {
                table: connection.execute(
                    f"SELECT * FROM {table} ORDER BY id"
                ).fetchall()
                for table in tables
            }

    before_rejection = persisted_state()
    for team_id, name in ((4762, "SSV Jeddeloh III"), (999999, "SSV Jeddeloh")):
        observe(name, team_id)
        with pytest.raises(ProviderImportOrchestrationError) as failure:
            provider.import_current_competition()
        assert isinstance(failure.value.__cause__, OpenLigaDBIntegrityError)
        assert persisted_state() == before_rejection
        assert len(graph.operations) == 1
        latest_run = SyncRunsRepository(database_path).get_recent(
            run_type="provider_import"
        )[0]
        assert latest_run.status == "failed"

    observe("SSV Jeddeloh")
    assert provider.import_current_competition().items_unchanged == 1
    assert calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 1
    assert len(graph.operations) == 1
