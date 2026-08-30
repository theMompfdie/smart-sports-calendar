# ADR 0012: Select OpenLigaDB for the Nations League A group phase

- Status: Accepted
- Date: 2026-08-30
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #163, #164, #170
- Builds on: ADR 0004, ADR 0005, ADR 0007, ADR 0011

## Context

Phase 6 needs a permitted, recurring-cost-free authority for the 2026/27 UEFA
Nations League. The complete edition contains four league levels and later
knockout and play-off stages, but no reviewed no-cost source currently exposes
that entire lifecycle with an acceptable automation contract.

OpenLigaDB provides unauthenticated JSON access under ODbL 1.0. Two sanitized
observations of league `5978`, shortcut `nla`, season `2026`, returned the same
48 fixtures, 16 participants, four League A groups, and identity fingerprints.
An independent manual comparison with UEFA's published schedule found an exact
pairing and kickoff match for the League A group phase. OpenLigaDB remains a
community-maintained source rather than an official UEFA authority.

The project has an explicit EUR 0 recurring API-cost boundary. Runtime data is
used privately, while the repository may become public. Source code,
configuration examples, documentation, and synthetic tests must therefore be
publishable without exposing provider payloads, live fixture inventories,
databases, exports, secrets, or restricted documents.

## Decision

Select OpenLigaDB API v1 league `5978`, shortcut `nla`, season `2026`, as the
sole proposed authoritative writer for the 2026/27 UEFA Nations League League A
group phase, subject to these conditions:

- the approved boundary is exactly four League A groups, 16 participants, and
  48 fixtures from 24 September through 17 November 2026;
- Leagues B, C, and D plus every 2027 or 2028 knockout, final, and play-off
  stage remain excluded and require separate qualification;
- each accepted observation must contain 12 fixtures and four disjoint
  participants per selected group, including both directed fixtures for every
  participant pairing;
- stable provider fixture and participant IDs are persisted as correlation
  identities; the initial participant mapping accepts only the 16 exact,
  independently reviewed provider names;
- additional provider groups may coexist in the response but are filtered out
  before normalization and can never contribute canonical or removal evidence;
- every observation remains `partial`, `complete=false`, and
  `removal_eligible=false` because OpenLigaDB exposes no authoritative
  completeness or sufficiently explicit lifecycle taxonomy;
- linked logos and icons are neither fetched nor persisted;
- ODbL attribution is retained in source metadata and Outlook event bodies;
- raw responses, live fixture inventories, SQLite databases, exports, and
  provider-derived test fixtures are excluded from Git, CI artifacts, images,
  and releases; and
- malformed, incomplete, identity-conflicting, wrong-scope, stale, or failed
  observations preserve last-known-good state.

The source assignment is created only when an operator explicitly enables the
bounded source job. Qualification and implementation do not enable collection,
perform live staging, deploy production, or approve a broader Nations League
scope.

## Consequences

### Positive

- The selected authority adds no recurring API cost or secret credential.
- The existing OpenLigaDB client, attribution, scheduler, mapping repository,
  and non-destructive lifecycle path can be reused.
- Exact group-level double-round-robin checks prevent partial or cross-group
  data from reaching canonical state.
- Synthetic tests can prove the complete contract without redistributing live
  provider data.

### Negative

- Only League A's 2026 group phase is available; broader coverage remains a
  future source or operator-assisted import problem.
- Community editing requires exact name admission on first import and stable
  persisted IDs thereafter.
- Provider absence cannot automatically cancel or delete a fixture.
- ODbL attribution and database/produced-work obligations remain operational
  requirements even for private use.

## Alternatives considered

### Use football-data.org `UNL` / 2182

Rejected because the reviewed Nations League coverage requires a paid plan and
would violate the project's EUR 0 recurring API-cost boundary.

### Use Sportmonks season 27797

Rejected because its broader all-leagues coverage requires a paid plan and a
new adapter. It is not an automatic fallback.

### Import all OpenLigaDB Nations League groups and later placeholders

Rejected. Only League A passed the technical and manual evidence gates. Later
groups and stages cannot provide canonical or removal evidence.

### Scrape UEFA pages or automate a fixture PDF

Rejected for this runtime. UEFA material remains manual verification evidence
without a documented automated-use contract. A future operator-assisted,
manifest-based import is tracked separately and must retain its own provenance
and licensing controls.

## References

- [`../uefa-nations-league-source-qualification.md`](../uefa-nations-league-source-qualification.md)
- [`../phase-6-source-authority-matrix.md`](../phase-6-source-authority-matrix.md)
- [UEFA 2026/27 draw and format](https://www.uefa.com/uefanationsleague/news/02a1-1fc60cd57c4d-de2c1d716ed6-1000/)
- [UEFA league-phase fixtures](https://www.uefa.com/uefanationsleague/news/02a2-1fea18abbcbc-456e846509e7-1000/)
- [OpenLigaDB](https://www.openligadb.de/)
- [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
