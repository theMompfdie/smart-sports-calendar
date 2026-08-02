import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Season:
    id: int
    competition_id: int
    season_key: str
    name: str
    start_date: str | None
    end_date: str | None
    is_current: bool
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class SeasonsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_key(
        self,
        competition_id: int,
        season_key: str,
    ) -> Season | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    competition_id,
                    season_key,
                    name,
                    start_date,
                    end_date,
                    is_current,
                    metadata_json,
                    created_at,
                    updated_at
                FROM seasons
                WHERE competition_id = ?
                  AND season_key = ?
                """,
                (
                    competition_id,
                    season_key,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._map_row(row)

    def upsert(
        self,
        competition_id: int,
        season_key: str,
        name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        is_current: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> Season:
        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO seasons (
                    competition_id,
                    season_key,
                    name,
                    start_date,
                    end_date,
                    is_current,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (competition_id, season_key)
                DO UPDATE SET
                    name = excluded.name,
                    start_date = excluded.start_date,
                    end_date = excluded.end_date,
                    is_current = excluded.is_current,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    competition_id,
                    season_key,
                    name,
                    start_date,
                    end_date,
                    int(is_current),
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )

        season = self.get_by_key(
            competition_id=competition_id,
            season_key=season_key,
        )

        if season is None:
            raise RuntimeError(f"Season could not be loaded after upsert: {season_key}")

        return season

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
    def _map_row(row: sqlite3.Row) -> Season:
        metadata_json = row["metadata_json"]

        return Season(
            id=row["id"],
            competition_id=row["competition_id"],
            season_key=row["season_key"],
            name=row["name"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            is_current=bool(row["is_current"]),
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
