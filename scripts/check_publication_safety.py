from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

PRIVATE_DIRECTORY_NAMES = frozenset(
    {
        "backup",
        "backups",
        "export",
        "exports",
        "logs",
        "private",
        "provider-data",
        "raw-provider-data",
    }
)
PRIVATE_SUFFIXES = frozenset(
    {
        ".backup",
        ".db",
        ".db-shm",
        ".db-wal",
        ".ical",
        ".ics",
        ".key",
        ".p12",
        ".pem",
        ".pfx",
        ".sqlite",
        ".sqlite3",
    }
)
PRIVATE_BASENAMES = frozenset(
    {
        "calendar-export.json",
        "outlook-export.json",
        "provider-payload.json",
        "provider-response.json",
    }
)
REQUIRED_GITIGNORE_RULES = frozenset(
    {
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
        "private/",
        "provider-data/",
        "raw-provider-data/",
    }
)
REQUIRED_DOCKERIGNORE_RULES = frozenset(
    {
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
        "private",
        "provider-data",
        "raw-provider-data",
    }
)
SECRET_ASSIGNMENT = re.compile(
    r"(?m)^[ \t]*(?:"
    r"API_FOOTBALL_API_KEY|FOOTBALL_DATA_API_KEY|M365_CLIENT_SECRET|"
    r"OEFB_ICAL_FEED_URL"
    r")[ \t]*[:=][ \t]*[\"']?([^\s#\"']*)"
)
TOKEN_PATTERNS = (
    re.compile(r"gh" + r"[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA" + r"[0-9A-Z]{16}"),
    re.compile(r"xox" + r"[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
SAFE_VALUE_PREFIXES = (
    "$",
    "<",
    "ci-",
    "example",
    "placeholder",
    "replace-",
    "test-",
    "your-",
)
MAX_SCANNED_FILE_SIZE = 2_000_000


@dataclass(frozen=True, slots=True)
class Finding:
    path: str
    reason: str


def publication_candidate_paths(repository_root: Path) -> tuple[PurePosixPath, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repository_root,
        check=True,
        capture_output=True,
    )
    return tuple(
        PurePosixPath(item.decode("utf-8"))
        for item in result.stdout.split(b"\0")
        if item
    )


def audit_repository(
    repository_root: Path,
    paths: Iterable[PurePosixPath] | None = None,
) -> tuple[Finding, ...]:
    inspected_paths = (
        tuple(paths)
        if paths is not None
        else publication_candidate_paths(repository_root)
    )
    findings: list[Finding] = []

    for relative_path in inspected_paths:
        normalized = PurePosixPath(str(relative_path).replace("\\", "/"))
        findings.extend(_audit_path(normalized))
        file_path = repository_root.joinpath(*normalized.parts)
        if file_path.is_file():
            findings.extend(_audit_content(file_path, normalized))

    findings.extend(
        _audit_ignore_file(
            repository_root / ".gitignore",
            REQUIRED_GITIGNORE_RULES,
            ".gitignore",
        )
    )
    findings.extend(
        _audit_ignore_file(
            repository_root / ".dockerignore",
            REQUIRED_DOCKERIGNORE_RULES,
            ".dockerignore",
        )
    )
    return tuple(
        sorted(set(findings), key=lambda finding: (finding.path, finding.reason))
    )


def _audit_path(path: PurePosixPath) -> list[Finding]:
    lowered_parts = tuple(part.casefold() for part in path.parts)
    basename = lowered_parts[-1]
    findings: list[Finding] = []

    if basename == ".env" or (
        basename.startswith(".env.") and basename != ".env.example"
    ):
        findings.append(Finding(str(path), "private environment file is tracked"))
    if PRIVATE_DIRECTORY_NAMES.intersection(lowered_parts):
        findings.append(Finding(str(path), "private runtime-data directory is tracked"))
    if "manifests" in lowered_parts and "private" in lowered_parts:
        findings.append(Finding(str(path), "private fixture manifest is tracked"))
    if basename in PRIVATE_BASENAMES:
        findings.append(Finding(str(path), "provider or calendar export is tracked"))
    if _matches_private_suffix(basename):
        findings.append(Finding(str(path), "private runtime-data file type is tracked"))
    return findings


def _matches_private_suffix(basename: str) -> bool:
    return any(basename.endswith(suffix) for suffix in PRIVATE_SUFFIXES)


def _audit_content(file_path: Path, relative_path: PurePosixPath) -> list[Finding]:
    if file_path.stat().st_size > MAX_SCANNED_FILE_SIZE:
        return []
    content = file_path.read_bytes()
    if b"\0" in content:
        return []
    text = content.decode("utf-8", errors="replace")
    findings: list[Finding] = []

    for match in SECRET_ASSIGNMENT.finditer(text):
        value = match.group(1).strip()
        if value and not _is_safe_example_value(value):
            findings.append(
                Finding(str(relative_path), "possible real provider or Graph secret")
            )
            break
    if any(pattern.search(text) for pattern in TOKEN_PATTERNS):
        findings.append(Finding(str(relative_path), "possible credential material"))
    return findings


def _is_safe_example_value(value: str) -> bool:
    lowered = value.casefold()
    return lowered in {"''", '""'} or lowered.startswith(SAFE_VALUE_PREFIXES)


def _audit_ignore_file(
    path: Path,
    required_rules: frozenset[str],
    display_name: str,
) -> list[Finding]:
    if not path.is_file():
        return [Finding(display_name, "required exclusion file is missing")]
    rules = {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    return [
        Finding(display_name, f"required exclusion rule is missing: {rule}")
        for rule in sorted(required_rules - rules)
    ]


def render_findings(findings: Sequence[Finding]) -> str:
    lines = ["Publication safety check failed:"]
    lines.extend(f"- {finding.path}: {finding.reason}" for finding in findings)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check tracked files for private runtime data and credentials."
    )
    parser.add_argument(
        "--repository",
        type=Path,
        default=REPOSITORY_ROOT,
        help="Repository root to inspect (defaults to the current project).",
    )
    arguments = parser.parse_args(argv)
    repository_root = arguments.repository.resolve()
    findings = audit_repository(repository_root)
    if findings:
        parser.exit(status=1, message=f"{render_findings(findings)}\n")
    print(
        "Publication safety check passed for "
        f"{len(publication_candidate_paths(repository_root))} candidate files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
