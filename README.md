# SMART Sports Calendar

> A containerized synchronization service that automatically imports sports fixtures and events from multiple providers into Microsoft Outlook calendars using Microsoft Graph.

---

## Project Vision

SMART Sports Calendar is designed to become a reliable, extensible, and fully automated sports calendar synchronization platform.

The goal is to provide a single Outlook calendar containing all relevant sports events, automatically synchronized with official data sources, including schedule changes, postponed matches, cancellations, and newly announced fixtures.

The application is built with a strong focus on:

- Reliability
- Maintainability
- Extensibility
- Infrastructure as Code
- Containerized deployment
- Long-term support

---

## Planned Features

### Microsoft 365 Integration

- Microsoft Graph API
- Dedicated Outlook calendar
- Automatic event creation
- Automatic event updates
- Automatic event cancellation handling
- Outlook categories
- Rich event descriptions
- Time zone handling
- Reminder support

---

### Supported Competitions (Planned)

#### Austria

- Austrian Bundesliga
- ÖFB Cup

#### Germany

- Bundesliga
- 2. Bundesliga
- DFB Pokal

#### England

- Premier League
- Championship
- FA Cup
- EFL Cup

#### UEFA

- Champions League
- Europa League
- Conference League
- Nations League
- European Championship Qualification

#### United States

- NFL

Additional competitions can be added through a modular provider architecture.

---

## Architecture

```
                    Sports Providers
                           │
                           ▼
                  Provider Normalization
                           │
                           ▼
                    Synchronization Engine
                           │
                           ▼
                      SQLite Database
                           │
                           ▼
                 Microsoft Graph API
                           │
                           ▼
                Microsoft Outlook Calendar
```

---

## Design Principles

The application follows a modular architecture.

Each component has a single responsibility.

- Provider Layer
- Normalization Layer
- Database Layer
- Synchronization Engine
- Microsoft Graph Layer
- Configuration Layer

This allows adding new competitions or sports without changing the synchronization logic.

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.13 |
| Container | Docker |
| Management | Portainer |
| Database | SQLite |
| API | Microsoft Graph |
| Authentication | MSAL |
| Configuration | YAML |
| Logging | Python Logging |
| Version Control | Git + GitHub |

---

## Project Structure

```
smart-sports-calendar/

app/
    graph/
    providers/
    database/
    scheduler/
    models/
    config/
    logging/

config/

docs/

tests/

compose.yaml
Dockerfile
requirements.txt
README.md
```

---

## Deployment

The application is designed to be deployed on any Docker host.

Typical environments include:

- Ubuntu Server
- Docker Engine
- Portainer
- Docker Compose

The entire application should be deployable within minutes by cloning the repository and starting the Docker stack.

---

## Development Workflow

```
feature/*
        │
        ▼
develop
        │
        ▼
main
        │
        ▼
Production
```

- **main** contains stable releases.
- **develop** contains the current development state.
- Feature branches are merged into **develop** before being released.

---

## Roadmap

### Phase 1

- Project foundation
- Docker
- SQLite
- Logging
- Configuration

### Phase 2

- Microsoft Graph Authentication
- Outlook Calendar Discovery

### Phase 3

- Event Synchronization Engine

### Phase 4

- Premier League Provider

### Phase 5

- Bundesliga Providers

### Phase 6

- UEFA Competitions

### Phase 7

- NFL Provider

---

## Project Goals

- Fully automated synchronization
- No duplicate events
- Automatic handling of rescheduled matches
- Modular provider architecture
- Easy migration to new infrastructure
- Simple deployment using Docker and Portainer
- Minimal maintenance effort

---

## License

MIT License
