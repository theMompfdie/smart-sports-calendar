import logging
import signal
from functools import partial
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
from app.application.football_data_import_orchestrator import (
    FootballDataImportOrchestrator,
)
from app.application.football_data_import_runtime_service import (
    FootballDataImportRuntimeService,
)
from app.application.football_data_premier_league_service import (
    FootballDataCompetitionService,
    register_football_data_source,
)
from app.application.openligadb_dfb_pokal_service import (
    OpenLigaDBDFBPokalService,
    register_openligadb_source,
)
from app.application.openligadb_import_orchestrator import (
    OpenLigaDBImportOrchestrator,
)
from app.application.openligadb_import_runtime_service import (
    OpenLigaDBImportRuntimeService,
)
from app.application.source_registry import SourceRegistry
from app.config.settings import Settings, load_settings, validate_source_jobs
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
from app.graph.authentication import GraphTokenProvider
from app.graph.client import GraphClient
from app.logging.logger import configure_logging
from app.providers.api_football.catalog_adapter import ApiFootballCatalogAdapter
from app.providers.api_football.client import ApiFootballClient
from app.providers.api_football.fixture_adapter import ApiFootballFixtureAdapter
from app.providers.api_football.team_mappings import PREMIER_LEAGUE_TEAM_MAPPING
from app.providers.contracts import (
    SourceConfigurationError,
    SourceJobDefinition,
    SourceJobTask,
    SourceRole,
)
from app.providers.football_data.adapter import FootballDataCompetitionAdapter
from app.providers.football_data.client import FootballDataClient
from app.providers.football_data.profiles import (
    FootballDataCompetitionProfile,
    get_competition_profile,
)
from app.providers.openligadb.adapter import OpenLigaDBDFBPokalAdapter
from app.providers.openligadb.client import OpenLigaDBClient
from app.scheduler.scheduler import ScheduledJob, Scheduler
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
        validate_source_jobs(list(self.settings.source_jobs))
        active_api_football_jobs = tuple(
            job
            for job in self.settings.source_jobs
            if job.source_key == "api_football" and job.enabled
        )
        if self.settings.api_football.enabled != bool(active_api_football_jobs):
            raise SourceConfigurationError(
                "API_FOOTBALL_ENABLED and the active api_football source job "
                "must be configured together."
            )
        if active_api_football_jobs and (
            len(active_api_football_jobs) != 1
            or active_api_football_jobs[0].scope.sport_key != "football"
            or active_api_football_jobs[0].scope.competition_key != "premier_league"
            or active_api_football_jobs[0].scope.season_key != "2026_27"
        ):
            raise SourceConfigurationError(
                "The current API-Football adapter supports exactly the "
                "football/premier_league/2026_27 scope."
            )
        active_football_data_jobs = tuple(
            job
            for job in self.settings.source_jobs
            if job.source_key == "football_data" and job.enabled
        )
        if self.settings.football_data.enabled != bool(active_football_data_jobs):
            raise SourceConfigurationError(
                "FOOTBALL_DATA_ENABLED and the active football_data source job "
                "must be configured together."
            )
        football_data_profiles: dict[str, FootballDataCompetitionProfile] = {}
        for job in active_football_data_jobs:
            profile = get_competition_profile(
                job.scope.competition_key,
                job.scope.season_key,
            )
            if (
                job.scope.sport_key != "football"
                or profile is None
                or job.role is not SourceRole.AUTHORITATIVE
            ):
                raise SourceConfigurationError(
                    "The football-data.org adapter requires a supported "
                    "authoritative football competition profile."
                )
            football_data_profiles[job.job_key] = profile
        active_openligadb_jobs = tuple(
            job
            for job in self.settings.source_jobs
            if job.source_key == "openligadb" and job.enabled
        )
        if self.settings.openligadb.enabled != bool(active_openligadb_jobs):
            raise SourceConfigurationError(
                "OPENLIGADB_ENABLED and the active openligadb source job must "
                "be configured together."
            )
        if active_openligadb_jobs and (
            len(active_openligadb_jobs) != 1
            or active_openligadb_jobs[0].scope.sport_key != "football"
            or active_openligadb_jobs[0].scope.competition_key != "dfb_pokal"
            or active_openligadb_jobs[0].scope.season_key != "2026_27"
            or active_openligadb_jobs[0].role is not SourceRole.AUTHORITATIVE
        ):
            raise SourceConfigurationError(
                "The OpenLigaDB adapter supports exactly the authoritative "
                "football/dfb_pokal/2026_27 scope."
            )
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
        self.source_assignments_repository = SourceAssignmentsRepository(
            self.settings.database_path
        )
        self.fixture_import_repository = FixtureImportRepository(
            self.settings.database_path
        )
        self.api_football_fixture_import_service = ApiFootballFixtureImportService(
            data_sources_repository=self.data_sources_repository,
            fixture_import_repository=self.fixture_import_repository,
        )
        self.football_data_fixture_import_service = ApiFootballFixtureImportService(
            data_sources_repository=self.data_sources_repository,
            fixture_import_repository=self.fixture_import_repository,
            source_key="football_data",
        )
        self.openligadb_fixture_import_service = ApiFootballFixtureImportService(
            data_sources_repository=self.data_sources_repository,
            fixture_import_repository=self.fixture_import_repository,
            source_key="openligadb",
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
        self.football_data_client = (
            FootballDataClient(settings=self.settings.football_data)
            if self.settings.football_data.enabled
            else None
        )
        self.openligadb_client = (
            OpenLigaDBClient(settings=self.settings.openligadb)
            if self.settings.openligadb.enabled
            else None
        )
        self.openligadb_adapter = (
            OpenLigaDBDFBPokalAdapter(self.openligadb_client)
            if self.openligadb_client is not None
            else None
        )
        self.openligadb_competition_service = (
            OpenLigaDBDFBPokalService(
                settings=self.settings.openligadb,
                adapter=self.openligadb_adapter,
                sports_repository=self.sports_repository,
                competitions_repository=self.competitions_repository,
                seasons_repository=self.seasons_repository,
                participants_repository=self.participants_repository,
                season_participants_repository=self.season_participants_repository,
                data_sources_repository=self.data_sources_repository,
                source_mappings_repository=self.source_mappings_repository,
            )
            if self.openligadb_adapter is not None
            else None
        )
        self.football_data_adapters = {
            job.job_key: FootballDataCompetitionAdapter(
                self.football_data_client,
                football_data_profiles[job.job_key],
            )
            for job in active_football_data_jobs
            if self.football_data_client is not None
        }
        self.football_data_competition_services = {
            job.job_key: FootballDataCompetitionService(
                settings=self.settings.football_data,
                adapter=self.football_data_adapters[job.job_key],
                sports_repository=self.sports_repository,
                competitions_repository=self.competitions_repository,
                seasons_repository=self.seasons_repository,
                participants_repository=self.participants_repository,
                season_participants_repository=self.season_participants_repository,
                data_sources_repository=self.data_sources_repository,
                source_mappings_repository=self.source_mappings_repository,
                profile=self.football_data_adapters[job.job_key].profile,
            )
            for job in active_football_data_jobs
        }
        premier_league_job_key = next(
            (
                job.job_key
                for job in active_football_data_jobs
                if job.scope.competition_key == "premier_league"
            ),
            None,
        )
        self.football_data_adapter = (
            self.football_data_adapters.get(premier_league_job_key)
            if premier_league_job_key is not None
            else None
        )
        self.football_data_premier_league_service = (
            self.football_data_competition_services.get(premier_league_job_key)
            if premier_league_job_key is not None
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
                job_definition=next(
                    (
                        job
                        for job in self.settings.source_jobs
                        if job.source_key == "api_football" and job.enabled
                    ),
                    None,
                ),
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
        self.football_data_import_orchestrators = {
            job.job_key: FootballDataImportOrchestrator(
                competition_service=self.football_data_competition_services[
                    job.job_key
                ],
                import_service=self.football_data_fixture_import_service,
                sync_runs_repository=self.sync_runs_repository,
                data_sources_repository=self.data_sources_repository,
                job_definition=job,
            )
            for job in active_football_data_jobs
        }
        self.football_data_import_runtime_services = {
            job_key: FootballDataImportRuntimeService(
                orchestrator=orchestrator,
                sync_runs_repository=self.sync_runs_repository,
                logger=self.logger,
            )
            for job_key, orchestrator in self.football_data_import_orchestrators.items()
        }
        self.football_data_import_orchestrator = next(
            iter(self.football_data_import_orchestrators.values()), None
        )
        self.football_data_import_runtime_service = next(
            iter(self.football_data_import_runtime_services.values()), None
        )
        openligadb_job = next(iter(active_openligadb_jobs), None)
        self.openligadb_import_orchestrator = (
            OpenLigaDBImportOrchestrator(
                competition_service=self.openligadb_competition_service,
                import_service=self.openligadb_fixture_import_service,
                sync_runs_repository=self.sync_runs_repository,
                data_sources_repository=self.data_sources_repository,
                job_definition=openligadb_job,
            )
            if self.openligadb_competition_service is not None
            and openligadb_job is not None
            else None
        )
        self.openligadb_import_runtime_service = (
            OpenLigaDBImportRuntimeService(
                orchestrator=self.openligadb_import_orchestrator,
                sync_runs_repository=self.sync_runs_repository,
                logger=self.logger,
            )
            if self.openligadb_import_orchestrator is not None
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
        self.source_registry = SourceRegistry()
        if self.api_football_import_runtime_service is not None:
            self.source_registry.register(
                "api_football",
                self._run_api_football_source_job,
                supported_roles=frozenset({SourceRole.AUTHORITATIVE}),
                writes_canonical=True,
            )
        if self.football_data_import_runtime_services:
            self.source_registry.register(
                "football_data",
                task_factory=self._build_football_data_source_task,
                supported_roles=frozenset({SourceRole.AUTHORITATIVE}),
                writes_canonical=True,
            )
        if self.openligadb_import_runtime_service is not None:
            self.source_registry.register(
                "openligadb",
                self._run_openligadb_source_job,
                supported_roles=frozenset({SourceRole.AUTHORITATIVE}),
                writes_canonical=True,
            )
        self.source_scheduled_jobs = self.source_registry.build_scheduled_jobs(
            self.settings.source_jobs
        )
        self.scheduled_jobs = (
            *self.source_scheduled_jobs,
            ScheduledJob(
                job_key="system:calendar-synchronization",
                interval_seconds=self.settings.heartbeat_interval,
                task=self._run_synchronization,
            ),
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
        if self.settings.football_data.enabled:
            register_football_data_source(
                settings=self.settings.football_data,
                repository=self.data_sources_repository,
            )
        if self.settings.openligadb.enabled:
            register_openligadb_source(
                settings=self.settings.openligadb,
                repository=self.data_sources_repository,
            )
        self._persist_source_assignments()
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
        self.logger.info(
            "football-data.org provider is %s",
            "enabled" if self.football_data_client is not None else "disabled",
        )
        self.logger.info(
            "OpenLigaDB provider is %s",
            "enabled" if self.openligadb_client is not None else "disabled",
        )

        if self.settings.source_jobs:
            self.scheduler.run_jobs(
                jobs=self.scheduled_jobs,
                stop_event=self.stop_event,
            )
        else:
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

    def _run_api_football_source_job(self) -> object | None:
        runtime = self.api_football_import_runtime_service
        if runtime is None:
            raise SourceConfigurationError(
                "API-Football source job has no configured runtime."
            )
        return runtime.run()

    def _build_football_data_source_task(
        self,
        definition: SourceJobDefinition,
    ) -> SourceJobTask:
        return partial(self._run_football_data_source_job, definition.job_key)

    def _run_football_data_source_job(self, job_key: str) -> object | None:
        runtime = self.football_data_import_runtime_services.get(job_key)
        if runtime is None:
            raise SourceConfigurationError(
                f"football-data.org source job has no configured runtime: {job_key}."
            )
        return runtime.run()

    def _run_openligadb_source_job(self) -> object | None:
        runtime = self.openligadb_import_runtime_service
        if runtime is None:
            raise SourceConfigurationError(
                "OpenLigaDB source job has no configured runtime."
            )
        return runtime.run()

    def _persist_source_assignments(self) -> None:
        assignments: list[SourceAssignmentWrite] = []
        for job in self.settings.source_jobs:
            source = self.data_sources_repository.get_by_key(job.source_key)
            sport = self.sports_repository.get_by_key(job.scope.sport_key)
            if source is None and not job.enabled:
                continue
            if source is None or sport is None:
                raise SourceConfigurationError(
                    f"Source job cannot resolve source or sport: {job.job_key}."
                )
            competition = self.competitions_repository.get_by_key(
                sport_id=sport.id,
                competition_key=job.scope.competition_key,
            )
            if competition is None:
                raise SourceConfigurationError(
                    f"Source job cannot resolve competition: {job.job_key}."
                )
            season = self.seasons_repository.get_by_key(
                competition_id=competition.id,
                season_key=job.scope.season_key,
            )
            if season is None:
                raise SourceConfigurationError(
                    f"Source job cannot resolve season: {job.job_key}."
                )
            assignments.append(
                SourceAssignmentWrite(
                    job_key=job.job_key,
                    source_id=source.id,
                    competition_id=competition.id,
                    season_id=season.id,
                    role=job.role,
                    interval_seconds=job.interval_seconds,
                )
            )
        self.source_assignments_repository.synchronize(tuple(assignments))
