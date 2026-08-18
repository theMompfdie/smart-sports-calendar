# football-data.org Bundesliga Import

## Implemented boundary

Phase 5.5 adds the 2026/27 German Bundesliga as the first additional domestic
league supported by the `football_data` authoritative runtime. Its immutable
profile is `football/bundesliga/2026_27`, provider code `BL1`, competition ID
2002, and provider season ID 2522.

The implementation reuses the provider transport, canonical fixture import,
source assignment, SQLite persistence, and Outlook synchronization boundaries.
It does not add a second provider, automatic failover, cross-provider field
aggregation, standings, scores, media, or another competition.

The Bundesliga implementation is covered offline through a synthetic complete
provider snapshot, SQLite, and a recording Graph client. Live staging remains
an explicit operator gate and must not be inferred from normal CI.

## Complete-snapshot gate

A Bundesliga observation may become authoritative removal evidence only after
all of these checks pass:

- API version `v4`, competition code `BL1`, and competition ID `2002`;
- provider season ID `2522` and canonical season `2026_27`;
- season dates 2026-08-28 through 2027-05-22;
- exactly 18 distinct reviewed teams mapped to canonical participants;
- exactly 34 matchdays with every team appearing once per matchday;
- exactly 306 distinct stable match IDs forming a complete double round robin;
- only the reviewed regular-season stage and supported match statuses;
- valid UTC kickoff and source-update timestamps; and
- a successful, unfiltered response inside the freshness policy.

An empty, partial, malformed, stale, filtered, wrong-scope, or failed
observation produces neither canonical writes nor removal evidence. The last
known good state remains available for an independently scheduled Outlook
synchronization cycle.

## Identity, lifecycle, and coexistence

The provider match ID is the stable event identity. Kickoff or status changes
update the existing canonical event and its existing Outlook mapping rather
than creating a duplicate. The observation scope is `complete_season` for a
regular double round robin; the existing two-distinct-complete-observation rule
continues to guard missing-fixture reconciliation.

All football-data.org mappings retain the `football_data` source ID. Existing
Premier League and API-Football mappings are not reassigned, merged, or
deleted. Exactly one enabled authoritative source assignment is required for
each competition and season.

## Scheduling and quota

Premier League and Bundesliga have independent source job identities, due
times, locks, run metadata, and failure reporting. Both jobs use one shared
`FootballDataClient`, so retries and the minimum request interval contribute to
one provider-wide quota budget. A failure in one competition job is logged with
its safe job key and does not prevent the scheduler from running the other job.

The initial Bundesliga interval is six hours. One successful snapshot uses
three requests. Keep the independently enforced Free-plan ceiling at no more
than 10 requests per minute even when the optional provider quota header is
absent.

```env
FOOTBALL_DATA_ENABLED=true
FOOTBALL_DATA_API_KEY=<operator-secret>
FOOTBALL_DATA_REQUESTS_PER_MINUTE=10
FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS=6.1
SOURCE_JOBS_JSON=[{"job_key":"football-data-premier-league","source_key":"football_data","sport_key":"football","competition_key":"premier_league","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"football-data-bundesliga","source_key":"football_data","sport_key":"football","competition_key":"bundesliga","season_key":"2026_27","role":"authoritative","interval_seconds":21600}]
API_FOOTBALL_ENABLED=false
```

The visible attribution remains:

> Football data provided by the Football-Data.org API

Keep the token only in the operator-controlled secret store. Do not retain raw
live payloads, provider headers, secret-bearing URLs, account data, logos, or
crests in source control, logs, CI artifacts, issues, or screenshots.

## Live staging gate

Before this scope is described as staged or released, the operator must:

1. revalidate the active plan, coverage, immutable IDs, season dates, complete
   counts, quota, terms, and attribution;
2. enable the Bundesliga job only in the isolated staging stack and calendar;
3. verify the complete import, unchanged-cycle idempotency, one controlled
   fixture update, restart/recovery behavior, and source-specific logs;
4. confirm the Premier League job stays healthy under the shared quota budget;
5. verify that production volumes, databases, credentials, and calendars were
   not touched; and
6. record sanitized evidence without raw responses or credentials.

Production promotion remains manual and requires the normal release gates.
