# API-Football Fixture Normalization

## Status and boundary

Phase 4.4 implements the provider-to-canonical normalization boundary tracked
by GitHub issue #49. It validates complete API-Football Premier League fixture
collections and produces immutable canonical-ready values.

The workflow is deliberately side-effect-free. It does not insert or update
`sports_events`, `event_participants`, event source mappings, scheduler state,
or Outlook events. Persistence and lifecycle reconciliation remain Phase 4.5
work.

## Fixture identity and scope

The provider fixture ID is the only external fixture identity and is converted
losslessly to text. Titles, kickoff timestamps, team names, venue data, and
response order never participate in identity.

Every collection request uses the exact mapped scope:

- API-Football league ID `39`;
- the start year of the one canonical current Premier League season; and
- the complete paginated `/fixtures` result.

Every returned item must repeat that league and season scope. Duplicate fixture
IDs or out-of-scope items fail the entire normalization operation.

## Canonical mapping

The normalizer resolves the existing `api_football` data source and requires
the Phase 4.3 `competition`, `season`, and `participant` source mappings.
Missing or incompatible mappings raise `ProviderResolutionError`.

Provider team names are discarded before canonical lookup. The normalized
title is derived from the mapped canonical participant names, and roles are
fixed as:

| Role | Position |
| --- | --- |
| `home` | `1` |
| `away` | `2` |

Home and away must be distinct stable team IDs.

## Kickoff rules

Confirmed kickoff instants use the provider Unix timestamp when present and
validate any accompanying offset-aware ISO 8601 value against the same instant.
The result is always timezone-aware `datetime.UTC`, with canonical timezone
`UTC`.

Naive, malformed, contradictory, or out-of-range values fail explicitly. A
`TBD` fixture is represented with `kickoff_utc=None` and
`kickoff_confirmed=False`; a provider placeholder at midnight is never promoted
to a confirmed kickoff.

## Status mapping

The adapter implements the complete status table from the provider integration
contract:

| API-Football | Contract | Canonical-ready status |
| --- | --- | --- |
| `TBD`, `NS` | scheduled | `scheduled` |
| `1H`, `HT`, `2H`, `ET`, `BT`, `P`, `INT`, `LIVE` | live | `live` |
| `FT`, `AET`, `PEN` | finished | `finished` |
| `PST` | postponed | `postponed` |
| `CANC` | cancelled | `cancelled` |
| `SUSP` | suspended | `suspended` |
| `ABD` | abandoned | `abandoned` |
| `AWD`, `WO` | not played | `cancelled` plus safe reason metadata |

Unknown values raise `UnsupportedProviderValueError` and never default to
`scheduled`.

## Safe normalized values

The allowlist contains only fields needed by the future importer:

- stable external fixture ID;
- canonical sport, competition, season, home team, and away team IDs;
- deterministic title, event type, roles, and positions;
- confirmed UTC kickoff or explicit unconfirmed kickoff;
- mapped status;
- round, stage, and sequence number;
- venue name and city; and
- timezone-aware provider update time when supplied.

Only awarded/walkover status code and reason are retained in metadata. Raw
payloads, response headers, provider team names, request identifiers,
credentials, and secret-bearing URLs are excluded.

## Deterministic tests

`tests/fixtures/api_football/premier_league_fixtures.json` contains sanitized,
deterministic response-shape examples for scheduled, TBD, live, finished,
postponed, cancelled, suspended, abandoned, awarded, and walkover fixtures.
`catalog_metadata.json` records their provenance and sanitization boundary.

Tests cover validation, every supported status code, UTC conversion, equivalent
offsets, TBD semantics, pagination, scope checks, duplicate IDs, mapping-backed
SQLite resolution, deterministic canonical titles, and proof that no event
rows or event mappings are written.

## Downstream persistence

Phase 4.5 persists these normalized values through the transactional,
idempotent boundary documented in
[`api-football-fixture-import.md`](api-football-fixture-import.md). Later issues
still own persistent import reporting, scheduler execution, and
provider-to-Outlook orchestration.
