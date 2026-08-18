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
| DFB-Pokal | `dfb_pokal` | 2026/27 | `knockout_cup` | Added by issue #119 |

Bundesliga season dates are the qualified 2026-08-28 through 2027-05-22
boundaries recorded by issue #110 and ADR 0006.

Subsequent Phase 5 slices completed the Bundesliga participant/runtime path
and added the DFB-Pokal competition, season, and 64 reviewed 2026/27
participants. Shared clubs retain one canonical participant identity across
Bundesliga and DFB-Pokal memberships.

## Identity boundaries

Canonical keys remain independent from provider identifiers. The reviewed
football-data.org identities are:

| Canonical competition | Provider code | Provider ID |
| --- | --- | ---: |
| `premier_league` | `PL` | 2021 |
| `bundesliga` | `BL1` | 2002 |

Provider team-name resolution is also competition-scoped. A name registered
for one competition cannot resolve through another competition's mapping.
The Bundesliga mapping is implemented by issue #114. DFB-Pokal uses a separate
reviewed OpenLigaDB `teamId` plus provider-name mapping; it does not reuse the
football-data.org name resolver.

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
