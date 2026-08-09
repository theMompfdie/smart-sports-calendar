# football-data.org Premier League Import

## Implemented boundary

The `football_data` adapter is the sole released authoritative writer for
`football/premier_league/2026_27`. One scheduled cycle makes three API v4
requests: competition `PL`, its 2026 teams, and its 2026 matches with a limit
of 500. Outlook synchronization runs independently at `HEARTBEAT_INTERVAL`, so
additional calendar batches do not consume provider quota. Any provider,
validation, mapping, or persistence failure makes no canonical changes; the
calendar job may still reconcile previously committed events.

The transport sends the API token only as `X-Auth-Token`, applies separate
connect/read timeouts, bounded transient retries, response-size limits, HTTPS
origin validation, and an independent 10-requests-per-minute budget. Tokens,
raw payloads, account identifiers, and authorization headers are not logged or
persisted.

## Complete-snapshot gate

A batch is authoritative only when all of these conditions pass:

- API version `v4`, competition ID `2021`, and code `PL`;
- season ID and dates match canonical `2026_27`;
- exactly 20 distinct reviewed teams resolve to 20 canonical participants;
- exactly 380 distinct stable match IDs form a complete double round robin;
- every match belongs to the expected competition and season;
- every home/away participant is known and distinct;
- `utcDate` and `lastUpdated` are valid UTC timestamps;
- every status belongs to the documented supported vocabulary;
- the newest source update is not future-dated or stale for the season phase.

Empty, short, over-count, duplicate, malformed, stale, wrong-scope, unknown
status, failed, or partial collections produce no canonical fixture writes and
no Outlook handoff. Raw live responses are not retained or committed; normal
CI constructs synthetic dictionaries with the same structural invariants.

## Identity and lifecycle

The provider match ID is the stable event source mapping and does not depend on
title or kickoff. A changed kickoff for the same match ID updates the existing
canonical and Outlook event. Explicit provider cancellation maps to canonical
`cancelled`. Missing identity can contribute deletion evidence only through
the existing two-distinct-complete-observation reconciliation rule.

football-data.org mappings use their own source ID and `football_data:fixture:`
event-key prefix. Existing API-Football source mappings are neither reassigned
nor deleted.

## Configuration

```env
FOOTBALL_DATA_ENABLED=true
FOOTBALL_DATA_API_KEY=<operator-secret>
FOOTBALL_DATA_REQUESTS_PER_MINUTE=10
FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS=6.1
SOURCE_JOBS_JSON=[{"job_key":"football-data-premier-league","source_key":"football_data","sport_key":"football","competition_key":"premier_league","season_key":"2026_27","role":"authoritative","interval_seconds":3600}]
API_FOOTBALL_ENABLED=false
```

The required visible attribution while this data is served is:

> Football data provided by the Football-Data.org API

Before cancelling the subscription, disable retrieval and complete the scoped,
backed-up re-source-or-remove procedure documented in
[`football-data-qualification.md`](football-data-qualification.md). Do not
automatically purge provider-derived data.
