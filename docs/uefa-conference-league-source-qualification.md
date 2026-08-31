# UEFA Conference League Source Qualification

## Status

**Deferred from `v0.6.0-beta.1`: no authoritative writer is assigned. The
operator-approved UEFA club-competition boundary permits a future 2026/27
scope from the league phase through the final, with qualification kept as an
optional separate scope. No zero-cost 2026/27 automated candidate is currently
observable, and the operator did not approve a recurring paid source.**

This record was reviewed on 2026-08-29 for issue #161 and finalized with the
operator's deferral decision on 2026-08-31. It applies the hybrid tournament
contract completed in #151. It does not register an account, start a trial,
approve payment, accept provider terms, assign an authority, enable a catalog
entry, or authorize runtime collection.

Qualification remains fail-closed. Public catalog observations recorded here
contain no credentials, private payloads, team names, or individual provider
fixture IDs.

## Operator scope decision

The operator-approved Phase 6 rule for UEFA club competitions establishes the
following Conference League boundary:

- missing qualifying-round coverage does not block the main Conference League
  source decision;
- an approved 2026/27 release scope may begin with the league phase and
  continue through the knockout phase play-offs, round of 16, quarter-finals,
  semi-finals, and final;
- when a provider exposes qualification under a separate competition ID or a
  materially separate lifecycle, it may be qualified later as an optional
  source/competition scope; and
- qualification and main-competition observations must never be merged
  automatically or provide removal evidence for each other.

All 36 league-phase clubs reached the competition through qualification. That
sporting dependency does not require this calendar integration to import the
earlier fixtures. This is a lifecycle and release-boundary decision, not a
source or cost approval.

## Competition and lifecycle boundary

UEFA's 2026/27 regulations define one edition containing:

- a main-path first qualifying round;
- main-path and champions-path second and third qualifying rounds;
- main-path and champions-path play-offs;
- a six-match league phase for 36 clubs, producing 108 fixtures;
- knockout phase play-offs;
- round of 16, quarter-finals, and semi-finals; and
- a single-match final in Istanbul on 2 June 2027.

Qualification, play-off, and knockout ties are normally played over two legs.
Teams can transfer from Champions League and Europa League qualification, and
later-round participants and fixtures are discovered incrementally.

The canonical `2026_27` season remains the full edition boundary. The approved
release candidate is narrower: league phase through final. A provider may be
authoritative only for that explicit scope and must not imply full-edition
coverage.

The expected final main-scope shape is 153 fixtures: 108 league-phase
fixtures, 16 knockout-play-off fixtures, 16 round-of-16 fixtures, eight
quarter-finals, four semi-finals, and one final. This count is structural
evidence only. It does not prove that a provider response is complete.

UEFA completed the league-phase draw on 28 August 2026 and announced that the
full fixture calendar would be available no later than 30 August. Public
provider state during this review is therefore a post-draw, pre-final-calendar
observation and must not be treated as settled completeness evidence.

## Candidate review

### Official UEFA sources

UEFA is authoritative for the competition format, participants, draws,
official schedule, and regulations. Its public material confirms the 36
league-phase participants, opponent allocation, six-match structure,
matchday windows, knockout dates, and final.

No supported public fixture API or automatically updated competition feed was
found with stable machine fixture IDs, pagination, completeness semantics,
quotas, retention rules, or an automation contract for this application.
UEFA's platform terms prohibit systematic automated collection. Public UEFA
material is therefore manual verification evidence only. HTML scraping,
browser-session extraction, and undocumented endpoints remain excluded.

The UEFA Data Products Portal, business authentication API, and Intelligence
Centre evidence reviewed for the Champions League track do not publish a
self-service Conference League fixture product with generally available usage
terms.

### OpenLigaDB

OpenLigaDB is a credential-free community database rather than an official
UEFA source. Its documented model allows registered users to create and
maintain leagues, so catalog presence alone would not establish completeness
or authority.

A credential-free read of the public league directory on 2026-08-29 found no
2026/27 Conference League entry. Historical entries existed for 2022/23 and
2023/24, but no current league ID, shortcut, groups, fixtures, or participants
could be observed for the intended edition.

OpenLigaDB is therefore not a current candidate, not a permanently rejected
provider. It should be rechecked after UEFA's final fixture calendar has
propagated. If a 2026/27 entry appears, qualification would still require:

- two stable sanitized observations;
- exactly 36 resolved league-phase participants and 108 unique fixtures;
- credible stage and matchday structure;
- stable numeric fixture and participant IDs across updates;
- UTC kickoff correction behavior;
- explicit treatment of postponement and cancellation limitations; and
- manual comparison with UEFA.

Even a complete-looking community response should initially remain
removal-disabled because OpenLigaDB exposes no provider completeness marker
and no sufficiently explicit cancellation/postponement taxonomy. ODbL
attribution and produced-work or adapted-database obligations would apply.
Linked logos and icons remain excluded.

### football-data.org API v4

The credential-free public catalog observation on 2026-08-29 returned two
separate provider competitions:

| Provider competition | ID | Code | Plan | Public current season |
| --- | ---: | --- | --- | --- |
| UEFA Conference League | 2154 | `UCL` | `TIER_FOUR` | 2025/26, ID 2456 |
| Conference League Qualification | 2185 | `COLQ` | `TIER_FOUR` | 2025/26, ID 2452 |

The provider code `UCL` refers to the Conference League in this catalog and
must not be confused with football-data.org's Champions League code `CL`.
Explicit provider-to-canonical mapping is mandatory.

The split matches the operator-approved lifecycle boundary: `COLQ` can remain
outside the release while `UCL` is evaluated independently. Neither catalog
entry had advanced to 2026/27, so fixture count, participant resolution, stage
vocabulary, later-round coverage, and stable identity could not be validated.

`TIER_FOUR` corresponds to the currently published Pro plan at EUR 199 per
month for 100 competitions. The existing football-data.org transport,
validation, retry, quota, and failure-isolation code would reduce
implementation risk, but no paid plan is approved for this track.

The API exposes stable-looking numeric fixture and participant IDs, UTC
kickoffs, statuses, stages, matchdays, and `lastUpdated`; it documents season,
stage, matchday, status, and date filters. It does not guarantee stable match
IDs across changes or expose an exact completeness marker. A paid selection
would still require two secret-safe credentialed observations after `UCL`
advances to 2026/27.

The existing one-application, credential secrecy, visible attribution,
availability disclaimer, cancellation cleanup, and separate logo-rights
conditions apply.

### Sportmonks Football API v3

Sportmonks documents the Conference League as league ID `2286`. Its published
model covers qualification through the final, seasons, stages, rounds,
fixtures, participants, aggregates, and stable-looking IDs. It explicitly
describes the 36-team, six-match league phase and two-legged knockout ties.
This is the strongest documented technical fit among the reviewed candidates.

The public competition page identifies 2025/26 as season ID `25581`; it does
not publish the intended 2026/27 season ID. Credentialed season discovery and
fixture observation would therefore be required.

The Starter plan currently begins at EUR 29 per month for five selected
leagues and 2,000 calls per entity per hour. Its 14-day trial requires a valid
credit or debit card and automatically becomes paid unless cancelled. The
terms permit derived applications and returned-data storage but prohibit raw
resale, scope pricing per domain, disclaim completeness and availability, and
require a separate rights review for logos and photos.

Sportmonks would require a new provider integration and competition-specific
live validation. No trial, payment method, subscription, or terms acceptance
is approved.

### API-Football v3

API-Football documents a EUR 0 plan with 100 requests per day and broad
competition and fixture coverage. Its existing project integration and
lifecycle fields make it technically plausible.

API-Sports explicitly states that it does not grant the required licence to
use or publish competition data and that the user must obtain permission from
the competent league, federation, or event organizer. No UEFA-specific written
permission is recorded. API-Football therefore remains rejected as a new
Conference League authority under the current evidence.

### Other zero-cost candidates

TheSportsDB free season retrieval remains capped at 15 events without a
documented complete-pagination contract. OpenFootball does not publish a
current Conference League fixture dataset with provider-grade stable fixture
IDs and lifecycle coverage. Neither can qualify the 108-fixture league phase.

## Deferred decision

No authoritative writer is assigned for `uefa_conference_league` / `2026_27`.
The operator deferred the competition from `v0.6.0-beta.1` on 2026-08-31.
Implementation, credential use, paid registration, and source assignment
remain blocked until a later release explicitly reopens one of these paths:

1. **Zero-cost path — wait for an OpenLigaDB 2026/27 entry.** No candidate
   exists today. A later entry could reuse the existing adapter, but would
   remain community-dependent and initially removal-disabled.
2. **Sportmonks paid path — from EUR 29/month.** This is the strongest
   documented technical fit and the least expensive current paid option, but
   requires a card-backed trial, a new adapter, and full live and contractual
   qualification.
3. **football-data.org paid path — EUR 199/month.** This reuses the existing
   provider integration and cleanly separates `UCL` from `COLQ`, but its cost
   is substantially higher and 2026/27 has not reached the public catalog.
4. **Keep Conference League deferred.** Preserve the current unassigned state
   until a permitted source satisfies the operator's cost and evidence
   boundary.

API-Football is not an approvable option without separate UEFA rights
clearance. An operator selection authorizes only the next qualification gate,
not authority assignment or implementation.

## Re-evaluation gate

Before a later credentialed-validation or implementation issue can be created:

1. UEFA's finalized league-phase calendar must be published and propagated;
2. the operator selects the acceptable cost and provider path;
3. the selected main competition exposes the 2026/27 season;
4. two sanitized read-only observations prove stable fixture identity,
   competition and season scope, 36 resolved participants, exactly 108
   league-phase fixtures, stage and matchday semantics, UTC kickoffs,
   pagination, update behavior, and reproducible fingerprints;
5. terms, attribution, persistence, cancellation, and secret handling are
   explicitly accepted for the selected private-calendar use; and
6. later rounds remain incremental and non-removal-capable until separately
   qualified as exact stage or round boundaries.

Qualification remains optional and separate. It must not block or silently
expand the main scope.

## Re-evaluation triggers

Re-evaluate this decision when:

1. UEFA publishes the finalized 2026/27 league-phase fixture calendar;
2. OpenLigaDB publishes a credible current Conference League entry;
3. football-data.org `UCL` / 2154 advances to 2026/27 or changes plan tier;
4. Sportmonks publishes the 2026/27 season ID or changes plan and trial terms;
5. UEFA publishes or permits a supported API or calendar feed;
6. UEFA grants written permission for the intended API-Football use;
7. another permitted source proves stable, complete main-scope coverage; or
8. the operator selects or changes the allowed recurring-cost boundary.

## Sources

Reviewed 2026-08-29:

- [UEFA overview](https://www.uefa.com/uefaconferenceleague/news/02a6-20d57d15f093-a90cf54c928f-1000/)
- [UEFA league-phase draw](https://www.uefa.com/uefaconferenceleague/news/02a8-215821a6c3b6-3209db321888-1000/)
- [UEFA draw opponents](https://www.uefa.com/uefaconferenceleague/news/02a8-216e9ca380de-9d2c904b0cb8-1000/)
- [UEFA regulations](https://documents.uefa.com/r/Regulations-of-the-UEFA-Conference-League-2026/27/)
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
- [Sportmonks Conference League API](https://www.sportmonks.com/football-api/conference-league-api/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [API-Football pricing](https://www.api-football.com/pricing/)
- [API-Sports terms](https://api-sports.io/terms)
