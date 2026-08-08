# ADR 0001: Select API-Football for the Initial Football Integration

- Status: Accepted
- Date: 2026-08-08
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #42, #43

## Context

SMART Sports Calendar needs one external football data provider for the first
Premier League import. Provider-specific authentication, HTTP behavior,
pagination, payloads, and status values must remain outside the canonical
SQLite repositories and the existing Outlook synchronization engine.

The decision must support a low-volume, server-side calendar synchronization
service rather than a live-score product. It must be reproducible from current
technical and commercial evidence before provider-specific code is introduced.

## Decision drivers

Mandatory drivers are:

- current Premier League competition, season, team, and fixture coverage;
- stable provider identifiers;
- explicit lifecycle states, including postponement, cancellation, and
  abandonment;
- timezone-safe kickoff data;
- deterministic filtering and pagination;
- published quotas and observable rate-limit state;
- terms suitable for a derived application without raw-feed resale;
- representative payloads suitable for sanitized offline tests; and
- a price proportionate to a single-competition personal service.

Desirable drivers are a free development tier, simple server-side
authentication, explicit update guidance, broad future coverage, and a small
adapter surface.

The complete evaluation and dated source list are in
[`../provider-evaluation.md`](../provider-evaluation.md).

## Considered options

### API-Football

API-Football v3 documents stable fixture IDs, detailed fixture states, UTC and
offset-aware kickoff representations, query filters, paging metadata, quota
headers, and clear daily/per-minute limits. Its paid Pro plan is sufficient for
Premier League production use at a lower entry price than Sportmonks.

### football-data.org

football-data.org v4 has the simplest fixture-focused surface and explicitly
includes Premier League schedules in its free tier. Its public documentation
provides UTC timestamps and stable resource IDs. It was not selected because
publicly discoverable usage, storage, attribution, and redistribution terms
were insufficiently explicit for the mandatory commercial review, and its
status vocabulary has no distinct abandoned state.

### Sportmonks Football API

Sportmonks v3 has strong documentation, rich typed entities, broad coverage,
and explicit rate-limit telemetry. It was not selected because Premier League
access requires a paid plan starting above API-Football's entry price, while
its richer schema and include model add complexity without benefiting the
initial fixture-calendar scope.

## Decision

Use **API-Football v3** as the first provider for the Premier League import.

The production planning baseline is the directly purchased API-Football Pro
plan. The free plan is acceptable only for development and evaluation after the
required Premier League data has been confirmed available. No application
behavior may assume that free-tier coverage is permanent.

The provider adapter will later authenticate with a secret supplied through
validated environment configuration. It will translate the API-Football
response envelope and DTOs into the provider-independent contract defined in
[`../provider-integration-contract.md`](../provider-integration-contract.md).
Neither the API key nor a secret-bearing request URL may be logged or stored in
test fixtures.

## Rationale

API-Football offers the strongest fit for the first integration because:

1. its documentation explicitly says a fixture ID is unique and does not
   change;
2. its fixture statuses directly distinguish not-started, postponed,
   cancelled, abandoned, suspended, completed, technical-loss, and walkover
   cases;
3. its fixture timestamp supports unambiguous UTC normalization;
4. its response envelope exposes paging and application-level errors;
5. rate-limit state is available through documented daily and per-minute
   headers;
6. its terms explicitly permit building applications while prohibiting raw
   data resale; and
7. its entry paid plan is proportionate to the initial single-competition use
   case.

The decision prioritizes lifecycle correctness and contractual clarity over a
zero-cost production plan.

## Consequences

### Configuration

Later issues will need explicit provider configuration for API base URL, API
key, connect/read timeouts, plan-aware quota thresholds, and import scope. The
key must be injected through the environment and redacted from all diagnostic
output.

### Implementation

- API-Football transport DTOs stay in a provider-specific module.
- Provider DTOs never enter canonical repositories or Outlook synchronization.
- HTTP 200 is not sufficient for success; the response envelope's `errors`,
  `paging`, and `response` fields must be validated.
- Pagination must finish before a fetch is considered complete.
- Fixture identity is based on the provider fixture ID stored through the
  existing data-source and source-mapping model.
- Removed-fixture detection is a reconciliation concern and is permitted only
  after a complete successful authoritative fetch.
- Logos and image URLs are not imported in the initial scope.

### Testing

Representative responses will be manually captured from provider documentation
or an explicitly authorized development call in a later issue, sanitized,
reviewed, and committed as static fixtures. Normal CI will use only those files
and mocked transport boundaries. Live provider and Microsoft Graph calls remain
outside automated CI.

### Deployment and operations

- Production is expected to require a paid plan.
- Daily and per-minute remaining quota must be observable.
- Imports must be conservative when quota is low.
- Shared outbound IP infrastructure can reduce effective rate capacity.
- Provider availability and data correctness are not guaranteed by the terms;
  previously valid canonical data must survive transient or partial failures.

## Known risks and assumptions

- Prices, quotas, coverage, and terms can change.
- Free-tier Premier League access is not assumed.
- Provider data can be late, incomplete, or incorrect.
- A fixture absent from one incomplete response is not evidence of removal.
- The provider does not expose a dedicated removed status.
- Provider status values may expand without notice and unknown values must fail
  validation rather than silently map to `scheduled`.
- Competition logos, team crests, and other media can require third-party rights
  and are excluded.
- The project assumes the provider's documented immutable fixture ID remains
  stable across rescheduling.

## Reassessment triggers

Reevaluate the decision if any of the following occurs:

- Premier League fixtures are removed from the subscribed plan;
- fixture IDs change across rescheduling or provider corrections;
- required lifecycle changes cannot be detected reliably;
- pricing or quota changes make scheduled imports uneconomical;
- contractual terms no longer permit the intended derived application;
- API v3 is deprecated without a compatible migration path;
- reliability or freshness repeatedly violates the import service objective;
- another provider materially reduces lifecycle ambiguity or operational risk;
  or
- later competition phases require coverage unavailable on acceptable terms.

## Scope boundary

This ADR selects a provider and defines consequences only. It introduces no
credentials, HTTP client, retry implementation, schema change, source
registration, import, scheduler behavior, or Outlook synchronization change.
