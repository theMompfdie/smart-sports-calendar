import json
from pathlib import Path

import pytest
from app.database.database import Database
from app.database.participants_repository import ParticipantsRepository
from app.database.reminder_rules_repository import ReminderRulesRepository
from app.database.sports_repository import SportsRepository
from app.operations.reminder_rules import main


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "sports.db"
    Database(path).initialize()
    sports = SportsRepository(path)
    participants = ParticipantsRepository(path)
    football = sports.upsert("football", "Football", "⚽")
    american_football = sports.upsert(
        "american_football",
        "American Football",
        "🏈",
    )
    participants.upsert(
        football.id,
        "manchester_united",
        "team",
        "Manchester United",
    )
    participants.upsert(
        american_football.id,
        "new_england_patriots",
        "team",
        "New England Patriots",
    )
    return path


def run(database_path: Path, *arguments: str) -> int:
    return main(("--database", str(database_path), *arguments))


def test_list_outputs_empty_secret_safe_json(
    database_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run(database_path, "list") == 0

    assert json.loads(capsys.readouterr().out) == []


def test_set_show_and_replace_global_rule(
    database_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        run(
            database_path,
            "set",
            "--scope",
            "global",
            "--action",
            "suppress",
            "--note",
            "Selected teams only",
        )
        == 0
    )
    created = json.loads(capsys.readouterr().out)

    assert created["scope"] == "global"
    assert created["action"] == "suppress"
    assert created["operator_note"] == "Selected teams only"
    assert "id" not in created
    assert str(database_path) not in json.dumps(created)

    assert (
        run(
            database_path,
            "set",
            "--scope",
            "global",
            "--action",
            "enable",
            "--preferred-lead-minutes",
            "30",
        )
        == 0
    )
    updated = json.loads(capsys.readouterr().out)
    assert updated["action"] == "enable"
    assert updated["preferred_lead_minutes"] == 30
    assert updated["operator_note"] is None
    assert len(ReminderRulesRepository(database_path).list()) == 1

    assert run(database_path, "show", "--scope", "global") == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown == updated


@pytest.mark.parametrize(
    ("participant_key", "preferred"),
    [
        ("manchester_united", "60"),
        ("new_england_patriots", "480"),
    ],
)
def test_set_resolves_operator_team_keys(
    database_path: Path,
    capsys: pytest.CaptureFixture[str],
    participant_key: str,
    preferred: str,
) -> None:
    assert (
        run(
            database_path,
            "set",
            "--scope",
            "participant",
            "--participant",
            participant_key,
            "--action",
            "enable",
            "--preferred-lead-minutes",
            preferred,
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["participant"] == participant_key
    assert payload["preferred_lead_minutes"] == int(preferred)


def test_disable_and_delete_are_auditable(
    database_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run(database_path, "set", "--scope", "global", "--action", "suppress")
    capsys.readouterr()

    assert run(database_path, "disable", "--scope", "global") == 0
    disabled = json.loads(capsys.readouterr().out)
    assert disabled["active"] is False
    assert disabled["deleted_at"] is None

    assert run(database_path, "delete", "--scope", "global") == 0
    deleted = json.loads(capsys.readouterr().out)
    assert deleted["active"] is False
    assert deleted["deleted_at"] is not None

    assert run(database_path, "list") == 0
    assert json.loads(capsys.readouterr().out) == []
    assert run(database_path, "list", "--include-deleted") == 0
    assert len(json.loads(capsys.readouterr().out)) == 1


@pytest.mark.parametrize(
    "arguments",
    [
        ("--scope", "global", "--preferred-lead-minutes", "-1"),
        ("--scope", "global", "--quiet-start", "22:00"),
        ("--scope", "global", "--timezone", "Invalid/Zone"),
        (
            "--scope",
            "participant",
            "--participant",
            "unknown_team",
            "--action",
            "enable",
        ),
    ],
)
def test_invalid_set_fails_without_persisting_rule(
    database_path: Path,
    capsys: pytest.CaptureFixture[str],
    arguments: tuple[str, ...],
) -> None:
    with pytest.raises(SystemExit) as captured:
        run(database_path, "set", *arguments)

    output = capsys.readouterr()
    assert captured.value.code == 1
    assert output.out == ""
    assert "Reminder rule command failed:" in output.err
    assert str(database_path) not in output.err
    assert ReminderRulesRepository(database_path).list() == []


def test_database_failure_does_not_expose_path(
    database_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_initialize(database: Database) -> None:
        raise OSError(f"Cannot open private database at {database.database_path}")

    monkeypatch.setattr(Database, "initialize", fail_initialize)

    with pytest.raises(SystemExit) as captured:
        run(database_path, "list")

    output = capsys.readouterr()
    assert captured.value.code == 1
    assert output.out == ""
    assert output.err == ("Reminder rule command failed: database operation failed.\n")
    assert str(database_path) not in output.err
