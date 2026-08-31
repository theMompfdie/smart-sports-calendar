# Phase 7 NFL Isolated Staging Validation

## Purpose and release boundary

This record closes the live qualification gate in issue #190 for the Phase 7
`v0.7.0-beta.1` release candidate. It documents only sanitized aggregate
outcomes from the dedicated staging stack. Raw nflverse rows, fixture lists,
participant schedules, SQLite databases, Outlook exports, calendar IDs,
credentials, private paths, and deployment-specific identifiers remain outside
the repository and GitHub.

The accepted NFL authority is exactly:

- source job `nflverse-nfl-2026`;
- canonical scope `american_football/nfl/2026`;
- 272 active 2026 regular-season fixtures;
- 32 participant mappings;
- weeks 1–18 under stage `regular-season`;
- 272 source fixture mappings and 272 synchronized calendar mappings;
- `authoritative=true`, `complete=false`, `scope_kind=partial`, and
  `removal_eligible=false`; and
- one dedicated staging Outlook calendar target.

Preseason, postseason, results, scores, standings, statistics, rosters,
injuries, venues, weather, media, logos, and automatic provider failover are
not part of this evidence or release.

## Candidate and isolation

Final qualification used the reconciled `develop-525eb0b8` candidate, which
contains the published Phase 6 baseline and the Phase 7 NFL integration.
Staging used its own Compose project, writable volume, SQLite database,
credentials, Outlook calendar, configuration, and log stream. Production was
not modified.

The exact candidate contained these nine authoritative jobs:

| Job | Accepted scope |
| --- | --- |
| `football-data-premier-league` | Premier League 2026/27 |
| `football-data-bundesliga` | Bundesliga 2026/27 |
| `football-data-championship` | Championship 2026/27 regular season |
| `openligadb-dfb-pokal` | DFB-Pokal 2026/27 partial scope |
| `openligadb-second-bundesliga` | 2. Bundesliga 2026/27 partial scope |
| `oefb-ical-oefb-cup` | ÖFB-Cup 2026/27 permanent-partial scope |
| `openligadb-uefa-nations-league` | Nations League A 2026/27 group phase |
| `openligadb-uefa-champions-league` | Champions League 2026/27 league phase |
| `nflverse-nfl-2026` | NFL 2026 regular season |

The NFL source job uses the fixed public asset and needs no credential:

```json
{"job_key":"nflverse-nfl-2026","source_key":"nflverse","sport_key":"american_football","competition_key":"nfl","season_key":"2026","role":"authoritative","interval_seconds":21600}
```

`NFLVERSE_ENABLED=true` and the job must be configured together. The interval
must not be shorter than `NFLVERSE_MINIMUM_POLL_INTERVAL_SECONDS`, whose
minimum accepted value is 21,600 seconds.

## Accepted aggregate evidence

The strict read-only baseline completed with exit code `0` and reported:

- `database_quick_check=ok`;
- schema `008_add_calendar_sync_revisions`;
- 2,088 active sports events across exactly nine authorities;
- 2,088 calendar mappings in status `synced`;
- zero globally pending mapping revisions;
- 272 active NFL fixtures, 32 participant mappings, and 272 fixture source
  mappings;
- exactly 272 NFL calendar mappings in status `synced` and zero pending NFL
  revisions;
- stage `regular-season=272` and complete week coverage from 1 through 18;
- a completed nflverse run with 272 processed, 272 unchanged, and zero creates,
  updates, cancellations, deletions, deferrals, or failures; and
- a completed write-free calendar synchronization run.

Private Outlook inspection confirmed representative NFL events had the correct
participants, Europe/Vienna presentation time, NFL category, regular-season
and week metadata, nflverse CC BY 4.0 attribution, flex-scheduling notice, and
the three-hour fallback duration. Association-football events retained the
generic two-hour fallback.

## Restart and unchanged-cycle behavior

After application restart, the candidate retained all 2,088 events and
synchronized mappings with zero pending revisions. The next complete nflverse
run processed 272 unchanged fixtures without canonical writes. Repeated
calendar batches processed unchanged mappings without Graph creates, updates,
cancellations, deletions, deferrals, or failures. No duplicate or lost mapping
was observed.

The release gate is reproducible with the read-only command:

```bash
docker compose exec -T calendar-sync \
  python -m app.operations.staging_evidence \
  --database /data/sports.db \
  --limit 120 \
  --validate-phase-7-nfl-candidate
```

The strict validator requires the exact nine-authority candidate, every scope
and mapping invariant, the latest valid unchanged provider run for each
authority, zero pending revisions, and a latest write-free calendar run. It
prints no JSON when validation fails; the failure is written to standard error.

## Controlled failure and recovery

The operator completed a controlled nflverse failure and recovery exercise
against isolated staging. The failure preserved last-known-good SQLite and
Outlook state and did not authorize destructive reconciliation. Normal source
configuration was restored and the provider returned to a successful unchanged
272-fixture run.

The test database was restored afterward, so the transient failed-run record
was intentionally replaced. The public record therefore retains the operator
confirmation and the independent successful recovery/restart evidence instead
of reconstructing run metadata that no longer exists.

Deterministic offline tests remain the reproducible proof for transport retry,
fail-closed parsing, stable identity, omission handling, scheduler isolation,
restart, recovery, flex changes, and duplicate prevention.

## Backup and isolated restore

A stopped-container SQLite backup was stored outside the staging volume and
verified privately. A later restore copied that backup into a newly created,
isolated Docker volume without overwriting staging. The restored file matched
the backup byte-for-byte, returned `PRAGMA quick_check: ok`, and contained
2,088 sports events.

The restored historical snapshot retained a provider run that had been active
when the source container was stopped and a preceding calendar run with one
write. The strict candidate validator correctly rejected those latest-run
conditions. That rejection is not a restore-integrity failure: byte identity,
SQLite integrity, and readability prove restoration, while the separate strict
baseline and restart evidence prove candidate convergence.

Never start a restored private database against Graph merely to manufacture a
new convergence record. Validate restored state read-only and use a fresh
isolated candidate for live synchronization gates.

## Acceptance

Issue #190 is complete. The accepted evidence covers isolation, exact NFL
scope, source and calendar mappings, Outlook presentation, attribution,
idempotency, controlled failure/recovery, restart convergence, and readable
isolated backup restoration. It authorizes Phase 7 release preparation only;
it does not promote or modify production.
