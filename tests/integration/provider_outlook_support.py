import json
import logging
import sqlite3
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

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
    ProviderImportRunResult,
)
from app.application.api_football_import_runtime_service import (
    ApiFootballImportRuntimeService,
)
from app.config.settings import ApiFootballSettings
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.competitions_repository import CompetitionsRepository
from app.database.data_sources_repository import DataSourcesRepository
from app.database.event_participants_repository import EventParticipantsRepository
from app.database.fixture_import_repository import FixtureImportRepository
from app.database.participants_repository import ParticipantsRepository
from app.database.season_participants_repository import SeasonParticipantsRepository
from app.database.seasons_repository import SeasonsRepository
from app.database.source_mappings_repository import SourceMappingsRepository
from app.database.sports_events_repository import SportsEvent, SportsEventsRepository
from app.database.sports_repository import SportsRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import (
    SynchronizationQueryRepository,
)
from app.graph.client import GraphClientError, OutlookEventReference
from app.providers.api_football.catalog_adapter import ApiFootballCatalogAdapter
from app.providers.api_football.client import ApiFootballClient
from app.providers.api_football.fixture_adapter import ApiFootballFixtureAdapter
from app.providers.api_football.team_mappings import PREMIER_LEAGUE_TEAM_MAPPING
from app.providers.api_football.transport import HttpResponse
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayload,
    OutlookEventPayloadBuilder,
)
from app.synchronization.synchronization_orchestrator import (
    SynchronizationOrchestrator,
    SynchronizationRunResult,
)
from app.synchronization.synchronization_runtime_service import (
    SynchronizationRuntimeService,
)

from tests.catalog_support import CatalogInitializer

FIXTURE_DIRECTORY = Path(__file__).parents[1] / "fixtures" / "api_football"
CALENDAR_ID = "smart-sports-calendar-e2e"
PROVIDER_SECRET = "phase-47-provider-secret"


def _load_envelope(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIRECTORY / name).read_text(encoding="utf-8"))


LEAGUE_ITEMS = _load_envelope("premier_league.json")["response"]
TEAM_ITEMS = _load_envelope("premier_league_teams.json")["response"]
BASE_FIXTURE_ITEMS = _load_envelope("premier_league_fixtures.json")["response"]


def fixture_payload(external_id: int) -> dict[str, Any]:
    return deepcopy(
        next(
            item for item in BASE_FIXTURE_ITEMS if item["fixture"]["id"] == external_id
        )
    )


def update_fixture_payload(
    payload: dict[str, Any],
    *,
    kickoff_utc: datetime | None = None,
    status_code: str | None = None,
    status_reason: str | None = None,
    updated_at_utc: datetime | None = None,
) -> dict[str, Any]:
    updated = deepcopy(payload)
    fixture = updated["fixture"]
    if kickoff_utc is not None:
        kickoff = kickoff_utc.astimezone(UTC)
        fixture["date"] = kickoff.isoformat()
        fixture["timestamp"] = int(kickoff.timestamp())
    if status_code is not None:
        fixture["status"] = {
            "short": status_code,
            "long": status_reason or status_code,
        }
    if updated_at_utc is not None:
        fixture["updated"] = updated_at_utc.astimezone(UTC).isoformat()
    return updated


@dataclass(frozen=True)
class CapturedProviderRequest:
    path: str
    query: tuple[tuple[str, str], ...]
    header_names: tuple[str, ...]


class ScriptedApiFootballTransport:
    def __init__(self) -> None:
        self.fixture_items: list[dict[str, Any]] = []
        self.fixture_page_size = 100
        self.requests: list[CapturedProviderRequest] = []
        self._fixture_failures: dict[int, list[HttpResponse | Exception]] = {}

    def set_fixtures(
        self,
        items: list[dict[str, Any]],
        *,
        page_size: int = 100,
    ) -> None:
        self.fixture_items = deepcopy(items)
        self.fixture_page_size = page_size

    def fail_fixture_page(
        self,
        page: int,
        failures: list[HttpResponse | Exception],
    ) -> None:
        self._fixture_failures[page] = list(failures)

    def clear_failures(self) -> None:
        self._fixture_failures.clear()

    def get(
        self,
        url: str,
        headers: Mapping[str, str],
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> HttpResponse:
        del connect_timeout_seconds, read_timeout_seconds
        parsed = urlsplit(url)
        query = dict(parse_qsl(parsed.query))
        self.requests.append(
            CapturedProviderRequest(
                path=parsed.path,
                query=tuple(sorted(query.items())),
                header_names=tuple(sorted(name.casefold() for name in headers)),
            )
        )
        if parsed.path == "/fixtures":
            page = int(query["page"])
            failures = self._fixture_failures.get(page)
            if failures:
                failure = failures.pop(0)
                if isinstance(failure, Exception):
                    raise failure
                return failure
            return self._fixture_response(page)
        if parsed.path == "/leagues":
            return self._success_response(LEAGUE_ITEMS, page=1, total=1)
        if parsed.path == "/teams":
            return self._success_response(TEAM_ITEMS, page=1, total=1)
        return HttpResponse(status=404, headers={}, body=b"")

    def _fixture_response(self, page: int) -> HttpResponse:
        total_pages = max(
            1,
            (len(self.fixture_items) + self.fixture_page_size - 1)
            // self.fixture_page_size,
        )
        start = (page - 1) * self.fixture_page_size
        items = self.fixture_items[start : start + self.fixture_page_size]
        return self._success_response(items, page=page, total=total_pages)

    @staticmethod
    def _success_response(
        items: list[dict[str, Any]],
        *,
        page: int,
        total: int,
    ) -> HttpResponse:
        body = json.dumps(
            {
                "errors": [],
                "results": len(items),
                "paging": {"current": page, "total": total},
                "response": items,
            },
            separators=(",", ":"),
        ).encode()
        return HttpResponse(
            status=200,
            headers={
                "x-ratelimit-requests-limit": "7500",
                "x-ratelimit-requests-remaining": "7490",
                "x-ratelimit-limit": "300",
                "x-ratelimit-remaining": "295",
            },
            body=body,
        )


@dataclass(frozen=True)
class CapturedGraphOperation:
    method: str
    calendar_id: str
    event_id: str | None
    transaction_id: str | None
    payload: dict[str, object] | None


class RecordingGraphClient:
    def __init__(self) -> None:
        self.operations: list[CapturedGraphOperation] = []
        self.events: dict[str, dict[str, object]] = {}
        self._transaction_events: dict[str, str] = {}
        self.create_failure: Exception | None = None
        self.update_failure: Exception | None = None
        self.delete_failure: Exception | None = None

    def create_event(
        self,
        calendar_id: str,
        payload: OutlookEventPayload,
        transaction_id: str,
    ) -> OutlookEventReference:
        graph_payload = payload.to_graph_dict()
        self.operations.append(
            CapturedGraphOperation(
                method="POST",
                calendar_id=calendar_id,
                event_id=None,
                transaction_id=transaction_id,
                payload=graph_payload,
            )
        )
        if self.create_failure is not None:
            error = self.create_failure
            self.create_failure = None
            raise error
        event_id = self._transaction_events.setdefault(
            transaction_id,
            f"outlook-event-{len(self._transaction_events) + 1}",
        )
        self.events[event_id] = graph_payload
        return OutlookEventReference(id=event_id)

    def update_event(
        self,
        calendar_id: str,
        event_id: str,
        payload: OutlookEventPayload,
    ) -> OutlookEventReference:
        graph_payload = payload.to_graph_dict()
        self.operations.append(
            CapturedGraphOperation(
                method="PATCH",
                calendar_id=calendar_id,
                event_id=event_id,
                transaction_id=None,
                payload=graph_payload,
            )
        )
        if self.update_failure is not None:
            error = self.update_failure
            self.update_failure = None
            raise error
        if event_id not in self.events:
            raise GraphClientError("Mocked Outlook event does not exist.")
        self.events[event_id] = graph_payload
        return OutlookEventReference(id=event_id)

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        self.operations.append(
            CapturedGraphOperation(
                method="DELETE",
                calendar_id=calendar_id,
                event_id=event_id,
                transaction_id=None,
                payload=None,
            )
        )
        if self.delete_failure is not None:
            error = self.delete_failure
            self.delete_failure = None
            raise error
        self.events.pop(event_id, None)


@dataclass
class ProviderOutlookHarness:
    database_path: Path
    transport: ScriptedApiFootballTransport
    graph: RecordingGraphClient
    logger: logging.Logger
    provider_runtime: ApiFootballImportRuntimeService
    calendar_runtime: SynchronizationRuntimeService
    sync_runs: SyncRunsRepository
    mappings: SourceMappingsRepository
    events: SportsEventsRepository
    event_participants: EventParticipantsRepository
    calendar_mappings: CalendarEventMappingsRepository
    clock_value: datetime
    _clock_reference: list[datetime] = field(init=False, repr=False)

    @classmethod
    def create(
        cls, database_path: Path, *, initialize_test_catalog: CatalogInitializer
    ) -> "ProviderOutlookHarness":
        initialize_test_catalog(database_path)
        sports = SportsRepository(database_path)
        competitions = CompetitionsRepository(database_path)
        seasons = SeasonsRepository(database_path)
        participants = ParticipantsRepository(database_path)
        season_participants = SeasonParticipantsRepository(database_path)
        sources = DataSourcesRepository(database_path)
        mappings = SourceMappingsRepository(database_path)
        events = SportsEventsRepository(database_path)
        event_participants = EventParticipantsRepository(database_path)
        calendar_mappings = CalendarEventMappingsRepository(database_path)
        sync_runs = SyncRunsRepository(database_path)

        provider_settings = ApiFootballSettings(
            enabled=True,
            api_key=PROVIDER_SECRET,
            max_attempts=3,
            retry_base_delay_seconds=0.001,
            retry_max_delay_seconds=0.001,
        )
        register_api_football_source(provider_settings, sources)
        transport = ScriptedApiFootballTransport()
        clock = [datetime(2026, 8, 8, 12, tzinfo=UTC)]
        client = ApiFootballClient(
            settings=provider_settings,
            transport=transport,
            sleep=lambda _delay: None,
            clock=lambda: clock[0],
        )
        catalog_service = ApiFootballCatalogService(
            settings=provider_settings,
            adapter=ApiFootballCatalogAdapter(client),
            sports_repository=sports,
            competitions_repository=competitions,
            seasons_repository=seasons,
            participants_repository=participants,
            season_participants_repository=season_participants,
            data_sources_repository=sources,
            source_mappings_repository=mappings,
            team_mapping=PREMIER_LEAGUE_TEAM_MAPPING,
        )
        normalization_service = ApiFootballFixtureNormalizationService(
            adapter=ApiFootballFixtureAdapter(client),
            sports_repository=sports,
            competitions_repository=competitions,
            seasons_repository=seasons,
            participants_repository=participants,
            data_sources_repository=sources,
            source_mappings_repository=mappings,
        )
        import_service = ApiFootballFixtureImportService(
            data_sources_repository=sources,
            fixture_import_repository=FixtureImportRepository(database_path),
        )
        logger = logging.getLogger(f"phase47.{database_path.name}")
        logger.handlers.clear()
        logger.addHandler(logging.NullHandler())
        provider_runtime = ApiFootballImportRuntimeService(
            orchestrator=ApiFootballImportOrchestrator(
                catalog_service=catalog_service,
                normalization_service=normalization_service,
                import_service=import_service,
                data_sources_repository=sources,
                sync_runs_repository=sync_runs,
            ),
            sync_runs_repository=sync_runs,
            logger=logger,
        )
        graph = RecordingGraphClient()
        calendar_runtime = SynchronizationRuntimeService(
            orchestrator=SynchronizationOrchestrator(
                query_repository=SynchronizationQueryRepository(database_path),
                event_synchronizer=EventSynchronizer(
                    payload_builder=OutlookEventPayloadBuilder(),
                    graph_client=graph,  # type: ignore[arg-type]
                    mappings_repository=calendar_mappings,
                ),
                sync_runs_repository=sync_runs,
            ),
            sync_runs_repository=sync_runs,
            logger=logger,
        )
        harness = cls(
            database_path=database_path,
            transport=transport,
            graph=graph,
            logger=logger,
            provider_runtime=provider_runtime,
            calendar_runtime=calendar_runtime,
            sync_runs=sync_runs,
            mappings=mappings,
            events=events,
            event_participants=event_participants,
            calendar_mappings=calendar_mappings,
            clock_value=clock[0],
        )
        harness._clock_reference = clock
        return harness

    def set_clock(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("Phase 4.7 clock must be timezone-aware.")
        self.clock_value = value.astimezone(UTC)
        self._clock_reference[0] = self.clock_value

    def run_cycle(
        self,
    ) -> tuple[ProviderImportRunResult, SynchronizationRunResult]:
        provider_result = self.provider_runtime.run()
        if provider_result is None:
            raise AssertionError("Phase 4.7 provider cycle unexpectedly overlapped.")
        calendar_result = self.calendar_runtime.run(calendar_id=CALENDAR_ID, limit=100)
        if calendar_result is None:
            raise AssertionError("Phase 4.7 calendar cycle unexpectedly overlapped.")
        return provider_result, calendar_result

    def event_for_fixture(self, external_id: int) -> SportsEvent:
        source = DataSourcesRepository(self.database_path).get_by_key("api_football")
        if source is None:
            raise AssertionError("API-Football source missing from E2E database.")
        mapping = self.mappings.get_by_external_id(
            source_id=source.id,
            object_type="event",
            external_id=str(external_id),
        )
        if mapping is None:
            raise AssertionError(f"Fixture mapping missing: {external_id}")
        event = self.events.get_by_id(mapping.internal_id)
        if event is None:
            raise AssertionError(f"Fixture event missing: {external_id}")
        return event

    def table_count(self, table_name: str) -> int:
        allowed = {
            "calendar_event_mappings",
            "event_participants",
            "fixture_reconciliation_state",
            "source_mappings",
            "sports_events",
        }
        if table_name not in allowed:
            raise ValueError(f"Unsupported Phase 4.7 table count: {table_name}")
        with sqlite3.connect(self.database_path) as connection:
            return int(
                connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            )
