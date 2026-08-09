# football-data.org Premier League Isolated Staging Validation

This operator-run procedure is the live validation gate for issue #63 and the
`v0.4.5-beta.1` candidate. It validates the 2026/27 Premier League integration
against football-data.org API v4 and a dedicated Microsoft 365 staging
calendar. It does not authorize production promotion; that remains the manual
decision tracked by issue #64.

The deterministic automated suite remains the reproducible release gate. Live
validation adds environment confidence and must never run in GitHub Actions or
place credentials, tenant identifiers, calendar identifiers, raw responses, or
secret-bearing URLs in repository or GitHub artifacts.

## Safety boundary

- Deploy only the reviewed candidate from `develop` to
  `smart-calendar-staging`.
- Keep the staging stack, SQLite volume, Outlook calendar, credentials, and log
  stream distinct from production.
- Never allow two active instances to share a writable database or target
  calendar.
- Configure `football_data` as the only authoritative writer for
  `football` / `premier_league` / `2026_27`.
- Keep API-Football disabled. A missing or disabled authority must fail closed;
  it must not silently promote a fallback writer.
- Supply live credentials only through Portainer or an ignored operator secret
  store. Do not print the effective environment or enable shell tracing.
- Display the attribution text
  `Football data provided by the Football-Data.org API` wherever provider
  attribution is presented.

Stop immediately if isolation, calendar targeting, database ownership, secret
hygiene, source authority, or provider scope differs from this boundary.

## Prerequisites

- A reviewed candidate commit or immutable candidate tag from `develop`.
- The isolated `smart-calendar-staging` Portainer stack with automatic updates
  disabled for the validation window.
- A non-production Microsoft 365 mailbox and dedicated SMART Sports Calendar.
- A football-data.org token with access to competition `PL`, season `2026`.
- A verified backup of the staging SQLite volume.
- Access to staging-only networking controls for the recovery exercise.
- Green Ruff, pytest, Compose, Docker, and GitHub Actions checks for the
  candidate.

Confirm that the local `.env` path is ignored before entering any value:

```bash
git check-ignore .env
```

## Secret-safe configuration

Set real values only in Portainer or another ignored deployment secret store:

```env
INSTANCE_NAME=staging
M365_TENANT_ID=<deployment-secret>
M365_CLIENT_ID=<deployment-secret>
M365_CLIENT_SECRET=<deployment-secret>
M365_USER_ID=<target-mailbox>
OUTLOOK_CALENDAR_NAME=SMART Sports Calendar
OUTLOOK_CALENDAR_ID=<dedicated-staging-calendar-id>
GRAPH_STARTUP_VALIDATION_ENABLED=true
API_FOOTBALL_ENABLED=false
API_FOOTBALL_API_KEY=
FOOTBALL_DATA_ENABLED=true
FOOTBALL_DATA_API_KEY=<deployment-secret>
FOOTBALL_DATA_REQUESTS_PER_MINUTE=10
FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS=6.1
SOURCE_JOBS_JSON=[{"job_key":"football-data-premier-league","source_key":"football_data","sport_key":"football","competition_key":"premier_league","season_key":"2026_27","role":"authoritative","interval_seconds":3600}]
```

The free-plan budget is enforced even when optional quota headers are absent.
Do not copy tokens, effective configuration, headers, tenant data, or full
request URLs into the evidence record.

## Secret-safe evidence command

Use the built-in read-only summary instead of ad-hoc `SELECT *` queries:

```bash
python -m app.operations.staging_evidence --database /data/sports.db
```

It reports public source/scope keys, fixture and mapping aggregates, freshness,
status counts, calendar mapping status counts, and sanitized run counters. It
intentionally excludes external provider IDs, provider metadata, event titles,
calendar and Outlook IDs, error messages, raw responses, and URLs. Review the
output before copying it outside staging.

## Stage 1: Isolation, startup, and persistence

1. Freeze staging to the reviewed candidate commit or tag. Confirm production
   does not track `develop` and is not changed by this procedure.
2. Run `docker compose config --quiet`, deploy one staging instance, and verify
   it becomes healthy.
3. Confirm startup validates the expected calendar name and immutable ID before
   the scheduler starts. Neither identifier may appear in mismatch diagnostics.
4. Confirm logs identify `football_data` as the sole authoritative assignment
   for `premier_league` / `2026_27`, without credentials or URLs.
5. Run the evidence command. Expect one active authoritative assignment with
   source key `football_data`, role `authoritative`, and the configured interval.
6. Restart the container normally. Confirm `database_quick_check` remains `ok`,
   `startup_records` increases, and prior fixtures, mappings, and runs persist.

## Stage 2: Complete import and independent Outlook synchronization

1. Record only the non-identifying provider quota count before the cycle. Quota
   headers may be unavailable and are not required evidence.
2. Observe one complete scheduled provider cycle.
3. Verify the provider validates competition code `PL`, competition ID `2021`,
   season start `2026-08-21`, season end `2027-05-30`, 20 teams, 380 matches,
   380 unique match IDs, known statuses, and timezone-aware UTC kickoffs before
   committing the snapshot.
4. Run the evidence command. Expect 380 active fixtures, 380 source event
   mappings, the expected kickoff range, current provider freshness, and status
   counts totaling 380.
5. Verify a completed `provider_import` run precedes a separate
   `calendar_sync` run on the initial startup. The first calendar batch may
   consume newly imported provider data only after the complete snapshot is
   committed. Later calendar jobs remain independent of provider outcomes.
6. Verify created items appear only in the dedicated staging calendar and carry
   the expected Premier League content.
7. Review application and Portainer logs for tokens, secrets, authorization
   headers, raw payloads, tenant/calendar IDs, and secret-bearing URLs. None may
   be present.

Stop and disable `FOOTBALL_DATA_ENABLED` if collection is empty, partial,
malformed, stale, outside the intended scope, or unexpectedly quota-intensive.
The failed collection must not change the last-known-good snapshot or produce
removal evidence. An independently due calendar job may revalidate the existing
canonical state, but it must not issue an unnecessary Graph write.

## Stage 3: Unchanged-cycle idempotency

Observe a second complete snapshot without source changes and verify:

- fixture count and source mapping count remain 380;
- stable external identity correlates to the existing canonical fixtures;
- provider counters report unchanged items instead of creates or updates;
- no duplicate fixture, participant, source mapping, calendar mapping, or
  Outlook event is created; and
- no unnecessary Graph update is issued.

A naturally observed kickoff correction, postponement, cancellation, or other
lifecycle transition may be recorded, but must not be manufactured or awaited
as a release gate. Stable identity and explicit Outlook operations for
unobserved lifecycle cases are covered by deterministic tests.

## Stage 4: Controlled recovery

Perform these exercises only against staging:

1. Temporarily deny the staging container's outbound connection to
   `api.football-data.org` using the operator-controlled staging network. Do not
   alter or expose the token and do not send artificial traffic to the provider.
2. Observe one failed provider cycle. Verify it produces no canonical mutation
   or removal evidence and the last-known-good 380 fixtures remain active. A
   separately due calendar cycle is expected to remain operational; it must
   report unchanged decisions and issue no Graph create, update, or delete.
3. Restore staging egress and observe the next successful cycle. Verify it
   converges without duplicates or unnecessary Graph writes.
4. Stop and restart the container during the controlled validation window.
   Verify graceful shutdown, persisted run history, and deterministic recovery
   on startup. Interrupted-run state that cannot be safely produced live remains
   covered by the automated recovery tests.
5. Restore the verified backup into a new, isolated temporary validation volume
   with Graph/provider execution disabled. Run the evidence command, verify the
   database and expected counters, then retire that temporary validation stack.
   Never restore over production or connect the restored copy to a calendar.

## Evidence record for issue #63

Record observations, not configuration. Use `pass`, `fail`, or `skipped` with a
specific deterministic-test justification. Never include environment values,
raw headers, tokens, secrets, tenant/mailbox/calendar/application IDs, provider
external IDs, raw payloads, full URLs, screenshots containing identifiers, or
error text that has not been sanitized.

```markdown
### Staging live-validation record

- Candidate commit/tag: `<public Git reference>`
- Validation window (UTC): `<start>` to `<end>`
- Stack and production isolation: `<result>`
- Graph startup and staging-calendar target: `<result>`
- Sole authoritative source assignment: `<result>`
- SQLite restart persistence: `<result>`
- Complete 20-team / 380-fixture import: `<result>`
- Independent calendar scheduling and first-import ordering: `<result>`
- Second-cycle idempotency: `<result>`
- Controlled transient-failure recovery: `<result>`
- Restart/interrupted-run recovery: `<result>`
- Isolated backup and restore: `<result>`
- Provider quota before/after: `<non-identifying counts or unavailable>`
- Attribution and retention review: `<result>`
- Secret review: `<result>`
- Deterministic lifecycle tests used for skipped observations: `<tests>`
- Follow-up issues: `<numbers or none>`

#### Secret-safe database evidence

`<paste reviewed output from app.operations.staging_evidence>`
```

Issue #63 is complete only after the sanitized record is attached, every
failure has a follow-up issue, and the acceptance criteria are updated. A
successful staging record does not permit an automatic production update.
