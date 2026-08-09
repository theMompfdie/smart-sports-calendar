import argparse
import json
import os
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


@dataclass(frozen=True)
class SafeAuthoritySummary:
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
                items_failed
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
        recent_runs=tuple(SafeRunSummary(**dict(row)) for row in run_rows),
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
    return SafeFixtureScopeSummary(
        source_key=str(authority["source_key"]),
        competition_key=str(authority["competition_key"]),
        season_key=str(authority["season_key"]),
        fixtures_total=int(aggregate["fixtures_total"]),
        fixtures_active=int(aggregate["fixtures_active"] or 0),
        fixtures_deleted=int(aggregate["fixtures_deleted"] or 0),
        source_event_mappings=int(mapping_count[0]) if mapping_count else 0,
        earliest_start_utc=aggregate["earliest_start_utc"],
        latest_start_utc=aggregate["latest_start_utc"],
        latest_source_update_utc=aggregate["latest_source_update_utc"],
        status_counts={
            str(row["status"]): int(row["item_count"]) for row in status_rows
        },
    )


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
    arguments = parser.parse_args(argv)

    try:
        evidence = collect_staging_evidence(
            arguments.database,
            limit=arguments.limit,
        )
    except (FileNotFoundError, RuntimeError, ValueError, sqlite3.Error) as error:
        parser.exit(status=1, message=f"staging evidence failed: {error}\n")

    print(render_staging_evidence(evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
