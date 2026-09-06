"""Inbox, reminder and single-owner integration without live Graph or providers."""

import logging
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest
from app.application.manual_import_worker import ManualImportWorker
from app.application.manual_review_service import ManualReviewService
from app.database.manual_review_repository import ManualReviewRepository
from app.graph.client import (
    GraphClient,
    GraphClientError,
    OutlookEventNotFoundError,
    OutlookEventReference,
)
from app.imports.manual_inbox import ManualInbox, encoded
from app.operations.instance_lock import instance_lock
from app.operations.manual_import import main

from tests.imports.test_manual_apply import approved, rows
from tests.imports.test_manual_apply import service as service
from tests.imports.test_manual_preview import context as context
from tests.imports.test_manual_preview import encode


@pytest.fixture
def worker(service, context, tmp_path):
    inbox = ManualInbox(tmp_path / "inbox", context[3].instance_ref)
    result = ManualImportWorker(inbox, service, logging.getLogger("test"))
    result.initialize()
    return result


def submit(worker, context):
    raw = context[1]
    return worker.inbox.submit(
        "submit", raw["namespace"], raw["submission_id"], encode(raw)
    )


def status(worker, context):
    return worker.inbox.status(context[1]["namespace"], context[1]["submission_id"])


def approval(worker, context):
    report = status(worker, context)
    raw = context[1]
    return encoded(
        {
            "submission_id": raw["submission_id"],
            "import_type": "fixture_schedule",
            "schema_version": 1,
            "manifest_sha256": context[2].fingerprint,
            "preview_sha256": report["preview_sha256"],
            "instance_ref": context[3].instance_ref,
            "operator_ref": "operator",
            "approved_at": "2031-01-01T00:00:00Z",
        }
    )


def test_submit_is_write_free_until_worker_and_requires_approval(worker, context):
    before = context[0].read_bytes()
    submit(worker, context)
    assert context[0].read_bytes() == before
    worker.run()
    assert status(worker, context)["state"] == "AWAITING_APPROVAL"
    assert rows(context[0], "sports_events") == []
    worker.inbox.submit(
        "approve",
        context[1]["namespace"],
        context[1]["submission_id"],
        approval(worker, context),
    )
    worker.run()
    assert status(worker, context)["receipt"]["canonical_status"] == "committed"
    assert len(rows(context[0], "sports_events")) == 1
    submit(worker, context)
    worker.run()
    assert len(rows(context[0], "sports_events")) == 1


def test_partial_upload_and_bad_request_do_not_block_valid_package(worker, context):
    (worker.inbox.root / "pending" / ".partial.upload").write_bytes(b"{")
    (worker.inbox.root / "pending" / "000.json").write_bytes(b"not json")
    submit(worker, context)
    worker.run()
    assert status(worker, context)["state"] == "AWAITING_APPROVAL"
    assert (worker.inbox.root / "pending" / ".partial.upload").exists()


def test_wrong_instance_and_scope_fail_without_canonical_writes(worker, context):
    wrong = ManualInbox(worker.inbox.root, "other-instance")
    with pytest.raises(ValueError, match="another instance"):
        wrong.submit(
            "submit",
            context[1]["namespace"],
            context[1]["submission_id"],
            encode(context[1]),
        )
    worker.inbox.submit(
        "submit", "other-scope", context[1]["submission_id"], encode(context[1])
    )
    worker.run()
    assert rows(context[0], "import_batches") == []
    assert rows(context[0], "sports_events") == []


def test_post_commit_export_failure_replays_safely(worker, context, monkeypatch):
    submit(worker, context)
    worker.run()
    worker.inbox.submit(
        "approve",
        context[1]["namespace"],
        context[1]["submission_id"],
        approval(worker, context),
    )
    original = worker._publish

    def fail(*args, **kwargs):
        raise OSError("injected export failure")

    monkeypatch.setattr(worker, "_publish", fail)
    worker.run()
    assert rows(context[0], "import_batches")[0]["state"] == "APPLIED"
    assert len(list((worker.inbox.root / "pending").glob("*.json"))) == 1
    monkeypatch.setattr(worker, "_publish", original)
    worker.run()
    assert status(worker, context)["state"] == "APPLIED"
    assert len(rows(context[0], "manual_import_receipts")) == 1


def test_stale_approval_requires_explicit_new_preview(worker, context):
    submit(worker, context)
    worker.run()
    payload = approval(worker, context)
    with sqlite3.connect(context[0]) as conn:
        conn.execute("UPDATE participants SET name='changed' WHERE id=1")
    worker.inbox.submit(
        "approve", context[1]["namespace"], context[1]["submission_id"], payload
    )
    worker.run()
    assert status(worker, context)["state"] == "NEEDS_REVIEW"
    for _ in range(2):
        worker.inbox.submit(
            "preview", context[1]["namespace"], context[1]["submission_id"]
        )
        worker.run()
        assert status(worker, context)["state"] == "AWAITING_APPROVAL"
    assert rows(context[0], "sports_events") == []


def test_worker_limit_and_lock(worker, context):
    worker.limit = 1
    for number in range(3):
        raw = {**context[1], "submission_id": f"batch-{number}"}
        worker.inbox.submit(
            "submit", raw["namespace"], raw["submission_id"], encode(raw)
        )
    with worker._lock:
        worker.run()
    assert rows(context[0], "import_batches") == []
    worker.run()
    assert len(rows(context[0], "import_batches")) == 1
    worker.run()
    worker.run()
    assert len(rows(context[0], "import_batches")) == 3


def test_process_lock_rejects_second_owner_and_releases(context):
    with (
        instance_lock(context[0]),
        pytest.raises(RuntimeError, match="Another application"),
        instance_lock(context[0]),
    ):
        pytest.fail("Concurrent owner acquired the lock")
    with instance_lock(context[0]):
        pass


def test_cli_submission_status_and_target_errors(worker, context, tmp_path, capsys):
    path = tmp_path / "manifest.json"
    path.write_bytes(encode(context[1]))
    args = [
        "--inbox",
        str(worker.inbox.root),
        "--instance",
        context[3].instance_ref,
        "--namespace",
        context[1]["namespace"],
    ]
    assert main([*args, "submit", "--manifest", str(path)]) == 0
    assert "QUEUED" in capsys.readouterr().out
    assert main([*args, "status", "--submission", context[1]["submission_id"]]) == 3
    worker.run()
    assert main([*args, "status", "--submission", context[1]["submission_id"]]) == 0
    assert "AWAITING_APPROVAL" in capsys.readouterr().out
    assert (
        main([*args[:4], "--namespace", "wrong", "submit", "--manifest", str(path)])
        == 2
    )


def test_inbox_cannot_be_rebound_to_another_database(worker, context):
    with sqlite3.connect(context[0]) as conn:
        conn.execute("UPDATE manual_import_instance SET instance_id='other'")
    with pytest.raises(ValueError, match="collision"):
        worker.initialize()


class RecordingGraph:
    def __init__(self):
        self.events = {}
        self.transactions = {}
        self.calls = []
        self.fail = False

    def create_event(self, calendar_id, payload, transaction_id):
        self.calls.append(
            ("create", calendar_id, payload.to_graph_dict(), transaction_id)
        )
        if self.fail:
            raise GraphClientError("injected")
        identifier = self.transactions.setdefault(
            transaction_id, f"event-{len(self.transactions) + 1}"
        )
        self.events[identifier] = payload.to_graph_dict()
        return OutlookEventReference(identifier)

    def update_event(self, calendar_id, event_id, payload):
        self.calls.append(("update", calendar_id, payload.to_graph_dict()))
        if self.fail:
            raise GraphClientError("injected")
        if event_id not in self.events:
            raise OutlookEventNotFoundError("gone")
        self.events[event_id] = payload.to_graph_dict()
        return OutlookEventReference(event_id)

    def delete_event(self, calendar_id, event_id):
        self.calls.append(("delete", calendar_id, event_id))
        if self.fail:
            raise GraphClientError("injected")
        if event_id not in self.events:
            raise OutlookEventNotFoundError("gone")
        del self.events[event_id]


@pytest.fixture
def reviews(service, context):
    service.apply(approved(service, context[1]))
    graph = RecordingGraph()
    repository = ManualReviewRepository(context[0])
    result = ManualReviewService(
        repository,
        cast(GraphClient, graph),
        "isolated-calendar",
        logging.getLogger("test"),
        lambda: datetime(2031, 1, 1, tzinfo=UTC),
    )
    return result, graph


def test_overdue_review_is_once_and_keeps_original_due_date(reviews, context):
    service, graph = reviews
    service.synchronize()
    assert len(graph.events) == len(context[1]["review_plan"]["tasks"])
    for payload in graph.events.values():
        assert payload["isReminderOn"] is True
        assert payload["start"]["timeZone"] == "W. Europe Standard Time"
        assert "attendees" not in payload
        assert "Original due time" in payload["body"]["content"]
    before = context[0].read_bytes()
    calls = len(graph.calls)
    service.clock = lambda: datetime(2032, 1, 1, tzinfo=UTC)
    service.synchronize()
    restarted = ManualReviewService(
        service.repository,
        cast(GraphClient, graph),
        service.calendar,
        logging.getLogger("test"),
        service.clock,
    )
    restarted.synchronize()
    assert len(graph.calls) == calls
    assert context[0].read_bytes() == before
    assert all(call[1] == "isolated-calendar" for call in graph.calls)


def test_graph_failure_retries_stable_creation_identity(reviews):
    service, graph = reviews
    graph.fail = True
    service.synchronize()
    first = {call[-1] for call in graph.calls if call[0] == "create"}
    assert graph.events == {}
    graph.fail = False
    service.synchronize()
    assert {call[-1] for call in graph.calls if call[0] == "create"} == first
    assert len(graph.events) == len(first)


def test_reminder_changes_and_completion_do_not_dirty_fixture(
    service, context, reviews
):
    review, graph = reviews
    review.synchronize()
    before = rows(context[0], "sports_events")
    raw = context[1]
    raw["submission_id"] = "changed-plan"
    raw["review_plan"]["tasks"][0]["due_at"] = "2031-02-01T12:00:00Z"
    raw["review_plan"]["tasks"][0]["reminder_minutes"] = 30
    service.apply(approved(service, raw))
    review.synchronize()
    assert graph.calls[-1][0] == "update"
    assert graph.calls[-1][2]["reminderMinutesBeforeStart"] == 30
    assert rows(context[0], "sports_events") == before
    raw["submission_id"] = "completed-plan"
    raw["review_plan"] = {
        "state": "complete",
        "tasks": [],
        "completion_note": "All fixtures final.",
    }
    service.apply(approved(service, raw))
    review.synchronize()
    assert graph.events == {}
    assert rows(context[0], "sports_events") == before
    calls = len(graph.calls)
    review.synchronize()
    assert len(graph.calls) == calls


def test_deleted_reminder_recreated_only_on_explicit_update(service, context, reviews):
    review, graph = reviews
    review.synchronize()
    graph.events.clear()
    count = len(graph.calls)
    review.synchronize()
    assert len(graph.calls) == count
    context[1]["submission_id"] = "task-correction"
    context[1]["review_plan"]["tasks"][0]["note"] = "Review corrected round."
    service.apply(approved(service, context[1]))
    review.synchronize()
    review.synchronize()
    assert len(graph.events) == 1
    assert len(graph.transactions) == len(context[1]["review_plan"]["tasks"]) + 1


def test_record_failure_after_graph_create_recovers_then_retires(
    reviews, service, context, monkeypatch
):
    review, graph = reviews
    original = review.repository.completed

    def fail(*args):
        raise sqlite3.OperationalError("injected")

    monkeypatch.setattr(review.repository, "completed", fail)
    with pytest.raises(sqlite3.OperationalError):
        review.synchronize()
    assert len(graph.events) == 1
    monkeypatch.setattr(review.repository, "completed", original)
    context[1]["submission_id"] = "retire-uncertain"
    context[1]["review_plan"] = {
        "state": "complete",
        "tasks": [],
        "completion_note": "Done.",
    }
    service.apply(approved(service, context[1]))
    review.synchronize()
    assert graph.events == {}
    assert len(graph.transactions) == 2


def test_container_wires_manual_job_without_provider(tmp_path):
    from app.application.container import ApplicationContainer

    from tests.application.test_container import create_settings

    settings = replace(create_settings(tmp_path), manual_import_root=tmp_path / "inbox")
    container = ApplicationContainer(settings)
    assert [job.job_key for job in container.scheduled_jobs] == [
        "system:manual-import",
        "system:calendar-synchronization",
    ]
    assert container.manual_import_worker is not None


@pytest.mark.parametrize(
    "change",
    [
        {"manual_import_limit": 0},
        {"manual_import_limit": 101},
        {"manual_import_interval": 0},
    ],
)
def test_invalid_worker_configuration_fails_early(tmp_path, change):
    from tests.application.test_container import create_settings

    with pytest.raises(ValueError):
        replace(create_settings(tmp_path), **change)


def test_persistence_failure_keeps_approval_transport_for_retry(worker, context):
    submit(worker, context)
    worker.run()
    worker.inbox.submit(
        "approve",
        context[1]["namespace"],
        context[1]["submission_id"],
        approval(worker, context),
    )
    with sqlite3.connect(context[0]) as conn:
        conn.execute("""CREATE TRIGGER reject_receipt
            BEFORE INSERT ON manual_import_receipts
            BEGIN SELECT RAISE(ABORT,'injected'); END""")
    worker.run()
    assert status(worker, context)["state"] == "RETRYABLE_FAILURE"
    assert rows(context[0], "sports_events") == []
    assert len(list((worker.inbox.root / "pending").glob("*.json"))) == 1
    with sqlite3.connect(context[0]) as conn:
        conn.execute("DROP TRIGGER reject_receipt")
    worker.run()
    assert status(worker, context)["state"] == "APPLIED"


def test_profile_startup_checks_instance_before_configuring(worker, context):
    profile = {**context[4], "instance_ref": "other-instance"}
    (worker.inbox.root / "profiles" / "bad.json").write_bytes(encode(profile))
    before = rows(context[0], "source_assignments")
    with pytest.raises(ValueError, match="another instance"):
        worker.initialize()
    assert rows(context[0], "source_assignments") == before


def test_cli_approval_and_invalid_approval_status(worker, context, tmp_path):
    submit(worker, context)
    worker.run()
    path = tmp_path / "approval.json"
    path.write_bytes(b"{}")
    args = [
        "--inbox",
        str(worker.inbox.root),
        "--instance",
        context[3].instance_ref,
        "--namespace",
        context[1]["namespace"],
    ]
    assert (
        main(
            [
                *args,
                "approve",
                "--submission",
                context[1]["submission_id"],
                "--approval",
                str(path),
            ]
        )
        == 0
    )
    worker.run()
    assert main([*args, "status", "--submission", context[1]["submission_id"]]) == 2
    path.write_bytes(approval(worker, context))
    assert (
        main(
            [
                *args,
                "approve",
                "--submission",
                context[1]["submission_id"],
                "--approval",
                str(path),
            ]
        )
        == 0
    )
    worker.run()
    assert main([*args, "status", "--submission", context[1]["submission_id"]]) == 0
    assert status(worker, context)["state"] == "APPLIED"


def test_disabled_namespace_retires_only_its_appointments(reviews, context):
    review, graph = reviews
    review.synchronize()
    fixture_rows = rows(context[0], "sports_events")
    with sqlite3.connect(context[0]) as conn:
        conn.execute(
            "UPDATE source_assignments SET is_enabled=0 WHERE namespace=?",
            (context[1]["namespace"],),
        )
    review.synchronize()
    assert graph.events == {}
    assert [r["id"] for r in rows(context[0], "sports_events")] == [
        r["id"] for r in fixture_rows
    ]


def test_reactivated_completed_task_gets_fresh_creation_identity(
    reviews, service, context
):
    review, graph = reviews
    review.synchronize()
    old_transactions = set(graph.transactions)
    plan = context[1]["review_plan"]
    context[1]["submission_id"] = "finish"
    context[1]["review_plan"] = {
        "state": "complete",
        "tasks": [],
        "completion_note": "Done.",
    }
    service.apply(approved(service, context[1]))
    review.synchronize()
    context[1]["submission_id"] = "reopen"
    context[1]["review_plan"] = plan
    service.apply(approved(service, context[1]))
    review.synchronize()
    assert len(graph.events) == len(plan["tasks"])
    assert len(set(graph.transactions) - old_transactions) == len(plan["tasks"])


def test_reminder_failures_do_not_starve_other_tasks(reviews):
    review, graph = reviews
    graph.fail = True
    review.synchronize(limit=1)
    first = graph.calls[0][-1]
    review.synchronize(limit=1)
    assert graph.calls[1][-1] != first


def test_compose_keeps_inbox_optional_in_persistent_volume():
    from pathlib import Path

    compose = (Path(__file__).parents[2] / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    assert "MANUAL_IMPORT_ROOT: ${MANUAL_IMPORT_ROOT:-}" in compose
    assert "MANUAL_IMPORT_INTERVAL: ${MANUAL_IMPORT_INTERVAL:-60}" in compose
    assert "MANUAL_IMPORT_LIMIT: ${MANUAL_IMPORT_LIMIT:-10}" in compose
    assert "smart_sports_data:/data" in compose
