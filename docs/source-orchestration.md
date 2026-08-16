# Provider-Neutral Source Orchestration

## Scope

Issue #74 introduces the provider-neutral authority and scheduling boundary for
`v0.4.5-beta.1`. Issue #76 uses this boundary for the implemented
football-data.org Premier League transport and canonical import.

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

Keep the environment-variable form on one line. `football_data` is the only
released authoritative adapter for `football/premier_league/2026_27`; it must
be paired with `FOOTBALL_DATA_ENABLED=true`.

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

Outlook calendar synchronization is a separate scheduled job controlled by
`HEARTBEAT_INTERVAL`. Source jobs are registered first so the initial import
precedes the first calendar batch. Provider callbacks do not invoke Graph;
therefore a backlog larger than `SYNCHRONIZATION_BATCH_LIMIT` continues across
calendar heartbeats without consuming provider quota, and a failed provider
job does not prevent later synchronization of already committed canonical
events.

Provider import run metadata records the safe job key, source key, role,
competition key, season key, canonical IDs, authoritative flag, competition
format, lifecycle scope kind, optional stage/round, completeness, removal
eligibility, observation ID, UTC window, attempts, and sanitized quota
aggregates. A failed or overlapping import makes no canonical changes.

Source role and observation completeness are intentionally separate. An
authoritative job may produce a partial observation that safely creates or
updates fixtures without creating removal evidence. Phase 5.1 supports removal
reconciliation only for an unfiltered complete-season league scope. Complete
stage and round scopes are typed and validated but remain non-destructive until
the dedicated knockout/cup lifecycle slice.

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

Phase 5.1 adds no schema migration. The existing
`competitions.competition_type` column is the canonical typed competition
format, while observation lifecycle scope is persisted in existing provider
import-run metadata. Unknown persisted formats fail closed at repository
mapping boundaries.
