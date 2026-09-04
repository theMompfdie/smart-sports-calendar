from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta

import pytest
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.api_football_import_orchestrator import (
    ProviderImportOrchestrationError,
)
from app.application.openligadb_competition_service import (
    OPENLIGADB_ATTRIBUTION,
    OpenLigaDBCompetitionService,
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
from app.providers.openligadb.profiles import NATIONS_LEAGUE_A_PROFILE
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.integration.provider_outlook_support import RecordingGraphClient
from tests.providers.openligadb.support import (
    FETCHED_AT,
    nations_league_a_payloads,
)

CALENDAR_ID = "nations-league-a-staging-calendar"


class SnapshotAdapter:
    profile = NATIONS_LEAGUE_A_PROFILE

    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.snapshot = parse_snapshot(
            *nations_league_a_payloads(include_later_stage_fixture=True),
            profile=self.profile,
            fetched_at_utc=FETCHED_AT,
            request_attempts=3,
        )

    def fetch_snapshot(self):
        if self.failure is not None:
            raise self.failure
        return self.snapshot


def create_harness(database_path):
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    sources = DataSourcesRepository(database_path)
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
    service = OpenLigaDBCompetitionService(
        settings=settings,
        adapter=adapter,
        sports_repository=sports,
        competitions_repository=competitions,
        seasons_repository=seasons,
        participants_repository=participants,
        season_participants_repository=memberships,
        data_sources_repository=sources,
        source_mappings_repository=SourceMappingsRepository(database_path),
        profile=NATIONS_LEAGUE_A_PROFILE,
    )
    football = sports.get_by_key("football")
    assert football is not None
    competition = competitions.get_by_key(football.id, "uefa_nations_league")
    assert competition is not None
    season = seasons.get_by_key(competition.id, "2026_27")
    assert season is not None
    job = SourceJobDefinition(
        job_key="openligadb-uefa-nations-league",
        source_key="openligadb",
        role=SourceRole.AUTHORITATIVE,
        scope=SourceScope("football", "uefa_nations_league", "2026_27"),
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


def test_nations_league_a_import_is_idempotent_attributed_and_non_destructive(
    tmp_path,
) -> None:
    provider, calendar, adapter, graph = create_harness(
        tmp_path / "openligadb-nations-league-a.db"
    )

    first_import = provider.import_current_competition()
    first_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert first_import.items_created == 48
    assert first_import.items_cancelled == 0
    assert first_import.items_deleted == 0
    assert first_sync.items_created == 48
    assert len(graph.operations) == 48
    first_payload = graph.operations[0].payload
    assert first_payload is not None
    first_body = first_payload["body"]
    assert isinstance(first_body, Mapping)
    first_content = first_body["content"]
    assert isinstance(first_content, str)
    assert ">league_a_group_phase</td>" in first_content
    assert ">group-a-1</td>" in first_content
    assert OPENLIGADB_ATTRIBUTION in first_content

    assert provider.import_current_competition().items_unchanged == 48
    assert calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 48
    assert len(graph.operations) == 48

    adapter.snapshot = replace(
        adapter.snapshot,
        matches=adapter.snapshot.matches[:-1],
        fetched_at_utc=adapter.snapshot.fetched_at_utc + timedelta(minutes=5),
    )
    missing_import = provider.import_current_competition()
    missing_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert missing_import.items_cancelled == 0
    assert missing_import.items_deleted == 0
    assert missing_sync.items_cancelled == 0
    assert missing_sync.items_deleted == 0
    assert len(graph.operations) == 48


def test_nations_league_a_reschedule_preserves_outlook_identity(tmp_path) -> None:
    provider, calendar, adapter, graph = create_harness(
        tmp_path / "openligadb-nations-league-a-reschedule.db"
    )
    assert provider.import_current_competition().items_created == 48
    assert calendar.synchronize(CALENDAR_ID, 100).items_created == 48

    changed = adapter.snapshot.matches[0]
    adapter.snapshot = replace(
        adapter.snapshot,
        matches=(
            replace(
                changed,
                kickoff_utc=changed.kickoff_utc + timedelta(hours=2),
                source_updated_at=changed.source_updated_at + timedelta(days=1),
            ),
            *adapter.snapshot.matches[1:],
        ),
        fetched_at_utc=adapter.snapshot.fetched_at_utc + timedelta(minutes=5),
    )

    corrected_import = provider.import_current_competition()
    corrected_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert corrected_import.items_updated == 1
    assert corrected_import.items_unchanged == 47
    assert corrected_sync.items_updated == 1
    assert graph.operations[-1].method == "PATCH"


def test_nations_league_a_restart_and_failure_preserve_outlook_state(
    tmp_path,
) -> None:
    database_path = tmp_path / "openligadb-nations-league-a-recovery.db"
    provider, calendar, _, graph = create_harness(database_path)

    assert provider.import_current_competition().items_created == 48
    assert calendar.synchronize(CALENDAR_ID, 100).items_created == 48
    assert len(graph.operations) == 48

    restarted_provider, restarted_calendar, restarted_adapter, restarted_graph = (
        create_harness(database_path)
    )
    assert restarted_provider.import_current_competition().items_unchanged == 48
    assert restarted_calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 48
    assert restarted_graph.operations == []

    restarted_adapter.failure = RuntimeError("simulated provider outage")
    with pytest.raises(
        ProviderImportOrchestrationError,
        match="Provider import failed with RuntimeError",
    ):
        restarted_provider.import_current_competition()

    assert restarted_calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 48
    assert restarted_graph.operations == []

    restarted_adapter.failure = None
    assert restarted_provider.import_current_competition().items_unchanged == 48
    assert restarted_calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 48
    assert restarted_graph.operations == []

    provider_runs = SyncRunsRepository(database_path).get_recent(
        run_type="provider_import"
    )
    assert [run.status for run in provider_runs[:3]] == [
        "completed",
        "failed",
        "completed",
    ]
