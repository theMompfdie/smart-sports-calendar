# Provider-to-Outlook End-to-End Testing

## Purpose

Phase 4.7 verifies that the Phase 4 production boundaries compose correctly as
one deterministic workflow. The suite starts with sanitized API-Football HTTP
response envelopes and finishes at a recording Microsoft Graph boundary after
using the real client, adapters, application services, migrations,
repositories, payload builder, and synchronization orchestration.

No test uses a live provider, Microsoft Graph endpoint, credential, token, or
network connection.

## Tested path

```text
Sanitized API-Football JSON
             |
             v
Scripted HTTP transport boundary
             |
             v
API-Football client, pagination, DTOs, and adapters
             |
             v
Catalog mapping and fixture normalization
             |
             v
Provider import runtime and migrated SQLite
             |
             v
Synchronization query, payload builder, and event synchronizer
             |
             v
Recording Microsoft Graph boundary
```

The harness is implemented in
`tests/integration/provider_outlook_support.py`. The acceptance scenarios live
in `tests/integration/test_provider_to_outlook_end_to_end.py`.

## Boundaries and fixtures

The provider boundary reuses the repository-owned fixtures in
`tests/fixtures/api_football`. These envelopes are minimal, deterministic, and
sanitized. The scripted transport reconstructs real paginated HTTP responses,
returns rate-limit headers, and records only request paths, query values, and
header names. It deliberately does not retain authentication header values.

The Graph boundary records create, update, and delete operations in memory. It
models Graph transaction-ID idempotency so a failed create retry or fixture
reappearance cannot create a duplicate Outlook identity. All application and
domain services between these two external boundaries are production classes.

Every scenario creates an empty database and runs the production migration
runner. No copied schema or test-only database initializer is used.

## Scenario matrix

The suite verifies:

- initial fixture discovery and Outlook creation;
- unchanged-cycle idempotency without database or Graph duplication;
- complete multi-page fixture retrieval;
- discovery of an additional fixture;
- kickoff rescheduling with stable canonical and Outlook mappings;
- cancellation, correction, postponement, and reactivation;
- two-observation authoritative removal and Outlook deletion;
- identity-preserving reappearance through the persistent transaction ID;
- malformed and partially failed collections without canonical mutation or
  removal evidence, followed by idempotent calendar revalidation;
- real SQLite persistence and provider-run finalization failures;
- retry convergence after provider and Graph failures;
- separate provider-import and calendar-sync reporting;
- sanitized scope, attempt, rate-limit, error, request, and log diagnostics.

## Removal and reappearance behavior

A confirmed provider removal keeps the canonical event and source mapping as
history by setting `deleted_at`. The synchronization layer detects the deleted
canonical event, marks its calendar mapping for deletion, and deletes the
remote event. The calendar mapping remains as durable history.

If the same provider fixture reappears, the canonical event and source mapping
are restored in place. The deleted calendar mapping returns to `pending`,
clears stale remote content state, and reuses its persistent transaction ID for
retry-safe Outlook creation. This closes the integration gap discovered by the
Phase 4.7 suite without changing provider identity or physically deleting
canonical data.

## Running the tests

Run only the Phase 4.7 end-to-end suite:

```bash
pytest -q tests/integration/test_provider_to_outlook_end_to_end.py
```

Run all integration tests:

```bash
pytest -q tests/integration
```

Run the complete project validation:

```bash
ruff format --check .
ruff check .
pytest
docker compose config --quiet
```

## Remaining limitations

The suite proves deterministic application composition and infrastructure
requests, not provider subscription behavior or Microsoft Graph behavior in a
real tenant. The separate, credential-safe live procedure is documented in
[`phase-4-live-validation.md`](phase-4-live-validation.md). Release gating and
publication steps are documented in
[`phase-4-release-checklist.md`](phase-4-release-checklist.md); neither live
calls nor release publication occurs in normal CI.
