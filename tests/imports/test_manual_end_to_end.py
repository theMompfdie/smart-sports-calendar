"""Seven-scope inbox-to-canonical-to-Graph regression and isolated restore."""

import json
import logging
import sqlite3
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from shutil import copytree
from typing import cast

import pytest
from app.application.manual_import_service import ManualImportService
from app.application.manual_import_worker import ManualImportWorker
from app.application.manual_preview_service import parse_preview_configuration
from app.application.manual_review_service import ManualReviewService
from app.database.calendar_event_mappings_repository import (
    CalendarEventMappingsRepository,
)
from app.database.database import Database
from app.database.manual_import_repository import ManualImportRepository
from app.database.manual_review_repository import ManualReviewRepository
from app.database.sync_runs_repository import SyncRunsRepository
from app.database.synchronization_query_repository import SynchronizationQueryRepository
from app.graph.client import GraphClient, GraphClientError
from app.imports.manual_inbox import ManualInbox, encoded
from app.imports.manual_manifest import parse_manifest
from app.synchronization.event_synchronizer import EventSynchronizer
from app.synchronization.outlook_event_payload_builder import OutlookEventPayloadBuilder
from app.synchronization.synchronization_orchestrator import SynchronizationOrchestrator

from tests.integration.provider_outlook_support import RecordingGraphClient

TARGETS = {
    "austrian-bundesliga": "league",
    "fa-cup": "knockout_cup",
    "efl-cup": "knockout_cup",
    "uefa-conference-league": "hybrid_tournament",
    "nations-league-b": "hybrid_tournament",
    "nations-league-c": "hybrid_tournament",
    "nations-league-d": "hybrid_tournament",
}
EXAMPLES = Path(__file__).parents[2] / "docs/examples/manual-import"
NOW = datetime(2031, 1, 1, tzinfo=UTC)
CALENDAR = "isolated-manual-regression"


def sample(target):
    raw = json.loads((EXAMPLES / f"{target}-initial.json").read_bytes())
    raw["fixtures"] = raw["fixtures"][:1]
    return raw


class Harness:
    def __init__(self, root: Path, graph=None):
        self.root = root
        root.mkdir(exist_ok=True)
        self.path = root / "sports.db"
        fresh = not self.path.exists()
        Database(self.path).initialize()
        self.service = ManualImportService(
            ManualImportRepository(self.path), lambda: NOW
        )
        if fresh:
            self.seed()
        self.inbox = ManualInbox(root / "inbox", "regression-staging")
        self.worker = ManualImportWorker(
            self.inbox, self.service, logging.getLogger("test"), 100
        )
        self.worker.initialize()
        self.graph = graph or RecordingGraphClient()
        self.calendar = SynchronizationOrchestrator(
            query_repository=SynchronizationQueryRepository(self.path),
            event_synchronizer=EventSynchronizer(
                OutlookEventPayloadBuilder(),
                cast(GraphClient, self.graph),
                CalendarEventMappingsRepository(self.path),
            ),
            sync_runs_repository=SyncRunsRepository(self.path),
        )
        self.reviews = ManualReviewService(
            ManualReviewRepository(self.path),
            cast(GraphClient, self.graph),
            CALENDAR,
            logging.getLogger("test"),
            lambda: NOW,
        )

    def seed(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("""INSERT INTO sports(id,sport_key,name,created_at,updated_at)
                VALUES(1,'football','Football','t','t')""")
            for index, name in enumerate(("demo-home", "demo-away", "demo-third"), 1):
                conn.execute(
                    """INSERT INTO participants
                    (id,sport_id,participant_key,participant_type,name,created_at,updated_at)
                    VALUES(?,1,?,'team',?,'t','t')""",
                    (index, name, name),
                )
            seen = {}
            for target, format_name in TARGETS.items():
                raw = sample(target)
                key = raw["scope"]["competition_key"]
                if key in seen:
                    continue
                scope_id = len(seen) + 1
                seen[key] = scope_id
                conn.execute(
                    """INSERT INTO competitions
                    (id,sport_id,competition_key,name,competition_type,created_at,updated_at)
                    VALUES(?,1,?,?,?,'t','t')""",
                    (scope_id, key, key, format_name),
                )
                conn.execute(
                    """INSERT INTO seasons
                    (id,competition_id,season_key,name,created_at,updated_at)
                    VALUES(?,?,?,'Synthetic season','t','t')""",
                    (scope_id, scope_id, raw["scope"]["season_key"]),
                )
                for participant in (1, 2, 3):
                    conn.execute(
                        """INSERT INTO season_participants
                        (season_id,participant_id,created_at,updated_at)
                        VALUES(?,?,'t','t')""",
                        (scope_id, participant),
                    )
        for target, format_name in TARGETS.items():
            raw = sample(target)
            profile = {
                "instance_ref": "regression-staging",
                "namespace": raw["namespace"],
                "scope": {
                    k: raw["scope"][k]
                    for k in ("sport_key", "competition_key", "season_key")
                },
                "competition_format": format_name,
                "boundaries": raw["boundaries"],
            }
            self.service.configure(parse_preview_configuration(encoded(profile)))

    def status(self, raw):
        return self.inbox.status(raw["namespace"], raw["submission_id"])

    def stage(self, raw):
        self.inbox.submit(
            "submit", raw["namespace"], raw["submission_id"], encoded(raw)
        )
        self.worker.run()
        return self.status(raw)

    def approval(self, raw):
        report = self.status(raw)
        return encoded(
            {
                "submission_id": raw["submission_id"],
                "import_type": "fixture_schedule",
                "schema_version": 1,
                "manifest_sha256": parse_manifest(encoded(raw)).fingerprint,
                "preview_sha256": report["preview_sha256"],
                "instance_ref": "regression-staging",
                "operator_ref": "test-operator",
                "approved_at": "2031-01-01T00:00:00Z",
            }
        )

    def apply(self, raw):
        report = self.stage(raw)
        assert report["state"] in {"AWAITING_APPROVAL", "APPLIED"}, report
        if report["state"] != "APPLIED":
            self.inbox.submit(
                "approve", raw["namespace"], raw["submission_id"], self.approval(raw)
            )
            self.worker.run()
        assert self.status(raw)["state"] == "APPLIED", self.status(raw)

    def converge(self):
        result = self.calendar.synchronize(CALENDAR, 100)
        self.reviews.synchronize(100)
        return result

    def snapshot(self):
        tables = (
            "sports_events",
            "event_participants",
            "source_mappings",
            "calendar_event_mappings",
            "manual_review_appointments",
            "manual_import_receipts",
            "manual_review_plans",
            "source_assignments",
        )
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            result = {}
            for name in tables:
                # mark_checked deliberately refreshes audit time without a Graph write.
                volatile = (
                    {"last_synced_at", "updated_at"}
                    if name == "calendar_event_mappings"
                    else set()
                )
                result[name] = [
                    tuple(
                        value for key, value in dict(row).items() if key not in volatile
                    )
                    for row in conn.execute(f"SELECT * FROM {name} ORDER BY rowid")
                ]
            return result


@pytest.mark.parametrize("target", TARGETS)
def test_seven_targets_full_lifecycle_and_review_isolation(tmp_path, target):
    h = Harness(tmp_path)
    raw = sample(target)
    h.apply(raw)
    assert h.converge().items_created == 1
    first = h.snapshot()
    fixture_id = first["sports_events"][0][0]
    mapping = first["calendar_event_mappings"][0]
    original_review_events = {
        r["event_id"] for r in h.reviews.repository.snapshot(CALENDAR)[2]
    }
    raw["submission_id"] += "-corrected"
    raw["fixtures"][0]["kickoff"] = "2030-09-16T19:00:00+02:00"
    raw["fixtures"][0]["away"]["participant_key"] = "demo-third"
    h.apply(raw)
    assert h.converge().items_updated == 1
    assert h.snapshot()["sports_events"][0][0] == fixture_id
    assert h.snapshot()["calendar_event_mappings"][0][0] == mapping[0]
    for status in ("postponed", "scheduled", "cancelled"):
        raw["submission_id"] += "-" + status
        raw["fixtures"][0]["status"] = status
        h.apply(raw)
        assert h.converge().items_failed == 0
    assert {
        r["event_id"] for r in h.reviews.repository.snapshot(CALENDAR)[2]
    } == original_review_events
    before = h.snapshot()
    count = len(h.graph.operations)
    h.apply(raw)
    h.converge()
    restarted = Harness(tmp_path, h.graph)
    restarted.converge()
    assert restarted.snapshot() == before
    assert len(h.graph.operations) == count
    assert all(op.calendar_id == CALENDAR for op in h.graph.operations)


def test_review_only_manifest_creates_one_idempotent_outlook_appointment(tmp_path):
    h = Harness(tmp_path)
    raw = sample("fa-cup")
    raw["submission_id"] = "fa-cup-review-only"
    raw["fixtures"] = []

    h.apply(raw)
    receipt = h.status(raw)["receipt"]
    assert receipt["items"] == []
    assert set(receipt["counts"].values()) == {0}
    assert h.converge().items_created == 0
    first = h.snapshot()
    assert first["sports_events"] == []
    assert len(first["manual_review_appointments"]) == 1
    operation_count = len(h.graph.operations)

    h.apply(raw)
    assert h.converge().items_created == 0
    assert h.snapshot() == first
    assert len(h.graph.operations) == operation_count


def test_all_seven_scopes_coexist_and_partial_updates_preserve_others(tmp_path):
    h = Harness(tmp_path)
    for target in TARGETS:
        h.apply(sample(target))
    assert h.converge().items_created == 7
    before = h.snapshot()
    raw = sample("nations-league-c")
    raw["submission_id"] += "-rescheduled"
    raw["fixtures"][0]["kickoff"] = "2030-09-18T20:00:00+02:00"
    h.apply(raw)
    assert h.converge().items_updated == 1
    after = h.snapshot()
    assert len(after["sports_events"]) == 7
    assert (
        sum(
            old != new
            for old, new in zip(
                before["sports_events"], after["sports_events"], strict=True
            )
        )
        == 1
    )
    assert before["manual_review_appointments"] == after["manual_review_appointments"]
    assert before["source_mappings"] == after["source_mappings"]


def test_isolated_backup_restore_keeps_receipts_mappings_and_overdue_projection(
    tmp_path,
):
    root = tmp_path / "original"
    h = Harness(root)
    for target in TARGETS:
        h.apply(sample(target))
    h.converge()
    before = h.snapshot()
    copytree(root, tmp_path / "restored")
    restored = Harness(tmp_path / "restored", deepcopy(h.graph))
    count = len(restored.graph.operations)
    for target in TARGETS:
        restored.apply(sample(target))
    restored.converge()
    assert restored.snapshot() == before
    assert len(restored.graph.operations) == count
    assert h.snapshot() == before


def test_restore_invalidates_pending_approval_without_losing_completed_state(tmp_path):
    root = tmp_path / "original"
    h = Harness(root)
    h.apply(sample("fa-cup"))
    h.converge()
    raw = sample("efl-cup")
    h.stage(raw)
    approval = h.approval(raw)
    h.inbox.submit("approve", raw["namespace"], raw["submission_id"], approval)
    copytree(root, tmp_path / "restored")
    restored = Harness(tmp_path / "restored", deepcopy(h.graph))
    before = restored.snapshot()
    restored.worker.run()
    assert restored.status(raw)["state"] == "NEEDS_REVIEW"
    assert restored.snapshot() == before
    restored.inbox.submit("preview", raw["namespace"], raw["submission_id"])
    restored.worker.run()
    restored.apply(raw)
    assert restored.converge().items_created == 1
    assert len(h.snapshot()["sports_events"]) == 1


def test_downstream_failures_recover_both_flows_without_new_receipts(tmp_path):
    h = Harness(tmp_path)
    raw = sample("uefa-conference-league")
    h.apply(raw)
    before = h.snapshot()["manual_import_receipts"]
    h.graph.create_failure = GraphClientError("Injected transient failure")
    assert h.calendar.synchronize(CALENDAR, 100).items_failed == 1
    h.graph.create_failure = GraphClientError("Injected throttling boundary failure")
    h.reviews.synchronize(100)
    h.converge()
    assert h.snapshot()["manual_import_receipts"] == before
    count = len(h.graph.operations)
    h.converge()
    assert len(h.graph.operations) == count
    assert len(h.graph.events) == 1 + len(raw["review_plan"]["tasks"])


def test_rejected_mixed_scope_package_preserves_both_calendar_flows(tmp_path):
    h = Harness(tmp_path)
    raw = sample("nations-league-b")
    h.apply(raw)
    h.converge()
    before = h.snapshot()
    changed = deepcopy(raw)
    changed["submission_id"] += "-invalid"
    changed["fixtures"][0]["boundary"]["stage"] = "league_a_group_phase"
    h.stage(changed)
    assert h.status(changed)["state"] == "REJECTED"
    count = len(h.graph.operations)
    h.converge()
    assert h.snapshot() == before
    assert len(h.graph.operations) == count


@pytest.fixture
def http_graph(monkeypatch):
    from http.client import HTTPMessage
    from io import BytesIO
    from unittest.mock import Mock
    from urllib.error import HTTPError

    state = {"failure": None, "events": {}, "transactions": {}, "calls": []}

    def request(req, timeout):
        state["calls"].append((req.method, req.full_url))
        if state["failure"]:
            code = state["failure"]
            state["failure"] = None
            raise HTTPError(req.full_url, code, "injected", HTTPMessage(), None)
        payload = json.loads(req.data) if req.data else {}
        if req.method == "POST":
            transaction = payload["transactionId"]
            event = state["transactions"].setdefault(
                transaction, f"event-{len(state['transactions']) + 1}"
            )
        else:
            event = req.full_url.rsplit("/", 1)[-1]
            if event not in state["events"]:
                raise HTTPError(req.full_url, 404, "missing", HTTPMessage(), None)
        if req.method == "DELETE":
            del state["events"][event]
            return BytesIO(b"")
        state["events"][event] = payload
        return BytesIO(encoded({"id": event}))

    monkeypatch.setattr("app.graph.client.urlopen", request)
    token = Mock()
    token.get_access_token.return_value = "synthetic-test-token"
    graph = GraphClient("https://graph.microsoft.com/v1.0", "test-user", token)
    return graph, state


@pytest.mark.parametrize("http_status", [429, 503])
def test_real_graph_adapter_failure_recovers_both_flows(
    tmp_path, http_graph, http_status
):
    graph, state = http_graph
    h = Harness(tmp_path, graph)
    raw = sample("efl-cup")
    h.apply(raw)
    receipts = h.snapshot()["manual_import_receipts"]
    state["failure"] = http_status
    assert h.calendar.synchronize(CALENDAR, 100).items_failed == 1
    state["failure"] = http_status
    h.reviews.synchronize(100)
    h.converge()
    assert h.snapshot()["manual_import_receipts"] == receipts
    assert len(state["events"]) == 1 + len(raw["review_plan"]["tasks"])
    calls = len(state["calls"])
    h.converge()
    assert len(state["calls"]) == calls
    assert all(f"/calendars/{CALENDAR}/events" in url for _, url in state["calls"])


def test_real_graph_404_on_updated_review_recreates_only_that_task(
    tmp_path, http_graph
):
    graph, state = http_graph
    h = Harness(tmp_path, graph)
    raw = sample("efl-cup")
    h.apply(raw)
    h.converge()
    mappings = h.reviews.repository.snapshot(CALENDAR)[2]
    task_id = raw["review_plan"]["tasks"][0]["task_id"]
    original = next(row for row in mappings if row["task_id"] == task_id)
    del state["events"][original["event_id"]]
    fixture_mapping = h.snapshot()["calendar_event_mappings"]
    raw["submission_id"] += "-review-correction"
    raw["review_plan"]["tasks"][0]["note"] = "Check corrected publication."
    h.apply(raw)
    h.reviews.synchronize(100)
    h.reviews.synchronize(100)
    current = next(
        row
        for row in h.reviews.repository.snapshot(CALENDAR)[2]
        if row["task_id"] == task_id
    )
    assert current["event_id"] != original["event_id"]
    assert current["event_id"] in state["events"]
    assert current["applied_hash"] == current["desired_hash"]
    assert h.snapshot()["calendar_event_mappings"] == fixture_mapping
