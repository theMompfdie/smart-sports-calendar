# API-Football Premier League Catalog Mapping

## Status and scope

This document records the Phase 4.3 implementation boundary from GitHub issue
#47. The application can validate and resolve the API-Football Premier League,
its current season, and its complete team collection, then correlate those
provider identifiers with the existing canonical SQLite catalog.

This block does not import fixtures, run on the scheduler, write sports events,
or invoke Microsoft Graph.

## Provider identity

The selected source is registered idempotently as:

| Field | Value |
| --- | --- |
| Source key | `api_football` |
| Name | `API-Football` |
| API version family | `v3` |
| Base URL | `https://v3.football.api-sports.io` |
| Authentication metadata | `x-apisports-key` |

The stored source metadata describes the integration protocol only. It never
contains an API key, account identifier, request header value, or raw response.

## Exact competition and season resolution

The adapter requests `/leagues?id=39` and accepts exactly one response whose
league ID is `39`. It does not search by name and does not accept the first item
from an ambiguous response.

API-Football represents a season by its starting year. Exactly one season entry
must have `current=true`, and that year must equal the start year of the one
canonical Premier League season marked current. The provider year is stored
losslessly as the season mapping's external ID.

## Reviewed team correlation

The project-owned mapping in
`app/providers/api_football/team_mappings.py` correlates stable API-Football
team IDs with existing canonical participant keys. Provider names, team codes,
logos, venues, and response order never determine identity.

The mapping covers the complete canonical `2026_27` Premier League catalog. A
provider response must contain exactly the reviewed ID set before any mapping
write begins. Missing or unexpected IDs fail with `ProviderIntegrityError`.

API-Football documents that team IDs are unique and persist across competitions
and seasons. It also documents the `league` plus season-start-year request for
retrieving a competition's teams:

- [API-Football v3 documentation](https://www.api-football.com/documentation-v3)
- [Official team-ID retrieval tutorial](https://www.api-football.com/news/post/how-to-get-all-teams-and-their-ids)

## Persistence and conflict policy

The existing `data_sources`, `source_mappings`, and `season_participants` tables
remain authoritative. No schema migration is required.

The following object types are written:

- `competition`: API-Football league ID to canonical `premier_league`
- `season`: API-Football season start year to canonical current season
- `participant`: API-Football team ID to canonical team participant

`SourceMappingsRepository` rejects both conflict directions:

1. an existing external ID cannot be reassigned to another canonical row;
2. an existing canonical row cannot receive another external ID for the same
   source and object type.

The application service preflights the complete mapping set before persisting
individual correlations and reclassifies persistence conflicts as
`ProviderIntegrityError`. Repeated identical runs return existing source and
mapping rows without timestamp churn and skip existing season memberships.

## Safe metadata

Only selected diagnostic fields are retained in source-mapping metadata:

- provider display name and type;
- provider country and team code;
- season start/end dates and current flag;
- safe HTTPS logo URL;
- venue name and city.

Raw payloads, response headers, request IDs, credentials, and authentication
values are not persisted.

## Deterministic test data

Sanitized deterministic response-shape fixtures live in
`tests/fixtures/api_football`. They were prepared from the official API-Football
v3 documentation and the repository-owned canonical catalog; they were not
captured through a live provider request. The adjacent `catalog_metadata.json`
records that provenance, API version, preparation date, and sanitization
decisions. Normal tests use injected adapters or mocked transport and never
require network access, an API-Football credential, or a Microsoft 365
credential.

## Remaining Phase 4 work

Phase 4.4 and later issues still need to implement:

- fixture DTO validation and canonical normalization;
- sports-event and home/away participant persistence;
- incremental imports and lifecycle reconciliation;
- persistent import reporting and scheduling;
- provider-to-Outlook end-to-end integration.
