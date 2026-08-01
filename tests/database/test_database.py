import sqlite3
from pathlib import Path

import pytest
from app.database.database import Database

EXPECTED_TABLES = {
    "betting_markets",
    "betting_odds_snapshots",
    "betting_outcomes",
    "bookmakers",
    "calendar_event_mappings",
    "competitions",
    "data_sources",
    "event_participants",
    "event_results",
    "event_statistics",
    "participants",
    "schema_migrations",
    "seasons",
    "source_mappings",
    "sports",
    "sports_events",
    "sync_runs",
    "system_status",
}


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "data" / "sports.db"


@pytest.fixture
def initialized_database(database_path: Path) -> Database:
    database = Database(database_path)
    database.initialize()
    return database


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def test_initialize_creates_database_file(
    initialized_database: Database,
    database_path: Path,
) -> None:
    assert database_path.exists()
    assert database_path.is_file()


def test_initialize_creates_expected_tables(
    initialized_database: Database,
    database_path: Path,
) -> None:
    with connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                """
            )
        }

    assert table_names == EXPECTED_TABLES


def test_initial_migration_is_registered_once(
    initialized_database: Database,
    database_path: Path,
) -> None:
    initialized_database.initialize()

    with connect(database_path) as connection:
        migrations = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

    assert migrations == [("001_initial_schema",)]


def test_repeated_initialize_preserves_existing_data(
    initialized_database: Database,
    database_path: Path,
) -> None:
    initialized_database.record_startup()
    initialized_database.initialize()

    with connect(database_path) as connection:
        startup_records = connection.execute(
            """
            SELECT status
            FROM system_status
            """
        ).fetchall()

    assert startup_records == [("started",)]


def test_record_startup_creates_record(
    initialized_database: Database,
    database_path: Path,
) -> None:
    initialized_database.record_startup()

    with connect(database_path) as connection:
        record = connection.execute(
            """
            SELECT started_at, status
            FROM system_status
            """
        ).fetchone()

    assert record is not None
    assert record[0] is not None
    assert record[1] == "started"


def test_database_connections_enable_foreign_keys(
    initialized_database: Database,
) -> None:
    with initialized_database._connect() as connection:
        foreign_keys_enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert foreign_keys_enabled == 1


def test_foreign_key_constraint_rejects_unknown_sport(
    initialized_database: Database,
    database_path: Path,
) -> None:
    with (
        connect(database_path) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute(
            """
                INSERT INTO competitions (
                    sport_id,
                    competition_key,
                    name,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
            (
                999,
                "premier-league",
                "Premier League",
                "2026-08-01T12:00:00+00:00",
                "2026-08-01T12:00:00+00:00",
            ),
        )


def test_invalid_json_is_rejected(
    initialized_database: Database,
    database_path: Path,
) -> None:
    with (
        connect(database_path) as connection,
        pytest.raises(sqlite3.IntegrityError),
    ):
        connection.execute(
            """
                INSERT INTO sports (
                    sport_key,
                    name,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
            (
                "football",
                "Football",
                "{invalid-json}",
                "2026-08-01T12:00:00+00:00",
                "2026-08-01T12:00:00+00:00",
            ),
        )


def test_invalid_event_status_is_rejected(
    initialized_database: Database,
    database_path: Path,
) -> None:
    timestamp = "2026-08-01T12:00:00+00:00"

    with connect(database_path) as connection:
        sport_id = connection.execute(
            """
            INSERT INTO sports (
                sport_key,
                name,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "football",
                "Football",
                timestamp,
                timestamp,
            ),
        ).lastrowid

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO sports_events (
                    sport_id,
                    event_key,
                    event_type,
                    title,
                    start_time,
                    status,
                    first_seen_at,
                    last_seen_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sport_id,
                    "test-event",
                    "match",
                    "Test Event",
                    timestamp,
                    "invalid-status",
                    timestamp,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )


def test_deleting_event_cascades_to_calendar_mapping(
    initialized_database: Database,
    database_path: Path,
) -> None:
    timestamp = "2026-08-01T12:00:00+00:00"

    with connect(database_path) as connection:
        sport_id = connection.execute(
            """
            INSERT INTO sports (
                sport_key,
                name,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                "football",
                "Football",
                timestamp,
                timestamp,
            ),
        ).lastrowid

        event_id = connection.execute(
            """
            INSERT INTO sports_events (
                sport_id,
                event_key,
                event_type,
                title,
                start_time,
                first_seen_at,
                last_seen_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sport_id,
                "football-test-event",
                "match",
                "Test Match",
                timestamp,
                timestamp,
                timestamp,
                timestamp,
                timestamp,
            ),
        ).lastrowid

        connection.execute(
            """
            INSERT INTO calendar_event_mappings (
                event_id,
                calendar_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                event_id,
                "test-calendar",
                timestamp,
                timestamp,
            ),
        )

        connection.execute(
            """
            DELETE FROM sports_events
            WHERE id = ?
            """,
            (event_id,),
        )

        mapping_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM calendar_event_mappings
            """
        ).fetchone()[0]

    assert mapping_count == 0


def write_migration(
    migrations_directory: Path,
    filename: str,
    sql: str,
) -> None:
    migrations_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    (migrations_directory / filename).write_text(
        sql,
        encoding="utf-8",
    )


def test_failed_migration_is_completely_rolled_back(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    migrations_directory = tmp_path / "migrations"

    write_migration(
        migrations_directory,
        "001_broken.sql",
        """
        CREATE TABLE first_table (
            id INTEGER PRIMARY KEY
        );

        CREATE TABLE broken_table (
            id INTEGER PRIMARY KEY,
        );
        """,
    )

    database = Database(
        database_path,
        migrations_directory=migrations_directory,
    )

    with pytest.raises(sqlite3.Error):
        database.initialize()

    with connect(database_path) as connection:
        first_table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'first_table'
            """
        ).fetchone()

        migration = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            WHERE version = ?
            """,
            ("001_broken",),
        ).fetchone()

    assert first_table is None
    assert migration is None


def test_fixed_migration_can_be_retried(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    migrations_directory = tmp_path / "migrations"

    write_migration(
        migrations_directory,
        "001_retry.sql",
        """
        CREATE TABLE retry_table (
            id INTEGER PRIMARY KEY,
        );
        """,
    )

    database = Database(
        database_path,
        migrations_directory=migrations_directory,
    )

    with pytest.raises(sqlite3.Error):
        database.initialize()

    write_migration(
        migrations_directory,
        "001_retry.sql",
        """
        CREATE TABLE retry_table (
            id INTEGER PRIMARY KEY
        );
        """,
    )

    database.initialize()

    with connect(database_path) as connection:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'retry_table'
            """
        ).fetchone()

        migrations = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            """
        ).fetchall()

    assert table == ("retry_table",)
    assert migrations == [("001_retry",)]


def test_successful_migration_remains_after_later_failure(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    migrations_directory = tmp_path / "migrations"

    write_migration(
        migrations_directory,
        "001_valid.sql",
        """
        CREATE TABLE valid_table (
            id INTEGER PRIMARY KEY
        );
        """,
    )

    write_migration(
        migrations_directory,
        "002_broken.sql",
        """
        CREATE TABLE partial_table (
            id INTEGER PRIMARY KEY
        );

        INVALID SQL;
        """,
    )

    database = Database(
        database_path,
        migrations_directory=migrations_directory,
    )

    with pytest.raises(sqlite3.Error):
        database.initialize()

    with connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        migrations = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

    assert "valid_table" in tables
    assert "partial_table" not in tables
    assert migrations == [("001_valid",)]


def test_migrations_are_applied_in_version_order(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    migrations_directory = tmp_path / "migrations"

    write_migration(
        migrations_directory,
        "002_add_name.sql",
        """
        ALTER TABLE ordered_table
        ADD COLUMN name TEXT;
        """,
    )

    write_migration(
        migrations_directory,
        "001_create_table.sql",
        """
        CREATE TABLE ordered_table (
            id INTEGER PRIMARY KEY
        );
        """,
    )

    database = Database(
        database_path,
        migrations_directory=migrations_directory,
    )
    database.initialize()

    with connect(database_path) as connection:
        migrations = connection.execute(
            """
            SELECT version
            FROM schema_migrations
            ORDER BY applied_at
            """
        ).fetchall()

        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(ordered_table)")
        }

    assert migrations == [
        ("001_create_table",),
        ("002_add_name",),
    ]
    assert columns == {"id", "name"}


def test_duplicate_migration_numbers_are_rejected(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    migrations_directory = tmp_path / "migrations"

    write_migration(
        migrations_directory,
        "001_create_sports.sql",
        "CREATE TABLE sports (id INTEGER PRIMARY KEY);",
    )

    write_migration(
        migrations_directory,
        "001_create_events.sql",
        "CREATE TABLE events (id INTEGER PRIMARY KEY);",
    )

    database = Database(
        database_path,
        migrations_directory=migrations_directory,
    )

    with pytest.raises(
        ValueError,
        match="Duplicate migration number: 001",
    ):
        database.initialize()


def test_invalid_migration_filename_is_rejected(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    migrations_directory = tmp_path / "migrations"

    write_migration(
        migrations_directory,
        "initial-schema.sql",
        "CREATE TABLE invalid_name (id INTEGER PRIMARY KEY);",
    )

    database = Database(
        database_path,
        migrations_directory=migrations_directory,
    )

    with pytest.raises(
        ValueError,
        match="Invalid migration filename",
    ):
        database.initialize()
