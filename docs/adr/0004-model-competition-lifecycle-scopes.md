# ADR 0004: Model competition lifecycle and observation scopes explicitly

- Status: Accepted
- Date: 2026-08-16
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #104, #105
- Follows: ADR 0003

## Context

The production-qualified Premier League path treats one validated 20-team,
380-match response as a complete season observation. Its import scope contains
the competition, season, UTC season window, source authority flag, and generic
complete/filtered flags.

That representation cannot safely describe a cup whose fixtures become known
incrementally. A successful authoritative-source request may be partial, and a
complete cup observation may cover one stage or round rather than an entire
season. Treating source authority as snapshot completeness would allow absence
outside the observed scope to become false removal evidence.

The existing schema already stores canonical `competitions.competition_type`
and fixture `stage` / `round_name`. Provider import runs already persist safe
metadata in `sync_runs.metadata_json`.

## Decision

Use a provider-neutral typed model with two separate concepts:

- `CompetitionFormat`: `league` or `knockout_cup`;
- `FixtureObservationScopeKind`: `partial`, `complete_season`,
  `complete_stage`, or `complete_round`.

A lifecycle scope validates the allowed combination and its required stable
stage or round identifier. Unknown and contradictory values fail closed.

Source authority and observation completeness remain independent. An
authoritative source may submit a partial observation that creates or updates
fixtures but cannot produce absence/removal evidence. Verification, bootstrap,
and disabled sources remain outside canonical fixture writes under the current
source registry contract.

For Phase 5.1, removal reconciliation is enabled only when all of the following
are true:

1. the configured source is authoritative;
2. the observation is unfiltered;
3. the canonical competition format is `league`;
4. the scope kind is `complete_season`;
5. a valid bounded UTC season window is present.

`complete_stage` and `complete_round` are representable and validated, but they
do not yet create removal evidence. A later knockout/cup lifecycle issue must
implement and prove exact stage/round event selection before enabling that
behavior.

## Persistence

No schema migration is required for this decision.

- `competitions.competition_type` remains the canonical persisted format. The
  repository converts it to `CompetitionFormat` and rejects unknown values.
- The existing Premier League catalog deterministically restores `league` on
  idempotent startup without changing its row ID.
- Observation scope kind, format, optional stage/round, completeness, and
  removal eligibility are stored in the existing provider import-run metadata.
- Canonical event IDs, event keys, source mappings, reconciliation state, and
  Outlook mappings are not rewritten.

Adding a separate capability table or duplicate columns now would create two
sources of truth without adding a released behavior.

## Consequences

- Provider adapters cannot introduce provider-specific competition types into
  canonical repositories.
- The fixture import repository verifies the declared lifecycle format against
  the canonical competition before writing.
- Partial authoritative observations are safe and non-destructive.
- Existing Premier League CREATE, UPDATE, SKIP, CANCEL, DEFER, and two-complete-
  observation removal behavior remains unchanged.
- Later Phase 5 issues can add competition catalogs and cup reconciliation
  against one explicit contract.

## Alternatives considered

### Continue using `authoritative`, `complete`, and `filtered` booleans

Rejected because independent booleans do not identify the boundary that is
complete and permit contradictory combinations.

### Add a competition-capabilities table in Phase 5.1

Rejected for now because one canonical format value and run-scoped observation
metadata satisfy the approved behavior. A new table may be justified later if
one competition needs multiple persisted lifecycle strategies.

### Enable stage/round removal immediately

Rejected because the current repository selects missing candidates only by
competition, season, and UTC window. Enabling it without exact stage/round
selection would risk deleting fixtures outside the observed cup scope.
