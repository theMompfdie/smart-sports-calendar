# API-Football Fixture Import and Reconciliation

## Boundary

Phase 4.5 implements the persistence boundary tracked by GitHub issue #51. It
accepts only validated `NormalizedFixture` values from Phase 4.4. It does not
fetch provider data, schedule imports, write persistent run reports, or call
Microsoft Graph.

`ApiFootballFixtureImportService` validates the declared observation scope and
resolves the registered `api_football` source. `FixtureImportRepository` then
persists the complete observation in one `BEGIN IMMEDIATE` SQLite transaction.
Events, participants, stable source mappings, and reconciliation state either
commit together or roll back together.

## Stable identity and decisions

The provider fixture ID is correlated through an `event` source mapping. The
project-owned event key is deterministic:

```text
api_football:fixture:<provider fixture ID>
```

The import result uses explicit decisions:

- `CREATE`: create the canonical event, its home/away participants, and mapping.
- `UPDATE`: change provider-owned fields or reactivate a removed/cancelled event.
- `SKIP`: the persisted canonical content already matches.
- `CANCEL`: transition an existing event to canonical `cancelled`.
- `DELETE`: mark a fixture removed after two qualifying observations.
- `DEFER`: do not create a new fixture whose kickoff is still unconfirmed.

No decision physically deletes a sports event or its stable source mapping.
Repeated identical inputs leave the event and participant rows unchanged.

## Kickoff and optional-field rules

A confirmed UTC kickoff creates or updates `start_time`. A newly discovered
fixture without a confirmed kickoff is deferred because `sports_events`
requires a real start time; no midnight or other placeholder is fabricated.
If an existing event later becomes TBD, its last confirmed kickoff remains
stored until a new confirmed value arrives.

Absent optional values do not erase known `stage`, `round_name`, sequence,
venue, city, provider update timestamp, or metadata. Valid explicit normalized
values may update those fields.

## Lifecycle reconciliation

Canonical postponed, suspended, and abandoned states are persisted directly.
Cancelled, awarded, and walkover provider outcomes normalize to `cancelled`;
the latter two retain their sanitized provider reason in metadata.
`cancelled_at` is set only on the first transition and remains stable on
repeated observations. A later provider correction clears it.

Removal detection is permitted only for an observation explicitly declared
`authoritative=True`, complete through a supported typed lifecycle scope, and
`filtered=False`. A league `complete_season` scope requires a bounded UTC
season window. A knockout/cup `complete_stage` or `complete_round` scope must
be non-empty, and every returned fixture must match its exact normalized stage
or round. An optional stage on a complete-round scope is also part of the exact
boundary. Mixed or contradictory collections fail before repository writes.

The repository selects missing candidates only from the same source,
competition, season, optional UTC window, and declared stage/round boundary.
Fixtures in another stage or round cannot gain or advance reconciliation state.

The first qualifying absence creates a reconciliation candidate. A second,
distinct authoritative observation confirms it and sets `deleted_at`. Replaying
the same observation ID cannot advance the counter. Reappearance before
confirmation clears the candidate; reappearance after confirmation clears
`deleted_at` while retaining the original event and mapping identity.

Partial, failed, filtered, non-authoritative, empty, or scope-conflicting
observations cannot create removal candidates. Completeness is a qualified
provider claim; it is never inferred from HTTP success or the returned count.

## Migration and retry behavior

Migration `005_create_fixture_reconciliation_state.sql` adds only durable
candidate state and indexes. It is deterministic, preserves existing data, and
is idempotently registered by the existing migration runner.

An integrity failure, mapping conflict, or participant constraint failure rolls
back the complete observation. The unchanged input can be retried safely.
Mapping/key conflicts are surfaced as `ProviderIntegrityError` rather than
silently reassigning an external identity.

## Testing

The integration tests use migrated temporary SQLite databases and no live
provider or Graph calls. They cover stable identity, exact home/away
persistence, write-free repeated imports, kickoff changes and TBD retention,
optional-field preservation, cancellation and correction, two-observation
removal, same-observation replay, reappearance, partial-scope safety, mapping
conflicts, exact stage/round isolation, transactional rollback and retry, and
SQLite-to-recording-Graph removal/reappearance behavior.

## Remaining work

Concrete cup support still requires competition-specific provider
qualification, stable stage/round mapping, completeness evidence, catalog and
runtime configuration, and isolated staging validation.
