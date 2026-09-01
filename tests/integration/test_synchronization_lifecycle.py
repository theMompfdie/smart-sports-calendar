import logging
from dataclasses import replace
from unittest.mock import MagicMock

from app.database.reminder_rules_repository import (
    ReminderRulesRepository,
    ReminderRuleTarget,
)
from app.database.sports_events_repository import SportsEventsRepository
from app.database.synchronization_query_repository import (
    SynchronizationEvent,
    SynchronizationQueryRepository,
)
from app.domain.reminder_rules import (
    ReminderAction,
    ReminderRuleWrite,
    ReminderScope,
)
from app.graph.client import OutlookEventReference
from app.synchronization.event_reminder_resolver import EventReminderResolver
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import (
    OutlookEventPayload,
    OutlookEventPayloadBuilder,
)
from app.synchronization.synchronization_orchestrator import (
    SynchronizationOrchestrator,
)
from app.synchronization.synchronization_runtime_service import (
    SynchronizationRuntimeService,
)

from tests.integration.conftest import SynchronizationHarness

CALENDAR_ID = "integration-calendar"


class _LegacyPresentationBuilder(OutlookEventPayloadBuilder):
    def build(
        self,
        synchronization_event: SynchronizationEvent,
    ) -> OutlookEventPayload:
        payload = super().build(synchronization_event)
        return replace(
            payload,
            subject=synchronization_event.event.title,
            body="Status: scheduled\nSport: Football",
            body_content_type="text",
            categories=("Football", "Premier League", "SMART Sports Calendar"),
        )


def _build_runtime_service(
    harness: SynchronizationHarness,
    payload_builder: OutlookEventPayloadBuilder,
) -> SynchronizationRuntimeService:
    return SynchronizationRuntimeService(
        orchestrator=SynchronizationOrchestrator(
            query_repository=SynchronizationQueryRepository(harness.database_path),
            event_synchronizer=EventSynchronizer(
                payload_builder=payload_builder,
                graph_client=harness.graph_client,
                mappings_repository=harness.mappings_repository,
            ),
            sync_runs_repository=harness.sync_runs_repository,
        ),
        sync_runs_repository=harness.sync_runs_repository,
        logger=MagicMock(spec=logging.Logger),
    )


def test_create_then_skip_unchanged_event(
    synchronization_harness: SynchronizationHarness,
) -> None:
    first_result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert first_result is not None
    assert first_result.status == "completed"
    assert first_result.items_processed == 1
    assert first_result.items_created == 1
    assert first_result.items_updated == 0
    assert first_result.items_unchanged == 0
    assert first_result.items_cancelled == 0
    assert first_result.items_deleted == 0
    assert first_result.items_failed == 0

    mapping = synchronization_harness.mappings_repository.get_by_event(
        event_id=synchronization_harness.event.id,
        calendar_id=CALENDAR_ID,
    )

    assert mapping is not None
    assert mapping.sync_status == "synced"
    assert mapping.outlook_event_id == "outlook-event-1"
    assert mapping.content_hash is not None
    assert mapping.last_synced_at is not None
    assert mapping.last_sync_error is None

    second_result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert second_result is not None
    assert second_result.status == "completed"
    assert second_result.items_processed == 1
    assert second_result.items_created == 0
    assert second_result.items_updated == 0
    assert second_result.items_unchanged == 1
    assert second_result.items_cancelled == 0
    assert second_result.items_deleted == 0
    assert second_result.items_failed == 0

    synchronization_harness.graph_client.create_event.assert_called_once()
    synchronization_harness.graph_client.update_event.assert_not_called()
    synchronization_harness.graph_client.delete_event.assert_not_called()

    sync_runs = synchronization_harness.sync_runs_repository.get_recent(
        run_type="calendar_sync",
        limit=10,
    )

    assert len(sync_runs) == 2
    assert all(sync_run.status == "completed" for sync_run in sync_runs)

    latest_run, first_run = sync_runs

    assert latest_run.items_processed == 1
    assert latest_run.items_created == 0
    assert latest_run.items_unchanged == 1
    assert latest_run.items_failed == 0

    assert first_run.items_processed == 1
    assert first_run.items_created == 1
    assert first_run.items_unchanged == 0
    assert first_run.items_failed == 0


def test_existing_mapping_converges_to_new_presentation_without_duplicate(
    synchronization_harness: SynchronizationHarness,
) -> None:
    legacy_service = _build_runtime_service(
        synchronization_harness,
        _LegacyPresentationBuilder(),
    )
    first_result = legacy_service.run(CALENDAR_ID, 100)

    assert first_result is not None
    assert first_result.items_created == 1
    before = synchronization_harness.mappings_repository.get_by_event(
        synchronization_harness.event.id,
        CALENDAR_ID,
    )
    assert before is not None
    assert before.outlook_event_id == "outlook-event-1"

    synchronization_harness.graph_client.update_event.return_value = (
        OutlookEventReference(id="outlook-event-1")
    )
    current_service = _build_runtime_service(
        synchronization_harness,
        OutlookEventPayloadBuilder(),
    )
    update_result = current_service.run(CALENDAR_ID, 100)

    assert update_result is not None
    assert update_result.items_created == 0
    assert update_result.items_updated == 1
    synchronization_harness.graph_client.create_event.assert_called_once()
    synchronization_harness.graph_client.update_event.assert_called_once()
    update_payload = synchronization_harness.graph_client.update_event.call_args.kwargs[
        "payload"
    ]
    assert update_payload.subject == "⚽ Arsenal vs Liverpool"
    assert update_payload.categories == ("Premier League",)
    assert update_payload.body_content_type == "html"
    assert "<h3" in update_payload.body

    after = synchronization_harness.mappings_repository.get_by_event(
        synchronization_harness.event.id,
        CALENDAR_ID,
    )
    assert after is not None
    assert after.id == before.id
    assert after.outlook_event_id == before.outlook_event_id
    assert after.transaction_id == before.transaction_id

    unchanged_result = current_service.run(CALENDAR_ID, 100)

    assert unchanged_result is not None
    assert unchanged_result.items_unchanged == 1
    synchronization_harness.graph_client.update_event.assert_called_once()


def test_runtime_team_rule_converges_existing_outlook_event(
    synchronization_harness: SynchronizationHarness,
) -> None:
    rules = ReminderRulesRepository(synchronization_harness.database_path)
    service = _build_runtime_service(
        synchronization_harness,
        OutlookEventPayloadBuilder(
            reminder_resolver=EventReminderResolver(rules),
        ),
    )
    first_result = service.run(CALENDAR_ID, 100)
    assert first_result is not None
    assert first_result.items_created == 1
    before = synchronization_harness.mappings_repository.get_by_event(
        synchronization_harness.event.id,
        CALENDAR_ID,
    )
    assert before is not None
    assert before.last_synced_presentation_revision == 1

    selector = rules.resolve_target(
        ReminderRuleTarget(
            ReminderScope.PARTICIPANT,
            participant_key="arsenal",
        )
    )
    rules.set(
        ReminderRuleWrite(
            selector,
            action=ReminderAction.ENABLE,
            preferred_lead_minutes=60,
        )
    )
    invalidated = synchronization_harness.mappings_repository.get_by_id(before.id)
    assert invalidated is not None
    assert invalidated.presentation_revision == 2
    assert invalidated.last_synced_presentation_revision == 1

    synchronization_harness.graph_client.update_event.return_value = (
        OutlookEventReference(id="outlook-event-1")
    )
    update_result = service.run(CALENDAR_ID, 100)

    assert update_result is not None
    assert update_result.items_created == 0
    assert update_result.items_updated == 1
    assert synchronization_harness.graph_client.create_event.call_count == 1
    assert synchronization_harness.graph_client.update_event.call_count == 1
    payload = synchronization_harness.graph_client.update_event.call_args.kwargs[
        "payload"
    ]
    assert payload.is_reminder_on is True
    assert payload.reminder_minutes_before_start == 60
    after = synchronization_harness.mappings_repository.get_by_id(before.id)
    assert after is not None
    assert after.transaction_id == before.transaction_id
    assert after.outlook_event_id == before.outlook_event_id
    assert after.last_synced_presentation_revision == 2

    rules.set(
        ReminderRuleWrite(
            selector,
            action=ReminderAction.ENABLE,
            preferred_lead_minutes=60,
        )
    )
    unchanged_result = service.run(CALENDAR_ID, 100)

    assert unchanged_result is not None
    assert unchanged_result.items_unchanged == 1
    assert synchronization_harness.graph_client.update_event.call_count == 1

    rules.delete(selector)
    fallback_result = service.run(CALENDAR_ID, 100)

    assert fallback_result is not None
    assert fallback_result.items_updated == 1
    assert synchronization_harness.graph_client.update_event.call_count == 2
    fallback_payload = (
        synchronization_harness.graph_client.update_event.call_args.kwargs["payload"]
    )
    assert fallback_payload.is_reminder_on is True
    assert fallback_payload.reminder_minutes_before_start == 15


def test_changed_event_is_updated_in_outlook(
    synchronization_harness: SynchronizationHarness,
) -> None:
    first_result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert first_result is not None
    assert first_result.items_created == 1

    synchronization_harness.graph_client.update_event.return_value = (
        OutlookEventReference(id="outlook-event-1")
    )

    events_repository = SportsEventsRepository(synchronization_harness.database_path)
    event = synchronization_harness.event

    events_repository.upsert(
        sport_id=event.sport_id,
        competition_id=event.competition_id,
        season_id=event.season_id,
        parent_event_id=event.parent_event_id,
        event_key=event.event_key,
        event_type=event.event_type,
        title="Arsenal vs Liverpool – Rescheduled",
        stage=event.stage,
        round_name=event.round_name,
        sequence_number=event.sequence_number,
        start_time="2026-08-15T17:30:00+00:00",
        end_time="2026-08-15T19:30:00+00:00",
        timezone=event.timezone,
        venue_name=event.venue_name,
        city=event.city,
        country_code=event.country_code,
        status=event.status,
        source_updated_at="2026-08-02T18:00:00+00:00",
        cancelled_at=event.cancelled_at,
        deleted_at=event.deleted_at,
        metadata=event.metadata,
    )

    second_result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert second_result is not None
    assert second_result.status == "completed"
    assert second_result.items_processed == 1
    assert second_result.items_created == 0
    assert second_result.items_updated == 1
    assert second_result.items_unchanged == 0
    assert second_result.items_failed == 0

    synchronization_harness.graph_client.create_event.assert_called_once()
    synchronization_harness.graph_client.update_event.assert_called_once()

    update_call = synchronization_harness.graph_client.update_event.call_args

    assert update_call.kwargs["calendar_id"] == CALENDAR_ID
    assert update_call.kwargs["event_id"] == "outlook-event-1"
    payload = update_call.kwargs["payload"]
    assert payload.subject == "⚽ Arsenal vs Liverpool – Rescheduled"
    assert payload.categories == ("Premier League",)
    mapping = synchronization_harness.mappings_repository.get_by_event(
        event_id=event.id,
        calendar_id=CALENDAR_ID,
    )

    assert mapping is not None
    assert mapping.sync_status == "synced"
    assert mapping.outlook_event_id == "outlook-event-1"
    assert mapping.last_sync_error is None


def test_cancelled_event_is_updated_in_outlook(
    synchronization_harness: SynchronizationHarness,
) -> None:
    first_result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert first_result is not None
    assert first_result.items_created == 1

    synchronization_harness.graph_client.update_event.return_value = (
        OutlookEventReference(id="outlook-event-1")
    )

    events_repository = SportsEventsRepository(synchronization_harness.database_path)
    event = synchronization_harness.event

    events_repository.upsert(
        sport_id=event.sport_id,
        competition_id=event.competition_id,
        season_id=event.season_id,
        parent_event_id=event.parent_event_id,
        event_key=event.event_key,
        event_type=event.event_type,
        title=event.title,
        stage=event.stage,
        round_name=event.round_name,
        sequence_number=event.sequence_number,
        start_time=event.start_time,
        end_time=event.end_time,
        timezone=event.timezone,
        venue_name=event.venue_name,
        city=event.city,
        country_code=event.country_code,
        status="cancelled",
        source_updated_at="2026-08-02T18:30:00+00:00",
        cancelled_at="2026-08-02T18:30:00+00:00",
        deleted_at=event.deleted_at,
        metadata=event.metadata,
    )

    second_result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert second_result is not None
    assert second_result.status == "completed"
    assert second_result.items_processed == 1
    assert second_result.items_created == 0
    assert second_result.items_updated == 0
    assert second_result.items_unchanged == 0
    assert second_result.items_cancelled == 1
    assert second_result.items_failed == 0

    synchronization_harness.graph_client.create_event.assert_called_once()
    synchronization_harness.graph_client.update_event.assert_called_once()

    update_call = synchronization_harness.graph_client.update_event.call_args

    assert update_call.kwargs["calendar_id"] == CALENDAR_ID
    assert update_call.kwargs["event_id"] == "outlook-event-1"

    mapping = synchronization_harness.mappings_repository.get_by_event(
        event_id=event.id,
        calendar_id=CALENDAR_ID,
    )

    assert mapping is not None
    assert mapping.sync_status == "synced"
    assert mapping.outlook_event_id == "outlook-event-1"
    assert mapping.last_sync_error is None


def test_delete_pending_mapping_is_deleted_from_outlook(
    synchronization_harness: SynchronizationHarness,
) -> None:
    first_result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert first_result is not None
    assert first_result.items_created == 1

    mapping = synchronization_harness.mappings_repository.get_by_event(
        event_id=synchronization_harness.event.id,
        calendar_id=CALENDAR_ID,
    )

    assert mapping is not None
    assert mapping.sync_status == "synced"
    assert mapping.outlook_event_id == "outlook-event-1"

    delete_pending_mapping = (
        synchronization_harness.mappings_repository.mark_delete_pending(
            mapping_id=mapping.id,
        )
    )

    assert delete_pending_mapping is not None
    assert delete_pending_mapping.sync_status == "delete_pending"

    second_result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert second_result is not None
    assert second_result.status == "completed"
    assert second_result.items_processed == 1
    assert second_result.items_created == 0
    assert second_result.items_updated == 0
    assert second_result.items_unchanged == 0
    assert second_result.items_cancelled == 0
    assert second_result.items_deleted == 1
    assert second_result.items_failed == 0

    synchronization_harness.graph_client.create_event.assert_called_once()
    synchronization_harness.graph_client.update_event.assert_not_called()
    synchronization_harness.graph_client.delete_event.assert_called_once_with(
        calendar_id=CALENDAR_ID,
        event_id="outlook-event-1",
    )

    deleted_mapping = synchronization_harness.mappings_repository.get_by_event(
        event_id=synchronization_harness.event.id,
        calendar_id=CALENDAR_ID,
    )

    assert deleted_mapping is not None
    assert deleted_mapping.sync_status == "deleted"
    assert deleted_mapping.outlook_event_id == "outlook-event-1"
    assert deleted_mapping.outlook_change_key is None
    assert deleted_mapping.last_sync_error is None

    sync_runs = synchronization_harness.sync_runs_repository.get_recent(
        run_type="calendar_sync",
        limit=10,
    )

    assert len(sync_runs) == 2

    latest_run = sync_runs[0]

    assert latest_run.status == "completed"
    assert latest_run.items_processed == 1
    assert latest_run.items_deleted == 1
    assert latest_run.items_failed == 0


def test_graph_create_failure_is_persisted(
    synchronization_harness: SynchronizationHarness,
) -> None:
    synchronization_harness.graph_client.create_event.side_effect = RuntimeError(
        "Graph unavailable"
    )

    result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert result is not None
    assert result.status == "completed_with_errors"
    assert result.items_processed == 1
    assert result.items_created == 0
    assert result.items_updated == 0
    assert result.items_unchanged == 0
    assert result.items_cancelled == 0
    assert result.items_deleted == 0
    assert result.items_failed == 1

    mapping = synchronization_harness.mappings_repository.get_by_event(
        event_id=synchronization_harness.event.id,
        calendar_id=CALENDAR_ID,
    )

    assert mapping is not None
    assert mapping.sync_status == "failed"
    assert mapping.outlook_event_id is None
    assert mapping.content_hash is None
    assert mapping.sync_attempts == 1
    assert mapping.last_synced_at is None
    assert mapping.last_sync_error == "Graph unavailable"

    synchronization_harness.graph_client.create_event.assert_called_once()
    synchronization_harness.graph_client.update_event.assert_not_called()
    synchronization_harness.graph_client.delete_event.assert_not_called()

    sync_runs = synchronization_harness.sync_runs_repository.get_recent(
        run_type="calendar_sync",
        limit=10,
    )

    assert len(sync_runs) == 1

    sync_run = sync_runs[0]

    assert sync_run.status == "completed_with_errors"
    assert sync_run.items_processed == 1
    assert sync_run.items_created == 0
    assert sync_run.items_failed == 1
    assert sync_run.error_message is None


def test_startup_recovers_interrupted_sync_run_before_synchronization(
    synchronization_harness: SynchronizationHarness,
) -> None:
    interrupted_run = synchronization_harness.sync_runs_repository.start(
        run_type="calendar_sync",
        metadata={"calendar_id": CALENDAR_ID},
    )

    updated_interrupted_run = (
        synchronization_harness.sync_runs_repository.update_progress(
            sync_run_id=interrupted_run.id,
            items_processed=3,
            items_created=1,
            items_updated=1,
            items_unchanged=1,
            items_cancelled=0,
            items_deleted=0,
            items_failed=0,
        )
    )

    assert updated_interrupted_run is not None
    assert updated_interrupted_run.status == "running"
    assert updated_interrupted_run.finished_at is None

    result = synchronization_harness.service.run(
        calendar_id=CALENDAR_ID,
        limit=100,
    )

    assert result is not None
    assert result.status == "completed"
    assert result.items_processed == 1
    assert result.items_created == 1
    assert result.items_failed == 0

    recovered_run = synchronization_harness.sync_runs_repository.get_by_id(
        interrupted_run.id
    )

    assert recovered_run is not None
    assert recovered_run.status == "failed"
    assert recovered_run.finished_at is not None
    assert recovered_run.error_message == (
        "Interrupted synchronization run recovered during application startup."
    )
    assert recovered_run.items_processed == 3
    assert recovered_run.items_created == 1
    assert recovered_run.items_updated == 1
    assert recovered_run.items_unchanged == 1
    assert recovered_run.metadata == {"calendar_id": CALENDAR_ID}

    completed_run = synchronization_harness.sync_runs_repository.get_by_id(
        result.sync_run_id
    )

    assert completed_run is not None
    assert completed_run.status == "completed"
    assert completed_run.finished_at is not None
    assert completed_run.error_message is None
    assert completed_run.id != recovered_run.id

    running_runs = synchronization_harness.sync_runs_repository.get_by_status("running")

    assert running_runs == []

    synchronization_harness.graph_client.create_event.assert_called_once()
    synchronization_harness.graph_client.update_event.assert_not_called()
    synchronization_harness.graph_client.delete_event.assert_not_called()
