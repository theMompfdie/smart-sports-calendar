"""Atomic manual apply, recovery and stage-isolation regression coverage."""

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from shutil import copy2

import pytest
from app.application.manual_import_service import ManualImportService
from app.database.database import Database
from app.database.manual_import_repository import ManualImportRepository
from app.database.source_assignments_repository import (
    SourceAssignmentsRepository,
    SourceAssignmentWrite,
)
from app.imports.manual_manifest import parse_manifest
from app.providers.contracts import SourceRole

from tests.imports.test_manual_preview import context as context
from tests.imports.test_manual_preview import encode


@pytest.fixture
def service(context):
    result = ManualImportService(
        ManualImportRepository(context[0]), lambda: datetime(2031, 1, 1, tzinfo=UTC)
    )
    result.configure(context[3])
    return result


def approved(service, raw):
    manifest = parse_manifest(encode(raw))
    service.receive(manifest.payload)
    preview = service.prepare(manifest.submission_id)
    assert preview.accepted, preview.to_dict()
    payload = {
        "submission_id": manifest.submission_id,
        "import_type": manifest.import_type,
        "schema_version": manifest.schema_version,
        "manifest_sha256": manifest.fingerprint,
        "preview_sha256": preview.fingerprint,
        "instance_ref": preview.to_dict()["instance_ref"],
        "operator_ref": "test-operator",
        "approved_at": "2031-01-01T00:00:00Z",
    }
    service.approve(manifest.submission_id, encode(payload))
    return manifest.submission_id


def rows(path, table):
    assert table in {
        "sports_events",
        "source_mappings",
        "manual_review_plans",
        "manual_import_receipts",
        "import_batches",
        "source_assignments",
    }
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table}")]


def test_atomic_receipt_plan_and_redelivery_are_idempotent(service, context):
    identifier = approved(service, context[1])
    receipt = service.apply(identifier)
    assert receipt["canonical_status"] == "committed"
    assert receipt["outlook_status"] == "pending"
    assert receipt["counts"]["CREATE"] == 1
    assert len(rows(context[0], "sports_events")) == 1
    assert len(rows(context[0], "manual_review_plans")) == 1
    assert rows(context[0], "import_batches")[0]["state"] == "APPLIED"
    before = context[0].read_bytes()
    assert service.receive(encode(context[1])) == "APPLIED"
    assert service.apply(identifier) == receipt
    assert context[0].read_bytes() == before


def test_unchanged_new_submission_keeps_event_revision_and_review_plan(
    service, context
):
    service.apply(approved(service, context[1]))
    original = rows(context[0], "sports_events")
    plan = rows(context[0], "manual_review_plans")
    context[1]["submission_id"] = "unchanged-redelivery"
    context[1]["provenance"]["prepared_at"] = "2030-09-02T11:00:00Z"
    result = service.apply(approved(service, context[1]))
    assert result["counts"]["SKIP"] == 1
    assert rows(context[0], "sports_events") == original
    assert rows(context[0], "manual_review_plans") == plan
    assert len(rows(context[0], "manual_import_receipts")) == 2


def test_receipt_failure_rolls_back_entire_batch_and_can_retry(service, context):
    context[1]["fixtures"].append(
        {**context[1]["fixtures"][0], "fixture_id": "second", "leg": "second"}
    )
    identifier = approved(service, context[1])
    with sqlite3.connect(context[0]) as conn:
        conn.execute("""CREATE TRIGGER injected_receipt_failure
            BEFORE INSERT ON manual_import_receipts
            BEGIN SELECT RAISE(ABORT,'injected'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        service.apply(identifier)
    for table in (
        "sports_events",
        "source_mappings",
        "manual_review_plans",
        "manual_import_receipts",
    ):
        assert rows(context[0], table) == []
    assert rows(context[0], "import_batches")[0]["state"] == "APPROVED"
    with sqlite3.connect(context[0]) as conn:
        conn.execute("DROP TRIGGER injected_receipt_failure")
    assert service.apply(identifier)["counts"]["CREATE"] == 2


def test_restart_and_backup_restore_keep_applied_receipt(service, context, tmp_path):
    identifier = approved(service, context[1])
    receipt = service.apply(identifier)
    backup = tmp_path / "restored.sqlite"
    copy2(context[0], backup)
    restored = ManualImportService(ManualImportRepository(backup))
    assert restored.apply(identifier) == receipt
    Database(backup).initialize()
    assert restored.apply(identifier) == receipt


def test_stale_catalog_after_approval_requires_new_review(service, context):
    identifier = approved(service, context[1])
    with sqlite3.connect(context[0]) as conn:
        conn.execute("UPDATE participants SET name='Changed' WHERE id=1")
    with pytest.raises(ValueError, match="new preview"):
        service.apply(identifier)
    assert rows(context[0], "import_batches")[0]["state"] == "NEEDS_REVIEW"
    assert rows(context[0], "sports_events") == []
    assert rows(context[0], "manual_review_plans") == []


def test_received_package_and_missing_approval_cannot_apply(service, context):
    service.receive(encode(context[1]))
    with pytest.raises(ValueError, match="approval"):
        service.apply(context[2].submission_id)
    assert rows(context[0], "sports_events") == []


def test_submission_identity_cannot_be_rebound(service, context):
    service.receive(encode(context[1]))
    context[1]["fixtures"][0]["city"] = "Changed"
    with pytest.raises(ValueError, match="different bytes"):
        service.receive(encode(context[1]))


def test_manual_grants_survive_automatic_bootstrap_without_fake_timer(service, context):
    repository = SourceAssignmentsRepository(context[0])
    before = repository.get_all()
    assert before[0].interval_seconds is None
    assert repository.synchronize(()) == before
    service.configure(context[3])
    assert repository.get_all() == before


def test_broad_provider_blocks_manual_registration_without_partial_profile(context):
    repository = SourceAssignmentsRepository(context[0])
    with sqlite3.connect(context[0]) as conn:
        conn.execute("""INSERT INTO data_sources
            (id,source_key,name,created_at,updated_at)
            VALUES (2,'openligadb','Provider','t','t')""")
    repository.synchronize(
        (SourceAssignmentWrite("league-a", 2, 1, 1, SourceRole.AUTHORITATIVE, 60),)
    )
    importer = ManualImportService(ManualImportRepository(context[0]))
    with pytest.raises(sqlite3.IntegrityError, match="Overlapping"):
        importer.configure(context[3])
    assert len(repository.get_all()) == 1
    with sqlite3.connect(context[0]) as conn:
        assert (
            conn.execute("SELECT count(*) FROM manual_import_profiles").fetchone()[0]
            == 0
        )


def test_nonoverlapping_stages_coexist_and_overlap_is_rejected(context):
    repo = SourceAssignmentsRepository(context[0])
    with sqlite3.connect(context[0]) as conn:
        conn.execute("""INSERT INTO data_sources
            (id,source_key,name,created_at,updated_at)
            VALUES (2,'openligadb','Provider','t','t')""")
    automated = SourceAssignmentWrite(
        "league-a",
        2,
        1,
        1,
        SourceRole.AUTHORITATIVE,
        60,
        stages=frozenset({"league_a_group_phase"}),
    )
    repo.synchronize((automated,))
    importer = ManualImportService(ManualImportRepository(context[0]))
    importer.configure(context[3])
    assert len(repo.get_all()) == 2
    assert len(repo.synchronize((automated,))) == 2
    conflicting = replace(
        context[3], profile=replace(context[3].profile, namespace="other")
    )
    with pytest.raises(sqlite3.IntegrityError):
        importer.configure(conflicting)
    assert len(repo.get_all()) == 2


def test_review_only_change_does_not_dirty_fixtures(service, context):
    service.apply(approved(service, context[1]))
    original = rows(context[0], "sports_events")
    context[1]["submission_id"] = "review-date-update"
    context[1]["review_plan"]["tasks"][0]["due_at"] = "2030-12-01T10:00:00Z"
    result = service.apply(approved(service, context[1]))
    assert result["counts"]["SKIP"] == 1
    assert rows(context[0], "sports_events") == original
    assert "2030-12-01" in rows(context[0], "manual_review_plans")[0]["plan_json"]


def test_explicit_cancellation_and_reinstatement_keep_identity(service, context):
    service.apply(approved(service, context[1]))
    original_id = rows(context[0], "sports_events")[0]["id"]
    for index, status in enumerate(("cancelled", "scheduled")):
        context[1]["submission_id"] = f"status-{index}"
        context[1]["fixtures"][0]["status"] = status
        service.apply(approved(service, context[1]))
        current = rows(context[0], "sports_events")[0]
        assert current["id"] == original_id
        assert current["status"] == status


def test_distinct_return_leg_never_uses_provider_pair_correlation(service, context):
    service.apply(approved(service, context[1]))
    context[1]["submission_id"] = "second-leg"
    context[1]["fixtures"][0]["fixture_id"] = "second-leg"
    context[1]["fixtures"][0]["leg"] = "second"
    assert service.apply(approved(service, context[1]))["counts"]["CREATE"] == 1
    assert len(rows(context[0], "sports_events")) == 2


def test_applied_package_and_receipt_are_immutable(service, context):
    service.apply(approved(service, context[1]))
    with sqlite3.connect(context[0]) as conn:
        for statement in (
            "UPDATE import_batches SET state='APPROVED'",
            "UPDATE manual_import_receipts SET receipt_json='{}'",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable|Immutable"):
                conn.execute(statement)


def test_graph_failure_does_not_rollback_canonical_batch_and_recovers(service, context):
    from typing import cast

    from app.database.calendar_event_mappings_repository import (
        CalendarEventMappingsRepository,
    )
    from app.database.sync_runs_repository import SyncRunsRepository
    from app.database.synchronization_query_repository import (
        SynchronizationQueryRepository,
    )
    from app.graph.client import GraphClient, GraphClientError
    from app.synchronization.event_synchronizer import EventSynchronizer
    from app.synchronization.outlook_event_payload_builder import (
        OutlookEventPayloadBuilder,
    )
    from app.synchronization.synchronization_orchestrator import (
        SynchronizationOrchestrator,
    )

    from tests.integration.provider_outlook_support import RecordingGraphClient

    graph = RecordingGraphClient()
    calendar = SynchronizationOrchestrator(
        query_repository=SynchronizationQueryRepository(context[0]),
        event_synchronizer=EventSynchronizer(
            OutlookEventPayloadBuilder(),
            cast(GraphClient, graph),
            CalendarEventMappingsRepository(context[0]),
        ),
        sync_runs_repository=SyncRunsRepository(context[0]),
    )
    identifier = approved(service, context[1])
    receipt = service.apply(identifier)
    assert not graph.operations
    graph.create_failure = GraphClientError("Injected Graph outage")
    assert calendar.synchronize("test-smart-calendar", 100).items_failed == 1
    assert service.apply(identifier) == receipt
    assert calendar.synchronize("test-smart-calendar", 100).items_created == 1
    assert len(graph.events) == 1
    assert context[1]["provenance"]["attribution"] in str(
        next(iter(graph.events.values()))
    )
    count = len(graph.operations)
    context[1]["submission_id"] = "unchanged-after-graph"
    service.apply(approved(service, context[1]))
    calendar.synchronize("test-smart-calendar", 100)
    assert len(graph.operations) == count
    assert all(op.calendar_id == "test-smart-calendar" for op in graph.operations)


def test_legacy_migration_preserves_events_assignments_and_revisions(context, tmp_path):
    from pathlib import Path

    from tests.imports.test_manual_preview import persist

    persist(context)
    migration_dir = tmp_path / "old-migrations"
    migration_dir.mkdir()
    for path in Path("app/database/migrations").glob("*.sql"):
        if int(path.name[:3]) < 13:
            copy2(path, migration_dir / path.name)
    legacy = tmp_path / "legacy.sqlite"
    Database(legacy, migration_dir).initialize()
    tables = (
        "sports",
        "competitions",
        "seasons",
        "participants",
        "season_participants",
        "data_sources",
        "sports_events",
        "event_participants",
        "source_mappings",
    )
    with sqlite3.connect(context[0]) as original, sqlite3.connect(legacy) as target:
        original.row_factory = sqlite3.Row
        for table in tables:
            for row in original.execute(f"SELECT * FROM {table}"):
                columns = ",".join(row.keys())
                marks = ",".join("?" for _ in row)
                target.execute(
                    f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(row)
                )
        target.execute("""INSERT INTO source_assignments
            (job_key,source_id,competition_id,season_id,role,interval_seconds,
             created_at,updated_at)
            VALUES ('legacy',1,1,1,'authoritative',60,'t','t')""")
    events = rows(legacy, "sports_events")
    assignments = rows(legacy, "source_assignments")
    Database(legacy).initialize()
    Database(legacy).initialize()
    assert rows(legacy, "sports_events") == events
    actual = rows(legacy, "source_assignments")[0]
    assert actual == {**assignments[0], "namespace": None, "stages_json": None}
    with sqlite3.connect(legacy) as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        identity = conn.execute(
            "SELECT instance_id FROM manual_import_instance"
        ).fetchone()[0]
    Database(legacy).initialize()
    with sqlite3.connect(legacy) as conn:
        assert (
            conn.execute("SELECT instance_id FROM manual_import_instance").fetchone()[0]
            == identity
        )


def test_nations_league_bcd_apply_preserves_automated_a(context):
    from app.application.manual_preview_service import (
        manual_fixture_record,
        parse_preview_configuration,
    )
    from app.database.fixture_import_repository import (
        FixtureImportRepository,
        FixtureImportScopeRecord,
    )
    from app.database.manual_preview_repository import ManualPreviewRepository
    from app.domain.competition_lifecycle import (
        CompetitionFormat,
        CompetitionLifecycleScope,
        FixtureObservationScopeKind,
    )

    from tests.imports.test_manual_preview import EXAMPLES

    raw_b = json.loads((EXAMPLES / "nations-league-b-initial.json").read_bytes())
    with sqlite3.connect(context[0]) as conn:
        conn.execute("""UPDATE competitions SET competition_key='uefa_nations_league',
            competition_type='hybrid_tournament'""")
        conn.execute("""INSERT INTO data_sources
            (id,source_key,name,created_at,updated_at)
            VALUES (2,'openligadb','Provider','t','t')""")
    a_stage = "league_a_group_phase"
    assignments = SourceAssignmentsRepository(context[0])
    a = SourceAssignmentWrite(
        "league-a", 2, 1, 1, SourceRole.AUTHORITATIVE, 60, stages=frozenset({a_stage})
    )
    assignments.synchronize((a,))
    manifest = parse_manifest(encode(raw_b))
    state = ManualPreviewRepository(context[0]).read(manifest)
    record_a = replace(
        manual_fixture_record(manifest, manifest.fixtures[0], state),
        stage=a_stage,
        external_id="a-1",
        event_key_prefix="openligadb",
    )
    scope = FixtureImportScopeRecord(
        1,
        1,
        None,
        None,
        True,
        CompetitionLifecycleScope(
            CompetitionFormat.HYBRID_TOURNAMENT, FixtureObservationScopeKind.PARTIAL
        ),
        False,
        "a-snapshot",
        manifest.provenance.observed_at,
    )
    canonical = FixtureImportRepository(context[0])
    canonical.import_observation(2, (record_a,), scope)
    original_a = rows(context[0], "sports_events")[0]
    importer = ManualImportService(
        ManualImportRepository(context[0]), lambda: datetime(2031, 1, 1, tzinfo=UTC)
    )
    for league in "bcd":
        raw = json.loads(
            (EXAMPLES / f"nations-league-{league}-initial.json").read_bytes()
        )
        profile = {
            "instance_ref": "test-staging",
            "namespace": raw["namespace"],
            "scope": {
                key: raw["scope"][key]
                for key in ("sport_key", "competition_key", "season_key")
            },
            "competition_format": "hybrid_tournament",
            "boundaries": raw["boundaries"],
        }
        importer.configure(parse_preview_configuration(encode(profile)))
        assert importer.apply(approved(importer, raw))["counts"]["CREATE"] == 1
    assert len(rows(context[0], "sports_events")) == 4
    assert rows(context[0], "sports_events")[0] == original_a
    assignments.synchronize((a,))
    assert len(assignments.get_all(enabled_only=True)) == 4
    from app.database.fixture_import_repository import FixtureImportConflictError

    with pytest.raises(FixtureImportConflictError, match="authority"):
        canonical.import_observation(
            2, (replace(record_a, stage="league_b_group_phase"),), scope
        )
    assert rows(context[0], "sports_events")[0] == original_a


def test_wrong_instance_profile_cannot_rebind_database(service, context):
    before = rows(context[0], "source_assignments")
    with pytest.raises(ValueError, match="another configured instance"):
        service.configure(replace(context[3], instance_ref="production"))
    assert rows(context[0], "source_assignments") == before


def test_disabled_manual_grant_invalidates_approval(service, context):
    identifier = approved(service, context[1])
    with sqlite3.connect(context[0]) as conn:
        conn.execute("UPDATE source_assignments SET is_enabled=0")
    with pytest.raises(ValueError, match="new preview"):
        service.apply(identifier)
    assert rows(context[0], "sports_events") == []
    assert rows(context[0], "import_batches")[0]["state"] == "NEEDS_REVIEW"


def test_automatic_staged_authority_cannot_reconcile_another_stage(context):
    from app.database.fixture_import_repository import (
        FixtureImportConflictError,
        FixtureImportRepository,
        FixtureImportScopeRecord,
    )
    from app.domain.competition_lifecycle import (
        CompetitionFormat,
        CompetitionLifecycleScope,
        FixtureObservationScopeKind,
        TournamentStageKind,
    )

    with sqlite3.connect(context[0]) as conn:
        conn.execute("UPDATE competitions SET competition_type='hybrid_tournament'")
        conn.execute("""INSERT INTO data_sources
            (id,source_key,name,created_at,updated_at)
            VALUES (2,'openligadb','Provider','t','t')""")
    SourceAssignmentsRepository(context[0]).synchronize(
        (
            SourceAssignmentWrite(
                "league-a",
                2,
                1,
                1,
                SourceRole.AUTHORITATIVE,
                60,
                stages=frozenset({"league_a_group_phase"}),
            ),
        )
    )
    scope = FixtureImportScopeRecord(
        1,
        1,
        None,
        None,
        True,
        CompetitionLifecycleScope(
            CompetitionFormat.HYBRID_TOURNAMENT,
            FixtureObservationScopeKind.COMPLETE_STAGE,
            stage="league_b_group_phase",
            stage_kind=TournamentStageKind.LEAGUE_PHASE,
        ),
        False,
        "bad-removal",
        datetime(2030, 9, 1, tzinfo=UTC),
    )
    with pytest.raises(FixtureImportConflictError, match="Removal exceeds"):
        FixtureImportRepository(context[0]).import_observation(2, (), scope)


def test_source_jobs_accept_explicit_disjoint_stage_authorities(monkeypatch):
    from app.config.settings import load_source_jobs

    jobs = [
        {
            "job_key": f"job-{letter}",
            "source_key": f"provider-{letter}",
            "sport_key": "football",
            "competition_key": "uefa_nations_league",
            "season_key": "2026_27",
            "role": "authoritative",
            "interval_seconds": 60,
            "authority_stages": [f"league_{letter}_group_phase"],
        }
        for letter in "ab"
    ]
    monkeypatch.setenv("SOURCE_JOBS_JSON", json.dumps(jobs))
    assert load_source_jobs()[0].authority_stages == frozenset({"league_a_group_phase"})
    jobs[1]["authority_stages"] = jobs[0]["authority_stages"]
    monkeypatch.setenv("SOURCE_JOBS_JSON", json.dumps(jobs))
    with pytest.raises(ValueError, match="authoritative"):
        load_source_jobs()
    jobs[1]["authority_stages"] = []
    monkeypatch.setenv("SOURCE_JOBS_JSON", json.dumps(jobs))
    with pytest.raises(ValueError, match="authority_stages"):
        load_source_jobs()
