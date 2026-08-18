# OpenLigaDB DFB-Pokal Source Qualification

## Status

**Qualified by ADR 0007 for non-destructive `partial` observations only.**

Issue #118 evaluates the public OpenLigaDB API as the no-cost automated source
candidate for the 2026/27 DFB-Pokal. The identified competition is league
`4945`, shortcut `dfb`, season `2026`. The official DFB schedule is the manual
verification reference and is not scraped or used as an automated writer.

The maximum accepted scope remains `partial`. A successful command does not
prove a complete round, authorize removals, implement a provider adapter, or
enable a source job.

## Public evidence reviewed on 2026-08-18

OpenLigaDB describes itself as a free community project intended for automated
use in applications and websites. Read access to its JSON API requires no
account or token. API data is published under ODbL 1.0. A public use of a
produced work therefore needs OpenLigaDB attribution; a publicly used adapted
database can additionally trigger share-alike and machine-readable-access
obligations. Linked club logos and icons have separate rights and are excluded.

The source is community maintained, not an official DFB publication. Users can
edit results, and OpenLigaDB's own API documentation warns that DFB-Pokal
shortcuts have historically not been as consistent as the Bundesliga
shortcuts. Provider IDs and data must therefore be qualified season by season.

The 2026/27 league directory currently reports:

- league ID `4945`;
- shortcut `dfb`;
- season `2026`;
- sport ID `1` (`Fußball`);
- six groups with stable group IDs and orders from first round through final;
- 32 currently published first-round fixtures; and
- a displayed quality index of 100.

The quality index and a full list of currently known fixtures are not a
completeness contract. The API has no documented pagination, quota header,
rate-limit contract, cancellation state, placeholder flag, or immutable
snapshot marker. Those limitations keep the source `partial` and
removal-disabled.

The first live observation on 2026-08-18 was manually compared with the
official DFB first-round schedule published on 2026-06-24. All 32 pairings and
kickoff times matched after accounting for harmless club-name variants. The
DFB boundary of 30 fixtures from 21–24 August plus the Dortmund and Bayern
fixtures on 1–2 September also matched. This comparison validates the current
observation only; it is not provider-side completeness evidence.

A second complete observation at 18:46:46 UTC reproduced the first
observation's fixture and participant fingerprints, counts, group identities,
kickoff boundaries, update boundary, and status counts. ADR 0007 therefore
approves the source for a later non-destructive implementation while retaining
the permanent `partial` boundary.

## Read-only qualification command

The command makes three bounded, unauthenticated HTTPS GET requests. It does
not open SQLite, call Microsoft Graph, persist raw payloads, retrieve logos, or
write calendar events.

```powershell
python -m app.operations.openligadb_qualification
```

It validates and reports only bounded evidence:

- league, sport, shortcut, season, and API identity;
- the six declared provider groups and deterministic `round-1` through
  `round-6` normalization;
- aggregate fixture, participant, status, and per-round counts;
- SHA-256 fingerprints of sorted fixture and participant IDs;
- UTC kickoff and provider-update boundaries; and
- the fixed `partial` authoritative scope.

It does not emit individual fixture IDs, participant IDs or names, raw
responses, logo URLs, venue data, goals, or results.

## Fail-closed boundary

The qualifier rejects non-200, non-JSON, malformed, oversized, or non-list
responses; missing or duplicate league/round/fixture identities; the wrong
sport, league, shortcut, or season; unknown fixture groups; duplicate teams in
one fixture; missing team identity; non-UTC kickoff values; unexpected provider
timezone declarations; invalid update timestamps; dates outside the season;
empty fixture collections; and a round count above the DFB-Pokal capacity.

Normal CI uses synthetic payloads and remains network-free.

## Required implementation and operating gates

1. Run the full qualifier before implementation staging and retain only its
   sanitized output.
2. Repeat the manual DFB comparison whenever a relevant provider change is
   observed.
3. Repeat the complete API observation after a meaningful interval and compare
   fixture and participant fingerprints, counts, group identities, kickoff
   boundaries, status counts, and latest-update evidence.
4. Apply the exact visible attribution and ODbL operating boundary from ADR
   0007.
5. Keep every observation `partial`. OpenLigaDB does not expose enough
   provider-side completeness evidence to authorize `complete_round` or
   `complete_stage` removal semantics.
6. Keep the separate implementation issue limited to DFB-Pokal catalog,
   mapping, adapter, runtime, and staging work.

## Mapping limitations for the later adapter

- `matchID` is the candidate stable external fixture identifier.
- `teamId` is the candidate stable participant identifier.
- Team short names are optional in live data and are not identity fields.
- `leagueId` plus `leagueSeason` binds the season; the reusable shortcut alone
  is insufficient.
- `groupID` is the provider round identity and `groupOrderID` normalizes to
  `round-{n}` independently of localized names.
- `matchDateTimeUTC` is the kickoff authority. `lastUpdateDateTime` is a naive
  provider-local timestamp and is converted using `Europe/Berlin` only after
  `timeZoneID` is validated as `W. Europe Standard Time`.
- `matchIsFinished` distinguishes scheduled from finished matches but does not
  provide a safe cancelled/postponed taxonomy.
- The API exposes no explicit home/away role field beyond `team1` and `team2`,
  no leg identifier, and no placeholder flag.
- Club icon URLs are ignored and must never be imported under this decision.

## Sources

- [OpenLigaDB](https://www.openligadb.de/)
- [OpenLigaDB API](https://api.openligadb.de/)
- [OpenLigaDB API samples and behavior notes](https://github.com/OpenLigaDB/OpenLigaDB-Samples)
- [OpenLigaDB 2026 league directory](https://www.openligadb.de/Leagues?season=2026)
- [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- [DFB-Pokal 2026/27 round dates](https://www.dfb.de/maenner/wettbewerbe/dfb-pokal/rahmentermine)
- [Official DFB season plan](https://datencenter.dfb.de/en/competitions/33/seasons/current?datacenter_name=data-center)
