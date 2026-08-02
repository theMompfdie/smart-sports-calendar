import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class SeasonParticipant:
    id: int
    season_id: int
    participant_id: int
    created_at: str
    updated_at: str


class SeasonParticipantsRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def get(
        self,
        season_id: int,
        participant_id: int,
    ) -> SeasonParticipant | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, season_id, participant_id, created_at, updated_at
                FROM season_participants
                WHERE season_id = ?
                  AND participant_id = ?
                """,
                (season_id, participant_id),
            ).fetchone()

        return None if row is None else self._map_row(row)

    def list_by_season(self, season_id: int) -> list[SeasonParticipant]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, season_id, participant_id, created_at, updated_at
                FROM season_participants
                WHERE season_id = ?
                ORDER BY participant_id
                """,
                (season_id,),
            ).fetchall()

        return [self._map_row(row) for row in rows]

    def upsert(
        self,
        season_id: int,
        participant_id: int,
    ) -> SeasonParticipant:
        timestamp = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO season_participants (
                    season_id,
                    participant_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT (season_id, participant_id)
                DO UPDATE SET updated_at = excluded.updated_at
                """,
                (season_id, participant_id, timestamp, timestamp),
            )

        membership = self.get(season_id, participant_id)
        if membership is None:
            raise RuntimeError(
                "Season participant could not be loaded after upsert: "
                f"season={season_id}, participant={participant_id}"
            )
        return membership

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _map_row(row: sqlite3.Row) -> SeasonParticipant:
        return SeasonParticipant(
            id=row["id"],
            season_id=row["season_id"],
            participant_id=row["participant_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
