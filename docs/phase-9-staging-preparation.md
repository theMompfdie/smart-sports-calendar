# Phase 9 staging preparation for the Docker host

## Status and reuse of accepted evidence

The operator accepted all seven bounded targets under #254 on 2026-09-06,
against `39caf0441bade383b68abd470d79d3d835d9313f` and image
`smart-calendar-staging-calendar-sync:phase9-39caf04`.
The existing Portainer Git stack and its isolated persistent storage were used.

This guide remains a procedure for a new or materially changed candidate.
It is not a request to repeat accepted imports, lifecycle, backup or restart
checks. See the [release checklist](v0.9.0-beta.1-release-checklist.md)
and [accepted evidence](https://github.com/theMompfdie/smart-sports-calendar/issues/254).
Final documentation and publication are #255; production blocker #233 remains.

## 1. Read-only inventory in PuTTY

These commands inspect the named staging container without changing its state:

```bash
STAGING_CONTAINER=smart-calendar-staging-calendar-sync-1

docker ps --filter "name=^/${STAGING_CONTAINER}$" \
  --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'

docker inspect --format \
  '{{ index .Config.Labels "com.docker.compose.project" }}' \
  "$STAGING_CONTAINER"

docker inspect --format \
  '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' \
  "$STAGING_CONTAINER"

docker inspect --format \
  '{{ index .Config.Labels "com.docker.compose.project.config_files" }}' \
  "$STAGING_CONTAINER"
```

Expected project: `smart-calendar-staging`. Working/config-file paths are private
host details; keep them locally. Empty or Portainer-internal paths are not a
reason to invent a Compose directory. Never print the full container environment
or an unfiltered Docker inspect result.

Copy [the preflight script](../scripts/phase9_staging_preflight.py) to
`/root/ssc-phase9/phase9_staging_preflight.py`. It needs host Python 3.10 or later
and the Docker CLI. It does not require project dependencies or live Graph calls.

```bash
umask 077
mkdir -p /root/ssc-phase9
python3 --version
python3 /root/ssc-phase9/phase9_staging_preflight.py \
  --container "$STAGING_CONTAINER" \
  > /root/ssc-phase9/preflight-before.json
cat /root/ssc-phase9/preflight-before.json
```

The allowlisted report contains image identity, isolation checks, schema,
aggregate counts and target-catalog availability. It does not print credentials,
calendar IDs, event titles, profile contents or physical volume paths.
It reads SQLite with `mode=ro` and `query_only`; it never initializes a database.

Before upgrade, the basic health/isolation gate can pass while
`phase9_runtime_enabled` is false. That is not a Phase 9 qualification pass.
The checks compare running containers on this host; they cannot rule out an
external writer on another host or an unconfigured application using the tenant.

## 2. Freeze the verified candidate

Record the full candidate SHA and its green integration CI. Do not use an
invented SHA, an unmerged working tree, a floating image tag or an automatic
latest build as qualification evidence. Keep the old image ID from preflight.

Use the existing **Portainer Git stack** as the deployment owner:

1. Open `smart-calendar-staging` in Portainer and record its current repository
   reference, Compose path, image tag and automatic-update settings privately.
2. Pause Git polling/webhook updates for the qualification window. Keep the
   existing Git repository connection and stack name.
3. Prepare the full verified #253 merge SHA as the repository reference and
   `phase9-<short-merge-sha>` as `IMAGE_TAG`. These values are supplied after the
   operator merge and green integration CI; do not deploy placeholder values.
4. Preserve the existing Compose path, credentials, calendar and volume settings.
   The repository Compose file uses `build` and `pull_policy: build`; the build
   must use that exact Git revision. An image tag alone does not prove its source.
5. Complete the backup below before saving/redeploying. Then use the existing
   stack's Git update/redeploy action and inspect its build/deployment result.
   Record the resulting image ID and require a healthy container.

Portainer documents branch, tag and pinned SHA references in its
[Git reference model](https://architecture.portainer.io/ch6). Field and action
names vary by installed version. If that installation cannot accept the full
SHA, resolve its revision-pinning support before qualification. Do not detach
from Git, create a second stack or treat a floating `develop` deployment as a
frozen candidate. No Git tag or release is created by this procedure.

## 3. Back up only staging before replacement

Keep backup artifacts private and outside the application volume. The following
block checks that database, media and any enabled inbox are beneath `/data`.
If it fails, adapt the backup to the actual mounts before proceeding.

```bash
set -eu
STAGING_CONTAINER=smart-calendar-staging-calendar-sync-1
test "$(docker inspect --format \
  '{{ index .Config.Labels "com.docker.compose.project" }}' \
  "$STAGING_CONTAINER")" = smart-calendar-staging

umask 077
BACKUP="/root/ssc-phase9/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP/data"

docker inspect --format '{{.Image}}' "$STAGING_CONTAINER" \
  > "$BACKUP/old-image-id.txt"

docker exec -i "$STAGING_CONTAINER" python - > "$BACKUP/layout.json" <<'PY'
import json
import os
from pathlib import Path
root = Path('/data').resolve()
database = Path(os.environ.get('DATABASE_PATH', '/data/sports.db')).resolve()
media = Path(os.environ.get('MEDIA_ROOT', '/data/media')).resolve()
paths = [database, media]
inbox = os.environ.get('MANUAL_IMPORT_ROOT', '').strip()
if inbox:
    paths.append(Path(inbox).resolve())
if not all(path.is_relative_to(root) for path in paths):
    raise SystemExit('Backup scope needs explicit mount review.')
print(json.dumps({'database': str(database.relative_to(root))}))
PY

# Stop only staging; restart the existing container even if copying fails.
trap 'docker start "$STAGING_CONTAINER" >/dev/null' EXIT
docker stop --time 60 "$STAGING_CONTAINER" >/dev/null
docker cp -a "$STAGING_CONTAINER:/data/." "$BACKUP/data/"

python3 - "$BACKUP" <<'PY'
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
root = Path(sys.argv[1])
layout = json.loads((root / 'layout.json').read_text())
database = root / 'data' / layout['database']
if not database.is_file() or database.stat().st_size == 0:
    raise SystemExit('Backup database is missing or empty.')
with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as conn:
    if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise SystemExit('Backup database integrity check failed.')
manifest = {}
for path in sorted((root / 'data').rglob('*')):
    if path.is_file():
        with path.open('rb') as handle:
            digest = hashlib.sha256()
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
            manifest[str(path.relative_to(root))] = digest.hexdigest()
(root / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Staging backup copied and integrity-checked.')
PY

docker start "$STAGING_CONTAINER" >/dev/null
trap - EXIT
```

This captures full `/data`, including media and any inbox, not just the main
SQLite file. Store the private integrity manifest and old image ID with it.
State created after this snapshot is not part of that backup.

Do not run `down --volumes`, delete existing volumes, or restore over a running
instance. A live isolated restore must use a new test volume with networking
blocked; it must never target the original writable database/calendar. The
regression tests cover logical restore independently; host restore evidence
still belongs to #254 and is not claimed by a successful backup alone.

## 4. Deploy and check the candidate

Before redeploying, set these environment variables in the existing Portainer
staging stack so the replacement container receives them:

```dotenv
MANUAL_IMPORT_ROOT=/data/manual-import
MANUAL_IMPORT_INTERVAL=60
MANUAL_IMPORT_LIMIT=10
GRAPH_STARTUP_VALIDATION_ENABLED=true
```

Preserve existing credentials, calendar, providers, volumes and media settings.
Keep the normal container user (UID 10001); root access on the host does not
require running the application as root. A restart loads separately reviewed
startup profiles. Submissions and approvals then require no application stop.

Run the stronger post-upgrade gate:

```bash
python3 /root/ssc-phase9/phase9_staging_preflight.py \
  --container smart-calendar-staging-calendar-sync-1 --require-phase9 \
  > /root/ssc-phase9/preflight-after.json
cat /root/ssc-phase9/preflight-after.json
```

Require a healthy container, the recorded image ID, schema
`014_manual_review_appointments`, enabled manual runtime, isolated persistent
storage and successful Graph startup validation. The report checks that startup
validation is configured; verify successful execution through the private
startup logs too. No import starts merely because this preflight passes.

## 5. Qualify data before importing

The seed now includes the reviewed 2026/27 target catalogs. Catalog presence
does not qualify source rights, trusted profiles or stage authority.
FA Cup participant membership remains pending until the First Round Proper
draw; use an active review-only manifest until its fixtures are published.

The accepted #254 matrix is:

| Target | Accepted boundary | Fixtures | Reviews |
| --- | --- | ---: | ---: |
| Austrian Bundesliga | Regular-season rounds 1-16 | 96 | 2 |
| FA Cup | First Round Proper publication check | 0 | 1 |
| EFL Cup | Preliminary through third round | 76 | 1 |
| UEFA Conference League | League phase | 108 | 1 |
| Nations League B | League B group phase | 48 | 1 |
| Nations League C | League C group phase | 48 | 1 |
| Nations League D | League D group phase | 12 | 1 |

For each target retain a private permitted source document, observation time,
rights/attribution record, stable fixture IDs, trusted profile, normalized
manifest and schedule-update review plan. Real fixture data and private source
files must come from the operator's reviewed documents. Synthetic test examples
must not be submitted to the existing staging calendar as if they were real.

Preserve existing Nations League A and its mappings. A broad League A grant
must be explicitly reviewed before narrowing; B/C/D imports cannot silently
acquire its stages. Europa League follows #269 after Phase 9, with provider
requalification or a reviewed manual fallback.

## 6. Live validation sequence

Use [the operator workflow](manual-import-workflow.md) for exact submit, status,
preview and detached-approval commands. One small qualified scope goes first:

1. Record baseline counts, active authority, fixture mappings and reminders.
2. Submit the reviewed manifest and wait for AWAITING_APPROVAL; inspect all
   fixture and review-plan decisions. Confirm no calendar change before approval.
3. Approve the exact preview and wait for APPLIED and its receipt.
4. Verify fixture and dedicated update-review events in the staging calendar,
   including Vienna time, reminder lead, no attendees and namespace isolation.
5. Re-submit unchanged input and restart staging; require stable identities and
   no duplicates or unnecessary Outlook updates.
6. Qualify an actual correction/partial update and an explicitly completed task;
   confirm other scopes and normal sports reminders remain unchanged.
7. Reference accepted automated interruption/Graph recovery in #253 and the
   live stopped-backup, isolated-readback and restart evidence in #254.
   No additional forced live interruption is required for the accepted tree.
8. Repeat source/scope qualification and evidence for the other six targets.

The immutable receipt proves canonical commit, not current Outlook convergence.
Retain sanitized aggregate results publicly; keep IDs, documents, profiles,
approvals, backups and tenant details private. #255 owns release preparation.
Production remains a separate promotion, with blocker #233 still open.

## Regression evidence prepared under #253

The network-free tests cover seven-profile lifecycle/correction/cancellation,
combined coexistence, partial-update isolation, both Outlook flows, unchanged
replay, isolated backup/restore, stale restored approval, and downstream failure.
Tests through the real Graph adapter cover HTTP 429/503 and an updated reminder
returning HTTP 404. The latter required a focused Graph error-classification fix.

Host preflight tests verify secret redaction, old-image readiness rejection,
shared/nested storage and calendar detection, wrong-instance rejection and
read-only SQLite access. Full local/PR results are recorded in issue #253;
these automated checks do not replace the live evidence in #254.
