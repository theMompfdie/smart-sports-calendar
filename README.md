# SMART Sports Calendar

> A containerized synchronization service that imports sports fixtures and events from multiple data providers into a dedicated Microsoft Outlook calendar using Microsoft Graph.

## Current Status

**Current release:**
[v0.9.0-beta.1](https://github.com/theMompfdie/smart-sports-calendar/releases/tag/v0.9.0-beta.1)
(GitHub pre-release)

**Production promotion:** provider requalification completed in
[#233](https://github.com/theMompfdie/smart-sports-calendar/issues/233).
The production upgrade and target-specific imports remain operator-controlled.

**Development stage:** Beta

**Completed releases:** Phases 1-9.

**Latest delivery:** Phase 9 reviewed manual imports, published on 2026-09-06.
All seven bounded staging targets are accepted in
[#254](https://github.com/theMompfdie/smart-sports-calendar/issues/254).
The signed tag targets verified main commit `36bd6fe`; all five main CI jobs
passed, including 1,516 tests. See the
[Phase 9 release checklist](docs/v0.9.0-beta.1-release-checklist.md).

**Next delivery:** Stable v1.0.0 after the remaining roadmap gates pass.

The application foundation, persistent domain model, repository layer,
Microsoft Graph integration, Outlook synchronization engine, and scheduled
provider runtimes for the qualified Premier League, Bundesliga, EFL
Championship regular season, DFB-Pokal, 2. Bundesliga, ÖFB-Cup, UEFA Nations
League A group phase, UEFA Champions League league phase, and NFL 2026 regular
season are implemented and have passed isolated live staging.

The beta release includes provider-neutral source selection, eight
approved 2026/27 association-football authorities, one approved NFL 2026
regular-season authority, hybrid UEFA and bounded NFL lifecycle models, isolated
multi-instance deployment, and secret-safe live staging validation through
Outlook. It remains a pre-release:
production promotion is a separate explicit operator decision and is never
performed automatically. The official ECAL calendar remains unapproved for
automated ingestion.

## Project Vision

SMART Sports Calendar synchronizes sports fixtures into a dedicated Outlook
calendar and updates them when schedules, participants, or event states change.

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
- project-scoped images, containers, networks, and SQLite volumes
- validated per-instance identifiers in logs and Docker labels
- credential-free three-instance Compose isolation validation
- GitHub Actions CI pipeline

### Microsoft 365 Integration

- application authentication through Microsoft Entra ID
- Microsoft Graph access token acquisition
- reusable Microsoft Graph client
- required Outlook calendar targeting by immutable Graph calendar ID
- optional startup reachability validation by configured calendar name
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
- bounded stage/round reconciliation for qualified knockout/cup observations
- scheduled non-overlapping provider-import orchestration
- persistent import-run counters, recovery, and sanitized rate-limit diagnostics
- successful-import handoff to the existing Outlook synchronization runtime
- provider-payload-to-SQLite-to-mocked-Graph end-to-end validation
- retry-safe Outlook deletion and identity-preserving fixture reappearance
- deterministic mocked tests without live provider calls

The catalog, normalization, fixture-import, reporting, and runtime services are
dependency-injected. API-Football remains opt-in and performs no provider call
unless explicitly enabled.

Provider-neutral source jobs provide explicit competition/season authority,
roles, independent intervals, adapter registration, fail-closed startup
validation, and persistent assignment history. The current API-Football writer
must be paired with an explicit authoritative source job when enabled. The
football-data.org API v4 runtime supports strict 2026/27 Premier League,
Bundesliga, and EFL Championship profiles, independent competition jobs, and a
shared provider-wide quota. Premier League and Bundesliga require complete
seasons. Championship accepts only its qualified 552-fixture `REGULAR_SEASON`
stage through one exact response or validated `500 + 52` pagination; its seven
play-off fixtures remain excluded. Each scope fails closed before canonical or
Outlook handoff unless its exact completeness contract validates. Championship
live staging passed its operator gate. The 2026/27 DFB-Pokal uses the
public OpenLigaDB API through a separate knockout-cup profile. Its observations
are permanently partial: they
may create or update known fixtures but never infer cancellation or removal.
The same public provider is qualified and implemented as the preferred no-cost
2026/27 2. Bundesliga authority. Its initial runtime is removal-disabled and
passed isolated staging. OpenLigaDB also provides the implemented, bounded
2026/27 UEFA Nations League A group-phase authority: exactly 48 fixtures and
16 participants, permanently removal-disabled, with every other league and
later stage excluded. Its 2026/27 UEFA Champions League authority is bounded
to exactly 144 league-phase fixtures and 36 participants; qualifying and every
knockout stage remain excluded and removal-disabled. The official ÖFB
competition iCalendar feed provides
the private 2026/27 ÖFB-Cup authority through a strict permanent-partial
contract; it can create or update stable fixtures but absence is never
destructive.

Phase 4 documentation:

- [provider requirements and evaluation](docs/provider-evaluation.md)
- [API-Football selection ADR](docs/adr/0001-select-api-football.md)
- [Premier League official-feed qualification](docs/premier-league-official-feed-qualification.md)
- [ECAL automated-source rejection ADR](docs/adr/0002-reject-ecal-as-automated-source.md)
- [football-data.org Premier League selection ADR](docs/adr/0003-select-football-data-for-premier-league.md)
- [football-data.org qualification](docs/football-data-qualification.md)
- [football-data.org Premier League import](docs/football-data-premier-league-import.md)
- [provider-independent integration contract](docs/provider-integration-contract.md)
- [provider-neutral source orchestration](docs/source-orchestration.md)
- [Premier League catalog mapping](docs/api-football-catalog-mapping.md)
- [fixture normalization](docs/api-football-fixture-normalization.md)
- [idempotent fixture import](docs/api-football-fixture-import.md)
- [scheduled import runtime](docs/api-football-import-runtime.md)
- [provider-to-Outlook end-to-end testing](docs/provider-outlook-end-to-end-testing.md)
- [deployment and operations](docs/deployment.md)
- [manual live validation](docs/phase-4-live-validation.md)
- [Phase 4 release checklist](docs/phase-4-release-checklist.md)
- [v0.4 stabilization roadmap](docs/v0.4-stabilization-roadmap.md)

Phase 5 decision records:

- [competition lifecycle model](docs/adr/0004-model-competition-lifecycle-scopes.md)
- [source and authority matrix](docs/phase-5-source-authority-matrix.md)
- [source qualification boundary ADR](docs/adr/0005-bound-phase-5-source-qualification.md)
- [football-data.org Bundesliga selection ADR](docs/adr/0006-select-football-data-for-bundesliga.md)
- [football-data.org Bundesliga import](docs/football-data-bundesliga-import.md)
- [football-data.org Championship import](docs/football-data-championship-import.md)
- [football-data.org Championship selection ADR](docs/adr/0008-select-football-data-for-championship-regular-season.md)
- [OpenLigaDB DFB-Pokal selection ADR](docs/adr/0007-select-openligadb-for-dfb-pokal.md)
- [OpenLigaDB DFB-Pokal qualification](docs/openligadb-dfb-pokal-qualification.md)
- [OpenLigaDB DFB-Pokal import](docs/openligadb-dfb-pokal-import.md)
- [OpenLigaDB 2. Bundesliga qualification](docs/openligadb-2-bundesliga-qualification.md)
- [OpenLigaDB 2. Bundesliga selection ADR](docs/adr/0009-select-openligadb-for-2-bundesliga.md)
- [OpenLigaDB 2. Bundesliga import](docs/openligadb-second-bundesliga-import.md)
- [Austrian Bundesliga source qualification](docs/austrian-bundesliga-source-qualification.md)
- [FA Cup source qualification](docs/fa-cup-source-qualification.md)
- [EFL Cup source qualification](docs/efl-cup-source-qualification.md)
- [ÖFB-Cup source qualification](docs/oefb-cup-source-qualification.md)
- [ÖFB-Cup authority selection ADR](docs/adr/0010-select-oefb-calendar-for-oefb-cup.md)
- [Phase 5 multi-competition staging validation](docs/phase-5-multi-competition-staging-validation.md)
- [v0.5.0-beta.1 release checklist](docs/v0.5.0-beta.1-release-checklist.md)

Phase 6 decision records:

- [hybrid UEFA lifecycle ADR](docs/adr/0011-model-hybrid-uefa-lifecycle.md)
- [source and authority matrix](docs/phase-6-source-authority-matrix.md)
- [Champions League source qualification](docs/uefa-champions-league-source-qualification.md)
- [OpenLigaDB Champions League selection ADR](docs/adr/0013-select-openligadb-for-champions-league-league-phase.md)
- [OpenLigaDB Champions League import](docs/openligadb-champions-league-import.md)
- [Champions League isolated staging validation](docs/champions-league-staging-validation.md)
- [Europa League source qualification](docs/uefa-europa-league-source-qualification.md)
- [Conference League source qualification](docs/uefa-conference-league-source-qualification.md)
- [Nations League source qualification](docs/uefa-nations-league-source-qualification.md)
- [OpenLigaDB Nations League A selection ADR](docs/adr/0012-select-openligadb-for-nations-league-a.md)
- [OpenLigaDB Nations League A import](docs/openligadb-nations-league-a-import.md)
- [Public repository and runtime data safety](docs/public-repository-data-safety.md)
- [Nations League A isolated staging validation](docs/nations-league-a-staging-validation.md)
- [v0.6.0-beta.1 release checklist](docs/v0.6.0-beta.1-release-checklist.md)

Phase 7 decision records:

- [NFL source qualification](docs/nfl-source-qualification.md)
- [NFL authority selection ADR](docs/adr/0013-select-nflverse-for-nfl-regular-season.md)
- [Phase 7 source and authority matrix](docs/phase-7-source-authority-matrix.md)
- [Phase 7 isolated staging validation](docs/phase-7-staging-validation.md)
- [v0.7.0-beta.1 release checklist](docs/v0.7.0-beta.1-release-checklist.md)

Phase 8 design and implementation documentation:

- [Outlook presentation, reminder, and media ADR](docs/adr/0014-model-outlook-presentation-reminders-and-media.md)
- [Outlook presentation, reminder, and media contract](docs/outlook-presentation-reminder-media-contract.md)
- [Runtime reminder rule administration](docs/runtime-reminder-rules.md) —
  persisted rules, local CLI, Vienna-aware quiet-period calculation, and Graph
  payload projection are implemented together with targeted, revision-safe
  convergence of existing Outlook events
- [Rights-controlled media asset registry](docs/media-asset-registry.md) —
  persistent metadata, explicit approval and version history, safe local
  PNG/JPEG normalization, content-addressed operator storage, and restart-safe
  Outlook inline-attachment reconciliation are implemented
- [Phase 8 isolated staging validation](docs/phase-8-staging-validation.md) —
  accepted live upgrade, reminder mutation, media recovery, unchanged-cycle,
  backup/restore, and canonical-isolation evidence for issue #214
- [Phase 8 release checklist](docs/v0.8.0-beta.1-release-checklist.md)
- [Phase 8 candidate release notes](RELEASE_NOTES_v0.8.0-beta.1.md)

For optional real logos, use the
[logo rights preparation workflow](docs/logo-rights-workflow.md),
[rights catalog template](docs/templates/logo-rights-catalog.md), and
[permission email template](docs/templates/logo-permission-request.md).
These prepare later private-use reviews; they do not clear individual logos.
Unresolved rights retain text-only or reviewed project-owned artwork.

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

The database model covers sports, competitions, seasons, participants, season
participants, data sources, source assignments, source mappings, sports
events, event participants, results, statistics, calendar event mappings, and
synchronization runs. It supports team-based competitions and
participant-based sports that may be added later.

The [multi-competition catalog foundation](docs/multi-competition-catalog.md)
records the qualified Bundesliga competition and 2026/27 season alongside the
existing Premier League catalog. This is catalog metadata only: Bundesliga
participants, fixture import, scheduling, staging, and release remain separate
Phase 5 work.

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
OUTLOOK_CALENDAR_ID=your-outlook-calendar-id
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

`OUTLOOK_CALENDAR_ID` is required and is the immutable Graph calendar identifier
used for all synchronization writes. `OUTLOOK_CALENDAR_NAME` is used only by
the optional startup reachability check and must refer to the same dedicated
SMART Sports Calendar. `SYNCHRONIZATION_BATCH_LIMIT` limits the number of
events processed in one run. Bounded runs process unmapped and retry/lifecycle
work before ordinary synced mappings; synced mappings are revalidated in
oldest-synchronized-first order so every event progresses without starvation.

Keep `GRAPH_STARTUP_VALIDATION_ENABLED` enabled for normal deployments. Disable it only for isolated tests or environments without Graph connectivity. Never commit secrets.

API-Football is disabled by default. When `API_FOOTBALL_ENABLED=true`,
`API_FOOTBALL_API_KEY` is required. The application imports the mapped current
Premier League season every `API_FOOTBALL_IMPORT_INTERVAL_SECONDS`, persists a
separate provider-import report, and independently runs Outlook synchronization
every `HEARTBEAT_INTERVAL`. The API key is sent only in the
`x-apisports-key` header and must never be logged.

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

SQLite data is stored in the project-scoped `smart_sports_data` logical volume.
Removing a container does not remove the database; deleting the corresponding
project volume permanently deletes it.

For deployment, upgrade, backup, rollback, and troubleshooting information,
see [`docs/deployment.md`](docs/deployment.md).

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

The complete pytest suite must pass without failures. See
[pytest runtime measurements](docs/pytest-runtime.md) for the baseline,
fixture isolation strategy, and reproducible timing commands.

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

**Status:** _Completed_

**Release:** `v0.4.0-alpha.1`

- API-Football v3 selected and documented
- provider request, error, pagination, retry, and rate-limit handling implemented
- Premier League source, competition, season, and team mapping implemented
- Premier League fixture validation and canonical-ready normalization implemented
- Premier League fixture persistence and import implemented
- idempotent incremental updates and lifecycle reconciliation implemented
- import reporting, recovery, scheduling, and Outlook handoff implemented
- deterministic provider-to-Outlook end-to-end integration coverage implemented
- deployment, upgrade, live-validation, and release documentation completed

### v0.4.5 Authoritative-Source Beta

**Status:** _Beta pre-release_

**Target release:** `v0.4.5-beta.1`

- document the two-stack Portainer operating model
- remove Docker Compose naming and persistence conflicts
- verify at least three independent local containers
- deploy an isolated staging stack with automatic `develop` updates
- complete provider-neutral per-competition source orchestration
- integrate the qualified football-data.org Premier League authority
- complete credential-safe provider and Microsoft Graph live validation
- qualify and publish an immutable GitHub beta candidate
- promote to production manually only after the deferred live provider-failure
  exercise in issue #101

This track is managed by
[GitHub issue #72](https://github.com/theMompfdie/smart-sports-calendar/issues/72).
Phase 5 does not begin until its blocking stabilization gates are complete. See
the [v0.4 stabilization roadmap](docs/v0.4-stabilization-roadmap.md) for the
delivery order and operational boundaries.

### Phase 5 – Additional Domestic Competitions

**Status:** _Completed in `v0.5.0-beta.1`_

- source qualification and competition-specific authority decisions
- German Bundesliga qualified and implemented through the credential-free
  provider-to-SQLite-to-mocked-Graph boundary; isolated live staging completed
- DFB-Pokal qualified and implemented with OpenLigaDB through the
  provider-to-SQLite-to-mocked-Graph boundary; isolated live staging completed
  and absence never causes removal
- 2\. Bundesliga qualified and implemented with OpenLigaDB through the
  provider-to-SQLite-to-mocked-Graph boundary; initial operation remains
  removal-disabled and isolated live staging is completed
- EFL Championship regular season implemented with strict 552-fixture and
  `500 + 52` pagination contracts; isolated live staging completed
- Austrian Bundesliga deferred because no reviewed no-cost candidate provides
  a permitted complete scope and no paid plan was approved
- FA Cup deferred because official sources are manual-only, no reviewed free
  API supplies a safe 2026/27 scope, and no paid plan was approved
- EFL Cup deferred because the official ECAL calendar is not permitted for
  automated collection, no reviewed free API supplies a safe complete scope,
  and no paid plan was approved
- ÖFB-Cup official iCalendar source qualified and implemented for private,
  non-destructive `partial` use through the provider-to-SQLite-to-mocked-Graph
  boundary; isolated live staging, Outlook attribution, failure/recovery, and
  idempotency validation completed

### Phase 6 – UEFA Competitions

**Status:** _Completed in `v0.6.0-beta.1` through master issue
[#150](https://github.com/theMompfdie/smart-sports-calendar/issues/150)_

- provider-neutral hybrid lifecycle and identity contract completed by
  [#151](https://github.com/theMompfdie/smart-sports-calendar/issues/151)
- UEFA Champions League 2026/27 delivery tracked by
  [#153](https://github.com/theMompfdie/smart-sports-calendar/issues/153)
- zero-cost source qualification tracked by
  [#154](https://github.com/theMompfdie/smart-sports-calendar/issues/154):
  OpenLigaDB `ucl` / 4946 is qualified for exactly the 144-fixture, 36-club
  league phase with permanent removal-disabled handling; qualifying and all
  knockout stages remain excluded; isolated live staging passed, and the
  superseded football-data.org issue
  [#155](https://github.com/theMompfdie/smart-sports-calendar/issues/155)
  was closed without using the credential for UCL
- UEFA Europa League 2026/27 delivery tracked by
  [#157](https://github.com/theMompfdie/smart-sports-calendar/issues/157),
  with completed source qualification in
  [#158](https://github.com/theMompfdie/smart-sports-calendar/issues/158): the
  competition is deferred from `v0.6.0-beta.1`; Footballdata.io free access,
  UEL league 46, and current season 90443 are confirmed, but only qualifying
  and play-off fixtures were available in that historical observation.
  Footballdata.io remains the
  preferred zero-cost re-evaluation candidate for the later league-phase
  integration. No authority was assigned for Phase 6; the later manual
  staging delivery is described in the Version 1.0 checkpoint below
- UEFA Conference League 2026/27 delivery tracked by
  [#160](https://github.com/theMompfdie/smart-sports-calendar/issues/160),
  with completed source qualification in
  [#161](https://github.com/theMompfdie/smart-sports-calendar/issues/161): the
  competition is deferred from `v0.6.0-beta.1` because no zero-cost 2026/27
  automated candidate exists and no paid provider was approved; no authority
  or runtime is assigned
- UEFA Nations League 2026/27 delivery tracked by
  [#163](https://github.com/theMompfdie/smart-sports-calendar/issues/163),
  with completed source and scope qualification in
  [#164](https://github.com/theMompfdie/smart-sports-calendar/issues/164) and
  implementation in
  [#170](https://github.com/theMompfdie/smart-sports-calendar/issues/170):
  OpenLigaDB is the selected EUR 0 authority for exactly the 48-fixture,
  16-participant League A group phase; Leagues B, C, and D and all later stages
  remain excluded; isolated live staging, controlled failure/recovery, and
  backup/restore validation were completed in
  [#172](https://github.com/theMompfdie/smart-sports-calendar/issues/172)
- UEFA EURO 2028 qualification is tracked by
  [#176](https://github.com/theMompfdie/smart-sports-calendar/issues/176) and
  [#177](https://github.com/theMompfdie/smart-sports-calendar/issues/177), but
  is explicitly deferred from `v0.6.0-beta.1`. Evidence is retained for a
  post-draw recheck after 6 December 2026 and any implementation belongs to a
  separately approved December release.

The released Phase 6 subset is deliberately bounded to the Champions League
league phase and Nations League A group phase. Europa League, Conference
League, UEFA EURO 2028 qualification, later Champions League stages, and later
Nations League stages remain outside `v0.6.0-beta.1`.

### Phase 7 – NFL Provider

**Status:** _Published as `v0.7.0-beta.1`_ through
[#178](https://github.com/theMompfdie/smart-sports-calendar/issues/178) and
[#198](https://github.com/theMompfdie/smart-sports-calendar/issues/198).

- [#179](https://github.com/theMompfdie/smart-sports-calendar/issues/179)
  qualifies the zero-cost nflverse schedule release for exactly the NFL 2026
  regular season: 32 teams, 272 games, and weeks 1–18
- the nflverse CSV transport, strict adapter, 32-team catalog, provider-neutral
  runtime, SQLite import, scheduler integration, and Outlook synchronization
  are implemented for exactly the approved scope
- the authority remains non-destructive because late-season times are
  subject to NFL flex scheduling and the community feed has no authoritative
  snapshot-completeness marker
- preseason and postseason remain separate, unqualified scopes
- raw NFL/nflverse data, logos, databases, and Outlook exports remain outside
  the public repository; generated events require nflverse and CC BY 4.0
  attribution
- NFL Outlook events without an explicit provider end time reserve a
  deterministic three-hour calendar window; other sports retain the generic
  two-hour fallback
- deterministic SQLite-to-mocked-Graph coverage proves flex updates, restart,
  failure/recovery, unchanged reruns, attribution, and duplicate prevention
- isolated live staging accepted 272 fixtures and mappings, write-free reruns,
  restart convergence, controlled failure/recovery, and an isolated readable
  backup restore; production promotion remains separate and manual

Qualification records:

- [NFL source qualification](docs/nfl-source-qualification.md)
- [Phase 7 source matrix](docs/phase-7-source-authority-matrix.md)
- [ADR 0013](docs/adr/0013-select-nflverse-for-nfl-regular-season.md)
- [Phase 7 staging record](docs/phase-7-staging-validation.md)
- [Phase 7 release checklist](docs/v0.7.0-beta.1-release-checklist.md)

### Phase 8 – Outlook presentation, reminders, and media

**Status:** _Published as `v0.8.0-beta.1`_
under [#199](https://github.com/theMompfdie/smart-sports-calendar/issues/199)
and [#214](https://github.com/theMompfdie/smart-sports-calendar/issues/214).

The candidate adds competition-only categories, sport icons, deterministic
HTML, Vienna event timezone projection, persistent runtime reminder rules,
quiet-hour resolution, targeted presentation convergence, and optional
rights-controlled inline artwork. Migrations 009–012 preserve existing data.
The nine qualified authorities and provider lifecycle boundaries are unchanged.

Visual presentation, runtime reminder mutation/restart, synthetic cleanup,
media replacement/recovery, backup/restore, full-calendar inventory, and
write-free convergence are accepted. The recurring Championship provider
response-contract violation was a documented beta limitation. Requalification
completed in #233 on 2026-09-06; strict parsing and data retention remain active.
The signed Phase 8 beta is published; the Phase 9 prerequisite is satisfied.

### Phase 9 - Reviewed manual fixture imports

**Status:** _Published as `v0.9.0-beta.1`_.

The `v0.9.0-beta.1` release adds operator-reviewed manual imports for
Austrian Bundesliga, EFL Cup, UEFA Conference League and Nations League B/C/D.
Their accepted published scopes contain 388 fixtures. FA Cup is accepted as a
review-only First Round Proper publication check, with no invented fixtures.
Eight dedicated Outlook update-review appointments cover all seven targets.

The [manual import ADR](docs/adr/0015-import-reviewed-manual-fixture-manifests.md)
defines stable fixture IDs, source provenance, write-free preview, exact
detached approval, atomic canonical apply and durable receipts.
Partial omissions never delete games. Extraction from source documents stays
outside the scheduled runtime; version 1 imports schedules, not results.

Use the [preparation guide](docs/manual-import-preparation.md),
[preview contract](docs/manual-import-preview.md),
[atomic backend guide](docs/manual-import-apply.md) and
[Docker-host workflow](docs/manual-import-workflow.md).
Trusted profiles require qualified catalogs and explicit authority.
Nations League B/C/D own disjoint group stages alongside existing League A;
a broad grant is never narrowed implicitly.

Enable the optional inbox on one owning instance with
`MANUAL_IMPORT_ROOT=/data/manual-import`, `MANUAL_IMPORT_INTERVAL=60` and
`MANUAL_IMPORT_LIMIT=10`. Submit reviewed input, inspect AWAITING_APPROVAL,
approve the exact preview, then verify APPLIED and actual Outlook convergence.
QUEUED alone is not import success. Later updates retain fixture IDs and use
new submission IDs.

Review plans supply due dates and reminder lead times for future publications,
draws and kickoff checks. The worker creates separate Outlook appointments;
the operator still obtains and reviews the next source update.
Task completion retires only those appointments, not fixture history.

See the [release notes](RELEASE_NOTES_v0.9.0-beta.1.md) for the accepted
scope, recovery evidence and known limitations. The DFB-Pokal alias issue
[#268](https://github.com/theMompfdie/smart-sports-calendar/issues/268)
affects source freshness. The provider gate in
[#233](https://github.com/theMompfdie/smart-sports-calendar/issues/233) is resolved;
production backup, upgrade and target-specific import checks remain required.

Competition retirement, UEL delivery and the general README/repository audit
are v1.0 follow-ups #267, #269 and #270. The operator selected this beta
as the last planned pre-release; stable v1.0.0 still requires all final gates.

### Version 1.0 Europa League checkpoint - 2026-09-07

After Phase 9, issue [#269][uel-delivery] requalified the automated candidates
and selected reviewed manual import. PR #277 delivered the 2026/27 UEL
catalog. The isolated staging import contains **144 league-phase fixtures**
and initially eight review appointments. The accepted review-only extension
brings the total to **26 converged review appointments**, including weekly
Monday checks through May 31, 2027, at 09:00 Europe/Vienna. The operator
confirmed the fixture appointments; unchanged replay returned 144 SKIP without
canonical duplicates.

The delivered boundary is league-phase rounds 1-8. Later knockout rounds
through the final require new reviewed packages, explicit authority/profile
extensions under the accepted publication-review cadence. No automated UEL
writer or production deployment is claimed. Post-import backup, isolated
restore and staging restart passed. The operator reconfirmed the complete
league phase; diagnostic fix #278 is integrated with all five CI jobs green.
See the dated [UEL qualification record][uel-qualification] for evidence and
the [UEL delivery record](docs/uefa-europa-league-delivery.md) for the current
source matrix, update procedure, release-note entry and production runbook.
Final documentation integration and the separate v1.0 release gates remain
open.

[uel-delivery]: https://github.com/theMompfdie/smart-sports-calendar/issues/269
[uel-qualification]: docs/uefa-europa-league-source-qualification.md

## Release History

Published Phase 9 notes are available in
[RELEASE_NOTES_v0.9.0-beta.1.md](RELEASE_NOTES_v0.9.0-beta.1.md).
The signed pre-release was published on 2026-09-06.

Phase 8 candidate notes are available in
[`RELEASE_NOTES_v0.8.0-beta.1.md`](RELEASE_NOTES_v0.8.0-beta.1.md).

Detailed Phase 4 release notes are available in
[`RELEASE_NOTES_v0.4.0-alpha.1.md`](RELEASE_NOTES_v0.4.0-alpha.1.md).

Detailed authoritative-source beta release notes are available in
[`RELEASE_NOTES_v0.4.5-beta.1.md`](RELEASE_NOTES_v0.4.5-beta.1.md).

Detailed Phase 5 beta release notes are available in
[`RELEASE_NOTES_v0.5.0-beta.1.md`](RELEASE_NOTES_v0.5.0-beta.1.md).

Detailed Phase 6 beta release notes are available in
[`RELEASE_NOTES_v0.6.0-beta.1.md`](RELEASE_NOTES_v0.6.0-beta.1.md).

Phase 7 release notes are available in
[`RELEASE_NOTES_v0.7.0-beta.1.md`](RELEASE_NOTES_v0.7.0-beta.1.md).

### `v0.7.0-beta.1`

- zero-cost nflverse authority for exactly 272 NFL 2026 regular-season games,
  32 teams, and weeks 1–18
- stable `game_id` correlation with Eastern-time normalization and safe NFL
  flex-scheduling updates
- permanently partial, removal-disabled lifecycle behavior that preserves
  last-known-good SQLite and Outlook state on omissions or failures
- visible nflverse CC BY 4.0 attribution and flex-scheduling notice in Outlook
- deterministic three-hour NFL fallback duration while association football
  retains the generic two-hour fallback
- provider-neutral scheduling, SQLite persistence, Graph synchronization,
  retry, restart, recovery, and unchanged-cycle idempotency coverage
- isolated live staging and backup/restore acceptance without publishing raw
  fixture data, private database content, or deployment identifiers
- explicit exclusion of preseason, postseason, results, statistics, standings,
  rosters, injuries, venues, weather, media, and logos
- 1,048 passing automated tests

### `v0.6.0-beta.1`

- provider-neutral hybrid UEFA stage, round, tie, leg, and partial-observation
  lifecycle model
- zero-cost OpenLigaDB UEFA Champions League authority for exactly 144
  league-phase fixtures and 36 participants
- zero-cost OpenLigaDB UEFA Nations League authority for exactly 48 League A
  group-phase fixtures and 16 participants
- permanent removal-disabled handling for both new UEFA authorities
- deterministic SQLite-to-mocked-Graph coverage for imports, reschedules,
  restart, failure/recovery, attribution, and unchanged-cycle idempotency
- isolated live staging, Outlook convergence, controlled provider failure,
  recovery, and backup/restore evidence
- explicit deferral of Europa League, Conference League, EURO 2028
  qualification, and every unqualified later tournament scope
- 967 passing automated tests

### `v0.5.0-beta.1`

- six concurrent qualified 2026/27 competition authorities
- Bundesliga and EFL Championship through football-data.org
- DFB-Pokal and removal-disabled 2. Bundesliga through OpenLigaDB
- private permanent-partial ÖFB-Cup authority through the official iCalendar
  feed
- explicit league, complete-stage, and non-destructive cup lifecycle scopes
- Outlook synchronization prioritization for changed and pending revisions
- deterministic migration `008_add_calendar_sync_revisions`
- six-authority live staging, Outlook convergence, restart, failure, recovery,
  and idempotency evidence
- explicit deferral of Austrian Bundesliga, FA Cup, EFL Cup, and UEFA scopes
- 898 passing automated tests

### `v0.4.5-beta.1`

- isolated staging and production Docker/Portainer operating model
- provider-neutral per-competition and per-season source authority
- qualified football-data.org API v4 Premier League integration
- complete 2026/27 Premier League import with 380 stable fixtures
- independent recurring provider and Outlook synchronization schedules
- visible authoritative-source attribution in Outlook events
- secret-safe qualification and staging-evidence commands
- credential-safe live staging validation and idempotent Outlook convergence
- controlled production-promotion evidence was completed in issue #101

### `v0.4.0-alpha.1`

- first API-Football v3 provider integration
- deterministic Premier League catalog and team mappings
- validated, timezone-safe fixture normalization
- atomic idempotent imports and lifecycle reconciliation
- scheduled import reporting, retry handling, and Outlook handoff
- provider-to-SQLite-to-mocked-Graph end-to-end coverage
- deployment, upgrade, rollback, live-validation, and release documentation
- 477 passing automated tests

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

This remains a beta pre-release.

- live provider and Microsoft Graph tenant behavior is not exercised by CI
- no administrative user interface
- synchronization locking is process-local only
- multiple application instances must not synchronize the same calendar or
  database concurrently
- distributed locking and supported multi-instance coordination are not
  implemented
- production promotion remains a separate manual operator decision

The synchronization engine and scheduled provider-to-canonical-to-Outlook
runtimes are covered by deterministic provider-payload-to-SQLite-to-mocked-
Graph tests. Live provider and tenant validation remains an explicit,
credential-safe manual activity and is never part of normal CI. See the
[Phase 7 NFL staging record](docs/phase-7-staging-validation.md), the
[Champions League staging record](docs/champions-league-staging-validation.md),
the
[Nations League staging record](docs/nations-league-a-staging-validation.md),
and the
[`docs/v0.7.0-beta.1-release-checklist.md`](docs/v0.7.0-beta.1-release-checklist.md).

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

The MIT License applies to the software, not to provider-derived runtime data,
private Outlook content, generated databases, credentials, backups, or source
documents. Before any repository visibility change, follow the
[public-repository data-safety policy](docs/public-repository-data-safety.md)
and run `python scripts/check_publication_safety.py`. Production source
subscriptions must remain at EUR 0 recurring cost unless a future explicit
operator decision changes that policy.
