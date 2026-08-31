# Nations League A Isolated Staging Validation

## Status and purpose

This operator-run procedure is the remaining live gate in issue #172 for the
OpenLigaDB UEFA Nations League A 2026/27 group-phase authority implemented by
 #170 and merged through PR #171. It extends the released Phase 5 staging
candidate with exactly one additional authority. It does not authorize
production promotion, a release, or any broader Nations League scope.

The validator accepts exactly these seven enabled authorities:

| Job | Maximum lifecycle scope |
| --- | --- |
| `football-data-premier-league` | qualified `complete_season` |
| `football-data-bundesliga` | qualified `complete_season` |
| `football-data-championship` | qualified `complete_stage` for `REGULAR_SEASON` |
| `openligadb-dfb-pokal` | permanently `partial` |
| `openligadb-second-bundesliga` | removal-disabled `partial` |
| `oefb-ical-oefb-cup` | permanently `partial` |
| `openligadb-uefa-nations-league` | filtered, removal-disabled `partial` for `league_a_group_phase` |

For Nations League A, validation requires exactly 48 active fixtures, 48 event
source mappings, 16 private participant source mappings, one Outlook mapping
per fixture, one calendar target, no pending revisions, stage count
`league_a_group_phase=48`, and four round counts of 12 for `group-a-1` through
`group-a-4`. Its latest provider run must report `authoritative=true`,
`filtered=true`, `complete=false`, `scope_kind=partial`,
`scope_stage_kind=league_phase`, and `removal_eligible=false`.

Stop immediately if staging shares a database, volume, calendar, credentials,
stack name, or writable resource with production. Never print the effective
environment or copy raw logs, provider responses, event details, external IDs,
calendar identifiers, or deployment identifiers into GitHub evidence.

## Preconditions

- The isolated staging stack runs the reviewed revision containing the #172
  evidence tooling.
- Ruff, pytest, Compose, Docker, and GitHub Actions pass for that revision.
- Staging automatic updates are disabled for the validation window.
- A dedicated non-production Microsoft 365 mailbox and calendar are selected.
- The staging database has a verified backup before recovery exercises.
- The operator can edit only the staging OpenLigaDB base URL for the controlled
  failure exercise.
- The six released Phase 5 authorities already satisfy their documented
  staging contracts.
- No real secret, feed URL, database, calendar export, or provider dataset is
  present in the checkout or image build context.

Confirm locally that secret files are ignored and the checkout is clean:

```bash
git check-ignore .env .env.portainer-staging
git status --short --branch
```

## Secret-safe configuration

Keep real identifiers and credentials only in Portainer or another ignored
operator secret store. Preserve the existing six Phase 5 jobs and append this
seventh entry to the single-line `SOURCE_JOBS_JSON` array:

```json
{"job_key":"openligadb-uefa-nations-league","source_key":"openligadb","sport_key":"football","competition_key":"uefa_nations_league","season_key":"2026_27","role":"authoritative","interval_seconds":21600}
```

Required non-secret settings are:

```env
INSTANCE_NAME=staging
IMAGE_TAG=<reviewed-git-reference>
DATABASE_PATH=/data/sports.db
GRAPH_STARTUP_VALIDATION_ENABLED=true
OPENLIGADB_ENABLED=true
OPENLIGADB_BASE_URL=https://api.openligadb.de
OPENLIGADB_MINIMUM_REQUEST_INTERVAL_SECONDS=1
```

Do not paste the complete rendered Compose configuration into an issue because
it includes deployment-specific values. Validate and redeploy only the staging
project:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

## Fresh source qualification

Before accepting imported data, run the credential-free bounded validator from
the reviewed application image or checkout:

```bash
python -m app.operations.openligadb_qualification --competition nations-league-a-group-phase
```

The sanitized result must retain:

- qualification profile `nations-league-a-group-phase`;
- OpenLigaDB league `5978`, shortcut `nla`, provider season `2026`;
- exactly 48 selected fixtures and 16 participants;
- four selected groups with 12 fixtures each;
- stable fixture and participant SHA-256 fingerprints; and
- no structural, timezone, duplicate, cross-group, or scope failure.

The command emits only bounded aggregates, public competition metadata, and
hashed provider identity sets. Review the JSON before copying it outside the
staging host. Any changed fingerprint requires explicit comparison and review;
it must not be accepted merely because the counts still match.

## Read-only candidate evidence

After all seven provider jobs and calendar synchronization have converged, run:

```bash
docker compose exec -T calendar-sync python -m app.operations.staging_evidence --database /data/sports.db --limit 100 --validate-nations-league-a-candidate
```

The command opens SQLite read-only and fails unless the exact seven-authority
candidate and every required lifecycle invariant are satisfied. Its output
contains only:

- public canonical source, job, competition, season, stage, and round keys;
- aggregate fixture, mapping, status, and revision counts;
- UTC observation boundaries and run counters;
- safe lifecycle flags and error categories; and
- SHA-256 hashes of sorted source event IDs.

It excludes event titles, participant names, provider IDs, Outlook IDs,
calendar IDs, URLs, tokens, credentials, raw metadata, error messages, and raw
payloads.

## Validation sequence

### 1. Initial convergence and attribution

1. Confirm the container is healthy and Graph startup validation accepts only
   the dedicated staging calendar.
2. Wait for all seven independent provider jobs and calendar batches to
   complete.
3. Run the candidate evidence command and stop on any validation failure.
4. Confirm the Nations League scope has 48 fixtures, 48 event mappings, 16
   participant mappings, 48 synchronized Outlook mappings, zero pending
   revisions, one target calendar, the exact stage, and four 12-fixture groups.
5. Manually sample private staging events and confirm the visible attribution:
   `Fixture data provided by OpenLigaDB (ODbL 1.0): https://www.openligadb.de/`.
6. Confirm Leagues B/C/D and every later stage are absent.

### 2. Unchanged-cycle idempotency

Allow another complete provider and calendar cycle without configuration
changes, then rerun candidate evidence. Require stable fixture and source-ID
fingerprints, 48 unchanged Nations League items, zero create/update/cancel/
delete decisions, zero pending revisions, and no Graph writes.

Do not edit live SQLite or provider payloads to manufacture a reschedule. If no
natural provider change occurs during the window, cite the deterministic
reschedule proof in
`tests/integration/test_openligadb_nations_league_a_to_outlook.py`.

### 3. Restart and recovery

Restart only the staging application:

```bash
docker compose restart calendar-sync
docker compose ps
```

After convergence, rerun candidate evidence. `startup_records` must increase;
fixture fingerprints, participant/event mappings, and Outlook mappings must
retain their identities. Do not manufacture an interrupted SQLite write; cite
the automated recovery coverage for unsafe interruption points.

### 4. Controlled OpenLigaDB failure

Perform this only after a successful backup and baseline:

1. Set only the staging `OPENLIGADB_BASE_URL=https://127.0.0.1` and redeploy.
2. Observe one bounded failed cycle for all three OpenLigaDB jobs.
3. Confirm last-known-good Nations League, DFB-Pokal, and 2. Bundesliga state is
   unchanged while football-data.org, ÖFB iCalendar, and calendar
   synchronization remain operational.
4. Confirm no cancellation or deletion evidence is created.
5. Restore `OPENLIGADB_BASE_URL=https://api.openligadb.de`, redeploy, and
   require successful unchanged convergence.

Never alter tokens, authority roles, job scopes, production configuration, or
the production stack. Review logs locally for the expected safe error category
but do not paste unreviewed error text into GitHub.

### 5. Backup and isolated restore

Follow the scoped SQLite backup procedure in [`deployment.md`](deployment.md).
Restore only into a new explicitly named recovery volume with Graph and every
provider disabled. Never overwrite staging or production and never connect the
restored database to a calendar.

Run the evidence command against the restored database without a candidate
validator. Confirm `database_quick_check=ok`, seven authority scopes, expected
aggregates, and stable fingerprints. Volume deletion remains a separate
explicit operator action.

## Sanitized evidence template for #172

```markdown
### Nations League A isolated staging record

- Candidate commit/tag: `<public Git reference>`
- Validation window (UTC): `<start>` to `<end>`
- Staging/production isolation: `<pass/fail>`
- Exact seven-authority configuration: `<pass/fail>`
- Fresh Nations League qualification: `<pass/fail and aggregate comparison>`
- League A 48-fixture/16-participant/four-group boundary: `<pass/fail>`
- Initial SQLite and Outlook convergence: `<pass/fail>`
- OpenLigaDB/ODbL attribution: `<pass/fail>`
- Excluded leagues and stages absent: `<pass/fail>`
- Unchanged-cycle idempotency: `<pass/fail>`
- Restart recovery: `<pass/fail>`
- Deterministic reschedule/interruption evidence: `<test names and result>`
- OpenLigaDB failure and recovery: `<pass/fail>`
- Other-authority isolation during failure: `<pass/fail>`
- Backup integrity and isolated restore: `<pass/fail>`
- Secret, identifier, payload, and export review: `<pass/fail>`
- Follow-up defects or limitations: `<issue numbers or none>`

#### Secret-safe candidate evidence

`<paste reviewed staging_evidence JSON>`
```

Issue #172 may close only when every gate passes or every failed gate has a
focused blocking issue. Successful staging does not authorize production
promotion, a tag, or release publication.
