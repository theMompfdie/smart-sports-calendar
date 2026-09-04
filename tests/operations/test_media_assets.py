import json
from pathlib import Path

from app.database.database import Database
from app.operations.media_assets import main
from PIL import Image


def test_cli_import_approve_replace_disable_and_safe_list(
    tmp_path: Path,
    capsys,
) -> None:
    database_path = tmp_path / "sports.db"
    media_root = tmp_path / "media"
    source_file = tmp_path / "trophy.png"
    Database(database_path).initialize()
    Image.new("RGBA", (60, 60), (240, 180, 20, 255)).save(source_file)
    base = ["--database", str(database_path), "--media-root", str(media_root)]
    import_arguments = [
        "--asset-key",
        "project.trophy",
        "--owner-type",
        "project",
        "--owner-key",
        "smart_sports_calendar",
        "--variant",
        "trophy",
        "--file",
        str(source_file),
        "--source-reference",
        "https://private.example/source?token=secret",
        "--license-name",
        "MIT",
        "--permission-reference",
        "private-record-secret",
    ]

    assert main([*base, "import", *import_arguments]) == 0
    imported = json.loads(capsys.readouterr().out)

    assert imported["version"] == 1
    assert imported["approved"] is False
    assert imported["active"] is False
    assert imported["has_permission_reference"] is True
    serialized = json.dumps(imported)
    assert "token=secret" not in serialized
    assert "private-record-secret" not in serialized
    assert str(media_root) not in serialized

    assert (
        main(
            [
                *base,
                "approve",
                "--asset-key",
                "project.trophy",
                "--version",
                "1",
                "--reviewer",
                "operator",
            ]
        )
        == 0
    )
    approved = json.loads(capsys.readouterr().out)
    assert approved["approved"] is True
    assert approved["active"] is True

    Image.new("RGBA", (60, 60), (20, 80, 180, 255)).save(source_file)
    assert main([*base, "replace", *import_arguments]) == 0
    replacement = json.loads(capsys.readouterr().out)
    assert replacement["version"] == 2
    assert replacement["active"] is False

    assert main([*base, "list", "--include-inactive"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [asset["version"] for asset in listed] == [1, 2]
    assert [asset["active"] for asset in listed] == [True, False]

    assert main([*base, "disable", "--asset-key", "project.trophy"]) == 0
    disabled = json.loads(capsys.readouterr().out)
    assert disabled["approved"] is True
    assert disabled["active"] is False
