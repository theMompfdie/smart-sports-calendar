import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Participant:
    id: int
    sport_id: int
    participant_key: str
    participant_type: str
    name: str
    short_name: str | None
    country_code: str | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class ParticipantsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_key(
        self,
        sport_id: int,
        participant_key: str,
    ) -> Participant | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    sport_id,
                    participant_key,
                    participant_type,
                    name,
                    short_name,
                    country_code,
                    metadata_json,
                    created_at,
                    updated_at
                FROM participants
                WHERE sport_id = ?
                  AND participant_key = ?
                """,
                (sport_id, participant_key),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def upsert(
        self,
        sport_id: int,
        participant_key: str,
        participant_type: str,
        name: str,
        short_name: str | None = None,
        country_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Participant:
        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO participants (
                    sport_id,
                    participant_key,
                    participant_type,
                    name,
                    short_name,
                    country_code,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (sport_id, participant_key)
                DO UPDATE SET
                    participant_type = excluded.participant_type,
                    name = excluded.name,
                    short_name = excluded.short_name,
                    country_code = excluded.country_code,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    sport_id,
                    participant_key,
                    participant_type,
                    name,
                    short_name,
                    country_code,
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )

        participant = self.get_by_key(sport_id, participant_key)
        if participant is None:
            raise RuntimeError(
                "Participant could not be loaded after upsert: "
                f"{participant_key}"
            )
        return participant

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _serialize_metadata(metadata: dict[str, Any] | None) -> str | None:
        if metadata is None:
            return None
        return json.dumps(metadata, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _map_row(row: sqlite3.Row) -> Participant:
        metadata_json = row["metadata_json"]
        return Participant(
            id=row["id"],
            sport_id=row["sport_id"],
            participant_key=row["participant_key"],
            participant_type=row["participant_type"],
            name=row["name"],
            short_name=row["short_name"],
            country_code=row["country_code"],
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
