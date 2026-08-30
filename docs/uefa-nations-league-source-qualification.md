# UEFA Nations League Source Qualification

## Status

**Qualified for `v0.6.0-beta.1`: on 2026-08-30 the operator selected
OpenLigaDB `nla` / 5978 at EUR 0 as the bounded authority for the 48-fixture
League A group phase only and accepted the applicable ODbL conditions.
Leagues B, C, and D and every later stage remain excluded. Implementation is
tracked by #170 and does not itself complete live staging or release approval.**

This record was reviewed on 2026-08-29 and extended with two technical
observations and the operator decision on 2026-08-30 for issue #164. It applies
the hybrid tournament and bounded-observation contract completed in #151. It
does not register an account, start a trial, approve payment, enable runtime
collection, perform live staging, or approve production use.

Public observations contain no credentials, private payloads, team names, or
individual provider fixture IDs.

## Competition and lifecycle boundary

UEFA identifies the active fifth Nations League edition as 2026/27. Its league
phase runs from 24 September through 17 November 2026 and contains 54 national
teams across four separately meaningful leagues:

- League A: four groups of four teams and 48 fixtures;
- League B: four groups of four teams and 48 fixtures;
- League C: four groups of four teams and 48 fixtures; and
- League D: two groups of three teams and 12 fixtures.

The complete league phase contains 156 fixtures. Later stages add:

- four two-legged League A quarter-finals: eight fixtures;
- four two-legged League A/B play-offs: eight fixtures;
- four two-legged League B/C play-offs: eight fixtures;
- two semi-finals, a third-place match, and the final: four fixtures; and
- two two-legged League C/D play-offs in March 2028: four fixtures.

The expected full-edition shape is therefore 188 fixtures. Later participants
are determined by league-phase results, so quarter-final, play-off, and final
boundaries remain incremental until their draws and schedules are published.

The March 2028 League C/D play-offs belong to the 2026/27 competition outcome
but cross the normal season-year expectation. A provider season ending in
November 2026 cannot silently imply full-edition coverage.

## Candidate release boundaries

No boundary is approved. Public evidence supports these operator choices:

1. **League A group phase only** — 48 scheduled fixtures.
2. **League A group phase through finals** — 60 eventual fixtures, with later
   rounds remaining incremental until separately observed.
3. **All four league phases** — 156 scheduled fixtures.
4. **Full edition** — 188 eventual fixtures, including the March 2028 C/D
   play-offs.
5. **Defer** — keep the competition unassigned and disabled.

A source qualified for one boundary cannot supply completeness or removal
evidence for another league, group, stage, round, or edition.

## Candidate review

### Official UEFA sources

UEFA is authoritative for the competition format, league and group allocation,
fixture list, schedule, promotion and relegation rules, later-stage dates, and
regulations. Its public fixture list contains the complete 156-fixture league
phase.

No supported public fixture API or automatically updated competition feed was
found with stable machine fixture IDs, pagination, completeness semantics,
quotas, retention rules, or an automation contract for this application.
UEFA's platform terms prohibit systematic automated collection. UEFA pages are
therefore manual verification evidence only. HTML scraping, browser-session
extraction, and undocumented endpoints remain excluded.

The UEFA Data Products Portal and related business services do not publish a
self-service Nations League fixture product with generally available terms.

### OpenLigaDB League A

OpenLigaDB is a credential-free community database, not an official UEFA
source. Registered users can create and maintain leagues, and similarly named
or overlapping entries can coexist. Stable numeric IDs are technically useful,
but catalog presence alone is not authority or completeness evidence.

The public 2026 directory contains this focused candidate:

| Field | Observed value |
| --- | --- |
| League ID | `5978` |
| Shortcut | `nla` |
| Season | `2026` |
| Name | Nations League A 2026 |
| Authentication | None |
| Cost | EUR 0 |

A sanitized credential-free observation on 2026-08-29 returned:

- 48 fixtures with 48 unique fixture IDs;
- 16 participants with 16 unique participant IDs;
- four group-phase groups matching the League A structure;
- UTC kickoffs from 24 September through 17 November 2026;
- four additional configured later-stage groups for quarter-final first legs,
  quarter-final second legs, semi-finals, and final or third-place matches;
- no later-stage fixtures; and
- zero finished fixtures.

The 48-fixture and 16-participant shape matches UEFA's League A group phase.

Two secret-safe validator observations at `2026-08-30T09:14:57.467166Z` and
`2026-08-30T09:16:32.440837Z` returned identical evidence:

- 48 source and in-scope fixtures with 48 unique fixture IDs;
- 16 participants;
- 12 fixtures in each of the four League A groups;
- zero fixtures in the configured quarter-final, semi-final, and final groups;
- all 48 fixtures in `SCHEDULED` status;
- UTC kickoffs from `2026-09-24T18:45:00Z` through
  `2026-11-17T19:45:00Z`;
- latest source update `2026-08-01T17:25:19.593000Z`;
- no missing timezone declaration and three credential-free requests;
- fixture-ID fingerprint
  `d972894ee25924c4f8bcf680c6a4a0d820acb2b926263c663ab666e9cce80157`;
  and
- participant-ID fingerprint
  `0eeb66755b15c4d9b7faf517298bfd5280eac76b3a94b3a1cb683d4f5c5cd838`.

A separate manual comparison against UEFA's official fixture list produced an
exact 48-of-48 pairing and UTC-kickoff match, with zero missing and zero
unexpected fixtures. The independent canonical comparison fingerprint was
`1676e35e54d308d7f19dbf76da4c6da0dad066aaca73fd03b2c0459e406dcae5`.

The curated `nations-league-a-group-phase` profile ignores later-stage
fixtures for its scoped fingerprint while recording the complete source count.
It rejects incomplete groups, reused participants across groups, duplicate
identities, invalid UTC data, or any fixture-count deviation.

Re-run the same credential-free evidence path with:

```powershell
python -m app.operations.openligadb_qualification --competition nations-league-a-group-phase
```

The command emits only bounded aggregates, public group metadata, and hashed
provider identities. It never emits team names or individual fixture IDs.

If selected, the initial OpenLigaDB boundary should remain removal-disabled.
The provider exposes no completeness marker and no sufficiently explicit
cancellation, postponement, abandonment, or awarded-match taxonomy. Later
round group placeholders cannot create completeness or removal evidence.

ODbL attribution and produced-work or adapted-database obligations apply.
Linked logos, flags, and icons remain excluded.

### OpenLigaDB broad Nations League entry

The public directory also contains league ID `4955`, shortcut `unl`, season
`2026`, named Nations League 2026/27. Its sanitized observation returned:

- zero fixtures;
- zero participants; and
- four generic groups named preliminary round, quarter-final, semi-final, and
  final.

This entry does not represent Leagues A, B, C, or D and is rejected as current
all-leagues evidence. Its empty response must fail closed and can never create
removal evidence.

### football-data.org API v4

The credential-free public catalog observation returned:

| Field | Observed value |
| --- | --- |
| Competition ID | `2182` |
| Code | `UNL` |
| Type | `CUP` |
| Plan | `TIER_FOUR` |
| Current season | 2026/27, ID `2507` |
| Public season dates | 24 September to 17 November 2026 |

`TIER_FOUR` corresponds to the currently published Pro plan at EUR 199 per
month for 100 competitions. The existing football-data.org transport,
validation, retry, quota, and failure-isolation code would reduce integration
risk, but no paid plan is approved.

The public season dates match the league phase only. They do not prove League
A quarter-finals, promotion/relegation play-offs, finals, or the March 2028 C/D
boundary. Credentialed observations must enumerate stages, groups, fixtures,
participants, pagination, and later-season behavior before a scope can qualify.

The API exposes stable-looking numeric IDs, UTC kickoffs, statuses, stages,
matchdays, and `lastUpdated`, but does not guarantee stable IDs across changes
or expose an exact completeness marker. One-application use, credential
secrecy, visible attribution, availability disclaimer, cancellation cleanup,
and separate media-rights conditions apply.

### Sportmonks Football API v3

Sportmonks documents the intended 2026/27 edition as season ID `27797`. Its
public schedule description exposes separate League A, B, C, and D stages and
exactly 156 league-phase fixtures:

| Stage | Fixtures |
| --- | ---: |
| League A | 48 |
| League B | 48 |
| League C | 48 |
| League D | 12 |

Its model documents stage, round, fixture, participant, venue, lineup, and
stable-looking IDs. This is the strongest documented all-leagues technical
fit among the reviewed candidates. Public marketing does not prove later 2027
and 2028 completeness or stable identity across live corrections.

The Starter plan begins at EUR 29 per month for five selected leagues and
2,000 calls per entity per hour. The 14-day trial requires a valid credit or
debit card and automatically becomes paid unless cancelled. Terms permit
derived applications and returned-data storage but prohibit raw resale,
price scope per domain, disclaim completeness and availability, and require a
separate rights review for flags, logos, and photos.

Sportmonks requires a new provider integration and secret-safe live validation.
No trial, payment method, subscription, or terms acceptance is approved.

### API-Football v3

API-Football documents a EUR 0 plan with 100 requests per day and broad fixture
coverage. Its existing project integration and lifecycle fields make it
technically plausible.

API-Sports states that it does not grant the licence required to use or publish
competition data and that the user must obtain permission from the responsible
federation or event organizer. No UEFA-specific written permission is recorded.
API-Football remains rejected as a new Nations League authority.

### Other zero-cost candidates

TheSportsDB free season retrieval remains capped at 15 events without a
documented complete-pagination contract. OpenFootball does not publish a
current provider-grade 2026/27 Nations League fixture dataset with stable IDs
and lifecycle semantics. Neither can qualify even the 48-fixture League A
group phase.

## Decision

The operator selected the zero-cost League A path through OpenLigaDB `nla` /
5978 on 2026-08-30. The 48 group-phase fixtures passed two stable observations
and an exact manual UEFA comparison. Later rounds remain incremental and
unapproved, and removal remains disabled. ADR 0012 records the authority,
scope, ODbL, private-runtime, and public-repository boundaries.

Sportmonks season 27797 and football-data.org `UNL` / 2182 remain rejected for
this release because they require recurring payment. They are neither fallback
writers nor approved broader scopes.

Full-edition or League A-through-finals approval requires later stage-specific
evidence regardless of the selected provider. API-Football is not approvable
without separate UEFA rights clearance.

## Required next gate

Issue #170 must implement and verify the selected boundary before live staging:

1. enforce the exact 48-fixture, 16-participant, four-group contract;
2. keep later groups and stages filtered and removal-ineligible;
3. retain attribution and stable private source mappings;
4. prove idempotency, rescheduling, failure/recovery, and Outlook behavior with
   synthetic provider data in normal CI; and
5. repeat the bounded observation and lifecycle checks in isolated staging
   before release inclusion.

## Re-evaluation triggers

Re-evaluate when:

1. OpenLigaDB `nla` / 5978 changes its League A fixture or later-stage shape;
2. OpenLigaDB publishes complete League B, C, or D entries;
3. football-data.org `UNL` / 2182 changes plan tier or later-stage coverage;
4. Sportmonks changes season 27797, plan, trial, or coverage terms;
5. UEFA publishes or permits a supported API or calendar feed;
6. UEFA grants written permission for the intended API-Football use;
7. another permitted source proves stable selected-scope coverage; or
8. the operator selects or changes the scope or recurring-cost boundary.

## Sources

Reviewed 2026-08-29 and 2026-08-30:

- [UEFA 2026/27 draw and format](https://www.uefa.com/uefanationsleague/news/02a1-1fc60cd57c4d-de2c1d716ed6-1000/)
- [UEFA league-phase fixtures](https://www.uefa.com/uefanationsleague/news/02a2-1fea18abbcbc-456e846509e7-1000/)
- [UEFA regulations](https://documents.uefa.com/r/Regulations-of-the-UEFA-Nations-League-2026/27/)
- [UEFA platform terms](https://www.uefa.com/termsconditions/)
- [UEFA Data Products Portal](https://data.uefa.com/products/)
- [OpenLigaDB](https://www.openligadb.de/)
- [OpenLigaDB API](https://api.openligadb.de/)
- [OpenLigaDB API behavior and maintenance model](https://github.com/OpenLigaDB/OpenLigaDB-Samples)
- [OpenLigaDB 2026 league directory](https://www.openligadb.de/Leagues?season=2026)
- [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org public competition catalog](https://api.football-data.org/v4/competitions)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [football-data.org terms and attribution](https://www.football-data.org/about)
- [football-data.org competition resource](https://docs.football-data.org/general/v4/competition.html)
- [football-data.org match resource](https://docs.football-data.org/general/v4/match.html)
- [Sportmonks Nations League API](https://www.sportmonks.com/football-api/nations-league-api/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [API-Football pricing](https://www.api-football.com/pricing/)
- [API-Sports terms](https://api-sports.io/terms)
