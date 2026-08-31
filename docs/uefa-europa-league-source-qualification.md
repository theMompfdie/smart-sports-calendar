# UEFA Europa League Source Qualification

## Status

**Deferred from `v0.6.0-beta.1`: no authoritative writer is assigned. A
2026-08-31 re-observation confirmed that the zero-cost OpenLigaDB candidate is
still structurally incomplete and that a configured free football-data.org
account cannot access `EL` / 2146. A separate Footballdata.io free account
includes the Europa League and exposes the current 2026/27 season, but its
league-phase fixtures have not propagated yet. Footballdata.io remains the
preferred zero-cost re-evaluation candidate; no paid source is approved for
this release.**

This record was reviewed on 2026-08-29 and re-observed on 2026-08-31 for issue
 #158. It applies the hybrid tournament contract completed in #151. It does not
start a trial, approve payment, assign an authority, enable a catalog entry,
or authorize runtime collection.

Qualification remains fail-closed. Public catalog observations recorded here
contain no credentials, private payloads, team names, or individual provider
fixture IDs.

## Operator scope decision

On 2026-08-29 the operator approved the following competition boundary:

- missing qualifying-round coverage does not block the main Europa League
  source decision;
- an approved 2026/27 release scope may begin with the league phase and
  continue through the knockout phase play-offs, round of 16, quarter-finals,
  semi-finals, and final;
- when a provider exposes qualification under a separate competition ID or a
  materially separate lifecycle, it may be qualified later as an optional
  source/competition scope; and
- qualification and main-competition observations must never be merged
  automatically or provide removal evidence for each other.

This is a lifecycle and release-boundary decision, not a source or cost
approval. Documentation must not imply qualifying-round support unless that
separate scope later qualifies.

## Competition and lifecycle boundary

UEFA's 2026/27 regulations and competition overview define one edition from
the first qualifying round on 9 July 2026 through the final in Frankfurt on
26 May 2027. The complete edition contains:

- first, second, and third qualifying rounds;
- qualifying play-offs;
- an eight-match league phase for 36 clubs, producing 144 fixtures;
- knockout phase play-offs;
- round of 16, quarter-finals, and semi-finals; and
- a single-match final.

Qualifying, play-off, and knockout ties are played over two legs. Teams can
enter from Champions League qualification, and later-round participants and
fixtures are discovered incrementally.

The canonical `2026_27` season remains the full edition boundary. The approved
release candidate is narrower: league phase through final. A provider may be
authoritative only for that explicit scope and must not imply full-edition
coverage. The expected final main-scope shape is 189 fixtures: 144 league-phase
fixtures, 16 knockout-play-off fixtures, 16 round-of-16 fixtures, eight
quarter-finals, four semi-finals, and one final. Only the league-phase boundary
can be structurally complete before later draws and progression resolve.

## Candidate review

### Official UEFA sources

UEFA is authoritative for the competition format, participants, draws,
official schedule, and regulations. Its public pages now list the 36
league-phase participants, opponents, matchday windows, knockout dates, and
final.

No supported public fixture API or automatically updated competition feed was
found with stable machine fixture IDs, pagination, completeness semantics,
quotas, retention rules, or an automation contract for this application.
UEFA's platform terms prohibit systematic collection and automated scraping.
Public UEFA material is therefore manual verification evidence only. HTML
scraping, browser-session extraction, and undocumented endpoints remain
excluded.

The UEFA Data Products Portal, business authentication API, and Intelligence
Centre evidence reviewed for the Champions League track do not publish a
self-service Europa League fixture product or generally available usage terms.

### OpenLigaDB

OpenLigaDB is a credential-free community database rather than an official
UEFA source. Its documented model allows registered users to create and
maintain leagues, and similarly named duplicate or incomplete leagues can
exist. Stable numeric fixture, participant, league, season, sport, and group
IDs are technically useful, but a league-directory entry is not completeness
or authority evidence.

The public 2026 league directory contained a new candidate on 2026-08-29:

| Field | Observed value |
| --- | --- |
| League ID | `6000` |
| Shortcut | `uel2026` |
| Season | `2026` |
| Name | Europa League 2026/27 |
| Authentication | None |
| Cost | EUR 0 |

A sanitized read-only observation at `2026-08-29T10:37:36Z` returned:

- 16 fixtures with 16 unique fixture IDs;
- 14 unique participant IDs and no unresolved participant slots;
- one UTC kickoff value for all 16 fixtures;
- all fixtures assigned to `Ligaphase`;
- four configured group names (`Ligaphase`, `Viertelfinale`, `Halbfinale`,
  and `Finale`), omitting knockout phase play-offs and round of 16; and
- zero finished fixtures.

A second readiness observation at `2026-08-31T12:03:53Z` still returned only:

- 16 fixtures with 16 unique fixture IDs;
- 15 unique participants rather than the required 36;
- league-phase kickoffs spanning only 16 September through 22 October 2026;
- the same four configured groups, still omitting the knockout phase play-offs
  and round of 16; and
- no fixtures in the configured quarter-final, semi-final, or final groups.

The participant count changed from 14 to 15 while the fixture inventory
remained at 16. This confirms active but incomplete community maintenance, not
a stable or complete league-phase snapshot.

This observation occurred on the morning after UEFA's 28 August league-phase
draw, before the finalized dated fixture list had propagated across the
reviewed provider catalogs. It is therefore classified as `not ready`, not as
a permanent provider rejection. The response is not the official 36-team,
144-fixture league-phase boundary and cannot qualify the source, assign
authority, enable imports, or provide removal evidence. The source should be
re-observed after the finalized UEFA schedule is published and propagated,
but a later complete-looking response still requires two stable observations
and manual comparison with UEFA.

If OpenLigaDB later qualifies, its community maintenance, lack of explicit
cancellation/postponement taxonomy, and absence of a provider completeness
marker mean the initial implementation should remain permanently
removal-disabled unless stronger competition-specific evidence supports a
later ADR. Existing ODbL attribution and produced-work/adapted-database rules
would apply, and linked logos or icons would remain excluded.

### football-data.org API v4

The credential-free public catalog observation on 2026-08-29 returned two
separate provider competitions:

| Provider competition | ID | Code | Plan | Public current season |
| --- | ---: | --- | --- | --- |
| UEFA Europa League | 2146 | `EL` | `TIER_TWO` | 2025/26, ID 2455 |
| Europa League Qualification | 2183 | `ELQ` | `TIER_THREE` | 2026, ID 2532 |

This split matches the operator-approved lifecycle boundary: `ELQ` can remain
outside the release while `EL` is evaluated independently. The main `EL`
catalog had not yet advanced to 2026/27, so its league-phase fixture count,
participant resolution, stage vocabulary, later-round coverage, and stable
identity could not be validated.

`TIER_TWO` corresponds to the currently published Standard plan at EUR 49 per
month for 30 competitions. The existing football-data.org transport,
validation, retry, quota, and failure-isolation code would reduce
implementation risk, but no paid plan is approved for this track.

The API exposes stable-looking numeric fixture and participant IDs, UTC
kickoffs, statuses, stages, matchdays, and `lastUpdated`; it documents season,
stage, matchday, status, and date filters. It does not guarantee stable match
IDs across changes or expose an exact completeness marker. A paid selection
would still require two secret-safe credentialed observations after `EL`
advances to 2026/27.

The existing one-application, credential secrecy, visible attribution,
availability disclaimer, cancellation cleanup, and separate logo-rights
conditions apply.

On 2026-08-31 the operator authorized secret-safe, read-only availability
checks with an existing free credential. The authenticated competition catalog
returned HTTP 200 with 13 accessible competitions, but did not contain `EL` /
2146. The documented direct competition endpoint returned HTTP 403. No fixture
or participant endpoint was called, and no credential, header, private payload,
or account data was emitted or persisted. The free account therefore cannot
supply the main Europa League competition under the current plan boundary.

### Footballdata.io API v1

Footballdata.io is a separate provider from football-data.org. The operator's
free account dashboard explicitly includes UEFA Europa League among its five
selected leagues. Secret-safe read-only checks on 2026-08-31 confirmed:

- an active free API key with an observed monthly allowance of 2,000 requests;
- UEFA Europa League league ID `46` in the free-plan search results;
- current season ID `90443`, year `20262027`, plus 17 historical seasons;
- 69 season teams and 80 unique completed fixtures across four provider
  rounds;
- 52 unique fixture participants, with kickoffs from 9 July through 27 August
  2026; and
- zero fixtures when the current season was filtered from 1 September 2026
  through 31 January 2027.

The current response therefore covers qualifying and play-offs but none of the
official 144-fixture, 36-participant league phase. UEFA published the finalized
league-phase fixtures on 29 August and matchday 1 is on 16/17 September, about
eight days after the Champions League begins. This result is classified as
`not ready` propagation evidence, not a permanent provider rejection.

The API exposes numeric league, season, round, fixture, and team identities,
UTC-convertible match timestamps, status, update, date filtering, and
pagination. Its documented examples and live nested response shapes differ in
some details, so any adapter must validate the observed v1 contract rather
than assume the examples are exact. The free tier requires attribution;
coverage varies by league and season. The terms permit reasonable caching but
may require written permission for long-term storage or bulk replication.
Those persistence, attribution, cancellation, availability, and third-party
data-rights boundaries require explicit acceptance before authority
assignment.

### Sportmonks Football API v3

Sportmonks documents Europa League as league ID `5`. Its published model covers
seasons, three qualifying rounds, play-offs, the 36-team league phase,
knockout stages, rounds, fixtures, participants, aggregates, and
stable-looking IDs. This is the strongest documented technical fit among the
reviewed commercial candidates.

The Starter plan currently begins at EUR 29 per month for five selected
leagues and 2,000 calls per entity per hour. Its 14-day trial requires a valid
credit or debit card and automatically becomes paid unless cancelled. The
terms permit building derived applications and storing/distributing returned
data but prohibit raw resale, scope pricing per domain, disclaim completeness
and availability, and require a separate rights review for logos and photos.

Sportmonks would require a new provider integration and competition-specific
live validation. No trial, payment method, subscription, or terms acceptance
is approved.

### API-Football v3

API-Football documents a EUR 0 plan with 100 requests per day and broad
competition/fixture coverage. Its existing project integration and lifecycle
fields make it technically plausible.

API-Sports explicitly states that it does not grant the required licence to
use or publish competition data and that the user must obtain permission from
the competent league, federation, or event organizer. No UEFA-specific written
permission is recorded. API-Football therefore remains rejected as a new
Europa League authority under the current evidence.

### Other zero-cost candidates

TheSportsDB free season retrieval remains capped at 15 events without a
documented complete-pagination contract. OpenFootball does not publish a
current Europa League fixture dataset with provider-grade stable fixture IDs
and lifecycle coverage. Neither can qualify the 144-fixture league phase.

## Deferred decision

No authoritative writer is assigned for `uefa_europa_league` / `2026_27`.
The operator deferred Europa League from `v0.6.0-beta.1` on 2026-08-31 because
none of the reviewed zero-cost paths currently supplies the required
36-participant, 144-fixture league phase and no recurring paid source is
approved for this release. Footballdata.io remains the preferred later path
because free-plan access, current season identity, and qualifying data are
already observable.

The evaluated paths remain:

1. **Preferred zero-cost path — re-observe Footballdata.io.** Free access and
   the current season are confirmed, but the league phase has not propagated.
   A later complete observation still requires full technical and contractual
   qualification plus a new provider adapter.
2. **Alternative zero-cost path — wait and re-observe OpenLigaDB.** This avoids
   a new subscription and reuses the existing adapter, but current data is
   severely incomplete and any later implementation is expected to remain
   removal-disabled and community-source dependent.
3. **football-data.org paid path — EUR 49/month.** This reuses the existing
   provider integration and cleanly separates `EL` from paid `ELQ`, but costs
   more and still needs 2026/27 catalog publication plus two credentialed
   observations.
4. **Sportmonks paid path — from EUR 29/month.** This has the strongest
   documented hybrid model and lower starting price, but requires a credit
   card-backed trial, a new adapter, and full live/contractual qualification.
5. **Defer Europa League — selected for `v0.6.0-beta.1`.** Preserve the current
   unassigned state until a permitted source satisfies the operator's cost and
   evidence boundary.

API-Football is not an approvable option without separate UEFA rights
clearance. An operator selection authorizes only the next qualification gate,
not authority assignment or implementation.

## Required re-evaluation gate

Before a credentialed-validation or implementation issue can be created:

1. the operator selects the acceptable cost and provider path;
2. the selected main competition exposes the finalized 2026/27 league-phase
   schedule;
3. two sanitized read-only observations prove stable fixture identity,
   competition/season scope, 36 resolved participants, exactly 144
   league-phase fixtures, stage/matchday semantics, UTC kickoffs, pagination,
   update behavior, and reproducible fingerprints;
4. terms, attribution, persistence, cancellation, and secret handling are
   explicitly accepted for the selected private-calendar use; and
5. later rounds remain incremental and non-removal-capable until separately
   qualified as exact stage or round boundaries.

Qualification remains optional and separate. It must not block or silently
expand the main scope.

## Re-evaluation triggers

Re-evaluate this decision when:

1. Footballdata.io season `90443` publishes the complete 36-team, 144-fixture
   league phase with stable fixture identity, schedule, and update behavior;
2. OpenLigaDB `uel2026` / 6000 publishes the complete 36-team, 144-fixture
   league phase with stable identities and credible group structure;
3. football-data.org `EL` / 2146 advances to 2026/27 or changes plan tier;
4. Sportmonks changes its plan, trial, or Europa League coverage terms;
5. UEFA publishes or permits a supported API or calendar feed;
6. UEFA grants written permission for the intended API-Football use;
7. another permitted source proves stable, complete main-scope coverage; or
8. the operator selects or changes the allowed recurring-cost boundary.

## Sources

Reviewed 2026-08-29 and re-observed 2026-08-31:

- [UEFA 2026/27 Europa League overview](https://www.uefa.com/uefaeuropaleague/news/02a6-20d57d095740-e1e0b3de85df-1000/)
- [UEFA 2026/27 Europa League regulations](https://documents.uefa.com/r/Regulations-of-the-UEFA-Europa-League-2026/27/)
- [UEFA league-phase draw and opponents](https://www.uefa.com/uefaeuropaleague/accesslist/)
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
- [football-data.org API policies](https://docs.football-data.org/general/v4/policies.html)
- [Footballdata.io API documentation](https://footballdata.io/documentation/)
- [Footballdata.io league endpoints](https://footballdata.io/documentation/leagues/)
- [Footballdata.io season endpoints](https://footballdata.io/documentation/seasons/)
- [Footballdata.io rate limits](https://footballdata.io/documentation/rate-limits/)
- [Footballdata.io terms](https://footballdata.io/terms/)
- [Sportmonks Europa League API](https://www.sportmonks.com/football-api/europa-league-api/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [API-Football pricing](https://www.api-football.com/pricing/)
- [API-Sports terms](https://api-sports.io/terms)
