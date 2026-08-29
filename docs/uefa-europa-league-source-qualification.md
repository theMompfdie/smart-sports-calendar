# UEFA Europa League Source Qualification

## Status

**Conditional for `v0.6.0-beta.1`: no authoritative writer is assigned. The
operator approved a possible 2026/27 release boundary from the league phase
through the final, with qualifying kept as an optional separate scope. The
current zero-cost OpenLigaDB candidate is structurally incomplete, while the
technically viable football-data.org and Sportmonks paths require an explicit
paid-source decision.**

This record was reviewed on 2026-08-29 for issue #158. It applies the hybrid
tournament contract completed in #151. It does not register an account, start
a trial, approve payment, accept provider terms, assign an authority, enable a
catalog entry, or authorize runtime collection.

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

## Conditional decision

No authoritative writer is assigned for `uefa_europa_league` / `2026_27`.
Implementation, credential use, paid registration, and source assignment are
blocked until the operator chooses one of these paths:

1. **Zero-cost path — wait and re-observe OpenLigaDB.** This avoids a new
   subscription and reuses the existing adapter, but current data is severely
   incomplete and any later implementation is expected to remain
   removal-disabled and community-source dependent.
2. **football-data.org paid path — EUR 49/month.** This reuses the existing
   provider integration and cleanly separates `EL` from paid `ELQ`, but costs
   more and still needs 2026/27 catalog publication plus two credentialed
   observations.
3. **Sportmonks paid path — from EUR 29/month.** This has the strongest
   documented hybrid model and lower starting price, but requires a credit
   card-backed trial, a new adapter, and full live/contractual qualification.
4. **Defer Europa League.** Preserve the current unassigned state until a
   permitted source satisfies the operator's cost and evidence boundary.

API-Football is not an approvable option without separate UEFA rights
clearance. An operator selection authorizes only the next qualification gate,
not authority assignment or implementation.

## Required next gate

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

1. OpenLigaDB `uel2026` / 6000 publishes the complete 36-team, 144-fixture
   league phase with stable identities and credible group structure;
2. football-data.org `EL` / 2146 advances to 2026/27 or changes plan tier;
3. Sportmonks changes its plan, trial, or Europa League coverage terms;
4. UEFA publishes or permits a supported API or calendar feed;
5. UEFA grants written permission for the intended API-Football use;
6. another permitted source proves stable, complete main-scope coverage; or
7. the operator selects or changes the allowed recurring-cost boundary.

## Sources

Reviewed 2026-08-29:

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
- [Sportmonks Europa League API](https://www.sportmonks.com/football-api/europa-league-api/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [API-Football pricing](https://www.api-football.com/pricing/)
- [API-Sports terms](https://api-sports.io/terms)
