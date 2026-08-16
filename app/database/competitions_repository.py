import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.competition_lifecycle import CompetitionFormat


@dataclass(frozen=True)
class Competition:
    id: int
    sport_id: int
    competition_key: str
    name: str
    short_name: str | None
    country_code: str | None
    competition_type: CompetitionFormat | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        if self.competition_type is not None:
            object.__setattr__(
                self,
                "competition_type",
                CompetitionFormat(self.competition_type),
            )


class CompetitionsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_key(
        self,
        sport_id: int,
        competition_key: str,
    ) -> Competition | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    sport_id,
                    competition_key,
                    name,
                    short_name,
                    country_code,
                    competition_type,
                    metadata_json,
                    created_at,
                    updated_at
                FROM competitions
                WHERE sport_id = ?
                  AND competition_key = ?
                """,
                (
                    sport_id,
                    competition_key,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._map_row(row)

    def upsert(
        self,
        sport_id: int,
        competition_key: str,
        name: str,
        short_name: str | None = None,
        country_code: str | None = None,
        competition_type: CompetitionFormat | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Competition:
        timestamp = datetime.now(UTC).isoformat()
        competition_type_value = (
            None
            if competition_type is None
            else CompetitionFormat(competition_type).value
        )
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO competitions (
                    sport_id,
                    competition_key,
                    name,
                    short_name,
                    country_code,
                    competition_type,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (sport_id, competition_key)
                DO UPDATE SET
                    name = excluded.name,
                    short_name = excluded.short_name,
                    country_code = excluded.country_code,
                    competition_type = excluded.competition_type,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    sport_id,
                    competition_key,
                    name,
                    short_name,
                    country_code,
                    competition_type_value,
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )

        competition = self.get_by_key(
            sport_id=sport_id,
            competition_key=competition_key,
        )

        if competition is None:
            raise RuntimeError(
                f"Competition could not be loaded after upsert: {competition_key}"
            )

        return competition

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
    def _map_row(row: sqlite3.Row) -> Competition:
        metadata_json = row["metadata_json"]

        return Competition(
            id=row["id"],
            sport_id=row["sport_id"],
            competition_key=row["competition_key"],
            name=row["name"],
            short_name=row["short_name"],
            country_code=row["country_code"],
            competition_type=row["competition_type"],
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
