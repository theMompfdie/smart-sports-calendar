import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DataSource:
    id: int
    source_key: str
    name: str
    base_url: str | None
    is_active: bool
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class DataSourcesRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_key(
        self,
        source_key: str,
    ) -> DataSource | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    source_key,
                    name,
                    base_url,
                    is_active,
                    metadata_json,
                    created_at,
                    updated_at
                FROM data_sources
                WHERE source_key = ?
                """,
                (source_key,),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_all(
        self,
        active_only: bool = False,
    ) -> list[DataSource]:
        query = """
            SELECT
                id,
                source_key,
                name,
                base_url,
                is_active,
                metadata_json,
                created_at,
                updated_at
            FROM data_sources
        """
        parameters: tuple[object, ...] = ()

        if active_only:
            query += """
                WHERE is_active = ?
            """
            parameters = (1,)

        query += """
            ORDER BY name, id
        """

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def upsert(
        self,
        source_key: str,
        name: str,
        base_url: str | None = None,
        is_active: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> DataSource:
        existing_source = self.get_by_key(source_key)
        if (
            existing_source is not None
            and existing_source.name == name
            and existing_source.base_url == base_url
            and existing_source.is_active is is_active
            and existing_source.metadata == metadata
        ):
            return existing_source

        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO data_sources (
                    source_key,
                    name,
                    base_url,
                    is_active,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (source_key)
                DO UPDATE SET
                    name = excluded.name,
                    base_url = excluded.base_url,
                    is_active = excluded.is_active,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    source_key,
                    name,
                    base_url,
                    int(is_active),
                    metadata_json,
                    timestamp,
                    timestamp,
                ),
            )

        data_source = self.get_by_key(source_key)

        if data_source is None:
            raise RuntimeError(
                f"Data source could not be loaded after upsert: {source_key}"
            )

        return data_source

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
    def _map_row(row: sqlite3.Row) -> DataSource:
        metadata_json = row["metadata_json"]

        return DataSource(
            id=row["id"],
            source_key=row["source_key"],
            name=row["name"],
            base_url=row["base_url"],
            is_active=bool(row["is_active"]),
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
