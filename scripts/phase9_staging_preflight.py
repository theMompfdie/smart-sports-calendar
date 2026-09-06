"""Read-only Docker-host preflight; emit only allowlisted operational evidence."""

import argparse
import json
import subprocess
from pathlib import PurePosixPath

CONTAINER = "smart-calendar-staging-calendar-sync-1"
PROJECT = "smart-calendar-staging"
SCHEMA = "014_manual_review_appointments"
PROBE = r"""
import importlib.util
import json
import os
import sqlite3
from pathlib import Path
from contextlib import closing

path = Path(os.environ.get('DATABASE_PATH', '/data/sports.db'))
result = {
    'manual_code_available':
        importlib.util.find_spec('app.operations.manual_import') is not None
}
uri = path.resolve(strict=True).as_uri() + '?mode=ro'
with closing(sqlite3.connect(uri, uri=True)) as conn:
    conn.execute('PRAGMA query_only=ON')
    result['quick_check_ok'] = (
        conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    )
    result['schema_version'] = conn.execute(
        'SELECT max(version) FROM schema_migrations'
    ).fetchone()[0]
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    for name in (
        'sports_events', 'manual_import_profiles', 'manual_import_receipts',
        'manual_review_plans', 'manual_review_appointments'
    ):
        result[name + '_count'] = (
            conn.execute('SELECT count(*) FROM ' + name).fetchone()[0]
            if name in tables else None
        )
    keys = (
        'austrian_bundesliga', 'fa_cup', 'efl_cup',
        'uefa_conference_league', 'uefa_nations_league'
    )
    result['manual_target_catalog'] = {
        key: bool(conn.execute(
            'SELECT 1 FROM competitions WHERE competition_key=?', (key,)
        ).fetchone()) for key in keys
    }
    if 'import_batches' in tables:
        result['batch_states'] = dict(conn.execute(
            'SELECT state,count(*) FROM import_batches GROUP BY state'
        ))
print(json.dumps(result))
"""


def environment(record: dict) -> dict[str, str]:
    return dict(
        item.split("=", 1)
        for item in record.get("Config", {}).get("Env", [])
        if "=" in item
    )


def mount_for(record: dict, path: str) -> dict | None:
    candidate = PurePosixPath(path)
    if not candidate.is_absolute():
        return None
    matches = [
        mount
        for mount in record.get("Mounts", [])
        if candidate == PurePosixPath(mount["Destination"])
        or PurePosixPath(mount["Destination"]) in candidate.parents
    ]
    return max(matches, key=lambda mount: len(mount["Destination"]), default=None)


def overlap(first: str, second: str) -> bool:
    if not first or not second:
        return False
    left, right = PurePosixPath(first), PurePosixPath(second)
    return left == right or left in right.parents or right in left.parents


def assess(
    target: dict, running: list[dict], probe: dict, require_phase9: bool = False
) -> dict:
    env = environment(target)
    labels = target.get("Config", {}).get("Labels") or {}
    checks = {
        "staging_instance": env.get("INSTANCE_NAME") == "staging",
        "staging_project": labels.get("com.docker.compose.project") == PROJECT,
        "calendar_service": labels.get("com.docker.compose.service") == "calendar-sync",
        "running": target.get("State", {}).get("Running") is True,
        "healthy": target.get("State", {}).get("Health", {}).get("Status") == "healthy",
        "graph_startup_validation": env.get(
            "GRAPH_STARTUP_VALIDATION_ENABLED", "true"
        ).lower()
        == "true",
        "calendar_configured": bool(env.get("OUTLOOK_CALENDAR_ID")),
        "quick_check_ok": probe.get("quick_check_ok") is True,
    }
    paths = [env.get("DATABASE_PATH", "/data/sports.db")]
    inbox = env.get("MANUAL_IMPORT_ROOT", "").strip()
    if inbox:
        paths.append(inbox)
    mounts = [mount_for(target, path) for path in paths]
    checks["persistent_writable_storage"] = all(
        m and m.get("RW") and m.get("Type") in {"volume", "bind"} for m in mounts
    )
    sources: set[str] = set()
    for mount in mounts:
        source = mount.get("Source") if mount else None
        if isinstance(source, str):
            sources.add(source)
    others = [record for record in running if record["Id"] != target["Id"]]
    checks["exclusive_storage"] = not any(
        mount.get("RW")
        and any(overlap(mount.get("Source", ""), source) for source in sources)
        for record in others
        for mount in record.get("Mounts", [])
    )
    calendar = env.get("OUTLOOK_CALENDAR_ID")
    checks["exclusive_calendar_configuration"] = bool(calendar) and not any(
        environment(record).get("OUTLOOK_CALENDAR_ID") == calendar for record in others
    )
    ready = bool(
        probe.get("manual_code_available")
        and probe.get("schema_version") == SCHEMA
        and inbox
    )
    if require_phase9:
        checks["phase9_runtime_enabled"] = ready
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "image": target.get("Config", {}).get("Image"),
        "image_id": target.get("Image"),
        "phase9_runtime_enabled": ready,
        "database": probe,
    }


def docker(*args: str) -> str:
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True
    ).stdout


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default=CONTAINER)
    parser.add_argument("--require-phase9", action="store_true")
    args = parser.parse_args(argv)
    try:
        target = json.loads(docker("inspect", args.container))[0]
        identifiers = docker("ps", "-q").split()
        running = json.loads(docker("inspect", *identifiers)) if identifiers else []
        probe = json.loads(docker("exec", args.container, "python", "-c", PROBE))
        result = assess(target, running, probe, args.require_phase9)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, IndexError):
        print(
            json.dumps(
                {
                    "passed": False,
                    "error": "Docker inspection or read-only database probe failed.",
                }
            )
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
