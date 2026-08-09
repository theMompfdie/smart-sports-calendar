import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.providers.contracts import SourceRole


@dataclass(frozen=True)
class SourceAssignment:
    id: int
    job_key: str
    source_id: int
    competition_id: int
    season_id: int
    role: SourceRole
    interval_seconds: int
    is_enabled: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SourceAssignmentWrite:
    job_key: str
    source_id: int
    competition_id: int
    season_id: int
    role: SourceRole
    interval_seconds: int


class SourceAssignmentsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def synchronize(
        self,
        assignments: tuple[SourceAssignmentWrite, ...],
    ) -> list[SourceAssignment]:
        timestamp = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE source_assignments SET is_enabled = 0, updated_at = ?",
                (timestamp,),
            )
            for assignment in assignments:
                enabled = assignment.role is not SourceRole.DISABLED
                connection.execute(
                    """
                    INSERT INTO source_assignments (
                        job_key, source_id, competition_id, season_id, role,
                        interval_seconds, is_enabled, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (job_key)
                    DO UPDATE SET
                        source_id = excluded.source_id,
                        competition_id = excluded.competition_id,
                        season_id = excluded.season_id,
                        role = excluded.role,
                        interval_seconds = excluded.interval_seconds,
                        is_enabled = excluded.is_enabled,
                        updated_at = excluded.updated_at
                    """,
                    (
                        assignment.job_key,
                        assignment.source_id,
                        assignment.competition_id,
                        assignment.season_id,
                        assignment.role.value,
                        assignment.interval_seconds,
                        int(enabled),
                        timestamp,
                        timestamp,
                    ),
                )
        return self.get_all()

    def get_all(self, *, enabled_only: bool = False) -> list[SourceAssignment]:
        query = """
            SELECT id, job_key, source_id, competition_id, season_id, role,
                   interval_seconds, is_enabled, created_at, updated_at
            FROM source_assignments
        """
        parameters: tuple[object, ...] = ()
        if enabled_only:
            query += " WHERE is_enabled = ?"
            parameters = (1,)
        query += " ORDER BY job_key"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
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
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
