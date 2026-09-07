# SMART Sports Calendar - v1.0.0

Sports fixtures in a dedicated Microsoft Outlook calendar, kept current by
qualified providers and reviewed manual imports. The service runs in Docker,
stores identities in SQLite and writes appointments through Microsoft Graph.

<!-- Mit tatkräftiger Unterstützung meines JARVIS. -->

## Version 1.0.0

Version 1.0.0 combines qualified automated sports schedules with reviewed
manual imports, including the bounded Europa League delivery. Completed-season
retirement preserves calendar history, and strict provider validation keeps
last-known-good data on failures.

Start with the [installation and upgrade guide](docs/installation.md).
Read the [v1.0.0 release notes](docs/releases/v1.0.0.md) for changes, accepted
scope and deployment considerations. The [release index](docs/releases/README.md)
and [GitHub releases][releases] provide the version history.
Production promotion is a separate operator action.

## What it does

- Imports supported fixture schedules and preserves stable provider/manual IDs.
- Creates and updates Outlook appointments without duplicates on unchanged runs.
- Handles explicit cancellations and qualified lifecycle changes. Partial
  observations never turn missing fixtures into cancellations or deletions.
- Keeps last-known-good data when a provider fails; other jobs continue.
- Adds sport icons, competition categories and deterministic HTML descriptions.
- Supports competition/team reminders and reviewed optional media assets.
- Imports operator-reviewed schedules with preview, approval and audit receipts.
- Creates separate review appointments to remind the operator to check manual
  schedules; these reminders do not retrieve or approve updates automatically.
- Deactivates completed seasons without removing existing fixture or review
  appointments. Late corrections require explicit reactivation.

## Supported scope

Qualification is bounded by competition, season and stage. Enabling an adapter
alone does not enable every competition it could theoretically retrieve.
The accepted football season is **2026/27**; NFL is **2026 regular season**.

| Competition | Delivery | Boundary |
| --- | --- | --- |
| Premier League | football-data.org | Complete season |
| Bundesliga | football-data.org | Complete season |
| EFL Championship | football-data.org | 552 regular-season matches |
| DFB-Pokal | OpenLigaDB | Published cup fixtures |
| 2. Bundesliga | OpenLigaDB | Partial, removal disabled |
| ÖFB-Cup | Private official iCalendar | Partial, removal disabled |
| Champions League | OpenLigaDB | 144 league-phase fixtures |
| Nations League A | OpenLigaDB | 48 group-phase fixtures |
| NFL | nflverse | 272 games, weeks 1-18 |
| Austrian Bundesliga | Manual import | Approved stages |
| FA Cup and EFL Cup | Manual import | Approved stages |
| Conference League | Manual import | Approved stages |
| Nations League B/C/D | Manual import | Separate approved leagues |
| Europa League | Manual import | 144 league-phase fixtures |

Championship play-offs are excluded. The DFB-Pokal source uses partial
snapshots; missing fixtures are not removal evidence.

The [automated-source matrix](docs/phase-7-source-authority-matrix.md),
[manual preparation guide](docs/manual-import-preparation.md) and
[Europa League operations](docs/uefa-europa-league-delivery.md) provide details.
UEL later knockout packages require explicit reviewed stage authority when
published; future intent is not an enabled writer. Qualifying rounds are
excluded.
A fresh installation contains no private manual schedules or approvals.

Exactly one authoritative writer owns each competition/season or explicitly
reviewed disjoint stage boundary. API-Football remains an opt-in integration
foundation; it is not an additional default writer or automatic fallback.

## First calendar

You need a Microsoft 365 mailbox, an Entra application authorized for that
mailbox, a dedicated Outlook calendar, Docker Engine with Compose v2 and the
credentials for any selected provider. The
[step-by-step installation guide](docs/installation.md) covers calendar
provisioning, private configuration and a one-provider first synchronization.

Compose builds from the selected repository checkout. `IMAGE_TAG` names the
local image; it does not select source code or download a published image.
Use an immutable reviewed commit for staging and a verified release tag for
production. Keep staging and production databases, credentials and calendars
separate. Never run two owners against one writable database or calendar.

## Daily operation

Automated providers run at their configured intervals. Outlook synchronization
runs independently in bounded batches. A healthy container only proves the
health check passed; verify startup, provider runs and calendar convergence.
Use the [configuration reference](docs/deployment.md) for detailed settings.

For a manual competition:

1. Obtain a permitted schedule and prepare a schema-versioned package outside
   the runtime, preserving stable manual fixture IDs.
2. Submit it to the private inbox and inspect the worker's preview.
3. Approve that exact manifest and preview for this instance.
4. Wait for `APPLIED`, then verify the resulting Outlook appointments.
5. Process review reminders and corrections throughout the season.

Follow the [Docker-host workflow](docs/manual-import-workflow.md) and
[preparation guide](docs/manual-import-preparation.md). Synthetic repository
examples demonstrate the format and must not be mistaken for real schedules.
Missing entries in a partial package do not mean cancellation.

For a completed season, use the
[retirement cookbook](docs/season-retirement-cookbook.md). The owner must be
stopped for maintenance. Review completion evidence and the correction grace
period before deactivation. Preserve the configured authority and manual
profile; removing configuration is not season retirement. All existing fixture
and review appointments remain history until the operator deletes the calendar.
Reactivation resumes synchronization, so later approved corrections may update
those appointments. A new season needs a new qualified scope.

## Presentation and rights

Provision competition color categories manually in Outlook. The application
assigns category names; it does not manage mailbox category colors. Configure
[runtime reminders](docs/runtime-reminder-rules.md) through their supported
operations rather than editing SQLite.

Third-party logos are optional. The
[media registry](docs/media-asset-registry.md) requires explicit rights evidence
and approved assets. Text/icon fallback is supported. The MIT license covers
this code, not provider datasets, trademarks or third-party imagery. Keep
private feed URLs, source packages and media outside Git and release assets.

## Limits

- No live scores, standings, odds, statistics or automatic document extraction.
- No automatic authority failover, heuristic fixture merging or source scraping.
- No arbitrary season expansion, NFL play-offs or unqualified UEFA stages.
- No automatic creation of the target calendar or Outlook category palette.
- No automatic updates for manually maintained competitions.
- No general database downgrade; restore matching complete state for rollback.
- Upstream correctness is not guaranteed. Strict malformed-snapshot rejection
  remains enabled. The [accepted Championship recovery][recovery] retains
  the historical evidence limits.

## Development

Python 3.13 is the supported development/CI baseline. Install the development
requirements, which include the runtime requirements:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check app scripts tests
pytest
python scripts/check_publication_safety.py
```

On Windows activate `.venv\Scripts\Activate.ps1` instead. Normal tests use
synthetic data and mocked services; live qualification is a separate gate.
See [test runtime](docs/pytest-runtime.md) and the
[repository audit](docs/repository-audit-v1.0.0.md).

The architecture separates configuration, application services, repositories,
provider adapters, Graph access and synchronization. See the
[architecture
decisions](docs/adr/0015-import-reviewed-manual-fixture-manifests.md)
and [provider contract](docs/provider-integration-contract.md).

Changes flow through a focused branch into `develop`, then a reviewed release
PR into `main`. The operator creates signed commits and performs merges.
Do not publish a release until its documented gates pass.

## License

[MIT](LICENSE). Provider and asset rights are reviewed separately.

[releases]: https://github.com/theMompfdie/smart-sports-calendar/releases

[recovery]: docs/football-data-status-recovery.md
