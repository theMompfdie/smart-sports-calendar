# SMART Sports Calendar

> A containerized synchronization service that imports sports fixtures and events from multiple data providers into a dedicated Microsoft Outlook calendar using Microsoft Graph.

## Current Status

**Current release:** `v0.2.0-alpha.1`  
**Development stage:** Alpha  
**Completed phases:** Phase 1 and Phase 2  
**Automated tests:** 184 passing tests

The project foundation, Microsoft Graph connectivity, persistent database model, catalog initialization, and repository layer are implemented.

Automatic provider imports and Outlook event synchronization are not implemented yet.

## Project Vision

SMART Sports Calendar is designed to become a reliable, extensible, and fully automated sports calendar synchronization platform.

The goal is to maintain a single Outlook calendar containing all relevant sports events. Fixtures should be imported from external providers and automatically updated when schedules, participants, results, or event states change.

The application focuses on:

- reliability and traceability
- modular and maintainable architecture
- support for multiple sports and providers
- automatic handling of schedule changes
- duplicate prevention
- persistent synchronization state
- containerized deployment
- simple migration between Docker environments
- minimal manual maintenance

## Implemented Features

### Application Foundation

- Python 3.13 application
- dependency initialization through an application container
- environment-based configuration
- structured application logging
- graceful shutdown handling
- heartbeat scheduler
- Docker image and Docker Compose deployment
- persistent SQLite volume
- container health check
- Portainer-compatible deployment
- GitHub Actions CI pipeline

### Microsoft 365 Integration

- application authentication through Microsoft Entra ID
- Microsoft Graph access token acquisition
- reusable Microsoft Graph client
- Outlook calendar lookup by configured name
- optional Graph authentication and calendar validation during startup
- configurable target mailbox and Graph API base URL

### Database and Persistence

- versioned SQLite schema migrations
- foreign-key enforcement
- schema validation
- persistent domain model for sports calendar data
- synchronization history and error tracking
- provider-to-domain mapping support
- Outlook event mapping and lifecycle tracking

### Catalog Initialization

The application initializes canonical catalog data for:

- sports
- competitions
- seasons
- participants

Catalog initialization is idempotent and can safely run during repeated application startups.

### Repository Layer

The following repositories are implemented and tested:

- `SportsRepository`
- `CompetitionsRepository`
- `SeasonsRepository`
- `ParticipantsRepository`
- `SeasonParticipantsRepository`
- `DataSourcesRepository`
- `SourceMappingsRepository`
- `SportsEventsRepository`
- `EventParticipantsRepository`
- `EventResultsRepository`
- `EventStatisticsRepository`
- `CalendarEventMappingsRepository`
- `SyncRunsRepository`

### Synchronization State

The persistence layer supports:

- provider source mappings
- internal sports event identifiers
- Outlook calendar and event identifiers
- Outlook change keys
- content hashes
- pending, synchronized, failed, deletion-pending, and deleted states
- retry preparation
- synchronization attempt counters
- last synchronization timestamps
- retained synchronization errors
- import and synchronization run history
- progress counters
- structured JSON metadata
- completed, completed-with-errors, and failed run results

## Planned Features

### Provider Integration

- modular provider interface
- provider-specific API clients
- normalization into the internal domain model
- provider request and rate-limit handling
- incremental fixture imports
- source identifier mapping
- retry and error recovery

### Outlook Synchronization

- automatic event creation
- automatic event updates
- cancellation and deletion handling
- duplicate prevention
- Outlook categories
- rich event descriptions
- time zone conversion
- configurable reminders
- content-based change detection
- synchronization reconciliation

## Planned Competitions

### Austria

- Austrian Bundesliga
- 2. Liga
- ÖFB Cup

### Germany

- Bundesliga
- 2. Bundesliga
- DFB-Pokal

### England

- Premier League
- Championship
- FA Cup
- EFL Cup

### UEFA

- UEFA Champions League
- UEFA Europa League
- UEFA Conference League
- UEFA Nations League
- European Championship Qualification

### United States

- NFL

Additional sports, competitions, and providers can be added through the modular data model and provider architecture.

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

The database and repository layer form the boundary between external provider data and Microsoft Outlook synchronization.

External provider identifiers are stored separately from the canonical internal domain model. This allows providers to be replaced or combined without coupling Outlook events directly to one provider.

## Domain Model

The current database model covers:

- sports
- competitions
- seasons
- participants
- season participants
- data sources
- source mappings
- sports events
- event participants
- event results
- event statistics
- calendar event mappings
- synchronization runs

This structure supports both team-based competitions such as football and participant-based sports that may be added later.

## Design Principles

### Separation of Responsibilities

The application is divided into dedicated layers:

- configuration
- application lifecycle
- provider integration
- normalization
- persistence
- synchronization
- Microsoft Graph communication
- scheduling
- logging

### Canonical Internal Data

Provider-specific data is converted into a stable internal model before it is synchronized to Outlook.

### Idempotent Processing

Repeated imports and synchronization runs must update existing records rather than create duplicates.

### Persistent Traceability

Mappings, synchronization states, attempts, errors, and execution history are stored persistently in SQLite.

### Extensibility

New sports, competitions, seasons, participants, and provider integrations can be added without redesigning the synchronization layer.

## Technology Stack

| Component | Technology |
|---|---|
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
│   │   └── container.py
│   ├── config/
│   │   └── settings.py
│   ├── database/
│   │   ├── migrations/
│   │   ├── database.py
│   │   ├── *_catalog.py
│   │   └── *_repository.py
│   ├── graph/
│   │   ├── authentication.py
│   │   └── client.py
│   ├── logging/
│   │   └── logger.py
│   ├── scheduler/
│   │   └── scheduler.py
│   └── main.py
├── config/
├── docs/
│   └── deployment.md
├── tests/
│   ├── application/
│   ├── database/
│   └── graph/
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Configuration

Configuration is supplied through environment variables.

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

Optional application settings:

```env
TZ=Europe/Vienna
DATABASE_PATH=/data/sports.db
LOG_LEVEL=INFO
HEARTBEAT_INTERVAL=300
OUTLOOK_CALENDAR_NAME=SMART Sports Calendar
GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
GRAPH_STARTUP_VALIDATION_ENABLED=true
```

`GRAPH_STARTUP_VALIDATION_ENABLED` should remain enabled during normal deployments. It can be disabled for isolated tests or environments without Microsoft Graph connectivity.

Secrets must not be committed to the repository.

## Deployment

The application is designed for deployment on any Docker-compatible host.

Typical environments include:

- Docker Engine
- Docker Compose
- Portainer
- Linux-based container hosts

### Start with Docker Compose

```bash
docker compose up -d --build
```

### Check Container Status

```bash
docker compose ps
```

### View Logs

```bash
docker compose logs -f calendar-sync
```

### Stop the Application

```bash
docker compose down
```

The SQLite database is stored in the persistent Docker volume:

```text
smart_sports_data
```

Removing the container does not remove the database. Deleting the volume will permanently delete the stored application data.

For additional deployment information, see [`docs/deployment.md`](docs/deployment.md).

## Local Development

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux or macOS:

```bash
source .venv/bin/activate
```

Install application and development dependencies:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Run the quality checks:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

Expected result for `v0.2.0-alpha.1`:

```text
184 passed
```

Apply automatic formatting when required:

```bash
python -m ruff format .
```

## Development Workflow

```text
feature/*
    |
    v
develop
    |
    v
release/*
    |
    v
main
    |
    v
Release
```

- `main` contains released versions.
- `develop` contains the integrated development state.
- `feature/*` branches contain isolated implementation blocks.
- `release/*` branches prepare a version for release.
- Feature branches are merged into `develop`.
- Release branches are merged into `main`.

## Roadmap

### Phase 1 – Application Foundation

**Status: Completed**  
**Release: `v0.1.0-alpha.1`**

- Python project foundation
- environment-based configuration
- logging
- application container
- scheduler and heartbeat
- SQLite initialization
- Microsoft Graph authentication
- Microsoft Graph client
- Outlook calendar discovery
- Docker image
- Docker Compose deployment
- persistent storage
- Portainer deployment support
- CI and development tooling

### Phase 2 – Persistent Domain and Repository Layer

**Status: Completed**  
**Release: `v0.2.0-alpha.1`**

- versioned database migrations
- complete sports domain schema
- sports and competition catalogs
- season and participant catalogs
- data-source management
- external source mappings
- sports event persistence
- event participants
- results and statistics
- Outlook calendar event mappings
- synchronization lifecycle states
- synchronization run history
- repository integration in the application container
- full repository test coverage
- 184 passing automated tests

### Phase 3 – Synchronization Engine

**Status: Next**

- synchronization orchestration
- import run coordination
- event normalization workflow
- Outlook event creation and updates
- change detection using content hashes
- cancellation and deletion handling
- retry and error recovery
- synchronization reporting

### Phase 4 – Initial Football Provider

**Status: Planned**

- first external football data provider
- Premier League fixture import
- team and season mapping
- provider-specific error and rate-limit handling

### Phase 5 – Additional Domestic Competitions

**Status: Planned**

- Austrian competitions
- German competitions
- additional English competitions

### Phase 6 – UEFA Competitions

**Status: Planned**

- Champions League
- Europa League
- Conference League
- Nations League
- European Championship Qualification

### Phase 7 – NFL Provider

**Status: Planned**

- NFL teams
- regular season
- playoffs
- schedule updates

## Release History

### `v0.2.0-alpha.1`

- complete persistent sports domain model
- database migration support
- canonical catalog initialization
- repository layer for all current domain entities
- source and Outlook event mapping
- synchronization state and execution history
- 184 passing automated tests

### `v0.1.0-alpha.1`

- initial application foundation
- Docker and Portainer deployment
- SQLite persistence
- configuration and logging
- scheduler
- Microsoft Graph authentication and calendar discovery

## Current Limitations

This is an alpha release.

The following capabilities are not available yet:

- external sports provider imports
- automatic Outlook event creation
- automatic Outlook event updates
- cancellation reconciliation
- production-ready synchronization scheduling
- administrative user interface
- multi-instance coordination

The application currently provides the technical foundation and persistent data layer required for these features.

## Project Goals

- fully automated sports calendar synchronization
- no duplicate Outlook events
- automatic handling of rescheduled and cancelled fixtures
- modular support for multiple data providers
- clear synchronization history and error traceability
- portable Docker-based deployment
- reliable recovery after restarts
- minimal operational maintenance

## License

This project is licensed under the MIT License.