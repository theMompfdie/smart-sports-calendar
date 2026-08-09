# ADR 0003: Select football-data.org for the Premier League

- Status: Accepted
- Date: 2026-08-09
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #72, #79
- Follows: ADR 0002
- Does not supersede: ADR 0001 for existing API-Football deployments

## Context

ADR 0002 rejected the official ECAL calendar because its public terms do not
permit the intended automated retrieval. The next candidate needed to provide
a permitted, deterministic, low-cost source for one complete Premier League
season without weakening the provider-neutral architecture in #72.

football-data.org API v4 publicly includes Premier League fixtures in its free
tier. Its terms allow a registered key for one application, require credential
confidentiality and visible attribution, and prohibit continuing to reference
obtained football data after subscription cancellation.

## Decision

Select `football-data.org` API v4 as the single authoritative writer for the
2026/27 Premier League in `v0.4.5-beta.1`, subject to all conditions in the
qualification record.

The live, read-only qualification observed competition `PL`/`2021`, season
`2502`, 20 teams, and 380 distinct matches. Two fingerprint-bearing snapshots
separated by 60 seconds produced the same SHA-256 identity fingerprint and the
same scope, status, kickoff-boundary, and source-update aggregates.

Implementation must use stable provider match IDs, fail closed on any
incomplete snapshot, preserve last-known-good state, and require two complete
380-match snapshots before absence can become removal evidence. It must not
perform automatic failover or combine fields from multiple providers.

## Mandatory conditions

- Display `Football data provided by the Football-Data.org API` visibly while
  provider-derived data is served.
- Keep the API key in the operator-controlled secret store and out of code,
  logs, evidence, and CI.
- Enforce the configured request budget even when optional quota headers are
  absent; retry HTTP 429 with bounded backoff.
- Use synthetic test payloads only unless explicit fixture-reuse permission is
  obtained later.
- Before subscription cancellation takes effect, disable retrieval and either
  re-source every served fixture from an approved source or remove the derived
  Outlook events and provider-derived persisted data through a scoped,
  backed-up operator procedure.
- Do not import logos, crests, photos, or other separately protected media.

## Consequences

- Issue #74 may implement provider-neutral source authority and scheduling.
- Issue #76 implements the football-data.org adapter and Premier League
  canonical import after #74 is complete.
- Issue #63 must use this source for the isolated live staging gate.
- API-Football remains a supported legacy source but is not an automatic
  Premier League fallback.
- Free-tier schedule delay is accepted for calendar synchronization; live
  scores and statistics remain out of scope.

## Alternatives considered

### ECAL official calendar

Rejected by ADR 0002 because the published terms prohibit the intended
automated collection workflow.

### API-Football

Retained as an implemented fallback and potential bootstrap source. It was not
selected for this release because football-data.org provides the required
Premier League fixture scope on a permitted free tier with a smaller API
surface.

### Transfermarkt scraping

Rejected. Undocumented scraping is not an authorized ingestion contract.

Detailed evidence and operating constraints are recorded in
[`../football-data-qualification.md`](../football-data-qualification.md).
