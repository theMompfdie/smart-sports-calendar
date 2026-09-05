# Previewing a manual fixture import

Issue #250 adds a standalone, write-free preview of `fixture_schedule` v1.
It does not submit, approve or apply a package and does not contact Graph.
The manifest contract is described in
[the preparation guide](manual-import-preparation.md).

## Run a preview

Use an already initialized instance database and an operator-controlled profile:

```powershell
python -m app.operations.manual_import_preview `
  --database C:/private/calendar.sqlite `
  --profile C:/private/manual-profile.json `
  --manifest C:/private/fixtures.json
```

The same module runs on Linux with Linux paths. Docker inbox commands and
mount configuration follow in #252. The CLI prints a private JSON report to
stdout; redirect it only into operator-controlled storage. Exit code 0 means
the batch is valid for this preview; exit code 2 means rejection or unavailable
input/database. It is not evidence of applied fixtures or Outlook convergence.

The command opens the existing SQLite database with `mode=ro`, enables
`query_only` and reads one transaction snapshot. It never initializes a missing
database, runs migrations, registers sources, synchronizes assignments,
acquires Graph credentials or writes a receipt. Normal SQLite WAL locking and
shared-memory coordination remain necessary when reading a running instance;
do not use `immutable=1`, which could ignore committed WAL data.

## Trusted profile

[The synthetic EFL Cup profile][profile]
shows the complete configuration shape:

- `instance_ref`: an operator-controlled stable identifier for this instance;
- `namespace`: the permanent manual fixture namespace;
- `scope`: exact `sport_key`, `competition_key` and `season_key`;
- `competition_format`: the canonical competition format;
- `boundaries`: the qualified stage, round and nullable stage-kind combinations.

The profile must be stored separately from incoming manifests and writable only
by the operator. A submitted package cannot grant its own scope. Participant
keys and names come from the selected season's persisted catalog membership.
Unknown keys and catalog/profile conflicts reject the batch, without fuzzy
matching or automatic catalog creation. The synthetic profile is not a real
source qualification or a provisioned catalog.

The manual source key is `manual`. A missing source row is visible in the
precondition and permits planning only; its controlled provisioning belongs
to #251/#252. An inactive manual source rejects preview. Any enabled competing
authoritative or bootstrap assignment rejects preview. Verification and
disabled assignments do not grant writes. Existing whole-season assignments
remain whole-season assignments, including Nations League A.

## Fixture decisions

The report includes source provenance, normalized fixture records, effective
existing-event targets, per-record reasons and warnings, and decision counts:

- CREATE: a new stable identity with resolved participants and confirmed time;
- UPDATE: a reviewed correction, postponement or explicit reinstatement;
- SKIP: the existing eligible canonical content is unchanged;
- CANCEL: a first explicit cancellation of a known mapped fixture;
- DEFER: unresolved participants or a new fixture without confirmed kickoff.

Unresolved existing fixtures remain unchanged. An existing fixture with unknown
kickoff retains its last confirmed time, with an explicit warning. Null venue
or city retain the existing values, matching the current canonical importer;
these nulls are not clearing instructions. Repeated cancellation is SKIP.
Source observation and preparation timestamps stay outside event content
comparison, so a newly prepared unchanged manifest need not update Outlook.

Only exact manual source mappings with the expected stable event key are
accepted. Mappings outside scope, shared provider mappings and suspicious new
IDs for an existing matchup/round/leg require explicit review. No automatic
cross-source correlation is performed. A distinct round or explicitly different
leg may create a distinct identity. Issue #251 must preserve this behavior when
integrating apply; the historical provider importer's heuristic must not run
for manual fixtures.

Omitted fixtures produce no operation. DELETE is unavailable. Any rejected
record makes `accepted` false for the whole batch; decisions shown for other
rows are diagnostic candidates, not permission to import those rows. Structural
parser errors reject before state lookup and identify the invalid field.

## Update-review appointments

Review appointments are listed separately from sports fixtures as CREATE,
UPDATE, SKIP or RETIRE, using stable task IDs. The complete proposed plan
replaces the namespace's accepted plan; a complete plan explicitly retires its
previous tasks. Each proposed task includes the original due time and reminder
lead minutes. Overdue tasks stay visible. No wall-clock polling changes the
preview fingerprint or silently reschedules a task.

The pure planner supports comparison against an accepted plan in its snapshot.
The current database has no accepted-plan storage, so the standalone reader
supplies no previous plan and shows initial task creation. Issue #251 must add
transactional plan persistence and extend this reader before applying imports.
Issue #252 owns actual Outlook appointment projection and one-time overdue
catch-up. This preview does not create Outlook events or dismiss reminders.

## Review and stale-state checks

`preview_sha256` hashes the canonical JSON report before adding that field.
The report binds the exact manifest bytes, validator version, instance reference,
resolved database-path identity, effective trusted profile and relevant state.
That state includes season catalog membership, source assignments and activity,
namespace mappings, canonical season events and their participants, schema
versions and the accepted review plan when supplied.

The digest includes absent proposed mappings and the season's possible identity
candidates. It conservatively invalidates on another event change within that
season, but unrelated startup logs do not invalidate it. It is neither an mtime
check nor a full-database hash. Identical copies at different database paths
are different targets. Moving the database requires another preview.

`validate_preview_approval` checks report integrity, exact package identity,
instance, fingerprints and approval time against a newly calculated report.
There is no standalone apply or approval-writing command in this issue.
Issue #251 must read and recalculate under its single `BEGIN IMMEDIATE`
transaction and reject changed preconditions before any mutation. Persisted
instance identity and receipt integration must be finalized there; a path hash
alone is not a durable database-instance UUID across restore/replacement.

## Nations League authority extension

The design extension in
[ADR 0015](adr/0015-import-reviewed-manual-fixture-manifests.md) proposes explicit,
non-overlapping stage grants for one competition/season. A pure validator and
regression tests cover broad-grant and stage-overlap rejection here.
No assignment schema, runtime writer selection or scheduler ownership changes
are made in #250. Manual B/C/D preview remains blocked by an enabled broad
League A assignment until #251 implements and qualifies the explicit migration
and runtime enforcement. A profile cannot narrow that existing assignment.

[profile]: examples/manual-import/profiles/efl-cup-preview-profile.json
