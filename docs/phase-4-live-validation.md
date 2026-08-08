# Phase 4 Manual Live Validation

## Purpose and safety boundary

This checklist validates the Phase 4 release candidate against a real
API-Football subscription and a dedicated Microsoft 365 calendar. It is an
explicit, operator-run activity. It is not executed by pytest or GitHub
Actions and must never place credentials or tenant-specific identifiers in the
repository, logs, screenshots, issues, or test fixtures.

The deterministic automated suite remains the reproducible release gate. Live
validation adds environment confidence but does not replace those tests.

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
   to the same dedicated calendar before enabling provider imports.

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
