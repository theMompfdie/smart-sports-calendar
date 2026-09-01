# Runtime reminder rule administration

Status: Implemented persistence, local operator CLI, Vienna-aware reminder
resolution, and targeted Outlook convergence for Phase 8.4–8.6 (#209–#211)

SMART Sports Calendar stores reminder preferences in the same SQLite database
as its canonical sports data. Migration `009_create_reminder_rules` is
forward-only, deterministic, and idempotent. It creates the reminder-rule
schema without modifying or deleting existing sports events.

Each Outlook payload build reads and resolves the currently committed rules.
Quiet-period calculation produces exactly one integer Graph lead or a disabled
reminder. Migration `010_add_presentation_sync_revisions` separates desired
and last-synchronized Outlook presentation revisions from canonical fixture
revisions. A rule mutation and its mapping invalidations commit in one SQLite
transaction, so only matching live mappings become immediately actionable.

## Rule scopes and inheritance

A rule can target one of five canonical scopes:

1. `global`
2. `competition`
3. `participant`
4. `competition_participant`
5. `event`

Resolution overlays non-null fields in that fixed broad-to-specific order. The
compatibility fallback enables reminders 15 minutes before an event in
`Europe/Vienna`. There is no numeric operator priority and display names are
never matching keys.

Participant rules for both sides of an event have equal precedence. Conflicting
values are rejected instead of being selected by database row order. A more
specific competition-participant or event rule can resolve that conflict.
Inherited lead-time ranges are validated before an operator mutation commits.
The mutation is rolled back if it would make an existing event policy invalid.
Rules that only become applicable to a future event remain fail-safe at resolver
time and never gain an implicit ordering.

## Operator CLI

Run the CLI locally against one explicit database path. Stop or otherwise
quiesce the application before migration, backup, or restore work. Normal rule
updates use an immediate SQLite transaction and a five-second busy timeout, so
readers continue to see a committed state and concurrent writers fail cleanly
rather than partially applying a rule.

The intended selected-team policy can be configured as follows:

```console
python -m app.operations.reminder_rules --database /data/sports.db set --scope global --action suppress --note "Selected teams only"
python -m app.operations.reminder_rules --database /data/sports.db set --scope participant --participant manchester_united --action enable --preferred-lead-minutes 60
python -m app.operations.reminder_rules --database /data/sports.db set --scope participant --participant new_england_patriots --action enable --preferred-lead-minutes 60 --minimum-lead-minutes 60 --maximum-lead-minutes 480 --quiet-start 22:00 --quiet-end 08:00 --timezone Europe/Vienna
```

`set` completely replaces the current rule at that natural scope. Omitted
policy fields become inherited fields; they do not retain values from the
previous rule. `--action inherit` explicitly selects no action at that scope,
but at least one other policy field must then be supplied.

Inspect or manage rules with canonical catalog keys:

```console
python -m app.operations.reminder_rules --database /data/sports.db list
python -m app.operations.reminder_rules --database /data/sports.db list --include-deleted
python -m app.operations.reminder_rules --database /data/sports.db show --scope participant --participant manchester_united
python -m app.operations.reminder_rules --database /data/sports.db disable --scope participant --participant manchester_united
python -m app.operations.reminder_rules --database /data/sports.db delete --scope participant --participant manchester_united
python -m app.operations.reminder_rules --database /data/sports.db effective-preview --event nfl:new_england_patriots:night_game
```

`suppress` is a reminder policy action and therefore participates in
inheritance. `disable` deactivates the complete rule while retaining its
current audit record. `delete` tombstones and deactivates the rule; deleted
history appears only with `list --include-deleted`. A later `set` creates a new
current row and preserves the tombstoned history.

The CLI initializes pending migrations without loading Microsoft 365 or source
credentials. It rejects unknown or ambiguous canonical keys, malformed local
times, negative or inconsistent lead ranges, and unknown IANA timezones. JSON
output contains canonical keys and audit timestamps but omits internal database
IDs, Outlook IDs, event titles, the database path, and private provider data.
`effective-preview` additionally reports the resolution reason, integer lead,
UTC and configured-local reminder instants, and any conflicting policy fields.
It does not contact Microsoft Graph or a sports provider.

Rule updates do not increment `sports_events.sync_revision`. A presentation
revision is acknowledged only for the revision captured before rendering. If a
second rule mutation commits during a Graph request, the newer revision remains
pending for the next bounded synchronization cycle. If re-rendering produces
the same content hash, the application records the captured revision as checked
without sending an unnecessary Graph PATCH.

After changing a global HTML template or another project-wide presentation
policy, explicitly queue every live mapping:

```console
python -m app.operations.presentation_revisions --database /data/sports.db --invalidate-all
```

The command prints only the number of affected mappings. Existing transaction
IDs, Outlook IDs, retry state, deletions, and canonical revisions remain
unchanged. The configured synchronization batch limit drains this backlog over
successive cycles; canonical fixture changes retain higher candidate priority.

## Quiet-period resolution

Lead limits are inclusive elapsed minutes between UTC instants. Quiet-period
membership and boundary selection use the effective rule's IANA timezone.
The resolver starts with the preferred lead. If that instant is strictly
inside the quiet period, it moves backward to the most recent quiet-start
boundary and recomputes the actual lead. Exact quiet-start and quiet-end values
are allowed. Equal boundaries mean no quiet period.

The resulting reminder is disabled with a zero-minute Graph lead when the
policy is suppressed, equal-precedence fields conflict, the shifted lead is
outside its configured bounds, or the shifted instant cannot be represented as
an exact integer number of minutes before kickoff.

Daylight-saving boundaries are resolved independently of the host timezone.
For an ambiguous local boundary, the earlier absolute instant is selected so a
notification is never silently moved later. For a nonexistent boundary during
the spring transition, the resolver selects the latest valid local minute
before it. Canonical kickoff changes and committed rule changes are recalculated
on the next payload build without restarting the process.

## Backup, restore, and rollback

Before first running code that contains migrations 009 and 010, stop the exact
instance and create a transactionally consistent copy of its project-scoped
`/data/sports.db` as described in [Deployment](deployment.md). Keep the backup
outside the Docker volume and verify it with `PRAGMA quick_check`.

The migration records, reminder rules, and presentation revisions are part of
the SQLite database, so a normal database backup and restore includes them.
Migration 010 intentionally queues every existing mapping once to converge the
Phase 8 HTML/category/icon/reminder projection. There is no destructive
downgrade SQL. If an application rollback requires the pre-migration schema:

1. stop the exact application instance;
2. preserve the current database separately for investigation;
3. restore the verified pre-upgrade database backup;
4. restore the previously verified application version; and
5. start one instance and verify health, migration state, and calendar target.

Restoring an older backup intentionally loses every rule and other state change
recorded after that backup. Never attach a restored copy and the original
writable database to active instances targeting the same Outlook calendar.
