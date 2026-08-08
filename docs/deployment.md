# Deployment Guide

This document describes how to build, deploy, and maintain the SMART Sports Calendar application.

---

# Architecture

The application is designed to run as a Docker container.

```
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

# Repository

The project is deployed directly from the Git repository.

Current development branch:

```
develop
```

Release deployments use a reviewed commit from:

```
main
```

Alpha versions are published as GitHub pre-releases with an immutable version
tag. The current Compose file builds the image from the checked-out source.
Publishing and pulling images through GitHub Container Registry (GHCR) is not
implemented yet.

---

# Local Development

## Build

```bash
docker compose build
```

## Start

```bash
docker compose up
```

or

```bash
docker compose up -d
```

## Show running containers

```bash
docker compose ps
```

## View logs

```bash
docker compose logs -f
```

## Stop

```bash
docker compose down
```

The command above **does not delete** persistent data.

## Scheduled API-Football imports

API-Football is opt-in. Configure these values through the deployment secret
store or Portainer environment; never commit a real key:

```env
API_FOOTBALL_ENABLED=true
API_FOOTBALL_API_KEY=replace-with-deployment-secret
API_FOOTBALL_IMPORT_INTERVAL_SECONDS=3600
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
| `API_FOOTBALL_IMPORT_INTERVAL_SECONDS` | `3600` | Positive integer scheduler interval while the provider is enabled |

`OUTLOOK_CALENDAR_ID` is required for every Graph write. It must be the
immutable Graph ID of the dedicated SMART Sports Calendar.
`OUTLOOK_CALENDAR_NAME` is used by startup validation and must resolve to that
same calendar. Do not target a general-purpose personal calendar.

## Application and Microsoft Graph configuration

| Setting | Default | Validation and purpose |
| --- | --- | --- |
| `TZ` | `Europe/Vienna` in Compose | Operational container timezone; canonical fixture timestamps remain UTC |
| `DATABASE_PATH` | `/data/sports.db` | SQLite file inside the persistent volume |
| `LOG_LEVEL` | `INFO` | Python logging level; never use logs to expose configuration secrets |
| `HEARTBEAT_INTERVAL` | `300` | Positive integer calendar-only interval while API-Football is disabled |
| `M365_TENANT_ID` | none | Required deployment secret/reference for Graph authentication |
| `M365_CLIENT_ID` | none | Required deployment secret/reference for Graph authentication |
| `M365_CLIENT_SECRET` | none | Required secret; never commit or print it |
| `M365_USER_ID` | none | Required target mailbox identifier |
| `OUTLOOK_CALENDAR_NAME` | `SMART Sports Calendar` | Startup reachability lookup; must identify the dedicated target calendar |
| `OUTLOOK_CALENDAR_ID` | none | Required immutable Graph calendar ID used by synchronization writes |
| `SYNCHRONIZATION_BATCH_LIMIT` | `100` | Positive integer maximum events processed per calendar run |
| `GRAPH_BASE_URL` | Microsoft Graph v1.0 | Graph API root; use the documented production endpoint unless testing an isolated mock |
| `GRAPH_STARTUP_VALIDATION_ENABLED` | `true` | Boolean; keep enabled for deployed environments |

All settings are external. `.env.example` contains placeholders only. Use a
local ignored `.env` file or Portainer secret/environment configuration for
real values. The image must never contain credentials.

When enabled, every interval performs a complete current Premier League import
and invokes Outlook synchronization only after the canonical import succeeds.
When disabled, the existing calendar-only cycle uses `HEARTBEAT_INTERVAL`.

Provider-import and calendar-sync outcomes are stored separately in
`sync_runs`. The runtime lock is process-local, so deploy only one application
instance for a shared SQLite database and Outlook calendar.

---

# Persistent Storage

Application data is stored inside the Docker named volume

```
smart_sports_data
```

The SQLite database is located inside the container at

```
/data/sports.db
```

Removing the container does **not** remove the database.

Only the following command removes persistent data:

```bash
docker compose down --volumes
```

This command should only be used when a complete reset is intended.

## Backup before upgrade

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

## Upgrade to v0.4.0-alpha.1

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

## Rollback

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

# Portainer Deployment

Deployment is performed directly from Git.

Configuration:

| Setting | Value |
|----------|-------|
| Build Method | Repository |
| Branch or tag | `main` or an immutable released tag |
| Compose File | `docker-compose.yml` |
| Authentication | GitHub Personal Access Token |
| GitOps Updates | Disabled |

Portainer clones the repository and builds the application locally using the provided Dockerfile.

---

# Container Security

The application intentionally **does not run as root**.

Container user:

```
UID: 10001
GID: 10001
```

This follows Docker security best practices and limits the impact of a potential container compromise.

---

# Existing Volumes

When migrating from an older container that was running as root, the database volume may still belong to the root user.

Typical error:

```
sqlite3.OperationalError: attempt to write a readonly database
```

To fix ownership:

```bash
docker run --rm \
    -v smart_sports_data:/data \
    alpine:latest \
    chown -R 10001:10001 /data
```

Restart the container afterwards.

---

# Health Check

The application exposes a Docker health check.

Verify:

```bash
docker compose ps
```

Expected:

```
healthy
```

---

# Logs

Application logs are written to standard output.

View logs:

```bash
docker compose logs -f
```

or through Portainer:

```
Containers
→ smart-sports-calendar
→ Logs
```

No dedicated log volume is used.

---

# Updating the Application

Current workflow:

```
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

# Release Workflow

The source and release workflow is:

```
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
Controlled alpha deployment
```

The release branch is created from fully validated `develop`, reviewed into
`main`, and tagged on the resulting `main` commit. GitHub Releases publishes
the release notes as a pre-release. GHCR remains a future enhancement; do not
document or deploy a registry image that has not been built and verified.

---

# Troubleshooting

## Verify Docker configuration

```bash
docker compose config
```

## Verify running containers

```bash
docker ps
```

## View logs

```bash
docker compose logs -f
```

## Restart container

```bash
docker compose restart
```

## Provider or synchronization failure

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

## Check persistent volumes

```bash
docker volume ls
```

## Inspect the application volume

```bash
docker volume inspect smart_sports_data
```

---

# Current Status

| Component | Status |
|-----------|--------|
| GitHub Repository | ✅ |
| Develop Branch | ✅ |
| Dockerfile | ✅ |
| Docker Compose | ✅ |
| Local Build | ✅ |
| Portainer Git Deployment | ✅ |
| SQLite Persistence | ✅ |
| Health Check | ✅ |
| Non-root Container | ✅ |
| GitHub Releases | Implemented for versioned pre-releases |
| GitHub Actions | Implemented |
| GitHub Container Registry | Planned |
