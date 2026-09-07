import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.application.api_football_import_orchestrator import (
    ProviderImportOrchestrationError,
)
from app.graph.client import GraphClientError
from app.providers.api_football.transport import HttpResponse

from tests.catalog_support import CatalogInitializer
from tests.integration.provider_outlook_support import (
    CALENDAR_ID,
    PROVIDER_SECRET,
    ProviderOutlookHarness,
    fixture_payload,
    update_fixture_payload,
)


def create_harness(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> ProviderOutlookHarness:
    return ProviderOutlookHarness.create(
        tmp_path / "provider-outlook-e2e.db",
        initialize_test_catalog=initialize_test_catalog,
    )


def test_payload_to_sqlite_to_graph_is_idempotent_and_updates_in_place(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    harness = create_harness(tmp_path, initialize_test_catalog=initialize_test_catalog)
    first_fixture = fixture_payload(900001)
    harness.transport.set_fixtures([first_fixture])

    first_provider, first_calendar = harness.run_cycle()

    assert first_provider.items_created == 1
    assert first_provider.items_failed == 0
    assert first_calendar.items_created == 1
    event = harness.event_for_fixture(900001)
    event_id = event.id
    event_mapping = harness.calendar_mappings.get_by_event(event.id, CALENDAR_ID)
    assert event_mapping is not None
    mapping_id = event_mapping.id
    outlook_event_id = event_mapping.outlook_event_id
    assert outlook_event_id == "outlook-event-1"
    assert [
        (participant.role, participant.position_number)
        for participant in harness.event_participants.get_for_event(event.id)
    ] == [("home", 1), ("away", 2)]
    assert [operation.method for operation in harness.graph.operations] == ["POST"]
    assert harness.graph.operations[0].calendar_id == CALENDAR_ID
    assert [request.path for request in harness.transport.requests] == [
        "/leagues",
        "/teams",
        "/fixtures",
    ]
    assert harness.transport.requests[0].query == (("id", "39"),)
    assert harness.transport.requests[1].query == (
        ("league", "39"),
        ("season", "2026"),
    )
    assert ("page", "1") in harness.transport.requests[2].query

    harness.set_clock(datetime(2026, 8, 8, 13, tzinfo=UTC))
    repeated_provider, repeated_calendar = harness.run_cycle()

    assert repeated_provider.items_unchanged == 1
    assert repeated_calendar.items_unchanged == 1
    assert [operation.method for operation in harness.graph.operations] == ["POST"]
    assert harness.table_count("sports_events") == 1
    assert harness.table_count("event_participants") == 2
    assert harness.table_count("calendar_event_mappings") == 1

    second_fixture = fixture_payload(900004)
    harness.transport.set_fixtures(
        [first_fixture, second_fixture],
        page_size=1,
    )
    harness.set_clock(datetime(2026, 8, 8, 14, tzinfo=UTC))
    discovery_provider, discovery_calendar = harness.run_cycle()

    assert discovery_provider.items_created == 1
    assert discovery_provider.items_unchanged == 1
    assert discovery_calendar.items_created == 1
    assert discovery_calendar.items_unchanged == 1
    assert harness.table_count("sports_events") == 2
    assert harness.table_count("event_participants") == 4
    provider_run = harness.sync_runs.get_by_id(discovery_provider.sync_run_id)
    assert provider_run is not None
    assert provider_run.source_id is not None
    assert provider_run.metadata is not None
    assert provider_run.metadata["competition_id"] == event.competition_id
    assert provider_run.metadata["season_id"] == event.season_id
    assert provider_run.metadata["window_start_utc"] == ("2026-08-21T00:00:00+00:00")
    assert provider_run.metadata["window_end_utc"] == (
        "2027-05-30T23:59:59.999999+00:00"
    )
    assert provider_run.metadata["authoritative"] is True
    assert provider_run.metadata["complete"] is True
    assert provider_run.metadata["filtered"] is False
    assert provider_run.metadata["observation_id"] == (
        discovery_provider.observation_id
    )
    assert provider_run.metadata["observed_at_utc"] == ("2026-08-08T14:00:00+00:00")
    assert provider_run.metadata["page_count"] == 2
    assert provider_run.metadata["request_attempts"] == 2
    assert provider_run.metadata["rate_limits"]["daily_remaining"] == 7490

    moved_kickoff = datetime(2026, 8, 21, 16, tzinfo=UTC)
    moved_fixture = update_fixture_payload(
        first_fixture,
        kickoff_utc=moved_kickoff,
        updated_at_utc=datetime(2026, 8, 8, 15, tzinfo=UTC),
    )
    harness.transport.set_fixtures([moved_fixture, second_fixture], page_size=1)
    harness.set_clock(datetime(2026, 8, 8, 15, tzinfo=UTC))
    moved_provider, moved_calendar = harness.run_cycle()

    assert moved_provider.items_updated == 1
    assert moved_provider.items_unchanged == 1
    assert moved_calendar.items_updated == 1
    assert moved_calendar.items_unchanged == 1
    moved_event = harness.event_for_fixture(900001)
    assert moved_event.id == event_id
    assert moved_event.start_time == moved_kickoff.isoformat()
    moved_mapping = harness.calendar_mappings.get_by_event(event_id, CALENDAR_ID)
    assert moved_mapping is not None
    assert moved_mapping.id == mapping_id
    assert moved_mapping.outlook_event_id == outlook_event_id
    assert [operation.method for operation in harness.graph.operations] == [
        "POST",
        "POST",
        "PATCH",
    ]
    assert all(
        operation.calendar_id == CALENDAR_ID for operation in harness.graph.operations
    )


def test_lifecycle_removal_and_reappearance_preserve_stable_identity(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    harness = create_harness(tmp_path, initialize_test_catalog=initialize_test_catalog)
    scheduled = fixture_payload(900001)
    harness.transport.set_fixtures([scheduled])
    harness.run_cycle()
    event = harness.event_for_fixture(900001)
    mapping = harness.calendar_mappings.get_by_event(event.id, CALENDAR_ID)
    assert mapping is not None
    mapping_id = mapping.id
    transaction_id = mapping.transaction_id
    outlook_event_id = mapping.outlook_event_id

    cancelled = update_fixture_payload(
        scheduled,
        status_code="CANC",
        status_reason="Match Cancelled",
        updated_at_utc=datetime(2026, 8, 8, 13, tzinfo=UTC),
    )
    harness.transport.set_fixtures([cancelled])
    harness.set_clock(datetime(2026, 8, 8, 13, tzinfo=UTC))
    cancelled_provider, cancelled_calendar = harness.run_cycle()
    assert cancelled_provider.items_cancelled == 1
    assert cancelled_calendar.items_cancelled == 1
    assert harness.event_for_fixture(900001).status == "cancelled"

    corrected = update_fixture_payload(
        scheduled,
        status_code="NS",
        status_reason="Not Started",
        updated_at_utc=datetime(2026, 8, 8, 14, tzinfo=UTC),
    )
    harness.transport.set_fixtures([corrected])
    harness.set_clock(datetime(2026, 8, 8, 14, tzinfo=UTC))
    corrected_provider, corrected_calendar = harness.run_cycle()
    assert corrected_provider.items_updated == 1
    assert corrected_calendar.items_updated == 1
    assert harness.event_for_fixture(900001).status == "scheduled"

    postponed = update_fixture_payload(
        scheduled,
        status_code="PST",
        status_reason="Match Postponed",
        updated_at_utc=datetime(2026, 8, 8, 14, 30, tzinfo=UTC),
    )
    harness.transport.set_fixtures([postponed])
    harness.set_clock(datetime(2026, 8, 8, 14, 30, tzinfo=UTC))
    postponed_provider, postponed_calendar = harness.run_cycle()
    assert postponed_provider.items_updated == 1
    assert postponed_calendar.items_updated == 1
    assert harness.event_for_fixture(900001).status == "postponed"

    harness.transport.set_fixtures([corrected])
    harness.set_clock(datetime(2026, 8, 8, 14, 45, tzinfo=UTC))
    reactivated_provider, reactivated_calendar = harness.run_cycle()
    assert reactivated_provider.items_updated == 1
    assert reactivated_calendar.items_updated == 1
    assert harness.event_for_fixture(900001).status == "scheduled"

    harness.transport.set_fixtures([])
    harness.set_clock(datetime(2026, 8, 8, 15, tzinfo=UTC))
    first_absence, _ = harness.run_cycle()
    assert first_absence.items_deleted == 0
    assert harness.event_for_fixture(900001).deleted_at is None

    harness.set_clock(datetime(2026, 8, 8, 16, tzinfo=UTC))
    second_absence, deletion_calendar = harness.run_cycle()
    assert second_absence.items_deleted == 1
    assert deletion_calendar.items_deleted == 1
    deleted_event = harness.event_for_fixture(900001)
    assert deleted_event.id == event.id
    assert deleted_event.deleted_at is not None
    deleted_mapping = harness.calendar_mappings.get_by_event(event.id, CALENDAR_ID)
    assert deleted_mapping is not None
    assert deleted_mapping.sync_status == "deleted"

    harness.transport.set_fixtures([corrected])
    harness.set_clock(datetime(2026, 8, 8, 17, tzinfo=UTC))
    reappeared_provider, reappeared_calendar = harness.run_cycle()

    assert reappeared_provider.items_updated == 1
    assert reappeared_calendar.items_created == 1
    restored_event = harness.event_for_fixture(900001)
    restored_mapping = harness.calendar_mappings.get_by_event(event.id, CALENDAR_ID)
    assert restored_mapping is not None
    assert restored_event.id == event.id
    assert restored_event.deleted_at is None
    assert restored_mapping.id == mapping_id
    assert restored_mapping.transaction_id == transaction_id
    assert restored_mapping.outlook_event_id == outlook_event_id
    assert harness.table_count("sports_events") == 1
    assert harness.table_count("calendar_event_mappings") == 1
    assert [operation.method for operation in harness.graph.operations] == [
        "POST",
        "PATCH",
        "PATCH",
        "PATCH",
        "PATCH",
        "DELETE",
        "POST",
    ]


def test_failed_collections_do_not_mutate_or_handoff_and_retry_converges(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    *,
    initialize_test_catalog: CatalogInitializer,
) -> None:
    harness = create_harness(tmp_path, initialize_test_catalog=initialize_test_catalog)
    caplog.set_level(logging.DEBUG, logger=harness.logger.name)
    first_fixture = fixture_payload(900001)
    second_fixture = fixture_payload(900004)
    harness.transport.set_fixtures([first_fixture])
    harness.run_cycle()
    initial_calendar_runs = len(
        harness.sync_runs.get_recent(run_type="calendar_sync", limit=20)
    )
    initial_graph_operations = len(harness.graph.operations)

    malformed = HttpResponse(status=200, headers={}, body=b"{")
    harness.transport.fail_fixture_page(1, [malformed])
    harness.set_clock(datetime(2026, 8, 8, 13, tzinfo=UTC))
    with pytest.raises(ProviderImportOrchestrationError) as malformed_error:
        harness.run_cycle()
    assert PROVIDER_SECRET not in str(malformed_error.value)

    harness.transport.clear_failures()
    harness.transport.set_fixtures([first_fixture, second_fixture], page_size=1)
    unavailable = HttpResponse(status=503, headers={}, body=b"")
    harness.transport.fail_fixture_page(2, [unavailable, unavailable, unavailable])
    harness.set_clock(datetime(2026, 8, 8, 14, tzinfo=UTC))
    with pytest.raises(ProviderImportOrchestrationError) as partial_error:
        harness.run_cycle()
    assert PROVIDER_SECRET not in str(partial_error.value)

    assert harness.table_count("sports_events") == 1
    assert harness.table_count("fixture_reconciliation_state") == 0
    assert len(harness.graph.operations) == initial_graph_operations
    assert (
        len(harness.sync_runs.get_recent(run_type="calendar_sync", limit=20))
        == initial_calendar_runs
    )
    failed_runs = harness.sync_runs.get_recent(run_type="provider_import", limit=20)
    assert [run.status for run in failed_runs[:2]] == ["failed", "failed"]
    assert all(run.metadata is not None for run in failed_runs[:2])

    harness.transport.clear_failures()
    harness.set_clock(datetime(2026, 8, 8, 15, tzinfo=UTC))
    retry_provider, retry_calendar = harness.run_cycle()
    assert retry_provider.items_created == 1
    assert retry_provider.items_unchanged == 1
    assert retry_calendar.items_created == 1
    assert retry_calendar.items_unchanged == 1
    assert harness.table_count("sports_events") == 2
    assert harness.table_count("calendar_event_mappings") == 2

    diagnostic_text = json.dumps(
        {
            "requests": [repr(request) for request in harness.transport.requests],
            "provider_runs": [
                {
                    "error": run.error_message,
                    "metadata": run.metadata,
                }
                for run in harness.sync_runs.get_recent(
                    run_type="provider_import",
                    limit=20,
                )
            ],
            "graph": [repr(operation) for operation in harness.graph.operations],
        },
        sort_keys=True,
    )
    assert PROVIDER_SECRET not in diagnostic_text
    assert PROVIDER_SECRET not in caplog.text
    assert "x-apisports-key" in {
        header
        for request in harness.transport.requests
        for header in request.header_names
    }


@pytest.mark.parametrize(
    ("trigger_name", "trigger_sql", "persisted_before_retry"),
    [
        (
            "fail_fixture_persistence",
            """
            CREATE TRIGGER fail_fixture_persistence
            BEFORE INSERT ON sports_events
            BEGIN
                SELECT RAISE(ABORT, 'forced fixture persistence failure');
            END;
            """,
            0,
        ),
        (
            "fail_provider_finalization",
            """
            CREATE TRIGGER fail_provider_finalization
            BEFORE UPDATE OF status ON sync_runs
            WHEN OLD.run_type = 'provider_import' AND NEW.status = 'completed'
            BEGIN
                SELECT RAISE(ABORT, 'forced provider finalization failure');
            END;
            """,
            1,
        ),
    ],
)
def test_persistence_and_finalization_failures_are_terminal_and_retryable(
    tmp_path: Path,
    trigger_name: str,
    trigger_sql: str,
    persisted_before_retry: int,
    *,
    initialize_test_catalog: CatalogInitializer,
) -> None:
    harness = create_harness(tmp_path, initialize_test_catalog=initialize_test_catalog)
    harness.transport.set_fixtures([fixture_payload(900001)])
    with sqlite3.connect(harness.database_path) as connection:
        connection.executescript(trigger_sql)

    with pytest.raises(ProviderImportOrchestrationError):
        harness.run_cycle()

    provider_runs = harness.sync_runs.get_recent(run_type="provider_import", limit=10)
    assert len(provider_runs) == 1
    assert provider_runs[0].status == "failed"
    assert provider_runs[0].items_failed == 1
    assert harness.table_count("sports_events") == persisted_before_retry
    assert harness.sync_runs.get_recent(run_type="calendar_sync", limit=10) == []
    assert harness.graph.operations == []

    with sqlite3.connect(harness.database_path) as connection:
        connection.execute(f"DROP TRIGGER {trigger_name}")
    harness.set_clock(datetime(2026, 8, 8, 13, tzinfo=UTC))
    retry_provider, retry_calendar = harness.run_cycle()

    assert retry_provider.status == "completed"
    assert retry_calendar.status == "completed"
    assert harness.table_count("sports_events") == 1
    assert harness.table_count("calendar_event_mappings") == 1
    assert [operation.method for operation in harness.graph.operations] == ["POST"]


def test_graph_failure_keeps_committed_import_and_retries_without_duplicates(
    tmp_path: Path, *, initialize_test_catalog: CatalogInitializer
) -> None:
    harness = create_harness(tmp_path, initialize_test_catalog=initialize_test_catalog)
    harness.transport.set_fixtures([fixture_payload(900001)])
    harness.graph.create_failure = GraphClientError("Mocked Graph unavailable.")

    provider_result, failed_calendar = harness.run_cycle()

    assert provider_result.status == "completed"
    assert provider_result.items_created == 1
    assert failed_calendar.status == "completed_with_errors"
    assert failed_calendar.items_failed == 1
    event = harness.event_for_fixture(900001)
    failed_mapping = harness.calendar_mappings.get_by_event(event.id, CALENDAR_ID)
    assert failed_mapping is not None
    assert failed_mapping.sync_status == "failed"
    assert failed_mapping.outlook_event_id is None
    transaction_id = failed_mapping.transaction_id
    assert harness.table_count("sports_events") == 1

    harness.set_clock(datetime(2026, 8, 8, 13, tzinfo=UTC))
    retry_provider, retry_calendar = harness.run_cycle()

    assert retry_provider.items_unchanged == 1
    assert retry_calendar.status == "completed"
    assert retry_calendar.items_created == 1
    synchronized = harness.calendar_mappings.get_by_event(event.id, CALENDAR_ID)
    assert synchronized is not None
    assert synchronized.sync_status == "synced"
    assert synchronized.transaction_id == transaction_id
    assert synchronized.outlook_event_id == "outlook-event-1"
    assert harness.table_count("sports_events") == 1
    assert harness.table_count("source_mappings") == 23
    assert harness.table_count("event_participants") == 2
    assert harness.table_count("calendar_event_mappings") == 1
    assert [operation.method for operation in harness.graph.operations] == [
        "POST",
        "POST",
    ]
    provider_runs = harness.sync_runs.get_recent(run_type="provider_import", limit=10)
    calendar_runs = harness.sync_runs.get_recent(run_type="calendar_sync", limit=10)
    assert [run.status for run in provider_runs] == ["completed", "completed"]
    assert [run.status for run in calendar_runs] == [
        "completed",
        "completed_with_errors",
    ]
