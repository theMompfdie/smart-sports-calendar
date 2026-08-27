# OpenLigaDB 2. Bundesliga Import

## Status and boundary

Issue #132 implements the OpenLigaDB authority qualified by #124 and ADR 0009
for the 2026/27 German 2. Bundesliga regular season.

The runtime is intentionally removal-disabled. It may create and update known
fixtures, but a missing provider fixture never cancels or deletes canonical or
Outlook state. Qualification proves the structural 306-fixture season shape;
it does not override the provider's community-editing and lifecycle limits.

## Provider and mapping

- source: OpenLigaDB public API v1;
- league: `4938`;
- shortcut: `bl2`;
- provider season: `2026`;
- canonical scope: `football/second_bundesliga/2026_27`;
- job key: `openligadb-second-bundesliga`;
- polling default: 21,600 seconds;
- authentication: none;
- license: ODbL 1.0.

The runtime validates exactly 18 reviewed participant ID/name pairs, 34 stable
matchdays, nine fixtures and one appearance per participant per matchday, 306
unique fixture IDs, and one fixture for every directed participant pairing.
Any identity-set change fails closed for operator review.

Exactly 18 reviewed finished fixtures omit `timeZoneID`. This profile alone may
accept the missing declaration because every fixture still contains an
explicit UTC kickoff. DFB-Pokal timezone validation remains strict.

## Configuration

```env
OPENLIGADB_ENABLED=true
SOURCE_JOBS_JSON=[{"job_key":"openligadb-second-bundesliga","source_key":"openligadb","sport_key":"football","competition_key":"second_bundesliga","season_key":"2026_27","role":"authoritative","interval_seconds":21600}]
```

The DFB-Pokal job may be enabled in the same JSON array. Both jobs share the
bounded provider client but use separate adapters, services, orchestrators,
runtime locks, scheduler state, sync runs, and canonical scopes.

## Persistence and lifecycle

Competition, season, participant, and fixture correlation uses stable provider
IDs. Names are validation evidence and never substitute for identity. The
canonical league stage is `regular_season`; matchdays normalize to
`matchday-1` through `matchday-34`.

Every runtime observation is emitted as `partial`, `complete=false`, and
`removal_eligible=false`. Allowed import decisions are `CREATE`, `UPDATE`, and
`SKIP`. Empty, malformed, incomplete, stale, wrong-scope, network-failed, or
identity-changed responses preserve last-known-good state.

The source metadata and Outlook event body retain exactly:

`Fixture data provided by OpenLigaDB (ODbL 1.0): https://www.openligadb.de/`

Logo/icon URLs and raw provider responses are neither fetched separately nor
persisted.

## Verification

Normal CI is credential-free and network-free. Synthetic 306-fixture tests
cover the complete provider contract. SQLite-to-mocked-Graph integration proves
first import, unchanged rerun, reschedule update, stable Outlook identity, and
non-destructive missing-fixture behavior.

Before merge readiness and release inclusion, isolated staging must prove a
fresh qualification, first import, unchanged rerun, restart, update handling,
attribution, and failure isolation using only staging database, calendar,
configuration, credentials, and logs. Production promotion remains manual and
out of scope.
