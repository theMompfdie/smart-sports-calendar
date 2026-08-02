import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EventResult:
    id: int
    event_id: int
    result_type: str
    participant_id: int | None
    value_text: str | None
    value_number: float | None
    position_number: int | None
    is_final: bool
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class EventResultsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_id(
        self,
        result_id: int,
    ) -> EventResult | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    result_type,
                    participant_id,
                    value_text,
                    value_number,
                    position_number,
                    is_final,
                    metadata_json,
                    created_at,
                    updated_at
                FROM event_results
                WHERE id = ?
                """,
                (result_id,),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_for_event(
        self,
        event_id: int,
    ) -> list[EventResult]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    result_type,
                    participant_id,
                    value_text,
                    value_number,
                    position_number,
                    is_final,
                    metadata_json,
                    created_at,
                    updated_at
                FROM event_results
                WHERE event_id = ?
                ORDER BY
                    position_number IS NULL,
                    position_number,
                    id
                """,
                (event_id,),
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def create(
        self,
        event_id: int,
        result_type: str,
        participant_id: int | None = None,
        value_text: str | None = None,
        value_number: float | None = None,
        position_number: int | None = None,
        is_final: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> EventResult:
        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO event_results (
                    event_id,
                    result_type,
                    participant_id,
                    value_text,
                    value_number,
                    position_number,
                    is_final,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    result_type,
                    participant_id,
                    value_text,
                    value_number,
                    position_number,
                    int(is_final),
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )
            result_id = cursor.lastrowid

        if result_id is None:
            raise RuntimeError(
                f"Event result could not be created: event_id={event_id}"
            )

        result = self.get_by_id(result_id)

        if result is None:
            raise RuntimeError(
                f"Event result could not be loaded after creation: {result_id}"
            )

        return result

    def delete_for_event(
        self,
        event_id: int,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM event_results
                WHERE event_id = ?
                """,
                (event_id,),
            )

        return cursor.rowcount

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

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
    def _map_row(row: sqlite3.Row) -> EventResult:
        metadata_json = row["metadata_json"]

        return EventResult(
            id=row["id"],
            event_id=row["event_id"],
            result_type=row["result_type"],
            participant_id=row["participant_id"],
            value_text=row["value_text"],
            value_number=row["value_number"],
            position_number=row["position_number"],
            is_final=bool(row["is_final"]),
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
