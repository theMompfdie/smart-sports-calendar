import sqlite3
from pathlib import Path

import pytest
from app.database.database import Database
from app.database.source_assignments_repository import (
    SourceAssignmentsRepository,
    SourceAssignmentWrite,
)
from app.providers.contracts import SourceRole


def create_scope(database_path: Path) -> tuple[int, int, int, int]:
    Database(database_path).initialize()
    timestamp = "2026-08-09T12:00:00+00:00"
    with sqlite3.connect(database_path) as connection:
        first_source_id = connection.execute(
            """
            INSERT INTO data_sources (
                source_key, name, is_active, created_at, updated_at
            ) VALUES ('first', 'First', 1, ?, ?)
            """,
            (timestamp, timestamp),
        ).lastrowid
        second_source_id = connection.execute(
            """
            INSERT INTO data_sources (
                source_key, name, is_active, created_at, updated_at
            ) VALUES ('second', 'Second', 1, ?, ?)
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
        competition_id = connection.execute(
            """
            INSERT INTO competitions (
                sport_id, competition_key, name, created_at, updated_at
            ) VALUES (?, 'premier_league', 'Premier League', ?, ?)
            """,
            (sport_id, timestamp, timestamp),
        ).lastrowid
        season_id = connection.execute(
            """
            INSERT INTO seasons (
                competition_id, season_key, name, created_at, updated_at
            ) VALUES (?, '2026_27', '2026/27', ?, ?)
            """,
            (competition_id, timestamp, timestamp),
        ).lastrowid
    assert first_source_id is not None
    assert second_source_id is not None
    assert competition_id is not None
    assert season_id is not None
    return first_source_id, second_source_id, competition_id, season_id


def write(
    job_key: str,
    source_id: int,
    competition_id: int,
    season_id: int,
    role: SourceRole,
) -> SourceAssignmentWrite:
    return SourceAssignmentWrite(
        job_key=job_key,
        source_id=source_id,
        competition_id=competition_id,
        season_id=season_id,
        role=role,
        interval_seconds=3600,
    )


def test_synchronize_preserves_rows_and_disables_removed_jobs(tmp_path: Path) -> None:
    database_path = tmp_path / "sports.db"
    first, second, competition, season = create_scope(database_path)
    repository = SourceAssignmentsRepository(database_path)
    repository.synchronize(
        (
            write(
                "authority",
                first,
                competition,
                season,
                SourceRole.AUTHORITATIVE,
            ),
            write(
                "verification",
                second,
                competition,
                season,
                SourceRole.VERIFICATION,
            ),
        )
    )

    before = repository.get_all()
    after = repository.synchronize(
        (
            write(
                "authority",
                first,
                competition,
                season,
                SourceRole.AUTHORITATIVE,
            ),
        )
    )

    assert [item.job_key for item in after] == ["authority", "verification"]
    assert after[0].id == before[0].id
    assert after[0].is_enabled is True
    assert after[1].is_enabled is False


def test_database_rejects_two_active_authorities_for_scope(tmp_path: Path) -> None:
    database_path = tmp_path / "sports.db"
    first, second, competition, season = create_scope(database_path)
    repository = SourceAssignmentsRepository(database_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.synchronize(
            (
                write(
                    "first",
                    first,
                    competition,
                    season,
                    SourceRole.AUTHORITATIVE,
                ),
                write(
                    "second",
                    second,
                    competition,
                    season,
                    SourceRole.AUTHORITATIVE,
                ),
            )
        )

    assert repository.get_all() == []
