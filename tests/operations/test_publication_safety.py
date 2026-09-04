from pathlib import Path, PurePosixPath

from scripts.check_publication_safety import audit_repository, render_findings


def write_ignore_files(root: Path) -> None:
    (root / ".gitignore").write_text(
        "\n".join(
            (
                ".env.*",
                "*.db",
                "*.db-shm",
                "*.db-wal",
                "*.ical",
                "*.ics",
                "backups/",
                "data/",
                "exports/",
                "logs/",
                "manifests/private/",
                "/media/",
                "private/",
                "provider-data/",
                "raw-provider-data/",
            )
        ),
        encoding="utf-8",
    )
    (root / ".dockerignore").write_text(
        "\n".join(
            (
                ".env.*",
                "*.db",
                "*.db-*",
                "*.ical",
                "*.ics",
                "backups",
                "data",
                "exports",
                "logs",
                "manifests",
                "media/**",
                "private",
                "provider-data",
                "raw-provider-data",
            )
        ),
        encoding="utf-8",
    )


def test_audit_accepts_synthetic_fixture_and_placeholder_configuration(
    tmp_path: Path,
) -> None:
    write_ignore_files(tmp_path)
    fixture = tmp_path / "tests" / "fixtures" / "synthetic.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(
        '{"home": "Example FC", "away": "Sample United"}', encoding="utf-8"
    )
    example = tmp_path / ".env.example"
    example.write_text(
        "FOOTBALL_DATA_API_KEY=replace-with-deployment-secret\n",
        encoding="utf-8",
    )

    findings = audit_repository(
        tmp_path,
        (
            PurePosixPath("tests/fixtures/synthetic.json"),
            PurePosixPath(".env.example"),
        ),
    )

    assert findings == ()


def test_audit_rejects_private_runtime_files_and_environment(tmp_path: Path) -> None:
    write_ignore_files(tmp_path)
    database = tmp_path / "backups" / "sports.db"
    database.parent.mkdir()
    database.write_bytes(b"SQLite format 3")
    environment = tmp_path / ".env.staging"
    secret_key = "M365_" + "CLIENT_SECRET"
    environment.write_text(f"{secret_key}=not-for-source-control\n", encoding="utf-8")

    findings = audit_repository(
        tmp_path,
        (
            PurePosixPath("backups/sports.db"),
            PurePosixPath(".env.staging"),
        ),
    )

    rendered = render_findings(findings)
    assert "private runtime-data directory is tracked" in rendered
    assert "private runtime-data file type is tracked" in rendered
    assert "private environment file is tracked" in rendered
    assert "not-for-source-control" not in rendered


def test_audit_rejects_root_media_without_rejecting_application_package(
    tmp_path: Path,
) -> None:
    write_ignore_files(tmp_path)

    findings = audit_repository(
        tmp_path,
        (
            PurePosixPath("media/assets/ab/example.png"),
            PurePosixPath("app/media/asset_service.py"),
        ),
    )

    assert any(
        finding.path == "media/assets/ab/example.png"
        and finding.reason == "private media directory is tracked"
        for finding in findings
    )
    assert not any(finding.path == "app/media/asset_service.py" for finding in findings)


def test_audit_rejects_secret_assignments_without_echoing_values(
    tmp_path: Path,
) -> None:
    write_ignore_files(tmp_path)
    configuration = tmp_path / "deployment.txt"
    secret = "realistic-private-value"
    secret_key = "FOOTBALL_DATA_" + "API_KEY"
    configuration.write_text(
        f"{secret_key}={secret}\n",
        encoding="utf-8",
    )

    findings = audit_repository(
        tmp_path,
        (PurePosixPath("deployment.txt"),),
    )

    rendered = render_findings(findings)
    assert "possible real provider or Graph secret" in rendered
    assert secret not in rendered


def test_audit_rejects_common_credential_material_without_echoing_it(
    tmp_path: Path,
) -> None:
    write_ignore_files(tmp_path)
    credential = "gh" + "p_" + ("a" * 40)
    notes = tmp_path / "notes.txt"
    notes.write_text(f"temporary credential: {credential}\n", encoding="utf-8")

    findings = audit_repository(tmp_path, (PurePosixPath("notes.txt"),))

    rendered = render_findings(findings)
    assert "possible credential material" in rendered
    assert credential not in rendered


def test_audit_requires_repository_and_container_exclusions(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.db\n", encoding="utf-8")
    (tmp_path / ".dockerignore").write_text("*.db\n", encoding="utf-8")

    findings = audit_repository(tmp_path, ())

    assert any(
        finding.path == ".gitignore" and "*.ics" in finding.reason
        for finding in findings
    )
    assert any(
        finding.path == ".dockerignore" and "provider-data" in finding.reason
        for finding in findings
    )
