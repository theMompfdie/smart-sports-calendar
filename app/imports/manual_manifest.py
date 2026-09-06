"""Strict, side-effect-free parsing of the manual fixture_schedule v1 format."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.competition_lifecycle import (
    CompetitionFormat,
    FixtureLeg,
    TournamentStageKind,
)

MAX_BYTES = 2 * 1024 * 1024
MAX_FIXTURES = 2000
MAX_BOUNDARIES = 256
MAX_DEPTH = 12
MAX_REVIEW_TASKS = 32
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})\Z")


class ManifestValidationError(ValueError):
    """Safe diagnostics identify a field, never echo untrusted input values."""


@dataclass(frozen=True)
class ManifestScope:
    sport_key: str
    competition_key: str
    season_key: str


@dataclass(frozen=True)
class FixtureBoundary:
    stage: str
    round_name: str
    stage_kind: TournamentStageKind | None


@dataclass(frozen=True)
class ManifestProvenance:
    issuer: str
    document_ref: str
    rights_ref: str
    attribution: str
    document_sha256: str | None
    checksum_unavailable_reason: str | None
    observed_at: datetime
    prepared_at: datetime


@dataclass(frozen=True)
class ManualFixture:
    fixture_id: str
    boundary: FixtureBoundary
    home_key: str | None
    away_key: str | None
    kickoff_utc: datetime | None
    timezone: str
    kickoff_confirmed: bool
    status: str
    group: str | None
    tie_key: str | None
    leg: FixtureLeg | None
    venue: str | None
    city: str | None

    @property
    def participants_resolved(self) -> bool:
        return self.home_key is not None and self.away_key is not None


@dataclass(frozen=True)
class ManualReviewTask:
    task_id: str
    due_at: datetime
    reminder_minutes: int
    reason: str
    target_stage: str | None
    target_round: str | None
    note: str | None


@dataclass(frozen=True)
class ManualReviewPlan:
    state: str
    tasks: tuple[ManualReviewTask, ...]
    completion_note: str | None


@dataclass(frozen=True)
class ManualManifest:
    import_type: str
    schema_version: int
    submission_id: str
    namespace: str
    scope: ManifestScope
    boundaries: tuple[FixtureBoundary, ...]
    provenance: ManifestProvenance
    fixtures: tuple[ManualFixture, ...]
    review_plan: ManualReviewPlan
    fingerprint: str
    payload: bytes

    def external_id(self, fixture: ManualFixture) -> str:
        # Neither identifier permits ':', so the encoding is injective.
        return f"{self.namespace}:{fixture.fixture_id}"


@dataclass(frozen=True)
class ManualSourceProfile:
    """Trusted catalog/profile snapshot, supplied by the caller, not the file."""

    namespace: str
    scope: ManifestScope
    competition_format: CompetitionFormat
    boundaries: frozenset[FixtureBoundary]
    participant_keys: frozenset[str]


@dataclass(frozen=True)
class ManifestApproval:
    submission_id: str
    import_type: str
    schema_version: int
    manifest_sha256: str
    preview_sha256: str
    instance_ref: str
    operator_ref: str
    approved_at: datetime


def _fail(path: str, reason: str) -> None:
    raise ManifestValidationError(f"{path}: {reason}") from None


def _object(value: Any, fields: str, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        _fail(path, "requires exactly the documented fields")
    return value


def _text(value: Any, path: str, limit: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or value != value.strip()
        or any(
            ord(c) < 32 or 127 <= ord(c) <= 159 or 0xD800 <= ord(c) <= 0xDFFF
            for c in value
        )
        or "<" in value
        or ">" in value
    ):
        _fail(path, "requires bounded plain text without surrounding whitespace")
    return value


def _key(value: Any, path: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        _fail(path, "requires a stable ASCII identifier (1-128 characters)")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    return None if value is None else _text(value, path)


def _optional_key(value: Any, path: str) -> str | None:
    return None if value is None else _key(value, path)


def _digest(value: Any, path: str) -> str:
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        _fail(path, "requires a lowercase SHA-256 digest")
    return value


def _enum(value: Any, allowed: set[str], path: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        _fail(path, "unsupported value")
    return value


def _timestamp(value: Any, path: str, *, utc: bool = False) -> datetime:
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        _fail(path, "requires an offset timestamp with second precision")
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        _fail(path, "invalid timestamp")
    if utc and result.utcoffset() != UTC.utcoffset(result):
        _fail(path, "requires UTC")
    return result


def _array(value: Any, path: str, maximum: int, *, minimum: int = 1) -> list[Any]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        _fail(path, "array size outside supported limits")
    return value


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("json", "duplicate object field")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    _fail("json", "non-finite numbers are forbidden")


def _decode(payload: bytes) -> Any:
    if not isinstance(payload, bytes) or not 1 <= len(payload) <= MAX_BYTES:
        _fail("payload", "requires 1-2097152 UTF-8 bytes")
    try:
        text = payload.decode("utf-8")
        # Bound nesting before invoking the recursive standard-library parser.
        depth, quoted, escaped = 0, False, False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > MAX_DEPTH:
                    _fail("json", "nesting limit exceeded")
            elif char in "]}":
                depth -= 1
        return json.loads(
            text, object_pairs_hook=_unique_pairs, parse_constant=_invalid_constant
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as error:
        if isinstance(error, ManifestValidationError):
            raise
        raise ManifestValidationError("json: invalid UTF-8 JSON document") from None


def _boundary(value: Any, path: str) -> FixtureBoundary:
    item = _object(value, "stage round_name stage_kind", path)
    kind = item["stage_kind"]
    if kind is not None:
        kind = TournamentStageKind(
            _enum(kind, set(TournamentStageKind), path + ".stage_kind")
        )
    return FixtureBoundary(
        _key(item["stage"], path + ".stage"),
        _key(item["round_name"], path + ".round_name"),
        kind,
    )


def _participant(value: Any, path: str) -> str | None:
    slot = _object(value, "resolution participant_key", path)
    resolution = _enum(
        slot["resolution"], {"resolved", "unresolved"}, path + ".resolution"
    )
    if resolution == "resolved":
        return _key(slot["participant_key"], path + ".participant_key")
    if slot["participant_key"] is not None:
        _fail(path, "unresolved participants must have a null key")
    return None


def _fixture(value: Any, path: str) -> ManualFixture:
    row = _object(
        value,
        "fixture_id boundary home away kickoff timezone kickoff_confirmed "
        "status group tie_key leg venue city",
        path,
    )
    home = _participant(row["home"], path + ".home")
    away = _participant(row["away"], path + ".away")
    if home is not None and home == away:
        _fail(path, "home and away must be distinct")
    status = _enum(
        row["status"], {"scheduled", "postponed", "cancelled"}, path + ".status"
    )
    if status == "cancelled" and (home is None or away is None):
        _fail(path, "cancellation requires resolved participants")
    timezone = _text(row["timezone"], path + ".timezone", 64)
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        _fail(path + ".timezone", "requires a known IANA timezone")
    if type(row["kickoff_confirmed"]) is not bool:
        _fail(path + ".kickoff_confirmed", "requires a boolean")
    kickoff = None
    if row["kickoff_confirmed"]:
        local = _timestamp(row["kickoff"], path + ".kickoff")
        try:
            projected = local.astimezone(zone)
            kickoff = local.astimezone(UTC)
        except (OverflowError, ValueError):
            _fail(path + ".kickoff", "timestamp outside supported range")
        if (
            projected.replace(tzinfo=None) != local.replace(tzinfo=None)
            or projected.utcoffset() != local.utcoffset()
        ):
            _fail(path + ".kickoff", "local time or offset disagrees with timezone")
    elif row["kickoff"] is not None:
        _fail(path + ".kickoff", "unconfirmed kickoff must be null")
    leg = row["leg"]
    if leg is not None:
        leg = FixtureLeg(_enum(leg, set(FixtureLeg), path + ".leg"))
    tie = _optional_key(row["tie_key"], path + ".tie_key")
    if leg in {FixtureLeg.FIRST, FixtureLeg.SECOND} and tie is None:
        _fail(path + ".tie_key", "two-legged fixtures require a tie key")
    if tie is not None and leg is None:
        _fail(path + ".leg", "a tie key requires an explicit leg")
    return ManualFixture(
        _key(row["fixture_id"], path + ".fixture_id"),
        _boundary(row["boundary"], path + ".boundary"),
        home,
        away,
        kickoff,
        timezone,
        row["kickoff_confirmed"],
        status,
        _optional_key(row["group"], path + ".group"),
        tie,
        leg,
        _optional_text(row["venue"], path + ".venue"),
        _optional_text(row["city"], path + ".city"),
    )


def _review_plan(value: Any) -> ManualReviewPlan:
    plan = _object(value, "state tasks completion_note", "review_plan")
    state = _enum(plan["state"], {"active", "complete"}, "review_plan.state")
    raw_tasks = plan["tasks"]
    if not isinstance(raw_tasks, list) or len(raw_tasks) > MAX_REVIEW_TASKS:
        _fail("review_plan.tasks", "requires an array with at most 32 tasks")
    if state == "complete":
        if raw_tasks:
            _fail("review_plan.tasks", "a completed plan cannot retain tasks")
        return ManualReviewPlan(
            state, (), _text(plan["completion_note"], "review_plan.completion_note")
        )
    if not raw_tasks or plan["completion_note"] is not None:
        _fail("review_plan", "active plan requires tasks and a null completion note")
    tasks = []
    for i, value in enumerate(raw_tasks):
        path = f"review_plan.tasks[{i}]"
        item = _object(
            value,
            "task_id due_at reminder_minutes reason target_stage target_round note",
            path,
        )
        stage = _optional_key(item["target_stage"], path + ".target_stage")
        round_name = _optional_key(item["target_round"], path + ".target_round")
        if round_name is not None and stage is None:
            _fail(path, "a target round requires a target stage")
        lead = item["reminder_minutes"]
        if type(lead) is not int or not 0 <= lead <= 10080:
            _fail(
                path + ".reminder_minutes", "requires integer minutes from 0 to 10080"
            )
        tasks.append(
            ManualReviewTask(
                _key(item["task_id"], path + ".task_id"),
                _timestamp(item["due_at"], path + ".due_at", utc=True),
                lead,
                _enum(
                    item["reason"],
                    {
                        "kickoff_confirmation",
                        "next_round_draw",
                        "return_leg_schedule",
                        "periodic_review",
                    },
                    path + ".reason",
                ),
                stage,
                round_name,
                _optional_text(item["note"], path + ".note"),
            )
        )
    if len({task.task_id for task in tasks}) != len(tasks):
        _fail("review_plan.tasks", "duplicate task identities")
    return ManualReviewPlan(state, tuple(tasks), None)


def parse_manifest(payload: bytes) -> ManualManifest:
    """Parse untrusted bytes without catalog, persistence, approval or Graph access."""
    root = _object(
        _decode(payload),
        "import_type schema_version submission_id namespace "
        "scope boundaries provenance fixtures review_plan",
        "manifest",
    )
    _enum(root["import_type"], {"fixture_schedule"}, "import_type")
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        _fail("schema_version", "only integer version 1 is supported")
    scope = _object(
        root["scope"], "sport_key competition_key season_key observation_scope", "scope"
    )
    _enum(scope["observation_scope"], {"partial"}, "scope.observation_scope")
    boundaries = tuple(
        _boundary(v, f"boundaries[{i}]")
        for i, v in enumerate(_array(root["boundaries"], "boundaries", MAX_BOUNDARIES))
    )
    if len(set(boundaries)) != len(boundaries):
        _fail("boundaries", "duplicate boundaries")
    provenance = _object(
        root["provenance"],
        "issuer document_ref rights_ref attribution "
        "document_sha256 checksum_unavailable_reason observed_at prepared_at",
        "provenance",
    )
    checksum = provenance["document_sha256"]
    reason = provenance["checksum_unavailable_reason"]
    if checksum is None:
        reason = _text(reason, "provenance.checksum_unavailable_reason")
    else:
        checksum = _digest(checksum, "provenance.document_sha256")
        if reason is not None:
            _fail(
                "provenance.checksum_unavailable_reason",
                "must be null when checksum exists",
            )
    observed = _timestamp(provenance["observed_at"], "provenance.observed_at", utc=True)
    prepared = _timestamp(provenance["prepared_at"], "provenance.prepared_at", utc=True)
    if observed > prepared:
        _fail("provenance", "observation must not follow preparation")
    fixtures = tuple(
        _fixture(v, f"fixtures[{i}]")
        for i, v in enumerate(
            _array(root["fixtures"], "fixtures", MAX_FIXTURES, minimum=0)
        )
    )
    if len({f.fixture_id for f in fixtures}) != len(fixtures):
        _fail("fixtures", "duplicate fixture identities")
    if any(f.boundary not in boundaries for f in fixtures):
        _fail("fixtures", "fixture outside declared boundary")
    review_plan = _review_plan(root["review_plan"])
    if not fixtures and review_plan.state != "active":
        _fail("fixtures", "an empty fixture list requires an active review plan")
    return ManualManifest(
        "fixture_schedule",
        1,
        _key(root["submission_id"], "submission_id"),
        _key(root["namespace"], "namespace"),
        ManifestScope(
            *(
                _key(scope[k], "scope." + k)
                for k in ("sport_key", "competition_key", "season_key")
            )
        ),
        boundaries,
        ManifestProvenance(
            _text(provenance["issuer"], "provenance.issuer"),
            _key(provenance["document_ref"], "provenance.document_ref"),
            _key(provenance["rights_ref"], "provenance.rights_ref"),
            _text(provenance["attribution"], "provenance.attribution", 512),
            checksum,
            reason,
            observed,
            prepared,
        ),
        fixtures,
        review_plan,
        hashlib.sha256(payload).hexdigest(),
        payload,
    )


def validate_profile(manifest: ManualManifest, profile: ManualSourceProfile) -> None:
    """Check explicit catalog keys and qualified boundaries; never infer mappings."""
    if not isinstance(profile.competition_format, CompetitionFormat):
        _fail("profile.competition_format", "requires a catalog CompetitionFormat")
    if manifest.namespace != profile.namespace or manifest.scope != profile.scope:
        _fail("profile", "manifest scope or namespace does not match")
    if not set(manifest.boundaries) <= profile.boundaries:
        _fail("boundaries", "scope is not qualified by the profile")
    for fixture in manifest.fixtures:
        for key in (fixture.home_key, fixture.away_key):
            if key is not None and key not in profile.participant_keys:
                _fail("participants", "unknown participant key")
        hybrid = profile.competition_format is CompetitionFormat.HYBRID_TOURNAMENT
        if hybrid != (fixture.boundary.stage_kind is not None):
            _fail("boundary.stage_kind", "stage kind disagrees with catalog format")
        if profile.competition_format is CompetitionFormat.LEAGUE and (
            fixture.leg is not None or fixture.tie_key is not None
        ):
            _fail("fixture.leg", "league fixtures cannot declare cup legs")


def parse_approval(payload: bytes, manifest: ManualManifest) -> ManifestApproval:
    """Parse detached approval; the caller validates preview and instance binding."""
    row = _object(
        _decode(payload),
        "submission_id import_type schema_version manifest_sha256 "
        "preview_sha256 instance_ref operator_ref approved_at",
        "approval",
    )
    _enum(row["import_type"], {"fixture_schedule"}, "approval.import_type")
    if type(row["schema_version"]) is not int or row["schema_version"] != 1:
        _fail("approval.schema_version", "only integer version 1 is supported")
    submission = _key(row["submission_id"], "approval.submission_id")
    digest = _digest(row["manifest_sha256"], "approval.manifest_sha256")
    if submission != manifest.submission_id or digest != manifest.fingerprint:
        _fail("approval", "manifest binding does not match")
    approved = _timestamp(row["approved_at"], "approval.approved_at", utc=True)
    if approved < manifest.provenance.prepared_at:
        _fail("approval.approved_at", "approval must not precede preparation")
    return ManifestApproval(
        submission,
        "fixture_schedule",
        1,
        digest,
        _digest(row["preview_sha256"], "approval.preview_sha256"),
        _key(row["instance_ref"], "approval.instance_ref"),
        _key(row["operator_ref"], "approval.operator_ref"),
        approved,
    )
