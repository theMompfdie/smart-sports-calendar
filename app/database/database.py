import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


MIGRATION_FILE_PATTERN = re.compile(
    r"^(?P<number>\d{3})_[a-z0-9_]+\.sql$"
)


class Database:
    def __init__(
        self,
        database_path: Path,
        migrations_directory: Path | None = None,
    ) -> None:
        self.database_path = database_path
        self.migrations_directory = (
            migrations_directory
            if migrations_directory is not None
            else Path(__file__).parent / "migrations"
        )

    def initialize(self) -> None:
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._connect() as connection:
            self._create_migration_table(connection)
            self._apply_migrations(connection)

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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _create_migration_table(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.commit()

    def _apply_migrations(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        migration_paths = self._get_migration_paths()

        for migration_path in migration_paths:
            version = migration_path.stem

            existing_migration = connection.execute(
                """
                SELECT version
                FROM schema_migrations
                WHERE version = ?
                """,
                (version,),
            ).fetchone()

            if existing_migration is not None:
                continue

            migration_sql = migration_path.read_text(
                encoding="utf-8",
            )

            self._apply_migration(
                connection=connection,
                version=version,
                migration_sql=migration_sql,
            )

    def _get_migration_paths(self) -> list[Path]:
        if not self.migrations_directory.exists():
            raise FileNotFoundError(
                "Migrations directory does not exist: "
                f"{self.migrations_directory}"
            )

        migration_paths = sorted(
            self.migrations_directory.glob("*.sql"),
        )

        migration_numbers: set[str] = set()

        for migration_path in migration_paths:
            match = MIGRATION_FILE_PATTERN.fullmatch(
                migration_path.name
            )

            if match is None:
                raise ValueError(
                    "Invalid migration filename: "
                    f"{migration_path.name}. "
                    "Expected format: 001_description.sql"
                )

            migration_number = match.group("number")

            if migration_number in migration_numbers:
                raise ValueError(
                    "Duplicate migration number: "
                    f"{migration_number}"
                )

            migration_numbers.add(migration_number)

        return migration_paths

    @staticmethod
    def _apply_migration(
        connection: sqlite3.Connection,
        version: str,
        migration_sql: str,
    ) -> None:
        applied_at = datetime.now(UTC).isoformat()

        quoted_version = Database._quote_sql_literal(version)
        quoted_applied_at = Database._quote_sql_literal(applied_at)

        migration_script = f"""
            BEGIN IMMEDIATE;

            {migration_sql}

            INSERT INTO schema_migrations (
                version,
                applied_at
            )
            VALUES (
                {quoted_version},
                {quoted_applied_at}
            );

            COMMIT;
        """

        try:
            connection.executescript(migration_script)
        except sqlite3.Error:
            if connection.in_transaction:
                connection.rollback()

            raise

    @staticmethod
    def _quote_sql_literal(value: str) -> str:
        escaped_value = value.replace("'", "''")
        return f"'{escaped_value}'"