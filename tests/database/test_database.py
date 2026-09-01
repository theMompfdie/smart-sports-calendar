import sqlite3
from pathlib import Path
from shutil import copy2
from uuid import uuid4

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
    "fixture_reconciliation_state",
    "participants",
    "reminder_rules",
    "schema_migrations",
    "season_participants",
    "seasons",
    "source_mappings",
    "source_assignments",
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


def test_migrations_are_registered_once(
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

    assert migrations == [
        ("001_initial_schema",),
        ("002_create_season_participants",),
        ("003_extend_sync_run_counters",),
        ("004_add_mapping_transaction_id",),
        ("005_create_fixture_reconciliation_state",),
        ("006_extend_provider_import_runs",),
        ("007_create_source_assignments",),
        ("008_add_calendar_sync_revisions",),
        ("009_create_reminder_rules",),
        ("010_add_presentation_sync_revisions",),
    ]


def test_presentation_revision_schema_is_monotonic_and_indexed(
    initialized_database: Database,
    database_path: Path,
) -> None:
    with connect(database_path) as connection:
        columns = {
            row[1]: row
            for row in connection.execute("PRAGMA table_info(calendar_event_mappings)")
        }
        indexes = {
            row[1]
            for row in connection.execute("PRAGMA index_list(calendar_event_mappings)")
        }

    assert columns["presentation_revision"][3] == 1
    assert columns["presentation_revision"][4] == "1"
    assert columns["last_synced_presentation_revision"][3] == 1
    assert columns["last_synced_presentation_revision"][4] == "0"
    assert "idx_calendar_mappings_presentation_revision" in indexes


def test_reminder_rules_schema_has_scope_and_policy_constraints(
    initialized_database: Database,
    database_path: Path,
) -> None:
    with connect(database_path) as connection:
        columns = {
            row[1]: row
            for row in connection.execute("PRAGMA table_info(reminder_rules)")
        }
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(reminder_rules)")
        }

    assert columns["scope"][3] == 1
    assert columns["is_active"][3] == 1
    assert columns["is_active"][4] == "1"
    assert columns["deleted_at"][3] == 0
    assert {
        "uq_reminder_rules_global_current",
        "uq_reminder_rules_competition_current",
        "uq_reminder_rules_participant_current",
        "uq_reminder_rules_competition_participant_current",
        "uq_reminder_rules_event_current",
        "idx_reminder_rules_active_scope",
    }.issubset(indexes)


def test_fixture_reconciliation_state_has_stable_constraints(
    initialized_database: Database,
    database_path: Path,
) -> None:
    with connect(database_path) as connection:
        columns = {
            row[1]: row
            for row in connection.execute(
                "PRAGMA table_info(fixture_reconciliation_state)"
            )
        }
        indexes = connection.execute(
            "PRAGMA index_list(fixture_reconciliation_state)"
        ).fetchall()

    assert columns["missing_observation_count"][3] == 1
    assert columns["missing_observation_count"][4] == "0"
    assert columns["last_observation_id"][2] == "TEXT"
    assert sum(index[2] == 1 for index in indexes) == 2


def test_sync_runs_contains_extended_counters(
    initialized_database: Database,
    database_path: Path,
) -> None:
    with connect(database_path) as connection:
        columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(sync_runs)")
        }

    assert "items_unchanged" in columns
    assert columns["items_unchanged"][2] == "INTEGER"
    assert columns["items_unchanged"][3] == 1
    assert columns["items_unchanged"][4] == "0"

    assert "items_cancelled" in columns
    assert columns["items_cancelled"][2] == "INTEGER"
    assert columns["items_cancelled"][3] == 1
    assert columns["items_cancelled"][4] == "0"

    assert "items_deferred" in columns
    assert columns["items_deferred"][2] == "INTEGER"
    assert columns["items_deferred"][3] == 1
    assert columns["items_deferred"][4] == "0"


def test_sync_runs_accepts_dedicated_provider_import_type(
    initialized_database: Database,
    database_path: Path,
) -> None:
    timestamp = "2026-08-08T12:00:00+00:00"
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO sync_runs (run_type, started_at)
            VALUES ('provider_import', ?)
            """,
            (timestamp,),
        )


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

        transaction_id = str(uuid4())

        connection.execute(
            """
            INSERT INTO calendar_event_mappings (
                event_id,
                calendar_id,
                transaction_id,
                sync_status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (
                event_id,
                "calendar-id",
                transaction_id,
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


def test_calendar_event_mappings_contains_transaction_id(
    initialized_database: Database,
    database_path: Path,
) -> None:
    with connect(database_path) as connection:
        columns = {
            row[1]: row
            for row in connection.execute("PRAGMA table_info(calendar_event_mappings)")
        }

        indexes = connection.execute(
            "PRAGMA index_list(calendar_event_mappings)"
        ).fetchall()

    assert "transaction_id" in columns
    assert columns["transaction_id"][2] == "TEXT"
    assert columns["transaction_id"][3] == 1
    assert any(index[2] == 1 for index in indexes)


def test_source_assignment_migration_preserves_existing_source_mapping(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    legacy_migrations = tmp_path / "legacy-migrations"
    legacy_migrations.mkdir()
    migrations = Path(__file__).parents[2] / "app" / "database" / "migrations"
    for migration in sorted(migrations.glob("00[1-6]_*.sql")):
        copy2(migration, legacy_migrations / migration.name)
    Database(database_path, migrations_directory=legacy_migrations).initialize()
    timestamp = "2026-08-09T12:00:00+00:00"
    with connect(database_path) as connection:
        source_id = connection.execute(
            """
            INSERT INTO data_sources (
                source_key, name, is_active, created_at, updated_at
            ) VALUES ('legacy', 'Legacy', 1, ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid
        sport_id = connection.execute(
            """
            INSERT INTO sports (sport_key, name, created_at, updated_at)
            VALUES ('football', 'Football', ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO source_mappings (
                source_id, object_type, internal_id, external_id,
                created_at, updated_at
            ) VALUES (?, 'sport', ?, 'legacy-football', ?, ?)
            """,
            (source_id, sport_id, timestamp, timestamp),
        )

    Database(database_path).initialize()

    with connect(database_path) as connection:
        mapping = connection.execute(
            """
            SELECT source_id, object_type, internal_id, external_id
            FROM source_mappings
            """
        ).fetchone()
    assert mapping == (source_id, "sport", sport_id, "legacy-football")


def test_sync_revision_migration_preserves_data_and_queues_reconciliation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    legacy_migrations = tmp_path / "legacy-migrations"
    legacy_migrations.mkdir()
    migrations = Path(__file__).parents[2] / "app" / "database" / "migrations"
    for migration in sorted(migrations.glob("00[1-7]_*.sql")):
        copy2(migration, legacy_migrations / migration.name)
    Database(database_path, migrations_directory=legacy_migrations).initialize()
    timestamp = "2026-08-27T20:00:00+00:00"
    with connect(database_path) as connection:
        sport_id = connection.execute(
            """
            INSERT INTO sports (sport_key, name, created_at, updated_at)
            VALUES ('football', 'Football', ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid
        event_id = connection.execute(
            """
            INSERT INTO sports_events (
                sport_id, event_key, event_type, title, start_time,
                first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, 'legacy-fixture', 'match', 'Legacy fixture', ?, ?, ?, ?, ?)
            """,
            (sport_id, timestamp, timestamp, timestamp, timestamp, timestamp),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO calendar_event_mappings (
                event_id, calendar_id, transaction_id, outlook_event_id,
                content_hash, sync_status, last_synced_at, created_at, updated_at
            ) VALUES (?, 'calendar-1', ?, 'outlook-1', 'hash-1', 'synced', ?, ?, ?)
            """,
            (event_id, str(uuid4()), timestamp, timestamp, timestamp),
        )

    Database(database_path).initialize()

    with connect(database_path) as connection:
        migrated = connection.execute(
            """
            SELECT event.sync_revision, mapping.last_synced_revision,
                   mapping.sync_status
            FROM sports_events AS event
            JOIN calendar_event_mappings AS mapping ON mapping.event_id = event.id
            """
        ).fetchone()

    assert migrated == (1, 0, "synced")


def test_reminder_rule_migration_preserves_existing_events(tmp_path: Path) -> None:
    database_path = tmp_path / "sports.db"
    legacy_migrations = tmp_path / "legacy-migrations"
    legacy_migrations.mkdir()
    migrations = Path(__file__).parents[2] / "app" / "database" / "migrations"
    for migration in sorted(migrations.glob("00[1-8]_*.sql")):
        copy2(migration, legacy_migrations / migration.name)
    Database(database_path, migrations_directory=legacy_migrations).initialize()
    timestamp = "2026-09-01T10:00:00+00:00"
    with connect(database_path) as connection:
        sport_id = connection.execute(
            """
            INSERT INTO sports (sport_key, name, created_at, updated_at)
            VALUES ('football', 'Football', ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO sports_events (
                sport_id, event_key, event_type, title, start_time,
                first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, 'existing-fixture', 'match', 'Existing fixture', ?, ?, ?, ?, ?)
            """,
            (sport_id, timestamp, timestamp, timestamp, timestamp, timestamp),
        )

    database = Database(database_path)
    database.initialize()
    database.initialize()

    with connect(database_path) as connection:
        event = connection.execute(
            "SELECT event_key, title FROM sports_events"
        ).fetchone()
        rules = connection.execute("SELECT COUNT(*) FROM reminder_rules").fetchone()
        migration = connection.execute(
            """
            SELECT COUNT(*) FROM schema_migrations
            WHERE version = '009_create_reminder_rules'
            """
        ).fetchone()

    assert event == ("existing-fixture", "Existing fixture")
    assert rules == (0,)
    assert migration == (1,)


def test_presentation_revision_migration_queues_existing_mapping(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "sports.db"
    legacy_migrations = tmp_path / "legacy-migrations"
    legacy_migrations.mkdir()
    migrations = Path(__file__).parents[2] / "app" / "database" / "migrations"
    for migration in sorted(migrations.glob("00[1-9]_*.sql")):
        copy2(migration, legacy_migrations / migration.name)
    Database(database_path, migrations_directory=legacy_migrations).initialize()
    timestamp = "2026-09-01T10:00:00+00:00"
    with connect(database_path) as connection:
        sport_id = connection.execute(
            """
            INSERT INTO sports (sport_key, name, created_at, updated_at)
            VALUES ('football', 'Football', ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid
        event_id = connection.execute(
            """
            INSERT INTO sports_events (
                sport_id, event_key, event_type, title, start_time,
                first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, 'existing-fixture', 'match', 'Existing fixture', ?, ?, ?, ?, ?)
            """,
            (sport_id, timestamp, timestamp, timestamp, timestamp, timestamp),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO calendar_event_mappings (
                event_id, calendar_id, transaction_id, outlook_event_id,
                content_hash, sync_status, last_synced_revision,
                created_at, updated_at
            ) VALUES (?, 'calendar-1', ?, 'outlook-1', 'hash-1', 'synced', 1, ?, ?)
            """,
            (event_id, str(uuid4()), timestamp, timestamp),
        )

    Database(database_path).initialize()

    with connect(database_path) as connection:
        revisions = connection.execute(
            """
            SELECT presentation_revision, last_synced_presentation_revision,
                   sync_revision, last_synced_revision
            FROM calendar_event_mappings
            JOIN sports_events ON sports_events.id = calendar_event_mappings.event_id
            """
        ).fetchone()

    assert revisions == (1, 0, 1, 1)
