from dataclasses import replace
from datetime import timedelta

from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.openligadb_dfb_pokal_service import (
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
from app.providers.contracts import SourceJobDefinition, SourceRole, SourceScope
from app.providers.openligadb.models import parse_snapshot
from app.providers.openligadb.profiles import DFB_POKAL_PROFILE
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.integration.provider_outlook_support import RecordingGraphClient
from tests.providers.openligadb.support import FETCHED_AT, payloads

CALENDAR_ID = "dfb-pokal-staging-calendar"


class SnapshotAdapter:
    profile = DFB_POKAL_PROFILE

    def __init__(self) -> None:
        self.snapshot = parse_snapshot(
            *payloads(),
            profile=DFB_POKAL_PROFILE,
            fetched_at_utc=FETCHED_AT,
            request_attempts=3,
        )

    def fetch_snapshot(self):
        return self.snapshot


def create_harness(database_path):
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    source_mappings = SourceMappingsRepository(database_path)
    runs = SyncRunsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
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
    tmp_path,
) -> None:
    provider, calendar, adapter, graph = create_harness(
        tmp_path / "openligadb-dfb-pokal.db"
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
    assert payload["subject"] == "SC St. Tönis vs Eintracht Frankfurt"
    body = payload["body"]
    assert isinstance(body, dict)
    assert f"Source: {OPENLIGADB_ATTRIBUTION}" in body["content"]
    assert "Round: round-1" in body["content"]

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
