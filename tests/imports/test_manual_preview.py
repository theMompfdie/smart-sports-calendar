"""Manual preview integration and approval regressions, without live services."""

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.application.manual_preview_service import (
    ManualPreviewService,
    _record,
    parse_preview_configuration,
    plan_preview,
    validate_preview_approval,
)
from app.database.database import Database
from app.database.fixture_import_repository import (
    FixtureImportRepository,
    FixtureImportScopeRecord,
)
from app.database.manual_preview_repository import ManualPreviewRepository
from app.domain.competition_lifecycle import (
    CompetitionLifecycleScope,
    FixtureObservationScopeKind,
)
from app.imports.manual_authority import StageAuthority, validate_stage_authorities
from app.imports.manual_manifest import (
    ManifestApproval,
    ManifestValidationError,
    parse_manifest,
)
from app.operations.manual_import_preview import main

EXAMPLES = Path(__file__).resolve().parents[2] / "docs/examples/manual-import"
NOW = datetime(2030, 9, 10, tzinfo=UTC)


def encode(value):
    return json.dumps(value).encode("utf-8")


@pytest.fixture
def context(tmp_path):
    raw = json.loads((EXAMPLES / "efl-cup-initial.json").read_bytes())
    raw["fixtures"] = raw["fixtures"][:1]
    manifest = parse_manifest(encode(raw))
    config_raw = {
        "instance_ref": "test-staging",
        "namespace": raw["namespace"],
        "scope": {
            key: raw["scope"][key]
            for key in ("sport_key", "competition_key", "season_key")
        },
        "competition_format": "knockout_cup",
        "boundaries": raw["boundaries"],
    }
    config = parse_preview_configuration(encode(config_raw))
    path = tmp_path / "preview.sqlite"
    Database(path).initialize()
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO sports (id, sport_key, name, created_at,
            updated_at) VALUES (1, ?, 'Football', 't', 't')
            """,
            (raw["scope"]["sport_key"],),
        )
        conn.execute(
            """
            INSERT INTO competitions (id, sport_id, competition_key,
            name, competition_type, created_at, updated_at) VALUES (1,
            1, ?, 'Cup', 'knockout_cup', 't', 't')
            """,
            (raw["scope"]["competition_key"],),
        )
        conn.execute(
            """
            INSERT INTO seasons (id, competition_id, season_key, name,
            created_at, updated_at) VALUES (1, 1, ?, 'Season', 't',
            't')
            """,
            (raw["scope"]["season_key"],),
        )
        for index, key in enumerate(("demo-home", "demo-away"), 1):
            conn.execute(
                """
                INSERT INTO participants (id, sport_id,
                participant_key, participant_type, name, created_at,
                updated_at) VALUES (?, 1, ?, 'team', ?, 't', 't')
                """,
                (index, key, key),
            )
            conn.execute(
                """
                INSERT INTO season_participants (season_id,
                participant_id, created_at, updated_at) VALUES (1, ?,
                't', 't')
                """,
                (index,),
            )
        conn.execute(
            """
            INSERT INTO data_sources (id, source_key, name,
            created_at, updated_at) VALUES (1, 'manual', 'Manual',
            't', 't')
            """
        )
    return path, raw, manifest, config, config_raw


def report(context, raw=None):
    path, original, _, config, _ = context
    return ManualPreviewService(ManualPreviewRepository(path)).preview(
        encode(original if raw is None else raw), config
    )


def persist(context):
    path, _, manifest, config, _ = context
    state = ManualPreviewRepository(path).read(manifest)
    record = _record(manifest, manifest.fixtures[0], state)
    result = FixtureImportRepository(path).import_observation(
        1,
        (record,),
        FixtureImportScopeRecord(
            1,
            1,
            None,
            None,
            True,
            CompetitionLifecycleScope(
                config.profile.competition_format, FixtureObservationScopeKind.PARTIAL
            ),
            False,
            "test",
            manifest.provenance.observed_at,
        ),
    )
    return result.items[0].event_id


def approval(context, preview):
    manifest = context[2]
    return ManifestApproval(
        manifest.submission_id,
        manifest.import_type,
        manifest.schema_version,
        manifest.fingerprint,
        preview.fingerprint,
        context[3].instance_ref,
        "operator",
        datetime(2031, 1, 1, tzinfo=UTC),
    )


def test_read_only_repeat_is_deterministic_and_prohibits_writes(context):
    path = context[0]
    before = path.read_bytes()
    first = report(context)
    assert first.accepted
    assert first.to_dict()["summary"]["CREATE"] == 1
    assert first == report(context)
    assert path.read_bytes() == before
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM sports")
    finally:
        conn.close()


def test_missing_database_not_initialized(tmp_path, context):
    path = tmp_path / "missing" / "new.sqlite"
    with pytest.raises(FileNotFoundError):
        ManualPreviewRepository(path).read(context[2])
    assert not path.parent.exists()


def test_canonical_replay_matches_existing_importer(context):
    persist(context)
    before = context[0].read_bytes()
    planned = report(context)
    assert planned.accepted
    assert planned.to_dict()["summary"]["SKIP"] == 1
    assert context[0].read_bytes() == before
    persist(context)
    assert report(context).to_dict()["summary"]["SKIP"] == 1


@pytest.mark.parametrize(
    "status,decision", [("cancelled", "CANCEL"), ("postponed", "UPDATE")]
)
def test_explicit_lifecycle_updates(context, status, decision):
    persist(context)
    raw = context[1]
    raw["fixtures"][0]["status"] = status
    assert report(context).to_dict()["summary"][decision] == 1


def test_cancellation_without_mapping_rejects_whole_batch(context):
    context[1]["fixtures"][0]["status"] = "cancelled"
    planned = report(context)
    assert not planned.accepted
    assert planned.to_dict()["errors"][0]["record"] == 0


def test_unresolved_and_unknown_kickoff_follow_existing_rules(context):
    raw = context[1]
    # Use the schema's existing unresolved synthetic participant structure.
    sample = json.loads((EXAMPLES / "efl-cup-initial.json").read_bytes())
    raw["fixtures"] = [sample["fixtures"][1]]
    assert report(context).to_dict()["summary"]["DEFER"] == 1


def test_unknown_kickoff_retains_existing_time(context):
    persist(context)
    raw = context[1]
    raw["fixtures"][0]["kickoff"] = None
    raw["fixtures"][0]["kickoff_confirmed"] = False
    raw["fixtures"][0]["status"] = "postponed"
    planned = report(context).to_dict()
    assert planned["accepted"]
    assert "retaining_last_confirmed_kickoff" in planned["fixtures"][0]["warnings"]


def test_omission_and_new_round_do_not_reconcile(context):
    persist(context)
    raw = context[1]
    raw["fixtures"][0]["fixture_id"] = "new-round"
    # A second ID for the same matchup/boundary is never silently correlated.
    rejected = report(context)
    assert not rejected.accepted
    assert (
        rejected.to_dict()["errors"][0]["code"] == "candidate_identity_requires_review"
    )
    raw["fixtures"][0]["boundary"]["round_name"] = "later-round"
    raw["boundaries"].append({**raw["boundaries"][0], "round_name": "later-round"})
    new_config = {**context[4], "boundaries": raw["boundaries"]}
    cfg = parse_preview_configuration(encode(new_config))
    preview = ManualPreviewService(ManualPreviewRepository(context[0])).preview(
        encode(raw), cfg
    )
    assert preview.accepted
    assert preview.to_dict()["summary"]["CREATE"] == 1
    assert "DELETE" not in preview.to_dict()["summary"]


@pytest.mark.parametrize(
    "role,accepted",
    [
        ("authoritative", False),
        ("bootstrap", False),
        ("verification", True),
        ("disabled", True),
    ],
)
def test_current_broad_provider_assignment_cannot_be_relabelled_as_stage(
    context, role, accepted
):
    with sqlite3.connect(context[0]) as conn:
        conn.execute(
            """
            INSERT INTO data_sources (id, source_key, name,
            created_at, updated_at) VALUES (2, 'openligadb',
            'Provider', 't', 't')
            """
        )
        conn.execute(
            """
            INSERT INTO source_assignments (job_key, source_id,
            competition_id, season_id, role, interval_seconds,
            created_at, updated_at) VALUES ('league-a', 2, 1, 1, ?,
            60, 't', 't')
            """,
            (role,),
        )
    assert report(context).accepted is accepted


def test_reading_changes_does_not_issue_sql_mutations(context, monkeypatch):
    original = sqlite3.connect
    statements = []

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    assert report(context).accepted
    assert all(
        sql.lstrip().split()[0].upper() in {"SELECT", "BEGIN", "PRAGMA"}
        for sql in statements
    )


def test_approval_binding_and_state_change(context):
    reviewed = report(context)
    approved = approval(context, reviewed)
    validate_preview_approval(
        approved, context[2], reviewed, report(context), context[3]
    )
    persist(context)
    with pytest.raises(ValueError, match="stale"):
        validate_preview_approval(
            approved, context[2], reviewed, report(context), context[3]
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("instance_ref", "prod"),
        ("preview_sha256", "0" * 64),
        ("manifest_sha256", "0" * 64),
        ("submission_id", "other"),
        ("import_type", "fixture_result"),
    ],
)
def test_wrong_approval_is_rejected(context, field, value):
    reviewed = report(context)
    approved = replace(approval(context, reviewed), **{field: value})
    with pytest.raises(ValueError):
        validate_preview_approval(approved, context[2], reviewed, reviewed, context[3])


def test_relevant_catalog_change_invalidates_but_unrelated_runtime_log_does_not(
    context,
):
    initial = report(context)
    with sqlite3.connect(context[0]) as conn:
        conn.execute(
            "INSERT INTO system_status(started_at,status) VALUES ('t','started')"
        )
    assert report(context) == initial
    with sqlite3.connect(context[0]) as conn:
        conn.execute("UPDATE participants SET name='Renamed' WHERE id=1")
    assert report(context).fingerprint != initial.fingerprint


def test_review_plan_replacement_is_separate_from_fixture_operations(context):
    path, _, manifest, config, _ = context
    state = ManualPreviewRepository(path).read(manifest)
    first = plan_preview(manifest, config, state).to_dict()
    replay = plan_preview(
        manifest, config, replace(state, accepted_review_plan=manifest.review_plan)
    ).to_dict()
    assert first["fixtures"] == replay["fixtures"]
    assert first["review_appointments"][0]["decision"] == "CREATE"
    assert replay["review_appointments"][0]["decision"] == "SKIP"
    complete = replace(
        manifest.review_plan, state="complete", tasks=(), completion_note="Done"
    )
    done = plan_preview(
        replace(manifest, review_plan=complete),
        config,
        replace(state, accepted_review_plan=manifest.review_plan),
    ).to_dict()
    assert done["review_appointments"][0]["decision"] == "RETIRE"


def test_cli_has_no_bootstrap_and_returns_private_json(context, tmp_path, capsys):
    manifest_path, profile_path = tmp_path / "manifest.json", tmp_path / "profile.json"
    manifest_path.write_bytes(encode(context[1]))
    profile_path.write_bytes(encode(context[4]))
    before = hashlib.sha256(context[0].read_bytes()).digest()
    assert (
        main(
            [
                "--database",
                str(context[0]),
                "--profile",
                str(profile_path),
                "--manifest",
                str(manifest_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["accepted"]
    assert hashlib.sha256(context[0].read_bytes()).digest() == before


def test_stage_authority_proposal_rejects_overlap_and_broad_legacy_grants():
    isolated = tuple(
        StageAuthority(f"writer-{stage}", frozenset({stage})) for stage in "ABCD"
    )
    validate_stage_authorities(isolated)
    for conflict in (
        StageAuthority("broad", None),
        StageAuthority("duplicate", frozenset({"B"})),
    ):
        with pytest.raises(ValueError):
            validate_stage_authorities((*isolated, conflict))


def test_same_round_different_explicit_leg_is_not_correlated(context):
    persist(context)
    raw = context[1]
    raw["fixtures"][0]["fixture_id"] = "second-leg"
    raw["fixtures"][0]["leg"] = "second"
    preview = report(context)
    assert preview.accepted
    assert preview.to_dict()["summary"]["CREATE"] == 1


def test_duplicate_ids_for_one_match_reject_entire_batch(context):
    raw = context[1]
    raw["fixtures"].append({**raw["fixtures"][0], "fixture_id": "duplicate"})
    preview = report(context)
    assert not preview.accepted
    assert preview.to_dict()["errors"] == [
        {"record": 1, "code": "duplicate_fixture_candidate"}
    ]


def test_unknown_participant_is_record_level_error(context):
    context[1]["fixtures"][0]["away"]["participant_key"] = "unknown"
    result = report(context).to_dict()
    assert not result["accepted"]
    assert result["errors"][0]["record"] == 0


@pytest.mark.parametrize("change", ["authority", "membership", "source", "mapping"])
def test_additional_relevant_preconditions_invalidate_approval(context, change):
    reviewed = report(context)
    with sqlite3.connect(context[0]) as conn:
        if change == "authority":
            conn.execute("""
                INSERT INTO source_assignments
                (job_key,source_id,competition_id,season_id,role,
                 interval_seconds,created_at,updated_at)
                VALUES ('manual',1,1,1,'authoritative',60,'t','t')
            """)
        elif change == "membership":
            conn.execute("DELETE FROM season_participants WHERE participant_id=2")
        elif change == "source":
            conn.execute("UPDATE data_sources SET is_active=0 WHERE id=1")
    if change == "mapping":
        persist(context)
    current = report(context)
    with pytest.raises(ValueError):
        validate_preview_approval(
            approval(context, reviewed), context[2], reviewed, current, context[3]
        )


def test_identical_database_copy_is_a_different_target(context, tmp_path):
    reviewed = report(context)
    copy_path = tmp_path / "other.sqlite"
    copy_path.write_bytes(context[0].read_bytes())
    current = ManualPreviewService(ManualPreviewRepository(copy_path)).preview(
        encode(context[1]), context[3]
    )
    assert current.fingerprint != reviewed.fingerprint


def test_unresolved_existing_fixture_is_deferred_without_changes(context):
    persist(context)
    raw = context[1]
    raw["fixtures"][0]["away"] = {"resolution": "unresolved", "participant_key": None}
    before = context[0].read_bytes()
    assert report(context).to_dict()["summary"]["DEFER"] == 1
    assert context[0].read_bytes() == before
    raw["fixtures"][0]["status"] = "cancelled"
    with pytest.raises(ManifestValidationError, match="resolved participants"):
        report(context)


def test_mapped_event_in_another_stage_is_rejected(context):
    persist(context)
    with sqlite3.connect(context[0]) as conn:
        conn.execute("UPDATE sports_events SET stage='league_a_group_phase'")
    preview = report(context).to_dict()
    assert not preview["accepted"]
    assert preview["errors"][0]["code"] == "mapped_event_outside_authority"


def test_shared_provider_mapping_requires_explicit_handover(context):
    event_id = persist(context)
    with sqlite3.connect(context[0]) as conn:
        conn.execute("""INSERT INTO data_sources
            (id,source_key,name,created_at,updated_at)
            VALUES (2,'provider','Provider','t','t')""")
        conn.execute(
            """INSERT INTO source_mappings
            (source_id,object_type,internal_id,external_id,created_at,updated_at)
            VALUES (2,'event',?,'other','t','t')""",
            (event_id,),
        )
    assert not report(context).accepted


def test_overdue_review_task_remains_visible_and_reschedule_only_updates_review(
    context,
):
    path, _, manifest, config, _ = context
    state = ManualPreviewRepository(path).read(manifest)
    state = replace(state, accepted_review_plan=manifest.review_plan)
    old = plan_preview(manifest, config, state).to_dict()
    task = replace(
        manifest.review_plan.tasks[0], due_at=datetime(2000, 1, 1, tzinfo=UTC)
    )
    plan = replace(manifest.review_plan, tasks=(task,))
    new = plan_preview(replace(manifest, review_plan=plan), config, state).to_dict()
    assert new["accepted"]
    assert new["fixtures"] == old["fixtures"]
    assert new["review_appointments"][0]["decision"] == "UPDATE"


def test_tampered_serialized_report_cannot_be_approved(context):
    original = report(context)
    forged = replace(original, payload=original.payload.replace('"CREATE"', '"SKIP"'))
    with pytest.raises(ValueError, match="integrity"):
        validate_preview_approval(
            approval(context, original), context[2], forged, original, context[3]
        )


def test_manifest_formatting_requires_new_preview(context):
    reviewed = report(context)
    formatted = json.dumps(context[1], indent=2).encode("utf-8")
    current = ManualPreviewService(ManualPreviewRepository(context[0])).preview(
        formatted, context[3]
    )
    assert current.fingerprint != reviewed.fingerprint


def test_cli_rejects_without_leaking_missing_path(context, tmp_path, capsys):
    profile = tmp_path / "profile.json"
    profile.write_bytes(encode(context[4]))
    missing = tmp_path / "private-secret-name.json"
    assert (
        main(
            [
                "--database",
                str(context[0]),
                "--profile",
                str(profile),
                "--manifest",
                str(missing),
            ]
        )
        == 2
    )
    output = capsys.readouterr().out
    assert "private-secret" not in output
    assert not json.loads(output)["accepted"]


def test_live_wal_snapshot_includes_committed_changes(context):
    with sqlite3.connect(context[0]) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        initial = report(context)
        conn.execute("UPDATE participants SET name='WAL name' WHERE id=1")
        conn.commit()
        assert report(context).fingerprint != initial.fingerprint


@pytest.mark.parametrize(
    "name,kind",
    [
        ("austrian-bundesliga", "league"),
        ("fa-cup", "knockout_cup"),
        ("efl-cup", "knockout_cup"),
        ("uefa-conference-league", "hybrid_tournament"),
        ("nations-league-b", "hybrid_tournament"),
        ("nations-league-c", "hybrid_tournament"),
        ("nations-league-d", "hybrid_tournament"),
    ],
)
def test_all_seven_scope_shapes_preview_against_catalog(context, name, kind):
    raw = json.loads((EXAMPLES / f"{name}-initial.json").read_bytes())
    config_raw = {
        **context[4],
        "namespace": raw["namespace"],
        "scope": {
            key: raw["scope"][key]
            for key in ("sport_key", "competition_key", "season_key")
        },
        "competition_format": kind,
        "boundaries": raw["boundaries"],
    }
    with sqlite3.connect(context[0]) as conn:
        conn.execute(
            "UPDATE competitions SET competition_key=?,competition_type=?",
            (raw["scope"]["competition_key"], kind),
        )
    preview = ManualPreviewService(ManualPreviewRepository(context[0])).preview(
        encode(raw), parse_preview_configuration(encode(config_raw))
    )
    assert preview.accepted
    assert preview.to_dict()["summary"] == {
        "CREATE": 1,
        "DEFER": 1,
        "UPDATE": 0,
        "SKIP": 0,
        "CANCEL": 0,
    }


def test_cancellation_replay_and_reinstatement_match_canonical_behavior(context):
    persist(context)
    raw = context[1]
    raw["fixtures"][0]["status"] = "cancelled"
    cancelled = parse_manifest(encode(raw))
    changed_context = (*context[:2], cancelled, *context[3:])
    persist(changed_context)
    assert report(context).to_dict()["summary"]["SKIP"] == 1
    raw["fixtures"][0]["status"] = "scheduled"
    assert report(context).to_dict()["summary"]["UPDATE"] == 1
