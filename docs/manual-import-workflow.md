# Docker-host manual import workflow

Issue #252 adds an optional inbox worker and dedicated Outlook update-review
appointments. It reuses the [atomic backend](manual-import-apply.md) and
[reviewed manifest contract](manual-import-preparation.md).
Automated qualification #253 and bounded seven-target staging #254 are
accepted. Final publication is tracked in
[the Phase 9 checklist](v0.9.0-beta.1-release-checklist.md); production remains
separately approved and blocked by #233.

## Enable one owning instance

The existing application process is the only database/calendar writer. Startup
holds an OS lifetime lock beside the configured database; a second application
using that database fails before initialization. Crashes release the lock.
Never remove a live lock file, share a writable database across hosts, or run a
second importer container. This is a local filesystem lock, not a distributed
lease. Normal scheduler jobs run sequentially; a worker cycle is also guarded
against reentrant calls.

Configure these optional variables in the selected instance's private env file:

```dotenv
MANUAL_IMPORT_ROOT=/data/manual-import
MANUAL_IMPORT_INTERVAL=60
MANUAL_IMPORT_LIMIT=10
```

An empty `MANUAL_IMPORT_ROOT` disables both inbox processing and update-review
appointment synchronization. The root must be absolute. The interval must be
positive; the limit is 1-100 requests and 1-100 Graph task operations per cycle.
Pending work rotates between cycles so a failing item cannot monopolize a batch.
Provider and normal fixture synchronization keep their existing schedules.

The supplied Compose file forwards these variables. Its existing `/data` volume
persists the database, lock and inbox. Keep staging and production project
names,
volumes, instance names, databases and target calendars separate. Use a local
filesystem supporting locks, hard links, atomic rename and fsync. The image runs
as UID 10001; bind-mounted directories must be writable by that user. No new
ports, credentials, privileged containers or Graph permissions are introduced.

Before upgrading, follow the stopped-instance database backup procedure.
Migration 014 adds separate review-appointment mappings and preserves canonical
fixtures, import packages, receipts and accepted plans. Back up the complete
inbox together with the database; never copy only a live WAL main database file.

## Install trusted profiles

Profiles are independent operator configuration, never part of an incoming
package. Prepare a profile using the
[documented shape](manual-import-preview.md#trusted-profile). Its `instance_ref`
must equal `INSTANCE_NAME`; scope and participants must already exist in the
qualified catalog. The synthetic examples are not live competition catalogs.

On first enablement, let the worker initialize its root. Install separately
reviewed `*.json` profiles into `/data/manual-import/profiles/` and restart the
selected application once to load them. For example, on a Linux Docker host:

```bash
# Run from the checked-out project with the selected Compose env file.
docker compose --env-file /private/staging.env exec -T calendar-sync \
  sh -c 'umask 077; cat > /data/manual-import/profiles/profile.upload &&
         mv /data/manual-import/profiles/profile.upload \
            /data/manual-import/profiles/profile.json' \
  < /private/reviewed-profile.json
docker compose --env-file /private/staging.env restart calendar-sync
```

These commands create private files as the configured container user. The
profile directory is for the
operator only. Existing permanent namespaces cannot move to another competition
or season. Removing a profile file does not disable its persisted grant.
Authority changes require a separately reviewed configuration and qualification;
a package cannot widen its own authority. Broad League A grants are never
narrowed implicitly to admit B/C/D. No automatic provider handover is supplied.

The root contains immutable instance/database identity markers. Reusing it with
a different database or instance fails startup. A relocated restored database
requires fresh pending previews under the backend's existing identity rules.
Do not edit these markers to bypass an instance mismatch.

## Submit and inspect

Copy a reviewed manifest into private storage inside the selected container.
Using `/data` retains it across container replacement; keep source files out of
the public repository. Documents/PDF extraction stays outside the runtime.

```bash
docker compose --env-file /private/staging.env exec -T calendar-sync \
  sh -c 'umask 077; cat > /data/fixtures.json' < /private/fixtures.json

docker compose --env-file /private/staging.env exec -T calendar-sync \
  python -m app.operations.manual_import \
  --inbox /data/manual-import --instance staging --namespace manual-scope \
  submit --manifest /data/fixtures.json
```

Replace `staging`, `manual-scope` and the submission ID below with the
reviewed profile/manifest values. These are examples, not prequalified scopes.
The CLI only publishes an immutable file. `QUEUED` does not mean validated,
approved, imported or synchronized. Existing identical archived requests are
already processed; inspect their status instead of expecting another apply.

After the worker runs, read its private result:

```bash
docker compose --env-file /private/staging.env exec -T calendar-sync \
  python -m app.operations.manual_import \
  --inbox /data/manual-import --instance staging --namespace manual-scope \
  status --submission my-submission-id
```

The worker stores RECEIVED, prepares the preview and publishes
AWAITING_APPROVAL or REJECTED. The output contains the preview and its exact
`preview_sha256`. Inspect every fixture decision, warning, scope, provenance and
review-plan change. Neither receipt nor preview generation contacts Graph.
An unknown/unqualified catalog is rejected, not provisioned from input.

## Approve and apply

Prepare a detached approval using the exact fields in the
[approval contract](manual-import-preview.md#review-and-stale-state-checks).
Use the actual
submission/type/version, manifest fingerprint, published preview fingerprint,
instance, operator identity and current aware UTC approval time. There is no
command that silently approves the latest unseen preview.

```bash
docker compose --env-file /private/staging.env exec -T calendar-sync \
  sh -c 'umask 077; cat > /data/approval.json' < /private/approval.json

docker compose --env-file /private/staging.env exec -T calendar-sync \
  python -m app.operations.manual_import \
  --inbox /data/manual-import --instance staging --namespace manual-scope \
  approve --submission my-submission-id --approval /data/approval.json
```

The owning worker validates that approval and applies the batch. Status then
contains APPLIED and the immutable receipt. Canonical changes, receipt and
accepted plan share one transaction. A successful receipt records historical
Outlook status as pending; inspect normal synchronization logs and mappings for
actual fixture convergence. Graph failure never rolls back the canonical batch.

Stale state produces NEEDS_REVIEW without canonical changes. Request a fresh
preview, inspect it, then create a new approval:

```bash
docker compose --env-file /private/staging.env exec -T calendar-sync \
  python -m app.operations.manual_import \
  --inbox /data/manual-import --instance staging --namespace manual-scope \
  preview --submission my-submission-id
```

Each explicit preview request has a new request identity and clears a pending
approval. Wait for the result before sending approval. An intentional corrected
or later import uses a new submission ID while retaining stable fixture IDs.
Omitted fixtures never imply cancellation or deletion.

## Recovery, diagnostics and retention

CLI exit codes are:

- 0: request queued or status available without an error; inspect its state;
- 2: invalid target/input, rejected operation or stale approval;
- 3: inbox/status unavailable or a reported persistence retry is pending.

Startup lock conflicts fail with a nonzero process exit. Check the owning
container, mount permissions and configured instance rather than deleting the
lock. Worker logs use fixed diagnostics and stable IDs, never payloads or
credentials. Private status contains `error` independently of durable batch
state.
Malformed transport is archived without canonical writes; incomplete `.upload`
files are ignored. Unreadable or oversized files are retried/skipped with
bounded
fairness; inspect the private inbox when diagnostics persist.

`pending/` contains immutable requests; `archive/` retains processed input;
`results/` contains replaceable private status/preview/receipt exports. Exact
manifest bytes are retained in SQLite. Manifests remain limited to 2 MiB;
encoded transport and status files are bounded at 16 MiB. Temporary writes are
fsynced and published atomically, with private Unix file permissions.

Persistence failures leave the approval request pending for a later cycle.
An export/archive failure after commit replays safely and returns the existing
receipt. Restart retries pending transport; repeated APPLIED delivery creates
no additional canonical events. A missing result can be rebuilt by explicitly
requesting a preview of the stored package. Invalid requests require correction;
there is no implicit approval or automatic source failover.

No automatic payload expiry or database receipt deletion is enabled. Retain the
full database/inbox through qualification and backup. After a verified backup,
the operator may remove obsolete archived transport and ignored partial uploads
from a stopped instance under the local retention policy. Keep pending requests,
profiles, identity markers and current results. Re-delivering an archived
request
whose archive was removed still cannot duplicate an APPLIED database package.

## Outlook update-review appointments

Only successfully applied packages replace a namespace's accepted full plan.
The worker projects those tasks into the configured SMART calendar using
separate `manual_review_appointments` mappings, stable creation identities and
the existing Graph client. It never uses sports fixture or team-reminder
mappings.

Appointments have a `[Manual update]` title, enabled reminder with the supplied
lead time, Vienna presentation, 15-minute duration, free availability, and no
attendees. The body retains the original due time and explains the manual update
cycle. Dates cover missing kickoff confirmation, next-round draws and return
legs;
the application does not detect a draw or publication automatically.

For first-discovered overdue tasks, the persisted start is current time plus
the reminder lead and five minutes. Restart and unchanged replay preserve that
first catch-up time. Note-only edits preserve it; an explicitly changed due time
is projected anew. Dismissing or deleting a reminder does not trigger polling
recreation; an explicit task update can recover a missing event.

Changed tasks update their existing events. Explicitly completed/replaced tasks
retire only their namespace's managed appointments. A reopened completed task
gets a fresh creation identity. Disabling a namespace retires its appointments.
Graph failures retain pending intent and retry on later cycles. Creation intent
is persisted before POST; retry reuses its transaction ID and patches the
desired
payload before marking it complete. An uncertain POST is recovered before its
intent can be retired, preventing an orphan after a mapping-write failure.

Observe `Manual review appointment pending` logs for Graph recovery. Receipt
status is historical and does not assert reminder delivery. Live tenant
behavior and host backup/restore were accepted in #254, complemented by
automated recovery in #253. Reuse those records for the accepted candidate.
New scopes and materially changed deployments still require qualification.
