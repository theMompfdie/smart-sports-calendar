# Phase 8 Outlook Presentation and Media Staging Validation

## Status and release boundary

Status: **partially accepted; final qualification and publication pending**

This runbook owns the isolated live qualification gate in issue #214 for the
`v0.8.0-beta.1` release candidate. It validates the Phase 8 presentation,
runtime reminder, and rights-controlled media behavior against the dedicated
staging SQLite database and Outlook calendar.

Passing this runbook authorizes release preparation only. It does not publish
a tag, create a GitHub release, modify production, or authorize production
promotion.

Never publish raw provider rows, fixture inventories, event titles, calendar
or Outlook identifiers, databases, media files, rights records, credentials,
private paths, source URLs containing secrets, backup manifests, or screenshots
that reveal tenant-specific information.

## Candidate and isolation gate

The validation candidate is built from:

- branch `release/214-v0.8.0-beta.1`;
- the exact reviewed candidate commit recorded privately and later in this
  document after verification;
- the Phase 7 nine-authority baseline; and
- schema `012_create_calendar_event_asset_attachments`.

Stop before deployment unless all statements are true:

- the Portainer stack is exactly `smart-calendar-staging`;
- `INSTANCE_NAME=staging`;
- the stack has its own writable volume, SQLite database, media directory,
  Outlook calendar, credentials, configuration, and logs;
- no other active instance writes to that database or Outlook calendar;
- production remains pinned to its approved immutable release;
- the candidate source is frozen for the validation window;
- `GRAPH_STARTUP_VALIDATION_ENABLED=true`;
- `MEDIA_ROOT=/data/media` or another staging-only persistent path;
- the ignored staging environment renders without printing its values:

  ```bash
  git check-ignore .env .env.portainer-staging
  docker compose --env-file .env.portainer-staging config --quiet
  ```

Do not run `env`, `docker inspect`, raw SQLite dumps, or `SELECT *` as
evidence.

## Backup before candidate deployment

Stop only the exact staging application before copying data. Back up the full
staging `/data` state, not SQLite alone:

- `/data/sports.db`;
- every file below `/data/media`; and
- no unrelated or production volume.

Resolve and verify the exact physical staging volume before the copy. Keep the
backup outside the writable staging volume. Privately record a SHA-256 manifest
for the database and media files, verify that the database is non-empty, and
run `PRAGMA quick_check` against the copied database. Restart staging only
after the snapshot is complete.

Follow the scoped procedure in [deployment.md](deployment.md). Never use
`docker compose down --volumes` during qualification.

## Deploy and validate the upgrade

1. Freeze the staging stack to the reviewed candidate revision.
2. Build and start exactly one `calendar-sync` instance.
3. Require the container to become healthy and startup validation to resolve
   only the dedicated staging calendar.
4. Inspect sanitized startup logs for migration or initialization failures.
5. When the candidate changes the global Outlook HTML template or presentation
   policy, queue every live mapping exactly once after the verified backup:

   ```bash
   docker compose exec -T calendar-sync \
     python -m app.operations.presentation_revisions \
     --database /data/sports.db \
     --invalidate-all
   ```

   Record the aggregate `affected_mappings` count. Do not repeat the command
   while that candidate is converging.

   A pending presentation revision also queues a durable media-body refresh
   before an equal core payload hash is acknowledged. Existing matching CID
   attachments are audited and reused; missing attachments are recovered.
   A failed optional Graph operation remains retryable after a restart without
   another invalidation. Events without media keep the equal-hash no-write path.

   Recovery from candidate `fe50c45`: that candidate could acknowledge a
   media-only presentation change without refreshing the media body. Its zero
   pending-revision count is not visual acceptance evidence. After deploying a
   verified candidate containing the revision-aware media-refresh fix and taking
   a fresh backup, invalidate once for the new candidate. Do not re-import the
   same image assets or repeat invalidation on the old candidate.
6. Run the read-only baseline:

   ```bash
   docker compose exec -T calendar-sync \
     python -m app.operations.staging_evidence \
     --database /data/sports.db \
     --limit 120
   ```

7. Require `database_quick_check=ok`, schema 012, exactly nine authoritative
   jobs, preserved fixture and calendar mapping counts, and no duplicate
   Outlook appointments.
8. Allow bounded synchronization cycles to drain the one-time presentation
   backlog created by the Phase 8 migrations.

Record only aggregate before/after counts. Existing mapping and transaction
identities must remain stable, but their private values must not be copied into
GitHub evidence.

The calendar run's `unchanged` counter describes the core payload, not optional
media writes. Zero mapping revisions and an unchanged core run alone do not
prove that the media HTML or remote attachments are correct. Also require zero
pending media convergence, a scoped remote attachment/CID check, and fresh
Outlook visual inspection before accepting presentation changes.

## Outlook presentation inspection

Privately sample representative football and NFL events in Outlook Web and the
operator's supported desktop client. Confirm:

- exactly one competition category with the manually assigned Outlook color;
- one canonical sport icon prefix in the subject;
- the event editor itself shows the Vienna-compatible timezone rather than UTC,
  with summer and winter samples matching the canonical instant;
- cancellation wording remains unambiguous;
- escaped, readable HTML with participants, Vienna kickoff, location when
  available, status, notices, and source attribution;
- no empty result or statistic placeholder table;
- explicit source end times are retained;
- association-football fallback duration is two hours and NFL fallback
  duration is three hours; and
- no provider HTML, script, remote image, tracking pixel, or source URL is
  rendered.

Record pass/fail and client names only. Do not publish calendar screenshots
unless every tenant- and fixture-specific value has been reviewed and redacted.

## Runtime reminder qualification

The confirmed profile contains six active rules: one global rule, three
competition rules, and two participant rules. The global rule suppresses
reminders by default and supplies shared timing: preferred/minimum lead
60 minutes, maximum 480 minutes, quiet period `22:00`–`08:00`, and
`Europe/Vienna`. The narrower rules enable reminders and inherit these fields.

Before changing an existing profile, privately read it back with `list` and
`show`. Confirm the three exact canonical competition keys with the operator;
#214 names DFB-Pokal (`dfb_pokal`) but does not identify the other two.
Do not overwrite the already accepted profile merely to reproduce examples.

For a fresh profile, run inside the staging container:

```bash
# Set these shell variables privately to the three reviewed catalog keys first.
: "${COMPETITION_ONE:?Set the first reviewed competition key}"
: "${COMPETITION_TWO:?Set the second reviewed competition key}"
: "${COMPETITION_THREE:?Set the third reviewed competition key}"

python -m app.operations.reminder_rules --database /data/sports.db set \
  --scope global --action suppress \
  --preferred-lead-minutes 60 --minimum-lead-minutes 60 \
  --maximum-lead-minutes 480 --quiet-start 22:00 --quiet-end 08:00 \
  --timezone Europe/Vienna --note "Phase 8 shared reminder policy"

for competition in "$COMPETITION_ONE" "$COMPETITION_TWO" "$COMPETITION_THREE"; do
  python -m app.operations.reminder_rules --database /data/sports.db set \
    --scope competition --competition "$competition" --action enable
done

python -m app.operations.reminder_rules --database /data/sports.db set \
  --scope participant --participant manchester_united --action enable
python -m app.operations.reminder_rules --database /data/sports.db set \
  --scope participant --participant new_england_patriots --action enable
```

`set` replaces the whole rule. Omitted timing fields inherit from broader
rules; they do not retain old overrides. Keep CLI output and effective-preview
event keys private.

Use `effective-preview --event <private-canonical-event-key>` and compare
Outlook for a competition-only enable, a participant-only enable where
available, a default-suppressed fixture, and daytime/nighttime cases. An event
matching both competition and participant enable rules does not independently
prove participant-only behavior.

Exercise all mutation paths without restarting:

1. Set a selected participant's preferred lead to 75 minutes and action to
   enable; confirm only its affected mappings become presentation-pending.
2. Restore the action-only enable rule and verify inherited 60-minute behavior.
3. Disable that rule, preview the result, and compare Outlook. Suppression is
   expected only for a sample without an applicable competition enable rule.
4. Set the participant rule again and verify the inherited policy.
5. Delete the other participant rule and verify its inherited result; an
   applicable competition rule may still enable reminders.
6. Recreate that participant rule with action enable, retaining deleted audit
   history.
7. Restart staging and confirm the six final active rules and effective
   policy survive. Keep identifiers and raw CLI readback private.

The late-night case must never schedule a notification inside the Vienna quiet
period. A shift to the previous allowed boundary is valid only when the actual
lead remains between 60 and 480 minutes. Actual notification delivery is a
separate observation from the stored Outlook reminder setting.

## Synthetic-final cleanup

After accepted trophy/media samples, retire the temporary synthetic fixture
through the existing synchronized deletion lifecycle for that exact local
test event. Retire only its temporary event-scoped reminder rule. Do not delete
database rows, clear the calendar, or alter real provider fixtures.

Verify normal synchronization removed the exact remote event and attachments,
retained intended audit history, and restored six active profile rules.
Take a fresh final baseline afterward; the temporary synthetic event/rule must
not inflate final acceptance counts.

The evidence collector retains raw global event, mapping, and attachment-status
counts, and reports the completed subset separately in `retired_local_audit`.
Phase 8 may discount this subset only when the local event is tombstoned, has no
competition, season, parent/child, or provider mapping, has at least one calendar
mapping, all its calendar mappings are successfully `deleted`, and all event
rules are retired. Every remaining attachment audit row must be `event_deleted`
with cleared desired, synchronized, pending, obsolete, remote, and error fields.
The media pending-convergence count excludes only this verified terminal subset.

For example, 2,088 live source fixtures plus one fully retired local test may
produce 2,089 raw event rows, 2,088 `synced` mappings and one `deleted` mapping.
The retired event and mapping counts are each one; a retained terminal attachment
is reported separately and is not unfinished media work. Do not delete those
rows to force the raw totals to match. Live extra events, incomplete deletion,
residual media state, current event rules, and provider failures still block the
gate. Earlier phase validators retain their original strict totals.


## Rights-controlled media qualification

Use only project-owned synthetic artwork or assets with reviewed permission.
Input files, rights records, and normalized binaries remain private and
untracked. At minimum prepare:

- one project-owned `trophy` asset for
  `smart_sports_calendar`;
- one competition `logo` asset for a staged competition; and
- two participant `logo` assets that occur in staged fixtures.

Import, review, and approve each exact version with the documented
`app.operations.media_assets` commands in
[media-asset-registry.md](media-asset-registry.md). Never import an internet
logo merely because it is publicly visible.

After convergence, confirm:

- competition artwork renders through one `cid:` attachment at approximately
  44 x 44 in the outer header cell and 24 x 24 beside the Competition detail;
- participant artwork renders through one reusable `cid:` attachment at
  approximately 44 x 44 beside the correct team name in the title and 30 x 30
  beside the same team in the Participants section;
- the event remains readable when one or all optional images are absent;
- no source URL or filesystem path appears in Outlook;
- the same local asset is not duplicated in SQLite;
- replacing one approved asset uploads the new attachment, switches the body,
  and removes the obsolete attachment without recreating the event;
- disabling one asset removes its image and restores text-only fallback;
- approving the reviewed version again restores the image; and
- an interrupted or failed optional media operation leaves the core event
  synchronized and converges after the controlled cause is removed.

For the failure exercise, manipulate only a precisely resolved staging asset
or staging network boundary after the full `/data` backup exists. Keep the
operation recoverable, never use a wildcard, and never touch production.

## Restart, unchanged cycle, and strict gate

Restart only the staging application. Require the database, media registry,
rules, mappings, and attachments to survive. Run enough bounded cycles to
converge, then require one complete write-free calendar run.

Execute the strict read-only gate:

```bash
docker compose exec -T calendar-sync \
  python -m app.operations.staging_evidence \
  --database /data/sports.db \
  --limit 120 \
  --validate-phase-8-candidate
```

The gate requires:

- SQLite quick check and exact schema 012;
- the exact Phase 7 nine-authority fixture baseline;
- zero pending canonical or presentation revisions;
- a recent unchanged NFL run and write-free calendar run;
- at least one active global and two active participant reminder rules;
  this is a minimum-count guard, not proof of the exact six-rule profile;
- active project, competition, and two participant media assets;
- at least one synchronized competition, home, and away attachment; and
- no failed, pending, uploaded-only, cleanup-pending, obsolete, or otherwise
  unconverged attachment state.

Review the JSON before copying it to GitHub. The Phase 8 projection section
contains aggregate counts only.

Run the strict gate a second time after another unchanged cycle. The two
aggregate projection summaries must remain stable and the second cycle must
perform no Graph create, update, delete, or attachment upload.

## Isolated restore

Restore the stopped-instance backup only into a new explicitly named recovery
volume. Disable Graph and all providers for the restored copy. Never overwrite
staging or production and never connect the restored database to a calendar.

Privately require:

- byte-identical restored database and media files;
- `PRAGMA quick_check=ok`;
- readable schema 012;
- the expected aggregate fixture, mapping, rule, media, and attachment state;
  and
- no missing normalized file referenced by an active media record.

Destroying the temporary recovery volume is a separate explicit operator
decision and is not part of this runbook.

## Accepted checkpoint and outstanding evidence — 2026-09-04

The source of acceptance is [issue #214](https://github.com/theMompfdie/smart-sports-calendar/issues/214).
The current release-branch checkpoint is `a5496c3`; later preparation changes
require their own committed-candidate checks.

Accepted partial observations include competition/home/away/NFL/trophy visual
samples, six remote attachment/CID checks, displayed 60-minute and Vienna
quiet-hour-shifted reminders, default suppression and competition-only enable
samples, and zero revision/media backlog followed by run 8278 with 208
unchanged attachment rows.

Remaining gates are effective rule previews and mutations, restart persistence,
synthetic-final cleanup, media replacement/fallback/interrupted recovery,
full backup/isolated restore, final provider/canonical/Outlook integrity,
duplicate auditing, and fresh unchanged-cycle evidence after all exercises.
Existing accepted evidence may be referenced instead of repeated, but a
screenshot is not recovery evidence and a core unchanged counter is not proof
of zero media writes. #232 and #233 remain open.

## Evidence record

Complete only after every operation has actually passed:

- Candidate commit: `<verified commit>`
- Staging isolation: `<pass/fail>`
- Full stopped-instance backup: `<pass/fail>`
- Upgrade and schema 012: `<pass/fail>`
- Existing mapping convergence/no duplicates: `<pass/fail>`
- Outlook Web presentation: `<pass/fail>`
- Outlook desktop presentation: `<pass/fail>`
- Reminder mutation and Vienna quiet-hours: `<pass/fail>`
- Media upload/replacement/fallback: `<pass/fail>`
- Optional-media failure and recovery: `<pass/fail>`
- Restart persistence: `<pass/fail>`
- Write-free unchanged rerun: `<pass/fail>`
- Backup and isolated restore: `<pass/fail>`
- Strict Phase 8 evidence exit code: `<pass/fail>`

Until every required result is recorded and reviewed, issue #214 and the
`v0.8.0-beta.1` release gate remain open.
