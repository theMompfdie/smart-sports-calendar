import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EventParticipant:
    id: int
    event_id: int
    participant_id: int
    role: str
    position_number: int | None
    is_primary: bool
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class EventParticipantsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get(
        self,
        event_id: int,
        participant_id: int,
        role: str,
    ) -> EventParticipant | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    participant_id,
                    role,
                    position_number,
                    is_primary,
                    metadata_json,
                    created_at,
                    updated_at
                FROM event_participants
                WHERE event_id = ?
                  AND participant_id = ?
                  AND role = ?
                """,
                (
                    event_id,
                    participant_id,
                    role,
                ),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_for_event(
        self,
        event_id: int,
    ) -> list[EventParticipant]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    event_id,
                    participant_id,
                    role,
                    position_number,
                    is_primary,
                    metadata_json,
                    created_at,
                    updated_at
                FROM event_participants
                WHERE event_id = ?
                ORDER BY
                    position_number IS NULL,
                    position_number,
                    id
                """,
                (event_id,),
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def upsert(
        self,
        event_id: int,
        participant_id: int,
        role: str,
        position_number: int | None = None,
        is_primary: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> EventParticipant:
        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO event_participants (
                    event_id,
                    participant_id,
                    role,
                    position_number,
                    is_primary,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (event_id, participant_id, role)
                DO UPDATE SET
                    position_number = excluded.position_number,
                    is_primary = excluded.is_primary,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    event_id,
                    participant_id,
                    role,
                    position_number,
                    int(is_primary),
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )

        event_participant = self.get(
            event_id=event_id,
            participant_id=participant_id,
            role=role,
        )

        if event_participant is None:
            raise RuntimeError(
                "Event participant could not be loaded after upsert: "
                f"event_id={event_id}, "
                f"participant_id={participant_id}, "
                f"role={role}"
            )

        return event_participant

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
    def _map_row(row: sqlite3.Row) -> EventParticipant:
        metadata_json = row["metadata_json"]

        return EventParticipant(
            id=row["id"],
            event_id=row["event_id"],
            participant_id=row["participant_id"],
            role=row["role"],
            position_number=row["position_number"],
            is_primary=bool(row["is_primary"]),
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
