# Deployment Guide

This document describes how to build, deploy, and maintain the SMART Sports Calendar application.

---

## Architecture

The application is designed to run as a Docker container.

```text
GitHub Repository
        │
        ▼
Docker Build
        │
        ▼
Docker Image
        │
        ▼
Portainer Stack
        │
        ▼
Persistent Docker Volume
        │
        ▼
SQLite Database
```

---

## Repository

The project is deployed directly from the Git repository.

Current development branch:

```text
develop
```

Release deployments use a reviewed commit from:

```text
main
```

Alpha versions are published as GitHub pre-releases with an immutable version
tag. The current Compose file builds the image from the checked-out source.
Publishing and pulling images through GitHub Container Registry (GHCR) is not
implemented yet.

---

## Local Development

### Build

```bash
docker compose build
```

### Start

```bash
docker compose up
```

or

```bash
docker compose up -d
```

### Show running containers

```bash
docker compose ps
```

### View local logs

```bash
docker compose logs -f
```

### Stop

```bash
docker compose down
```

The command above **does not delete** persistent data.

### Scheduled API-Football imports

API-Football is opt-in. Configure these values through the deployment secret
store or Portainer environment; never commit a real key:

```env
API_FOOTBALL_ENABLED=true
API_FOOTBALL_API_KEY=replace-with-deployment-secret
API_FOOTBALL_IMPORT_INTERVAL_SECONDS=3600
SOURCE_JOBS_JSON=[{"job_key":"api-football-premier-league","source_key":"api_football","sport_key":"football","competition_key":"premier_league","season_key":"2026_27","role":"authoritative","interval_seconds":3600}]
```

The complete provider settings are:

| Setting | Default | Validation and purpose |
| --- | --- | --- |
| `API_FOOTBALL_ENABLED` | `false` | Explicit opt-in; accepts the documented boolean values |
| `API_FOOTBALL_API_KEY` | empty | Required only when the provider is enabled; supplied through the deployment secret store |
| `API_FOOTBALL_BASE_URL` | API-Football v3 HTTPS URL | HTTPS only; credentials, query strings, and fragments are rejected |
| `API_FOOTBALL_CONNECT_TIMEOUT_SECONDS` | `5` | Positive finite connection timeout |
| `API_FOOTBALL_READ_TIMEOUT_SECONDS` | `30` | Positive finite response timeout |
| `API_FOOTBALL_MAX_ATTEMPTS` | `3` | Positive integer, maximum `10` |
| `API_FOOTBALL_RETRY_BASE_DELAY_SECONDS` | `1` | Positive finite first backoff delay |
| `API_FOOTBALL_RETRY_MAX_DELAY_SECONDS` | `30` | Positive finite cap, not lower than the base delay |
| `API_FOOTBALL_IMPORT_INTERVAL_SECONDS` | `3600` | Legacy positive provider interval; an explicit source job's `interval_seconds` is authoritative |
| `SOURCE_JOBS_JSON` | `[]` | Provider-neutral job array; every active competition/season scope requires exactly one authority and every enabled adapter requires a matching job |
| `FOOTBALL_DATA_ENABLED` | `false` | Enables the approved API v4 Premier League/Bundesliga adapter; requires at least one matching authoritative job |
| `FOOTBALL_DATA_API_KEY` | empty | Secret API token; required only when enabled and never stored in Git |
| `FOOTBALL_DATA_BASE_URL` | `https://api.football-data.org` | HTTPS-only provider origin without credentials, query, or fragment |
| `FOOTBALL_DATA_MAX_ATTEMPTS` | `3` | Bounded transient retry count, maximum `10` |
| `FOOTBALL_DATA_REQUESTS_PER_MINUTE` | `10` | Must not exceed the approved free-plan limit |
| `FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS` | `6.1` | Enforces the configured per-minute request budget |
| `OPENLIGADB_ENABLED` | `false` | Enables the public API v1 DFB-Pokal and/or 2. Bundesliga adapters; requires at least one matching authoritative job |
| `OPENLIGADB_BASE_URL` | `https://api.openligadb.de` | HTTPS-only public provider origin without credentials, query, or fragment |
| `OPENLIGADB_CONNECT_TIMEOUT_SECONDS` | `5` | Positive finite connection timeout |
| `OPENLIGADB_READ_TIMEOUT_SECONDS` | `30` | Positive finite response timeout |
| `OPENLIGADB_MAX_ATTEMPTS` | `3` | Bounded transient retry count, maximum `10` |
| `OPENLIGADB_RETRY_BASE_DELAY_SECONDS` | `1` | Positive finite first backoff delay |
| `OPENLIGADB_RETRY_MAX_DELAY_SECONDS` | `30` | Positive finite cap, not lower than the base delay |
| `OPENLIGADB_MINIMUM_REQUEST_INTERVAL_SECONDS` | `1` | Positive minimum spacing between public provider requests |
| `OEFB_ICAL_ENABLED` | `false` | Enables the private official ÖFB-Cup iCalendar authority; requires its matching authoritative job |
| `OEFB_ICAL_FEED_URL` | empty | Required only when enabled; opaque HTTPS subscription URL supplied through the deployment secret store and never logged |
| `OEFB_ICAL_CONNECT_TIMEOUT_SECONDS` | `5` | Positive finite connection timeout |
| `OEFB_ICAL_READ_TIMEOUT_SECONDS` | `30` | Positive finite response timeout |
| `OEFB_ICAL_MAX_ATTEMPTS` | `3` | Bounded transient retry count, maximum `10` |
| `OEFB_ICAL_RETRY_BASE_DELAY_SECONDS` | `1` | Positive finite first backoff delay |
| `OEFB_ICAL_RETRY_MAX_DELAY_SECONDS` | `30` | Positive finite cap, not lower than the base delay |
| `OEFB_ICAL_MINIMUM_POLL_INTERVAL_SECONDS` | `21600` | Minimum six-hour poll interval required by the qualified feed contract |

The JSON value must remain on one line in `.env` or Portainer. Adapter and job
enablement must agree. The existing API-Football adapter supports only the
`authoritative` role because it writes canonical data. `football_data` supports
the authoritative 2026/27 Premier League and Bundesliga complete-season scopes
and the Championship `REGULAR_SEASON` complete-stage scope. `openligadb`
supports the authoritative 2026/27 DFB-Pokal and 2. Bundesliga scopes and
requires no credential. `oefb_ical` supports only the private, permanently
partial 2026/27 ÖFB-Cup scope and never derives removal evidence from absence.
Keep the football-data.org token and opaque ÖFB feed URL in Portainer or another
ignored operator secret store. See
[source orchestration](source-orchestration.md).

`OUTLOOK_CALENDAR_ID` is required for every Graph write. It must be the
immutable Graph ID of the dedicated SMART Sports Calendar.
`OUTLOOK_CALENDAR_NAME` is used by startup validation and must resolve to that
same calendar. Do not target a general-purpose personal calendar.

### Application and Microsoft Graph configuration

| Setting | Default | Validation and purpose |
| --- | --- | --- |
| `TZ` | `Europe/Vienna` in Compose | Operational container timezone; canonical fixture timestamps remain UTC |
| `DATABASE_PATH` | `/data/sports.db` | SQLite file inside the persistent volume |
| `LOG_LEVEL` | `INFO` | Python logging level; never use logs to expose configuration secrets |
| `HEARTBEAT_INTERVAL` | `300` | Positive interval for the independent Outlook calendar synchronization job |
| `M365_TENANT_ID` | none | Required deployment secret/reference for Graph authentication |
| `M365_CLIENT_ID` | none | Required deployment secret/reference for Graph authentication |
| `M365_CLIENT_SECRET` | none | Required secret; never commit or print it |
| `M365_USER_ID` | none | Required target mailbox identifier |
| `OUTLOOK_CALENDAR_NAME` | `SMART Sports Calendar` | Startup reachability lookup; must identify the dedicated target calendar |
| `OUTLOOK_CALENDAR_ID` | none | Required immutable Graph calendar ID used by synchronization writes |
| `SYNCHRONIZATION_BATCH_LIMIT` | `100` | Positive maximum per run; unmapped, retry/lifecycle, and revision-pending work runs first, then synced mappings rotate oldest-synchronized-first |
| `GRAPH_BASE_URL` | Microsoft Graph v1.0 | Graph API root; use the documented production endpoint unless testing an isolated mock |
| `GRAPH_STARTUP_VALIDATION_ENABLED` | `true` | Boolean; keep enabled for deployed environments |

All settings are external. `.env.example` contains placeholders only. Use a
local ignored `.env` file or Portainer secret/environment configuration for
real values. The image must never contain credentials.

Each enabled source job imports its configured scope at its own
`SOURCE_JOBS_JSON.interval_seconds`. Outlook synchronization is a separate job
that runs every `HEARTBEAT_INTERVAL`, including while providers are enabled.
At startup, configured source jobs are ordered before the first calendar job;
later calendar batches continue independently without unnecessary provider
requests.

Provider-import and calendar-sync outcomes are stored separately in
`sync_runs`. The runtime lock is process-local, so deploy only one application
instance for a shared SQLite database and Outlook calendar.

---

## Persistent Storage

Application data is stored inside the Compose logical volume

```text
smart_sports_data
```

For multi-instance deployments, Docker prefixes the actual volume with the
Compose project or Portainer stack name. Examples:

```text
smart-calendar-staging_smart_sports_data
smart-calendar-prod_smart_sports_data
```

The released `v0.4.0-alpha.1` used the legacy unscoped physical volume name
`smart_sports_data`. Preserve that volume during upgrade and follow an explicit
backup/migration decision; do not attach it to staging and production at the
same time.

The SQLite database is located inside the container at

```text
/data/sports.db
```

Removing the container does **not** remove the database.

Only the following command removes persistent data:

```bash
docker compose down --volumes
```

This command should only be used when a complete reset is intended.

### Backup before upgrade

Stop the service before copying SQLite so the backup is transactionally
consistent:

```bash
mkdir -p backups
docker compose stop calendar-sync
docker run --rm \
    -v smart_sports_data:/data:ro \
    -v "$PWD/backups:/backup" \
    alpine:3.21 \
    cp /data/sports.db /backup/sports-pre-v0.4.0-alpha.1.db
docker compose start calendar-sync
```

Store the backup outside the Docker volume and verify that the copied file is
non-empty. Never use `docker compose down --volumes` during an upgrade.

### Upgrade to v0.4.0-alpha.1

1. Back up `/data/sports.db` using the stopped-container procedure above.
2. Review `.env` against `.env.example` without replacing real secrets with
   placeholders.
3. Keep `API_FOOTBALL_ENABLED=false` for the first upgraded startup.
4. Check out the reviewed `v0.4.0-alpha.1` tag after the pre-release exists.
5. Run `docker compose config --quiet` and resolve every missing-variable
   warning.
6. Run `docker compose up -d --build`.
7. Verify `docker compose ps` reports `healthy` and inspect startup logs.
8. Confirm migrations and canonical initialization completed without errors.
9. Complete the manual Graph validation, then the provider validation in
   [`phase-4-live-validation.md`](phase-4-live-validation.md).

Database initialization and forward migrations are idempotent. Schema
downgrades are not implemented.

### Upgrade from v0.4.5-beta.1 to v0.5.0-beta.1

1. Stop the exact application stack and create a transactionally consistent
   backup of its project-scoped `/data/sports.db` volume.
2. Verify the backup is non-empty and keep it outside the Docker volume.
3. Review `.env.example` and add only the provider settings required by the
   approved competition jobs. Never replace existing secrets with placeholders.
4. Keep every new provider disabled until its exact `SOURCE_JOBS_JSON`
   authority, catalog, season, and secret configuration is ready.
5. Check out the verified signed `v0.5.0-beta.1` tag.
6. Run `docker compose config --quiet` and resolve every missing or invalid
   setting before starting the container.
7. Run `docker compose up --detach --build` for exactly one instance attached to
   the existing project-scoped volume and Outlook calendar.
8. Verify startup health and confirm migration
   `008_add_calendar_sync_revisions` completes without error.
9. Allow bounded Outlook synchronization batches to drain every pending
   calendar revision. A temporary revision backlog after migration is expected;
   creates, updates, and lifecycle work are prioritized before unchanged rows.
10. Run the secret-safe staging evidence command and verify zero pending
    calendar mapping revisions before enabling production promotion.

The Phase 5 catalog and source assignments initialize idempotently. Migration
`008_add_calendar_sync_revisions` preserves existing events and mappings while
queueing them for one safe payload-revision reconciliation. Do not downgrade an
upgraded database in place.

### Rollback

Prefer a forward fix when the upgraded database is healthy. Running older code
against a newer schema is not a supported downgrade path.

If a full rollback is required:

1. stop the application;
2. preserve a separate copy of the current database for investigation;
3. restore the verified pre-upgrade database backup into the named volume;
4. restore the previously released source tag;
5. start exactly one instance and verify health, logs, and calendar targeting.

Restoring a backup discards all state recorded after that backup, including
fixture observations, mappings, and run history. Do not perform it without an
explicit operational decision.

---

## Portainer Deployment

Deployment is performed directly from Git.

### Released alpha single-instance limitation

The released `v0.4.0-alpha.1` Compose definition has fixed container and volume
names and supports only one deployment on a Docker host. The current
development Compose definition removes those conflicts for the target
`v0.4.5-beta.1`. Do not use the new multi-instance procedure with the old alpha
tag.

Never work around an old release conflict by pointing two containers at the
same SQLite volume or Outlook calendar.

### Multiple Instances

The current development Compose definition scopes generated container,
image, network, and volume names through the Compose project name. Portainer
uses the stack name as that project boundary.

| Setting | Staging | Production |
| --- | --- | --- |
| Portainer stack | `smart-calendar-staging` | `smart-calendar-prod` |
| Source | `develop` during normal development | approved immutable release tag |
| GitOps updates | enabled | disabled |
| Deployment action | automatic | explicit manual promotion |
| SQLite storage | dedicated staging volume | dedicated production volume |
| Outlook target | dedicated non-production calendar | dedicated production calendar |
| Secrets | staging-only Portainer configuration | production-only Portainer configuration |
| Logs | staging container stream | production container stream |

Staging and production must not share writable storage, a database, an Outlook
calendar, or secret configuration. The runtime lock is process-local and does
not make shared state safe.

Use lowercase instance identifiers containing letters, digits, hyphens, or
underscores. The identifier appears in the application logger name and a
non-secret Docker label. It does not replace the Portainer stack name.

For a local staging example:

```bash
INSTANCE_NAME=staging IMAGE_TAG=develop \
  docker compose --project-name smart-calendar-staging up --detach --build
```

For a PowerShell staging example:

```powershell
$env:INSTANCE_NAME = "staging"
$env:IMAGE_TAG = "develop"
docker compose --project-name smart-calendar-staging up --detach --build
```

The resulting resources include:

```text
smart-calendar-staging-calendar-sync-1
smart-calendar-staging-calendar-sync:develop
smart-calendar-staging_default
smart-calendar-staging_smart_sports_data
```

Validate three rendered project configurations without starting containers:

```bash
python scripts/validate_multi_instance.py --config-only
```

With a running Docker daemon, execute the complete credential-free acceptance
test:

```bash
python scripts/validate_multi_instance.py
```

The complete test starts three project-scoped probe containers concurrently,
verifies their images, networks, volumes, SQLite data, and logs, and removes
only those test stacks and test volumes afterward. The probe override performs
no Microsoft Graph or provider calls.

Use `smart-calendar-prod` and an approved immutable release value for
`IMAGE_TAG` in production. The source checkout must be pinned to the same tag;
`IMAGE_TAG` labels the locally built project image but does not select Git
source by itself.

During release-candidate qualification, freeze staging to the immutable
candidate tag. Resume automatic `develop` updates only after qualification is
finished. Production must never track `develop`.

For `v0.4.5-beta.1`, publishing the GitHub pre-release and manually promoting
it to production are separate decisions. The pre-release may be qualified in
isolated staging, but production promotion remains blocked until the deferred
controlled provider-failure exercise in issue #101 is complete.

The implementation and remaining live-validation order is documented in
[`v0.4-stabilization-roadmap.md`](v0.4-stabilization-roadmap.md).

### Portainer source configuration

Staging configuration:

| Setting | Value |
| ---------- | ------- |
| Build Method | Repository |
| Branch or tag | `develop` during normal development |
| Compose File | `docker-compose.yml` |
| Authentication | GitHub Personal Access Token |
| GitOps Updates | Enabled |
| Stack name | `smart-calendar-staging` |
| `INSTANCE_NAME` | `staging` |
| `IMAGE_TAG` | `develop` |

Production configuration:

| Setting | Value |
| ---------- | ------- |
| Build Method | Repository |
| Branch or tag | approved immutable release tag |
| Compose File | `docker-compose.yml` |
| Authentication | GitHub Personal Access Token |
| GitOps Updates | Disabled |
| Stack name | `smart-calendar-prod` |
| `INSTANCE_NAME` | `prod` |
| `IMAGE_TAG` | approved immutable release tag |

Portainer clones the repository and builds the application locally using the provided Dockerfile.

---

## Container Security

The application intentionally **does not run as root**.

Container user:

```text
UID: 10001
GID: 10001
```

This follows Docker security best practices and limits the impact of a potential container compromise.

---

## Existing Volumes

When migrating from an older container that was running as root, the database volume may still belong to the root user.

Typical error:

```text
sqlite3.OperationalError: attempt to write a readonly database
```

To fix ownership:

```bash
docker run --rm \
    -v smart-calendar-prod_smart_sports_data:/data \
    alpine:latest \
    chown -R 10001:10001 /data
```

Replace the example with the exact project-scoped volume reported for the
affected stack. The legacy alpha deployment uses `smart_sports_data`.

Restart the container afterwards.

---

## Health Check

The application exposes a Docker health check.

Verify:

```bash
docker compose ps
```

Expected:

```text
healthy
```

---

## Logs

Application logs are written to standard output.

View logs:

```bash
docker compose logs -f
```

or through Portainer:

```text
Stacks
→ smart-calendar-staging or smart-calendar-prod
→ calendar-sync container
→ Logs
```

No dedicated log volume is used.

### Secret-safe staging evidence

For issue #63, open the `calendar-sync` container console for
`smart-calendar-staging` and run:

```bash
python -m app.operations.staging_evidence --database /data/sports.db
```

For the Phase 5 six-authority candidate, follow
[`phase-5-multi-competition-staging-validation.md`](phase-5-multi-competition-staging-validation.md)
and run the strict read-only profile after convergence:

```bash
python -m app.operations.staging_evidence --database /data/sports.db --limit 50 --validate-phase-5-candidate
```

The command opens SQLite in read-only mode and reports only database integrity,
schema version, startup count, public authoritative source/scope keys, fixture
and source-mapping aggregates, kickoff range, source freshness, normalized
status counts, calendar-mapping status counts, revision-pending mapping counts,
and recent synchronization counters. Strict validation requires the persisted
event and calendar revisions to be fully converged. It deliberately omits
configuration, provider external IDs, event
details, error messages, metadata, calendar IDs, Outlook IDs, raw responses,
and source URLs. Review the output before adding it to sanitized GitHub
evidence.

Do not replace this with `env`, `docker inspect`, a raw database dump, or
`SELECT *` output. Those sources may disclose deployment or tenant data.

---

## Updating the Application

Current workflow:

```text
VS Code
        │
        ▼
develop branch
        │
        ▼
Git Push
        │
        ▼
Portainer Git Stack
        │
        ▼
Docker Build
        │
        ▼
Container Restart
```

---

## Release Workflow

The source and release workflow is:

```text
VS Code
        │
        ▼
develop
        │
        ▼
Pull Request
        │
        ▼
main
        │
        ▼
Git Tag
        │
        ▼
GitHub Release
        │
        ▼
Portainer source build
        │
        ▼
Immutable beta staging qualification
        │
        ▼
Controlled manual production promotion
```

The release branch is created from fully validated `develop`, reviewed back
into `develop`, and followed by a final verified `develop` to `main` pull
request. The resulting `main` commit is signed-tagged and GitHub Releases
publishes the release notes as a pre-release. Staging can then be frozen to the
immutable tag for final operational confirmation. Production promotion is a
separate explicit manual decision and is never implied by tag or pre-release
publication. GHCR remains a future enhancement; do not document or deploy a
registry image that has not been built and verified.

---

## Troubleshooting

### Verify Docker configuration

```bash
docker compose config
```

### Verify running containers

```bash
docker ps
```

### Inspect container logs

```bash
docker compose logs -f
```

### Restart container

```bash
docker compose restart
```

### Provider or synchronization failure

Check logs and the separate `provider_import` and `calendar_sync` records in
`sync_runs`. Provider configuration, authentication, authorization, timeout,
network, rate-limit, server, request, schema, resolution, pagination, partial
fetch, and integrity failures remain distinct. A failed or partial provider
collection does not provide removal evidence and does not start Outlook
synchronization.

HTTP 429 and retryable transport/server failures use bounded attempts and
respect available retry guidance. Do not respond by starting overlapping
manual instances. Correct the cause and allow the next scheduled cycle, or
restart the single instance after verifying no run remains active.

Never paste API keys, client secrets, tokens, authorization headers, or full
secret-bearing URLs into logs, issues, or validation evidence.

### Check persistent volumes

```bash
docker volume ls
```

### Inspect the application volume

```bash
docker volume inspect smart-calendar-prod_smart_sports_data
```

---

## Current Status

| Component | Status |
| ----------- | -------- |
| GitHub Repository | ✅ |
| Develop Branch | ✅ |
| Dockerfile | ✅ |
| Docker Compose | ✅ |
| Local Build | ✅ |
| Portainer Git Deployment | ✅ |
| Concurrent Staging and Production | Implemented; live Portainer validation pending |
| SQLite Persistence | ✅ |
| Health Check | ✅ |
| Non-root Container | ✅ |
| GitHub Releases | Implemented for versioned pre-releases |
| GitHub Actions | Implemented |
| GitHub Container Registry | Planned |
