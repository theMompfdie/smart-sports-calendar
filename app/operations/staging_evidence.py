import argparse
import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SafeRunSummary:
    id: int
    run_type: str
    started_at: str
    finished_at: str | None
    status: str
    items_processed: int
    items_created: int
    items_updated: int
    items_unchanged: int
    items_cancelled: int
    items_deleted: int
    items_deferred: int
    items_failed: int
    source_key: str | None
    job_key: str | None
    competition_key: str | None
    season_key: str | None
    authoritative: bool | None
    complete: bool | None
    scope_kind: str | None
    removal_eligible: bool | None
    error_category: str | None
    scope_stage: str | None = None
    scope_stage_kind: str | None = None
    filtered: bool | None = None


@dataclass(frozen=True)
class SafeAuthoritySummary:
    job_key: str
    source_key: str
    sport_key: str
    competition_key: str
    season_key: str
    role: str
    interval_seconds: int


@dataclass(frozen=True)
class SafeFixtureScopeSummary:
    source_key: str
    competition_key: str
    season_key: str
    fixtures_total: int
    fixtures_active: int
    fixtures_deleted: int
    source_event_mappings: int
    source_event_ids_sha256: str | None
    calendar_mappings: int
    calendar_targets: int
    calendar_mapping_status_counts: dict[str, int]
    earliest_start_utc: str | None
    latest_start_utc: str | None
    latest_source_update_utc: str | None
    status_counts: dict[str, int]
    calendar_mappings_revision_pending: int = 0
    source_participant_mappings: int = 0
    stage_counts: dict[str, int] = field(default_factory=dict)
    round_counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SafePhase8ProjectionSummary:
    current_reminder_rules_by_scope: dict[str, int]
    active_reminder_rules_by_scope: dict[str, int]
    media_assets_by_state: dict[str, int]
    active_media_assets_by_owner_type: dict[str, int]
    event_attachments_by_status: dict[str, int]
    synced_event_attachments_by_slot: dict[str, int]
    event_attachments_pending_convergence: int


@dataclass(frozen=True)
class SafeRetiredLocalAuditSummary:
    sports_events: int = 0
    calendar_mappings: int = 0
    event_attachments: int = 0


@dataclass(frozen=True)
class StagingEvidence:
    database_quick_check: str
    schema_version: str | None
    startup_records: int
    sports_events: int
    active_authorities: tuple[SafeAuthoritySummary, ...]
    fixture_scopes: tuple[SafeFixtureScopeSummary, ...]
    calendar_mappings_by_status: dict[str, int]
    recent_runs: tuple[SafeRunSummary, ...]
    calendar_mappings_revision_pending: int = 0
    phase_8_projection: SafePhase8ProjectionSummary | None = None
    retired_local_audit: SafeRetiredLocalAuditSummary | None = None


class StagingEvidenceValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CandidateAuthorityRequirement:
    source_key: str
    competition_key: str
    scope_kind: str
    complete: bool
    removal_eligible: bool
    expected_fixture_count: int | None
    scope_stage: str | None = None
    scope_stage_kind: str | None = None
    filtered: bool | None = None
    expected_participant_mapping_count: int | None = None
    expected_stage_counts: tuple[tuple[str, int], ...] | None = None
    expected_round_counts: tuple[tuple[str, int], ...] | None = None
    expected_round_keys: tuple[str, ...] | None = None
    expected_unchanged_count: int | None = None
    sport_key: str = "football"
    season_key: str = "2026_27"


PHASE_5_AUTHORITIES = {
    "football-data-premier-league": CandidateAuthorityRequirement(
        source_key="football_data",
        competition_key="premier_league",
        scope_kind="complete_season",
        complete=True,
        removal_eligible=True,
        expected_fixture_count=380,
    ),
    "football-data-bundesliga": CandidateAuthorityRequirement(
        source_key="football_data",
        competition_key="bundesliga",
        scope_kind="complete_season",
        complete=True,
        removal_eligible=True,
        expected_fixture_count=306,
    ),
    "football-data-championship": CandidateAuthorityRequirement(
        source_key="football_data",
        competition_key="championship",
        scope_kind="complete_stage",
        complete=True,
        removal_eligible=True,
        expected_fixture_count=552,
        scope_stage="REGULAR_SEASON",
    ),
    "openligadb-dfb-pokal": CandidateAuthorityRequirement(
        source_key="openligadb",
        competition_key="dfb_pokal",
        scope_kind="partial",
        complete=False,
        removal_eligible=False,
        expected_fixture_count=None,
    ),
    "openligadb-second-bundesliga": CandidateAuthorityRequirement(
        source_key="openligadb",
        competition_key="second_bundesliga",
        scope_kind="partial",
        complete=False,
        removal_eligible=False,
        expected_fixture_count=306,
    ),
    "oefb-ical-oefb-cup": CandidateAuthorityRequirement(
        source_key="oefb_ical",
        competition_key="oefb_cup",
        scope_kind="partial",
        complete=False,
        removal_eligible=False,
        expected_fixture_count=48,
    ),
}

PHASE_6_NATIONS_LEAGUE_A_AUTHORITIES = {
    **PHASE_5_AUTHORITIES,
    "openligadb-uefa-nations-league": CandidateAuthorityRequirement(
        source_key="openligadb",
        competition_key="uefa_nations_league",
        scope_kind="partial",
        complete=False,
        removal_eligible=False,
        expected_fixture_count=48,
        scope_stage="league_a_group_phase",
        scope_stage_kind="league_phase",
        filtered=True,
        expected_participant_mapping_count=16,
        expected_stage_counts=(("league_a_group_phase", 48),),
        expected_round_counts=(
            ("group-a-1", 12),
            ("group-a-2", 12),
            ("group-a-3", 12),
            ("group-a-4", 12),
        ),
    ),
}

PHASE_6_CHAMPIONS_LEAGUE_AUTHORITIES = {
    **PHASE_6_NATIONS_LEAGUE_A_AUTHORITIES,
    "openligadb-uefa-champions-league": CandidateAuthorityRequirement(
        source_key="openligadb",
        competition_key="uefa_champions_league",
        scope_kind="partial",
        complete=False,
        removal_eligible=False,
        expected_fixture_count=144,
        scope_stage="league_phase",
        scope_stage_kind="league_phase",
        filtered=True,
        expected_participant_mapping_count=36,
        expected_stage_counts=(("league_phase", 144),),
        expected_round_counts=tuple((f"matchday-{order}", 18) for order in range(1, 9)),
    ),
}

PHASE_7_NFL_AUTHORITIES = {
    **PHASE_6_CHAMPIONS_LEAGUE_AUTHORITIES,
    "nflverse-nfl-2026": CandidateAuthorityRequirement(
        source_key="nflverse",
        competition_key="nfl",
        scope_kind="partial",
        complete=False,
        removal_eligible=False,
        scope_stage="regular-season",
        expected_fixture_count=272,
        expected_participant_mapping_count=32,
        expected_stage_counts=(("regular-season", 272),),
        expected_round_keys=tuple(f"week-{week}" for week in range(1, 19)),
        expected_unchanged_count=272,
        sport_key="american_football",
        season_key="2026",
    ),
}


def collect_staging_evidence(
    database_path: Path,
    *,
    limit: int = 10,
) -> StagingEvidence:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file does not exist: {database_path}")

    database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")

        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        schema_version = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            ORDER BY version DESC
            LIMIT 1
            """
        ).fetchone()
        startup_records = _count_rows(connection, "system_status")
        sports_events = _count_rows(connection, "sports_events")
        mapping_rows = connection.execute(
            """
            SELECT sync_status, COUNT(*) AS item_count
            FROM calendar_event_mappings
            GROUP BY sync_status
            ORDER BY sync_status
            """
        ).fetchall()
        revision_pending_row = connection.execute(
            """
            SELECT COUNT(*)
            FROM calendar_event_mappings AS mapping
            JOIN sports_events AS event ON event.id = mapping.event_id
            WHERE event.deleted_at IS NULL
              AND (
                  mapping.last_synced_revision < event.sync_revision
                  OR mapping.last_synced_presentation_revision <
                      mapping.presentation_revision
              )
            """
        ).fetchone()
        authority_rows = connection.execute(
            """
            SELECT
                source.source_key,
                sport.sport_key,
                competition.competition_key,
                season.season_key,
                assignment.role,
                assignment.interval_seconds,
                assignment.job_key,
                assignment.source_id,
                assignment.competition_id,
                assignment.season_id
            FROM source_assignments AS assignment
            JOIN data_sources AS source ON source.id = assignment.source_id
            JOIN competitions AS competition
              ON competition.id = assignment.competition_id
            JOIN sports AS sport ON sport.id = competition.sport_id
            JOIN seasons AS season ON season.id = assignment.season_id
            WHERE assignment.is_enabled = 1
              AND assignment.role = 'authoritative'
              AND source.is_active = 1
            ORDER BY sport.sport_key, competition.competition_key,
                     season.season_key, source.source_key
            """
        ).fetchall()
        fixture_scopes = tuple(
            _fixture_scope_summary(connection, row) for row in authority_rows
        )
        run_rows = connection.execute(
            """
            SELECT
                id,
                run_type,
                started_at,
                finished_at,
                status,
                items_processed,
                items_created,
                items_updated,
                items_unchanged,
                items_cancelled,
                items_deleted,
                items_deferred,
                items_failed,
                metadata_json
            FROM sync_runs
            ORDER BY started_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        retired_local_audit = _retired_local_audit_summary(connection)
        phase_8_projection = _phase_8_projection_summary(
            connection, retired_event_attachments=retired_local_audit.event_attachments
        )

    if quick_check is None:
        raise RuntimeError("SQLite quick check returned no result.")

    return StagingEvidence(
        database_quick_check=str(quick_check[0]),
        schema_version=(
            None if schema_version is None else str(schema_version["version"])
        ),
        startup_records=startup_records,
        sports_events=sports_events,
        active_authorities=tuple(
            SafeAuthoritySummary(
                job_key=str(row["job_key"]),
                source_key=str(row["source_key"]),
                sport_key=str(row["sport_key"]),
                competition_key=str(row["competition_key"]),
                season_key=str(row["season_key"]),
                role=str(row["role"]),
                interval_seconds=int(row["interval_seconds"]),
            )
            for row in authority_rows
        ),
        fixture_scopes=fixture_scopes,
        calendar_mappings_by_status={
            str(row["sync_status"]): int(row["item_count"]) for row in mapping_rows
        },
        calendar_mappings_revision_pending=(
            int(revision_pending_row[0]) if revision_pending_row is not None else 0
        ),
        recent_runs=tuple(_safe_run_summary(row) for row in run_rows),
        phase_8_projection=phase_8_projection,
        retired_local_audit=retired_local_audit,
    )


def _retired_local_audit_summary(
    connection: sqlite3.Connection,
) -> SafeRetiredLocalAuditSummary:
    # Keep raw totals intact. Only Phase 8 discounts this fully terminal subset.
    row = connection.execute(
        """
        WITH retired_events AS (
            SELECT e.id FROM sports_events e
            WHERE e.deleted_at IS NOT NULL
              AND e.competition_id IS NULL AND e.season_id IS NULL
              AND e.parent_event_id IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM sports_events child WHERE child.parent_event_id = e.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM source_mappings s
                  WHERE s.object_type = 'event' AND s.internal_id = e.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM reminder_rules r
                  WHERE r.event_id = e.id AND r.deleted_at IS NULL
              )
              AND EXISTS (
                  SELECT 1 FROM calendar_event_mappings m WHERE m.event_id = e.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM calendar_event_mappings m
                  WHERE m.event_id = e.id
                    AND (m.sync_status != 'deleted' OR m.last_sync_error IS NOT NULL)
              )
              AND NOT EXISTS (
                  SELECT 1 FROM calendar_event_asset_attachments a
                  JOIN calendar_event_mappings m ON m.id = a.calendar_event_mapping_id
                  WHERE m.event_id = e.id AND (
                      a.status != 'event_deleted'
                      OR a.desired_asset_id IS NOT NULL
                      OR a.desired_sha256 IS NOT NULL
                      OR a.synchronized_asset_id IS NOT NULL
                      OR a.synchronized_sha256 IS NOT NULL
                      OR a.content_id IS NOT NULL
                      OR a.outlook_attachment_id IS NOT NULL
                      OR a.pending_asset_id IS NOT NULL
                      OR a.pending_sha256 IS NOT NULL
                      OR a.pending_content_id IS NOT NULL
                      OR a.pending_outlook_attachment_id IS NOT NULL
                      OR a.obsolete_outlook_attachment_id IS NOT NULL
                      OR a.last_error IS NOT NULL
                  )
              )
        ), retired_mappings AS (
            SELECT m.id FROM calendar_event_mappings m
            JOIN retired_events e ON e.id = m.event_id
        )
        SELECT
            (SELECT COUNT(*) FROM retired_events),
            (SELECT COUNT(*) FROM retired_mappings),
            (SELECT COUNT(*) FROM calendar_event_asset_attachments a
             JOIN retired_mappings m ON m.id = a.calendar_event_mapping_id)
        """
    ).fetchone()
    return SafeRetiredLocalAuditSummary(
        sports_events=int(row[0]),
        calendar_mappings=int(row[1]),
        event_attachments=int(row[2]),
    )


def _fixture_scope_summary(
    connection: sqlite3.Connection,
    authority: sqlite3.Row,
) -> SafeFixtureScopeSummary:
    aggregate = connection.execute(
        """
        SELECT
            COUNT(*) AS fixtures_total,
            SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END) AS fixtures_active,
            SUM(CASE WHEN deleted_at IS NOT NULL THEN 1 ELSE 0 END) AS fixtures_deleted,
            MIN(start_time) AS earliest_start_utc,
            MAX(start_time) AS latest_start_utc,
            MAX(source_updated_at) AS latest_source_update_utc
        FROM sports_events
        WHERE competition_id = ? AND season_id = ? AND event_type = 'match'
        """,
        (authority["competition_id"], authority["season_id"]),
    ).fetchone()
    if aggregate is None:
        raise RuntimeError("Could not aggregate authoritative fixture scope.")
    mapping_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM source_mappings AS mapping
        JOIN sports_events AS event ON event.id = mapping.internal_id
        WHERE mapping.source_id = ? AND mapping.object_type = 'event'
          AND event.competition_id = ? AND event.season_id = ?
        """,
        (
            authority["source_id"],
            authority["competition_id"],
            authority["season_id"],
        ),
    ).fetchone()
    participant_mapping_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM source_mappings AS mapping
        JOIN season_participants AS membership
          ON membership.participant_id = mapping.internal_id
        WHERE mapping.source_id = ? AND mapping.object_type = 'participant'
          AND membership.season_id = ?
        """,
        (authority["source_id"], authority["season_id"]),
    ).fetchone()
    status_rows = connection.execute(
        """
        SELECT status, COUNT(*) AS item_count
        FROM sports_events
        WHERE competition_id = ? AND season_id = ? AND event_type = 'match'
        GROUP BY status
        ORDER BY status
        """,
        (authority["competition_id"], authority["season_id"]),
    ).fetchall()
    stage_rows = connection.execute(
        """
        SELECT stage, COUNT(*) AS item_count
        FROM sports_events
        WHERE competition_id = ? AND season_id = ? AND event_type = 'match'
          AND stage IS NOT NULL
        GROUP BY stage
        ORDER BY stage
        """,
        (authority["competition_id"], authority["season_id"]),
    ).fetchall()
    round_rows = connection.execute(
        """
        SELECT round_name, COUNT(*) AS item_count
        FROM sports_events
        WHERE competition_id = ? AND season_id = ? AND event_type = 'match'
          AND round_name IS NOT NULL
        GROUP BY round_name
        ORDER BY round_name
        """,
        (authority["competition_id"], authority["season_id"]),
    ).fetchall()
    source_mapping_rows = connection.execute(
        """
        SELECT mapping.external_id
        FROM source_mappings AS mapping
        JOIN sports_events AS event ON event.id = mapping.internal_id
        WHERE mapping.source_id = ? AND mapping.object_type = 'event'
          AND event.competition_id = ? AND event.season_id = ?
        ORDER BY mapping.external_id
        """,
        (
            authority["source_id"],
            authority["competition_id"],
            authority["season_id"],
        ),
    ).fetchall()
    calendar_aggregate = connection.execute(
        """
        SELECT
            COUNT(*) AS mapping_count,
            COUNT(DISTINCT mapping.calendar_id) AS calendar_targets
        FROM calendar_event_mappings AS mapping
        JOIN sports_events AS event ON event.id = mapping.event_id
        WHERE event.competition_id = ? AND event.season_id = ?
        """,
        (authority["competition_id"], authority["season_id"]),
    ).fetchone()
    calendar_status_rows = connection.execute(
        """
        SELECT mapping.sync_status, COUNT(*) AS item_count
        FROM calendar_event_mappings AS mapping
        JOIN sports_events AS event ON event.id = mapping.event_id
        WHERE event.competition_id = ? AND event.season_id = ?
        GROUP BY mapping.sync_status
        ORDER BY mapping.sync_status
        """,
        (authority["competition_id"], authority["season_id"]),
    ).fetchall()
    revision_pending_row = connection.execute(
        """
        SELECT COUNT(*)
        FROM calendar_event_mappings AS mapping
        JOIN sports_events AS event ON event.id = mapping.event_id
        WHERE event.competition_id = ?
          AND event.season_id = ?
          AND event.deleted_at IS NULL
          AND (
              mapping.last_synced_revision < event.sync_revision
              OR mapping.last_synced_presentation_revision <
                  mapping.presentation_revision
          )
        """,
        (authority["competition_id"], authority["season_id"]),
    ).fetchone()
    source_event_ids = [str(row["external_id"]) for row in source_mapping_rows]
    return SafeFixtureScopeSummary(
        source_key=str(authority["source_key"]),
        competition_key=str(authority["competition_key"]),
        season_key=str(authority["season_key"]),
        fixtures_total=int(aggregate["fixtures_total"]),
        fixtures_active=int(aggregate["fixtures_active"] or 0),
        fixtures_deleted=int(aggregate["fixtures_deleted"] or 0),
        source_event_mappings=int(mapping_count[0]) if mapping_count else 0,
        source_event_ids_sha256=(
            hashlib.sha256("\n".join(source_event_ids).encode()).hexdigest()
            if source_event_ids
            else None
        ),
        calendar_mappings=(
            int(calendar_aggregate["mapping_count"])
            if calendar_aggregate is not None
            else 0
        ),
        calendar_targets=(
            int(calendar_aggregate["calendar_targets"])
            if calendar_aggregate is not None
            else 0
        ),
        calendar_mapping_status_counts={
            str(row["sync_status"]): int(row["item_count"])
            for row in calendar_status_rows
        },
        calendar_mappings_revision_pending=(
            int(revision_pending_row[0]) if revision_pending_row is not None else 0
        ),
        earliest_start_utc=aggregate["earliest_start_utc"],
        latest_start_utc=aggregate["latest_start_utc"],
        latest_source_update_utc=aggregate["latest_source_update_utc"],
        status_counts={
            str(row["status"]): int(row["item_count"]) for row in status_rows
        },
        source_participant_mappings=(
            int(participant_mapping_count[0]) if participant_mapping_count else 0
        ),
        stage_counts=_safe_count_map(stage_rows, "stage"),
        round_counts=_safe_count_map(round_rows, "round_name"),
    )


def _safe_run_summary(row: sqlite3.Row) -> SafeRunSummary:
    metadata = _load_run_metadata(row["metadata_json"])
    return SafeRunSummary(
        id=int(row["id"]),
        run_type=str(row["run_type"]),
        started_at=str(row["started_at"]),
        finished_at=(None if row["finished_at"] is None else str(row["finished_at"])),
        status=str(row["status"]),
        items_processed=int(row["items_processed"]),
        items_created=int(row["items_created"]),
        items_updated=int(row["items_updated"]),
        items_unchanged=int(row["items_unchanged"]),
        items_cancelled=int(row["items_cancelled"]),
        items_deleted=int(row["items_deleted"]),
        items_deferred=int(row["items_deferred"]),
        items_failed=int(row["items_failed"]),
        source_key=_safe_identifier(metadata.get("source_key")),
        job_key=_safe_identifier(metadata.get("job_key")),
        competition_key=_safe_identifier(metadata.get("competition_key")),
        season_key=_safe_identifier(metadata.get("season_key")),
        authoritative=_safe_bool(metadata.get("authoritative")),
        complete=_safe_bool(metadata.get("complete")),
        scope_kind=_safe_identifier(metadata.get("scope_kind")),
        removal_eligible=_safe_bool(metadata.get("removal_eligible")),
        error_category=_safe_identifier(metadata.get("error_category")),
        scope_stage=_safe_identifier(metadata.get("scope_stage")),
        scope_stage_kind=_safe_identifier(metadata.get("scope_stage_kind")),
        filtered=_safe_bool(metadata.get("filtered")),
    )


def _load_run_metadata(value: object) -> dict[str, object]:
    if value is None:
        return {}
    try:
        metadata = json.loads(str(value))
    except json.JSONDecodeError as error:
        raise RuntimeError("Sync run metadata is not valid JSON.") from error
    if not isinstance(metadata, dict):
        raise RuntimeError("Sync run metadata must be a JSON object.")
    return metadata


def _safe_identifier(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value):
        return None
    return value


def _safe_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _safe_count_map(rows: Sequence[sqlite3.Row], key: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        identifier = _safe_identifier(row[key])
        if identifier is not None:
            result[identifier] = int(row["item_count"])
    return result


def _phase_8_projection_summary(
    connection: sqlite3.Connection,
    *,
    retired_event_attachments: int = 0,
) -> SafePhase8ProjectionSummary:
    current_reminder_rows = connection.execute(
        """
        SELECT scope, COUNT(*) AS item_count
        FROM reminder_rules
        WHERE deleted_at IS NULL
        GROUP BY scope
        ORDER BY scope
        """
    ).fetchall()
    active_reminder_rows = connection.execute(
        """
        SELECT scope, COUNT(*) AS item_count
        FROM reminder_rules
        WHERE deleted_at IS NULL AND is_active = 1
        GROUP BY scope
        ORDER BY scope
        """
    ).fetchall()
    media_state_rows = connection.execute(
        """
        SELECT
            CASE
                WHEN is_active = 1 THEN 'active'
                WHEN is_approved = 1 THEN 'approved_inactive'
                ELSE 'pending'
            END AS asset_state,
            COUNT(*) AS item_count
        FROM media_assets
        GROUP BY asset_state
        ORDER BY asset_state
        """
    ).fetchall()
    active_media_owner_rows = connection.execute(
        """
        SELECT owner_type, COUNT(*) AS item_count
        FROM media_assets
        WHERE is_active = 1 AND is_approved = 1
        GROUP BY owner_type
        ORDER BY owner_type
        """
    ).fetchall()
    attachment_status_rows = connection.execute(
        """
        SELECT status, COUNT(*) AS item_count
        FROM calendar_event_asset_attachments
        GROUP BY status
        ORDER BY status
        """
    ).fetchall()
    attachment_slot_rows = connection.execute(
        """
        SELECT slot, COUNT(*) AS item_count
        FROM calendar_event_asset_attachments
        WHERE status = 'synced'
          AND desired_asset_id IS NOT NULL
          AND synchronized_asset_id = desired_asset_id
          AND desired_sha256 IS NOT NULL
          AND synchronized_sha256 = desired_sha256
          AND content_id IS NOT NULL
          AND outlook_attachment_id IS NOT NULL
        GROUP BY slot
        ORDER BY slot
        """
    ).fetchall()
    pending_attachment_row = connection.execute(
        """
        SELECT COUNT(*)
        FROM calendar_event_asset_attachments
        WHERE status != 'synced'
           OR desired_asset_id IS NOT synchronized_asset_id
           OR desired_sha256 IS NOT synchronized_sha256
           OR pending_asset_id IS NOT NULL
           OR pending_sha256 IS NOT NULL
           OR pending_content_id IS NOT NULL
           OR pending_outlook_attachment_id IS NOT NULL
           OR obsolete_outlook_attachment_id IS NOT NULL
        """
    ).fetchone()
    return SafePhase8ProjectionSummary(
        current_reminder_rules_by_scope=_safe_count_map(
            current_reminder_rows,
            "scope",
        ),
        active_reminder_rules_by_scope=_safe_count_map(
            active_reminder_rows,
            "scope",
        ),
        media_assets_by_state=_safe_count_map(media_state_rows, "asset_state"),
        active_media_assets_by_owner_type=_safe_count_map(
            active_media_owner_rows,
            "owner_type",
        ),
        event_attachments_by_status=_safe_count_map(
            attachment_status_rows,
            "status",
        ),
        synced_event_attachments_by_slot=_safe_count_map(
            attachment_slot_rows,
            "slot",
        ),
        event_attachments_pending_convergence=(
            (0 if pending_attachment_row is None else int(pending_attachment_row[0]))
            - retired_event_attachments
        ),
    )


def validate_phase_5_candidate(evidence: StagingEvidence) -> None:
    _validate_candidate(
        evidence,
        requirements=PHASE_5_AUTHORITIES,
        candidate_name="Phase 5",
    )


def validate_nations_league_a_candidate(evidence: StagingEvidence) -> None:
    _validate_candidate(
        evidence,
        requirements=PHASE_6_NATIONS_LEAGUE_A_AUTHORITIES,
        candidate_name="Phase 6 Nations League A",
    )


def validate_champions_league_candidate(evidence: StagingEvidence) -> None:
    _validate_candidate(
        evidence,
        requirements=PHASE_6_CHAMPIONS_LEAGUE_AUTHORITIES,
        candidate_name="Phase 6 Champions League",
    )


def validate_phase_7_nfl_candidate(evidence: StagingEvidence) -> None:
    _validate_candidate(
        evidence,
        requirements=PHASE_7_NFL_AUTHORITIES,
        candidate_name="Phase 7 NFL",
        require_write_free_calendar_run=True,
    )


def validate_phase_8_candidate(evidence: StagingEvidence) -> None:
    _validate_candidate(
        evidence,
        requirements=PHASE_7_NFL_AUTHORITIES,
        candidate_name="Phase 8",
        require_write_free_calendar_run=True,
        allow_retired_local_audit=True,
    )
    errors: list[str] = []
    if evidence.schema_version != "012_create_calendar_event_asset_attachments":
        errors.append("database schema is not the Phase 8 candidate schema")
    projection = evidence.phase_8_projection
    if projection is None:
        errors.append("Phase 8 projection evidence is missing")
    else:
        active_rules = projection.active_reminder_rules_by_scope
        if active_rules.get("global", 0) < 1 or active_rules.get("participant", 0) < 2:
            errors.append("Phase 8 reminder profile is incomplete")
        active_media = projection.active_media_assets_by_owner_type
        if (
            active_media.get("project", 0) < 1
            or active_media.get("competition", 0) < 1
            or active_media.get("participant", 0) < 2
        ):
            errors.append("Phase 8 active media coverage is incomplete")
        retired = evidence.retired_local_audit or SafeRetiredLocalAuditSummary()
        attachment_statuses = _subtract_retired_status(
            projection.event_attachments_by_status,
            "event_deleted",
            retired.event_attachments,
        )
        if not attachment_statuses:
            errors.append("Phase 8 event attachment evidence is missing")
        elif set(attachment_statuses) != {"synced"}:
            errors.append("Phase 8 event attachments are not fully synchronized")
        if projection.event_attachments_pending_convergence != 0:
            errors.append("Phase 8 event attachments have pending convergence")
        slots = projection.synced_event_attachments_by_slot
        if any(slots.get(slot, 0) < 1 for slot in ("competition", "home", "away")):
            errors.append("Phase 8 required attachment slots are missing")
    if errors:
        raise StagingEvidenceValidationError("; ".join(errors))


def _subtract_retired_status(
    statuses: Mapping[str, int], status: str, retired_count: int
) -> dict[str, int]:
    remaining = dict(statuses)
    if retired_count:
        remaining[status] = remaining.get(status, 0) - retired_count
        if remaining[status] == 0:
            del remaining[status]
    return remaining


def _validate_candidate(
    evidence: StagingEvidence,
    *,
    requirements: Mapping[str, CandidateAuthorityRequirement],
    candidate_name: str,
    require_write_free_calendar_run: bool = False,
    allow_retired_local_audit: bool = False,
) -> None:
    errors: list[str] = []
    if evidence.database_quick_check != "ok":
        errors.append("SQLite quick check did not pass")
    if evidence.schema_version is None:
        errors.append("database schema has no migration version")
    if evidence.startup_records < 1:
        errors.append("database has no startup record")

    authorities = {
        authority.job_key: authority for authority in evidence.active_authorities
    }
    expected_jobs = set(requirements)
    if set(authorities) != expected_jobs:
        errors.append(
            f"enabled authoritative jobs do not match the {candidate_name} candidate"
        )

    fixture_scopes = {scope.competition_key: scope for scope in evidence.fixture_scopes}
    expected_competitions = {
        requirement.competition_key for requirement in requirements.values()
    }
    if set(fixture_scopes) != expected_competitions:
        errors.append(f"fixture scopes do not match the {candidate_name} candidate")
    scoped_fixture_total = sum(
        scope.fixtures_total for scope in evidence.fixture_scopes
    )
    retired = (
        evidence.retired_local_audit
        if allow_retired_local_audit and evidence.retired_local_audit is not None
        else SafeRetiredLocalAuditSummary()
    )
    if (
        retired.sports_events < 0
        or retired.calendar_mappings < retired.sports_events
        or retired.event_attachments < 0
        or (
            retired.sports_events == 0
            and (retired.calendar_mappings != 0 or retired.event_attachments != 0)
        )
    ):
        errors.append("retired local audit counts are inconsistent")
    if evidence.sports_events - retired.sports_events != scoped_fixture_total:
        errors.append(
            f"database contains events outside the {candidate_name} candidate scopes"
        )
    if _subtract_retired_status(
        evidence.calendar_mappings_by_status, "deleted", retired.calendar_mappings
    ) != {"synced": scoped_fixture_total}:
        errors.append("calendar mappings are not globally converged")
    if evidence.calendar_mappings_revision_pending != 0:
        errors.append("calendar mapping revisions are not globally converged")

    provider_runs: dict[str, SafeRunSummary] = {}
    for run in evidence.recent_runs:
        job_key = run.job_key
        if (
            run.run_type == "provider_import"
            and job_key is not None
            and job_key in requirements
            and job_key not in provider_runs
        ):
            provider_runs[job_key] = run

    for job_key, requirement in requirements.items():
        source_key = requirement.source_key
        competition_key = requirement.competition_key
        authority = authorities.get(job_key)
        if authority is not None and (
            authority.source_key != source_key
            or authority.sport_key != requirement.sport_key
            or authority.competition_key != competition_key
            or authority.season_key != requirement.season_key
            or authority.role != "authoritative"
            or authority.interval_seconds != 21600
        ):
            errors.append(f"authority configuration is invalid for {competition_key}")

        fixture_scope = fixture_scopes.get(competition_key)
        if fixture_scope is not None:
            if fixture_scope.source_key != source_key:
                errors.append(f"fixture source is invalid for {competition_key}")
            if fixture_scope.season_key != requirement.season_key:
                errors.append(f"fixture season is invalid for {competition_key}")
            if fixture_scope.fixtures_total <= 0:
                errors.append(f"fixture scope is empty for {competition_key}")
            if (
                requirement.expected_fixture_count is not None
                and fixture_scope.fixtures_total != requirement.expected_fixture_count
            ):
                errors.append(f"fixture count is invalid for {competition_key}")
            if fixture_scope.fixtures_active != fixture_scope.fixtures_total:
                errors.append(f"inactive fixtures exist for {competition_key}")
            if fixture_scope.fixtures_deleted != 0:
                errors.append(f"deleted fixtures exist for {competition_key}")
            if fixture_scope.source_event_mappings != fixture_scope.fixtures_total:
                errors.append(f"source mapping count is invalid for {competition_key}")
            if fixture_scope.source_event_ids_sha256 is None:
                errors.append(
                    f"source mapping fingerprint is missing for {competition_key}"
                )
            if fixture_scope.calendar_mappings != fixture_scope.fixtures_active:
                errors.append(
                    f"calendar mapping count is invalid for {competition_key}"
                )
            if fixture_scope.calendar_targets != 1:
                errors.append(f"calendar target count is invalid for {competition_key}")
            if fixture_scope.calendar_mapping_status_counts != {
                "synced": fixture_scope.fixtures_active
            }:
                errors.append(
                    f"calendar mappings are not converged for {competition_key}"
                )
            if fixture_scope.calendar_mappings_revision_pending != 0:
                errors.append(
                    f"calendar mapping revisions are not converged for "
                    f"{competition_key}"
                )
            if (
                sum(fixture_scope.status_counts.values())
                != fixture_scope.fixtures_total
            ):
                errors.append(
                    f"fixture status counts are invalid for {competition_key}"
                )
            if (
                requirement.expected_participant_mapping_count is not None
                and fixture_scope.source_participant_mappings
                != requirement.expected_participant_mapping_count
            ):
                errors.append(
                    f"participant mapping count is invalid for {competition_key}"
                )
            if (
                requirement.expected_stage_counts is not None
                and fixture_scope.stage_counts
                != dict(requirement.expected_stage_counts)
            ):
                errors.append(f"stage counts are invalid for {competition_key}")
            if (
                requirement.expected_round_counts is not None
                and fixture_scope.round_counts
                != dict(requirement.expected_round_counts)
            ):
                errors.append(f"round counts are invalid for {competition_key}")
            if requirement.expected_round_keys is not None and set(
                fixture_scope.round_counts
            ) != set(requirement.expected_round_keys):
                errors.append(f"round coverage is invalid for {competition_key}")

        provider_run = provider_runs.get(job_key)
        if provider_run is None:
            errors.append(f"recent provider run is missing for {competition_key}")
        elif (
            provider_run.status != "completed"
            or provider_run.source_key != source_key
            or provider_run.competition_key != competition_key
            or provider_run.season_key != requirement.season_key
            or provider_run.authoritative is not True
            or provider_run.complete is not requirement.complete
            or provider_run.scope_kind != requirement.scope_kind
            or provider_run.removal_eligible is not requirement.removal_eligible
            or provider_run.scope_stage != requirement.scope_stage
            or provider_run.scope_stage_kind != requirement.scope_stage_kind
            or (
                requirement.filtered is not None
                and provider_run.filtered is not requirement.filtered
            )
            or provider_run.items_failed != 0
            or (
                requirement.expected_unchanged_count is not None
                and (
                    provider_run.items_processed != requirement.expected_unchanged_count
                    or provider_run.items_unchanged
                    != requirement.expected_unchanged_count
                    or provider_run.items_created != 0
                    or provider_run.items_updated != 0
                    or provider_run.items_cancelled != 0
                    or provider_run.items_deleted != 0
                    or provider_run.items_deferred != 0
                )
            )
        ):
            errors.append(f"latest provider run is invalid for {competition_key}")

    if require_write_free_calendar_run:
        calendar_run = next(
            (run for run in evidence.recent_runs if run.run_type == "calendar_sync"),
            None,
        )
        if calendar_run is None:
            errors.append("recent calendar synchronization run is missing")
        elif (
            calendar_run.status != "completed"
            or calendar_run.items_processed <= 0
            or calendar_run.items_unchanged != calendar_run.items_processed
            or calendar_run.items_created != 0
            or calendar_run.items_updated != 0
            or calendar_run.items_cancelled != 0
            or calendar_run.items_deleted != 0
            or calendar_run.items_deferred != 0
            or calendar_run.items_failed != 0
        ):
            errors.append("latest calendar synchronization run is not write-free")

    if errors:
        raise StagingEvidenceValidationError("; ".join(errors))


def render_staging_evidence(evidence: StagingEvidence) -> str:
    return json.dumps(
        asdict(evidence),
        indent=2,
        sort_keys=True,
    )


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    allowed_tables = {"sports_events", "system_status"}
    if table_name not in allowed_tables:
        raise ValueError(f"Unsupported table: {table_name}")

    row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    if row is None:
        raise RuntimeError(f"Could not count rows in {table_name}.")
    return int(row[0])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Print a secret-safe, read-only summary for staging validation. "
            "The output intentionally excludes provider metadata, error messages, "
            "calendar identifiers, Outlook identifiers, and event details."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("DATABASE_PATH", "/data/sports.db")),
        help="SQLite database path (defaults to DATABASE_PATH).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of recent run summaries (default: 10).",
    )
    validation_group = parser.add_mutually_exclusive_group()
    validation_group.add_argument(
        "--validate-phase-5-candidate",
        action="store_true",
        help=(
            "Require the exact Premier League, Bundesliga, Championship regular "
            "season, and permanently partial OpenLigaDB Phase 5 staging candidate "
            "to be fully converged."
        ),
    )
    validation_group.add_argument(
        "--validate-nations-league-a-candidate",
        action="store_true",
        help=(
            "Require the exact released Phase 5 authorities plus the permanently "
            "partial and filtered UEFA Nations League A group-phase authority to "
            "be fully converged."
        ),
    )
    validation_group.add_argument(
        "--validate-champions-league-candidate",
        action="store_true",
        help=(
            "Require the exact Nations League A candidate authorities plus the "
            "permanently partial and filtered UEFA Champions League league-phase "
            "authority to be fully converged."
        ),
    )
    validation_group.add_argument(
        "--validate-phase-7-nfl-candidate",
        action="store_true",
        help=(
            "Require the exact released Phase 6 authorities plus the permanently "
            "partial NFL 2026 regular-season nflverse authority to be fully "
            "converged."
        ),
    )
    validation_group.add_argument(
        "--validate-phase-8-candidate",
        action="store_true",
        help=(
            "Require the released Phase 7 authority set plus the Phase 8 schema, "
            "runtime reminder profile, approved media coverage, synchronized "
            "inline attachments, and a write-free calendar cycle."
        ),
    )
    arguments = parser.parse_args(argv)

    try:
        evidence = collect_staging_evidence(
            arguments.database,
            limit=arguments.limit,
        )
        if arguments.validate_phase_5_candidate:
            validate_phase_5_candidate(evidence)
        elif arguments.validate_nations_league_a_candidate:
            validate_nations_league_a_candidate(evidence)
        elif arguments.validate_champions_league_candidate:
            validate_champions_league_candidate(evidence)
        elif arguments.validate_phase_7_nfl_candidate:
            validate_phase_7_nfl_candidate(evidence)
        elif arguments.validate_phase_8_candidate:
            validate_phase_8_candidate(evidence)
    except (FileNotFoundError, RuntimeError, ValueError, sqlite3.Error) as error:
        parser.exit(status=1, message=f"staging evidence failed: {error}\n")

    print(render_staging_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
