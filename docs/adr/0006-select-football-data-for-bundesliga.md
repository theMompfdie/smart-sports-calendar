# ADR 0006: Select football-data.org for the German Bundesliga

- Status: Accepted
- Date: 2026-08-17
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #104, #108, #110, #114
- Follows: ADR 0005
- Supersedes in part: ADR 0005's conditional Bundesliga gate
- Does not authorize: live staging, release, or production use

Implementation status: issue #114 implements the approved adapter and runtime
boundary. This ADR still does not by itself authorize live staging, release, or
production use.

## Context

ADR 0005 selected the 2026/27 German Bundesliga as the first Phase 5
implementation candidate, conditional on contractual, plan, lifecycle, and
live-validation gates. Public coverage alone could not prove a complete,
stable, removal-capable season.

football-data.org API v4 includes Bundesliga fixtures in its Free plan. The
competition is a regular 18-team, 34-matchday double round robin, allowing an
unfiltered 306-match season to use the `complete_season` observation scope
defined by ADR 0004.

## Decision

Select football-data.org API v4 competition `BL1` / 2002 as the sole proposed
authoritative writer for the 2026/27 German Bundesliga, subject to every
condition in the qualification record.

Two operator-controlled, read-only observations on 2026-08-17 were separated
by about 23 minutes and 41 seconds. Both independently passed the curated
profile and reported:

- API version `v4` and season ID `2522`;
- season dates 2026-08-28 through 2027-05-22;
- 18 distinct teams and 306 distinct positive match IDs;
- 261 `SCHEDULED` and 45 `TIMED` matches;
- one complete match page and three requests;
- the same kickoff boundaries and latest source-update timestamp; and
- SHA-256 fixture-identity fingerprint
  `034542c2c3c5df368547f2e54108ca4810a68eed44b06860204be0e945c116a9`.

The optional quota header was absent in both observations. The operator
separately confirmed the active Free plan and its documented limit of 10
requests per minute. A normal snapshot uses three requests; one immediate
complete retry uses six and retains four requests of per-minute headroom. The
initial polling interval is six hours.

Qualification authorizes creation of a separate implementation issue. It does
not create catalog records, mappings, source assignments, jobs, database
writes, Outlook events, staging approval, or a release claim.

## Mandatory conditions

- Keep exactly one authoritative source assignment for Bundesliga season
  2026/27. Alternatives and legacy mappings may be verification or bootstrap
  sources only, never automatic failover or simultaneous writers.
- Accept removal evidence only from two complete, successful, unfiltered
  306-match authoritative snapshots. Any stale, partial, filtered, empty,
  malformed, failed, or wrong-scope response preserves last-known-good state.
- Preserve the curated `BL1` / 2002, 18-team, 306-match, 34-matchday profile.
  Operator-supplied competition identities or expected counts are prohibited.
- Enforce the 10-request-per-minute Free-plan limit independently because the
  optional quota header may be absent. Classify HTTP 429 as retryable and use
  bounded backoff without overlapping jobs.
- Display `Football data provided by the Football-Data.org API` visibly while
  provider-derived data is served.
- Keep credentials in the operator-controlled secret store and out of code,
  logs, evidence, screenshots, issues, CI, and URLs.
- Use synthetic test payloads unless explicit fixture-reuse permission is
  obtained. Do not import logos, crests, photos, or other separately protected
  media.
- Before subscription cancellation takes effect, disable retrieval and either
  qualify a replacement or remove derived Outlook events and provider-derived
  persisted data through a scoped, backed-up operator procedure.
- Revalidate coverage, season identity, completeness, plan, quota, terms, and
  attribution before staging and after material provider or season changes.

## Consequences

- A focused Bundesliga implementation issue may now be created under #104.
- Existing football-data.org infrastructure may be generalized without
  weakening the Premier League profile or its released behavior.
- API-Football remains ineligible as a new authority without written
  competition-specific rights clearance.
- No database migration is approved by this decision. A later implementation
  must prove whether the existing catalog and source-mapping schema suffice.
- Bundesliga remains qualified but not implemented, staged, or released until
  its separate delivery and validation gates pass.

## Alternatives considered

### Approve from public coverage alone

Rejected because coverage does not prove complete retrieval, identity
stability, lifecycle semantics, freshness, pagination, or safe removals.

### Select API-Football

Rejected as a new authority because no competition-specific written rights
clearance is recorded under the current API-Sports terms.

### Select Sportmonks

Not selected for this regular-season league because it requires a paid choice
and additional adapter work without improving the qualified calendar scope.

### Enable multiple authoritative writers

Rejected because simultaneous writers or automatic failover would make
identity, ownership, and removal evidence ambiguous.

Detailed evidence and operating constraints are recorded in
[`../football-data-qualification.md`](../football-data-qualification.md).
