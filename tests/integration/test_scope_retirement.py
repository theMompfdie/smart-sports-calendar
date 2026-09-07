"""Retirement, restart, history retention and recovery without live services."""

import json
import logging
import sqlite3
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.application.container import ApplicationContainer
from app.application.scope_retirement_service import ScopeRetirementService
from app.database.database import Database
from app.database.scope_retirement_repository import ScopeRetirementRepository
from app.database.source_assignments_repository import (
    SourceAssignmentsRepository,
)
from app.graph.client import GraphClientError
from app.imports.manual_inbox import encoded
from app.operations.instance_lock import instance_lock
from app.operations.season_retirement import main
from app.providers.contracts import SourceRole

from tests.database.test_source_assignments_repository import create_scope, write
from tests.imports.test_manual_end_to_end import CALENDAR, Harness, sample

DECISION = {
    "operator_ref": "test-operator",
    "evidence_ref": "complete-schedule-review-267",
    "completed_at": "2030-12-01T00:00:00Z",
    "grace_days": 14,
    "complete_schedule_confirmed": True,
}
NOW = datetime(2031, 1, 1, tzinfo=UTC)


def retirement(path):
    return ScopeRetirementService(
        ScopeRetirementRepository(path),
        CALENDAR,
        lambda: NOW,
        inbox_root=path.parent / "inbox",
    )


def deactivate(service, job):
    report = service.preview(job, DECISION)
    assert not report["blockers"], report
    return service.deactivate(job, DECISION, report["preview_sha256"])


def audit(path):
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT operation FROM scope_retirement_audit ORDER BY id"
        ).fetchall()


def test_retirement_restart_replay_and_late_correction_preserve_history(tmp_path):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    h.apply(raw)
    h.converge()
    before = h.snapshot()
    job = "manual:" + raw["namespace"]
    service = retirement(h.path)
    report = deactivate(service, job)
    assert report["status"] == "retiring"
    assert service.repository.blocked(job)
    with pytest.raises(ValueError, match="pending review"):
        service.reactivate(job, "operator", "late-correction")
    restarted = Harness(tmp_path, h.graph)
    assert restarted.converge().items_created == 0
    assert retirement(h.path).preview(job, DECISION)["status"] == "retired"
    count = len(h.graph.operations)
    deactivate(service, job)
    restarted.converge()
    assert len(h.graph.operations) == count
    after = h.snapshot()
    for table in (
        "sports_events",
        "event_participants",
        "source_mappings",
        "calendar_event_mappings",
        "manual_import_receipts",
        "source_assignments",
    ):
        assert after[table] == before[table], table
    assert audit(h.path) == [("deactivate",)]
    assert h.service.apply(raw["submission_id"])["canonical_status"] == "committed"
    raw["submission_id"] += "-late"
    with pytest.raises(ValueError, match="retired"):
        h.service.receive(encoded(raw))
    service.reactivate(job, "operator", "late-correction")
    service.reactivate(job, "operator", "late-correction")
    raw["fixtures"][0]["kickoff"] = "2030-09-16T19:00:00+02:00"
    h.apply(raw)
    assert h.converge().items_updated == 1
    assert audit(h.path) == [("deactivate",), ("reactivate",)]
    assert h.snapshot()["sports_events"][0][0] == before["sports_events"][0][0]


def test_stage_retirement_rejects_pending_batches_and_isolates_other_writer(tmp_path):
    h = Harness(tmp_path)
    b, c = sample("nations-league-b"), sample("nations-league-c")
    h.apply(b)
    h.apply(c)
    h.converge()
    other = [
        r
        for r in h.reviews.repository.snapshot(CALENDAR)[2]
        if r["namespace"] == c["namespace"]
    ]
    pending_ids = []
    for state in ("RECEIVED", "AWAITING_APPROVAL", "APPROVED"):
        pending = deepcopy(b)
        pending["submission_id"] += "-" + state.lower()
        h.service.receive(encoded(pending))
        if state != "RECEIVED":
            h.service.prepare(pending["submission_id"])
        if state == "APPROVED":
            h.stage(pending)
            h.service.approve(pending["submission_id"], h.approval(pending))
        pending_ids.append(pending["submission_id"])
    service = retirement(h.path)
    report = service.preview("manual:" + b["namespace"], DECISION)
    assert len(report["batches_to_reject"]) == 3
    deactivate(service, "manual:" + b["namespace"])
    h.converge()
    assert [
        r
        for r in h.reviews.repository.snapshot(CALENDAR)[2]
        if r["namespace"] == c["namespace"]
    ] == other
    for submission in pending_ids:
        with h.service.repository.transaction() as tx:
            assert tx.batch(submission)["state"] == "REJECTED"
            assert tx.batch(submission)["approval_payload"] is None
        with pytest.raises(ValueError):
            h.service.apply(submission)
        with pytest.raises(ValueError, match="retired"):
            h.service.prepare(submission)
    assert not service.repository.blocked("manual:" + c["namespace"])
    c["submission_id"] += "-update"
    c["fixtures"][0]["kickoff"] = "2030-09-16T19:00:00+02:00"
    h.apply(c)
    assert h.converge().items_updated == 1


@pytest.mark.parametrize(
    "change,blocker",
    [
        ({"grace_days": 365}, "correction_grace_period_not_elapsed"),
        ({"completed_at": "2030-01-01T00:00:00Z"}, "unresolved_or_later_fixtures"),
    ],
)
def test_preview_blocks_unsafe_completion(tmp_path, change, blocker):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    h.apply(raw)
    h.converge()
    service = retirement(h.path)
    decision = DECISION | change
    report = service.preview("manual:" + raw["namespace"], decision)
    assert blocker in report["blockers"]
    with pytest.raises(ValueError, match="Unsafe"):
        service.deactivate(report["job_key"], decision, report["preview_sha256"])
    assert audit(h.path) == []


def test_pending_graph_and_unknown_kickoff_fail_closed(tmp_path):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    h.apply(raw)
    service = retirement(h.path)
    job = "manual:" + raw["namespace"]
    assert "pending_fixture_graph_work" in service.preview(job, DECISION)["blockers"]
    h.converge()
    raw["submission_id"] += "-unknown"
    raw["fixtures"][0]["fixture_id"] += "-unpublished"
    raw["fixtures"][0]["away"]["participant_key"] = "demo-third"
    raw["fixtures"][0]["kickoff"] = None
    raw["fixtures"][0]["kickoff_confirmed"] = False
    h.apply(raw)
    assert any(
        "unresolved_manual_observations" in b
        for b in service.preview(job, DECISION)["blockers"]
    )


def test_stale_preview_and_instance_lock_block_mutation(tmp_path):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    h.apply(raw)
    h.converge()
    service = retirement(h.path)
    job = "manual:" + raw["namespace"]
    report = service.preview(job, DECISION)
    raw["submission_id"] += "-new"
    h.service.receive(encoded(raw))
    with pytest.raises(ValueError, match="stale"):
        service.deactivate(job, DECISION, report["preview_sha256"])
    with instance_lock(h.path), pytest.raises(RuntimeError, match="owns"):
        service.preview(job, DECISION)
    assert audit(h.path) == []


def test_graph_review_failure_recovers_after_restart(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    h.apply(raw)
    h.converge()
    service = retirement(h.path)
    job = "manual:" + raw["namespace"]
    deactivate(service, job)
    original = h.graph.delete_event
    monkeypatch.setattr(
        h.graph, "delete_event", Mock(side_effect=GraphClientError("temporary"))
    )
    h.converge()
    assert service.preview(job, DECISION)["status"] == "retiring"
    monkeypatch.setattr(h.graph, "delete_event", original)
    Harness(tmp_path, h.graph).converge()
    assert service.preview(job, DECISION)["status"] == "retired"


def test_broad_grant_restart_scheduler_gate_and_future_season(tmp_path):
    path = tmp_path / "sports.db"
    first, second, competition, season = create_scope(path)
    assignments = SourceAssignmentsRepository(path)
    broad = write("authority", first, competition, season, SourceRole.AUTHORITATIVE)
    assignments.synchronize((broad,))
    service = retirement(path)
    deactivate(service, "authority")
    Database(path).initialize()
    assignments.synchronize((broad,))
    assert assignments.get_all()[0].stages is None
    task = Mock()
    container = SimpleNamespace(
        scope_retirement_repository=service.repository, logger=logging.getLogger("test")
    )
    guarded = ApplicationContainer._retirement_guard(container, "authority", task)
    guarded()
    task.assert_not_called()
    with pytest.raises(sqlite3.IntegrityError, match="Reactivate"):
        assignments.synchronize((replace(broad, stages=frozenset({"league"})),))
    with (
        pytest.raises(sqlite3.IntegrityError, match="Overlapping"),
        assignments._connect() as conn,
    ):
        conn.execute("BEGIN IMMEDIATE")
        assignments.write_connection(
            conn, replace(broad, job_key="conflict", source_id=second), "t"
        )
    with sqlite3.connect(path) as conn:
        future = conn.execute(
            """INSERT INTO seasons
            (competition_id,season_key,name,created_at,updated_at)
            VALUES (?,'2031_32','Next season','t','t')""",
            (competition,),
        ).lastrowid
    future_job = replace(broad, job_key="next-season", season_id=future)
    assignments.synchronize((broad, future_job))
    assert not service.repository.blocked("next-season")
    service.reactivate("authority", "operator", "correction")
    guarded()
    task.assert_called_once()


def test_cli_validates_decision_and_previews_without_canonical_writes(tmp_path, capsys):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    decision = tmp_path / "decision.json"
    decision.write_text(json.dumps(DECISION))
    args = [
        "preview",
        "--database",
        str(h.path),
        "--calendar",
        CALENDAR,
        "--job",
        "manual:" + raw["namespace"],
        "--decision",
        str(decision),
        "--inbox",
        str(h.inbox.root),
    ]
    before = h.snapshot()
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "active"
    assert h.snapshot() == before
    decision.write_text(json.dumps(DECISION | {"complete_schedule_confirmed": False}))
    with pytest.raises(SystemExit) as result:
        main(args)
    assert result.value.code == 2


@pytest.mark.parametrize(
    "change",
    [
        {"complete_schedule_confirmed": False},
        {"grace_days": -1},
        {"grace_days": True},
        {"completed_at": "2030-12-01T00:00:00"},
        {"evidence_ref": "https://private.example/?token=secret"},
    ],
)
def test_invalid_completion_decision_is_rejected(tmp_path, change):
    h = Harness(tmp_path)
    with pytest.raises(ValueError):
        retirement(h.path).preview(
            "manual:" + sample("efl-cup")["namespace"], DECISION | change
        )
    assert audit(h.path) == []


def test_atomic_failure_rolls_back_gate_review_plan_and_batch_rejection(tmp_path):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    h.apply(raw)
    h.converge()
    raw["submission_id"] += "-pending"
    h.stage(raw)
    before = h.snapshot()
    with sqlite3.connect(h.path) as conn:
        conn.execute("""CREATE TRIGGER injected_retirement_failure
            BEFORE INSERT ON scope_retirement_audit
            BEGIN SELECT RAISE(ABORT,'injected'); END""")
    service = retirement(h.path)
    job = "manual:" + raw["namespace"]
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        deactivate(service, job)
    assert not service.repository.blocked(job)
    assert h.snapshot() == before
    with h.service.repository.transaction() as tx:
        assert tx.batch(raw["submission_id"])["state"] == "AWAITING_APPROVAL"
    with sqlite3.connect(h.path) as conn:
        conn.execute("DROP TRIGGER injected_retirement_failure")
    deactivate(service, job)
    assert service.repository.blocked(job)


def test_retired_scope_blocks_standalone_preview_and_canonical_import(tmp_path):
    from app.database.fixture_import_repository import (
        FixtureImportConflictError,
        FixtureImportRepository,
        FixtureImportScopeRecord,
    )
    from app.database.manual_preview_repository import ManualPreviewRepository
    from app.domain.competition_lifecycle import CompetitionLifecycleScope
    from app.imports.manual_manifest import parse_manifest

    h = Harness(tmp_path)
    raw = sample("efl-cup")
    h.apply(raw)
    h.converge()
    service = retirement(h.path)
    job = "manual:" + raw["namespace"]
    report = deactivate(service, job)
    with pytest.raises(ValueError, match="retired"):
        ManualPreviewRepository(h.path).read(parse_manifest(encoded(raw)))
    a = report["assignment"]
    scope = FixtureImportScopeRecord(
        a["competition_id"],
        a["season_id"],
        None,
        None,
        True,
        CompetitionLifecycleScope("knockout_cup", "partial"),
        False,
        "interrupted-observation",
        NOW,
    )
    repository = FixtureImportRepository(h.path)
    with (
        pytest.raises(FixtureImportConflictError, match="retired"),
        repository._connect() as conn,
    ):
        conn.execute("BEGIN IMMEDIATE")
        repository.import_in_transaction(
            conn, a["source_id"], (), scope, namespace=raw["namespace"]
        )


def test_retirement_migration_preserves_legacy_broad_assignment(tmp_path):
    from pathlib import Path
    from shutil import copy2
    from unittest.mock import patch

    legacy = tmp_path / "migrations"
    legacy.mkdir()
    for source in (Path(__file__).parents[2] / "app/database/migrations").glob("*.sql"):
        if source.name[:3] < "015":
            copy2(source, legacy / source.name)
    path = tmp_path / "legacy.db"
    with patch(
        "tests.database.test_source_assignments_repository.Database",
        side_effect=lambda p: Database(p, legacy),
    ):
        first, _, competition, season = create_scope(path)
    repository = SourceAssignmentsRepository(path)
    repository.synchronize(
        (write("authority", first, competition, season, SourceRole.AUTHORITATIVE),)
    )
    before = repository.get_all()
    Database(path).initialize()
    Database(path).initialize()
    assert repository.get_all() == before
    assert not ScopeRetirementRepository(path).blocked("authority")


def test_preview_includes_pending_transport_and_worker_rejects_after_retirement(
    tmp_path,
):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    h.apply(raw)
    h.converge()
    raw["submission_id"] += "-queued"
    digest = h.inbox.submit(
        "submit", raw["namespace"], raw["submission_id"], encoded(raw)
    )
    service = retirement(h.path)
    job = "manual:" + raw["namespace"]
    report = service.preview(job, DECISION)
    assert report["inbox_transport_in_boundary"] == [
        {
            "sha256": digest,
            "namespace": raw["namespace"],
            "submission_id": raw["submission_id"],
            "action": "submit",
        }
    ]
    deactivate(service, job)
    h.worker.run()
    assert h.status(raw)["state"] == "REJECTED"
    assert len(h.snapshot()["sports_events"]) == 1


def test_missing_inbox_blocks_manual_retirement(tmp_path):
    h = Harness(tmp_path)
    raw = sample("efl-cup")
    service = ScopeRetirementService(
        ScopeRetirementRepository(h.path), CALENDAR, lambda: NOW
    )
    report = service.preview("manual:" + raw["namespace"], DECISION)
    assert "manual_inbox_required" in report["blockers"]
