# Provider Integration Contract

## Purpose and boundary

This document defines the provider-independent application boundary for Phase 4
of SMART Sports Calendar. Later provider adapters implement this contract; the
canonical SQLite repositories and Outlook synchronization engine consume only
normalized values.

```text
Provider HTTP and authentication
              |
              v
Provider-specific transport DTOs
              |
              v
Validation and normalization adapter
              |
              v
Provider-independent contract values
              |
              v
Import orchestration and canonical repositories
              |
              v
Existing Outlook synchronization engine
```

Provider DTO field names, response envelopes, API keys, request URLs,
pagination formats, and raw status strings must not cross the adapter boundary.
This contract does not define an HTTP client or retry implementation.

## Contract design rules

- Contract values are immutable typed values, not transport dictionaries.
- Every datetime is timezone-aware and normalized to UTC before crossing the
  boundary.
- Every provider identifier is an opaque non-empty string. Numeric provider IDs
  are converted without losing their exact decimal representation.
- Missing and explicit `null` values are distinguished only inside transport
  validation; normalized optional fields use `None`.
- Unknown enum values are rejected as unsupported values. They are never mapped
  silently to a default.
- Collection order from the provider has no semantic meaning. Normalized
  collections use a deterministic order before comparison or persistence.
- A fetch is authoritative only when all expected pages have completed and all
  items have validated.
- Provider capabilities describe observable behavior; callers do not infer
  capabilities from provider names.

## Typed concepts

The following Python-like definitions describe the required semantics. They are
not an implementation commitment for Issue #43.

```python
ProviderKey = NewType("ProviderKey", str)
ExternalId = NewType("ExternalId", str)
ContinuationToken = NewType("ContinuationToken", str)


class ProviderFixtureStatus(Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    ABANDONED = "abandoned"
    NOT_PLAYED = "not_played"


class ParticipantRole(Enum):
    HOME = "home"
    AWAY = "away"


@dataclass(frozen=True)
class ProviderIdentity:
    key: ProviderKey
    display_name: str
    api_version: str


@dataclass(frozen=True)
class ProviderCapabilities:
    competition_lookup: bool
    season_lookup: bool
    fixture_date_filter: bool
    fixture_status_filter: bool
    pagination: bool
    exposes_rate_limits: bool
    exposes_source_updated_at: bool
    complete_season_snapshot: bool


@dataclass(frozen=True)
class ProviderCompetition:
    external_id: ExternalId
    name: str
    short_name: str | None
    country_code: str | None
    competition_type: str | None


@dataclass(frozen=True)
class ProviderSeason:
    external_id: ExternalId
    competition_external_id: ExternalId
    name: str
    start_date: date | None
    end_date: date | None
    is_current: bool


@dataclass(frozen=True)
class ProviderTeam:
    external_id: ExternalId
    name: str
    short_name: str | None
    country_code: str | None


@dataclass(frozen=True)
class ProviderFixtureParticipant:
    team_external_id: ExternalId
    role: ParticipantRole


@dataclass(frozen=True)
class ProviderFixture:
    external_id: ExternalId
    competition_external_id: ExternalId
    season_external_id: ExternalId
    participants: tuple[ProviderFixtureParticipant, ...]
    kickoff_utc: datetime | None
    kickoff_confirmed: bool
    status: ProviderFixtureStatus
    title: str | None
    stage: str | None
    round_name: str | None
    venue_name: str | None
    source_updated_at: datetime | None


@dataclass(frozen=True)
class RateLimitSnapshot:
    limit: int | None
    remaining: int | None
    reset_at_utc: datetime | None
    window_seconds: int | None
    scope: str | None


@dataclass(frozen=True)
class FetchMetadata:
    provider: ProviderIdentity
    request_id: str | None
    fetched_at_utc: datetime
    scope_description: str
    page_count: int
    item_count: int
    rate_limits: tuple[RateLimitSnapshot, ...]


@dataclass(frozen=True)
class Page[T]:
    items: tuple[T, ...]
    continuation: ContinuationToken | None
    metadata: FetchMetadata
```

The concrete implementation may use protocols and separate query objects, but
it must preserve these semantics.

## Required provider operations

The boundary must support these logical operations:

```text
identity() -> ProviderIdentity
capabilities() -> ProviderCapabilities
find_competition(query) -> ProviderCompetition
find_season(competition_id, query) -> ProviderSeason
fetch_teams(competition_id, season_id, continuation) -> Page[ProviderTeam]
fetch_fixtures(scope, continuation) -> Page[ProviderFixture]
```

Competition and season lookup must fail on zero or multiple matches when a
single entity is required. Callers must not select the first fuzzy name match.
Provider-specific league numbers, season encodings, endpoint paths, or paging
numbers remain behind the adapter.

## External identifiers and source mappings

The existing `data_sources` and `source_mappings` model is authoritative for
provider correlation.

- One `data_sources` row represents the selected provider and API version
  family, using a stable `source_key` such as `api_football`.
- `source_mappings.object_type` uses the existing values `competition`,
  `season`, `participant`, and `event`.
- `external_id` stores the provider identifier exactly after lossless conversion
  to text. It must not include the provider name, URL, season, or mutable title.
- Lookup is by `(source_id, object_type, external_id)`.
- A rescheduled fixture keeps the same event mapping and canonical event.
- Provider URLs are optional diagnostic metadata, never an identity key and
  never stored if they contain credentials.
- An external ID mapping may not be reassigned to a different canonical object
  during an ordinary re-import. A conflict is an integrity error requiring
  investigation.
- Canonical keys are project-owned and are not reconstructed from mutable team
  names or kickoff timestamps.

## Transport DTO and canonical boundary

Transport DTOs mirror a versioned provider response and may contain provider
enums, nullability, wrapper objects, raw strings, and pagination metadata. They
are validated before normalization. They must not be accepted by repository
methods.

Normalized contract values:

- contain only fields needed by the application;
- use project-level enums and role semantics;
- contain UTC-aware datetimes;
- reference related objects by stable external ID;
- exclude credentials, raw headers, and secret-bearing URLs; and
- retain only safe diagnostic metadata.

Raw payloads are not written to canonical metadata columns. Any future need to
retain raw responses requires a separate issue covering retention, encryption,
size, licensing, and deletion policy.

## Kickoff normalization

1. Prefer an explicit provider UTC timestamp when available.
2. Otherwise parse the provider's ISO 8601 timestamp and require an explicit
   offset or documented response timezone.
3. Convert the instant to `datetime.UTC` before returning the fixture.
4. Persist the canonical `start_time` as an ISO 8601 UTC value and canonical
   `timezone` as `UTC`.
5. Never attach `Europe/Vienna`, the host timezone, or UTC to a naive provider
   value merely to make it parseable.
6. A known date without a confirmed time yields `kickoff_utc=None` and
   `kickoff_confirmed=False`; it must not create a fabricated midnight event.
7. DST display conversion belongs at the presentation/calendar boundary. It
   does not alter stored identity or comparison.
8. Equivalent instants with different offsets compare equal after UTC
   normalization.

## Participant semantics

- A football fixture must have exactly two primary participants.
- Exactly one participant has role `home`; exactly one has role `away`.
- Home and away must reference different stable team external IDs.
- Roles come from explicit provider fields, never response position unless the
  provider contract explicitly defines that position.
- Persistence uses the existing `event_participants.role` values `home` and
  `away`, with deterministic position numbers `1` and `2` respectively.
- A home/away reversal from the provider is a material update and must be
  logged; it must not create a second canonical fixture.
- Neutral venue does not remove or swap home/away roles.

## Lifecycle and status mapping

### API-Football adapter mapping

| API-Football status | Contract status | Canonical status | Notes |
| --- | --- | --- | --- |
| `TBD`, `NS` | `SCHEDULED` | `scheduled` | `TBD` has no trustworthy kickoff until a time is confirmed |
| `1H`, `HT`, `2H`, `ET`, `BT`, `P`, `INT`, `LIVE` | `LIVE` | `live` | `INT` remains live/interrupted unless later classified otherwise |
| `FT`, `AET`, `PEN` | `FINISHED` | `finished` | Result enrichment remains outside initial fixture scope |
| `PST` | `POSTPONED` | `postponed` | Identity is retained; a later date updates the same event |
| `CANC` | `CANCELLED` | `cancelled` | Set cancellation semantics without deleting identity |
| `SUSP` | `SUSPENDED` | `suspended` | May later resume or be rescheduled |
| `ABD` | `ABANDONED` | `abandoned` | Remains distinct from cancellation |
| `AWD`, `WO` | `NOT_PLAYED` | `cancelled` | Preserve the provider reason in safe metadata; no fabricated played result |

Unknown provider statuses produce `UnsupportedProviderValueError`. They do not
default to `scheduled`.

### Lifecycle rules

**Scheduled:** A fixture with stable identity and confirmed kickoff is eligible
for canonical import. Repeated unchanged imports are `SKIP` operations.

**Rescheduled:** A kickoff change with the same external fixture ID updates the
existing canonical event. It must not create a new event or source mapping. The
existing Outlook mapping then allows the synchronization engine to update the
same Outlook item.

**Postponed:** The canonical event remains present with status `postponed`.
Retain the last trustworthy kickoff for traceability until a new confirmed
kickoff is supplied; do not invent a replacement time. A later confirmed date
updates the same event and returns it to `scheduled`.

**Cancelled:** Set canonical status `cancelled` and `cancelled_at` at the first
observed transition. Repeated cancellation observations are idempotent. The
existing synchronization policy determines how the Outlook event is marked.

**Suspended:** Set canonical status `suspended`. A later provider transition may
return the same fixture to live, scheduled, postponed, finished, cancelled, or
abandoned without changing identity.

**Abandoned:** Set canonical status `abandoned`. Do not infer cancellation or a
result. A later explicit provider correction may transition the same fixture.

**Removed:** Removal is not a provider status. A fixture becomes a removal
candidate only when it was previously mapped but is absent from a complete,
successful, authoritative fetch whose declared scope includes that fixture.
Absence from a page, date window, status-filtered query, partial fetch, failed
fetch, or changed filter is never removal evidence.

Removal uses a two-observation policy:

1. First complete-snapshot absence records a safe diagnostic candidate marker
   outside canonical deletion behavior.
2. A second complete-snapshot absence in a later successful import confirms
   removal.
3. Confirmation sets canonical `deleted_at`; physical deletion is forbidden.
4. Reappearance before confirmation clears the candidate without changing
   identity.
5. Reappearance after confirmation restores the same mapping and requires an
   explicit canonical update, not a duplicate insert.

The storage mechanism for the candidate marker belongs to Phase 4.5. If the
existing schema cannot support it safely, that issue must define a deterministic
migration rather than overloading unrelated fields.

## Provider-owned canonical fields

Only fields in the following table may be updated automatically from an
ordinary fixture re-import.

| Canonical field | Ownership | Rule |
| --- | --- | --- |
| `competition_id`, `season_id` | Provider mapping | Update only through validated stable mappings; a change is logged as unusual |
| `event_type` | Project | Fixed to the project-defined football fixture type |
| `event_key` | Project | Stable after creation; never rebuilt from mutable provider fields |
| `title` | Derived | Deterministically derived from mapped canonical participant names |
| `stage`, `round_name`, `sequence_number` | Provider | Update when present and valid |
| `start_time`, `timezone` | Provider normalized | Update from confirmed kickoff; timezone remains `UTC` |
| `end_time` | Project policy | Not inferred unless a later issue defines a deterministic rule |
| `venue_name`, `city`, `country_code` | Provider | Update when present and validated; absence does not erase a known value unless the provider explicitly clears it |
| `status` | Provider mapped | Update only through the documented lifecycle mapping |
| `source_updated_at` | Provider | Update when trustworthy and timezone-aware |
| `first_seen_at` | Import system | Immutable after creation |
| `last_seen_at` | Import system | Update on every successful observation of the fixture |
| `cancelled_at` | Import system | Set on first cancellation; clear only after an explicit provider correction policy |
| `deleted_at` | Reconciliation system | Set only after confirmed removal policy |
| `metadata_json` | Mixed, allowlisted | Store only documented, non-secret fields with explicit ownership |

Provider import must not overwrite user/project-owned values merely because a
provider field is absent. Field clearing requires an explicit, tested mapping
rule.

## Validation expectations

Reject the affected item before persistence when any of these applies:

- external fixture, competition, season, or team ID is missing or empty;
- competition or season references do not match the requested scope;
- participant count or home/away roles are invalid;
- kickoff is malformed, naive without a documented timezone, or out of a
  defensible date range;
- provider status is unknown;
- a required string is blank after normalization;
- pagination metadata is contradictory;
- a response reports errors despite HTTP success;
- duplicate external IDs carry conflicting normalized content in one fetch; or
- a mapping would associate one external ID with a different canonical object.

Validation failures must include provider key, safe operation name, object type,
external ID when available, field path, and category. They must not include API
keys, authorization headers, or complete raw payloads.

## Error taxonomy

| Category | Retryable by default | Meaning |
| --- | --- | --- |
| `ProviderConfigurationError` | No | Missing/invalid settings or credential reference |
| `ProviderAuthenticationError` | No | Invalid or expired authentication |
| `ProviderAuthorizationError` | No | Credential or plan cannot access the resource |
| `ProviderTimeoutError` | Yes | Connect/read timeout, including provider-specific timeout response |
| `ProviderNetworkError` | Yes | DNS, connection reset, or temporary connectivity failure |
| `ProviderRateLimitError` | Yes, delayed | HTTP 429 or equivalent quota exhaustion; retain reset/retry metadata |
| `ProviderServerError` | Yes | Retryable provider 5xx failure |
| `ProviderRequestError` | No | Non-retryable malformed request or unsupported filter |
| `ProviderResponseSchemaError` | No | Malformed JSON or response that violates the supported schema |
| `ProviderResolutionError` | No | Provider catalog data cannot be resolved to exactly one compatible canonical object |
| `UnsupportedProviderValueError` | No | Unknown status, role, type, or other enum value |
| `ProviderPaginationError` | Conditional | Missing/repeated page, invalid continuation, or incomplete traversal |
| `ProviderPartialFetchError` | Conditional | Some pages/items failed; fetch is non-authoritative |
| `ProviderIntegrityError` | No | Conflicting IDs, mappings, or duplicate normalized objects |

“Retryable” is semantic guidance, not permission for unbounded retries. Phase
4.2 and Phase 4.6 must define bounded attempts, delay, jitter, `Retry-After` or
reset handling, and final failure reporting.

## Pagination and partial-fetch semantics

- Continuation state is opaque outside the adapter.
- Each page must identify current and terminal state deterministically.
- Repeated continuation tokens or pages are errors.
- A fetch succeeds only after the terminal page validates.
- Items are deduplicated by stable external ID; conflicting duplicates fail the
  fetch.
- Rate-limit state is captured after every page where exposed.
- No absence/removal decisions are allowed from an incomplete fetch.
- Persistence strategy in later issues must either stage the complete result or
  make partial progress explicitly recoverable without reporting success.
- Import success must not be recorded if page retrieval, validation,
  persistence, or finalization fails.

## Diagnostics and rate-limit metadata

Safe diagnostics include provider key, API version, logical operation, scope,
page number/count, item count, request correlation ID, fetch time, quota limit,
remaining quota, and reset time.

Never log or persist:

- API keys or authorization headers;
- full request URLs containing credentials;
- secret-bearing query strings;
- complete raw responses;
- personal account or billing details; or
- headers not explicitly allowlisted.

Provider timestamps and request IDs are diagnostic metadata, not correlation
identity.

## Test-data and live-call policy

### Static test fixtures

Representative fixtures must cover:

- competition and current-season lookup;
- team collection and deterministic home/away participants;
- scheduled fixture with confirmed UTC kickoff;
- TBD fixture without a trustworthy kickoff;
- rescheduled fixture using the same external ID;
- postponed, cancelled, suspended, abandoned, finished, technical-loss, and
  walkover statuses;
- multiple pages and terminal pagination;
- quota headers or metadata;
- HTTP-success envelope with application errors;
- malformed JSON/schema, missing IDs, unknown status, and duplicate conflict;
- timeout, authentication, authorization, rate-limit, server, and partial-fetch
  failures; and
- complete-snapshot removal and reappearance sequences.

Fixture files must:

1. contain no real API key, authorization header, account ID, email, billing
   data, or secret-bearing URL;
2. replace provider request IDs or other trace identifiers with deterministic
   placeholders;
3. retain only the minimum fields needed for the test;
4. use stable synthetic timestamps where real values are not essential;
5. record the source documentation URL, capture date, provider API version, and
   sanitization notes in adjacent metadata;
6. be reviewed before commit; and
7. be treated as test data, not as a redistributable provider dataset.

### CI policy

Normal unit, repository, integration, and regression tests must not require:

- network access;
- live API-Football access;
- a provider credential;
- a Microsoft 365 credential; or
- live Microsoft Graph access.

Any later live-provider smoke test must be separately marked, opt-in, excluded
from normal CI, read-only where possible, quota-bounded, and secret-safe. A live
test failure must not be disguised as a passing deterministic test.

## Contract-level testing strategy

Later implementation issues must add reusable provider contract tests that are
run against every adapter. The suite verifies:

- immutable typed normalized outputs;
- external-ID preservation;
- UTC normalization and naive-time rejection;
- deterministic home/away roles;
- complete status mapping and unknown-value failure;
- complete pagination and repeated-page detection;
- error-category mapping;
- secret-free diagnostic output;
- stable normalization for repeated identical payloads;
- field ownership during updates;
- idempotent reschedule behavior; and
- no removal action after incomplete fetches.

Transport tests use mocked HTTP responses. Import integration tests use the real
SQLite schema and static provider fixtures. Provider-to-Outlook end-to-end tests
use mocked provider transport and mocked Microsoft Graph.

## API-Football-specific assumptions delegated to its adapter

The selected adapter will later own these details and keep them out of generic
application code:

- v3 base URL and `x-apisports-key` authentication;
- league ID and season-start-year query encoding;
- response envelope fields `errors`, `results`, `paging`, and `response`;
- page-number continuation;
- fixture timestamp/date selection;
- status-code translation;
- HTTP 499 timeout classification;
- daily and per-minute rate-limit header names; and
- the distinction between HTTP success and envelope success.

## Non-goals for Phase 4.1

This contract introduces no provider package, runtime protocol, credentials,
HTTP transport, retry/backoff behavior, database migration, source row,
canonical import, scheduler integration, Graph call, or Outlook behavior
change. Those changes require their dedicated Phase 4 child issues and tests.
