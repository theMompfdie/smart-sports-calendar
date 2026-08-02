import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class CalendarEventMapping:
    id: int
    event_id: int
    calendar_id: str
    transaction_id: str
    outlook_event_id: str | None
    outlook_change_key: str | None
    content_hash: str | None
    sync_status: str
    sync_attempts: int
    last_synced_at: str | None
    last_sync_error: str | None
    created_at: str
    updated_at: str


class CalendarEventMappingsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_id(
        self,
        mapping_id: int,
    ) -> CalendarEventMapping | None:
        with self._connect() as connection:
            row = connection.execute(
                f"""
                {self._select_query()}
                WHERE id = ?
                """,
                (mapping_id,),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_by_event(
        self,
        event_id: int,
        calendar_id: str,
    ) -> CalendarEventMapping | None:
        with self._connect() as connection:
            row = connection.execute(
                f"""
                {self._select_query()}
                WHERE event_id = ?
                  AND calendar_id = ?
                """,
                (
                    event_id,
                    calendar_id,
                ),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_by_outlook_event(
        self,
        calendar_id: str,
        outlook_event_id: str,
    ) -> CalendarEventMapping | None:
        with self._connect() as connection:
            row = connection.execute(
                f"""
                {self._select_query()}
                WHERE calendar_id = ?
                  AND outlook_event_id = ?
                """,
                (
                    calendar_id,
                    outlook_event_id,
                ),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_by_status(
        self,
        sync_status: str,
    ) -> list[CalendarEventMapping]:
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                {self._select_query()}
                WHERE sync_status = ?
                ORDER BY updated_at, id
                """,
                (sync_status,),
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def create_pending(
        self,
        event_id: int,
        calendar_id: str,
        content_hash: str | None = None,
    ) -> CalendarEventMapping:
        timestamp = self._timestamp()
        transaction_id = str(uuid4())

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO calendar_event_mappings (
                    event_id,
                    calendar_id,
                    transaction_id,
                    content_hash,
                    sync_status,
                    sync_attempts,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 'pending', 0, ?, ?)
                """,
                (
                    event_id,
                    calendar_id,
                    transaction_id,
                    content_hash,
                    timestamp,
                    timestamp,
                ),
            )
            mapping_id = cursor.lastrowid

        mapping = self.get_by_id(mapping_id)

        if mapping is None:
            raise RuntimeError(
                "Calendar event mapping could not be loaded after creation: "
                f"event_id={event_id}, calendar_id={calendar_id}"
            )

        return mapping

    def mark_pending(
        self,
        mapping_id: int,
        content_hash: str | None = None,
    ) -> CalendarEventMapping | None:
        timestamp = self._timestamp()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE calendar_event_mappings
                SET
                    content_hash = COALESCE(?, content_hash),
                    sync_status = 'pending',
                    last_sync_error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    content_hash,
                    timestamp,
                    mapping_id,
                ),
            )

        if cursor.rowcount == 0:
            return None

        return self.get_by_id(mapping_id)

    def mark_synced(
        self,
        mapping_id: int,
        outlook_event_id: str,
        outlook_change_key: str | None,
        content_hash: str,
    ) -> CalendarEventMapping | None:
        timestamp = self._timestamp()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE calendar_event_mappings
                SET outlook_event_id = ?,
                    outlook_change_key = ?,
                    content_hash = ?,
                    sync_status = 'synced',
                    sync_attempts = sync_attempts + 1,
                    last_synced_at = ?,
                    last_sync_error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    outlook_event_id,
                    outlook_change_key,
                    content_hash,
                    timestamp,
                    timestamp,
                    mapping_id,
                ),
            )

        if cursor.rowcount == 0:
            return None

        return self.get_by_id(mapping_id)

    def mark_failed(
        self,
        mapping_id: int,
        error_message: str,
    ) -> CalendarEventMapping | None:
        timestamp = self._timestamp()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE calendar_event_mappings
                SET sync_status = 'failed',
                    sync_attempts = sync_attempts + 1,
                    last_sync_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    error_message,
                    timestamp,
                    mapping_id,
                ),
            )

        if cursor.rowcount == 0:
            return None

        return self.get_by_id(mapping_id)

    def mark_delete_failed(
        self,
        mapping_id: int,
        error_message: str,
    ) -> CalendarEventMapping | None:
        timestamp = self._timestamp()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE calendar_event_mappings
                SET sync_attempts = sync_attempts + 1,
                    last_sync_error = ?,
                    updated_at = ?
                WHERE id = ?
                  AND sync_status = 'delete_pending'
                """,
                (
                    error_message,
                    timestamp,
                    mapping_id,
                ),
            )

        if cursor.rowcount == 0:
            return None

        return self.get_by_id(mapping_id)

    def mark_delete_pending(
        self,
        mapping_id: int,
    ) -> CalendarEventMapping | None:
        return self._set_status(
            mapping_id=mapping_id,
            sync_status="delete_pending",
        )

    def mark_deleted(
        self,
        mapping_id: int,
    ) -> CalendarEventMapping | None:
        timestamp = self._timestamp()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE calendar_event_mappings
                SET sync_status = 'deleted',
                    sync_attempts = sync_attempts + 1,
                    outlook_change_key = NULL,
                    last_sync_error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    timestamp,
                    mapping_id,
                ),
            )

        if cursor.rowcount == 0:
            return None

        return self.get_by_id(mapping_id)

    def delete(
        self,
        mapping_id: int,
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM calendar_event_mappings
                WHERE id = ?
                """,
                (mapping_id,),
            )

        return cursor.rowcount > 0

    def _set_status(
        self,
        mapping_id: int,
        sync_status: str,
    ) -> CalendarEventMapping | None:
        timestamp = self._timestamp()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE calendar_event_mappings
                SET sync_status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    sync_status,
                    timestamp,
                    mapping_id,
                ),
            )

        if cursor.rowcount == 0:
            return None

        return self.get_by_id(mapping_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _select_query() -> str:
        return """
            SELECT
                id,
                event_id,
                calendar_id,
                transaction_id,
                outlook_event_id,
                outlook_change_key,
                content_hash,
                sync_status,
                sync_attempts,
                last_synced_at,
                last_sync_error,
                created_at,
                updated_at
            FROM calendar_event_mappings
        """

    @staticmethod
    def _map_row(row: sqlite3.Row) -> CalendarEventMapping:
        return CalendarEventMapping(
            id=row["id"],
            event_id=row["event_id"],
            calendar_id=row["calendar_id"],
            outlook_event_id=row["outlook_event_id"],
            transaction_id=row["transaction_id"],
            outlook_change_key=row["outlook_change_key"],
            content_hash=row["content_hash"],
            sync_status=row["sync_status"],
            sync_attempts=row["sync_attempts"],
            last_synced_at=row["last_synced_at"],
            last_sync_error=row["last_sync_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
