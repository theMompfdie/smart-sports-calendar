# UEFA Champions League Source Qualification

## Status

**Conditional for `v0.6.0-beta.1`: football-data.org is the operator-selected
zero-cost candidate for the UEFA Champions League league phase and later
stages. The 2026/27 qualifying rounds are deliberately outside the approved
release boundary, while credentialed main-competition qualification remains
pending.**

This record was reviewed on 2026-08-28 for issue #154 and updated with the
first readiness check on 2026-08-30 for issue #155. It applies the hybrid
tournament contract completed in #151 and the operator constraint that the
selected source must have zero recurring and zero one-time cost. Free account
registration and a free API credential are acceptable. Paid trials, payment
methods, subscriptions, usage charges, and licence fees are not approved.

Qualification remains fail-closed. No UEFA Champions League authority,
catalog entry, source assignment, credential, schedule, canonical fixture, or
Outlook event is approved by this record.

## Operator decision

On 2026-08-28 the operator selected football-data.org for the next
qualification step and approved a deliberately bounded 2026/27 release scope:

- synchronization begins with the league phase;
- knockout phase play-offs, round of 16, quarter-finals, semi-finals, and the
  final remain in the intended scope when exposed by `CL` / 2001;
- first, second, and third qualifying rounds and the qualifying play-offs are
  excluded for this season;
- the selected source must remain cost-free; free registration and a free API
  credential are permitted.

This is a source-candidate and release-boundary decision, not an authoritative
assignment. Credentialed qualification, terms acceptance during account/key
use, implementation, staging, and release approval remain separate gates.

## Competition and lifecycle boundary

UEFA's 2026/27 competition documentation defines one edition from the first
qualifying round on 7 July 2026 through the final on 5 June 2027. The edition
contains:

- first, second, and third qualifying rounds;
- play-offs;
- an eight-match league phase for 36 clubs;
- knockout phase play-offs;
- round of 16, quarter-finals, and semi-finals;
- a single-match final.

All qualifying ties, play-offs, knockout phase play-offs, round-of-16 ties,
quarter-finals, and semi-finals are played over two legs. The final is a
single fixture. Draw-dependent participants and later fixtures become known
incrementally. UEFA states that the 2026/27 league-phase match dates and
kickoff times were confirmed on 29 August 2026. The published inventory has 36
teams, eight matchdays, and 144 fixtures from 8 September 2026 through
27 January 2027.

The canonical `2026_27` season remains the complete edition boundary. A source
that exposes only the league phase and later stages can be considered only for
an explicitly bounded release scope; it cannot be described as the authority
for the full edition. SMART Sports Calendar does not merge separate stage
writers into one edition and does not use a second provider as automatic
failover.

## Operator source-cost constraint

The selected source must cost EUR 0 for the required fixture synchronization
scope. A free account and free API key are permitted. A candidate is
disqualified when production use requires a credit card, a time-limited paid
trial, a later mandatory subscription, pay-per-use, or a licence fee.

Cost is only one gate. A free source still needs permitted automated access,
stable fixture identities, sufficient lifecycle fields, safe quotas,
acceptable terms, and deterministic failure behavior.

## Candidate review

### Official UEFA sources

UEFA is the authoritative source for competition format, participants, draws,
match dates, fixture confirmations, and regulations. Its current public pages
provide official fixtures, results, teams, dates, and draw information for
2026/27.

No documented public fixture API or automatically updated competition-wide
calendar feed with a supported automation contract, stable source fixture IDs,
pagination, completeness semantics, quota, or retention terms was found in the
reviewed public material. Public pages and regulations are therefore approved
only for manual verification. HTML scraping, browser-session extraction, and
undocumented endpoints remain excluded.

### football-data.org API v4

football-data.org is the preferred zero-cost technical candidate. Its coverage
page lists UEFA Champions League in the permanent Free Tier. The public API
catalog identifies the main competition as ID `2001`, code `CL`, type `CUP`,
and plan `TIER_ONE`. Registration supplies an `X-Auth-Token`; the free plan is
EUR 0 and documents 10 requests per minute.

The match resource exposes numeric match, competition, season, and participant
IDs plus UTC kickoff, status, stage, matchday, and `lastUpdated`. Documented
statuses include scheduled, timed, suspended, postponed, cancelled, and
awarded. Competition match collections support season, stage, matchday,
status, and date filters. The existing project integration already implements
bounded authentication, quota, transport, pagination, validation, retry, and
failure isolation for other qualified competition profiles.

The public catalog nevertheless exposes qualifying as a different competition:

| Provider competition | ID | Code | Plan observed 2026-08-28 | Public current season |
| --- | ---: | --- | --- | --- |
| UEFA Champions League | 2001 | `CL` | `TIER_ONE` / free | 2026/27, ID 2557; fixture inventory empty on 2026-08-30 |
| Champions League Qualification | 2174 | `CLQ` | `TIER_TWO` / paid | 2026 qualifying, ID 2531 |

This split creates one accepted limitation and one remaining qualification
blocker:

1. the permanent free plan does not include the separately modeled
   qualification competition; the operator accepted its exclusion for the
   2026/27 release boundary on 2026-08-28;
2. the `CL` catalog advanced to 2026/27 and exposed all 36 participants by the
   2026-08-30 readiness check, but its season-filtered match collection still
   returned zero fixtures. Coverage, stage vocabulary, and fixture identity
   therefore remain unproven.

The public documentation does not guarantee stable match IDs across
reschedules or document an exact completeness marker. Numeric IDs are
promising but require two sanitized read-only observations before authority
approval. Until then all observations must be `partial` and non-removal-capable.

The terms bind one key to one application, require credential secrecy and the
visible attribution `Football data provided by the Football-Data.org API`, do
not guarantee accuracy or availability, and require the application to stop
referencing obtained data after subscription cancellation. Logos and images
require separate rights and remain excluded.

### API-Football v3

API-Football documents a EUR 0 plan with 100 requests per day, no required
credit card, and access to all competitions and endpoints subject to season
availability. Its fixture API supports league/season/date/round filtering,
pagination metadata, stable-looking fixture IDs, lifecycle statuses, and quota
headers. It is technically plausible and already has a bounded transport in
the repository.

API-Sports explicitly states, however, that it does not grant a licence to use
or publish supplied competition data and that users must obtain any required
permission from the competent league, federation, or event organizer. No UEFA-
specific written permission is recorded. Availability and free-plan content
may also change without notice.

API-Football is therefore rejected as a new authoritative Champions League
writer under the current evidence. Existing legacy provider support does not
create competition-specific rights.

### Sportmonks Football API v3

Sportmonks provides the strongest documented hybrid-tournament structure among
the reviewed candidates. Its documentation identifies Champions League as
league ID `2` and models seasons, qualifying stages, league stage, knockout
stages, rounds, fixtures, participants, aggregates, and stable-looking IDs.

The permanent free football plan includes only the Danish Superliga and
Scottish Premiership. Champions League access requires a paid league-selection
plan; the published Starter plan begins at EUR 29 per month. A time-limited
trial does not satisfy the zero-cost production constraint.

Sportmonks is rejected for this track on cost even though its technical model
would otherwise warrant live qualification.

## Conditional decision

No authoritative writer is assigned for `uefa_champions_league` / `2026_27`.

football-data.org may advance only after all of the following gates are
satisfied:

1. the free `CL` catalog advances to the 2026/27 edition and exposes the
   published league-phase schedule;
2. two credentialed, secret-safe, read-only observations separated by a
   meaningful interval prove stable fixture IDs, complete pagination,
   competition/season identity, stage and matchday semantics, participant
   resolution, UTC kickoffs, status behavior, and unchanged-response
   fingerprints;
3. the observed call count plus bounded retries fits the free quota and the
   shared provider polling budget;
4. the operator accepts the current football-data.org terms and attribution
   obligation for this private calendar use;
5. the implementation issue defines all unproven observations as `partial`
   and grants removal capability only to an exact stage or round boundary that
   has separate evidence.

The absence of qualifying-round coverage no longer blocks this season because
those stages are outside the approved release boundary. Documentation,
configuration, tests, staging evidence, and release notes must preserve that
boundary and must not imply full-edition coverage.

## Required credentialed evidence

The next operator-authorized qualification observation must use the existing
football-data.org secret configuration without printing the token, headers,
raw payload, account metadata, team names, or provider fixture IDs.

Record only:

- API version and sanitized free-plan/quota result;
- competition and season IDs;
- total fixture count and pagination boundaries;
- counts by stage, matchday, status, and participant-resolution state;
- earliest/latest UTC kickoff and latest source update;
- duplicate, missing-ID, timezone, and structural-validation results;
- a SHA-256 fingerprint of sorted provider fixture IDs and safe lifecycle
  fields;
- the same aggregate evidence from a second observation after a meaningful
  interval.

An empty, partial, stale, mixed-season, duplicate, malformed, throttled,
unauthorized, or failed response must not advance qualification.

## Readiness observation on 2026-08-30

After UEFA published the finalized league-phase schedule, a secret-safe,
read-only football-data.org check at `2026-08-30T08:40:34Z` returned:

- competition ID `2001` and code `CL`;
- current season ID `2557`, bounded from 2026-09-08 through 2027-01-27;
- 36 distinct participants; and
- zero fixtures for `season=2026`.

The empty fixture collection is a fail-closed `not ready` result, not the first
successful qualification observation. No token, headers, account metadata,
team names, fixture IDs, or raw payload were retained or published. The
curated `champions-league-league-phase` validator profile now requires exactly
36 teams, 144 `LEAGUE_STAGE` fixtures, eight complete matchdays, and one
appearance per team per matchday. It rejects an empty or incomplete response
before evidence can be emitted.

## Re-evaluation triggers

Re-evaluate this decision when any of the following occurs:

1. football-data.org publishes the 2026/27 league-phase fixtures to the free
   `CL` account scope;
2. football-data.org moves `CLQ` into the permanent free tier;
3. UEFA publishes or explicitly permits a documented, automatically updated
   API or calendar feed with stable fixture identity;
4. UEFA grants written permission for the intended API-Football use;
5. another documented zero-cost provider proves full-edition coverage,
   permitted use, stable identity, lifecycle fields, and safe quotas; or
6. the operator changes the currently fixed zero-cost boundary in a new
   explicit decision.

## Sources

Reviewed 2026-08-28:

- [UEFA 2026/27 competition overview](https://www.uefa.com/uefachampionsleague/news/02a6-20d57cfcd03e-407c22a7f465-1000--2026-27-champions-league-teams-dates-draws-format-final/)
- [UEFA 2026/27 qualifying fixtures and format](https://www.uefa.com/uefachampionsleague/news/02a6-20e5a8be4e63-ae971c582f8c-1000--champions-league-qualifying-fixtures-results-dates-how-it-/)
- [UEFA 2026/27 regulations](https://documents.uefa.com/r/Regulations-of-the-UEFA-Champions-League-2026/27/G.1-Introduction-Online)
- [UEFA league-phase draw and publication timing](https://www.uefa.com/uefachampionsleague/draws/)
- [UEFA 2026/27 confirmed league-phase fixtures](https://www.uefa.com/uefachampionsleague/news/02a8-2174c9e9019d-f909a77bd77a-1000--2026-27-champions-league-all-the-league-phase-fixtures/)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org public competition catalog](https://api.football-data.org/v4/competitions)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [football-data.org terms and attribution](https://www.football-data.org/about)
- [football-data.org competition resource](https://docs.football-data.org/general/v4/competition.html)
- [football-data.org match resource](https://docs.football-data.org/general/v4/match.html)
- [football-data.org lookup tables](https://docs.football-data.org/general/v4/lookup_tables.html)
- [football-data.org API policies](https://docs.football-data.org/general/v4/policies.html)
- [API-Football coverage](https://www.api-football.com/coverage)
- [API-Football pricing](https://www.api-football.com/pricing)
- [API-Sports terms](https://api-sports.io/terms)
- [Sportmonks Champions League API](https://www.sportmonks.com/football-api/champions-league-api/)
- [Sportmonks league structure documentation](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/leagues)
- [Sportmonks free plan](https://www.sportmonks.com/football-api/free-plan/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/)
