import logging
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.database import Database
from app.database.event_participants_repository import (
    EventParticipantsRepository,
)
from app.database.participants_repository import ParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.sports_events_repository import (
    SportsEvent,
    SportsEventsRepository,
)
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.graph.client import GraphClient, OutlookEventReference
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


@dataclass(frozen=True)
class SynchronizationHarness:
    database_path: Path
    event: SportsEvent
    service: SynchronizationRuntimeService
    graph_client: MagicMock
    mappings_repository: CalendarEventMappingsRepository
    sync_runs_repository: SyncRunsRepository


@pytest.fixture
def synchronization_harness(
    tmp_path: Path,
) -> SynchronizationHarness:
    database_path = tmp_path / "integration.db"
    Database(database_path).initialize()

    sports_repository = SportsRepository(database_path)
    competitions_repository = CompetitionsRepository(database_path)
    seasons_repository = SeasonsRepository(database_path)
    participants_repository = ParticipantsRepository(database_path)
    sports_events_repository = SportsEventsRepository(database_path)
    event_participants_repository = EventParticipantsRepository(database_path)

    sport = sports_repository.upsert(
        sport_key="football",
        name="Football",
        icon="football",
    )

    competition = competitions_repository.upsert(
        sport_id=sport.id,
        competition_key="premier-league",
        name="Premier League",
        short_name="PL",
        country_code="GB",
        competition_type="league",
    )

    season = seasons_repository.upsert(
        competition_id=competition.id,
        season_key="2026-27",
        name="2026/27",
        start_date="2026-08-01",
        end_date="2027-05-31",
        is_current=True,
    )

    home_team = participants_repository.upsert(
        sport_id=sport.id,
        participant_key="arsenal",
        participant_type="team",
        name="Arsenal",
        short_name="ARS",
        country_code="GB",
    )

    away_team = participants_repository.upsert(
        sport_id=sport.id,
        participant_key="liverpool",
        participant_type="team",
        name="Liverpool",
        short_name="LIV",
        country_code="GB",
    )

    event = sports_events_repository.upsert(
        sport_id=sport.id,
        competition_id=competition.id,
        season_id=season.id,
        event_key="premier-league-2026-arsenal-liverpool",
        event_type="match",
        title="Arsenal vs Liverpool",
        stage="Regular Season",
        round_name="Matchday 1",
        sequence_number=1,
        start_time="2026-08-15T16:30:00+00:00",
        end_time="2026-08-15T18:30:00+00:00",
        timezone="UTC",
        venue_name="Emirates Stadium",
        city="London",
        country_code="GB",
        status="confirmed",
    )

    event_participants_repository.upsert(
        event_id=event.id,
        participant_id=home_team.id,
        role="home",
        position_number=1,
    )

    event_participants_repository.upsert(
        event_id=event.id,
        participant_id=away_team.id,
        role="away",
        position_number=2,
    )

    mappings_repository = CalendarEventMappingsRepository(database_path)
    sync_runs_repository = SyncRunsRepository(database_path)

    graph_client = MagicMock(spec=GraphClient)
    graph_client.create_event.return_value = OutlookEventReference(id="outlook-event-1")

    event_synchronizer = EventSynchronizer(
        payload_builder=OutlookEventPayloadBuilder(),
        graph_client=graph_client,
        mappings_repository=mappings_repository,
    )

    orchestrator = SynchronizationOrchestrator(
        query_repository=SynchronizationQueryRepository(database_path),
        event_synchronizer=event_synchronizer,
        sync_runs_repository=sync_runs_repository,
    )

    service = SynchronizationRuntimeService(
        orchestrator=orchestrator,
        sync_runs_repository=sync_runs_repository,
        logger=MagicMock(spec=logging.Logger),
    )

    return SynchronizationHarness(
        database_path=database_path,
        event=event,
        service=service,
        graph_client=graph_client,
        mappings_repository=mappings_repository,
        sync_runs_repository=sync_runs_repository,
    )
