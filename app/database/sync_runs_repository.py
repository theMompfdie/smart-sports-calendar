import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SyncRun:
    id: int
    run_type: str
    source_id: int | None
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
    error_message: str | None
    metadata: dict[str, Any] | None


class SyncRunsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_id(
        self,
        sync_run_id: int,
    ) -> SyncRun | None:
        with self._connect() as connection:
            row = connection.execute(
                f"""
                {self._select_query()}
                WHERE id = ?
                """,
                (sync_run_id,),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_by_status(
        self,
        status: str,
    ) -> list[SyncRun]:
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {self._select_query()}
                WHERE status = ?
                ORDER BY started_at DESC, id DESC
                """,
                (status,),
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def get_recent(
        self,
        limit: int = 20,
        run_type: str | None = None,
        source_id: int | None = None,
    ) -> list[SyncRun]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        query = f"""
            {self._select_query()}
            WHERE 1 = 1
        """
        parameters: list[object] = []

        if run_type is not None:
            query += """
                AND run_type = ?
            """
            parameters.append(run_type)

        if source_id is not None:
            query += """
                AND source_id = ?
            """
            parameters.append(source_id)

        query += """
            ORDER BY started_at DESC, id DESC
            LIMIT ?
        """
        parameters.append(limit)

        with self._connect() as connection:
            rows = connection.execute(
                query,
                tuple(parameters),
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def start(
        self,
        run_type: str,
        source_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SyncRun:
        started_at = self._timestamp()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO sync_runs (
                    run_type,
                    source_id,
                    started_at,
                    status,
                    metadata_json
                )
                VALUES (?, ?, ?, 'running', ?)
                """,
                (
                    run_type,
                    source_id,
                    started_at,
                    metadata_json,
                ),
            )
            sync_run_id = cursor.lastrowid

        if sync_run_id is None:
            raise RuntimeError("SQLite did not return an ID for the sync run.")
        sync_run = self.get_by_id(sync_run_id)

        if sync_run is None:
            raise RuntimeError(
                "Sync run could not be loaded after creation: "
                f"run_type={run_type}, source_id={source_id}"
            )

        return sync_run

    def update_progress(
        self,
        sync_run_id: int,
        *,
        items_processed: int,
        items_created: int,
        items_updated: int,
        items_unchanged: int = 0,
        items_cancelled: int = 0,
        items_deleted: int,
        items_deferred: int = 0,
        items_failed: int,
    ) -> SyncRun | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sync_runs
                SET items_processed = ?,
                    items_created = ?,
                    items_updated = ?,
                    items_unchanged = ?,
                    items_cancelled = ?,
                    items_deleted = ?,
                    items_deferred = ?,
                    items_failed = ?
                WHERE id = ?
                  AND status = 'running'
                """,
                (
                    items_processed,
                    items_created,
                    items_updated,
                    items_unchanged,
                    items_cancelled,
                    items_deleted,
                    items_deferred,
                    items_failed,
                    sync_run_id,
                ),
            )

        if cursor.rowcount == 0:
            return None

        return self.get_by_id(sync_run_id)

    def complete(
        self,
        sync_run_id: int,
        *,
        items_processed: int,
        items_created: int,
        items_updated: int,
        items_unchanged: int = 0,
        items_cancelled: int = 0,
        items_deleted: int,
        items_deferred: int = 0,
        items_failed: int,
        metadata: dict[str, Any] | None = None,
    ) -> SyncRun | None:
        status = "completed_with_errors" if items_failed > 0 else "completed"

        return self._finish(
            sync_run_id=sync_run_id,
            status=status,
            items_processed=items_processed,
            items_created=items_created,
            items_updated=items_updated,
            items_unchanged=items_unchanged,
            items_cancelled=items_cancelled,
            items_deleted=items_deleted,
            items_deferred=items_deferred,
            items_failed=items_failed,
            error_message=None,
            metadata=metadata,
        )

    def fail(
        self,
        sync_run_id: int,
        error_message: str,
        *,
        items_processed: int = 0,
        items_created: int = 0,
        items_updated: int = 0,
        items_unchanged: int = 0,
        items_cancelled: int = 0,
        items_deleted: int = 0,
        items_deferred: int = 0,
        items_failed: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> SyncRun | None:
        return self._finish(
            sync_run_id=sync_run_id,
            status="failed",
            items_processed=items_processed,
            items_created=items_created,
            items_updated=items_updated,
            items_unchanged=items_unchanged,
            items_cancelled=items_cancelled,
            items_deleted=items_deleted,
            items_deferred=items_deferred,
            items_failed=items_failed,
            error_message=error_message,
            metadata=metadata,
        )

    def recover_running(
        self,
        run_type: str,
        error_message: str,
    ) -> list[SyncRun]:
        if not run_type.strip():
            raise ValueError("run_type must not be empty")

        if not error_message.strip():
            raise ValueError("error_message must not be empty")

        finished_at = self._timestamp()

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM sync_runs
                WHERE run_type = ?
                  AND status = 'running'
                ORDER BY id
                """,
                (run_type,),
            ).fetchall()

            sync_run_ids = [row["id"] for row in rows]

            if not sync_run_ids:
                return []

            placeholders = ", ".join("?" for _ in sync_run_ids)

            connection.execute(
                f"""
                UPDATE sync_runs
                SET finished_at = ?,
                    status = 'failed',
                    error_message = ?
                WHERE id IN ({placeholders})
                  AND status = 'running'
                """,
                (
                    finished_at,
                    error_message,
                    *sync_run_ids,
                ),
            )

            recovered_rows = connection.execute(
                f"""
                {self._select_query()}
                WHERE id IN ({placeholders})
                ORDER BY id
                """,
                tuple(sync_run_ids),
            ).fetchall()

        return [self._map_row(row) for row in recovered_rows]

    def delete(
        self,
        sync_run_id: int,
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM sync_runs
                WHERE id = ?
                """,
                (sync_run_id,),
            )

        return cursor.rowcount > 0

    def _finish(
        self,
        sync_run_id: int,
        status: str,
        items_processed: int,
        items_created: int,
        items_updated: int,
        items_unchanged: int,
        items_cancelled: int,
        items_deleted: int,
        items_deferred: int,
        items_failed: int,
        error_message: str | None,
        metadata: dict[str, Any] | None,
    ) -> SyncRun | None:
        finished_at = self._timestamp()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE sync_runs
                SET finished_at = ?,
                    status = ?,
                    items_processed = ?,
                    items_created = ?,
                    items_updated = ?,
                    items_unchanged = ?,
                    items_cancelled = ?,
                    items_deleted = ?,
                    items_deferred = ?,
                    items_failed = ?,
                    error_message = ?,
                    metadata_json = ?
                WHERE id = ?
                  AND status = 'running'
                """,
                (
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
                    error_message,
                    metadata_json,
                    sync_run_id,
                ),
            )

        if cursor.rowcount == 0:
            return None

        return self.get_by_id(sync_run_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _serialize_metadata(
        metadata: dict[str, Any] | None,
    ) -> str | None:
        if metadata is None:
            return None

        return json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
        )

    @staticmethod
    def _select_query() -> str:
        return """
            SELECT
                id,
                run_type,
                source_id,
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
                error_message,
                metadata_json
            FROM sync_runs
        """

    @staticmethod
    def _map_row(row: sqlite3.Row) -> SyncRun:
        metadata_json = row["metadata_json"]

        return SyncRun(
            id=row["id"],
            run_type=row["run_type"],
            source_id=row["source_id"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            status=row["status"],
            items_processed=row["items_processed"],
            items_created=row["items_created"],
            items_updated=row["items_updated"],
            items_unchanged=row["items_unchanged"],
            items_cancelled=row["items_cancelled"],
            items_deleted=row["items_deleted"],
            items_deferred=row["items_deferred"],
            items_failed=row["items_failed"],
            error_message=row["error_message"],
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
        )
