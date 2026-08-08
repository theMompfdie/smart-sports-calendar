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

Production deployments will later use:

```
main
```

Future production releases will be published through GitHub Releases and GitHub Container Registry (GHCR).

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

---

# Portainer Deployment

Deployment is performed directly from Git.

Configuration:

| Setting | Value |
|----------|-------|
| Build Method | Repository |
| Branch | `develop` |
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

# Future Release Workflow

The project will gradually evolve to the following deployment pipeline:

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
GitHub Actions
        │
        ▼
Docker Image (GHCR)
        │
        ▼
Portainer
        │
        ▼
Production
```

At that stage Portainer will no longer build the image itself. Instead, it will pull versioned images directly from GitHub Container Registry.

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
| GitHub Releases | Planned |
| GitHub Actions | Planned |
| GitHub Container Registry | Planned |
