from dataclasses import replace
from datetime import timedelta

from app.application.api_football_catalog_service import register_api_football_source
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
    FixtureImportScope,
)
from app.application.football_data_import_orchestrator import (
    FootballDataImportOrchestrator,
)
from app.application.football_data_premier_league_service import (
    FootballDataPremierLeagueService,
    register_football_data_source,
)
from app.config.settings import ApiFootballSettings, FootballDataSettings
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
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.providers.contracts import SourceJobDefinition, SourceRole, SourceScope
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.integration.provider_outlook_support import RecordingGraphClient
from tests.providers.football_data.support import snapshot

CALENDAR_ID = "staging-calendar"


class SnapshotAdapter:
    def __init__(self) -> None:
        self.snapshot = snapshot()

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
    register_football_data_source(settings, sources)

    api_source = register_api_football_source(
        ApiFootballSettings(enabled=False, api_key=""), sources
    )
    football = sports.get_by_key("football")
    assert football is not None
    arsenal = participants.get_by_key(football.id, "arsenal")
    assert arsenal is not None
    api_mapping = mappings.upsert(
        source_id=api_source.id,
        object_type="participant",
        internal_id=arsenal.id,
        external_id="42",
        metadata={"provider_name": "Arsenal"},
    )

    adapter = SnapshotAdapter()
    service = FootballDataPremierLeagueService(
        settings=settings,
        adapter=adapter,  # type: ignore[arg-type]
        sports_repository=sports,
        competitions_repository=competitions,
        seasons_repository=seasons,
        participants_repository=participants,
        season_participants_repository=memberships,
        data_sources_repository=sources,
        source_mappings_repository=mappings,
    )
    batch = service.fetch_normalized_snapshot()
    api_fixture_mapping = (
        ApiFootballFixtureImportService(sources, FixtureImportRepository(database_path))
        .import_fixtures(
            (batch.fixtures[0],),
            FixtureImportScope(
                competition_id=batch.competition_id,
                season_id=batch.season_id,
                observation_id="existing-api-football-event",
                observed_at_utc=batch.fetched_at_utc,
                authoritative=False,
            ),
        )
        .items[0]
    )
    job = SourceJobDefinition(
        job_key="football-data-premier-league",
        source_key="football_data",
        role=SourceRole.AUTHORITATIVE,
        scope=SourceScope("football", "premier_league", "2026_27"),
        interval_seconds=3600,
    )
    provider = FootballDataImportOrchestrator(
        premier_league_service=service,
        import_service=ApiFootballFixtureImportService(
            sources,
            FixtureImportRepository(database_path),
            source_key="football_data",
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
    return (
        provider,
        calendar,
        adapter,
        graph,
        sources,
        mappings,
        api_mapping,
        api_fixture_mapping,
    )


def test_complete_snapshot_is_idempotent_and_kickoff_correction_updates_graph(
    tmp_path,
) -> None:
    (
        provider,
        calendar,
        adapter,
        graph,
        sources,
        mappings,
        api_mapping,
        api_fixture_mapping,
    ) = create_harness(tmp_path / "football-data.db")

    first_import = provider.import_current_premier_league()
    first_sync = calendar.synchronize(CALENDAR_ID, 500)
    first_operation_count = len(graph.operations)

    assert first_import.items_created == 379
    assert first_import.items_unchanged == 1
    assert first_sync.items_created == 380
    assert first_operation_count == 380

    second_import = provider.import_current_premier_league()
    second_sync = calendar.synchronize(CALENDAR_ID, 500)

    assert second_import.items_unchanged == 380
    assert second_sync.items_unchanged == 380
    assert len(graph.operations) == first_operation_count

    original_match = adapter.snapshot.matches[0]
    corrected_match = replace(
        original_match,
        kickoff_utc=original_match.kickoff_utc + timedelta(hours=2),
        source_updated_at=original_match.source_updated_at + timedelta(days=1),
    )
    adapter.snapshot = replace(
        adapter.snapshot,
        matches=(corrected_match, *adapter.snapshot.matches[1:]),
        fetched_at_utc=adapter.snapshot.fetched_at_utc + timedelta(minutes=1),
    )

    corrected_import = provider.import_current_premier_league()
    corrected_sync = calendar.synchronize(CALENDAR_ID, 500)

    assert corrected_import.items_updated == 1
    assert corrected_import.items_unchanged == 379
    assert corrected_sync.items_updated == 1
    assert graph.operations[-1].method == "PATCH"

    api_source = sources.get_by_key("api_football")
    football_data_source = sources.get_by_key("football_data")
    assert api_source is not None
    assert football_data_source is not None
    assert (
        mappings.get_by_external_id(api_source.id, "participant", "42") == api_mapping
    )
    football_data_fixture_mapping = mappings.get_by_external_id(
        football_data_source.id, "event", "1000"
    )
    assert football_data_fixture_mapping is not None
    assert football_data_fixture_mapping.internal_id == api_fixture_mapping.event_id
