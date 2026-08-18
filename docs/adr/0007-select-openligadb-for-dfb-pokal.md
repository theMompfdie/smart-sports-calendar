# ADR 0007: Select OpenLigaDB for the DFB-Pokal

- Status: Accepted
- Date: 2026-08-18
- Related issues: #104, #116, #118

## Context

Phase 5.6 provides bounded cup reconciliation, but the 2026/27 DFB-Pokal
requires a competition-specific source decision. The initial Sportmonks
candidate requires a paid subscription and was rejected by the operator for
this competition. football-data.org also places the DFB-Pokal outside the free
plan. Scraping the DFB or ORF websites is excluded by the source policy.

OpenLigaDB exposes the competition without authentication as league `4945`,
shortcut `dfb`, season `2026`. Its data is community maintained and published
under ODbL 1.0. The API exposes stable-looking fixture, participant, league,
season, and group identities, but no sufficient placeholder, cancellation,
postponement, or provider-side completeness contract.

Two complete read-only observations were performed on 2026-08-18 at
18:07:54 UTC and 18:46:46 UTC. Both reported:

- 32 unique first-round fixtures and 64 unique participants;
- fixture fingerprint
  `cf19f8f7e6f96dca91c3ceca05b4e05bdf94051b09d8c01147ef8bd90732435e`;
- participant fingerprint
  `d97f3a241e044cbc060bf25d22df233d941b0d3f33ed763df7a1b442aa454273`;
- six stable group IDs, ordered from first round through final;
- 32 `SCHEDULED` fixtures and no populated later round; and
- identical kickoff and source-update boundaries.

All 32 pairings and kickoff times were manually checked against the official
DFB first-round schedule. Harmless club-name differences did not alter the
pairings or times.

## Decision

Select OpenLigaDB API v1 as the only automated authority for the 2026/27
DFB-Pokal, subject to these mandatory boundaries:

- every observation has authoritative scope `partial`;
- OpenLigaDB observations may create and update known fixtures but never
  cancel, delete, or infer absence from missing records;
- `matchID` is the external fixture identity and `teamId` is the participant
  identity;
- `leagueId` plus `leagueSeason` binds the season;
- `groupID` is the provider round identity and `groupOrderID` maps to
  `round-{n}` independently of the localized group name;
- `matchDateTimeUTC` is the kickoff authority;
- the official DFB schedule is a manual verification source only and is never
  scraped or used as an automated writer;
- linked logo and icon resources are excluded; and
- the adapter must retain the fail-closed validations proved by issue #118.

The required visible attribution text is:

> Fixture data provided by OpenLigaDB (ODbL 1.0):
> https://www.openligadb.de/

For this private deployment, persisted provider-derived fixture records are
treated operationally as an internal adapted database and Outlook events as
produced works. Provenance and the ODbL notice must be retained. The project
code and provider-neutral schema remain independently licensed and must not
embed raw OpenLigaDB payloads.

Before the calendar, database, feed, or another substantial extract is made
public, the operator must perform a new ODbL distribution review. Public
produced works retain visible attribution; public use of an adapted database
must meet applicable ODbL share-alike and machine-readable-access obligations.

## Consequences

- A separate implementation issue may add only the DFB-Pokal catalog,
  mappings, adapter, non-destructive runtime, tests, documentation, and staging
  proof.
- The implementation cannot promote this source to `complete_round` or
  `complete_stage` without a new provider contract and ADR.
- Empty, incomplete, malformed, stale, or changed responses preserve the last
  known good canonical state.
- Community edits remain an operational risk. Identity and current DFB
  alignment must be rechecked before staging, release, and after material
  provider changes.
- No API credential, paid plan, automatic failover, or second writer is added.

## Rejected alternatives

### Sportmonks

Rejected for this competition because it requires a paid plan. It remains a
separate candidate for other competitions and is not a DFB-Pokal fallback.

### football-data.org

Rejected for the no-cost DFB-Pokal path because the competition is outside the
free plan.

### DFB or ORF scraping

Rejected because neither reviewed website provides a documented automated
source contract suitable for this project. The DFB schedule remains the manual
verification reference; ORF is not used.
