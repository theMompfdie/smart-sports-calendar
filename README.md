# SMART Sports Calendar

> A containerized synchronization service that imports sports fixtures and events from multiple data providers into a dedicated Microsoft Outlook calendar using Microsoft Graph.

## Current Status

**Current release:** `v0.3.0-alpha.1`  
**Development stage:** Alpha  
**Completed phases:** Phase 1, Phase 2, and Phase 3  
**Automated tests:** 468 passing tests

The application foundation, persistent domain model, repository layer, Microsoft Graph integration, Outlook synchronization engine, and the scheduled, reported API-Football Premier League import runtime are implemented.

## Project Vision

SMART Sports Calendar is designed as a reliable, extensible, and fully automated sports calendar synchronization platform. It maintains a dedicated Outlook calendar containing relevant sports events and updates them when schedules, participants, results, or event states change.

The application focuses on:

- reliability and traceability
- modular and maintainable architecture
- support for multiple sports and providers
- automatic handling of schedule changes and cancellations
- duplicate prevention and idempotent retries
- persistent synchronization state
- containerized deployment and simple migration
- minimal manual maintenance

## Implemented Features

### Application Foundation

- Python 3.13 application
- dependency initialization through an application container
- environment-based configuration
- structured application logging
- graceful shutdown handling
- scheduler integration
- Docker image and Docker Compose deployment
- persistent SQLite volume
- container health check
- Portainer-compatible deployment
- GitHub Actions CI pipeline

### Microsoft 365 Integration

- application authentication through Microsoft Entra ID
- Microsoft Graph access token acquisition
- reusable Microsoft Graph client
- Outlook calendar lookup by configured name or ID
- optional Graph authentication and calendar validation during startup
- Outlook event creation, update, cancellation, and deletion
- idempotent Graph event creation using a persistent transaction ID
- configurable target mailbox and Graph API base URL

### API-Football Integration Foundation

- API-Football v3 selected through a documented provider evaluation and ADR
- external provider configuration with opt-in enablement
- secret-safe `x-apisports-key` authentication
- explicit connect and read timeouts
- typed response-envelope, pagination, diagnostic, and rate-limit metadata
- bounded retry handling for retryable transport failures
- typed Premier League league, season, and team DTO validation
- exact provider competition and current-season resolution
- reviewed provider-team-ID mappings to existing canonical participants
- conflict-safe competition, season, and participant source mappings
- idempotent provider source registration and season memberships
- validated Premier League fixture DTOs and complete paginated retrieval
- timezone-safe UTC kickoff normalization with explicit TBD semantics
- deterministic home/away roles and exhaustive fixture-status mapping
- mapping-backed, side-effect-free canonical fixture normalization
- atomic, idempotent fixture persistence with stable event source mappings
- explicit create, update, skip, cancel, remove, and TBD-defer decisions
- lifecycle correction and two-observation authoritative removal handling
- scheduled non-overlapping provider-import orchestration
- persistent import-run counters, recovery, and sanitized rate-limit diagnostics
- successful-import handoff to the existing Outlook synchronization runtime
- deterministic mocked tests without live provider calls

The catalog, normalization, fixture-import, reporting, and runtime services are
dependency-injected. API-Football remains opt-in and performs no provider call
unless explicitly enabled.
See [`docs/api-football-catalog-mapping.md`](docs/api-football-catalog-mapping.md)
and
[`docs/api-football-fixture-normalization.md`](docs/api-football-fixture-normalization.md)
and
[`docs/api-football-fixture-import.md`](docs/api-football-fixture-import.md)
and
[`docs/api-football-import-runtime.md`](docs/api-football-import-runtime.md)
for the implemented boundaries.

### Database and Persistence

- versioned SQLite schema migrations
- foreign-key enforcement and schema validation
- persistent sports domain model
- provider-to-domain source mappings
- Outlook event mappings and lifecycle tracking
- synchronization run history, counters, errors, and JSON metadata
- persistent transaction IDs for safe event-creation retries
- persistent fixture-removal candidates with distinct-observation protection
- separately queryable provider-import and calendar-sync run history

### Catalog and Repository Layer

Canonical catalog initialization is implemented for sports, competitions, seasons, and participants. Initialization is idempotent and safe during repeated application startups.

Repositories are available for sports, competitions, seasons, participants, season participants, data sources, source mappings, sports events, event participants, results, statistics, Outlook calendar mappings, and synchronization runs.

### Outlook Synchronization Engine

- synchronization orchestration in configurable batches
- Outlook payload construction from canonical sports events
- content-hash based change detection
- event creation and update
- cancellation and deletion reconciliation
- unchanged-event detection without unnecessary Graph requests
- persistent mapping and run-state transitions
- isolated per-event failure handling within a batch
- retry handling for pending and failed mappings
- safe create retries using the same Graph `transactionId`
- recovery of interrupted running synchronization runs
- completed, completed-with-errors, and failed run results
- scheduler integration and synchronization reporting

## Architecture

```text
External Sports Providers
          |
          v
Provider Clients and Import
          |
          v
Normalization and Source Mapping
          |
          v
SQLite Domain Model
          |
          v
Synchronization Engine
          |
          v
Microsoft Graph API
          |
          v
Dedicated Outlook Calendar
```

Provider identifiers are stored separately from the canonical domain model. The synchronization engine reads canonical events from SQLite and reconciles them with persistent Outlook mappings. This keeps provider-specific logic independent from Microsoft Graph and allows providers to be replaced or combined later.

## Synchronization Lifecycle

Each calendar mapping retains its Outlook event ID, change key, content hash, transaction ID, status, attempt count, timestamps, and last error.

Supported lifecycle states include:

- `pending`
- `synced`
- `failed`
- `deletion_pending`
- `deleted`

New Outlook events are created with a stable, persisted transaction ID. If the first Graph request succeeds but the local process fails before persistence completes, a retry reuses the same transaction ID instead of creating another Outlook event.

Synchronization runs retain progress counters and final results. Failures are isolated to the affected event so the remaining batch can continue. Interrupted `running` runs are recovered during startup.

## Domain Model

The database model covers sports, competitions, seasons, participants, season participants, data sources, source mappings, sports events, event participants, results, statistics, calendar event mappings, and synchronization runs. It supports team-based competitions and participant-based sports that may be added later.

## Design Principles

- **Separation of responsibilities:** configuration, lifecycle, providers, persistence, synchronization, Graph, scheduling, and logging remain independent.
- **Canonical internal data:** provider data is normalized before Outlook synchronization.
- **Idempotent processing:** repeated imports, synchronization runs, and Graph create retries must not create duplicates.
- **Persistent traceability:** mappings, attempts, errors, and run history remain in SQLite.
- **Failure isolation:** one failed event does not abort the complete synchronization batch.
- **Extensibility:** additional sports, competitions, and providers do not require a redesign of the synchronization layer.

## Technology Stack

| Component | Technology |
| --- | --- |
| Language | Python 3.13 |
| Containerization | Docker |
| Orchestration | Docker Compose / Portainer |
| Database | SQLite |
| Microsoft 365 API | Microsoft Graph |
| Authentication | MSAL |
| Configuration | Environment variables |
| Logging | Python Logging |
| Testing | pytest |
| Linting and formatting | Ruff |
| CI | GitHub Actions |
| Version control | Git and GitHub |

## Project Structure

```text
smart-sports-calendar/
├── app/
│   ├── application/
│   ├── config/
│   ├── database/
│   │   └── migrations/
│   ├── graph/
│   ├── logging/
│   ├── providers/
│   ├── scheduler/
│   ├── synchronization/
│   └── main.py
├── config/
├── docs/
├── tests/
│   ├── application/
│   ├── database/
│   ├── graph/
│   ├── scheduler/
│   └── synchronization/
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Configuration

Copy the example configuration before starting the application:

```bash
cp .env.example .env
```

Required Microsoft 365 settings:

```env
M365_TENANT_ID=your-tenant-id
M365_CLIENT_ID=your-client-id
M365_CLIENT_SECRET=your-client-secret
M365_USER_ID=your-mailbox@example.com
```

Application and synchronization settings:

```env
TZ=Europe/Vienna
DATABASE_PATH=/data/sports.db
LOG_LEVEL=INFO
HEARTBEAT_INTERVAL=300
OUTLOOK_CALENDAR_NAME=SMART Sports Calendar
OUTLOOK_CALENDAR_ID=
SYNCHRONIZATION_BATCH_LIMIT=100
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
GRAPH_STARTUP_VALIDATION_ENABLED=true
API_FOOTBALL_ENABLED=false
API_FOOTBALL_API_KEY=your-api-football-key
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
API_FOOTBALL_CONNECT_TIMEOUT_SECONDS=5
API_FOOTBALL_READ_TIMEOUT_SECONDS=30
API_FOOTBALL_MAX_ATTEMPTS=3
API_FOOTBALL_RETRY_BASE_DELAY_SECONDS=1
API_FOOTBALL_RETRY_MAX_DELAY_SECONDS=30
API_FOOTBALL_IMPORT_INTERVAL_SECONDS=3600
```

`OUTLOOK_CALENDAR_ID` may be supplied directly. Otherwise, the configured calendar name is resolved through Microsoft Graph. `SYNCHRONIZATION_BATCH_LIMIT` limits the number of events processed in one run.

Keep `GRAPH_STARTUP_VALIDATION_ENABLED` enabled for normal deployments. Disable it only for isolated tests or environments without Graph connectivity. Never commit secrets.

API-Football is disabled by default. When `API_FOOTBALL_ENABLED=true`,
`API_FOOTBALL_API_KEY` is required. The application imports the mapped current
Premier League season every `API_FOOTBALL_IMPORT_INTERVAL_SECONDS`, persists a
separate provider-import report, and then runs Outlook synchronization after a
successful import. The API key is sent only in the `x-apisports-key` header and
must never be logged.

## Deployment

The application supports Docker Engine, Docker Compose, Portainer, and Linux-based container hosts.

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f calendar-sync
```

Stop the application without deleting its persistent data:

```bash
docker compose down
```

SQLite data is stored in the `smart_sports_data` volume. Removing the container does not remove the database; deleting the volume permanently deletes it.

For additional deployment information, see [`docs/deployment.md`](docs/deployment.md).

## Local Development

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Activate the environment on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Run the complete validation:

```bash
python -m pytest -v
python -m ruff check .
python -m ruff format --check .
docker compose config
```

Expected automated test result for `v0.3.0-alpha.1`:

```text
303 passed
```

## Development Workflow

```text
feature/* -> develop -> release/* -> main -> Release
```

- `main` contains released versions.
- `develop` contains the integrated development state.
- feature and fix branches contain isolated implementation blocks.
- release branches prepare a version for release.

## Roadmap

### Phase 1 – Application Foundation

**Status: Completed**  
**Release: `v0.1.0-alpha.1`**

- application lifecycle, configuration, logging, and scheduler
- SQLite initialization
- Microsoft Graph authentication and calendar discovery
- Docker, Portainer, CI, and development tooling

### Phase 2 – Persistent Domain and Repository Layer

**Status: Completed**  
**Release: `v0.2.0-alpha.1`**

- versioned database migrations and complete sports domain schema
- canonical catalogs and repository layer
- provider and Outlook mappings
- synchronization states and run history
- 184 passing automated tests

### Phase 3 – Outlook Synchronization Engine

**Status: Completed**  
**Release: `v0.3.0-alpha.1`**

- synchronization orchestration and batching
- Outlook payload construction
- create, unchanged, update, cancel, and delete lifecycle
- content-hash based change detection
- retry, recovery, and per-event failure isolation
- scheduler integration and run reporting
- persistent Graph transaction IDs for duplicate-safe creation retries
- integration coverage using a migrated SQLite database and mocked Graph client
- comprehensive deterministic automated tests

### Phase 4 – Initial Football Provider

**Status:** _In progress_

- API-Football v3 selected and documented
- provider request, error, pagination, retry, and rate-limit handling implemented
- Premier League source, competition, season, and team mapping implemented
- Premier League fixture validation and canonical-ready normalization implemented
- Premier League fixture persistence and import implemented
- idempotent incremental updates and lifecycle reconciliation implemented
- import reporting, recovery, scheduling, and Outlook handoff implemented

### Phase 5 – Additional Domestic Competitions

**Status:** _Planned_

- Austrian competitions
- German competitions
- additional English competitions

### Phase 6 – UEFA Competitions

**Status:** _Planned_

- Champions League
- Europa League
- Conference League
- Nations League
- European Championship Qualification

### Phase 7 – NFL Provider

**Status:** _Planned_

- NFL teams
- regular season and playoffs
- schedule updates

## Release History

### `v0.3.0-alpha.1`

- complete Outlook synchronization engine
- create, update, cancellation, and deletion reconciliation
- content-hash based change detection
- persistent synchronization mappings and run reporting
- batch processing with isolated event failures
- retry and startup recovery
- idempotent Graph event creation using persistent transaction IDs
- scheduler integration
- full lifecycle integration coverage
- 303 passing automated tests

### `v0.2.0-alpha.1`

- complete persistent sports domain model
- versioned migrations and canonical catalogs
- repository layer for all current domain entities
- source and Outlook mappings
- synchronization state and execution history
- 184 passing automated tests

### `v0.1.0-alpha.1`

- initial application foundation
- Docker and Portainer deployment
- SQLite persistence
- configuration, logging, and scheduler
- Microsoft Graph authentication and calendar discovery

## Current Limitations

This remains an alpha release.

- complete provider-to-SQLite-to-mocked-Graph end-to-end coverage remains Phase 4.7
- no administrative user interface
- synchronization locking is process-local only
- multiple application instances must not synchronize the same calendar/database concurrently
- distributed locking and supported multi-instance coordination are not implemented
- production behavior still requires validation against a real provider and target calendar

The synchronization engine and scheduled API-Football catalog-to-canonical-to-Outlook runtime are implemented with external boundaries mocked. Phase 4.7 adds the complete representative provider-to-mocked-Graph end-to-end validation.

## Project Goals

- fully automated sports calendar synchronization
- no duplicate Outlook events
- automatic handling of rescheduled and cancelled fixtures
- modular support for multiple providers
- clear synchronization history and error traceability
- portable Docker-based deployment
- reliable restart recovery
- minimal operational maintenance

## License

This project is licensed under the MIT License.
