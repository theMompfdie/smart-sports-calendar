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
from app.domain.competition_lifecycle import (
    CompetitionLifecycleScope,
    FixtureObservationScopeKind,
)
from app.providers.contracts import SourceJobDefinition, SourceRole, SourceScope
from app.providers.football_data.profiles import PREMIER_LEAGUE_PROFILE
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.integration.provider_outlook_support import (
    CapturedGraphOperation,
    RecordingGraphClient,
)
from tests.providers.football_data.support import snapshot

CALENDAR_ID = "staging-calendar"


class SnapshotAdapter:
    def __init__(self) -> None:
        self.profile = PREMIER_LEAGUE_PROFILE
        self.snapshot = snapshot()

    def fetch_snapshot(self, season_year: int):
        assert season_year == 2026
        return self.snapshot


def graph_body_content(operation: CapturedGraphOperation) -> str:
    payload = operation.payload
    assert payload is not None
    body = payload["body"]
    assert isinstance(body, dict)
    content = body["content"]
    assert isinstance(content, str)
    return content


def create_harness(database_path, *, persist_source_assignment: bool = True):
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
    football_data_source = register_football_data_source(settings, sources)

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
        adapter=adapter,
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
                lifecycle=CompetitionLifecycleScope(
                    competition_format=batch.competition_format,
                    scope_kind=FixtureObservationScopeKind.PARTIAL,
                ),
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
    if persist_source_assignment:
        SourceAssignmentsRepository(database_path).synchronize(
            (
                SourceAssignmentWrite(
                    job_key=job.job_key,
                    source_id=football_data_source.id,
                    competition_id=batch.competition_id,
                    season_id=batch.season_id,
                    role=job.role,
                    interval_seconds=job.interval_seconds,
                ),
            )
        )
    provider = FootballDataImportOrchestrator(
        competition_service=service,
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


def test_adding_authoritative_attribution_updates_existing_event_once(tmp_path) -> None:
    database_path = tmp_path / "attribution-upgrade.db"
    (
        _,
        calendar,
        _,
        graph,
        sources,
        _,
        _,
        api_fixture_mapping,
    ) = create_harness(database_path, persist_source_assignment=False)

    first_sync = calendar.synchronize(CALENDAR_ID, 100)
    mappings = CalendarEventMappingsRepository(database_path)
    first_mapping = mappings.get_by_event(api_fixture_mapping.event_id, CALENDAR_ID)
    assert first_mapping is not None
    assert first_sync.items_created == 1
    assert "Football data provided" not in graph_body_content(graph.operations[-1])

    event = SportsEventsRepository(database_path).get_by_id(
        api_fixture_mapping.event_id
    )
    source = sources.get_by_key("football_data")
    assert event is not None
    assert event.competition_id is not None
    assert event.season_id is not None
    assert source is not None
    SourceAssignmentsRepository(database_path).synchronize(
        (
            SourceAssignmentWrite(
                job_key="football-data-premier-league",
                source_id=source.id,
                competition_id=event.competition_id,
                season_id=event.season_id,
                role=SourceRole.AUTHORITATIVE,
                interval_seconds=3600,
            ),
        )
    )

    attribution_sync = calendar.synchronize(CALENDAR_ID, 100)
    attributed_mapping = mappings.get_by_event(
        api_fixture_mapping.event_id,
        CALENDAR_ID,
    )
    unchanged_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert attribution_sync.items_updated == 1
    assert unchanged_sync.items_unchanged == 1
    assert [operation.method for operation in graph.operations] == ["POST", "PATCH"]
    assert attributed_mapping is not None
    assert attributed_mapping.transaction_id == first_mapping.transaction_id
    assert "Football data provided by the Football-Data.org API" in graph_body_content(
        graph.operations[-1]
    )


def test_complete_snapshot_is_idempotent_and_kickoff_correction_updates_graph(
    tmp_path,
) -> None:
    database_path = tmp_path / "football-data.db"
    (
        provider,
        calendar,
        adapter,
        graph,
        sources,
        mappings,
        api_mapping,
        api_fixture_mapping,
    ) = create_harness(database_path)

    first_import = provider.import_current_premier_league()
    first_sync_batches = tuple(calendar.synchronize(CALENDAR_ID, 100) for _ in range(4))
    first_operation_count = len(graph.operations)

    assert first_import.items_created == 379
    assert first_import.items_unchanged == 1
    assert [batch.items_created for batch in first_sync_batches] == [100, 100, 100, 80]
    assert all(batch.items_failed == 0 for batch in first_sync_batches)
    assert first_operation_count == 380
    assert all(
        operation.payload is not None and "end" in operation.payload
        for operation in graph.operations
    )
    assert all(
        operation.payload is not None
        and "Football data provided by the Football-Data.org API"
        in graph_body_content(operation)
        for operation in graph.operations
    )

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
    canonical_event = SportsEventsRepository(database_path).get_by_id(
        football_data_fixture_mapping.internal_id
    )
    assert canonical_event is not None
    assert canonical_event.end_time is None
