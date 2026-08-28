# football-data.org EFL Championship Import

## Implemented boundary

Issue #135 adds the 2026/27 EFL Championship regular season to the existing
`football_data` authoritative runtime. The immutable canonical scope is
`football/championship/2026_27`; provider identity is code `ELC`, competition
ID `2016`, and season ID `2509`.

Only the 24-team, 46-matchday, 552-fixture `REGULAR_SEASON` stage is
implemented. The separate seven-fixture play-off stage remains unqualified and
is not requested, imported, reconciled, or used as removal evidence.

## Complete-stage gate

A Championship observation reaches canonical import only when all of these
conditions pass:

- API version `v4`, competition `ELC` / `2016`, and season ID `2509`;
- canonical and provider dates 2026-08-14 through 2027-05-01;
- exactly 24 distinct teams resolving through the reviewed competition-scoped
  mapping;
- exactly 46 matchdays with every team appearing once per matchday;
- exactly 552 unique provider match IDs forming a complete double round robin;
- every fixture has stage `REGULAR_SEASON`, a supported status, UTC kickoff,
  and UTC source-update timestamp;
- the source-update freshness policy passes; and
- match retrieval is either one exact 552-item response or exactly two pages
  containing 500 and 52 items with validated season, limit, and offset values.

An empty, partial, stale, malformed, duplicate, mixed-stage, wrong-offset,
wrong-scope, throttled, or failed observation stops before canonical writes.
The last-known-good SQLite and Outlook state remains available.

## Identity and lifecycle

Provider match IDs remain stable event identities across reschedules and status
changes. Provider team IDs map to reviewed canonical participants, while name
resolution remains competition-scoped. No fuzzy or cross-provider matching is
performed.

The authoritative lifecycle boundary is `complete_stage` with stage
`REGULAR_SEASON`, not `complete_season`. Missing regular-season fixtures can
enter the existing two-distinct-complete-observation reconciliation only after
the exact 552-fixture contract passes. Absence of a play-off fixture can never
cancel or delete a regular-season or play-off event.

## Scheduling and quota

The Championship job shares one throttled `FootballDataClient` with Premier
League and Bundesliga but retains an independent job key, interval, runtime
lock, import run, and failure boundary. A successful live observation uses
three requests when the provider returns all 552 fixtures together and four
requests when documented pagination is used.

```env
FOOTBALL_DATA_ENABLED=true
FOOTBALL_DATA_API_KEY=<operator-secret>
FOOTBALL_DATA_REQUESTS_PER_MINUTE=10
FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS=6.1
SOURCE_JOBS_JSON=[{"job_key":"football-data-premier-league","source_key":"football_data","sport_key":"football","competition_key":"premier_league","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"football-data-bundesliga","source_key":"football_data","sport_key":"football","competition_key":"bundesliga","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"football-data-championship","source_key":"football_data","sport_key":"football","competition_key":"championship","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"openligadb-dfb-pokal","source_key":"openligadb","sport_key":"football","competition_key":"dfb_pokal","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"openligadb-second-bundesliga","source_key":"openligadb","sport_key":"football","competition_key":"second_bundesliga","season_key":"2026_27","role":"authoritative","interval_seconds":21600}]
```

The visible attribution remains:

> Football data provided by the Football-Data.org API

Keep the token only in the operator-controlled secret store. Raw live payloads,
headers, account data, logos, and credentials must not enter source control,
logs, screenshots, issues, or CI artifacts.

## Staging gate

Before the Championship is described as staged or released, isolated staging
must prove:

1. one successful 552-fixture import with `complete_stage`,
   `scope_stage=REGULAR_SEASON`, and removal eligibility;
2. bounded Outlook convergence with no duplicate creation;
3. an unchanged provider rerun and unchanged Graph reconciliation;
4. restart recovery with stable source and Outlook mappings;
5. football-data.org failure isolation while OpenLigaDB jobs and calendar
   synchronization continue; and
6. secret-safe candidate evidence with zero revision-pending mappings.

Production promotion and release publication remain separate manual gates.
