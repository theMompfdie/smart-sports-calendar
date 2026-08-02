import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Sport:
    id: int
    sport_key: str
    name: str
    icon: str | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class SportsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_key(self, sport_key: str) -> Sport | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    sport_key,
                    name,
                    icon,
                    metadata_json,
                    created_at,
                    updated_at
                FROM sports
                WHERE sport_key = ?
                """,
                (sport_key,),
            ).fetchone()

        if row is None:
            return None

        return self._map_row(row)

    def upsert(
        self,
        sport_key: str,
        name: str,
        icon: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Sport:
        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sports (
                    sport_key,
                    name,
                    icon,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (sport_key)
                DO UPDATE SET
                    name = excluded.name,
                    icon = excluded.icon,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    sport_key,
                    name,
                    icon,
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )

        sport = self.get_by_key(sport_key)

        if sport is None:
            raise RuntimeError(f"Sport could not be loaded after upsert: {sport_key}")

        return sport

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
    def _map_row(row: sqlite3.Row) -> Sport:
        metadata_json = row["metadata_json"]

        return Sport(
            id=row["id"],
            sport_key=row["sport_key"],
            name=row["name"],
            icon=row["icon"],
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
