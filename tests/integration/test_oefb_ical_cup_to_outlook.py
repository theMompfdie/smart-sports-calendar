from dataclasses import replace
from datetime import timedelta

import pytest
from app.application.api_football_fixture_import_service import (
    ApiFootballFixtureImportService,
)
from app.application.api_football_import_orchestrator import (
    ProviderImportOrchestrationError,
)
from app.application.oefb_ical_competition_service import (
    OEFB_ICAL_ATTRIBUTION,
    OefbIcalCompetitionService,
    register_oefb_ical_source,
)
from app.application.oefb_ical_import_orchestrator import OefbIcalImportOrchestrator
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
from app.providers.oefb_ical.models import parse_snapshot
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.integration.provider_outlook_support import RecordingGraphClient
from tests.providers.oefb_ical.support import (
    FETCHED_AT,
    LAST_MODIFIED,
    calendar_payload,
    settings,
)

CALENDAR_ID = "oefb-cup-staging-calendar"


def production_payload() -> bytes:
    return (
        calendar_payload()
        .replace(b"X-HOMENR:2000", b"X-HOMENR:1027")
        .replace(b"X-AWAYNR:2001", b"X-AWAYNR:1031")
        .replace(b"Provider Team 2000", b"Wiener Viktoria")
        .replace(b"Provider Team 2001", b"FAC Wien")
    )


class SnapshotAdapter:
    def __init__(self) -> None:
        self.failure: Exception | None = None
        self.snapshot = parse_snapshot(
            production_payload(),
            fetched_at_utc=FETCHED_AT,
            request_attempts=2,
            last_modified=LAST_MODIFIED,
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
    source_mappings = SourceMappingsRepository(database_path)
    runs = SyncRunsRepository(database_path)
    initialize_sports_catalog(sports)
    initialize_competitions_catalog(competitions, sports)
    initialize_seasons_catalog(seasons, competitions, sports)
    initialize_participants_catalog(
        participants, memberships, sports, competitions, seasons
    )
    provider_settings = settings()
    source = register_oefb_ical_source(provider_settings, sources)
    adapter = SnapshotAdapter()
    service = OefbIcalCompetitionService(
        settings=provider_settings,
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
    competition = competitions.get_by_key(football.id, "oefb_cup")
    assert competition is not None
    season = seasons.get_by_key(competition.id, "2026_27")
    assert season is not None
    job = SourceJobDefinition(
        job_key="oefb-ical-oefb-cup",
        source_key="oefb_ical",
        role=SourceRole.AUTHORITATIVE,
        scope=SourceScope("football", "oefb_cup", "2026_27"),
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
    provider = OefbIcalImportOrchestrator(
        competition_service=service,
        import_service=ApiFootballFixtureImportService(
            sources,
            FixtureImportRepository(database_path),
            source_key="oefb_ical",
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


def test_oefb_cup_import_is_idempotent_and_renders_attribution(tmp_path) -> None:
    provider, calendar, adapter, graph = create_harness(tmp_path / "oefb-cup.db")

    first_import = provider.import_current_competition()
    first_sync = calendar.synchronize(CALENDAR_ID, 100)

    assert first_import.items_created == 1
    assert first_import.items_cancelled == 0
    assert first_import.items_deleted == 0
    assert first_sync.items_created == 1
    payload = graph.operations[0].payload
    assert payload is not None
    assert payload["subject"] == "⚽ Wiener Viktoria vs FAC Wien"
    assert payload["categories"] == ["UNIQA ÖFB Cup"]
    body = payload["body"]
    assert isinstance(body, dict)
    assert f"Source: {OEFB_ICAL_ATTRIBUTION}" in body["content"]

    assert provider.import_current_competition().items_unchanged == 1
    assert calendar.synchronize(CALENDAR_ID, 100).items_unchanged == 1
    assert len(graph.operations) == 1

    event = adapter.snapshot.events[0]
    adapter.snapshot = replace(
        adapter.snapshot,
        events=(
            replace(
                event,
                kickoff_utc=event.kickoff_utc + timedelta(hours=2),
                dtstamp_utc=event.dtstamp_utc + timedelta(days=1),
            ),
        ),
        fetched_at_utc=adapter.snapshot.fetched_at_utc + timedelta(minutes=5),
    )

    assert provider.import_current_competition().items_updated == 1
    assert calendar.synchronize(CALENDAR_ID, 100).items_updated == 1
    assert graph.operations[-1].method == "PATCH"


def test_oefb_cup_provider_failure_preserves_outlook_identity(tmp_path) -> None:
    database_path = tmp_path / "oefb-cup-recovery.db"
    provider, calendar, _, graph = create_harness(database_path)
    assert provider.import_current_competition().items_created == 1
    assert calendar.synchronize(CALENDAR_ID, 100).items_created == 1
    assert len(graph.operations) == 1

    restarted_provider, restarted_calendar, restarted_adapter, restarted_graph = (
        create_harness(database_path)
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
