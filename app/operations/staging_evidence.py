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
class StagingEvidence:
    database_quick_check: str
    schema_version: str | None
    startup_records: int
    sports_events: int
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
        calendar_mappings_by_status={
            str(row["sync_status"]): int(row["item_count"]) for row in mapping_rows
        },
        recent_runs=tuple(SafeRunSummary(**dict(row)) for row in run_rows),
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
