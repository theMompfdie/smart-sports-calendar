# EFL Cup Source Qualification

## Status

**Deferred for `v0.5.0-beta.1`: no reviewed no-cost candidate can provide a
permitted, complete, machine-readable 2026/27 authority.**

Issue #127 evaluates the EFL Cup before any provider adapter, catalog, mapping,
source job, SQLite import, Microsoft Graph synchronization, or release claim is
approved. SMART Sports Calendar is a hobby project, so a permitted and
technically trustworthy no-cost source is preferred even when another bounded
adapter would be required. No paid plan was approved for this review.

Deferral assigns no authoritative writer. It does not remove the competition
from the roadmap, but it prevents incomplete or unapproved data from entering
canonical persistence or Outlook.

## Competition lifecycle boundary

The EFL publishes the cup incrementally through successive draws. Clubs taking
part in UEFA competition can enter in round three, byes may be required, rounds
one through five are single-match ties, the semi-finals are two-legged, and the
final is a single neutral-ground match. Fixtures can be rearranged and an
unfulfilled tie can result in a bye into the following round.

A currently published fixture list is therefore neither a complete-season
snapshot nor proof that one round is complete. A future authority must preserve
stable fixture identity across draw completion, participant resolution,
rescheduling, venue changes, byes, and the two semi-final legs. It must also
identify the tie and leg independently enough to prevent two legs from being
merged.

The maximum safe observation under this decision is `partial` and
removal-disabled. A future `complete_round` or `complete_stage` decision
requires new provider-specific qualification. No 2026/27 EFL Cup observation
is removal-eligible under this record.

## Candidate review

### Official EFL sources and ECAL calendar

The EFL publishes the current competition fixture page, draw announcements,
round information, and competition rules. These are authoritative manual
verification sources. No documented public EFL fixture API was found.

The EFL also links an official digital calendar delivered by ECAL. Its public
entry point includes an `EFL Competitions` category, but the ECAL end-user terms
limit the service to personal use and explicitly prohibit robots, scraping,
data mining, and similar systematic collection. Scheduled server retrieval,
canonical persistence, and derived Outlook writes therefore remain outside the
permitted public end-user contract recorded in ADR 0002.

No personalized subscription was created and no secret-bearing calendar URL or
payload was inspected. Written permission covering automated retrieval,
caching, retention, attribution, and derived private-calendar use would be
required before ECAL could be reconsidered.

### OpenLigaDB

A secret-free read-only observation on 2026-08-28 inspected all 826 leagues
returned by the documented `getavailableleagues` endpoint. It found no exact
EFL Cup, Carabao Cup, or Football League Cup competition.

OpenLigaDB therefore exposes no competition, season, round, participant, or
fixture identity that can be qualified. It remains a preferred no-cost
candidate only if a non-empty structurally reviewable EFL Cup scope is added in
the future.

### football-data.org

football-data.org identifies the Football League Cup as `FLC` / `2139`, with a
2026/27 season in the reviewed catalog. Access belongs to the paid Advanced
tier, currently EUR 99 per month. The provider's free tier includes the
Championship but not the Football League Cup.

No paid plan or credentialed cup observation was approved. The candidate is
not selected without current-season fixture coverage, stable tie and leg
identity, exact round completeness, and safe placeholder behavior.

### API-Football

API-Football has broad technical coverage and a limited free plan, but the
reviewed API-Sports terms do not grant the data-use and publication rights
required for a new Phase 5 authority. The customer must obtain permission from
the competent rights holder, and no EFL-specific written clearance is recorded.

Free access does not overcome that rights blocker. Existing legacy mappings do
not authorize a new EFL Cup writer.

### Sportmonks

Sportmonks documents EFL Cup league `27` and exposes season, stage, round,
fixture, participant, state, pagination, and schedule relationships. This makes
it the strongest reviewed technical candidate for a future qualification.

The permanent free plan covers only the Danish Superliga and Scottish
Premiership. EFL Cup access requires a paid plan or a one-time trial attached
to a paid subscription. The Starter plan begins at EUR 29 per month for five
selected competitions. No recurring cost, trial, credential, or two-observation
live qualification was approved, so Sportmonks is not selected.

### TheSportsDB

TheSportsDB identifies the EFL Cup as league `4570`. A secret-free V1
observation on 2026-08-28 returned exactly 15 events for `2026-2027`, with 15
unique event IDs and dates from 2026-08-01 through 2026-08-08. Its season-list
response returned five seasons and did not list `2026-2027`.

The documented V1 season endpoint is capped at 15 events without pagination,
so this response cannot represent the progressive cup schedule. The documented
V2 full-schedule request returned HTTP 400 because a paid API key is required.
The terms also leave third-party content permission with the API user. No paid
access or separate rights clearance was approved, so TheSportsDB is rejected
for this scope.

### Other free calendar and export services

FotMob offers an EFL Cup calendar-sync page, but its terms explicitly prohibit
robots, crawlers, indexing, and other systematic or regular use. It is not a
permitted automated source.

Fixtures24 offers a free updating EFL Cup calendar, but the reviewed public
material does not establish authoritative provenance, a permitted automation
contract, stable fixture `UID` behavior, round completeness, or lifecycle
semantics. Fixture Download offers free JSON, CSV, and iCalendar exports for
some competitions, but warns that its JSON schema can change without notice,
does not document stable fixture identity, and did not expose a reviewed
2026/27 EFL Cup dataset. These consumer services do not satisfy the authority
contract.

### OpenFootball datasets

OpenFootball publishes public-domain community football datasets without an
API key. Its current England repository covers the four national league levels
but does not publish a current EFL Cup schedule. The text format also provides
no provider-issued stable fixture identity or authoritative completeness
marker.

The project remains useful for open-data experimentation but is not a safe
2026/27 EFL Cup authority.

## Deferred operating decision

- No authoritative writer is assigned for `efl_cup` / `2026_27`.
- No credential, subscription, trial, adapter, catalog, mapping, source job, or
  scheduler configuration is approved.
- All candidate observations remain outside canonical persistence and Outlook.
- No empty, partial, stale, malformed, ambiguous, throttled, or failed response
  may change last-known-good state or contribute destructive evidence.
- No implementation issue should be created from this deferred decision.
- If a future qualification selects one authority, implementation remains
  mandatory in a separate focused issue and pull request, with regression and
  isolated staging validation before any release claim.

## Exact re-evaluation triggers

Reopen qualification only when at least one of these conditions is true:

1. the EFL publishes or explicitly permits a documented API or calendar feed
   with stable competition, round, tie, leg, and fixture identities;
2. ECAL or the EFL grants written permission for the complete automated use;
3. OpenLigaDB adds a non-empty EFL Cup scope with structurally reviewable
   rounds and stable identities across two observations;
4. another documented no-cost provider offers suitable data rights, complete
   round retrieval, stable identities, lifecycle states, and safe quotas;
5. the operator obtains EFL-specific written data permission for API-Football;
   or
6. the operator explicitly approves a paid Sportmonks or other provider plan
   and its current coverage, price, domain, quota, terms, attribution,
   retention, cancellation, and exit obligations.

Any re-evaluation must perform two secret-safe read-only observations separated
by a meaningful interval. It must fail closed on pagination gaps, duplicate or
replaced fixtures, unknown participants, byes, two-leg ambiguity, unsupported
states, timezone ambiguity, and incomplete round boundaries.

## Sources

- [Official EFL Cup competition page](https://www.efl.com/competitions/carabao-cup/)
- [Official 2026/27 EFL season and cup dates](https://www.efl.com/news/2026/may/29/everything-you-need-to-know-about-the-2026-27-efl-season/)
- [Official EFL handbook and cup rules](https://www.efl.com/documents/efl-handbook.pdf)
- [Official EFL digital calendar](https://efl.ecal.com/)
- [ECAL terms of use](https://ecal.com/terms-of-use/)
- [ECAL automated-source rejection](adr/0002-reject-ecal-as-automated-source.md)
- [OpenLigaDB API](https://api.openligadb.de/)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [API-Sports terms](https://api-sports.io/terms)
- [Sportmonks free plan](https://www.sportmonks.com/football-api/free-plan/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [TheSportsDB API guide](https://www.thesportsdb.com/docs_api_guide)
- [TheSportsDB pricing](https://www.thesportsdb.com/docs_pricing.php?billing=annual)
- [TheSportsDB terms](https://www.thesportsdb.com/docs_terms_of_use.php)
- [FotMob EFL Cup calendar](https://www.fotmob.com/leagues/133/synccalendar/efl-cup)
- [FotMob terms of use](https://www.fotmob.com/terms)
- [Fixture Download terms](https://fixturedownload.com/terms)
- [Fixtures24 EFL Cup calendar](https://www.fixtures24.com/eng/competitions/efl-cup)
- [OpenFootball England repository](https://github.com/openfootball/england)
