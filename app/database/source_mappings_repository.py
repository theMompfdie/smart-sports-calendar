import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class SourceMappingConflictError(RuntimeError):
    """A provider mapping conflicts with an existing stable correlation."""


@dataclass(frozen=True)
class SourceMapping:
    id: int
    source_id: int
    object_type: str
    internal_id: int
    external_id: str
    source_url: str | None
    metadata: dict[str, Any] | None
    created_at: str
    updated_at: str


class SourceMappingsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get_by_external_id(
        self,
        source_id: int,
        object_type: str,
        external_id: str,
    ) -> SourceMapping | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    source_id,
                    object_type,
                    internal_id,
                    external_id,
                    source_url,
                    metadata_json,
                    created_at,
                    updated_at
                FROM source_mappings
                WHERE source_id = ?
                  AND object_type = ?
                  AND external_id = ?
                """,
                (
                    source_id,
                    object_type,
                    external_id,
                ),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_by_internal_id(
        self,
        source_id: int,
        object_type: str,
        internal_id: int,
    ) -> SourceMapping | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    source_id,
                    object_type,
                    internal_id,
                    external_id,
                    source_url,
                    metadata_json,
                    created_at,
                    updated_at
                FROM source_mappings
                WHERE source_id = ?
                  AND object_type = ?
                  AND internal_id = ?
                """,
                (
                    source_id,
                    object_type,
                    internal_id,
                ),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def get_for_source(
        self,
        source_id: int,
        object_type: str | None = None,
    ) -> list[SourceMapping]:
        query = """
            SELECT
                id,
                source_id,
                object_type,
                internal_id,
                external_id,
                source_url,
                metadata_json,
                created_at,
                updated_at
            FROM source_mappings
            WHERE source_id = ?
        """
        parameters: tuple[object, ...] = (source_id,)

        if object_type is not None:
            query += """
                AND object_type = ?
            """
            parameters = (
                source_id,
                object_type,
            )

        query += """
            ORDER BY object_type, internal_id, id
        """

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def upsert(
        self,
        source_id: int,
        object_type: str,
        internal_id: int,
        external_id: str,
        source_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SourceMapping:
        external_mapping = self.get_by_external_id(
            source_id=source_id,
            object_type=object_type,
            external_id=external_id,
        )
        if external_mapping is not None and external_mapping.internal_id != internal_id:
            raise SourceMappingConflictError(
                "External source mapping is already assigned to another "
                f"canonical object: source_id={source_id}, "
                f"object_type={object_type}, external_id={external_id}."
            )

        internal_mapping = self.get_by_internal_id(
            source_id=source_id,
            object_type=object_type,
            internal_id=internal_id,
        )
        if internal_mapping is not None and internal_mapping.external_id != external_id:
            raise SourceMappingConflictError(
                "Canonical object is already assigned to another external ID: "
                f"source_id={source_id}, object_type={object_type}, "
                f"internal_id={internal_id}."
            )

        if (
            external_mapping is not None
            and external_mapping.source_url == source_url
            and external_mapping.metadata == metadata
        ):
            return external_mapping

        timestamp = datetime.now(UTC).isoformat()
        metadata_json = self._serialize_metadata(metadata)

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO source_mappings (
                        source_id,
                        object_type,
                        internal_id,
                        external_id,
                        source_url,
                        metadata_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (
                        source_id,
                        object_type,
                        external_id
                    )
                    DO UPDATE SET
                        source_url = excluded.source_url,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at
                    WHERE source_mappings.internal_id = excluded.internal_id
                    """,
                    (
                        source_id,
                        object_type,
                        internal_id,
                        external_id,
                        source_url,
                        metadata_json,
                        timestamp,
                        timestamp,
                    ),
                )
        except sqlite3.IntegrityError as error:
            conflicting_mapping = self.get_by_internal_id(
                source_id=source_id,
                object_type=object_type,
                internal_id=internal_id,
            )
            if (
                conflicting_mapping is not None
                and conflicting_mapping.external_id != external_id
            ):
                raise SourceMappingConflictError(
                    "Canonical object is already assigned to another external ID: "
                    f"source_id={source_id}, object_type={object_type}, "
                    f"internal_id={internal_id}."
                ) from error
            raise

        mapping = self.get_by_external_id(
            source_id=source_id,
            object_type=object_type,
            external_id=external_id,
        )

        if mapping is None:
            raise RuntimeError(
                "Source mapping could not be loaded after upsert: "
                f"source_id={source_id}, "
                f"object_type={object_type}, "
                f"external_id={external_id}"
            )

        if mapping.internal_id != internal_id:
            raise SourceMappingConflictError(
                "External source mapping is already assigned to another "
                f"canonical object: source_id={source_id}, "
                f"object_type={object_type}, external_id={external_id}."
            )

        return mapping

    def delete(
        self,
        source_id: int,
        object_type: str,
        external_id: str,
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM source_mappings
                WHERE source_id = ?
                  AND object_type = ?
                  AND external_id = ?
                """,
                (
                    source_id,
                    object_type,
                    external_id,
                ),
            )

        return cursor.rowcount > 0

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
    def _map_row(row: sqlite3.Row) -> SourceMapping:
        metadata_json = row["metadata_json"]

        return SourceMapping(
            id=row["id"],
            source_id=row["source_id"],
            object_type=row["object_type"],
            internal_id=row["internal_id"],
            external_id=row["external_id"],
            source_url=row["source_url"],
            metadata=(json.loads(metadata_json) if metadata_json is not None else None),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
