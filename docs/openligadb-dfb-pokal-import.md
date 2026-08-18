# OpenLigaDB DFB-Pokal Import

## Scope

Issue #119 implements the qualified 2026/27 DFB-Pokal OpenLigaDB authority.
The fixed provider identity is league `4945`, shortcut `dfb`, season `2026`.
The canonical identity is `football/dfb_pokal/2026_27`.

The adapter makes three public, unauthenticated HTTPS requests per observation:

- `/getavailableleagues/2026`;
- `/getavailablegroups/dfb/2026`; and
- `/getmatchdata/dfb/2026`.

Responses are bounded before JSON parsing. Timeouts, request spacing, retry
count, exponential backoff, and `Retry-After` handling are explicit. Linked
team icons and logos are never requested or persisted.

## Identity and validation

- `matchID` is the stable fixture source identity.
- `teamId` plus the reviewed provider name resolves one of 64 canonical teams.
- `leagueId` plus `leagueSeason` binds the competition season.
- `groupID` is retained as provider round identity.
- `groupOrderID` maps deterministically to `round-{n}`.
- `matchDateTimeUTC` is the kickoff authority.
- naive `lastUpdateDateTime` values are interpreted in `Europe/Berlin`, as
  qualified with provider `timeZoneID` `W. Europe Standard Time`.

Empty, malformed, wrong-scope, duplicate, future-updated, unknown-team, and
inconsistent-round observations fail before canonical fixture persistence.

## Permanent partial boundary

Every observation is authoritative for fields it contains but permanently has
scope `partial`. The runtime always persists:

```text
authoritative_scope=partial
scope_kind=partial
complete=false
removal_eligible=false
```

Known fixtures may be created or updated. Missing provider records never
cancel, delete, or contribute absence evidence. Promoting this provider to a
complete round or stage requires a new provider contract and ADR.

## Attribution

The active source assignment supplies the following text to every generated
Outlook event:

```text
Fixture data provided by OpenLigaDB (ODbL 1.0): https://www.openligadb.de/
```

The code does not persist raw provider payloads. Before distributing a
calendar, database, feed, or other substantial extract publicly, repeat the
ODbL distribution review recorded in ADR 0007.

## Configuration

OpenLigaDB requires no account, token, or secret. Configure the isolated
staging stack with one matching source job:

```env
OPENLIGADB_ENABLED=true
OPENLIGADB_BASE_URL=https://api.openligadb.de
OPENLIGADB_CONNECT_TIMEOUT_SECONDS=5
OPENLIGADB_READ_TIMEOUT_SECONDS=30
OPENLIGADB_MAX_ATTEMPTS=3
OPENLIGADB_RETRY_BASE_DELAY_SECONDS=1
OPENLIGADB_RETRY_MAX_DELAY_SECONDS=30
OPENLIGADB_MINIMUM_REQUEST_INTERVAL_SECONDS=1
SOURCE_JOBS_JSON=[{"job_key":"openligadb-dfb-pokal","source_key":"openligadb","sport_key":"football","competition_key":"dfb_pokal","season_key":"2026_27","role":"authoritative","interval_seconds":21600}]
```

When the staging stack also runs Premier League or Bundesliga, add their
independent jobs to the same one-line JSON array. Never configure a second
active authority for `dfb_pokal/2026_27`.

## Verification

Offline coverage proves provider parsing, reviewed participant resolution,
source mapping, permanent-partial preservation, idempotent SQLite import,
Outlook create/update behavior, and visible attribution without live network
or Graph credentials.

Before approving staging:

1. deploy only to the isolated staging database and Outlook calendar;
2. confirm one enabled `openligadb-dfb-pokal` source assignment;
3. compare the observed identity/count fingerprint with issue #118 evidence;
4. confirm created Outlook events contain the exact attribution;
5. run a second unchanged cycle and confirm no Graph writes;
6. confirm sync-run metadata remains `partial` and removal-disabled; and
7. record sanitized evidence in issue #119 without event details or calendar
   identifiers.

Live staging is not complete merely because the offline suite passes. The
operator must execute and review this checklist against the dedicated staging
deployment before #119 can close.
