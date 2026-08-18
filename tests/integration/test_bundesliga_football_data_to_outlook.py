from dataclasses import replace
from datetime import timedelta

from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.football_data_import_orchestrator import (
    FootballDataImportOrchestrator,
)
from app.application.football_data_premier_league_service import (
    FootballDataCompetitionService,
    register_football_data_source,
)
from app.config.settings import FootballDataSettings
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
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.providers.contracts import SourceJobDefinition, SourceRole, SourceScope
from app.providers.football_data.profiles import (
    BUNDESLIGA_PROFILE,
    PREMIER_LEAGUE_PROFILE,
    FootballDataCompetitionProfile,
)
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.integration.provider_outlook_support import RecordingGraphClient
from tests.providers.football_data.support import snapshot

CALENDAR_ID = "bundesliga-staging-calendar"


class SnapshotAdapter:
    def __init__(self, profile: FootballDataCompetitionProfile) -> None:
        self.profile = profile
        self.snapshot = snapshot(profile)

    def fetch_snapshot(self, season_year: int):
        assert season_year == 2026
        return self.snapshot


def create_harness(database_path):
    Database(database_path).initialize()
    sports = SportsRepository(database_path)
    competitions = CompetitionsRepository(database_path)
    seasons = SeasonsRepository(database_path)
    participants = ParticipantsRepository(database_path)
    memberships = SeasonParticipantsRepository(database_path)
    sources = DataSourcesRepository(database_path)
    mappings = SourceMappingsRepository(database_path)
    runs = SyncRunsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )

    settings = FootballDataSettings(enabled=True, api_key="test-token")
    source = register_football_data_source(settings, sources)
    adapters = {
        profile.competition_key: SnapshotAdapter(profile)
        for profile in (PREMIER_LEAGUE_PROFILE, BUNDESLIGA_PROFILE)
    }
    services = {
        profile.competition_key: FootballDataCompetitionService(
            settings=settings,
            adapter=adapters[profile.competition_key],
            sports_repository=sports,
            competitions_repository=competitions,
            seasons_repository=seasons,
            participants_repository=participants,
            season_participants_repository=memberships,
            data_sources_repository=sources,
            source_mappings_repository=mappings,
            profile=profile,
        )
        for profile in (PREMIER_LEAGUE_PROFILE, BUNDESLIGA_PROFILE)
    }
    batches = {
        competition_key: service.fetch_normalized_snapshot()
        for competition_key, service in services.items()
    }
    jobs = {
        competition_key: SourceJobDefinition(
            job_key=f"football-data-{competition_key.replace('_', '-')}",
            source_key="football_data",
            role=SourceRole.AUTHORITATIVE,
            scope=SourceScope("football", competition_key, "2026_27"),
            interval_seconds=21600,
        )
        for competition_key in services
    }
    SourceAssignmentsRepository(database_path).synchronize(
        tuple(
            SourceAssignmentWrite(
                job_key=job.job_key,
                source_id=source.id,
                competition_id=batches[competition_key].competition_id,
                season_id=batches[competition_key].season_id,
                role=job.role,
                interval_seconds=job.interval_seconds,
            )
            for competition_key, job in jobs.items()
        )
    )
    providers = {
        competition_key: FootballDataImportOrchestrator(
            competition_service=service,
            import_service=ApiFootballFixtureImportService(
                sources,
                FixtureImportRepository(database_path),
                source_key="football_data",
            ),
            sync_runs_repository=runs,
            data_sources_repository=sources,
            job_definition=jobs[competition_key],
        )
        for competition_key, service in services.items()
    }
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
    return providers, calendar, adapters, graph, source, mappings


def test_bundesliga_snapshot_is_idempotent_and_updates_existing_outlook_event(
    tmp_path,
) -> None:
    database_path = tmp_path / "bundesliga-football-data.db"
    providers, calendar, adapters, graph, source, mappings = create_harness(
        database_path
    )
    provider = providers["bundesliga"]
    adapter = adapters["bundesliga"]

    first_import = provider.import_current_competition()
    first_sync_batches = tuple(calendar.synchronize(CALENDAR_ID, 100) for _ in range(4))
    first_operation_count = len(graph.operations)

    assert first_import.items_created == 306
    assert [batch.items_created for batch in first_sync_batches] == [100, 100, 100, 6]
    assert all(batch.items_failed == 0 for batch in first_sync_batches)
    assert first_operation_count == 306
    assert all(operation.method == "POST" for operation in graph.operations)

    second_import = provider.import_current_competition()
    second_sync = calendar.synchronize(CALENDAR_ID, 500)

    assert second_import.items_unchanged == 306
    assert second_sync.items_unchanged == 306
    assert len(graph.operations) == first_operation_count

    original_match = adapter.snapshot.matches[0]
    adapter.snapshot = replace(
        adapter.snapshot,
        matches=(
            replace(
                original_match,
                kickoff_utc=original_match.kickoff_utc + timedelta(hours=2),
                source_updated_at=original_match.source_updated_at + timedelta(days=1),
            ),
            *adapter.snapshot.matches[1:],
        ),
        fetched_at_utc=adapter.snapshot.fetched_at_utc + timedelta(minutes=1),
    )

    corrected_import = provider.import_current_competition()
    corrected_sync = calendar.synchronize(CALENDAR_ID, 500)

    assert corrected_import.items_updated == 1
    assert corrected_import.items_unchanged == 305
    assert corrected_sync.items_updated == 1
    assert len(graph.operations) == first_operation_count + 1
    assert graph.operations[-1].method == "PATCH"

    fixture_mapping = mappings.get_by_external_id(source.id, "event", "2000")
    assert fixture_mapping is not None
    canonical_event = SportsEventsRepository(database_path).get_by_id(
        fixture_mapping.internal_id
    )
    assert canonical_event is not None
    assert canonical_event.title
    assert canonical_event.end_time is None


def test_premier_league_and_bundesliga_share_sqlite_without_identity_collisions(
    tmp_path,
) -> None:
    database_path = tmp_path / "multi-competition-football-data.db"
    providers, calendar, _, graph, source, mappings = create_harness(database_path)

    premier_league_import = providers["premier_league"].import_current_competition()
    bundesliga_import = providers["bundesliga"].import_current_competition()
    sync_batches = tuple(calendar.synchronize(CALENDAR_ID, 100) for _ in range(7))

    assert premier_league_import.items_created == 380
    assert bundesliga_import.items_created == 306
    assert [batch.items_created for batch in sync_batches] == [
        100,
        100,
        100,
        100,
        100,
        100,
        86,
    ]
    assert len(graph.operations) == 686

    premier_league_mapping = mappings.get_by_external_id(source.id, "event", "1000")
    bundesliga_mapping = mappings.get_by_external_id(source.id, "event", "2000")
    assert premier_league_mapping is not None
    assert bundesliga_mapping is not None
    assert premier_league_mapping.internal_id != bundesliga_mapping.internal_id

    events = SportsEventsRepository(database_path)
    premier_league_event = events.get_by_id(premier_league_mapping.internal_id)
    bundesliga_event = events.get_by_id(bundesliga_mapping.internal_id)
    assert premier_league_event is not None
    assert bundesliga_event is not None
    assert premier_league_event.competition_id != bundesliga_event.competition_id

    premier_league_team = mappings.get_by_external_id(source.id, "participant", "101")
    bundesliga_team = mappings.get_by_external_id(source.id, "participant", "1001")
    assert premier_league_team is not None
    assert bundesliga_team is not None
    assert premier_league_team.internal_id != bundesliga_team.internal_id

    assert (
        providers["premier_league"].import_current_competition().items_unchanged == 380
    )
    assert providers["bundesliga"].import_current_competition().items_unchanged == 306
    unchanged_sync = calendar.synchronize(CALENDAR_ID, 700)
    assert unchanged_sync.items_unchanged == 686
    assert len(graph.operations) == 686
