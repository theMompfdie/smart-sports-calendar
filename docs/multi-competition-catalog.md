# Multi-Competition Catalog Foundation

## Scope

Issue #112 establishes the Phase 5.4 catalog and provider-identity boundary.
The deterministic database bootstrap now describes competitions, seasons, and
participant memberships through explicit competition-scoped definitions.

The catalog contains:

| Competition | Canonical key | Season | Format | Catalog status |
| --- | --- | --- | --- | --- |
| Premier League | `premier_league` | 2026/27 | `league` | Existing implemented baseline |
| Bundesliga | `bundesliga` | 2026/27 | `league` | Competition and season only |

Bundesliga season dates are the qualified 2026-08-28 through 2027-05-22
boundaries recorded by issue #110 and ADR 0006.

## Identity boundaries

Canonical keys remain independent from provider identifiers. The reviewed
football-data.org identities are:

| Canonical competition | Provider code | Provider ID |
| --- | --- | ---: |
| `premier_league` | `PL` | 2021 |
| `bundesliga` | `BL1` | 2002 |

Provider team-name resolution is also competition-scoped. A name registered
for one competition cannot resolve through another competition's mapping.
The Bundesliga mapping is intentionally empty until a separate implementation
issue adds a reviewed participant catalog and deterministic offline fixtures.

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

## Explicit non-enablement

Cataloged and provider-mapped do not mean implemented or released. Phase 5.4
does not add Bundesliga teams, fixtures, source mappings, an authoritative
source assignment, a scheduler job, SQLite events, staging behavior, or
Microsoft Graph writes. The football-data.org production adapter remains
strictly Premier-League-specific until a later issue generalizes and validates
the complete import path.
