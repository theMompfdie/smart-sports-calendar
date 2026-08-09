# SMART Sports Calendar v0.4.5-beta.1

`v0.4.5-beta.1` is the authoritative-source and isolated-deployment beta. It
supersedes the unissued `v0.4.0-beta.1` plan and builds on the released
`v0.4.0-alpha.1` synchronization engine.

## Highlights

- Adds provider-neutral source registration, scheduling, and one authoritative
  writer per competition and season.
- Qualifies football-data.org API v4 as the authoritative source for the
  2026/27 Premier League season.
- Imports the complete 20-team, 380-fixture Premier League schedule through
  stable provider identities and deterministic canonical mappings.
- Synchronizes provider imports and Outlook batches on independent recurring
  schedules so calendar convergence does not consume provider quota.
- Supports isolated staging and production Docker/Portainer stacks with
  distinct names, volumes, SQLite databases, Outlook calendars, credentials,
  configuration, and logs.
- Renders the reviewed source attribution in Outlook event bodies:
  `Football data provided by the Football-Data.org API`.

## Added

- Provider contracts, source roles, source scopes, source assignments, and
  migration `007_create_source_assignments`.
- Secret-safe football-data.org qualification and staging-evidence operations.
- Complete-snapshot validation for scope, count, identity, status, freshness,
  duplicate detection, and removal evidence.
- Credential-free end-to-end coverage from provider-shaped data through SQLite
  to mocked Microsoft Graph.
- Project-scoped Compose resources and automated three-instance isolation
  validation.
- Explicit synchronization counters for create, update, unchanged, cancel,
  delete, defer, and failure decisions.

## Changed and fixed

- Calendar synchronization is an independent recurring scheduler job and
  rotates stable mappings to prevent batch starvation.
- Graph payloads provide a fallback end time for fixtures without an explicit
  end value.
- Calendar startup validation safely reports the configured target name without
  exposing its identifier.
- API-Football catalog requests no longer send unsupported pagination input.
- Existing API-Football mappings coexist non-destructively with the selected
  football-data.org authority.
- Attribution changes update existing Outlook events once while preserving
  transaction IDs; following cycles are unchanged.

## Live staging validation

The dedicated staging stack validated:

- Microsoft Graph authentication and the intended isolated Outlook calendar;
- one active football-data.org authority for
  `football/premier_league/2026_27`;
- 380 active fixtures, 380 source mappings, and 380 synchronized calendar
  mappings;
- an intact SQLite database through restart, backup, and restore exercises;
- a stable 380-fixture provider snapshot with no duplicate or destructive
  changes;
- creation and convergence of exactly 380 Outlook events;
- a one-time attribution payload migration followed by a control cycle with
  `updated=0`, `unchanged=100`, and `failed=0`;
- visible reviewed source attribution in an Outlook event;
- secret-safe logs and evidence output.

## Known limitations

- This is a beta pre-release and is not approved for unattended production
  promotion.
- The controlled live provider network-failure exercise was explicitly
  deferred to issue #101. Deterministic retry and fail-closed tests pass, but
  that is not represented as completed live evidence. Manual production
  promotion remains blocked until #101 is complete.
- Only the 2026/27 Premier League scope is released through football-data.org.
- There is no automatic provider failover, field aggregation, or heuristic
  cross-source merge.
- The official ECAL feed is excluded from automated ingestion under its current
  public terms. Transfermarkt scraping and undocumented website APIs are also
  excluded.
- The free football-data.org tier may provide delayed schedule or score data.
  This beta is fixture-calendar focused and does not add standings, lineups,
  odds, or historical enrichment.

## Deployment and upgrade notes

- Package version: `0.4.5b1`.
- Back up the SQLite database before upgrading and verify the backup outside
  the writable application volume.
- Migration `007_create_source_assignments` is forward-only, deterministic, and
  idempotent. Running older code against the migrated database is not a
  supported rollback.
- Staging may follow `develop` during normal development but must be frozen to
  the immutable candidate tag during release qualification.
- Production must use a distinct Portainer stack and explicitly approved tag;
  it must never track `develop` or share staging state.
- API tokens and Microsoft credentials remain external Portainer configuration
  and must never enter Git, images, logs, issues, or release artifacts.

## Verification

- `ruff check .`
- `ruff format --check .`
- `pytest` — 566 passed before release preparation
- Docker Compose configuration validation
- Docker image build and health validation in GitHub Actions
- credential-free multi-instance validation
- GitHub Actions checks on the release pull request

The signed release tag must point to the reviewed `main` merge commit. GitHub
must publish this version as a pre-release, not as a stable release.
