# ADR 0009: Select OpenLigaDB for the 2. Bundesliga regular season

- Status: Accepted
- Date: 2026-08-27
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #104, #108, #124
- Builds on: ADR 0004, ADR 0005, ADR 0007

## Context

Phase 5 needs one permitted authoritative writer for the 2026/27 German
2. Bundesliga. football-data.org exposes `BL2` only through a paid Standard
plan. SMART Sports Calendar is a hobby project, so a permitted and technically
trustworthy no-cost source is preferred even when it requires another bounded
provider adapter.

OpenLigaDB provides unauthenticated JSON access under ODbL 1.0. It is community
maintained rather than an official DFL source, so cost does not remove the need
for strict identity, completeness, lifecycle, attribution, and fail-closed
validation.

Two read-only observations separated by about three minutes returned identical
league, group, fixture, participant, status, kickoff, update, and fingerprint
evidence. Both exposed league `4938`, shortcut `bl2`, season `2026`, 18
participants, 34 matchdays with nine fixtures each, and 306 unique directed
pairings. A local comparison against all 306 rows in the official DFL fixture
PDF found no missing or additional pairing and produced the same normalized
pairing fingerprint.

Exactly 18 finished fixtures omitted the optional `timeZoneID` declaration;
all fixtures retained an explicit UTC kickoff. This stable omission is bounded
in the qualification profile and retained as an aggregate diagnostic.

## Decision

Select OpenLigaDB API v1 league `4938`, shortcut `bl2`, season `2026`, as the
sole proposed authoritative writer for the 2026/27 2. Bundesliga regular
season, subject to these conditions:

- the maximum qualified observation is the complete 18-team, 34-matchday,
  306-fixture regular season;
- promotion/relegation matches remain a separate, unqualified scope;
- every accepted snapshot must contain exactly nine fixtures and all 18
  participants in every matchday plus exactly one directed fixture for every
  participant pairing;
- fixture, participant, league, season, sport, and group IDs are the identity
  basis; names and kickoff timestamps are not identities;
- a missing `timeZoneID` is accepted only for this profile when the explicit
  UTC kickoff remains valid; any different non-empty timezone fails closed;
- linked logos and icons are never retrieved or persisted;
- the existing OpenLigaDB ODbL attribution and produced-work/adapted-database
  operating conditions apply;
- a short, malformed, empty, wrong-scope, failed, or structurally incomplete
  observation preserves last-known-good state;
- an unexplained fixture-ID or participant-ID set change requires explicit
  review and must not become automatic removal evidence; and
- missing cancellation/postponement taxonomy means initial implementation is
  non-destructive even when a snapshot is structurally `complete_season`.

Qualification authorizes a separate implementation issue. It does not add a
catalog entry, source assignment, adapter, job, database write, staging action,
calendar operation, production deployment, or release claim.

## Consequences

### Positive

- No recurring provider subscription is required for this competition.
- The already integrated OpenLigaDB transport, license boundary, and
  attribution model can be reused.
- Exact double-round-robin invariants provide stronger completeness evidence
  than response count or provider quality indicators alone.
- The paid football-data.org candidate remains available as an explicit
  fallback if the no-cost source later stops satisfying the contract.

### Negative

- A separate league adapter/profile and reviewed participant mapping are still
  required.
- Community editing requires stricter runtime diagnostics and manual review of
  identity-set changes.
- Initial operation cannot infer cancellation or deletion from provider
  absence despite structurally complete snapshots.
- OpenLigaDB publishes no rate-limit contract, so polling must remain
  conservative.

## Alternatives considered

### Use football-data.org Standard

Rejected as the default because it adds a recurring EUR 49/month cost while a
permitted no-cost candidate passes the competition contract. It remains a paid
fallback, not an automatic failover writer.

### Treat the official DFL PDF or website as the automated source

Rejected. The PDF is a manual verification reference, not a documented
automated API or automatically updated feed. HTML scraping and undocumented
endpoints remain outside policy.

### Allow automatic removals from every complete OpenLigaDB response

Rejected. Structural completeness does not resolve community identity edits or
the missing cancellation/postponement taxonomy. A later ADR may reconsider
removal only with additional lifecycle evidence.

## References

- [`../openligadb-2-bundesliga-qualification.md`](../openligadb-2-bundesliga-qualification.md)
- [`../phase-5-source-authority-matrix.md`](../phase-5-source-authority-matrix.md)
- [OpenLigaDB](https://www.openligadb.de/)
- [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- [Official DFL fixture list](https://media.dfl.de/sites/3/2026/07/EN_uvW2SdCp_Bundesliga-2_Fixture-List_2026_27.pdf)
