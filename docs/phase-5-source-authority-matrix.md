# Phase 5 Source and Authority Matrix

## Status and decision boundary

This record implements the source-qualification decision for GitHub issue #108.
Initial evidence was reviewed on 2026-08-16. The Bundesliga decision was
updated from two live observations and operator plan confirmation on
2026-08-17. Provider coverage, prices, terms, competition formats, and season
data can change and must be revalidated before an operator accepts a
subscription or enables a source.

The matrix evaluates the released Premier League baseline and all eleven Phase
5 candidates. It does not itself enable a source, add catalog data, or
authorize a paid plan. The final `v0.5.0-beta.1` release boundary contains the
six explicitly assigned authorities recorded below.

Implementation status update, 2026-08-28: the qualified Bundesliga,
Championship regular season, DFB-Pokal, 2. Bundesliga, and ÖFB-Cup paths passed
isolated live staging, Outlook convergence, unchanged-cycle validation,
restart, failure isolation, and recovery. Issue #118 qualifies OpenLigaDB
rather than the rejected paid Sportmonks candidate for the DFB-Pokal. ADR 0007
permanently limits that authority to non-destructive `partial` observations.

Cost-policy update, 2026-08-27: issue #124 evaluates the no-cost OpenLigaDB
`bl2` / 4938 candidate before the paid football-data.org fallback. A permitted,
technically trustworthy no-cost source is preferred for this hobby project even
when it requires another bounded adapter. Cost does not weaken qualification,
identity, lifecycle, failure, licensing, or attribution requirements.

Austrian Bundesliga update, 2026-08-28: issue #125 defers the competition for
`v0.5.0-beta.1`. No reviewed no-cost candidate provides a permitted complete
scope, and no paid plan was approved. The exact re-evaluation triggers are in
the focused qualification record.

FA Cup update, 2026-08-28: issue #126 also defers the competition for
`v0.5.0-beta.1`. The official FA sources are manual-only, OpenLigaDB has no FA
Cup competition, TheSportsDB has no free 2026/27 scope, and no paid provider or
separate data-rights clearance was approved.

EFL Cup update, 2026-08-28: issue #127 defers the competition for
`v0.5.0-beta.1`. The official ECAL calendar is not permitted for automated
collection, OpenLigaDB has no EFL Cup competition, TheSportsDB free retrieval
is capped at 15 events, other free calendar/export services lack the required
rights and deterministic authority contract, and no paid provider was approved.

ÖFB-Cup update, 2026-08-28: issue #128 qualifies the official competition-wide
ÖFB iCalendar feed for private, non-destructive `partial` use. Two stable
secret-safe observations proved unique provider fixture UIDs, UTC kickoffs,
structured participant identities, exact first- and second-round totals, and a
six-hour refresh contract. Issue #145 implements the provider, catalog,
runtime, and SQLite-to-mocked-Graph path. Isolated staging passed with 48
current-season fixtures, stable Outlook identity and attribution, unchanged
restart behavior, controlled provider failure, and clean recovery.

Decision meanings:

- `Qualified`: implementation may proceed with the named authority and stated
  conditions.
- `Conditional`: implementation remains blocked by every named condition.
- `Deferred`: the competition is outside the `v0.5.0-beta.1` implementation
  boundary.
- `Rejected`: no reviewed candidate is suitable under the stated constraints.

Only one authoritative writer may be enabled for a competition and season.
Candidates and existing legacy mappings are not failover writers. Verification
and bootstrap observations cannot create removal evidence.

## Provider-level findings

### football-data.org API v4

The public competition catalog and coverage page expose all matrix targets. The
catalog identifies competitions by numeric ID and, except for the ÖFB Cup, a
short code. Match resources expose stable-looking numeric IDs, UTC kickoff,
status, stage, group, and source-update fields. Match collections support
season, matchday, status, date, stage, and group filters and `limit`/`offset`
pagination with a maximum page size of 500.

The public catalog observed on 2026-08-16 reported these relevant identifiers
and commercial tiers:

| Competition | ID | Code | Type | Tier | Current catalog season observation |
| --- | ---: | --- | --- | --- | --- |
| Premier League | 2021 | `PL` | league | free | 2026/27 |
| Championship | 2016 | `ELC` | league | free | 2026/27 |
| Bundesliga | 2002 | `BL1` | league | free | 2026/27 |
| 2. Bundesliga | 2004 | `BL2` | league | Standard | 2026/27 |
| Austrian Bundesliga | 2012 | `ABL` | league | Advanced | 2026/27 ground-round dates only |
| FA Cup | 2055 | `FAC` | cup | Standard | 2025/26 |
| EFL Cup | 2139 | `FLC` | cup | Advanced | 2026/27 |
| DFB-Pokal | 2011 | `DFB` | cup | Standard | 2026/27 |
| ÖFB Cup | 2027 | none | cup | Pro | stale 2020/21 |
| UEFA Champions League | 2001 | `CL` | cup | free | 2025/26 |
| UEFA Europa League | 2146 | `EL` | cup | Standard | 2025/26 |
| UEFA Conference League | 2154 | `UCL` | cup | Pro | 2025/26 |

The public pricing page currently lists Free at EUR 0 for 12 competitions,
Standard at EUR 49 for 30, Advanced at EUR 99 for 50, and Pro at EUR 199 for
100 competitions per month. The pricing page and API policy documentation do
not currently agree on all per-minute plan limits. The operator must use the
lower verified dashboard/configuration limit until the discrepancy is resolved
and must not purchase a plan based on this record alone.

The terms scope a key to one application, require credential secrecy and the
visible attribution `Football data provided by the Football-Data.org API`, and
require the application to stop referencing obtained data when the subscription
ends. Logos and images require separate rights. Availability, accuracy, and
completeness are not guaranteed. Those conditions remain part of every
football-data.org decision.

### Sportmonks Football API v3

Sportmonks publishes fixture and season-schedule coverage for all target
domestic competitions and the UEFA candidates. Relevant published league IDs
include Championship `9`, FA Cup `24`, EFL Cup `27`, Bundesliga `82`,
2. Bundesliga `85`, DFB-Pokal `109`, Austrian Bundesliga `181`, Austrian Cup
`187`, and UEFA Conference League `2286`. Published pages also identify the
Premier League as `8`, Champions League as `2`, and Europa League as `5`.
Identifiers must still be resolved from a live league/season lookup because
marketing and documentation pages have previously disagreed on individual cup
IDs.

API v3 provides fixture, schedule, season, stage, round, group, participant,
and typed state resources. It documents pagination and explicit postponed,
cancelled, suspended, interrupted, and abandoned states. Knockout placeholders
can exist before participants are known, so placeholder identity and replacement
behavior require live validation before canonical mapping.

The Starter plan currently starts at EUR 29/month paid monthly, plus VAT where
applicable, and permits five selected leagues with 2,000 calls per entity per
hour. Paid plans include a 14-day trial that requires a payment method and
automatically converts unless cancelled. The operator must choose and accept a
subscription; this project does not do so automatically.

The terms permit derived applications and storage/distribution of returned
data while prohibiting raw-product resale. Use is domain-scoped. Logos and
images have separate rights. Completeness, accuracy, and availability are not
guaranteed. Cancellation stops renewal but preserves access only through the
paid billing period. A source replacement and retained-data decision is
therefore required before access ends.

### OpenLigaDB API v1

OpenLigaDB is a free community-maintained sports database intended for
automated use through an unauthenticated JSON API. Its 2026 directory exposes
the DFB-Pokal as league `4945`, shortcut `dfb`, and the 2. Bundesliga as league
`4938`, shortcut `bl2`, both for season `2026`. Matches expose fixture,
participant, league, season, and group IDs plus UTC kickoffs and provider-local
update timestamps.

The API data is offered under ODbL 1.0. Public produced works require
attribution, and public adapted databases can trigger share-alike and
machine-readable-access obligations. Linked club logos and icons have separate
rights and are excluded from retrieval and persistence.

Community editing and the absence of explicit placeholder, cancellation,
postponement, pagination, quota, and rate-limit semantics require a
competition-specific fail-closed contract. The incrementally published
DFB-Pokal source must stay `partial`. The 2. Bundesliga candidate exposes a
structurally provable 18-team, 34-matchday, 306-fixture double round robin.
ADR 0009 qualifies that scope but keeps initial operation non-destructive.

### API-Football v3

API-Football has broad technical coverage, stable fixture IDs, detailed states,
pagination, and published quota headers. It remains usable only for existing
legacy mappings or non-authoritative verification under the current review.
Its terms explicitly state that API-Sports does not grant a license to use or
publish supplied competition data and that the customer must obtain permission
from the competent rights holders. No such written authorization is recorded
for the Phase 5 targets. It is therefore rejected as a new Phase 5 authority
unless the operator records competition-specific rights clearance in a later
decision.

### Authentication, caching, and retention boundary

| Provider | Authentication and secret handling | Caching, persistence, derived use, and exit condition |
| --- | --- | --- |
| football-data.org | Send the application token only in `X-Auth-Token`; never log the header, client/account headers, raw errors, or a secret-bearing URL. | No separate public cache TTL was found. Persist only the fixture fields required by the calendar under the one-application and attribution conditions. Before cancellation, disable retrieval and either qualify a replacement source or remove provider-derived events, mappings, and retained data through a scoped, backed-up operator procedure. |
| Sportmonks | Keep the API token in environment/secret-store configuration and send it only in the supported `Authorization` header. Never place `api_token` in request URLs; sanitize transport failures. | Terms allow storage/distribution of returned data and derived applications but not resale of the service or raw product. Use is domain-scoped. Before subscription access ends, decide and document replacement, retained-data, and source-mapping handling. |
| OpenLigaDB | Public read access requires no account or token. Use only fixed HTTPS API paths and never retrieve linked logo/icon resources. | Data is ODbL 1.0. Record attribution and the deployment-specific produced-work/adapted-database decision before approval. Observations remain non-destructive unless competition-specific qualification proves a complete scope and an ADR authorizes removal evidence. |
| TheSportsDB | The public V1 development key is not secret; stay within the documented 30-request-per-minute free limit and use only documented API paths. | Community data and third-party rights require competition-specific review. Free season retrieval is capped at 15 events without documented pagination, so it cannot provide complete Austrian Bundesliga observations. |
| API-Football | Send the token only in `x-apisports-key`; redact authentication, account, quota, and raw-error details. | No new authoritative caching, persistence, or publication is approved because the provider does not grant the required data license. Existing legacy mappings remain non-authoritative unless separate rights clearance changes this decision. |

Provider response ordering is never completeness evidence. Adapters must consume
all advertised pages, reject pagination gaps or inconsistent totals, and sort
stable fixture identifiers before fingerprinting. A documented empty completed
scope can be valid only after competition-specific qualification; an
unexpected empty, stale, filtered, partial, malformed, or failed response is
non-authoritative and cannot advance removal evidence.

## Competition decision matrix

| Competition | Intended season | Phase 5.1 format and maximum safe observation | Proposed authority | Outcome | Blocking reason or operating condition |
| --- | --- | --- | --- | --- | --- |
| English Premier League | 2026/27 | `league`; authoritative unfiltered `complete_season` | football-data.org `PL` / 2021 | **Qualified** | Existing ADR 0003 and two-observation live evidence apply; 20 teams and 380 unique fixtures; visible attribution and cancellation cleanup remain mandatory. |
| EFL Championship | 2026/27 | `league`; authoritative `complete_stage` for `REGULAR_SEASON`; play-offs remain a separate `partial` scope | football-data.org `ELC` / 2016 | **Implemented and staged** | Two stable live observations proved 24 teams, 46 matchdays, and 552 unique fixtures. The runtime accepts only one exact 552-match response or documented `500 + 52` pagination and fails closed otherwise. Isolated live staging, unchanged-cycle idempotency, restart recovery, and provider-failure isolation passed. The seven play-off fixtures require later qualification and cannot provide removal evidence. |
| German Bundesliga | 2026/27 | `league`; authoritative unfiltered `complete_season` | football-data.org `BL1` / 2002 | **Implemented and staged** | ADR 0006 and issue #114 provide the qualified profile, reviewed 18-team mapping, complete-season runtime, offline SQLite-to-Graph proof, and isolated live staging evidence. Release remains a separate gate. |
| German 2. Bundesliga | 2026/27 | `league`; structurally `complete_season`, initially removal-disabled | OpenLigaDB league 4938 / `bl2` / 2026; football-data.org only as paid fallback | **Implemented and staged** | Issue #132 adds the reviewed 18-team catalog/mapping, multi-job runtime, strict 306-fixture contract, offline SQLite-to-Graph proof, and isolated live staging evidence. ADR 0009 requires review of identity-set changes and keeps operation non-destructive. |
| Austrian Bundesliga | 2026/27 | `league`; at most `partial` before explicit stage qualification | No authority assigned; Sportmonks league 181 remains a paid future candidate | **Deferred** | Official sources are manual-only; OpenLigaDB `BLÖ` / 5990 returned 36 groups and zero fixtures; football-data.org is paid and does not prove the full split lifecycle; API-Football lacks recorded data-rights clearance; TheSportsDB free retrieval stops at 15 events. No paid plan was approved. Re-evaluate only under the triggers in the focused qualification record. |
| FA Cup | 2026/27 | `knockout_cup`; `partial` and removal-disabled until a future round-specific qualification | No authority assigned; Sportmonks league 24 remains a paid future candidate | **Deferred** | Official sources are manual-only; OpenLigaDB has no FA Cup competition; football-data.org is paid and current-season scope is unproven; API-Football lacks recorded rights clearance; TheSportsDB has no free 2026/27 scope; OpenFootball has no current cup schedule or stable fixture IDs. No paid plan was approved. |
| EFL Cup | 2026/27 | `knockout_cup`; `partial` and removal-disabled until a future round-specific qualification | No authority assigned; Sportmonks league 27 remains a paid future candidate | **Deferred** | Official ECAL automation is prohibited; OpenLigaDB has no competition; football-data.org and Sportmonks require paid coverage; API-Football lacks recorded rights clearance; TheSportsDB free retrieval is capped at 15 events; other free calendars lack the required authority contract. No paid plan was approved. |
| DFB-Pokal | 2026/27 | `knockout_cup`; permanently `partial` with this provider | OpenLigaDB league 4945 / `dfb` / 2026 | **Implemented and staged** | ADR 0007 records two stable live observations and issue #119 adds the catalog, reviewed 64-team mapping, runtime, offline SQLite-to-Graph proof, exact attribution, permanent removal disablement, and isolated live staging evidence. |
| ÖFB Cup | 2026/27 | `knockout_cup`; permanently `partial` under the current contract | Official ÖFB competition iCalendar feed | **Implemented and staged** | Two stable observations proved 48 current fixtures across rounds one and two, unique numeric UIDs, UTC kickoffs, structured participant identities, and `PT6H` refresh. Issue #145 implements the reviewed 64-team catalog, permanent-partial runtime, strict provider boundary, offline SQLite-to-Graph proof, and isolated live staging. The multi-season feed has no explicit cancellation or completeness marker, so absence is never destructive. Use is limited to the operator's private calendar and the opaque feed URL remains secret. |
| UEFA Champions League | 2026/27 | not representable by one Phase 5.1 format; qualifying, league, and knockout scopes | Sportmonks league 2 as future candidate | **Deferred** | The hybrid lifecycle exceeds ADR 0004, participants and fixtures are incremental, and current authority evidence is incomplete. No `v0.5.0-beta.1` release claim. |
| UEFA Europa League | 2026/27 | not representable by one Phase 5.1 format; qualifying, league, and knockout scopes | Sportmonks league 5 as future candidate | **Deferred** | Same hybrid-model gap and incremental completeness risk as the Champions League. No `v0.5.0-beta.1` release claim. |
| UEFA Conference League | 2026/27 | not representable by one Phase 5.1 format; qualifying, league, and knockout scopes | Sportmonks league 2286 as future candidate | **Deferred** | Same hybrid-model gap and incremental completeness risk as the Champions League. No `v0.5.0-beta.1` release claim. |

The provider candidate set is not approval to run multiple authorities. A
future implementation must select exactly one provider assignment for each
competition and season after its conditions pass.

## Lifecycle and completeness conclusions

### Domestic leagues

The German Bundesliga and 2. Bundesliga have a deterministic 18-team,
34-matchday, 306-fixture regular-season shape. A verified unfiltered season
snapshot can therefore become `complete_season` and removal-capable under ADR
0004.

The Championship has 24 clubs and 552 regular-season fixtures. Two stable live
observations proved that football-data.org returns that exact double round
robin as `REGULAR_SEASON`. The provider currently returns all 552 matches in
one response despite a requested limit of 500; a future adapter must accept
only that exact complete response or validated `500 + 52` pagination. The
seven revised play-off fixtures remain a separate progressive scope because
their participants are not known until the table is complete.

The Austrian Bundesliga publishes a 22-round ground phase before splitting
into championship and relegation groups for rounds 23 through 32. A ground-
phase schedule is not a complete season. Phase-specific completeness and
stable post-split identity must be implemented before any removal decision.

### Domestic cups

Cup draws progressively reveal participants and fixtures. A successful request
for all currently known matches is not a complete season. The maximum future
destructive boundary is a provider- and competition-qualified
`complete_stage` or `complete_round`. ADR 0004 now supports bounded generic
reconciliation for those exact scopes, but every listed cup remains partial and
non-destructive until its provider-specific completeness evidence and mapping
contract are qualified.

### UEFA competitions

The three UEFA candidates combine qualifying rounds, a league phase, and
knockout rounds. ADR 0004 currently models a competition as either `league` or
`knockout_cup`; choosing either would erase material lifecycle semantics.
These competitions require a separate hybrid-format design before source
qualification can complete.

## First implementation wave

The first approved implementation candidate was the **2026/27 German
Bundesliga**, using football-data.org `BL1` / 2002. Its completed implementation
established the reusable multi-competition runtime used by later slices.

The EFL Championship regular-season qualification is complete under #123 and
its bounded implementation is delivered by #135. Isolated staging, restart,
unchanged-cycle, and provider-failure validation passed on 2026-08-28. Play-off
ingestion remains out of scope until separate live qualification succeeds.

The FA Cup, EFL Cup, Austrian Bundesliga, and UEFA competitions are not part of
the first implementation wave. FA Cup, EFL Cup, and Austrian Bundesliga have
explicit no-authority deferrals. DFB-Pokal was implemented later through its
separately qualified permanent-partial OpenLigaDB scope. ÖFB-Cup now has a
qualified official no-cost source, but remains unreleased until its separate
implementation and isolated staging gates pass.

## Secret-safe operator validation gate

Public catalog responses are discovery evidence only. For every conditional
candidate, an operator must perform an isolated, read-only validation before
the outcome can change to `Qualified`:

1. Use a dedicated development or staging credential and the documented HTTPS
   API only. Do not target SQLite, Outlook, Microsoft Graph, or production.
2. Enter the token interactively or through the existing secret store. Never
   place it in command history, a URL, a file, a screenshot, an issue, or CI.
3. Resolve competition and current-season identity from the provider rather
   than trusting the IDs in this dated record.
4. Retrieve every page in the intended unfiltered observation scope. Fail on
   HTTP errors, provider errors, malformed envelopes, pagination gaps,
   duplicates, wrong competition/season, unknown participants, non-UTC
   timestamps, unsupported states, placeholders outside the documented policy,
   or an unexplained empty result.
5. Repeat the same retrieval after a meaningful interval. Compare a SHA-256
   fingerprint of sorted fixture IDs plus aggregate counts and boundaries.
6. Record only provider/API version, competition and season IDs, counts,
   pagination totals, status/stage/round counts, UTC date boundaries, latest
   source-update time, request count, sanitized quota values, and the fixture-ID
   fingerprint. Do not record raw payloads, names, fixture IDs, account values,
   headers, or secret-bearing URLs.
7. Recheck current coverage, plan, quota, terms, attribution, cancellation,
   retention, and cost. Prefer a permitted, trustworthy no-cost candidate. The
   operator must explicitly approve any paid fallback or changed terms.
8. Update this decision record and add a focused ADR before implementation.

The qualification command exposes only reviewed, immutable competition
profiles. Premier League remains strict at `PL` / 2021, 20 teams, and 380
matches; Bundesliga is strict at `BL1` / 2002, 18 teams, and 306 matches.
Competition identities and expected counts are not free-form operator input.
Normal CI remains credential-free and network-free.

## Polling and operational budget

The initial low-volume policy is one complete schedule observation per enabled
competition every six hours, plus one operator-triggered observation after a
known draw or schedule publication. This is a budget, not permission to enable
a job.

- Four cycles/day require at least 120 collection calls/month before
  pagination, retries, qualification, catalog lookups, and monitoring.
- The Bundesliga fits within one football-data.org match response at 306
  fixtures. Championship qualification observed all 552 regular-season
  fixtures in one response despite the requested limit of 500; the adapter
  must also retain validated `500 + 52` support if provider behavior changes.
- Bundesliga qualification observed exactly three requests per snapshot. The
  operator confirmed the Free plan at 10 requests per minute after the optional
  quota header was absent in both observations. One immediate complete retry
  therefore uses six requests and retains four requests of headroom.
- Each implementation issue must calculate its exact calls/cycle from the live
  pagination result, reserve retry headroom, and stay below the lower of the
  documented and dashboard limits.
- Authentication, catalog, collection, and retry calls all count against that
  budget; no implementation may assume that a schedule endpoint costs one call
  until live response metadata proves it.
- OpenLigaDB qualification uses three unauthenticated requests per complete
  competition observation. No published quota permits aggressive polling;
  retain the shared six-hour default and bounded retries.
- Sources must honor `Retry-After` where provided, use bounded backoff, avoid
  overlapping jobs, and fail closed without advancing removal evidence.
- A stale, partial, malformed, empty, throttled, timed-out, or failed snapshot
  preserves the last known good canonical state.

## Required follow-up by outcome

| Outcome group | Required work before release |
| --- | --- |
| Bundesliga | Isolated staging, attribution, and unchanged-cycle idempotency are complete; retain the evidence through the release gate. |
| DFB-Pokal | Isolated OpenLigaDB staging and Outlook verification are complete; retain permanent-partial scope and ODbL attribution. |
| Championship and 2. Bundesliga | Both implemented scopes passed isolated live staging. Retain the Championship regular-season boundary and the removal-disabled OpenLigaDB 2. Bundesliga boundary through the release gate. |
| Austrian Bundesliga | Deferred by issue #125. Re-evaluate only when a permitted complete no-cost source appears, OpenLigaDB becomes structurally complete and stable, an official machine-readable feed is authorized, or the operator explicitly approves paid Sportmonks qualification. |
| FA Cup | Deferred by issue #126. Re-evaluate only when an official permitted feed appears, OpenLigaDB gains a stable complete intended scope, another permitted no-cost source qualifies, rights clearance is recorded, or the operator explicitly approves paid provider qualification. |
| EFL Cup | Deferred by issue #127. Re-evaluate only when an official permitted feed appears, ECAL/EFL grants written automation permission, OpenLigaDB gains a stable intended scope, another permitted no-cost source qualifies, rights clearance is recorded, or the operator explicitly approves paid provider qualification. |
| ÖFB-Cup | Isolated staging, Outlook attribution, identity stability, failure isolation, and recovery are complete; retain the private permanent-partial semantics through the release gate. |
| UEFA competitions | Hybrid competition-capability ADR and model implementation; then repeat source and live qualification. |
| All new competitions | Explicit source assignment with exactly one authority; scheduler isolation; credential-free unit/integration coverage; release documentation that distinguishes planned, qualified, implemented, staged, and released. |

No database migration was approved by the original #108 qualification slice.
The later synchronization-prioritization issue #136 added deterministic,
idempotent migration `008_add_calendar_sync_revisions`, independently reviewed
and covered by repository and staging-convergence tests.

## Primary evidence

Provider evidence, reviewed 2026-08-16:

- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org public competition catalog](https://api.football-data.org/v4/competitions)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [football-data.org terms and attribution](https://www.football-data.org/about)
- [football-data.org competition resource](https://docs.football-data.org/general/v4/competition.html)
- [football-data.org match resource](https://docs.football-data.org/general/v4/match.html)
- [football-data.org lookup tables](https://docs.football-data.org/general/v4/lookup_tables.html)
- [football-data.org API policies](https://docs.football-data.org/general/v4/policies.html)
- [Sportmonks coverage](https://www.sportmonks.com/football-api/coverage/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [Sportmonks API v3 pagination](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/introduction/pagination)
- [Sportmonks fixture states](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes/states)
- [Sportmonks fixture endpoint](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/fixtures/get-all-fixtures)
- [TheSportsDB API guide](https://www.thesportsdb.com/docs_api_guide)
- [TheSportsDB terms](https://www.thesportsdb.com/docs_terms_of_use.php)
- [TheSportsDB pricing](https://www.thesportsdb.com/docs_pricing.php?billing=annual)
- [API-Sports coverage](https://www.api-football.com/coverage)
- [API-Football pricing and quotas](https://api-sports.io/sports/football)
- [API-Sports terms](https://api-sports.io/terms)

Competition-format evidence, reviewed 2026-08-16:

- [EFL Championship competition](https://www.efl.com/competitions/efl-championship/)
- [2026/27 Championship play-off format](https://www.efl.com/news/2026/march/05/efl-statement--sky-bet-championship-play-off-format/)
- [Bundesliga fixture-list structure](https://www.bundesliga.com/en/bundesliga/news/how-the-bundesliga-fixture-list-is-made-bayern-munich-borussia-dortmund-20316)
- [2026/27 Bundesliga and 2. Bundesliga fixtures](https://www.bundesliga.com/en/bundesliga/news/2026-27-fixture-lists-now-available-38068)
- [Austrian Bundesliga competition format](https://www.bundesliga.at/de/news/artikel/bundesliga-spielmodus-2023-24)
- [2026/27 Austrian Bundesliga ground-round schedule](https://www.bundesliga.at/de/news/artikel/admiral-bundesliga-spielplan-fuer-den-grunddurchgang-2026-27)
- [Austrian Bundesliga source qualification](austrian-bundesliga-source-qualification.md)
- [FA Cup source qualification](fa-cup-source-qualification.md)
- [EFL Cup source qualification](efl-cup-source-qualification.md)
- [ÖFB-Cup source qualification](oefb-cup-source-qualification.md)
- [DFB-Pokal format](https://www.dfb.de/en/men/mens-dfb-pokal)
- [DFB-Pokal 2026/27 dates](https://www.dfb.de/maenner/wettbewerbe/dfb-pokal/rahmentermine)
- [FA Cup round dates](https://www.thefa.com/competitions/thefacup/round-dates)
- [EFL 2026/27 calendar](https://www.efl.com/news/2026/may/29/everything-you-need-to-know-about-the-2026-27-efl-season/)
- [2026/27 Champions League format](https://www.uefa.com/uefachampionsleague/news/025f-0fd4b42cc0a7-74498b7df63b-1000/)
- [2026/27 Europa League format](https://www.uefa.com/uefaeuropaleague/news/02a6-20d57d095740-e1e0b3de85df-1000--2026-27-europa-league-teams-dates-draws-format-final/)
- [2026/27 Conference League qualifying](https://www.uefa.com/uefaconferenceleague/news/02a6-20e5e911587f-cc10425958b3-1000--conference-league-qualifying-fixtures-results-dates-how-it-/)

Existing project evidence:

- [Premier League live qualification](football-data-qualification.md)
- [Premier League authority decision](adr/0003-select-football-data-for-premier-league.md)
- [Championship regular-season authority decision](adr/0008-select-football-data-for-championship-regular-season.md)
- [competition lifecycle model](adr/0004-model-competition-lifecycle-scopes.md)
- [provider integration contract](provider-integration-contract.md)
- [source orchestration](source-orchestration.md)
