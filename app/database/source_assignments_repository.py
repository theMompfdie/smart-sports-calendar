import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.imports.manual_manifest import IDENTIFIER
from app.providers.contracts import SourceRole


@dataclass(frozen=True)
class SourceAssignment:
    id: int
    job_key: str
    source_id: int
    competition_id: int
    season_id: int
    role: SourceRole
    interval_seconds: int | None
    is_enabled: bool
    created_at: str
    updated_at: str
    namespace: str | None = None
    stages: frozenset[str] | None = None


@dataclass(frozen=True)
class SourceAssignmentWrite:
    job_key: str
    source_id: int
    competition_id: int
    season_id: int
    role: SourceRole
    interval_seconds: int | None
    namespace: str | None = None
    stages: frozenset[str] | None = None


class SourceAssignmentsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def synchronize(
        self, assignments: tuple[SourceAssignmentWrite, ...]
    ) -> list[SourceAssignment]:
        timestamp = datetime.now(UTC).isoformat()
        by_key = {item.job_key: item for item in assignments}
        if len(by_key) != len(assignments):
            raise ValueError("Duplicate source assignment job key.")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for row in connection.execute(
                "SELECT * FROM source_assignments"
            ).fetchall():
                item = by_key.get(row["job_key"])
                # Automated bootstrap never disables operator-owned manual grants.
                if item is None and row["namespace"] is not None:
                    continue
                disabled = item is None or item.role is SourceRole.DISABLED
                changed = item is not None and any(
                    (
                        row["source_id"] != item.source_id,
                        row["competition_id"] != item.competition_id,
                        row["season_id"] != item.season_id,
                        row["role"] != item.role.value,
                        row["stages_json"] != self._stages_json(item),
                    )
                )
                if row["is_enabled"] and (disabled or changed):
                    connection.execute(
                        """UPDATE source_assignments
                        SET is_enabled=0,updated_at=? WHERE id=?""",
                        (timestamp, row["id"]),
                    )
            for item in assignments:
                self.write_connection(connection, item, timestamp)
        return self.get_all()

    @staticmethod
    def _stages_json(item: SourceAssignmentWrite) -> str | None:
        if item.stages is None:
            return None
        if not item.stages or any(
            not IDENTIFIER.fullmatch(stage) for stage in item.stages
        ):
            raise ValueError("Authority requires explicit nonempty stage identifiers.")
        return json.dumps(sorted(item.stages))

    @staticmethod
    def write_connection(
        connection: sqlite3.Connection, item: SourceAssignmentWrite, timestamp: str
    ) -> None:
        if not connection.in_transaction:
            raise ValueError("Source assignment requires a caller-owned transaction.")
        stages = SourceAssignmentsRepository._stages_json(item)
        existing = connection.execute(
            "SELECT * FROM source_assignments WHERE job_key=?", (item.job_key,)
        ).fetchone()
        if existing is not None and existing["namespace"] != item.namespace:
            raise ValueError("Cannot repurpose a manual assignment identity.")
        if (
            existing is not None
            and item.namespace is not None
            and any(
                existing[key] != getattr(item, key)
                for key in ("source_id", "competition_id", "season_id")
            )
        ):
            raise ValueError("Cannot move an established manual namespace.")
        if item.namespace is not None:
            if (
                not IDENTIFIER.fullmatch(item.namespace)
                or item.interval_seconds is not None
                or item.stages is None
            ):
                raise ValueError(
                    "Manual grants require a namespace, stages and no timer."
                )
            source = connection.execute(
                "SELECT source_key FROM data_sources WHERE id=?", (item.source_id,)
            ).fetchone()
            if source is None or source["source_key"] != "manual":
                raise ValueError("Manual namespace requires the manual data source.")
        if item.stages is not None and item.role is SourceRole.AUTHORITATIVE:
            rows = connection.execute(
                """SELECT e.stage FROM sports_events AS e
                JOIN source_mappings AS m ON m.internal_id=e.id
                    AND m.object_type='event'
                WHERE m.source_id=? AND e.competition_id=? AND e.season_id=?
                  AND (? IS NULL OR substr(m.external_id,1,length(?)+1)=? || ':')""",
                (
                    item.source_id,
                    item.competition_id,
                    item.season_id,
                    item.namespace,
                    item.namespace,
                    item.namespace,
                ),
            ).fetchall()
            if any(row["stage"] not in item.stages for row in rows):
                raise ValueError(
                    "Existing source mappings exceed the proposed stage grant."
                )
        connection.execute(
            """INSERT INTO source_assignments
            (job_key,source_id,competition_id,season_id,role,interval_seconds,
             is_enabled,created_at,updated_at,namespace,stages_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_key) DO UPDATE SET
            source_id=excluded.source_id, competition_id=excluded.competition_id,
            season_id=excluded.season_id, role=excluded.role,
            interval_seconds=excluded.interval_seconds,is_enabled=excluded.is_enabled,
            updated_at=excluded.updated_at,namespace=excluded.namespace,
            stages_json=excluded.stages_json
            WHERE source_assignments.source_id IS NOT excluded.source_id
               OR source_assignments.competition_id IS NOT excluded.competition_id
               OR source_assignments.season_id IS NOT excluded.season_id
               OR source_assignments.role IS NOT excluded.role
               OR source_assignments.interval_seconds IS NOT excluded.interval_seconds
               OR source_assignments.is_enabled IS NOT excluded.is_enabled
               OR source_assignments.stages_json IS NOT excluded.stages_json""",
            (
                item.job_key,
                item.source_id,
                item.competition_id,
                item.season_id,
                item.role.value,
                item.interval_seconds,
                int(item.role is not SourceRole.DISABLED),
                timestamp,
                timestamp,
                item.namespace,
                stages,
            ),
        )

    def get_all(self, *, enabled_only: bool = False) -> list[SourceAssignment]:
        query = "SELECT * FROM source_assignments"
        if enabled_only:
            query += " WHERE is_enabled=1"
        with self._connect() as connection:
            rows = connection.execute(query + " ORDER BY job_key").fetchall()
        return [
            SourceAssignment(
                id=row["id"],
                job_key=row["job_key"],
                source_id=row["source_id"],
                competition_id=row["competition_id"],
                season_id=row["season_id"],
                role=SourceRole(row["role"]),
                interval_seconds=row["interval_seconds"],
                is_enabled=bool(row["is_enabled"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                namespace=row["namespace"],
                stages=None
                if row["stages_json"] is None
                else frozenset(json.loads(row["stages_json"])),
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
