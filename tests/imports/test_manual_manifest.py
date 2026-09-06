"""Network-free regression coverage for untrusted manual import packages."""

import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.domain.competition_lifecycle import CompetitionFormat
from app.imports.manual_manifest import (
    MAX_BYTES,
    MAX_FIXTURES,
    ManifestScope,
    ManifestValidationError,
    ManualSourceProfile,
    parse_approval,
    parse_manifest,
    validate_profile,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "docs/examples/manual-import"


def sample():
    return json.loads((EXAMPLES / "efl-cup-initial.json").read_bytes())


def encoded(value):
    return json.dumps(value, ensure_ascii=True).encode("utf-8")


def profile(manifest, kind=CompetitionFormat.KNOCKOUT_CUP):
    return ManualSourceProfile(
        manifest.namespace,
        manifest.scope,
        kind,
        frozenset(manifest.boundaries),
        frozenset({"demo-home", "demo-away"}),
    )


@pytest.mark.parametrize(
    "name,kind",
    [
        ("austrian-bundesliga", CompetitionFormat.LEAGUE),
        ("fa-cup", CompetitionFormat.KNOCKOUT_CUP),
        ("efl-cup", CompetitionFormat.KNOCKOUT_CUP),
        ("uefa-conference-league", CompetitionFormat.HYBRID_TOURNAMENT),
        ("nations-league-b", CompetitionFormat.HYBRID_TOURNAMENT),
        ("nations-league-c", CompetitionFormat.HYBRID_TOURNAMENT),
        ("nations-league-d", CompetitionFormat.HYBRID_TOURNAMENT),
    ],
)
def test_all_target_examples_and_corrections_preserve_identity(name, kind):
    first_bytes = (EXAMPLES / f"{name}-initial.json").read_bytes()
    first = parse_manifest(first_bytes)
    corrected = parse_manifest((EXAMPLES / f"{name}-corrected.json").read_bytes())
    validate_profile(first, profile(first, kind))
    validate_profile(corrected, profile(first, kind))
    assert first.payload == first_bytes
    assert first.fingerprint == hashlib.sha256(first_bytes).hexdigest()
    assert first.submission_id != corrected.submission_id
    assert first.fingerprint != corrected.fingerprint
    assert first.fixtures[0].kickoff_utc == datetime(2030, 9, 14, 16, tzinfo=UTC)
    assert corrected.fixtures[0].kickoff_utc == datetime(
        2030, 9, 15, 17, 30, tzinfo=UTC
    )
    assert [first.external_id(f) for f in first.fixtures] == [
        corrected.external_id(f) for f in corrected.fixtures
    ]
    assert not first.fixtures[1].participants_resolved
    assert corrected.fixtures[1].participants_resolved


def test_models_and_original_bytes_are_immutable():
    manifest = parse_manifest(encoded(sample()))
    for model, attribute in (
        (manifest, "namespace"),
        (manifest.fixtures[0], "fixture_id"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(model, attribute, "changed")
    assert isinstance(manifest.fixtures, tuple)
    assert isinstance(manifest.boundaries, tuple)


@pytest.mark.parametrize(
    "field,value",
    [
        ("import_type", "fixture_result"),
        ("import_type", None),
        ("schema_version", True),
        ("schema_version", 1.0),
        ("schema_version", "1"),
        ("schema_version", 2),
        ("submission_id", ""),
        ("namespace", " changed"),
        ("namespace", "a:b"),
        ("namespace", "x" * 129),
        ("namespace", "Ã©"),
        ("fixtures", {}),
        ("boundaries", []),
        ("scope", None),
        ("provenance", []),
    ],
)
def test_invalid_envelope_fields(field, value):
    data = sample()
    data[field] = value
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("scope",),
        ("provenance",),
        ("fixtures", 0),
        ("fixtures", 0, "home"),
        ("fixtures", 0, "boundary"),
    ],
)
@pytest.mark.parametrize("operation", ["missing", "unknown"])
def test_every_object_is_closed_and_has_explicit_fields(path, operation):
    data = sample()
    target = data
    for key in path:
        target = target[key]
    if operation == "missing":
        del target[next(iter(target))]
    else:
        target["untrusted_private_field"] = "SECRET-CANARY"
    with pytest.raises(ManifestValidationError) as result:
        parse_manifest(encoded(data))
    assert "SECRET-CANARY" not in str(result.value)
    assert "untrusted_private_field" not in str(result.value)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"[]",
        b"null",
        b"{",
        b'{"a":1,"a":2}',
        b'{"x":{"a":1,"a":2}}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":-Infinity}',
        b"[" * 13 + b"0" + b"]" * 13,
    ],
)
def test_invalid_json_fails_with_sanitized_error(payload):
    with pytest.raises(ManifestValidationError):
        parse_manifest(payload)


def test_file_size_limit_is_enforced_before_decode():
    with pytest.raises(ManifestValidationError, match="payload"):
        parse_manifest(b" " * (MAX_BYTES + 1))


def test_fixture_count_and_duplicate_identity_limits():
    data = sample()
    data["fixtures"] = [data["fixtures"][0]] * (MAX_FIXTURES + 1)
    with pytest.raises(ManifestValidationError, match="array size"):
        parse_manifest(encoded(data))
    data["fixtures"] = data["fixtures"][:2]
    with pytest.raises(ManifestValidationError, match="duplicate fixture"):
        parse_manifest(encoded(data))


def test_duplicate_or_undeclared_boundaries_are_rejected():
    data = sample()
    data["boundaries"] *= 2
    with pytest.raises(ManifestValidationError, match="duplicate boundaries"):
        parse_manifest(encoded(data))
    data = sample()
    data["fixtures"][0]["boundary"]["round_name"] = "FINAL"
    with pytest.raises(ManifestValidationError, match="outside declared boundary"):
        parse_manifest(encoded(data))


@pytest.mark.parametrize(
    "value", ["complete_season", "complete_round", "complete_stage"]
)
def test_all_removal_capable_scopes_are_rejected(value):
    data = sample()
    data["scope"]["observation_scope"] = value
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "finished"),
        ("status", "DELETE"),
        ("status", {}),
        ("fixture_id", "a:b"),
        ("fixture_id", "x "),
        ("fixture_id", 1),
        ("home", {"resolution": "unresolved", "participant_key": "demo-home"}),
        ("home", {"resolution": "resolved", "participant_key": None}),
        ("home", {"resolution": "resolved", "participant_key": 42}),
        ("home", {"resolution": "guessed", "participant_key": "demo-home"}),
        ("away", {"resolution": "resolved", "participant_key": "demo-home"}),
        ("timezone", "Invalid/Secret-Canary"),
        ("timezone", "/etc/passwd"),
        ("kickoff_confirmed", 1),
        ("kickoff_confirmed", False),
        ("tie_key", None),
        ("leg", "third"),
        ("leg", None),
        ("venue", "<script>SECRET-CANARY</script>"),
        ("city", "x\ny"),
        ("venue", "x" * 257),
        ("city", "\ud800"),
        ("group", "has spaces"),
    ],
)
def test_invalid_fixture_fields_reject_entire_batch(field, value):
    data = sample()
    data["fixtures"][1][field] = value
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


@pytest.mark.parametrize(
    "kickoff",
    [
        "2030-02-30T12:00:00+01:00",
        "2030-09-14T18:00:00",
        "2030-09-14",
        "2030-09-14 18:00:00+02:00",
        "2030-09-14T18:00:00+01:00",
        "2030-03-31T02:30:00+01:00",
        "2030-03-31T02:30:00+02:00",
        "2030-10-27T02:30:00+03:00",
        "2030-09-14T18:00:60+02:00",
        "0001-01-01T00:00:00+14:00",
    ],
)
def test_invalid_or_ambiguous_kickoff(kickoff):
    data = sample()
    data["fixtures"][0]["kickoff"] = kickoff
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


@pytest.mark.parametrize("offset,hour", [("+02:00", 0), ("+01:00", 1)])
def test_explicit_offset_resolves_repeated_dst_hour(offset, hour):
    data = sample()
    data["fixtures"][0]["kickoff"] = "2030-10-27T02:30:00" + offset
    assert parse_manifest(encoded(data)).fixtures[0].kickoff_utc == datetime(
        2030, 10, 27, hour, 30, tzinfo=UTC
    )


def test_unknown_kickoff_is_explicit_and_postponement_does_not_invent_time():
    data = sample()
    row = data["fixtures"][0]
    row.update(kickoff=None, kickoff_confirmed=False, status="postponed")
    fixture = parse_manifest(encoded(data)).fixtures[0]
    assert fixture.kickoff_utc is None
    assert fixture.status == "postponed"


def test_cancellation_needs_resolved_participants_but_existing_mapping_is_later_gate():
    data = sample()
    data["fixtures"][0]["status"] = "cancelled"
    assert parse_manifest(encoded(data)).fixtures[0].status == "cancelled"
    data["fixtures"][1]["status"] = "cancelled"
    with pytest.raises(ManifestValidationError, match="cancellation"):
        parse_manifest(encoded(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_at", "2030-09-02T10:00:00Z"),
        ("observed_at", "2030-09-01T10:00:00+02:00"),
        ("document_sha256", "a" * 64),
        ("checksum_unavailable_reason", None),
        ("document_ref", "https://example.invalid/?token=secret"),
        ("rights_ref", "../private"),
        ("attribution", "<b>source</b>"),
    ],
)
def test_provenance_ordering_rights_and_checksum_contract(field, value):
    data = sample()
    data["provenance"][field] = value
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


def test_original_document_checksum_can_be_recorded_without_exception_reason():
    data = sample()
    data["provenance"].update(
        document_sha256="a" * 64, checksum_unavailable_reason=None
    )
    assert parse_manifest(encoded(data)).provenance.document_sha256 == "a" * 64


@pytest.mark.parametrize(
    "field,value",
    [
        ("namespace", "other"),
        ("scope", ManifestScope("football", "other", "demo_2030_31")),
        ("scope", ManifestScope("football", "efl_cup", "wrong_season")),
        ("participant_keys", frozenset({"demo-home"})),
        ("boundaries", frozenset()),
        ("competition_format", CompetitionFormat.LEAGUE),
        ("competition_format", CompetitionFormat.HYBRID_TOURNAMENT),
    ],
)
def test_profile_rejects_unknown_scope_participants_and_format(field, value):
    manifest = parse_manifest(encoded(sample()))
    with pytest.raises(ManifestValidationError):
        validate_profile(manifest, replace(profile(manifest), **{field: value}))


def approval_data(manifest):
    return {
        "submission_id": manifest.submission_id,
        "import_type": "fixture_schedule",
        "schema_version": 1,
        "manifest_sha256": manifest.fingerprint,
        "preview_sha256": "b" * 64,
        "instance_ref": "demo-staging",
        "operator_ref": "demo-operator",
        "approved_at": "2030-09-01T12:00:00Z",
    }


def test_detached_approval_binds_exact_bytes_and_does_not_claim_apply_readiness():
    manifest = parse_manifest(encoded(sample()))
    data = approval_data(manifest)
    approval = parse_approval(encoded(data), manifest)
    assert approval.instance_ref == "demo-staging"
    assert approval.preview_sha256 == "b" * 64
    other = parse_manifest(json.dumps(sample(), indent=2).encode())
    assert other.fixtures == manifest.fixtures
    assert other.fingerprint != manifest.fingerprint
    with pytest.raises(ManifestValidationError, match="binding"):
        parse_approval(encoded(data), other)


@pytest.mark.parametrize(
    "field,value",
    [
        ("submission_id", "different"),
        ("manifest_sha256", "c" * 64),
        ("preview_sha256", "not-a-hash"),
        ("schema_version", True),
        ("schema_version", 2),
        ("import_type", "fixture_result"),
        ("approved_at", "2030-09-01T10:00:00Z"),
        ("operator_ref", ""),
        ("instance_ref", 42),
    ],
)
def test_approval_rejects_mismatch_unknown_type_or_invalid_metadata(field, value):
    manifest = parse_manifest(encoded(sample()))
    data = approval_data(manifest)
    data[field] = value
    with pytest.raises(ManifestValidationError):
        parse_approval(encoded(data), manifest)


def test_identity_encoding_cannot_collide_across_namespace_separator():
    manifest = parse_manifest(encoded(sample()))
    assert manifest.external_id(manifest.fixtures[0]) == manifest.namespace + ":m001"
    data = sample()
    data["namespace"] = "a:b"
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


@pytest.mark.parametrize("league", ["b", "c", "d"])
def test_nations_league_profile_does_not_admit_league_a_or_other_leagues(league):
    data = json.loads((EXAMPLES / f"nations-league-{league}-initial.json").read_bytes())
    manifest = parse_manifest(encoded(data))
    trusted = profile(manifest, CompetitionFormat.HYBRID_TOURNAMENT)
    for other in "abcd":
        if other == league:
            continue
        changed = json.loads(encoded(data))
        changed["boundaries"][0]["stage"] = f"league_{other}_group_phase"
        for row in changed["fixtures"]:
            row["boundary"]["stage"] = f"league_{other}_group_phase"
        with pytest.raises(ManifestValidationError, match="not qualified"):
            validate_profile(parse_manifest(encoded(changed)), trusted)


def test_invalid_profile_format_cannot_disable_lifecycle_checks():
    manifest = parse_manifest(encoded(sample()))
    with pytest.raises(ManifestValidationError, match="CompetitionFormat"):
        validate_profile(
            manifest, replace(profile(manifest), competition_format="unknown")
        )


def test_boundary_count_is_bounded_before_per_item_validation():
    data = sample()
    data["boundaries"] *= 257
    with pytest.raises(ManifestValidationError, match="array size"):
        parse_manifest(encoded(data))


def test_brackets_and_escaped_quotes_inside_text_do_not_count_as_nesting():
    data = sample()
    data["provenance"]["attribution"] = 'Synthetic [ { \\"quoted\\" } ] reference'
    assert (
        parse_manifest(encoded(data)).provenance.attribution
        == data["provenance"]["attribution"]
    )


@pytest.mark.parametrize(
    "plan",
    [
        None,
        {},
        {"state": "active", "tasks": [], "completion_note": None},
        {"state": "complete", "tasks": [], "completion_note": None},
        {"state": "disabled", "tasks": [], "completion_note": "done"},
    ],
)
def test_review_plan_requires_explicit_pending_work_or_explained_completion(plan):
    data = sample()
    data["review_plan"] = plan
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


def test_review_only_manifest_requires_an_active_task():
    data = sample()
    data["fixtures"] = []
    manifest = parse_manifest(encoded(data))
    assert manifest.fixtures == ()
    assert manifest.review_plan.state == "active"
    assert manifest.review_plan.tasks

    data["review_plan"] = {
        "state": "complete",
        "tasks": [],
        "completion_note": "No further reviews are required.",
    }
    with pytest.raises(ManifestValidationError, match="active review plan"):
        parse_manifest(encoded(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_id", ""),
        ("reason", "auto_detect_draw"),
        ("due_at", None),
        ("due_at", "2030-09-10"),
        ("due_at", "2030-09-10T10:00:00+02:00"),
        ("reminder_minutes", True),
        ("reminder_minutes", -1),
        ("reminder_minutes", 10081),
        ("reminder_minutes", 1.5),
        ("target_stage", None),
        ("note", "<script>secret</script>"),
    ],
)
def test_invalid_review_task_fails_the_package(field, value):
    data = sample()
    task = data["review_plan"]["tasks"][1]
    task[field] = value
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


def test_review_task_identity_and_count_are_bounded():
    data = sample()
    data["review_plan"]["tasks"] *= 2
    with pytest.raises(ManifestValidationError, match="duplicate task"):
        parse_manifest(encoded(data))
    data["review_plan"]["tasks"] *= 9
    with pytest.raises(ManifestValidationError, match="at most 32"):
        parse_manifest(encoded(data))


def test_explicit_review_completion_is_not_complete_fixture_authority():
    data = sample()
    data["review_plan"] = {
        "state": "complete",
        "tasks": [],
        "completion_note": "Operator confirmed no further schedule checks needed.",
    }
    manifest = parse_manifest(encoded(data))
    assert manifest.review_plan.state == "complete"
    assert manifest.review_plan.tasks == ()
    assert data["scope"]["observation_scope"] == "partial"
    assert len(manifest.fixtures) == 2


def test_review_completion_cannot_retain_pending_tasks():
    data = sample()
    data["review_plan"].update(state="complete", completion_note="done")
    with pytest.raises(ManifestValidationError, match="cannot retain tasks"):
        parse_manifest(encoded(data))


def test_active_review_plan_cannot_silently_complete():
    data = sample()
    data["review_plan"]["completion_note"] = "done"
    with pytest.raises(ManifestValidationError):
        parse_manifest(encoded(data))


def test_overdue_review_is_retained_and_never_changes_fixtures():
    data = sample()
    original = parse_manifest(encoded(data))
    data["review_plan"]["tasks"][0]["due_at"] = "2020-01-01T08:00:00Z"
    changed = parse_manifest(encoded(data))
    assert changed.fixtures == original.fixtures
    assert changed.fingerprint != original.fingerprint
    assert changed.review_plan.tasks[0].due_at == datetime(2020, 1, 1, 8, tzinfo=UTC)
    assert changed.review_plan.tasks[0].reminder_minutes == 60
    with pytest.raises(ManifestValidationError, match="binding"):
        parse_approval(encoded(approval_data(original)), changed)


def test_future_round_review_does_not_expand_fixture_scope():
    data = sample()
    data["review_plan"]["tasks"][0]["target_round"] = "FUTURE_DRAW"
    manifest = parse_manifest(encoded(data))
    validate_profile(manifest, profile(manifest))
    assert manifest.review_plan.tasks[0].target_round == "FUTURE_DRAW"
    assert all(b.round_name != "FUTURE_DRAW" for b in manifest.boundaries)
