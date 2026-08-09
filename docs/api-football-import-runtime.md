# API-Football Import Runtime

## Boundary

Phase 4.6 implements the operational runtime tracked by GitHub issue #53. It
composes the existing API-Football catalog, fixture normalization, Phase 4.5
persistence, and Outlook synchronization boundaries. It does not change the
provider HTTP retry algorithm or the canonical fixture reconciliation rules.

When API-Football is disabled, the calendar synchronization job continues
without provider calls or provider-import run records. When enabled, one
provider job executes in this order:

1. recover interrupted `provider_import` run records once after startup;
2. refresh and validate the mapped Premier League catalog;
3. fetch and validate the complete current-season fixture collection;
4. normalize the collection and construct a bounded authoritative UTC scope;
5. atomically import the normalized fixtures;
6. finalize the persistent provider-import report;

Any failure before step 6 produces a failed provider-import run and no
canonical changes. Outlook synchronization is independently scheduled and
does not roll back an already committed canonical import.

## Scheduling and overlap

`SOURCE_JOBS_JSON.interval_seconds` controls each provider job interval.
`API_FOOTBALL_IMPORT_INTERVAL_SECONDS` remains the legacy provider interval
when source-job orchestration is not configured. `HEARTBEAT_INTERVAL` controls
the independent calendar synchronization job and defaults to 300 seconds.
Provider jobs are registered before the calendar job so the startup import is
available to the first synchronization batch. Subsequent batches can drain a
backlog without repeating provider requests.

The provider runtime uses a non-blocking process-local lock. A concurrent call
is skipped explicitly and cannot create a second run. The scheduler uses the
shutdown event for its wait, so SIGINT or SIGTERM interrupts the wait without
waiting for the complete configured interval.

This lock is intentionally not distributed. Multiple application instances
must not operate on the same database and target calendar concurrently.

## Import scope

Each operational import is a complete, unfiltered, authoritative snapshot for
the mapped current Premier League season. Its scope records:

- canonical competition and season IDs;
- UTC boundaries derived from the canonical season dates;
- provider fetch time as the observation time;
- a deterministic SHA-256-derived observation ID;
- completeness, filtering, and authority flags.

Pagination and validation finish before the Phase 4.5 transaction begins. A
partial collection therefore never becomes removal evidence.

## Persistent reporting

Migration `006_extend_provider_import_runs.sql` preserves existing run history,
adds the dedicated `provider_import` run type, and adds `items_deferred`.
Provider and calendar runs remain independently queryable.

Successful provider runs persist counts for processed, created, updated,
unchanged, cancelled, deleted, deferred, and failed items. Metadata contains
the sanitized scope, page count, aggregate request-attempt count, and available
daily/minute rate-limit and retry-after values.

Failed runs persist a stable exception category rather than arbitrary exception
text. Interrupted `running` imports are deterministically converted to
`failed` during the next runtime startup recovery.

## Retry and security

The runtime adds no retry loop. Timeouts, network failures, server errors, and
rate limits continue to use the bounded Phase 4.2 retry/backoff implementation.
The collection reports how many HTTP attempts were consumed across its pages.

API keys remain external configuration and are transmitted only in the
`x-apisports-key` header. Run metadata and runtime logs never contain keys,
tokens, authorization headers, or raw secret-bearing URLs.

## Validation boundary

Automated tests use mocked provider and Graph boundaries plus migrated SQLite.
They cover scope construction, counters, diagnostics, failures, recovery,
overlap, disabled mode, scheduler ordering, graceful shutdown, and the
independent provider-import and Outlook synchronization boundaries. Phase 4.7
still owns the complete representative provider-payload-to-SQLite-to-mocked-
Graph end-to-end suite.
