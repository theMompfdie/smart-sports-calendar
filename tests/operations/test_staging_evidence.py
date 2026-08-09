import json
from pathlib import Path

import pytest
from app.database.database import Database
from app.database.sync_runs_repository import SyncRunsRepository
from app.operations.staging_evidence import (
    collect_staging_evidence,
    main,
    render_staging_evidence,
)


def create_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "sports.db"
    database = Database(database_path)
    database.initialize()
    database.record_startup()
    return database_path


def test_collect_staging_evidence_returns_only_safe_operational_fields(
    tmp_path: Path,
) -> None:
    database_path = create_database(tmp_path)
    repository = SyncRunsRepository(database_path)

    completed = repository.start(
        run_type="provider_import",
        metadata={"api_key": "provider-secret", "calendar_id": "calendar-secret"},
    )
    repository.complete(
        completed.id,
        items_processed=8,
        items_created=5,
        items_updated=1,
        items_unchanged=2,
        items_deleted=0,
        items_failed=0,
        metadata={"authorization": "Bearer graph-secret"},
    )
    failed = repository.start(run_type="calendar_sync")
    repository.fail(
        failed.id,
        error_message="request exposed-secret failed",
        metadata={"url": "https://example.invalid/?token=secret-value"},
    )

    evidence = collect_staging_evidence(database_path)
    rendered = render_staging_evidence(evidence)
    payload = json.loads(rendered)

    assert payload["database_quick_check"] == "ok"
    assert payload["schema_version"] == "007_create_source_assignments"
    assert payload["startup_records"] == 1
    assert payload["sports_events"] == 0
    assert payload["calendar_mappings_by_status"] == {}
    assert [run["run_type"] for run in payload["recent_runs"]] == [
        "calendar_sync",
        "provider_import",
    ]
    assert payload["recent_runs"][1]["items_created"] == 5
    assert "provider-secret" not in rendered
    assert "calendar-secret" not in rendered
    assert "graph-secret" not in rendered
    assert "exposed-secret" not in rendered
    assert "secret-value" not in rendered
    assert "metadata" not in rendered
    assert "error_message" not in rendered


def test_collect_staging_evidence_is_read_only(tmp_path: Path) -> None:
    database_path = create_database(tmp_path)

    first = collect_staging_evidence(database_path)
    second = collect_staging_evidence(database_path)

    assert first == second


def test_collect_staging_evidence_rejects_invalid_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        collect_staging_evidence(tmp_path / "missing.db")

    database_path = create_database(tmp_path)
    with pytest.raises(ValueError, match="limit must be greater than zero"):
        collect_staging_evidence(database_path, limit=0)


def test_main_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    database_path = create_database(tmp_path)

    result = main(["--database", str(database_path), "--limit", "1"])

    assert result == 0
    assert json.loads(capsys.readouterr().out)["database_quick_check"] == "ok"
