import logging
import signal
from threading import Event
from types import FrameType

from app.application.api_football_catalog_service import (
    ApiFootballCatalogService,
    register_api_football_source,
)
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.api_football_fixture_normalization_service import (
    ApiFootballFixtureNormalizationService,
)
from app.application.api_football_import_orchestrator import (
    ApiFootballImportOrchestrator,
)
from app.application.api_football_import_runtime_service import (
    ApiFootballImportRuntimeService,
)
from app.config.settings import Settings, load_settings
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.competitions_catalog import initialize_competitions_catalog
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.database import Database
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.event_results_repository import EventResultsRepository
from app.database.event_statistics_repository import EventStatisticsRepository
from app.database.fixture_import_repository import FixtureImportRepository
from app.database.participants_catalog import initialize_participants_catalog
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_catalog import initialize_seasons_catalog
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_catalog import initialize_sports_catalog
from app.database.sports_events_repository import SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.graph.authentication import GraphTokenProvider
from app.graph.client import GraphClient
from app.logging.logger import configure_logging
from app.providers.api_football.catalog_adapter import ApiFootballCatalogAdapter
from app.providers.api_football.client import ApiFootballClient
from app.providers.api_football.fixture_adapter import ApiFootballFixtureAdapter
from app.providers.api_football.team_mappings import PREMIER_LEAGUE_TEAM_MAPPING
from app.scheduler.scheduler import Scheduler
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayloadBuilder,
)
from app.synchronization.synchronization_orchestrator import (
    SynchronizationOrchestrator,
)
from app.synchronization.synchronization_runtime_service import (
    SynchronizationRuntimeService,
)


class ApplicationContainer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.logger: logging.Logger = configure_logging(
            self.settings.log_level,
            self.settings.instance_name,
        )

        self.database = Database(self.settings.database_path)
        self.sports_repository = SportsRepository(self.settings.database_path)
        self.sports_events_repository = SportsEventsRepository(
            self.settings.database_path
        )
        self.competitions_repository = CompetitionsRepository(
            self.settings.database_path
        )
        self.event_results_repository = EventResultsRepository(
            self.settings.database_path
        )
        self.event_statistics_repository = EventStatisticsRepository(
            self.settings.database_path
        )
        self.calendar_event_mappings_repository = CalendarEventMappingsRepository(
            self.settings.database_path
        )
        self.seasons_repository = SeasonsRepository(self.settings.database_path)
        self.participants_repository = ParticipantsRepository(
            self.settings.database_path
        )
        self.synchronization_query_repository = SynchronizationQueryRepository(
            self.settings.database_path
        )
        self.season_participants_repository = SeasonParticipantsRepository(
            self.settings.database_path
        )
        self.event_participants_repository = EventParticipantsRepository(
            self.settings.database_path
        )
        self.data_sources_repository = DataSourcesRepository(
            self.settings.database_path
        )
        self.source_mappings_repository = SourceMappingsRepository(
            self.settings.database_path
        )
        self.fixture_import_repository = FixtureImportRepository(
            self.settings.database_path
        )
        self.api_football_fixture_import_service = ApiFootballFixtureImportService(
            data_sources_repository=self.data_sources_repository,
            fixture_import_repository=self.fixture_import_repository,
        )
        self.sync_runs_repository = SyncRunsRepository(self.settings.database_path)
        self.graph_token_provider = GraphTokenProvider(
            tenant_id=self.settings.m365_tenant_id,
            client_id=self.settings.m365_client_id,
            client_secret=self.settings.m365_client_secret,
        )
        self.graph_client = GraphClient(
            base_url=self.settings.graph_base_url,
            user_id=self.settings.m365_user_id,
            token_provider=self.graph_token_provider,
        )
        self.api_football_client = (
            ApiFootballClient(settings=self.settings.api_football)
            if self.settings.api_football.enabled
            else None
        )
        self.api_football_catalog_adapter = (
            ApiFootballCatalogAdapter(client=self.api_football_client)
            if self.api_football_client is not None
            else None
        )
        self.api_football_catalog_service = (
            ApiFootballCatalogService(
                settings=self.settings.api_football,
                adapter=self.api_football_catalog_adapter,
                sports_repository=self.sports_repository,
                competitions_repository=self.competitions_repository,
                seasons_repository=self.seasons_repository,
                participants_repository=self.participants_repository,
                season_participants_repository=self.season_participants_repository,
                data_sources_repository=self.data_sources_repository,
                source_mappings_repository=self.source_mappings_repository,
                team_mapping=PREMIER_LEAGUE_TEAM_MAPPING,
            )
            if self.api_football_catalog_adapter is not None
            else None
        )
        self.api_football_fixture_adapter = (
            ApiFootballFixtureAdapter(client=self.api_football_client)
            if self.api_football_client is not None
            else None
        )
        self.api_football_fixture_normalization_service = (
            ApiFootballFixtureNormalizationService(
                adapter=self.api_football_fixture_adapter,
                sports_repository=self.sports_repository,
                competitions_repository=self.competitions_repository,
                seasons_repository=self.seasons_repository,
                participants_repository=self.participants_repository,
                data_sources_repository=self.data_sources_repository,
                source_mappings_repository=self.source_mappings_repository,
            )
            if self.api_football_fixture_adapter is not None
            else None
        )
        catalog_service = self.api_football_catalog_service
        normalization_service = self.api_football_fixture_normalization_service
        self.api_football_import_orchestrator = (
            ApiFootballImportOrchestrator(
                catalog_service=catalog_service,
                normalization_service=normalization_service,
                import_service=self.api_football_fixture_import_service,
                data_sources_repository=self.data_sources_repository,
                sync_runs_repository=self.sync_runs_repository,
            )
            if catalog_service is not None and normalization_service is not None
            else None
        )
        self.api_football_import_runtime_service = (
            ApiFootballImportRuntimeService(
                orchestrator=self.api_football_import_orchestrator,
                sync_runs_repository=self.sync_runs_repository,
                logger=self.logger,
            )
            if self.api_football_import_orchestrator is not None
            else None
        )
        self.outlook_event_payload_builder = OutlookEventPayloadBuilder()
        self.event_synchronizer = EventSynchronizer(
            payload_builder=self.outlook_event_payload_builder,
            graph_client=self.graph_client,
            mappings_repository=self.calendar_event_mappings_repository,
        )
        self.synchronization_orchestrator = SynchronizationOrchestrator(
            query_repository=self.synchronization_query_repository,
            event_synchronizer=self.event_synchronizer,
            sync_runs_repository=self.sync_runs_repository,
        )
        self.synchronization_runtime_service = SynchronizationRuntimeService(
            orchestrator=self.synchronization_orchestrator,
            sync_runs_repository=self.sync_runs_repository,
            logger=self.logger,
        )
        self.scheduler = Scheduler(
            interval_seconds=(
                self.settings.api_football.import_interval_seconds
                if self.settings.api_football.enabled
                else self.settings.heartbeat_interval
            ),
            logger=self.logger,
        )
        self.stop_event = Event()

    def run(self) -> None:
        self._register_signal_handlers()

        self.database.initialize()
        initialize_sports_catalog(self.sports_repository)
        initialize_competitions_catalog(
            repository=self.competitions_repository,
            sports_repository=self.sports_repository,
        )
        initialize_seasons_catalog(
            repository=self.seasons_repository,
            competitions_repository=self.competitions_repository,
            sports_repository=self.sports_repository,
        )
        initialize_participants_catalog(
            repository=self.participants_repository,
            season_participants_repository=self.season_participants_repository,
            sports_repository=self.sports_repository,
            competitions_repository=self.competitions_repository,
            seasons_repository=self.seasons_repository,
        )
        register_api_football_source(
            settings=self.settings.api_football,
            repository=self.data_sources_repository,
        )
        self.database.record_startup()

        self.logger.info(
            "SMART Sports Calendar instance %s started",
            self.settings.instance_name,
        )
        self.logger.info(
            "Database path: %s",
            self.settings.database_path,
        )

        if self.settings.graph_startup_validation_enabled:
            self.graph_token_provider.get_access_token()
            self.logger.info("Microsoft Graph authentication successful")

            calendar = self.graph_client.find_calendar_by_name(
                self.settings.outlook_calendar_name
            )
            if calendar.id != self.settings.outlook_calendar_id:
                raise RuntimeError(
                    "Configured Outlook calendar target does not match the "
                    "calendar resolved by name."
                )
            self.logger.info(
                "Outlook calendar target validated: %s",
                calendar.name,
            )
        else:
            self.logger.info("Microsoft Graph startup validation is disabled")

        self.logger.info(
            "API-Football provider is %s",
            "enabled" if self.api_football_client is not None else "disabled",
        )

        self.scheduler.run(
            task=self._run_scheduled_cycle,
            stop_event=self.stop_event,
        )
        self.logger.info(
            "SMART Sports Calendar instance %s stopped",
            self.settings.instance_name,
        )

    def _register_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(
        self,
        signum: int,
        _frame: FrameType | None,
    ) -> None:
        signal_name = signal.Signals(signum).name
        self.logger.info(
            "Shutdown signal received: %s",
            signal_name,
        )
        self.stop_event.set()

    def _run_synchronization(self) -> None:
        self.synchronization_runtime_service.run(
            calendar_id=self.settings.outlook_calendar_id,
            limit=self.settings.synchronization_batch_limit,
        )

    def _run_scheduled_cycle(self) -> None:
        if self.api_football_import_runtime_service is not None:
            import_result = self.api_football_import_runtime_service.run()
            if import_result is None:
                return
        self._run_synchronization()
