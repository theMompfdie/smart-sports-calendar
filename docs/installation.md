# Installation and upgrade

This guide targets the v1.0.0 candidate. Stable publication remains pending;
use a reviewed immutable commit for staging until the signed tag is published.
Commands run in Bash on the Docker host with Docker access (`sudo -i` if
needed).

## Prerequisites and target calendar

1. Provide Docker Engine with Compose v2, Git, outbound HTTPS and persistent
   storage. Portainer is optional; no inbound application port is required.
2. Provide a Microsoft 365 work/school mailbox with Exchange Online and an
   Entra application using the configured tenant/client ID and client secret.
   This service uses application authentication, not interactive user login.
3. Have the tenant administrator authorize calendar read/write access. The
   Graph permission is `Calendars.ReadWrite` (application permission with admin
   consent). Restrict effective access to the intended mailbox. For new scoped
   deployments consult [Exchange application RBAC][rbac]: tenant-wide Entra
   grants and scoped RBAC grants are additive, so a broad grant must not defeat
   the intended restriction. Tenant administrators own authorization setup.
4. In Outlook, create one empty calendar in the intended mailbox named
   `SMART Sports Calendar`. Use a separate calendar and application credentials
   for staging. The runtime does not create calendars.
5. Retrieve that calendar's ID through an authorized administrative Graph
   client using `GET /users/{mailbox}/calendars?$select=id,name`. Follow paging
   and select exactly the calendar created above. Store the ID privately in
   `OUTLOOK_CALENDAR_ID`; store the matching name in `OUTLOOK_CALENDAR_NAME`.
   The [calendar API documentation][calendars] describes this read operation.
6. Acquire a football-data.org token if selecting that adapter, or the private
   official subscription URL for Ã–FB-Cup. OpenLigaDB and nflverse need no token.
   Reconfirm the documented source/season qualification for the target.

Do not grant mail-sending or directory-write permissions for this service.
Category colors are manually provisioned in Outlook; calendar synchronization
assigns names only. Third-party imagery is optional and needs separate rights.

## Clean installation: one automated competition

Use a fresh checkout and a private environment file outside it:

```bash
git clone https://github.com/theMompfdie/smart-sports-calendar.git
cd smart-sports-calendar
read -r -p 'Reviewed staging commit or published signed tag: ' RELEASE_REF
git checkout --detach "$RELEASE_REF"
git rev-parse HEAD
install -d -m 700 "$HOME/.config/smart-calendar"
install -m 600 .env.example "$HOME/.config/smart-calendar/staging.env"
export ENV_FILE="$HOME/.config/smart-calendar/staging.env"
export COMPOSE_PROJECT_NAME=smart-calendar-staging
```

Verify the printed commit against the approved candidate. For a published
release also verify `git verify-tag "$RELEASE_REF"` against the operator's
trusted signing key. An image tag alone does not select repository contents.

Edit the private file with the actual Microsoft 365 values from the preceding
section. Set `INSTANCE_NAME=staging`, a unique `IMAGE_TAG`, and keep
`DATABASE_PATH=/data/sports.db`, `MEDIA_ROOT=/data/media` and startup validation
enabled. Never print the resolved environment or commit it.

For a minimal first import choose the qualified 2026/27 2. Bundesliga scope.
Set these lines, leaving every other provider disabled:

```dotenv
OPENLIGADB_ENABLED=true
SOURCE_JOBS_JSON=[{"job_key":"openligadb-second-bundesliga","source_key":"openligadb","sport_key":"football","competition_key":"second_bundesliga","season_key":"2026_27","role":"authoritative","interval_seconds":21600}]
```

The catalog initializes through application services; no SQLite edits are
needed. This is a permanently partial source: disappearance is not deletion.
See [its qualification](openligadb-2-bundesliga-qualification.md).

```bash
docker compose --env-file "$ENV_FILE" config --quiet
docker compose --env-file "$ENV_FILE" up --detach --build
docker compose --env-file "$ENV_FILE" ps
docker compose --env-file "$ENV_FILE" logs --tail 100 calendar-sync
```

The fresh named volume is initialized for container UID 10001. If using a
bind mount instead, provision writable ownership for that user before startup;
do not solve permissions by running the application privileged.

Require successful configuration, authentication, calendar validation, catalog
initialization and the source import in the logs. Then wait for bounded calendar
batches to converge. A `healthy` result alone is not source or Graph acceptance.
Verify the current startup record as well:

```bash
container="$(docker compose --env-file "$ENV_FILE" ps -q calendar-sync)"
started="$(docker inspect --format '{{.State.StartedAt}}' "$container")"
docker exec -i "$container" python - "$started" \
  < scripts/check_startup_ready.py
```

Confirm fixtures appear in the dedicated Outlook calendar with expected teams,
kickoffs and source attribution. Subsequent unchanged cycles must preserve IDs
and avoid duplicate appointments. Provider import and calendar runs are
separate;
a source success alone does not establish Outlook convergence.

Add further jobs only after reviewing their explicit competition/season/stage
boundaries. Use [source orchestration](source-orchestration.md) and the
[configuration reference](deployment.md). Never introduce a second overlapping
writer. For manual schedules enable `MANUAL_IMPORT_ROOT=/data/manual-import`,
then follow the [profile, submission and approval
workflow](manual-import-workflow.md).
Private source packages, target approvals and profile setup are not shipped.

## Upgrade from the final beta

Keep the existing project name, volume, calendar ID and instance name. Retain
all configured source grants and manual profiles, including retired scopes.
Never copy staging event mappings into a different production calendar.

Record the old commit, image ID and private configuration. Stop the owner and
back up the complete data volume, including SQLite/WAL files, media, inbox,
profiles, receipts and audit artifacts. The following leaves the service stopped
if backup verification fails, rather than starting an unverified upgrade:

```bash
container="$(docker compose --env-file "$ENV_FILE" ps -q calendar-sync)"
test -n "$container"
old_image="$(docker inspect --format '{{.Image}}' "$container")"
umask 077
backup="$(mktemp -d "$HOME/smart-calendar-pre-v1-XXXXXXXX")"
mkdir "$backup/data"
printf '%s\n' "$old_image" > "$backup/image-id.txt"
git rev-parse HEAD > "$backup/source-commit.txt"
docker stop --time 120 "$container"
docker cp -a "$container:/data/." "$backup/data/"
docker run --rm --network none --user 0:0 \
  --mount "type=bind,src=$backup/data,dst=/backup,readonly" \
  --entrypoint python "$old_image" -c '
import sqlite3
connection = sqlite3.connect("file:/backup/sports.db?mode=ro", uri=True)
assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
connection.close()
print("Backup database verified")
'
(cd "$backup/data" && find . -type f -print0 | sort -z | xargs -0 sha256sum) \
  > "$backup/sha256.txt"
printf 'Private backup: %s\n' "$backup"
```

Keep the backup and matching secret configuration private and off the source
checkout. After verification, check out the reviewed new commit/tag, update
only the image tag and required configuration additions, and run the clean
installation's Compose validation/build/start and startup checks. Do not run
`down --volumes`. Migrations through `015_scope_retirement` are additive and
idempotent; no manual schema edits are needed.

Before acceptance verify preserved source/calendar identities, media and
review appointments, zero failed/pending synchronization work after convergence,
and an unchanged repeat cycle. Use the [retirement
cookbook](season-retirement-cookbook.md)
for a stopped-owner lifecycle operation, not configuration removal.

## Recovery

Normal retirement undo is explicit reactivation. Version rollback is different:
older images ignore the retirement gate and must not run against the upgraded
database. Stop the owner; preserve the failed state separately. Restore a
**matching complete pre-upgrade snapshot**, its private configuration and the
old immutable image into an isolated recovery volume first. Verify the stored
checksums and SQLite integrity before allowing writes.

Never run recovered and original owners against the same calendar concurrently.
A filesystem restore cannot undo Outlook changes made since the snapshot.
Review Graph identities/content and reconcile discrepancies before resuming the
original target. Do not blindly replay an old snapshot into a fresh calendar.
There is no supported automatic schema downgrade or universal destructive
restore command. See [deployment recovery details](deployment.md) and the
[manual-import rollback boundary](v0.9.0-beta.1-release-checklist.md).

## Portainer and troubleshooting

In Portainer use a Git-backed stack with the reviewed commit/tag as repository
reference, `docker-compose.yml` as the Compose file and the same private
variables. Give each stack a distinct project/instance, persistent volume and
target calendar. Recheck the actual image and startup after redeployment.

- Docker socket permission denied: Check: Use the authorized host/root shell.
- Healthy but no fixtures: Check: Provider enabled, matching job, source
  import, Graph run.
- Authentication/calendar validation fails: Check: Secret expiry, mailbox
  access, exact ID/name.
- Manual import awaiting approval: Check: Inspect and approve its exact current
  preview.
- Manual import rejected after retirement: Check: Explicit reactivation before
  correction.
- Unknown provider status: Check: Preserve state; inspect sanitized IDs; no
  heuristic repair.
- Migration or SQLite permission failure: Check: Stop; verify volume ownership
  and backup.
- Missing imagery: Check: Approved registry and rights; text/icon fallback is
  supported.

Keep diagnostic output private until reviewed for identifiers and secrets.
The [release checklist](v1.0.0-release-checklist.md) separates verified evidence
from the remaining final-candidate and operator publication steps.

[rbac]: https://learn.microsoft.com/en-us/exchange/permissions-exo/application-rbac
[calendars]: https://learn.microsoft.com/en-us/graph/api/user-list-calendars?view=graph-rest-1.0
