# OpenLigaDB Nations League A Import

## Status and boundary

Issue #170 implements the OpenLigaDB authority qualified by #164 and selected
by ADR 0012 for the 2026/27 UEFA Nations League League A group phase.

The exact boundary is four League A groups, 16 participants, and 48 fixtures
from 24 September through 17 November 2026. Leagues B, C, and D and every later
quarter-final, play-off, semi-final, third-place, and final fixture remain
excluded. The runtime is removal-disabled: a missing provider fixture never
cancels or deletes canonical or Outlook state.

## Provider and mapping

- source: OpenLigaDB public API v1;
- league: `5978`;
- shortcut: `nla`;
- provider season: `2026`;
- canonical scope: `football/uefa_nations_league/2026_27`;
- canonical stage: `league_a_group_phase`;
- stage kind: `league_phase`;
- job key: `openligadb-uefa-nations-league`;
- polling default: 21,600 seconds;
- authentication: none;
- recurring API cost: EUR 0;
- license: ODbL 1.0.

The profile selects provider group orders 1 through 4 and validates exactly 12
fixtures and four disjoint participants in each. Every ordered participant
pair must occur once. Additional provider groups are ignored before
normalization; a missing selected group, cross-group participant, duplicate
pairing, wrong scope, or incomplete 48-fixture set fails closed.

The 16 exact provider names were reviewed independently against UEFA. Their
numeric provider IDs are deliberately not copied into the public repository:
the first successful private import learns and persists each ID through the
source-mapping repository. Later ID/name conflicts fail before canonical
writes.

## Configuration

```env
OPENLIGADB_ENABLED=true
SOURCE_JOBS_JSON=[{"job_key":"openligadb-uefa-nations-league","source_key":"openligadb","sport_key":"football","competition_key":"uefa_nations_league","season_key":"2026_27","role":"authoritative","interval_seconds":21600}]
```

The DFB-Pokal and 2. Bundesliga jobs may be enabled in the same JSON array.
They share one bounded provider client but retain separate profiles, adapters,
services, orchestrators, runtime locks, scheduler state, import runs, and
canonical scopes. Exactly one enabled authoritative writer remains permitted
for each competition and season.

## Persistence and lifecycle

The canonical competition format is `hybrid_tournament`. Selected groups
normalize to `group-a-1` through `group-a-4` within the
`league_a_group_phase` stage.

Every runtime observation is `partial`, `complete=false`, `filtered=true`, and
`removal_eligible=false`. Allowed import decisions are `CREATE`, `UPDATE`, and
`SKIP`. Empty, malformed, incomplete, stale, wrong-scope, network-failed, or
identity-conflicting responses preserve last-known-good state.

Source metadata and Outlook event bodies retain exactly:

`Fixture data provided by OpenLigaDB (ODbL 1.0): https://www.openligadb.de/`

Logo/icon URLs and raw provider responses are neither fetched separately nor
persisted. Live fixture inventories, SQLite databases, exports, provider
payloads, and restricted verification documents must remain outside the public
repository, CI artifacts, container images, and releases.

## Verification

Normal CI is credential-free and network-free. Synthetic 48-fixture tests
cover the four complete double-round-robin groups without embedding live
provider IDs or fixture inventories. SQLite-to-mocked-Graph integration proves
first import, unchanged-cycle idempotency, one-fixture rescheduling, restart,
provider outage and recovery, Outlook attribution, and non-destructive missing
fixture behavior.

Before release inclusion, isolated staging must repeat the live qualification
and prove the same lifecycle behavior using only staging database, Outlook
calendar, configuration, and logs. Production promotion remains manual and is
out of scope for #170.
