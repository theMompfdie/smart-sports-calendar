# ADR 0005: Bound Phase 5 source qualification and first implementation wave

- Status: Accepted
- Date: 2026-08-16
- Related issues: #108, #116

## Context

Phase 5.1 introduced provider-neutral competition formats and observation
scopes. Phase 5 now needs competition-specific source decisions without
assuming that one provider is contractually and technically suitable for every
league and cup.

Public coverage is not proof of a complete, stable, removal-capable season.
Domestic split leagues, progressively drawn cups, revised play-offs, and UEFA's
hybrid league/knockout competitions have different completeness boundaries.
Provider prices and terms also differ materially.

## Decision

Adopt the outcome and evidence model in
[`../phase-5-source-authority-matrix.md`](../phase-5-source-authority-matrix.md).

The 2026/27 Premier League remains the only qualified and released authority,
using football-data.org. All domestic Phase 5 candidates remain conditional
until their explicit contractual, plan, lifecycle, and live-validation gates
pass. The three UEFA competitions are deferred beyond `v0.5.0-beta.1` because
their hybrid format is not representable by ADR 0004.

The first implementation candidate is the 2026/27 German Bundesliga alone,
using football-data.org competition `BL1` / 2002 after two secret-safe live
observations qualify the source. Implementation must not start while that
decision remains conditional.

API-Football is not eligible as a new Phase 5 authority without written
competition-specific rights clearance. Sportmonks is the preferred candidate
for Austrian and remaining domestic-cup qualification, but no subscription or
authority is approved by this ADR. Issue #118 supersedes that initial
preference for the DFB-Pokal alone by evaluating the no-cost OpenLigaDB
candidate; a competition-specific ADR must still approve or reject it.

## Consequences

- The next implementation issue stays focused on one regular-season league.
- Existing football-data.org infrastructure can be generalized only after the
  Bundesliga qualification gate passes and without weakening Premier League
  validation.
- Championship pagination and play-off semantics receive a separate issue.
- Split-league and concrete cup imports remain non-destructive until their
  competition-specific qualification proves a complete stage or round. Issue
  #116 provides the generic bounded reconciliation mechanism but does not
  qualify a source or competition.
- UEFA work first requires a hybrid competition-capability design.
- Provider alternatives may be verification, bootstrap, or future candidates,
  never simultaneous authoritative writers or automatic failover.
- Every live qualification is operator-controlled, read-only, secret-safe, and
  isolated from SQLite, Outlook, production, and normal CI.

## Rejected alternatives

### Qualify every competition from public coverage alone

Rejected because coverage pages do not prove current-season completeness,
stable identity across lifecycle changes, pagination behavior, or safe removal
boundaries.

### Select one universal provider for all Phase 5 competitions

Rejected because the current technical, contractual, cost, and freshness
evidence differs by competition. Provider-neutral orchestration exists
specifically to avoid this coupling.

### Include UEFA in the first beta wave

Rejected because treating a qualifying/league/knockout tournament as either a
plain league or a plain knockout cup would discard required canonical
lifecycle semantics.
