# Phase 7 Source and Authority Matrix

## Status and release boundary

This matrix records the final source decision for Phase 7 master issue #178,
the NFL source qualification in #179, and the accepted isolated-staging gate
in #190. Qualification was reviewed on 2026-08-30 and the combined nine-
authority candidate passed isolated staging on 2026-08-31. GitHub pre-release
publication remains a separate gate in #198.

The intended `v0.7.0-beta.1` boundary is the NFL 2026 regular season only:

- 32 teams;
- 272 games;
- weeks 1–18;
- nflverse game identities;
- Eastern kickoff normalization to UTC; and
- permanent non-destructive operation under the initial authority contract.

Preseason and postseason are excluded. Results, standings, statistics,
betting, rosters, injuries, stadium metadata, weather, and media are excluded.

## Decision

| Competition | Season and scope | Outcome | Selected candidate | Authority assignment | Operating boundary |
| --- | --- | --- | --- | --- | --- |
| NFL | 2026 regular season | Qualified, implemented, and accepted in isolated staging | nflverse automated `schedules/games.csv` release | Sole authoritative writer when explicitly enabled | Exactly 272 games, 32 teams, weeks 1–18; `partial`, `complete=false`, and removal disabled |

## Candidate comparison

| Candidate | Cost | Technical fit | Rights and operations | Decision |
| --- | ---: | --- | --- | --- |
| nflverse `schedules` release | EUR 0 | Current 272-game scope, stable-looking game IDs, CSV, documented Eastern times, five-minute source updates | Automated GitHub release under CC BY 4.0; underlying NFL rights caveat requires private-use and no-dataset-publication boundary | Selected for bounded implementation |
| NFL.com schedule pages | EUR 0 | Official format and schedule verification | No approved public fixture API or scraping permission | Manual verification only |
| ESPN schedule endpoints | EUR 0 | Broad technical fields and identifiers | Undocumented automated endpoint and no reviewed redistribution contract | Rejected as authority |
| Commercial sports APIs | Recurring cost | Potentially broad schedule and lifecycle support | Subscription, plan, retention, and redistribution review required | Rejected by current zero-cost policy |
| Operator-assisted manifest #168 | EUR 0 | Safe reviewed fallback | Source-specific rights review and manual approval required | Fallback only; never automatic failover |

## Qualification observations

Two observations on 2026-08-30 returned the same selected structure and
fixture-ID fingerprint:

- 272 regular-season rows and unique game IDs;
- 32 unique teams;
- weeks 1–18;
- zero missing dates or kickoff times;
- no 2026 postseason rows; and
- fixture-ID SHA-256
  `dfad7658d8ec34c973f522d3b175492f6bb6def2e7a114db7b8c12a2292d7d05`.

The raw dataset and fixture inventory are not repository artifacts.

## Authority conditions

1. Exactly one NFL 2026 regular-season writer may be enabled.
2. Every accepted observation contains exactly 272 unique games, 32 admitted
   teams, and weeks 1–18.
3. `game_id` is primary identity; secondary identifiers are diagnostics only.
4. Identity-set, week, or participant changes fail closed for operator review.
5. `gametime` is interpreted only in `America/New_York` as documented by
   nflverse, then converted to UTC.
6. Flex-schedule updates change the existing event and never create a new one.
7. Omission never creates cancellation or deletion evidence.
8. Raw source rows, fixture inventories, logos, databases, and Outlook exports
   remain outside GitHub and release artifacts.
9. Outlook events display nflverse and CC BY 4.0 attribution plus a flex-
   scheduling notice.
10. A licence, source-availability, provenance, or attribution change disables
    further collection pending review while preserving last-known-good state.

## Implemented and staged outcome

Phase 7 implements the standard-library CSV transport, strict structural
adapter, 32-team catalog and source mappings, provider-neutral source job,
SQLite import, scheduler runtime, Outlook attribution, flex-scheduling notice,
and deterministic three-hour NFL event fallback. Association-football events
retain the generic two-hour fallback.

The isolated candidate accepted exactly 272 active NFL fixtures, 32
participant mappings, 272 source fixture mappings, 272 synchronized calendar
mappings, and weeks 1–18 under stage `regular-season`. The complete candidate
contained nine authorities, 2,088 active events and synchronized calendar
mappings, and zero pending mapping revisions. Unchanged provider and calendar
runs were write-free. Restart, controlled failure/recovery, and isolated
backup/restore gates passed without publishing fixture rows or private
deployment identifiers.

The remaining gate is the reviewed `v0.7.0-beta.1` release workflow in #197
and #198. Publication does not promote production.

## References

- [NFL source qualification](nfl-source-qualification.md)
- [ADR 0013](adr/0013-select-nflverse-for-nfl-regular-season.md)
- [Public repository data safety](public-repository-data-safety.md)
- [Provider integration contract](provider-integration-contract.md)
- [Phase 7 isolated staging validation](phase-7-staging-validation.md)
- [v0.7.0-beta.1 release checklist](v0.7.0-beta.1-release-checklist.md)
