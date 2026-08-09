# Legacy Phase 4 API-Football Manual Live Validation

> This runbook records the API-Football validation procedure designed for the
> released `v0.4.0-alpha.1` implementation. It is not the release gate for
> `v0.4.5-beta.1`. Master issue #72 requires a replacement authoritative-source
> staging procedure before #63 can be completed.

Issue #73 rejected the ECAL-delivered Premier League calendar for automated
server retrieval under its current public end-user terms. This legacy runbook
must not be adapted by substituting a personalized ECAL URL. Issue #63 remains
blocked until a permitted authoritative source passes qualification and its
source-specific, secret-safe staging procedure is reviewed.

The replacement procedure must prove, at minimum:

- the deployed source is the single configured Premier League authority;
- a complete real current-season collection is committed before Outlook handoff;
- stable external identity survives an unchanged second cycle and a naturally
  observed correction or reschedule when available;
- malformed, partial, empty, stale, or failed collection retains last-known-good
  state and produces neither Outlook writes nor removal evidence;
- provider credentials or secret-bearing URLs are absent from logs, database
  evidence, screenshots, issues, and pull requests;
- source attribution and retention obligations are satisfied in the deployed
  application; and
- disabling or losing the source cannot silently promote a fallback writer.

## Purpose and safety boundary

This checklist validates the Phase 4 release candidate against a real
API-Football subscription and a dedicated Microsoft 365 calendar. It is an
explicit, operator-run activity. It is not executed by pytest or GitHub
Actions and must never place credentials or tenant-specific identifiers in the
repository, logs, screenshots, issues, or test fixtures.

The deterministic automated suite remains the reproducible release gate. Live
validation adds environment confidence but does not replace those tests.

The application image includes a read-only evidence command that intentionally
excludes error messages, metadata, event details, calendar identifiers,
Outlook identifiers, and provider identifiers:

```bash
python -m app.operations.staging_evidence --database /data/sports.db
```

Use this command for database evidence instead of ad-hoc `SELECT *` queries.
Review its output before copying it outside the staging environment.

If this legacy procedure is used for diagnostic comparison, it is executed only
in the isolated staging environment tracked by
[issue #63](https://github.com/theMompfdie/smart-sports-calendar/issues/63) and
does not qualify `v0.4.5-beta.1`.
The multi-instance implementation in
[issue #2](https://github.com/theMompfdie/smart-sports-calendar/issues/2) must
be complete before staging and production run concurrently on one Docker host.
Production promotion is a separate manual decision tracked by issue #64; a
successful staging run does not authorize an automatic production update.

## Prerequisites

- Use a controlled non-critical Microsoft 365 mailbox and a dedicated SMART
  Sports Calendar.
- Grant only the Graph application permissions already required by the
  deployment; do not broaden permissions for convenience.
- Obtain the immutable Graph ID for that dedicated calendar.
- Use an API-Football key whose subscription covers the selected Premier
  League season and has enough remaining quota for the validation window.
- Back up the persistent SQLite database and verify the backup.
- Ensure exactly one application instance can access the database and target
  calendar.
- Start from the reviewed Phase 4 release candidate and a clean deployment
  configuration.
- Confirm the staging stack, SQLite volume, calendar, credentials, and logs are
  distinct from production.
- Confirm production GitOps updates are disabled.

## Secret-safe configuration

Set real values only in the local secret store, `.env` file excluded by Git,
or Portainer secret/environment configuration:

```env
M365_TENANT_ID=<deployment-secret>
M365_CLIENT_ID=<deployment-secret>
M365_CLIENT_SECRET=<deployment-secret>
M365_USER_ID=<target-mailbox>
OUTLOOK_CALENDAR_NAME=SMART Sports Calendar
OUTLOOK_CALENDAR_ID=<dedicated-calendar-id>
GRAPH_STARTUP_VALIDATION_ENABLED=true
API_FOOTBALL_ENABLED=false
API_FOOTBALL_API_KEY=<deployment-secret>
API_FOOTBALL_IMPORT_INTERVAL_SECONDS=3600
```

Confirm `.env` is ignored by Git before inserting values:

```bash
git check-ignore .env
```

Do not print the effective environment or use shell tracing while secrets are
loaded.

## Stage 1: Graph and persistence validation

1. Keep `API_FOOTBALL_ENABLED=false`.
2. Run `docker compose config --quiet` and start the single application
   instance.
3. Confirm the container becomes healthy.
4. Confirm startup logs report successful Graph authentication and the expected
   calendar name without exposing a token, secret, or authorization header.
5. Confirm the SQLite database remains in the persistent volume after a normal
   container restart.
6. Confirm the configured calendar ID and startup-validated calendar name refer
   to the same dedicated calendar before enabling provider imports. Startup
   must fail before the scheduler runs when the ID does not match the calendar
   resolved by name; neither ID may appear in the mismatch diagnostic.
7. Run the secret-safe evidence command before and after the restart. Confirm
   that `startup_records` increases while existing run and fixture counters
   remain available and `database_quick_check` remains `ok`.

Stop if authentication, calendar targeting, storage ownership, migrations, or
secret hygiene is incorrect.

## Stage 2: Provider import and Outlook handoff

1. Record the provider quota outside the repository without recording the API
   key.
2. Set `API_FOOTBALL_ENABLED=true` and restart the application.
3. Observe one complete scheduled cycle.
4. Verify a completed `provider_import` run exists with competition, season,
   authoritative scope, counters, attempt data, and available rate-limit
   diagnostics.
5. Verify a separate `calendar_sync` run starts only after the provider import
   completes successfully.
6. Verify created Outlook items appear only in the configured dedicated
   calendar and contain the expected Premier League fixture data.
7. Confirm logs and persisted metadata contain no API key, Graph token, client
   secret, authorization header, or secret-bearing URL.
8. Capture the evidence command output. Do not supplement it with raw
   `metadata_json`, `error_message`, calendar mapping, or provider response
   fields.

Stop the provider by setting `API_FOOTBALL_ENABLED=false` if the collection is
partial, malformed, outside the intended competition/season, or unexpectedly
quota-intensive.

## Stage 3: Idempotency and lifecycle observations

Allow a second unchanged complete cycle and verify:

- no duplicate canonical fixture, source mapping, participant, calendar
  mapping, or Outlook item is created;
- unchanged items do not produce unnecessary Graph updates; and
- run counters distinguish unchanged items from creates and updates.

When the provider naturally reports a new fixture, kickoff change,
postponement, cancellation, or correction, verify that the existing stable
identity is retained and the documented explicit Outlook operation occurs. Do
not manipulate provider data or wait for a specific real-world lifecycle event
as a release gate; deterministic coverage for all lifecycle transitions exists
in the automated suite.

## Stage 4: Recovery validation

Use only a controlled environment. Do not manufacture failures against a
production calendar.

- After a transient connectivity or provider failure, verify the failure
  category is safe and the next successful cycle converges without duplicates.
- Verify a failed provider collection creates no Outlook handoff and no removal
  evidence.
- Verify a Graph failure leaves the completed provider import intact and a
  later synchronization retry converges.
- Verify SIGTERM or a normal container stop produces graceful shutdown logs and
  the next startup recovers any interrupted run record.

## Evidence record

Record only:

- release candidate commit or tag;
- UTC validation time;
- pass/fail for each stage;
- sanitized run IDs and decision counters;
- observed provider and calendar operation categories;
- quota numbers that contain no account identity; and
- follow-up issue numbers for defects.

Never record configuration values, raw headers, access tokens, API keys, client
secrets, tenant IDs, mailbox addresses, calendar IDs, or full request URLs.

Live validation is complete when all applicable stages pass or every skipped
observation is explicitly justified by deterministic automated coverage.

## Portainer execution record

Record the following checklist in issue #63. Use `pass`, `fail`, or `skipped`
with a justification; never paste Portainer environment values.

```markdown
### Staging live-validation record

- Candidate commit/tag: `<public Git reference>`
- Validation window (UTC): `<start>` to `<end>`
- Stack isolation: `<result>`
- Graph startup and calendar target: `<result>`
- SQLite restart persistence: `<result>`
- Provider import and separate Outlook handoff: `<result>`
- Second-cycle idempotency: `<result>`
- Controlled transient-failure recovery: `<result>`
- Interrupted-run recovery: `<result>`
- Backup and restore: `<result>`
- Provider quota before/after: `<non-identifying counts>`
- Secret review: `<result>`
- Follow-up issues: `<numbers or none>`

#### Secret-safe database evidence

`<paste reviewed output from app.operations.staging_evidence>`
```

The record documents observations, not configuration. Keep mailbox, tenant,
calendar, application-registration, and Portainer endpoint identifiers out of
the record even if they do not currently look sensitive.
