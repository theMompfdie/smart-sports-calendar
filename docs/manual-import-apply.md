# Atomic manual import persistence

Issue #251 implements the transactional backend for reviewed manual imports.
It is available as an application service through the container. Inbox transport,
operator CLI commands and the scheduled worker follow in #252; this is not yet
a complete Docker-host import workflow.

## Storage and migration

Migration `013_manual_import_persistence` preserves existing event, source and
assignment IDs. Legacy assignments retain broad competition/season ownership.
The migration does not infer League A ownership from a provider or job name.
Existing source-attribution revision triggers are recreated with stage bounds.

New storage includes:

- `manual_import_instance`: durable database UUID and configured instance name;
- `manual_import_profiles`: trusted namespace/profile and accepted attribution;
- `import_batches`: immutable exact package bytes, fingerprints and review state;
- `manual_import_receipts`: immutable successful canonical import receipts;
- `manual_review_plans`: the current accepted plan for each namespace.

No per-fixture staging tables or result fields are added. Payload retention and
cleanup policy belong to the inbox runbook in #252. SQLite, receipts and private
package artifacts remain on persistent volumes under operator-controlled access.
Use the existing stopped-instance backup/upgrade procedure before a schema
upgrade. Never copy a live WAL database by copying only its main file.

The migration is registered once. Reinitialization preserves the database UUID,
existing content and receipt history. Restore includes the full database and
private transport artifacts. A restored APPLIED package returns its existing
receipt without importing it again. Pending approvals remain bound to database
UUID, configured instance, resolved path and relevant state; a relocated copy
requires another preview. Production and staging must use distinct databases,
instance references and calendars.

## Authority configuration

Manual configuration is an explicit operator action through
`ManualImportService.configure`, separate from package receipt. It resolves the
existing catalog, registers the manual source if absent and creates a permanent
namespace assignment. An inactive manual source is not silently re-enabled.
A configured namespace cannot be moved to another source, competition or season.
All manual profiles in a database must agree on its configured instance name.

Manual grants use explicit stages and `interval_seconds = NULL`; they are not
periodic source jobs. Automatic configuration synchronization preserves these
manual grants on restart. The existing scheduler continues to schedule only its
automated source definitions; no new timer or worker is added in this issue.

Automatic `SOURCE_JOBS_JSON` entries may now add `authority_stages`, a nonempty
array of exact stage IDs. Omission or null retains broad ownership. For example,
adding this field to a separately reviewed League A assignment narrows its grant:

```json
{
  "authority_stages": ["league_a_group_phase"]
}
```

This is an optional field example, not a complete job definition. Existing
required job fields and positive automatic polling intervals remain mandatory.
No deployed configuration is changed by this implementation.

Database triggers reject overlapping active authoritative grants, including
broad-versus-bounded overlap. Configuration also rejects duplicate or malformed
stage sets. Narrowing a source grant fails when existing mappings lie outside
the proposed stages. One automatic source still has one assignment per season;
multiple manual namespaces can share `source_key = "manual"` with disjoint grants.

The canonical importer enforces both new fixture stages and existing mapped
stages. Scoped automated removal evidence must itself declare an owned stage;
a whole-season removal operation cannot bypass the grant. Manual batches always
use PARTIAL scope and never derive deletion or cancellation from omission.
Attribution lookup and revision invalidation use the event's actual stage, so
manual B/C/D grants do not change League A source presentation or revisions.

## Application service lifecycle

The existing application container exposes `manual_import_service`. Its methods
are intended for the single owning application process and the upcoming inbox
worker, not an additional concurrent writer process on the Docker host.

1. `configure(configuration)` installs the independently reviewed profile.
2. `receive(manifest_bytes)` validates and stores one immutable package as
   RECEIVED. Reusing its submission ID with different bytes is rejected.
3. `prepare(submission_id)` calculates the current preview and stores
   AWAITING_APPROVAL or REJECTED. It never applies canonical changes.
4. `approve(submission_id, approval_bytes)` validates the operator's detached
   approval against the reviewed and freshly calculated plans. A mismatch moves
   the package to NEEDS_REVIEW; a valid approval produces APPROVED.
5. `apply(submission_id)` revalidates inside `BEGIN IMMEDIATE`, imports the
   reviewed records and commits their receipt, accepted review plan and APPLIED
   state on the same connection.

Preview computation remains write-free. Storing the preview is explicit staging
bookkeeping, distinct from the standalone read-only CLI described in
[the preview guide](manual-import-preview.md). Re-preparing a pending package
requires another approval; input is never silently approved after state changes.

Apply uses exact manual mappings and disables the historical provider's matchup
correlation. It compares actual canonical decisions to the approved decisions
before committing. A mismatch or persistence failure rolls back the whole batch.
DEFER remains an explicit accepted outcome without a corresponding event write.

After a persistence failure the previous APPROVED state survives rollback and
can be retried after the cause is resolved. Transient retry scheduling belongs
to #252. A stale plan instead commits NEEDS_REVIEW without canonical changes.
Unchanged transport redelivery and repeated apply of APPLIED return the original
receipt. An intentional later replay uses a new submission ID and fresh approval;
unchanged events and review plans retain their revisions.

## Receipts, reminders and Outlook

The private receipt contains submission/type/version, fingerprints, provenance,
operator approval, per-ID outcomes and counts, commit time and accepted review
plan. It records canonical status as committed and Outlook status as pending.
This immutable historical receipt is not a live Outlook convergence indicator.
Inspect normal synchronization results/mappings for current convergence.

The accepted review plan changes only with the successful batch. Rejected input
and stale approval cannot replace it. Changed due dates or reminder lead times
alone do not dirty sports fixtures. Attribution is retained separately and its
accepted changes invalidate only the relevant manual event presentation.

Microsoft Graph stays outside the SQLite transaction. Existing synchronization
selects the committed canonical events and handles Graph failure/retry through
its established mappings. Graph failure never rolls back an already committed
manual batch. Dedicated update-review appointments, their mappings and overdue
catch-up behavior remain #252 work; storing a plan does not create an appointment.

## Qualification boundary

Tests cover legacy-data migration, rollback after multiple fixture writes,
receipt failure/retry, restart/restore, approval invalidation, explicit lifecycle
changes, unchanged replay and SQLite-to-mocked-Graph recovery. Synthetic Nations
League A/B/C/D coexistence verifies that B/C/D imports preserve A's canonical
state and that A cannot apply changes or removal evidence to another stage.

Live source qualification, inbox execution and staging evidence remain required
under #252-#254. Production promotion follows a verified release and separate
operator authorization; blocker #233 is unchanged. No production import or
release publication is performed by this change.
