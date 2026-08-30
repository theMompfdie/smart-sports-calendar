# Multi-Competition Catalog Foundation

## Scope

Issue #112 establishes the Phase 5.4 catalog and provider-identity boundary.
The deterministic database bootstrap now describes competitions, seasons, and
participant memberships through explicit competition-scoped definitions.

The catalog contains:

| Competition | Canonical key | Season | Format | Catalog status |
| --- | --- | --- | --- | --- |
| Premier League | `premier_league` | 2026/27 | `league` | Existing implemented baseline |
| Bundesliga | `bundesliga` | 2026/27 | `league` | Implemented by issue #114 |
| EFL Championship | `championship` | 2026/27 | `league` | Regular season implemented by issue #135; play-offs excluded |
| DFB-Pokal | `dfb_pokal` | 2026/27 | `knockout_cup` | Added by issue #119 |
| 2. Bundesliga | `second_bundesliga` | 2026/27 | `league` | Added by issue #132; removal disabled |
| UEFA Nations League | `uefa_nations_league` | 2026/27 | `hybrid_tournament` | League A group phase added by issue #170; removal disabled |

Bundesliga season dates are the qualified 2026-08-28 through 2027-05-22
boundaries recorded by issue #110 and ADR 0006.

Subsequent Phase 5 slices completed the Bundesliga participant/runtime path and
added the DFB-Pokal and 2. Bundesliga catalogs. Phase 6 issue #170 adds the 16
reviewed League A national teams. DFB-Pokal has 64 reviewed 2026/27
participants; 2. Bundesliga has 18. Shared clubs retain one canonical
participant identity across competition memberships.

## Identity boundaries

Canonical keys remain independent from provider identifiers. The reviewed
football-data.org identities are:

| Canonical competition | Provider code | Provider ID |
| --- | --- | ---: |
| `premier_league` | `PL` | 2021 |
| `bundesliga` | `BL1` | 2002 |
| `championship` | `ELC` | 2016 |

Provider team-name resolution is also competition-scoped. A name registered
for one competition cannot resolve through another competition's mapping.
The Bundesliga mapping is implemented by issue #114. The Championship mapping
contains exactly the 24 reviewed 2026/27 regular-season participants, including
country-specific identities for Cardiff City, Swansea City, and Wrexham.
DFB-Pokal and 2. Bundesliga use separate reviewed OpenLigaDB `teamId` plus
provider-name mappings; they do not reuse the football-data.org name resolver.
The Nations League profile admits only 16 exact reviewed provider names on
first import and learns their numeric IDs in the private source-mapping
repository. Those IDs are intentionally absent from the public catalog and
synthetic tests.

## Initialization behavior

Catalog initialization uses idempotent repository upserts. Repeated startup:

- preserves stable row IDs and creation timestamps;
- restores reviewed master-data fields if they were changed;
- does not delete unrelated or historical rows; and
- fails with the missing canonical key when a required sport, competition, or
  season dependency is absent.

The existing SQLite schema already supports multiple competitions, seasons,
participants, memberships, provider mappings, and source assignments. Phase
5.4 therefore requires no schema migration.

## Historical Phase 5.4 boundary

Cataloged and provider-mapped do not mean implemented or released. Phase 5.4
does not add Bundesliga teams, fixtures, source mappings, an authoritative
source assignment, a scheduler job, SQLite events, staging behavior, or
Microsoft Graph writes. The football-data.org production adapter remains
strictly Premier-League-specific until a later issue generalizes and validates
the complete import path.

That paragraph describes the completed #112 boundary. Issues #114 and #119
subsequently enabled the Bundesliga and DFB-Pokal implementation paths. Live
staging and release claims remain separate operator gates.
