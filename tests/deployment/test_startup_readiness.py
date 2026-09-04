import sqlite3
from pathlib import Path

import pytest
from scripts.check_startup_ready import startup_ready

STARTED_AT = "2026-09-04T10:00:00.123456789Z"


def test_missing_database_is_not_created(tmp_path: Path) -> None:
    path = tmp_path / "missing.db"
    assert not startup_ready(path, STARTED_AT)
    assert not path.exists()


def test_slow_initialization_waits_for_committed_startup(tmp_path: Path) -> None:
    path = tmp_path / "sports.db"
    with sqlite3.connect(path) as connection:
        assert not startup_ready(path, STARTED_AT)
        connection.execute(
            "CREATE TABLE system_status "
            "(id INTEGER PRIMARY KEY, started_at TEXT, status TEXT)"
        )
        connection.commit()
        assert not startup_ready(path, STARTED_AT)
        connection.execute(
            "INSERT INTO system_status VALUES (1, ?, 'started')",
            ("2026-09-04T10:00:05+00:00",),
        )
        assert not startup_ready(path, STARTED_AT)
        connection.commit()
        assert startup_ready(path, STARTED_AT)


@pytest.mark.parametrize(
    ("recorded_at", "status", "expected"),
    [
        ("2026-09-04T09:59:59+00:00", "started", False),
        ("2026-09-04T10:00:01+00:00", "started", True),
        ("2026-09-04T12:00:01+02:00", "started", True),
        ("2026-09-04T10:00:01+00:00", "failed", False),
        ("2026-09-04T10:00:01", "started", False),
    ],
)
def test_requires_current_successful_startup(
    tmp_path: Path, recorded_at: str, status: str, expected: bool
) -> None:
    path = tmp_path / "sports.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE system_status "
            "(id INTEGER PRIMARY KEY, started_at TEXT, status TEXT)"
        )
        connection.execute(
            "INSERT INTO system_status VALUES (1, ?, ?)", (recorded_at, status)
        )
    assert startup_ready(path, STARTED_AT) is expected


def test_restart_rejects_previous_startup(tmp_path: Path) -> None:
    path = tmp_path / "sports.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE system_status "
            "(id INTEGER PRIMARY KEY, started_at TEXT, status TEXT)"
        )
        connection.execute(
            "INSERT INTO system_status VALUES "
            "(1, '2026-09-04T10:00:01+00:00', 'started')"
        )
    assert startup_ready(path, STARTED_AT)
    assert not startup_ready(path, "2026-09-04T10:01:00Z")


def test_rejects_timezone_naive_container_start(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone"):
        startup_ready(tmp_path / "sports.db", "2026-09-04T10:00:00")
