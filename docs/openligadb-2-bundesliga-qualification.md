# OpenLigaDB 2. Bundesliga Source Qualification

## Status

**Qualified by ADR 0009 for non-destructive complete-season observations.**

Issue #124 evaluates OpenLigaDB league `4938`, shortcut `bl2`, season `2026`
before any catalog, source assignment, import runtime, scheduler, SQLite,
staging, Microsoft Graph, or Outlook behavior is enabled. The paid
football-data.org `BL2` candidate remains a fallback only if no permitted,
technically trustworthy no-cost source can pass qualification.

The intended lifecycle scope is the 18-team, 34-matchday, 306-fixture regular
season. The separately scheduled promotion/relegation matches are outside this
scope and must not be merged into it.

## Project cost policy

SMART Sports Calendar is a hobby project. A permitted and technically
trustworthy no-cost source is preferred over a paid source even when selecting
it requires another bounded provider adapter. A paid provider requires an
explicit operator decision and evidence that no acceptable no-cost candidate
can satisfy the competition contract.

Cost never overrides correctness. A free candidate must still pass the same
identity, completeness, lifecycle, failure, licensing, attribution, and
operational gates. An untrusted or incomplete free source is not preferable to
a qualified paid source.

## Public and licensing evidence

OpenLigaDB is a free community project with unauthenticated JSON API access.
Its data is available under ODbL 1.0. Public produced works require
attribution; a public adapted database can additionally trigger share-alike
and machine-readable-access obligations. Linked logos and icons have separate
rights and remain excluded.

OpenLigaDB is not an official DFL source. Community users can edit its data,
and the API exposes no immutable snapshot marker, pagination metadata, quota
header, documented rate limit, or explicit cancellation/postponement state.
Every observation must therefore prove the complete league structure
independently and fail closed otherwise. The official DFL fixture list remains
the manual verification reference and is never scraped as an automated writer.

## Live candidate evidence

Two secret-free read-only observations at
`2026-08-27T16:38:16.719516Z` and `2026-08-27T16:41:05.585725Z`, separated by
about two minutes and 49 seconds, returned identical evidence:

- API version `v1`;
- league ID `4938`, shortcut `bl2`, season `2026`, and sport ID `1`;
- 34 declared matchday groups with stable positive IDs and orders 1 through 34;
- exactly nine fixtures in every matchday;
- 306 fixtures with 306 distinct positive fixture IDs;
- 18 distinct participants;
- 306 distinct directed home/away pairings;
- 18 `FINISHED` and 288 `SCHEDULED` fixtures;
- kickoff coverage from `2026-08-07T18:30:00Z` through
  `2027-05-23T13:30:00Z`;
- latest provider update `2026-08-16T13:26:22.460000Z`;
- fixture-ID fingerprint
  `eb8065222d41e24db14d52dd0fd5a731b84720b15744ea5195af2ceac27caf30`;
- participant-ID fingerprint
  `7ca7a2e77389c01d15c1aacfa4c444a42db84cdb8d335fc63a39d6559ee484af`;
  and
- three unauthenticated HTTPS requests.

Exactly 18 finished fixtures omit `timeZoneID`; all 306 fixtures still expose
an explicit UTC kickoff. The qualifier accepts a missing timezone declaration
only for this reviewed BL2 profile, counts it in sanitized evidence, and still
rejects any non-empty value other than `W. Europe Standard Time`.
`lastUpdateDateTime` remains a naive provider-local value converted with
`Europe/Berlin`, matching the existing reviewed OpenLigaDB contract.

The complete local comparison against the official 17-page DFL fixture list
extracted exactly 306 unique rows and 34 matchdays with nine fixtures each.
After two uniquely reviewable provider-name variants were normalized, the DFL
and provider scopes had zero missing and zero additional pairings. Both
produced normalized pairing fingerprint
`422afa1b55ca354431ecfc70ce4c503e0bb722ad372f531b576ff0c713e78e58`.

No team name, individual provider ID, pairing, raw payload, logo URL, location,
result, or other fixture detail belongs in committed qualification evidence.

## Read-only qualification command

The command makes three bounded HTTPS GET requests without credentials:

```powershell
python -m app.operations.openligadb_qualification --competition 2-bundesliga
```

It validates:

- exact immutable profile identity for league, shortcut, season, and sport;
- exactly 34 unique matchday groups;
- exactly 306 unique fixtures and 18 unique participants;
- nine fixtures and all 18 participants in every matchday;
- one appearance per participant in every matchday;
- exactly one fixture for every directed participant pairing;
- stable positive fixture, participant, and group identities;
- fixed season date boundaries and explicit UTC kickoffs;
- bounded timezone behavior and provider-local update conversion;
- duplicate, missing, malformed, empty, wrong-scope, and future-update failure;
  and
- sanitized aggregate evidence only.

Normal CI uses synthetic payloads and remains credential-free and network-free.

## Approved operating gates

1. Apply the existing OpenLigaDB attribution and deployment-specific ODbL
   produced-work/adapted-database decision.
2. Keep all failed, short, malformed, empty, stale, or structurally incomplete
   observations non-destructive and preserve last-known-good state.
3. Require explicit review for any fixture-ID or participant-ID set change;
   never translate it directly into removal evidence.
4. Keep the initial implementation removal-disabled because OpenLigaDB exposes
   no explicit cancellation/postponement taxonomy.
5. Create a separate implementation issue for catalog, reviewed participant
   mapping, adapter, runtime, staging, and Outlook validation.

Qualification does not enable the source or make a release claim.

## Sources

- [OpenLigaDB](https://www.openligadb.de/)
- [OpenLigaDB API](https://api.openligadb.de/)
- [OpenLigaDB 2026 league directory](https://www.openligadb.de/Leagues?season=2026)
- [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- [Official 2026/27 Bundesliga and 2. Bundesliga fixture announcement](https://www.bundesliga.com/en/bundesliga/news/2026-27-fixture-lists-now-available-38068)
- [Official 2026/27 DFL calendar](https://www.bundesliga.com/en/bundesliga/news/calendar-for-2026-27-season-world-cup-34676)
