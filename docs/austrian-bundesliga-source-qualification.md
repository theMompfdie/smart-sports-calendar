# Austrian Bundesliga Source Qualification

## Status

**Deferred for `v0.5.0-beta.1`: no reviewed no-cost candidate can provide a
permitted, complete, machine-readable 2026/27 authority.**

Issue #125 evaluates the Austrian Bundesliga before any provider adapter,
catalog, mapping, source job, SQLite import, Microsoft Graph synchronization,
or release claim is approved. SMART Sports Calendar is a hobby project, so a
permitted and technically trustworthy no-cost source is preferred even when it
requires another bounded adapter. No paid plan was approved for this review.

Deferral is fail-closed. The competition remains visible in the backlog, but no
candidate may write canonical fixtures or supply removal evidence.

## Competition lifecycle boundary

The official 2026/27 schedule has 12 clubs and a 22-round ground phase. After
round 22, the field splits into championship and qualification groups for
rounds 23 through 32. Three European play-off matches follow. The later group
participants and fixtures cannot be treated as a complete-season snapshot
before the split is known.

Any future authority must expose stable competition, season, participant,
fixture, stage, and round identities across that transition. The maximum safe
initial observation is `partial`. A later `complete_stage` decision requires a
new qualification proving the exact stage boundary and provider behavior; no
2026/27 Austrian Bundesliga observation is removal-eligible under this record.

## Candidate review

### Official Austrian Bundesliga sources

The competition publishes official fixture pages, a ground-phase announcement,
downloadable schedule documents, and a calendar page. No documented public API
or automatically updated iCalendar feed was found. The calendar page links to
human-facing schedules rather than a machine-readable subscription.

Those official sources remain suitable for manual verification only. HTML
scraping and undocumented website endpoints are excluded by project policy and
were not inspected or used.

### OpenLigaDB

The public 2026 directory identifies `Admiral Bundesliga` as league `5990` with
shortcut `BLÖ`, but reports quality index `0`. A secret-free read-only API
observation on 2026-08-28 returned 36 generic matchday groups and zero
fixtures.

This conflicts with the official 22-round ground phase followed by ten split
rounds and separate European play-offs. The empty response cannot demonstrate
participants, stable fixture identities, lifecycle states, timestamps, or any
complete scope. OpenLigaDB is rejected for the current season unless its data
later becomes non-empty, structurally correct, and stable across two reviewed
observations.

### football-data.org

The public catalog identifies Austrian Bundesliga competition `ABL` / `2012`,
but access requires the paid Advanced tier. Public season information exposes
ground-round dates and does not establish the complete split and play-off
lifecycle required for a safe authority.

The candidate is rejected for this decision because it is both paid and
insufficiently proven for the full competition lifecycle. No credentialed
observation or subscription was approved.

### API-Football

API-Football has technically broad coverage, but the reviewed API-Sports terms
do not grant the data-use and publication rights required for a new Phase 5
authority. The customer must obtain permission from the competent rights
holder, and no competition-specific written clearance is recorded.

Free-plan availability therefore does not make this candidate eligible.
Existing legacy mappings do not authorize a new Austrian Bundesliga writer.

### Sportmonks

Sportmonks publishes Austrian Bundesliga coverage as league `181` and provides
the stage, round, fixture, participant, state, pagination, and quota concepts
needed for a future technical qualification. Its permanent free football plan
does not include the Austrian Bundesliga. The Starter plan begins at EUR 29
per month and the time-limited trial requires a payment method and converts to
a paid plan unless cancelled.

Sportmonks remains the strongest reviewed paid candidate, but it is not
selected. The operator did not approve recurring cost, a trial, credentials,
or two credentialed live observations.

### TheSportsDB

TheSportsDB documents a public V1 development key and a 30-request-per-minute
free limit. Its community database identifies the Austrian Bundesliga as
league `4621`. A secret-free read-only observation on 2026-08-28 resolved the
2026/27 season and returned 15 unique events with stable-looking positive IDs,
covering only rounds 1 through 3 and dates from 2026-07-31 through 2026-08-15.

That result exactly reaches the documented free `eventsseason` limit of 15;
the same documentation allows up to 3,000 season events only for premium
access. Free season history is also limited to five records. There is no
documented pagination mechanism for retrieving the omitted fixtures.

The free endpoint therefore cannot prove a complete ground phase or season,
detect omissions safely, or support deterministic reconciliation. The terms
also leave third-party competition-data rights with the user. TheSportsDB is
rejected as a free authoritative source for this scope.

## Deferred operating decision

- No authoritative writer is assigned for `austrian_bundesliga` / `2026_27`.
- No provider credential, subscription, trial, adapter, mapping, or source job
  is approved.
- All observed candidates remain outside canonical persistence and Outlook.
- No empty, partial, stale, malformed, ambiguous, throttled, or failed response
  may change last-known-good state or contribute destructive evidence.
- No separate implementation issue should be created from this decision.

## Exact re-evaluation triggers

Reopen qualification only when at least one of these conditions is true:

1. the Austrian Bundesliga publishes or explicitly permits a documented,
   automatically updated API or calendar feed with stable fixture identities;
2. OpenLigaDB exposes the official 2026/27 stage structure and a non-empty,
   complete intended scope that remains stable across two observations;
3. another documented no-cost provider offers complete season/stage retrieval,
   usable data rights, stable identities, lifecycle states, and safe quotas; or
4. the operator explicitly approves a paid Sportmonks plan and its current
   price, domain, quota, terms, attribution, retention, cancellation, and exit
   obligations before credentialed qualification begins.

Any re-evaluation must perform two secret-safe read-only observations separated
by a meaningful interval. It must fail closed on pagination gaps, duplicates,
unknown participants, unsupported placeholders or states, timezone ambiguity,
and structural mismatch across the league split.

## Sources

- [Official 2026/27 ground-phase schedule](https://www.bundesliga.at/de/news/artikel/admiral-bundesliga-spielplan-fuer-den-grunddurchgang-2026-27)
- [Official Austrian Bundesliga schedule](https://www.bundesliga.at/de/spielplan)
- [Official Austrian Bundesliga calendar page](https://www.oefbl.at/de/oefbl/kalender)
- [Official 2026/27 framework calendar](https://www.bundesliga.at/de/news/artikel/rahmenterminplan-fuer-die-saison-2026-27)
- [OpenLigaDB 2026 league directory](https://www.openligadb.de/Leagues?season=2026)
- [OpenLigaDB API](https://api.openligadb.de/)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [API-Sports terms](https://api-sports.io/terms)
- [Sportmonks Austrian Bundesliga coverage](https://www.sportmonks.com/football-api/admiral-bundesliga-api/)
- [Sportmonks free plan](https://www.sportmonks.com/football-api/free-plan/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [TheSportsDB API guide](https://www.thesportsdb.com/docs_api_guide)
- [TheSportsDB terms](https://www.thesportsdb.com/docs_terms_of_use.php)
- [TheSportsDB pricing](https://www.thesportsdb.com/docs_pricing.php?billing=annual)
