# Football Provider Evaluation

## Purpose

This document defines the requirements and evidence used to select the first
football data provider for SMART Sports Calendar. It supports GitHub Issue #43
and records facts verified on 2026-08-08. Provider documentation, prices, and
terms can change; the sources must be rechecked before purchasing a plan or
enabling production access. The official Premier League/ECAL calendar was
assessed separately on 2026-08-09 for issue #73.

The initial use case is deliberately narrow: import current English Premier
League competition, season, team, and fixture data into the existing canonical
SQLite model. Live scores, statistics, odds, and media assets are not required.

## Mandatory requirements

A candidate must provide all of the following:

1. Current Premier League competition, season, team, and fixture coverage.
2. Stable identifiers for competitions, seasons, teams, and fixtures.
3. Explicit fixture status values covering at least scheduled, postponed,
   cancelled, abandoned, and completed matches.
4. A timezone-aware kickoff representation that can be normalized to UTC.
5. Server-side authentication suitable for a secret supplied by environment
   configuration.
6. Complete deterministic collection retrieval through filtering and, where
   applicable, pagination.
7. Published request quotas or rate limits and observable quota state.
8. Terms that permit using the data to build this application without reselling
   the raw provider feed.
9. Representative documented payloads that can be sanitized and stored as
   deterministic test fixtures.
10. Automated testing without live provider or Microsoft Graph calls.
11. A versioned or otherwise stable API with usable reference documentation.
12. A plan suitable for a low-volume, server-side calendar synchronization
    service.

Failure to establish a mandatory requirement from an authoritative source is a
risk and may disqualify a candidate even when the API is technically capable.

## Desirable requirements

- A free development tier or inexpensive entry plan.
- Explicit last-updated timestamps.
- Date-range, league, season, team, and status filters.
- Machine-readable remaining-quota and reset information.
- Clear timeout, throttling, and retry guidance.
- A small payload surface for fixture-only imports.
- Broad enough coverage to support later domestic and UEFA phases.
- Published change/version information and responsive support.
- No mandatory vendor SDK.
- Clear data, logo, image, attribution, and redistribution rules.

## Evaluation method

Each candidate is rated as `Meets`, `Partial`, or `Does not meet` against the
same criteria. `Partial` means the capability exists but has a documented
constraint, commercial limitation, or material ambiguity. Marketing claims are
not treated as equivalent to technical or contractual guarantees.

No live API requests, trial accounts, credentials, or secrets were used for
this evaluation.

## v0.4.5 Premier League source reassessment

The Premier League's official digital calendar is delivered by ECAL. It is not
approved for automated ingestion: ECAL's public end-user terms limit the
service to personal use and prohibit robots, scraping, data mining, and similar
collection. Because authorized acquisition was not established, the project
did not create a subscription or inspect a personalized ICS payload. Stable
event identity, lifecycle representation, complete-snapshot behavior, and HTTP
cache validators therefore also remain unverified.

The dated evidence, rejection rationale, future iCalendar safety contract, and
parser decision are in
[`premier-league-official-feed-qualification.md`](premier-league-official-feed-qualification.md)
and [ADR 0002](adr/0002-reject-ecal-as-automated-source.md).

`football-data.org` is approved as the 2026/27 Premier League authority by
[ADR 0003](adr/0003-select-football-data-for-premier-league.md). Its public
terms govern registered API use, require visible attribution and credential
confidentiality, and impose a cancellation cleanup obligation. Secret-safe
live qualification proved 20 teams, 380 unique matches, and stable match
identity across two fingerprint-bearing observations.

## Comparison matrix

| Criterion | API-Football | football-data.org | Sportmonks Football API |
| --- | --- | --- | --- |
| Current Premier League fixtures | Meets; league `39` is documented and paid plans cover all competitions | Meets; Premier League is explicitly in the free tier | Meets; Premier League is explicitly supported on paid plans |
| Update speed and freshness | Meets; fixtures are documented as updating every 15 seconds in play, with daily calls recommended when no fixture is live | Partial; free-tier scores and schedules are explicitly delayed; paid tiers provide live scores | Meets; key live events are described as appearing within seconds, with provider verification |
| Stable identifiers | Meets; fixture IDs are documented as unique and immutable | Meets; integer IDs are exposed for competition, season, team, and match resources | Meets; documented league, season, team, and fixture IDs |
| Lifecycle status detail | Meets; includes TBD, postponed, cancelled, abandoned, suspended, technical-loss, walkover, and finished variants | Meets for scheduled, timed, live, suspended, postponed, cancelled, awarded, and finished; abandonment is not a documented match status | Meets; typed state entities are documented, but mapping requires an additional provider type lookup |
| Reschedule and removal behavior | Partial; status changes retain fixture ID, but no dedicated removed status exists, so complete-snapshot reconciliation is required | Partial; status workflow is documented, but explicit deletion/removal guarantees were not found | Partial; state modeling is rich, but explicit removal guarantees still require snapshot reconciliation |
| Kickoff/timezone semantics | Meets; ISO 8601 offset plus Unix UTC timestamp and timezone filtering | Meets; match `utcDate` is explicitly UTC | Partial; `starting_at` is documented, but the adapter must bind it to the response timezone contract |
| Authentication | Meets; `x-apisports-key` request header | Meets; `X-Auth-Token` request header | Meets; API token; examples commonly use a query parameter, so redaction discipline is essential |
| Filtering and pagination | Meets; league, season, date range, status, team, and page metadata | Meets for fixture scope; limit/offset support is documented | Meets; page/limit and response metadata are documented |
| Rate-limit visibility | Meets; daily and per-minute limit/remaining headers | Partial; published per-minute plan limits, but less detailed reset telemetry is documented | Meets; remaining/reset metadata and headers are documented per entity |
| Entry cost for Premier League | Meets; Pro is listed as 19.00/month with 7,500 requests/day; the public page text does not expose the currency symbol, so checkout currency must be confirmed; free tier is 100/day but available data may be restricted | Meets; Premier League fixtures are in the EUR 0/month free tier at 10 calls/minute, with delayed scores/schedules | Partial; Premier League is excluded from the permanent free plan; Starter begins at EUR 29/month |
| Terms and redistribution clarity | Meets with constraints; apps are allowed, raw resale is forbidden, and image/logo rights remain the user's responsibility | Partial; pricing and coverage are public, but no equally explicit public usage/redistribution terms were found during this review | Meets with constraints; derived apps may earn revenue, raw resale is forbidden, and logo/image rights remain the user's responsibility |
| Deterministic offline testing | Meets; documented JSON envelope and examples can be sanitized | Meets; documented resource examples can be sanitized | Meets; documented response examples can be sanitized |
| API stability and documentation | Meets; versioned v3 reference, consistent envelope, status table, and current operational guidance | Meets; versioned v4 reference with focused resource and error documentation | Meets; versioned v3 reference with typed entities, includes, pagination, and errors |
| Operational risk | Moderate; quota is daily and per-minute, shared outbound IPs can reduce effective capacity, and coverage is not guaranteed | Moderate; smallest operational surface, but delayed free-tier data and unclear public licensing terms require confirmation | Moderate; strong quota telemetry and coverage, but higher recurring cost and a richer schema increase adapter complexity |

## Candidate details

### API-Football

API-Football exposes a versioned v3 REST API. The fixture documentation states
that fixture IDs do not change, describes the full fixture-status vocabulary,
and exposes both an ISO 8601 date with an offset and a UTC Unix timestamp.
Fixture queries accept league, season, team, date range, status, and timezone
filters. Responses use a consistent envelope with `errors`, `results`, `paging`,
and `response` fields.

The public pricing page lists a free plan with 100 requests/day and a Pro plan
at 19.00/month with 7,500 requests/day. The page's accessible text does not
expose the currency symbol, so the billing currency must be confirmed in the
dashboard before purchase. The current rate-limit guidance also lists
10 requests/minute for Free and 300 requests/minute or 5 requests/second for
Pro. Limit and remaining values are returned in daily and per-minute response
headers. Dashboard subscriptions reset daily quota at 00:00 UTC.

The terms allow applications, websites, and similar derived projects, but
forbid reselling the raw data. They disclaim guaranteed availability and data
accuracy. Logos and images may require separate rights from their owners and
are therefore outside the Phase 4 fixture import.

Key risks:

- The free plan's available dataset can change and is not guaranteed to include
  all Premier League data needed by production.
- A production deployment should budget for Pro unless a pre-deployment check
  proves the free tier sufficient.
- HTTP 200 can still contain an error or empty response envelope; transport
  success alone is not import success.
- The provider documents HTTP 499 for timeout and 429 for rate limiting; both
  require explicit classification.
- Shared outbound IP rate limiting may reduce effective capacity.
- Removed fixtures are not represented by a dedicated status and require
  reconciliation across complete successful snapshots.

### football-data.org

football-data.org provides a compact v4 API and explicitly includes Premier
League fixtures in its free tier. Its match model includes competition, season,
home and away teams, an immutable-looking integer match ID, `utcDate`, status,
and `lastUpdated`. It has the smallest apparent integration surface of the three
candidates and is attractive for a low-volume calendar application.

The free plan is EUR 0/month, covers 12 competitions, and permits 10 calls per
minute. Scores and schedules may be delayed. Paid plans increase freshness,
coverage, and call limits.

It was not selected in the original 2026-08-08 evaluation because the public
terms had not yet been located and its published match-status vocabulary does
not contain a distinct abandoned status. The 2026-08-09 reassessment located
the general terms: a registered API key is scoped to one application,
credentials must remain confidential, visible attribution is required, and
data may no longer be referenced after subscription cancellation. These terms
remove the earlier discovery ambiguity. The operator accepted the required
attribution and scoped re-source-or-remove cancellation workflow. The source
is approved under ADR 0003 with fail-closed complete-snapshot rules.

### Sportmonks Football API

Sportmonks v3 provides broad coverage, stable resource identifiers, explicit
pagination, typed state entities, and rate-limit information per entity. The
Starter plan allows five selected leagues, provides 2,000 calls per entity per
hour, and starts at EUR 29/month. Premier League access requires a paid plan or
the time-limited trial; the permanent free plan covers other selected leagues.

Its terms permit building derived applications and storing/distributing data,
while prohibiting resale of the provider product. Separate rights are required
for logos and profile photos.

It is not selected because its higher recurring cost and more expansive entity
and include model do not provide material value for the narrow fixture-calendar
scope. It is a strong alternative if later phases require richer live data or
much broader competition coverage.

## Decision summary

API-Football is selected for the initial Premier League integration. It meets
all mandatory technical requirements, provides the most explicit fixture
lifecycle vocabulary of the evaluated candidates, and publishes sufficiently
clear quota and usage terms. The expected production baseline is the Pro plan;
the free plan may be used only for development after confirming that the needed
Premier League dataset is available.

The selection does not authorize credentials, live calls, or provider code in
Phase 4.1. Those belong to later Phase 4 child issues.

## Authoritative sources

Sources were accessed on 2026-08-08.

### API-Football

- [Football API documentation](https://www.api-football.com/documentation)
- [Football API coverage and pricing](https://api-sports.io/sports/football)
- [Rate-limit behavior and headers](https://www.api-football.com/news/post/how-ratelimit-works)
- [API-Sports terms of use](https://api-sports.io/terms)
- [Getting-started guide and pagination](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)

### football-data.org

- [Coverage](https://www.football-data.org/coverage)
- [Pricing](https://www.football-data.org/pricing)
- [Terms, privacy, and attribution](https://www.football-data.org/about)
- [Match resource and statuses](https://docs.football-data.org/general/v4/match.html)
- [API policies and throttling](https://docs.football-data.org/general/v4/policies.html)
- [Errors](https://docs.football-data.org/general/v4/errors.html)

### Sportmonks

- [Football API and pricing](https://www.sportmonks.com/football-api/)
- [Premier League coverage](https://www.sportmonks.com/football-api/premier-league-api/)
- [API v3 structure and pagination](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/api-structure-and-navigation)
- [Rate limits](https://docs.sportmonks.com/v3/api/rate-limit)
- [Terms of service](https://www.sportmonks.com/terms-of-service/)

## Revalidation checklist

Before purchasing or enabling production access, verify:

- Premier League league ID and current-season availability;
- exact plan price including VAT and billing period;
- daily and per-minute quota values;
- data retention, derived-use, and attribution permissions for the intended
  deployment;
- fixture, team, season, and league ID stability;
- current status enumeration and removal behavior;
- API version and deprecation notices; and
- whether the deployment's outbound IP is shared.
