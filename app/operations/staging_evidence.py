import argparse
import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import asdict, dataclass
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


class StagingEvidenceValidationError(RuntimeError):
    pass


PHASE_5_AUTHORITIES = {
    "football-data-premier-league": (
        "football_data",
        "premier_league",
        "complete_season",
        True,
        True,
        380,
    ),
    "football-data-bundesliga": (
        "football_data",
        "bundesliga",
        "complete_season",
        True,
        True,
        306,
    ),
    "openligadb-dfb-pokal": (
        "openligadb",
        "dfb_pokal",
        "partial",
        False,
        False,
        None,
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
        recent_runs=tuple(_safe_run_summary(row) for row in run_rows),
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
        earliest_start_utc=aggregate["earliest_start_utc"],
        latest_start_utc=aggregate["latest_start_utc"],
        latest_source_update_utc=aggregate["latest_source_update_utc"],
        status_counts={
            str(row["status"]): int(row["item_count"]) for row in status_rows
        },
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


def validate_phase_5_candidate(evidence: StagingEvidence) -> None:
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
    expected_jobs = set(PHASE_5_AUTHORITIES)
    if set(authorities) != expected_jobs:
        errors.append("enabled authoritative jobs do not match the Phase 5 candidate")

    fixture_scopes = {scope.competition_key: scope for scope in evidence.fixture_scopes}
    expected_competitions = {
        definition[1] for definition in PHASE_5_AUTHORITIES.values()
    }
    if set(fixture_scopes) != expected_competitions:
        errors.append("fixture scopes do not match the Phase 5 candidate")
    scoped_fixture_total = sum(
        scope.fixtures_total for scope in evidence.fixture_scopes
    )
    if evidence.sports_events != scoped_fixture_total:
        errors.append("database contains events outside the Phase 5 candidate scopes")
    if evidence.calendar_mappings_by_status != {"synced": scoped_fixture_total}:
        errors.append("calendar mappings are not globally converged")

    provider_runs: dict[str, SafeRunSummary] = {}
    for run in evidence.recent_runs:
        job_key = run.job_key
        if (
            run.run_type == "provider_import"
            and job_key is not None
            and job_key in PHASE_5_AUTHORITIES
            and job_key not in provider_runs
        ):
            provider_runs[job_key] = run

    for job_key, definition in PHASE_5_AUTHORITIES.items():
        (
            source_key,
            competition_key,
            scope_kind,
            complete,
            removal_eligible,
            expected_fixture_count,
        ) = definition
        authority = authorities.get(job_key)
        if authority is not None and (
            authority.source_key != source_key
            or authority.sport_key != "football"
            or authority.competition_key != competition_key
            or authority.season_key != "2026_27"
            or authority.role != "authoritative"
            or authority.interval_seconds != 21600
        ):
            errors.append(f"authority configuration is invalid for {competition_key}")

        fixture_scope = fixture_scopes.get(competition_key)
        if fixture_scope is not None:
            if fixture_scope.source_key != source_key:
                errors.append(f"fixture source is invalid for {competition_key}")
            if fixture_scope.season_key != "2026_27":
                errors.append(f"fixture season is invalid for {competition_key}")
            if fixture_scope.fixtures_total <= 0:
                errors.append(f"fixture scope is empty for {competition_key}")
            if (
                expected_fixture_count is not None
                and fixture_scope.fixtures_total != expected_fixture_count
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
            if (
                sum(fixture_scope.status_counts.values())
                != fixture_scope.fixtures_total
            ):
                errors.append(
                    f"fixture status counts are invalid for {competition_key}"
                )

        provider_run = provider_runs.get(job_key)
        if provider_run is None:
            errors.append(f"recent provider run is missing for {competition_key}")
        elif (
            provider_run.status != "completed"
            or provider_run.source_key != source_key
            or provider_run.competition_key != competition_key
            or provider_run.season_key != "2026_27"
            or provider_run.authoritative is not True
            or provider_run.complete is not complete
            or provider_run.scope_kind != scope_kind
            or provider_run.removal_eligible is not removal_eligible
            or provider_run.items_failed != 0
        ):
            errors.append(f"latest provider run is invalid for {competition_key}")

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
    parser.add_argument(
        "--validate-phase-5-candidate",
        action="store_true",
        help=(
            "Require the exact Premier League, Bundesliga, and permanently partial "
            "DFB-Pokal staging candidate to be fully converged."
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
    except (FileNotFoundError, RuntimeError, ValueError, sqlite3.Error) as error:
        parser.exit(status=1, message=f"staging evidence failed: {error}\n")

    print(render_staging_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
