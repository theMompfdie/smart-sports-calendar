# Provider-Neutral Source Orchestration

## Scope

Issue #74 introduces the provider-neutral authority and scheduling boundary for
`v0.4.5-beta.1`. Issue #76 uses this boundary for the implemented
football-data.org Premier League transport and canonical import. Phase 5 issue
 #114 extends the same boundary with a strict Bundesliga profile and
competition-scoped runtime dispatch. Issue #119 adds the isolated OpenLigaDB
DFB-Pokal writer with an invariant permanent-partial observation scope. Issue
 #132 reuses that provider boundary for an independent removal-disabled 2.
Bundesliga job. Issue #135 adds the qualified EFL Championship regular-season
stage without admitting the separate play-off stage. Phase 6 issue #170 adds a
third OpenLigaDB profile for only the UEFA Nations League A 2026/27 group
phase.

## Source jobs

`SOURCE_JOBS_JSON` is a JSON array. Each item contains:

- `job_key`: stable, unique operational identity;
- `source_key`: registered adapter identity;
- `sport_key`, `competition_key`, and `season_key`: canonical scope;
- `role`: `authoritative`, `bootstrap`, `verification`, or `disabled`;
- `interval_seconds`: independent positive scheduler interval.

Example for the existing API-Football adapter:

```json
[
  {
    "job_key": "api-football-premier-league",
    "source_key": "api_football",
    "sport_key": "football",
    "competition_key": "premier_league",
    "season_key": "2026_27",
    "role": "authoritative",
    "interval_seconds": 3600
  }
]
```

Keep the environment-variable form on one line. `football_data` supports the
authoritative `football/premier_league/2026_27` and
`football/bundesliga/2026_27` complete-season profiles plus the bounded
`football/championship/2026_27` `REGULAR_SEASON` complete-stage profile; it
must be paired with
`FOOTBALL_DATA_ENABLED=true`. Each profile has a separate job key and interval.
`openligadb` supports the authoritative `football/dfb_pokal/2026_27`,
`football/second_bundesliga/2026_27`, bounded
`football/uefa_nations_league/2026_27`, and bounded
`football/uefa_champions_league/2026_27` scopes and must be paired with
`OPENLIGADB_ENABLED=true`. It requires no credential. Each competition uses a
separate job key, runtime lock, import run, and failure boundary while sharing
the bounded public provider client.

## Validation

Startup fails before scheduling when:

- JSON is malformed or contains unknown or missing fields;
- job keys are duplicated;
- a source has multiple active jobs for one scope;
- an active scope has zero or multiple authoritative writers;
- an adapter is missing or does not support the configured role;
- an API-Football job and `API_FOOTBALL_ENABLED` disagree;
- canonical sport, competition, or season keys cannot be resolved.

Disabled jobs do not require an installed adapter. When their source catalog
row already exists they are persisted as inactive; otherwise they remain
configuration-only until the adapter registers the source. This permits a
future source to be documented without making it executable.

## Roles and write safety

- `authoritative` may write canonical fields. It contributes absence/removal
  evidence only when the individual observation declares a validated supported
  complete lifecycle scope.
- `bootstrap` may seed explicit mappings only through a runner designed for
  that role.
- `verification` may compare or report but cannot write canonical fields,
  cancel events, or contribute removal evidence.
- `disabled` is never scheduled and is persisted as inactive once its source
  catalog entry exists.

Adapters declare the roles they support when registered. The existing
API-Football runtime is a canonical writer and therefore accepts only
`authoritative`; configuring it as bootstrap or verification fails closed.
There is no automatic failover or field aggregation.

## Scheduling and reporting

Each active job has independent due time and interval state. A failure is
logged with its safe `job_key`, then the scheduler continues with other due
jobs. Provider-specific bounded retry and quota logic remains inside the
adapter boundary.

Multiple `football_data` competition jobs share one client instance. Its
minimum request interval and retry policy therefore enforce one provider-wide
quota budget instead of independent per-competition budgets. Each job still
has its own runtime lock, sync-run metadata, and failure boundary.

The Championship match request is stage-filtered and accepts only the exact
qualified 552-item response or documented `500 + 52` offset pagination. Each
returned fixture is independently checked as `REGULAR_SEASON`; play-offs,
partial pages, offset drift, duplicates, and mixed stages fail before canonical
writes or removal evidence.

OpenLigaDB jobs share one bounded client but have independent runtime locks and
retry/run-reporting boundaries. The DFB-Pokal, initial 2. Bundesliga, and UEFA
Nations League A group-phase runtimes declare `partial`, `complete=false`, and
`removal_eligible=false`. The Nations League observation is also `filtered`
because only provider groups 1 through 4 are admitted. Missing or excluded
records can therefore never advance cancellation or deletion evidence.

Outlook calendar synchronization is a separate scheduled job controlled by
`HEARTBEAT_INTERVAL`. Source jobs are registered first so the initial import
precedes the first calendar batch. Provider callbacks do not invoke Graph;
therefore a backlog larger than `SYNCHRONIZATION_BATCH_LIMIT` continues across
calendar heartbeats without consuming provider quota, and a failed provider
job does not prevent later synchronization of already committed canonical
events. Outlook-visible canonical changes increment a persisted event revision.
Mappings whose recorded revision is behind are selected before the ordinary
oldest-synchronized rotation, so increasing the batch limit is not required to
make a late-position fixture update promptly visible.

Provider import run metadata records the safe job key, source key, role,
competition key, season key, canonical IDs, authoritative flag, competition
format, lifecycle scope kind, optional stage/round, completeness, removal
eligibility, observation ID, UTC window, attempts, and sanitized quota
aggregates. A failed or overlapping import makes no canonical changes.

Source role and observation completeness are intentionally separate. An
authoritative job may produce a partial observation that safely creates or
updates fixtures without creating removal evidence. Removal reconciliation is
supported for an unfiltered complete-season league scope, a qualified non-empty
and exact complete-stage scope, and a non-empty exact complete-round
knockout/cup or hybrid-tournament scope. Candidate selection is bounded by
source, competition, season, and the declared stage/round identifiers. This
generic capability does not make a concrete stage or round complete or
authoritative; that claim remains adapter- and competition-qualified.

Public attribution is owned by the selected source catalog entry. The
synchronization query resolves the optional attribution only from the enabled
authoritative assignment for the event competition and season. The Outlook
presentation layer renders that reviewed text without knowing provider keys or
competition-specific rules.

## Persistence and migration

Migration `007_create_source_assignments` adds a source-assignment table and a
partial unique index that prevents two enabled authoritative rows for the same
canonical competition and season. Startup synchronizes configured jobs
transactionally: removed jobs are disabled rather than deleted, and existing
data sources, source mappings, canonical events, and Outlook mappings are not
rewritten.

Migration `008_add_calendar_sync_revisions` adds monotonic event revisions and
the last successfully processed revision to Outlook mappings. SQLite triggers
cover the event fields and related aggregates used by the Outlook payload.
Existing events start at revision `1` while existing mappings start at `0`,
which intentionally schedules one non-destructive reconciliation sweep after
upgrade. A concurrent canonical change cannot be lost: completion records the
revision loaded for that Graph operation and leaves the mapping pending when a
newer revision already exists.

Phase 5.1 adds no schema migration. The existing
`competitions.competition_type` column is the canonical typed competition
format, while observation lifecycle scope is persisted in existing provider
import-run metadata. Unknown persisted formats fail closed at repository
mapping boundaries.

## Phase 6 hybrid tournament contract

Phase 6.1 adds `hybrid_tournament` for competitions that combine qualifying,
league-phase, and knockout lifecycle segments. It does not register or enable a
UEFA authority.

Phase 6.2 initially evaluated football-data.org for the UEFA Champions League
but did not retain it as the released authority. The final
`v0.6.0-beta.1` boundary assigns OpenLigaDB `ucl` / 4946 only to the 2026/27
league phase. Qualifying, play-offs, knockout rounds, and every provider group
outside the eight accepted matchdays remain excluded. API-Football,
Sportmonks, and football-data.org are not concurrent writers for this scope.

Hybrid observations use the same source-job, import, repository,
reconciliation, and synchronization path as released competitions. A typed
stage kind accompanies exact normalized stage and round identifiers. Partial
or incrementally published observations remain non-removal-capable. Complete
hybrid stage/round claims require competition-specific qualification and retain
the existing non-empty, exact-boundary, authority, replay, and two-observation
safeguards.

Draw-dependent fixtures use explicit resolved/unresolved participant slots.

Issue #170 applies this contract to `uefa_nations_league/2026_27` without
expanding it. OpenLigaDB `nla` / 5978 is accepted only for the 48-fixture,
16-participant League A group phase. The profile validates four disjoint groups
of four teams and a complete directed double round robin within each group.
Provider groups outside 1 through 4 are ignored before normalization. Leagues
B, C, and D plus every later stage remain unassigned and cannot contribute
canonical or removal evidence.
Issue #155 applies the same permanent-partial contract to the Champions League
league phase. OpenLigaDB `ucl` / 4946 admits only groups 1 through 8, exactly
144 fixtures, and 36 reviewed clubs. Groups 9 through 16 plus qualification
are filtered and cannot contribute canonical or removal evidence.
Any unresolved slot produces `DEFER`, creates no placeholder participant or
calendar event, and cannot replace the last known good participants of an
already mapped event. First/second-leg metadata is diagnostic; stable source
fixture ID remains the correlation identity. See
[`adr/0011-model-hybrid-uefa-lifecycle.md`](adr/0011-model-hybrid-uefa-lifecycle.md).

## Phase 7 NFL regular-season contract

Phase 7 adds `american_football/nfl/2026` through the same provider-neutral
source assignment, import, persistence, scheduling, and Outlook synchronization
path. nflverse `schedules/games.csv` is the sole approved authority for exactly
272 `REG` games, 32 teams, and weeks 1–18. Its fixed asset requires no
credential and is polled no more frequently than every six hours.

Every accepted observation remains `partial`, `complete=false`, and
`removal_eligible=false`. Stable nflverse `game_id` values correlate flexed
kickoffs to existing events. A missing row, transport failure, schema change,
identity-set change, mixed season, invalid Eastern time, or participant mapping
failure rejects the observation and preserves last-known-good SQLite and
Outlook state.

Outlook events render nflverse CC BY 4.0 attribution and an NFL
flex-scheduling notice. When no provider end time exists, NFL events reserve
three hours; association football and other generic events retain the two-hour
fallback. Preseason, postseason, results, scores, standings, statistics,
rosters, venues, media, and logos are outside the contract.

## Effective retirement of completed scopes (unreleased Version 1.0)

The [retirement cookbook](season-retirement-cookbook.md) documents the explicit
preview/deactivate/reactivate maintenance CLI. The decision file configures the
completion evidence and `grace_days`; no new environment variable is required.
Migration 015 stores an effective inactive gate independently of configured
source roles. Retain the exact source job/profile and authority boundary on
restart. The gate skips routine polling/import and historical fixture sync,
while preserving source attribution and one authoritative writer per boundary.
Changing or removing a retired grant fails closed until explicit reactivation.
Future seasons need separate qualified catalogue/configuration entries and job
keys or manual namespaces. Broad grants are never narrowed implicitly.
