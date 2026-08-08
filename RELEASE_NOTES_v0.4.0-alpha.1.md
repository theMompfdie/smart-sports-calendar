# v0.4.0-alpha.1 – Phase 4 Initial Football Provider

This pre-release completes Phase 4 by adding the first external football
provider and the complete Premier League fixture-to-Outlook workflow. It
builds on the provider-independent Outlook synchronization engine delivered in
`v0.3.0-alpha.1`.

## Highlights

- API-Football v3 selected through a documented evidence-based evaluation and
  architecture decision record
- validated, secret-safe provider configuration and HTTPS transport
- explicit timeouts, response validation, pagination, bounded retry/backoff,
  and rate-limit handling
- deterministic Premier League competition, season, and team source mappings
- timezone-aware fixture normalization with explicit home/away and lifecycle
  semantics
- atomic, idempotent canonical fixture import with stable provider identities
- incremental discovery, kickoff updates, cancellation, postponement,
  correction, removal confirmation, and identity-preserving reappearance
- scheduled provider imports with persistent counters, diagnostics, recovery,
  and successful-import handoff to Outlook synchronization
- deterministic provider-payload-to-SQLite-to-mocked-Graph end-to-end coverage

## Reliability and behavior changes

- Repeated unchanged imports do not duplicate canonical events, participants,
  source mappings, calendar mappings, or Outlook items.
- A fixture keeps the same canonical and Outlook identity across rescheduling
  and lifecycle changes.
- Removal requires two distinct complete authoritative observations and keeps
  canonical history instead of physically deleting it.
- Reappearing fixtures revive the existing calendar mapping and reuse its
  persistent Graph transaction ID.
- Partial, malformed, or failed provider collections create no removal
  evidence and do not start Outlook synchronization.
- Provider import and calendar synchronization results remain separately
  queryable in persistent run history.
- Graph failure cannot roll back a completed provider import; later retries
  converge without duplicate state.

## Correctness fixes

The Phase 4 end-to-end suite identified and fixed two integration gaps:

- confirmed canonical removals now become explicit Outlook deletions; and
- a fixture that reappears after removal revives its deleted calendar mapping
  in place instead of creating a second mapping identity.

Both behaviors have focused repository and synchronization regression tests in
addition to the complete end-to-end scenarios.

## Configuration and operations

- API-Football remains disabled by default.
- Enabling it requires `API_FOOTBALL_API_KEY` and uses
  `API_FOOTBALL_IMPORT_INTERVAL_SECONDS` as the scheduler interval.
- `OUTLOOK_CALENDAR_ID` is required and must target only the dedicated SMART
  Sports Calendar.
- Provider authentication values are supplied through environment/deployment
  secrets and are never stored in the image or repository.
- The runtime lock is process-local. Exactly one instance may operate on one
  SQLite database and target calendar.
- SQLite remains stored in the persistent `smart_sports_data` volume.

See `docs/deployment.md` for deployment, backup, upgrade, rollback, diagnostics,
and single-instance requirements. See `docs/phase-4-live-validation.md` for the
separate credential-safe live-validation procedure.

## Validation

- 477 deterministic automated tests pass locally
- Ruff linting passes
- Ruff formatting verification passes
- Docker Compose configuration validates
- provider and Microsoft Graph boundaries are mocked in normal automated tests
- the real provider client, adapters, normalization, import runtime,
  migrations, repositories, and synchronization services are exercised by the
  Phase 4.7 end-to-end suite

GitHub Actions and final release-branch validation must be green before these
notes are used to publish the pre-release.

## Upgrade notes

- Back up the persistent SQLite database while the application is stopped.
- Review `.env` against `.env.example`; do not overwrite secrets with example
  placeholders.
- Keep `API_FOOTBALL_ENABLED=false` for the first upgraded startup.
- Database migrations run automatically and idempotently during startup.
- Schema downgrade is not supported; restoring the pre-upgrade database backup
  is required for a full rollback.
- Validate Graph authentication and the dedicated calendar before enabling
  provider imports.
- Enable API-Football only after reviewing subscription coverage and quota.

## Known limitations

- This is an alpha pre-release and is not production-ready.
- Normal CI makes no live API-Football or Microsoft Graph calls.
- Real provider subscription behavior and tenant-specific Graph behavior
  require the separate manual validation checklist.
- Only the mapped current English Premier League season is imported.
- Live scores, results, standings, statistics, odds, and additional
  competitions/providers are not included.
- Synchronization and provider-import locking is process-local; distributed
  multi-instance coordination is not implemented.
- No administrative user interface is included.
- GHCR image publication is not implemented; the current deployment builds
  from reviewed source.

## Release status

Published as the Phase 4 GitHub pre-release from the verified `main` commit
tagged `v0.4.0-alpha.1`.
