# v0.3.0-alpha.1 – Phase 3 Outlook Synchronization Engine

This pre-release completes Phase 3 and adds the complete Outlook synchronization engine on top of the persistent domain and repository layer introduced in Phase 2.

## Highlights

- Synchronization orchestration with configurable batch processing
- Outlook payload construction from canonical sports events
- Event creation, unchanged detection, updates, cancellations, and deletions
- Content-hash based change detection to avoid unnecessary Graph calls
- Persistent Outlook mapping and synchronization lifecycle state
- Per-event failure isolation so a single error does not abort the batch
- Retry support for pending and failed mappings
- Startup recovery for interrupted synchronization runs
- Scheduler integration and persistent run reporting
- Idempotent Graph event creation using stable, persisted transaction IDs

## Reliability

Graph create requests use a persistent `transactionId`. A retry therefore reuses the same identifier if Graph accepted the original request but the local process failed before the Outlook event ID was saved. This prevents duplicate Outlook events without creating a second mapping.

Synchronization runs persist progress counters, results, and errors. Interrupted `running` runs are recovered on startup, while failures remain isolated to the affected event.

## Validation

- 303 automated tests passed
- Ruff linting passed
- Ruff formatting check passed
- Docker Compose configuration validated
- Lifecycle integration tests use a migrated SQLite database with Microsoft Graph mocked

## Known Limitations

- No external sports data provider is integrated yet.
- Synchronization locking is process-local.
- Multiple application instances must not synchronize the same calendar/database concurrently.
- Distributed coordination remains outside the scope of this release.
- This is an alpha pre-release and is not yet production-ready.

## Next Phase

Phase 4 adds the first football data provider, starting with Premier League fixtures, provider mappings, normalization, and incremental imports.

## Upgrade Notes

- Back up the persistent SQLite volume before upgrading.
- Database migrations run during application startup.
- Configure `OUTLOOK_CALENDAR_ID` or ensure `OUTLOOK_CALENDAR_NAME` can be resolved.
- Review `SYNCHRONIZATION_BATCH_LIMIT` before enabling scheduled synchronization.
- Do not run multiple synchronizing instances against the same calendar/database.
