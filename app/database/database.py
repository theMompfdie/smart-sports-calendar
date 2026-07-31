import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class Database:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS system_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )

            connection.commit()

    def record_startup(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO system_status (
                    started_at,
                    status
                )
                VALUES (?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    "started",
                ),
            )

            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)
