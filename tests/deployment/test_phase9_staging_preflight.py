"""Read-only and secret-safe host preparation checks."""

import json
import os
import subprocess
import sys
from copy import deepcopy

import pytest
from app.database.database import Database
from scripts.phase9_staging_preflight import PROBE, SCHEMA, assess


@pytest.fixture
def container():
    return {
        "Id": "staging-id",
        "Image": "sha256:synthetic-image",
        "Config": {
            "Image": "smart-calendar-staging-calendar-sync:candidate-test",
            "Labels": {
                "com.docker.compose.project": "smart-calendar-staging",
                "com.docker.compose.service": "calendar-sync",
            },
            "Env": [
                "INSTANCE_NAME=staging",
                "DATABASE_PATH=/data/sports.db",
                "MANUAL_IMPORT_ROOT=/data/manual-import",
                "OUTLOOK_CALENDAR_ID=private-calendar-identifier",
                "M365_CLIENT_SECRET=do-not-print-this-secret",
            ],
        },
        "State": {"Running": True, "Health": {"Status": "healthy"}},
        "Mounts": [
            {
                "Destination": "/data",
                "Source": "/private/staging-volume",
                "Type": "volume",
                "RW": True,
            }
        ],
    }


def probe():
    return {
        "quick_check_ok": True,
        "schema_version": SCHEMA,
        "manual_code_available": True,
    }


def test_ready_preflight_never_exposes_env_or_mount_sources(container):
    result = assess(container, [container], probe(), True)
    assert result["passed"]
    rendered = json.dumps(result)
    for value in (
        "private-calendar-identifier",
        "do-not-print-this-secret",
        "/private/staging-volume",
    ):
        assert value not in rendered


def test_old_staging_can_be_inspected_but_cannot_pass_phase9_gate(container):
    old = {
        "quick_check_ok": True,
        "schema_version": "012_create_calendar_event_asset_attachments",
        "manual_code_available": False,
    }
    assert assess(container, [container], old)["passed"]
    assert not assess(container, [container], old, True)["passed"]


@pytest.mark.parametrize("shared", ["calendar", "volume", "nested-bind"])
def test_shared_state_fails_isolation(container, shared):
    other = deepcopy(container)
    other["Id"] = "other-instance"
    if shared == "calendar":
        other["Mounts"] = []
    else:
        other["Config"]["Env"] = []
        if shared == "nested-bind":
            other["Mounts"][0]["Source"] += "/sports.db"
            other["Mounts"][0]["Type"] = "bind"
    assert not assess(container, [container, other], probe(), True)["passed"]


def test_production_name_and_unmounted_inbox_fail_closed(container):
    container["Config"]["Env"][0] = "INSTANCE_NAME=production"
    assert not assess(container, [container], probe(), True)["passed"]
    container["Config"]["Env"][0] = "INSTANCE_NAME=staging"
    container["Config"]["Env"][2] = "MANUAL_IMPORT_ROOT=/ephemeral/inbox"
    assert not assess(container, [container], probe(), True)["passed"]


def test_probe_reads_existing_database_without_changing_bytes(tmp_path):
    path = tmp_path / "sports.db"
    Database(path).initialize()
    before = path.read_bytes()
    env = {
        **os.environ,
        "DATABASE_PATH": str(path),
        "M365_CLIENT_SECRET": "private-test-secret",
    }
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == SCHEMA
    assert payload["quick_check_ok"]
    assert payload["manual_import_profiles_count"] == 0
    assert "private-test-secret" not in result.stdout
    assert path.read_bytes() == before


def test_probe_never_initializes_missing_database(tmp_path):
    path = tmp_path / "missing.db"
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_PATH": str(path)},
    )
    assert result.returncode != 0
    assert not path.exists()
