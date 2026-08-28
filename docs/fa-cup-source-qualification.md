# FA Cup Source Qualification

## Status

**Deferred for `v0.5.0-beta.1`: no reviewed no-cost candidate can provide a
permitted, complete, machine-readable 2026/27 authority.**

Issue #126 evaluates the FA Cup before any provider adapter, catalog, mapping,
source job, SQLite import, Microsoft Graph synchronization, or release claim is
approved. SMART Sports Calendar is a hobby project, so a permitted and
technically trustworthy no-cost source is preferred even when another bounded
adapter would be required. No paid plan was approved for this review.

Deferral assigns no authoritative writer. It does not remove the competition
from the roadmap, but it prevents incomplete or unapproved data from entering
canonical persistence or Outlook.

## Competition lifecycle boundary

The official 2026/27 FA Cup has 743 accepted clubs and begins with 219 extra
preliminary-round ties. Later clubs enter through exemptions, draws reveal
fixtures incrementally, early-round replays can add ties, and dates can change
for postponements or broadcast selection. A list of currently published ties
is therefore not a complete-season snapshot.

Any future authority must preserve stable fixture identity across draw
completion, participant resolution, replay creation, rescheduling, and venue
changes. The maximum safe observation under this decision is `partial` and
removal-disabled. A future `complete_round` decision requires a new
qualification proving an exact provider-specific round boundary; no 2026/27 FA
Cup observation is removal-eligible under this record.

## Candidate review

### Official Football Association sources

The FA publishes current fixture and result pages, tie numbers, round dates,
accepted-club and exemption lists, draw documents, and the competition rules.
The fixture page explicitly warns that dates and times can change and currently
shows early-round replays. These are authoritative manual verification sources.

No documented public FA Cup API or automatically updated iCalendar feed was
found. The FA's public Grassroots Technology support record states that fixture
APIs are not offered for Full-Time and limits available integration to
administrator-generated display snippets. Human-facing web pages, embedded
snippets, downloadable PDFs, and undocumented endpoints do not satisfy the
project's automated-source contract. HTML scraping remains excluded.

### OpenLigaDB

A secret-free read-only observation on 2026-08-28 inspected all 826 leagues
returned by the documented `getavailableleagues` endpoint. It found no exact FA
Cup competition in any season.

OpenLigaDB therefore exposes no competition, season, round, participant, or
fixture identity that can be qualified. It remains a preferred no-cost
candidate only if a complete, structurally reviewable FA Cup scope is added in
the future.

### football-data.org

football-data.org identifies the FA Cup as `FAC` / `2055`, but access belongs
to the paid Standard tier, currently starting at EUR 49 per month. The public
catalog evidence reviewed for Phase 5 also lagged at 2025/26 rather than proving
the active 2026/27 progressive draw.

No paid plan or credentialed observation was approved. The candidate is not
selected without current-season coverage, stable round and replay behavior,
and an exact safe observation contract.

### API-Football

API-Football has broad technical coverage and a limited free plan, but the
reviewed API-Sports terms do not grant the data-use and publication rights
required for a new Phase 5 authority. The customer must obtain permission from
the competent rights holder, and no FA-specific written clearance is recorded.

Free access does not overcome that rights blocker. Existing legacy mappings do
not authorize a new FA Cup writer.

### Sportmonks

Sportmonks documents FA Cup league `24` and exposes season, stage, round,
fixture, participant, state, pagination, and schedule relationships. Its FA Cup
page states that the schedule can be retrieved as stages, rounds, and fixtures,
making it the strongest reviewed technical candidate.

The permanent free plan covers only the Danish Superliga and Scottish
Premiership. FA Cup access requires a paid plan or a one-time trial requiring a
payment method. The Starter plan begins at EUR 29 per month for five selected
competitions. No recurring cost, trial, credential, or two-observation live
qualification was approved, so Sportmonks is not selected.

### TheSportsDB

TheSportsDB identifies the FA Cup as league `4482`. A secret-free V1
observation on 2026-08-28 returned no 2026/27 events and its free season list
returned only five historical records. The documented V1 season endpoint is
limited to 15 events without pagination, which would be insufficient even if
the current season were populated.

The documented V2 full-league schedule supports a larger response but rejected
an anonymous request with HTTP 400 because an API key is required. The pricing
page reserves full premium JSON and higher data limits for the paid Single
Developer plan, currently USD 90 per year. The terms also leave permission for
third-party content with the API user.

The free access path cannot prove a complete round or season, and no paid
access was approved. TheSportsDB is rejected for this scope.

### OpenFootball datasets

OpenFootball publishes public-domain community football datasets without an API
key. Its current England repository covers the national league pyramid but
does not publish a current FA Cup schedule. The text format also provides no
provider-issued stable fixture identity or authoritative completeness marker.

The project is useful for open-data experimentation but is not a safe 2026/27
FA Cup authority.

## Deferred operating decision

- No authoritative writer is assigned for `fa_cup` / `2026_27`.
- No credential, subscription, trial, adapter, catalog, mapping, source job, or
  scheduler configuration is approved.
- All candidate observations remain outside canonical persistence and Outlook.
- No empty, partial, stale, malformed, ambiguous, throttled, or failed response
  may change last-known-good state or contribute destructive evidence.
- No implementation issue should be created from this deferred decision.
- If a future qualification selects one authority, implementation remains
  mandatory in a separate focused issue and pull request before staging or any
  release claim.

## Exact re-evaluation triggers

Reopen qualification only when at least one of these conditions is true:

1. The FA publishes or explicitly permits a documented, automatically updated
   API or calendar feed with stable competition, round, tie, and fixture IDs;
2. OpenLigaDB adds a non-empty FA Cup scope with structurally reviewable rounds
   and stable identities across two observations;
3. another documented no-cost provider offers complete round retrieval,
   suitable data rights, stable identities, lifecycle states, and safe quotas;
4. the operator obtains FA-specific written data permission for API-Football;
   or
5. the operator explicitly approves a paid Sportmonks or other provider plan
   and its current coverage, price, domain, quota, terms, attribution,
   retention, cancellation, and exit obligations.

Any re-evaluation must perform two secret-safe read-only observations separated
by a meaningful interval. It must fail closed on pagination gaps, duplicate or
replaced fixtures, unknown participants, replay and placeholder ambiguity,
unsupported states, timezone ambiguity, and incomplete round boundaries.

## Sources

- [Official 2026/27 FA Cup fixtures](https://www.thefa.com/competitions/thefacup/fixtures)
- [Official 2026/27 FA Cup round dates](https://www.thefa.com/competitions/thefacup/round-dates)
- [Official 2026/27 entries and exemptions](https://www.thefa.com/news/2026/jun/26/clubs-accepted-exemptions-mens-fa-cup-fa-youth-fa-trophy-fa-vase-2026-27)
- [Official early-round draws](https://www.thefa.com/news/2026/jul/02/2026-27-early-round-cup-draws)
- [FA Full-Time API support decision](https://grassrootstechnology.thefa.com/support/discussions/topics/48000566273)
- [OpenLigaDB API](https://api.openligadb.de/)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [API-Sports terms](https://api-sports.io/terms)
- [Sportmonks FA Cup coverage](https://www.sportmonks.com/football-api/fa-cup-api/)
- [Sportmonks free plan](https://www.sportmonks.com/football-api/free-plan/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [TheSportsDB API guide](https://www.thesportsdb.com/docs_api_guide)
- [TheSportsDB pricing](https://www.thesportsdb.com/docs_pricing.php?billing=annual)
- [TheSportsDB terms](https://www.thesportsdb.com/docs_terms_of_use.php)
- [OpenFootball England repository](https://github.com/openfootball/england)
