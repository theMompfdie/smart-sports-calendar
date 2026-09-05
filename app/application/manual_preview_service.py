"""Deterministic, write-free planning for reviewed manual fixture manifests."""

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any

from app.database.fixture_import_repository import (
    FixtureImportRecord,
    FixtureImportRepository,
    FixtureParticipantRecord,
)
from app.database.manual_preview_repository import (
    ManualPreviewRepository,
    ManualPreviewState,
)
from app.domain.competition_lifecycle import (
    CompetitionFormat,
    FixtureParticipantResolution,
)
from app.imports.manual_manifest import (
    MAX_BOUNDARIES,
    FixtureBoundary,
    ManifestApproval,
    ManifestScope,
    ManifestValidationError,
    ManualFixture,
    ManualManifest,
    ManualSourceProfile,
    _array,
    _boundary,
    _decode,
    _key,
    _object,
    parse_manifest,
    validate_profile,
)

VALIDATOR_VERSION = "manual-preview-v1"


def _json(value: Any) -> str:
    def encode(item: Any) -> Any:
        if isinstance(item, FixtureBoundary):
            return asdict(item)
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, (frozenset, set)):
            return sorted(
                item,
                key=lambda entry: json.dumps(entry, default=encode, sort_keys=True),
            )
        raise TypeError("Unsupported preview value.")

    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), default=encode
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PreviewConfiguration:
    instance_ref: str
    profile: ManualSourceProfile


def parse_preview_configuration(payload: bytes) -> PreviewConfiguration:
    """Trusted operator configuration is separate from untrusted submissions."""
    row = _object(
        _decode(payload),
        "instance_ref namespace scope competition_format boundaries",
        "configuration",
    )
    scope = _object(row["scope"], "sport_key competition_key season_key", "scope")
    boundaries = tuple(
        _boundary(value, "configuration.boundaries")
        for value in _array(
            row["boundaries"], "configuration.boundaries", MAX_BOUNDARIES
        )
    )
    if not boundaries or len(set(boundaries)) != len(boundaries):
        raise ManifestValidationError("configuration: empty or duplicate boundaries")
    try:
        kind = CompetitionFormat(row["competition_format"])
    except (ValueError, TypeError):
        raise ManifestValidationError(
            "configuration: invalid competition format"
        ) from None
    return PreviewConfiguration(
        _key(row["instance_ref"], "configuration.instance_ref"),
        ManualSourceProfile(
            _key(row["namespace"], "configuration.namespace"),
            ManifestScope(
                *(
                    _key(scope[key], "configuration.scope")
                    for key in ("sport_key", "competition_key", "season_key")
                )
            ),
            kind,
            frozenset(boundaries),
            frozenset(),
        ),
    )


@dataclass(frozen=True)
class PreviewReport:
    """Serialized report is immutable and includes its exact approval digest."""

    payload: str
    fingerprint: str
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return {**json.loads(self.payload), "preview_sha256": self.fingerprint}


class ManualPreviewService:
    def __init__(self, repository: ManualPreviewRepository) -> None:
        self.repository = repository

    def preview(
        self, payload: bytes, configuration: PreviewConfiguration
    ) -> PreviewReport:
        manifest = parse_manifest(payload)
        return plan_preview(manifest, configuration, self.repository.read(manifest))


def _record(
    manifest: ManualManifest, fixture: ManualFixture, state: ManualPreviewState
) -> FixtureImportRecord:
    people = {row["participant_key"]: row for row in state.participants}
    participants = tuple(
        FixtureParticipantRecord(
            None if key is None else people[key]["id"],
            role,
            index,
            FixtureParticipantResolution.UNRESOLVED
            if key is None
            else FixtureParticipantResolution.RESOLVED,
        )
        for index, (role, key) in enumerate(
            (("home", fixture.home_key), ("away", fixture.away_key)), 1
        )
    )
    title = " - ".join(
        people[key]["name"] if key else "TBD"
        for key in (fixture.home_key, fixture.away_key)
    )
    return FixtureImportRecord(
        external_id=manifest.external_id(fixture),
        sport_id=state.catalog["sport_id"],
        competition_id=state.catalog["competition_id"],
        season_id=state.catalog["season_id"],
        event_type="match",
        title=title,
        participants=participants,
        kickoff_utc=fixture.kickoff_utc,
        kickoff_confirmed=fixture.kickoff_confirmed,
        timezone=fixture.timezone,
        status=fixture.status,
        stage=fixture.boundary.stage,
        round_name=fixture.boundary.round_name,
        sequence_number=None,
        venue_name=fixture.venue,
        city=fixture.city,
        source_updated_at=None,
        metadata={"group": fixture.group},
        stage_kind=fixture.boundary.stage_kind,
        tie_key=fixture.tie_key,
        leg=fixture.leg,
        event_key_prefix="manual",
    )


def _plan_fixture(
    manifest: ManualManifest,
    fixture: ManualFixture,
    config: PreviewConfiguration,
    state: ManualPreviewState,
    participants_by_event: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    record = _record(manifest, fixture, state)
    source_ids = {
        source["id"] for source in state.sources if source["source_key"] == "manual"
    }
    mappings = [
        row
        for row in state.mappings
        if row["source_id"] in source_ids and row["external_id"] == record.external_id
    ]
    if len(mappings) > 1:
        raise ValueError("ambiguous_manual_mapping")
    event_id = mappings[0]["internal_id"] if mappings else None
    event = next((row for row in state.events if row["id"] == event_id), None)
    if mappings:
        expected = FixtureImportRepository.event_key("manual", record.external_id)
        if event is None or event["event_key"] != expected:
            raise ValueError("invalid_manual_mapping")
        if any(
            event[key] != state.catalog[key]
            for key in ("sport_id", "competition_id", "season_id")
        ):
            raise ValueError("mapped_event_outside_scope")
        if event["stage"] not in {b.stage for b in config.profile.boundaries}:
            raise ValueError("mapped_event_outside_authority")
        if any(
            row["internal_id"] == event_id
            and (
                row["source_id"] not in source_ids
                or row["external_id"] != record.external_id
            )
            for row in state.mappings
        ):
            raise ValueError("shared_event_requires_explicit_handover")
    else:
        expected = FixtureImportRepository.event_key("manual", record.external_id)
        if any(row["event_key"] == expected for row in state.events):
            raise ValueError("unmapped_stable_key_collision")
        if fixture.participants_resolved:
            pair = {(p.participant_id, p.role) for p in record.participants}
            for candidate in state.events:
                current = {
                    (p["participant_id"], p["role"])
                    for p in participants_by_event.get(candidate["id"], [])
                }
                lifecycle = json.loads(candidate["metadata_json"] or "{}").get(
                    "tournament_lifecycle", {}
                )
                if (
                    current == pair
                    and candidate["stage"] == record.stage
                    and candidate["round_name"] == record.round_name
                    and lifecycle.get("leg") == record.leg
                ):
                    raise ValueError("candidate_identity_requires_review")
    if fixture.status == "cancelled" and (
        event is None or not fixture.participants_resolved
    ):
        raise ValueError("cancellation_requires_known_resolved_identity")
    warnings: list[str] = []
    target: dict[str, Any] | None = None
    if not fixture.participants_resolved:
        decision, reason = "DEFER", "unresolved_participants"
    elif event is None and not fixture.kickoff_confirmed:
        decision, reason = "DEFER", "unconfirmed_new_kickoff"
    elif event is None:
        decision, reason = "CREATE", "new_stable_manual_identity"
    else:
        # Share canonical null/preservation and metadata comparison with the
        # existing importer, but never invoke its writes or heuristic mapping.
        target = FixtureImportRepository.target_values(event, record)
        target["cancelled_at"] = (
            event["cancelled_at"] or manifest.provenance.observed_at.isoformat()
            if fixture.status == "cancelled"
            else None
        )
        current = sorted(
            (p["participant_id"], p["role"], p["position_number"])
            for p in participants_by_event.get(event["id"], [])
        )
        intended = sorted(
            (p.participant_id, p.role, p.position_number) for p in record.participants
        )
        changed = current != intended or any(
            event[key] != value for key, value in target.items()
        )
        decision = (
            "SKIP"
            if not changed
            else "CANCEL"
            if fixture.status == "cancelled" and event["status"] != "cancelled"
            else "UPDATE"
        )
        reason = "unchanged" if not changed else "reviewed_correction"
        if not fixture.kickoff_confirmed:
            warnings.append("retaining_last_confirmed_kickoff")
        if fixture.venue is None and event["venue_name"] is not None:
            warnings.append("retaining_existing_venue")
        if fixture.city is None and event["city"] is not None:
            warnings.append("retaining_existing_city")
    return {
        "fixture_id": fixture.fixture_id,
        "event_id": event_id,
        "decision": decision,
        "reason": reason,
        "warnings": warnings,
        "normalized": asdict(record),
        "effective_target": target,
    }


def plan_preview(
    manifest: ManualManifest, config: PreviewConfiguration, state: ManualPreviewState
) -> PreviewReport:
    """Pure planning; an invalid record makes the whole report unapprovable."""
    errors: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    participants_by_event: dict[int, list[dict[str, Any]]] = {}
    for participant in state.event_participants:
        participants_by_event.setdefault(participant["event_id"], []).append(
            participant
        )
    try:
        if state.catalog["competition_type"] != config.profile.competition_format.value:
            raise ValueError("catalog_format_mismatch")
        people = frozenset(
            row["participant_key"]
            for row in state.participants
            if row["sport_id"] == state.catalog["sport_id"]
        )
        profile = ManualSourceProfile(
            config.profile.namespace,
            config.profile.scope,
            config.profile.competition_format,
            config.profile.boundaries,
            people,
        )
        validate_profile(replace(manifest, fixtures=()), profile)
        sources = {row["id"]: row for row in state.sources}
        if any(
            row["source_key"] == "manual" and not row["is_active"]
            for row in state.sources
        ):
            raise ValueError("manual_source_disabled")
        for assignment in state.assignments:
            if not assignment["is_enabled"] or assignment["role"] in {
                "disabled",
                "verification",
            }:
                continue
            source = sources.get(assignment["source_id"])
            if (
                source is None
                or source["source_key"] != "manual"
                or assignment["role"] != "authoritative"
            ):
                raise ValueError("conflicting_whole_season_writer")
        identities: set[tuple[Any, ...]] = set()
        for index, fixture in enumerate(manifest.fixtures):
            try:
                validate_profile(replace(manifest, fixtures=(fixture,)), profile)
                identity = (
                    fixture.home_key,
                    fixture.away_key,
                    fixture.boundary,
                    fixture.leg,
                )
                if fixture.participants_resolved and identity in identities:
                    raise ValueError("duplicate_fixture_candidate")
                identities.add(identity)
                items.append(
                    _plan_fixture(
                        manifest, fixture, config, state, participants_by_event
                    )
                )
            except ValueError as error:
                errors.append({"record": index, "code": str(error)})
    except ManifestValidationError as error:
        errors.append({"record": None, "code": str(error)})
    except ValueError as error:
        errors.append({"record": None, "code": str(error)})
    previous = (
        {}
        if state.accepted_review_plan is None
        else {task.task_id: asdict(task) for task in state.accepted_review_plan.tasks}
    )
    proposed = {task.task_id: asdict(task) for task in manifest.review_plan.tasks}
    reviews = [
        {
            "task_id": key,
            "decision": "RETIRE"
            if key not in proposed
            else "CREATE"
            if key not in previous
            else "SKIP"
            if previous[key] == proposed[key]
            else "UPDATE",
            "previous": previous.get(key),
            "proposed": proposed.get(key),
        }
        for key in sorted(previous.keys() | proposed.keys())
    ]
    body = {
        "validator_version": VALIDATOR_VERSION,
        "manifest_sha256": manifest.fingerprint,
        "namespace": manifest.namespace,
        "scope": asdict(manifest.scope),
        "provenance": asdict(manifest.provenance),
        "submission_id": manifest.submission_id,
        "import_type": manifest.import_type,
        "schema_version": manifest.schema_version,
        "instance_ref": config.instance_ref,
        "precondition_sha256": _digest(
            {"state": asdict(state), "config": asdict(config)}
        ),
        "accepted": not errors,
        "errors": errors,
        "fixtures": items,
        "summary": {
            op: sum(item["decision"] == op for item in items)
            for op in ("CREATE", "UPDATE", "SKIP", "CANCEL", "DEFER")
        },
        "review_plan": asdict(manifest.review_plan),
        "review_appointments": reviews,
        "warnings": ["preview_only_no_apply_or_graph_delivery"],
        "partial_omissions": "no_operation",
    }
    payload = _json(body)
    return PreviewReport(
        payload, hashlib.sha256(payload.encode("utf-8")).hexdigest(), not errors
    )


def validate_preview_approval(
    approval: ManifestApproval,
    manifest: ManualManifest,
    reviewed: PreviewReport,
    current: PreviewReport,
    configuration: PreviewConfiguration,
) -> None:
    """Call again under the future apply write transaction before any mutation."""
    for report in (reviewed, current):
        body = report.to_dict()
        if (
            hashlib.sha256(report.payload.encode("utf-8")).hexdigest()
            != report.fingerprint
            or body.get("accepted") is not True
            or body.get("validator_version") != VALIDATOR_VERSION
            or body.get("manifest_sha256") != manifest.fingerprint
            or body.get("instance_ref") != configuration.instance_ref
        ):
            raise ValueError("Preview integrity or target check failed.")
    if (
        not reviewed.accepted
        or not current.accepted
        or approval.manifest_sha256 != manifest.fingerprint
        or approval.submission_id != manifest.submission_id
        or approval.import_type != manifest.import_type
        or approval.schema_version != manifest.schema_version
        or approval.instance_ref != configuration.instance_ref
        or reviewed.to_dict()["instance_ref"] != configuration.instance_ref
        or reviewed.to_dict()["manifest_sha256"] != manifest.fingerprint
        or approval.preview_sha256 != reviewed.fingerprint
        or reviewed.fingerprint != current.fingerprint
        or approval.approved_at < manifest.provenance.prepared_at
    ):
        raise ValueError("Approval or preview is stale or belongs to another target.")
