# Cookbook: deactivate a completed competition season

Issue [#267][issue] adds an explicit maintenance workflow for completed seasons
and existing, disjoint stage grants. This is unreleased Version 1.0 work;
isolated live staging remains a release gate. The published v0.9.0-beta.1 image
does not contain these commands.

## What retirement changes

Retirement persists an effective inactive state in SQLite migration 015.
It does not edit the environment or trusted profile files. Keep the original
source job and profile configured: their authority, broad or stage-specific
boundary, source attribution and stable identities remain reserved.
Startup and configuration reload do not reactivate the scope. Trying to move,
narrow, disable or remove a retired grant fails closed; reactivate explicitly
before an intentional authority reconfiguration.

The scheduler skips provider work for overlapping retired scopes, manual
preview/apply rejects their new work, and routine sports-event synchronization
excludes their historical fixtures. Other seasons and disjoint stages continue.
Retirement is never fixture cancellation, deletion, or missing-snapshot
evidence.

Matching manual review plans and their Outlook appointments remain unchanged.
The retirement gate excludes both from routine synchronization, including
pending review writes. No review appointment is created, updated or deleted
while its scope is retired. This preserves the operator's calendar history of
manual update reminders for planning the next season. Import payloads, immutable
receipts and provenance retain the evidence of what was actually imported;
a reminder appointment alone is not proof that an import happened.
Explicit reactivation resumes the retained plans and any pending review work.

## Completion decision and correction period

Review the actual permitted source and document that **the entire owned
boundary** has finished. A passed kickoff, a season end date, an empty import,
or the end of the latest published round is insufficient evidence. Confirm
there are no unpublished later rounds, return legs, unresolved participants,
postponed matches or unknown kickoff times remaining in that boundary.

The decision file requires:

- `operator_ref`: a non-secret operator identifier.
- `evidence_ref`: a non-secret identifier referring to the private completion
  evidence; no source URLs, tokens, credentials or document contents.
- `completed_at`: the reviewed actual completion instant, including timezone.
  It must be at or after every stored fixture start/end in the boundary.
- `grace_days`: the explicit correction period, from 0 to 3650 whole days.
  The example uses 14 days; choose and review the period for this competition.
  Zero requires the same explicit decision and is not an automatic default.
- `complete_schedule_confirmed`: must be `true` after that review.

Deactivation is allowed only after `completed_at + grace_days`. The program
rejects stored live, postponed, suspended or abandoned fixtures, later start/end
times, and unresolved operator notices on non-cancelled events. It also checks
the latest accepted manual observation for each stable fixture ID, including
unknown kickoffs that never produced a canonical event. Partial imports retain
earlier observations; an omission cannot resolve an outstanding fixture.

Some sources keep past fixtures in `scheduled` or `confirmed` status and do not
supply results. Those statuses alone do not block retirement: the explicit
completion evidence is required. The program cannot independently verify that
an unpublished round does not exist. Resolve incorrect or outstanding source
data through the normal reviewed import before retirement; never edit SQLite.

For EFL Cup, qualify the actual completion of the selected season. This cookbook
does not assume a February end date. The dates and identifiers below are
synthetic examples, not completion evidence for a live competition.

## Before the maintenance window

1. Use a qualified image containing migration 015, boot it normally to migrate,
   and let fixture synchronization converge. Take a full instance backup using
   the [deployment procedure](deployment.md), including database, inbox,
   trusted profiles and retained private payloads.
2. Find the exact configured source job key. Manual jobs use
   `manual:<namespace>`. Select its **entire existing grant**. The CLI cannot
   split a broad grant or retire just one stage inside a multi-stage grant.
3. Prepare the private decision file on the instance's persistent volume,
   for example `/data/operations/retirement-decision.json`:

   ```json
   {
     "operator_ref": "operator-local",
     "evidence_ref": "efl-cup-2030-completion-reviewed",
     "completed_at": "2030-12-01T00:00:00Z",
     "grace_days": 14,
     "complete_schedule_confirmed": true
   }
   ```

4. Finish any approved import that should still apply. Remaining nonterminal
   packages in the boundary will be explicitly rejected by deactivation.
5. Stop the owning application. All retirement commands acquire its existing
   OS instance lock, including preview. A running owner causes refusal before
   any lifecycle change. Never remove the lock file or force past this refusal.

The shutdown must let any current import or Graph operation finish. Following
a forced termination, first restart normally and recover interrupted work.
Outstanding fixture Graph work blocks retirement until mappings, revisions and
media operations have converged. The CLI performs no Graph calls.

## Docker-host recipe

Run from the deployment checkout, with the actual instance values below.
For Portainer, stop the selected stack's owning container in Portainer and use
its exact container ID. Keep it present so its existing volume mounts can be
reused. Do not recreate, remove, or change the other stack.

```bash
stack='smart-calendar-staging'
env_file='/absolute/private/staging.env'
calendar_id='configured-staging-smart-calendar-id'
job='manual:demo-efl-cup-2030'
database='/data/sports.db'
decision='/data/operations/retirement-decision.json'
inbox='/data/manual-import'

docker compose --env-file "$env_file" -p "$stack" stop calendar-sync
container=$(docker compose --env-file "$env_file" -p "$stack" ps -aq calendar-sync)
image=$(docker inspect --format '{{.Image}}' "$container")
```

Verify that `container` is exactly the stopped target container and `image` is
the qualified image containing this feature. Adjust `database` for a custom
`DATABASE_PATH`. For manual grants, set `inbox` to the actual
`MANUAL_IMPORT_ROOT`; its instance and database markers must match.
Automated-only
grants do not require `--inbox`. Set `calendar_id` to the configured
`OUTLOOK_CALENDAR_ID`; do not copy a staging ID to production. The maintenance
container
uses that immutable local image and the stopped owner's volume mounts. It
does not run application bootstrap, retrieve credentials, or contact Graph.

Define a helper for this shell session:

```bash
retirement() {
  docker run --rm --network none --volumes-from "$container" \
    --entrypoint python "$image" -m app.operations.season_retirement "$@" \
    --database "$database" --calendar "$calendar_id" --job "$job" \
    --inbox "$inbox"
}

retirement preview --decision "$decision"
```

Inspect the complete preview, keeping it private. It shows the selected
assignment and stages, affected routine jobs and namespaces, preserved fixture
IDs, unresolved fixtures, pending Graph work, packages to reject, review plans
to preserve, existing review appointments with their calendar/event IDs, and
unprocessed inbox requests in the boundary. An unavailable, mismatched or
uninspectable manual inbox blocks retirement. Files arriving after the decision
are rejected by the worker while the scope remains retired.
The preview binds the decision, database identity, calendar, fixture snapshot
and affected work into `preview_sha256`.

Proceed only with an empty `blockers` list and the intended scope. An
overlapping
job extending beyond the selected boundary is refused. For example, retiring
a disjoint Nations League B grant leaves League A/C/D untouched, while a legacy
broad Nations League grant cannot be silently narrowed into a League B grant.

```bash
preview_sha256='paste-the-reviewed-preview-sha256'
retirement deactivate --decision "$decision" --preview-sha256 "$preview_sha256"
docker compose --env-file "$env_file" -p "$stack" start calendar-sync
```

Changing relevant database state between preview and deactivate invalidates
the preview. Restart, resolve the reported blocker, stop again and review a new
preview as necessary. Do not blindly retry an old approval.

After restart, inspect normal logs and verify that fixture and review
appointments retain their IDs and content. The scope becomes `retired` in the
maintenance transaction; no Graph cleanup is scheduled. Keep trusted profiles
and the original source configuration present.

Repeating `deactivate` with the same decision is idempotent. It does not create
another audit decision or write calendar events. A different decision for an
already retired scope is rejected.

## Pending packages and interruption policy

| Work at the boundary | Policy |
| --- | --- |
| Received, previewed or approved package | Reject atomically; clear approval |
| Needs-review or retryable package | Reject atomically; preserve payload |
| Applied package | Preserve immutable receipt and canonical outcome |
| Inbox transport not processed yet | Reject when processed while retired |
| Import currently applying | Owner lock refuses concurrent retirement |
| Fixture Graph work outstanding | Block until recovery and convergence |
| Matching review appointment | Preserve unchanged; freeze pending writes |

Old transport files are retained by the existing inbox lifecycle. Redelivery of
an APPLIED package remains an idempotent receipt lookup. A received/rejected
package cannot regain approval while the scope is retired. After explicit
reactivation, a fresh preview and approval are necessary before applying any
previously rejected package; old approvals were cleared.

The gate, package rejections and audit entry commit together. A pre-commit
failure rolls them all back. A post-commit interruption leaves the gate active
without scheduling Graph mutations. Current review plans, appointments and
immutable accepted receipts remain unchanged.

## Late correction and next season

Stop the owner and reactivate the same job with non-secret correction evidence:

```bash
retirement reactivate --operator-ref operator-local \
  --evidence-ref reviewed-late-correction
docker compose --env-file "$env_file" -p "$stack" start calendar-sync
```

The existing authority and stable fixture IDs are reused. Automated jobs resume;
manual corrections require the usual new preview and approval. Retained review
plans and pending review operations resume, so inspect them before reactivation.
Rejected package approvals remain invalid. Retire again with a new reviewed
decision and correction period after corrections converge.

A future season is an explicit new configuration/catalogue activation using a
new job or manual namespace and its qualified season/stage profile, following
the [source configuration](source-orchestration.md) or
[manual workflow](manual-import-workflow.md). Do not repurpose the old job key,
namespace or season IDs. Retirement of the old season stays effective; overlap
validation still rejects competing broad or overlapping stage writers. This
feature does not invent future-season catalogue entries or qualify a provider.

## Staging evidence and rollback

Issue #267 live acceptance completed on existing isolated staging with synthetic
scopes on candidate `59dd553`. Deactivation, restart, retained Outlook history,
control-scope updates and reactivation/correction were verified. Repeat
deactivation and unchanged replay also retain deterministic regression coverage.
For future qualification, use a staging database and SMART calendar to verify:

1. Preview and deactivate an actually completed, reviewed boundary.
2. Confirm unchanged fixture and review Outlook IDs and historical content.
3. Restart and repeat unchanged deactivation without new Graph writes.
4. Verify another season or disjoint stage continues importing normally.
5. Reactivate, apply a reviewed correction with retained IDs, and converge.
6. Record the private decision, preview, effective dates and retained-history
   evidence; link only non-secret references from release tracking.

Automated tests use synthetic data and mocked Graph. They do not replace this
live release gate. No live retirement or production deployment is performed by
implementing the feature or running its unit tests.

Normal undo is explicit reactivation. An older application
image does not understand migration 015's effective gate and must not run on
this database after retirement. For a version rollback, stop the owner and
restore the complete matching pre-upgrade backup using the existing rollback
procedure; qualify the resulting Outlook state before resuming. Do not drop
tables, erase audit records, or delete historical sports events.

[issue]: https://github.com/theMompfdie/smart-sports-calendar/issues/267
