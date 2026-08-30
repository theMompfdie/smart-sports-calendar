# ADR 0013: Select nflverse for the NFL 2026 Regular Season

- Status: Accepted
- Date: 2026-08-30
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #168, #178, #179
- Builds on: ADR 0004 and the provider integration contract

## Context

Phase 7 needs a recurring-cost-free, permitted, stable fixture source for the
NFL 2026 season. The operator wants automated schedule synchronization in a
private Outlook calendar while keeping the repository safe for future public
visibility.

The nflverse project publishes an automated `schedules` GitHub release in
multiple formats. Its release repository uses CC BY 4.0 and documents
programmatic data access and five-minute in-season schedule updates. Two
sanitized observations contained the same 272 regular-season games, 32 teams,
weeks 1–18, and fixture identity fingerprint.

NFL Football Operations independently describes the regular season as 272
games across 18 weeks. nflverse documents kickoff times in Eastern time.

The source remains community-maintained, late-season times can change under
NFL flex scheduling, and nflverse warns that underlying NFL data remains
subject to its owners' rights. The source therefore cannot justify publishing
the dataset or destructive reconciliation merely because its release
repository has an open licence.

## Decision

Select nflverse `schedules/games.csv` as the sole proposed authoritative writer
for exactly the NFL 2026 regular season, subject to explicit operator
enablement and these conditions:

- admit exactly 272 unique `REG` games, 32 reviewed teams, and weeks 1–18;
- use nflverse `game_id` as primary fixture identity;
- retain secondary identifiers only for diagnostics and operator review;
- interpret source dates and times in `America/New_York` and convert them to
  UTC with standard-library timezone rules;
- update flexed kickoffs through the stable primary identity;
- fail closed on any identity-set, week, participant, schema, timezone, or
  structural conflict;
- keep all observations `partial`, `complete=false`, and removal-disabled;
- exclude preseason, postseason, results, statistics, betting, roster, venue,
  weather, and media fields;
- display nflverse and CC BY 4.0 attribution plus a flex-scheduling notice;
- never publish raw source rows, fixture inventories, databases, Outlook
  exports, logos, or other provider/NFL assets; and
- stop collection for review if the source, licence, provenance, attribution,
  or private-use boundary changes.

Qualification authorizes a separate implementation issue. It does not enable
collection, perform staging, or approve production deployment.

## Consequences

### Positive

- The source adds no recurring cost or credential.
- CSV can be handled with the Python standard library.
- A 272-game structure and 32-team mapping provide strict admission checks.
- Stable game identity allows ordinary flex-schedule changes to update an
  existing canonical and Outlook event.
- CC BY attribution requirements are explicit and testable.

### Negative

- Community maintenance and upstream automation can introduce corrections or
  outages without a commercial support contract.
- Late-season dates and kickoff times can be provisional.
- Omission can never remove a fixture under this authority.
- A game moved to a different week or rekeyed by nflverse requires operator
  review rather than heuristic correlation.
- The private-use limitation must be reassessed before any public deployment
  or dataset publication.

## Alternatives considered

### NFL.com automated retrieval

Rejected. NFL.com is authoritative manual verification evidence, but no
documented public fixture API or approved scraping contract was identified.

### ESPN schedule endpoints

Rejected. The commonly used endpoints are undocumented and lack the source
contract required for an authoritative writer.

### Paid sports-data provider

Rejected for the initial release because it introduces recurring cost while a
qualified zero-cost path exists. Paid access is not automatic failover.

### Manual manifest import

Retained as a future operator-controlled fallback under #168. It must never
run simultaneously as another authoritative writer.

## References

- [`../nfl-source-qualification.md`](../nfl-source-qualification.md)
- [`../phase-7-source-authority-matrix.md`](../phase-7-source-authority-matrix.md)
- [nflverse-data](https://github.com/nflverse/nflverse-data)
- [nflverse schedules release](https://github.com/nflverse/nflverse-data/releases/tag/schedules)
- [CC BY 4.0 licence](https://github.com/nflverse/nflverse-data/blob/main/LICENSE.md)
- [NFL schedule structure](https://operations.nfl.com/gameday/nfl-schedule/creating-the-nfl-schedule)
