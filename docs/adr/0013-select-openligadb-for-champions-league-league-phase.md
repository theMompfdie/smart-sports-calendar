# ADR 0013: Select OpenLigaDB for the Champions League league phase

- Status: Accepted
- Date: 2026-08-31
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #150, #154, #155
- Builds on: ADR 0004, ADR 0007, ADR 0011, ADR 0012

## Context

Phase 6 needs a zero-recurring-cost fixture authority for the 2026/27 UEFA
Champions League. The operator approved a release boundary beginning with the
league phase and explicitly excluded qualification. The initially selected
football-data.org free candidate had advanced to 36 participants but still
returned no fixtures after UEFA published the schedule.

OpenLigaDB provides public ODbL-licensed JSON data without credentials. Two
sanitized observations of league `4946`, shortcut `ucl`, season `2026`,
returned 144 unique league-phase fixtures, 36 participants, and eight complete
18-fixture matchdays. UEFA's official structure and dates matched those
aggregates exactly.

## Decision

Select OpenLigaDB `4946/ucl/2026` as the sole proposed authoritative writer for
only `uefa_champions_league/2026_27/league_phase`, subject to these conditions:

- exactly groups 1 through 8, 36 participants, and 144 fixtures are admitted;
- every participant appears once per matchday and faces eight distinct
  opponents;
- groups 9 through 16 and every qualifying stage are filtered out;
- exact provider fixture IDs are the correlation identity;
- the reviewed provider ID/name pair is required for all 36 participants;
- observations remain partial and permanently removal-disabled;
- ODbL attribution remains visible in Outlook event bodies;
- raw live data and logos are not stored in the public repository; and
- failed, malformed, incomplete, stale, or identity-conflicting observations
  preserve last-known-good state.

The source job remains operator opt-in. This ADR does not deploy, perform live
Graph staging, qualify later stages, or approve another writer.

## Consequences

The UCL league phase can be synchronized without an account or recurring
provider cost by reusing the existing OpenLigaDB client and orchestration path.
The strict Swiss-style schedule validator rejects partial snapshots before
canonical writes. In exchange, missing fixtures can never cancel or delete
events, later knockout rounds remain manual until separately qualified, and
the community-maintained source needs continued official UEFA verification.

## Alternatives considered

football-data.org remains a possible verification source or future explicit
alternative, but its free 2026/27 match collection was empty during the
qualification window. It is not an automatic failover. API-Football lacks the
recorded UEFA-specific permission required by project policy. Sportmonks
requires a paid plan. UEFA pages are authoritative manual evidence but do not
offer the documented automated fixture contract required by this runtime.

## References

- [`../uefa-champions-league-source-qualification.md`](../uefa-champions-league-source-qualification.md)
- [`../phase-6-source-authority-matrix.md`](../phase-6-source-authority-matrix.md)
- [UEFA league-phase structure](https://www.uefa.com/uefachampionsleague/news/02a8-215821715a96-9a3b43fad585-1000--uefa-champions-league-league-phase-draw/)
- [OpenLigaDB](https://www.openligadb.de/)
