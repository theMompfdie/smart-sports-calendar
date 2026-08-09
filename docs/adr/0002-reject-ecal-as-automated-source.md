# ADR 0002: Reject ECAL as an Automated Premier League Source

- Status: Accepted
- Date: 2026-08-09
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #72, #73
- Supersedes: the official-feed preference for Premier League in #72 only
- Does not supersede: ADR 0001's historical API-Football implementation choice

## Context

The `v0.4.5-beta.1` plan prefers an official competition calendar feed when it
can act as a deterministic and permitted server-side authority. The Premier
League links to a digital calendar delivered by ECAL and advertises all 380
fixtures with automatic reschedule updates.

Official provenance is necessary but not sufficient. SMART Sports Calendar
would periodically retrieve the subscription, parse its events, persist a
canonical copy, and write derived events to a dedicated Outlook calendar. That
workflow must be both technically deterministic and permitted by the delivery
service's terms.

## Decision

Do not use the ECAL Premier League subscription as an automated application
source without explicit written permission.

The public ECAL end-user terms allow personal use and expressly prohibit data
mining, robots, scraping, and similar data-gathering methods. The intended
scheduled server retrieval falls within the prohibited automation boundary.
The project therefore did not generate or inspect a personalized feed.

Evaluate `football-data.org` v4 next as the preferred low-cost Premier League
API candidate. Treat that as a new qualification decision, not implicit
approval. API-Football remains the implemented legacy provider until a
permitted replacement passes its own contract and staging gates.

## Consequences

- Issue #75 must not implement an ECAL adapter under the current public terms.
- No ECAL subscription URL, subscriber identifier, or payload may enter source
  control, tests, logs, run metadata, screenshots, issues, or pull requests.
- Issue #63 cannot use ECAL to satisfy the real-data staging gate.
- The Premier League source choice remains unresolved until the next candidate
  is qualified or written ECAL permission is obtained.
- The provider-neutral orchestration boundary in #74 remains valid and must not
  encode ECAL-specific behavior.
- If a future authorized iCalendar source is selected, it must meet the strict
  snapshot, identity, time, lifecycle, conditional-request, and fail-closed
  rules in the qualification record.

## Alternatives considered

### Treat the official link as sufficient permission

Rejected. The link invites an end user to subscribe to a personal calendar; it
does not grant an application the right to automate collection and reuse.

### Inspect a personalized feed before deciding

Rejected. Technical curiosity does not justify creating or polling a service
subscription for a prohibited workflow. It could also expose a secret-bearing
subscriber URL.

### Use ECAL only as a verification source

Rejected for automated operation under the current terms. Manual personal
comparison may be performed by an operator, but it cannot become an ingestion
path or produce canonical writes or removals.

### Continue directly with API-Football

Retained as a safe fallback because it is already implemented, but not selected
as the next cost-minimizing design. `football-data.org` has an explicit free
Premier League tier and a smaller fixture surface, so it receives the next
qualification step.

## Reassessment trigger

Reassess this ADR only after written permission covers automated retrieval,
caching, retention, attribution, and derived private-calendar use, or if ECAL
publishes an API/service plan expressly supporting that workflow.

Detailed evidence and the future iCalendar contract are recorded in
[`../premier-league-official-feed-qualification.md`](../premier-league-official-feed-qualification.md).
