import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EventStatistic:
    id: int
    event_id: int
    participant_id: int | None
    source_id: int | None
    statistic_key: str
    statistic_name: str | None
    value_number: float | None
    value_text: str | None
    unit: str | None
    period: str | None
    recorded_at: str | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class EventStatisticsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_id(
        self,
        statistic_id: int,
    ) -> EventStatistic | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    participant_id,
                    source_id,
                    statistic_key,
                    statistic_name,
                    value_number,
                    value_text,
                    unit,
                    period,
                    recorded_at,
                    metadata_json,
                    created_at,
                    updated_at
                FROM event_statistics
                WHERE id = ?
                """,
                (statistic_id,),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_for_event(
        self,
        event_id: int,
    ) -> list[EventStatistic]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    participant_id,
                    source_id,
                    statistic_key,
                    statistic_name,
                    value_number,
                    value_text,
                    unit,
                    period,
                    recorded_at,
                    metadata_json,
                    created_at,
                    updated_at
                FROM event_statistics
                WHERE event_id = ?
                ORDER BY
                    participant_id IS NULL,
                    participant_id,
                    statistic_key,
                    recorded_at IS NULL,
                    recorded_at,
                    id
                """,
                (event_id,),
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def create(
        self,
        event_id: int,
        statistic_key: str,
        participant_id: int | None = None,
        source_id: int | None = None,
        statistic_name: str | None = None,
        value_number: float | None = None,
        value_text: str | None = None,
        unit: str | None = None,
        period: str | None = None,
        recorded_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EventStatistic:
        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO event_statistics (
                    event_id,
                    participant_id,
                    source_id,
                    statistic_key,
                    statistic_name,
                    value_number,
                    value_text,
                    unit,
                    period,
                    recorded_at,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    participant_id,
                    source_id,
                    statistic_key,
                    statistic_name,
                    value_number,
                    value_text,
                    unit,
                    period,
                    recorded_at,
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )
            statistic_id = cursor.lastrowid

        if statistic_id is None:
            raise RuntimeError(
                f"Event statistic could not be created: event_id={event_id}"
            )

        statistic = self.get_by_id(statistic_id)

        if statistic is None:
            raise RuntimeError(
                f"Event statistic could not be loaded after creation: {statistic_id}"
            )

        return statistic

    def delete_for_event(
        self,
        event_id: int,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM event_statistics
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
    def _map_row(row: sqlite3.Row) -> EventStatistic:
        metadata_json = row["metadata_json"]

        return EventStatistic(
            id=row["id"],
            event_id=row["event_id"],
            participant_id=row["participant_id"],
            source_id=row["source_id"],
            statistic_key=row["statistic_key"],
            statistic_name=row["statistic_name"],
            value_number=row["value_number"],
            value_text=row["value_text"],
            unit=row["unit"],
            period=row["period"],
            recorded_at=row["recorded_at"],
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
