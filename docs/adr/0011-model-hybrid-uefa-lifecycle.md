# ADR 0011: Model hybrid UEFA lifecycle and unresolved fixtures explicitly

- Status: Accepted
- Date: 2026-08-28
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #150, #151
- Follows: ADR 0004

## Context

ADR 0004 introduced provider-neutral league and knockout/cup formats with
partial, complete-season, complete-stage, and complete-round observation
scopes. That model safely supports the Phase 5 competition set, but no single
format describes a UEFA edition that moves through qualifying, play-offs, a
league phase, draw-dependent knockout rounds, two-legged ties, and a final.

UEFA schedules may also publish a stable fixture before one or both actual
participants are known. Persisting labels such as "winner of tie A" as teams
would create false canonical identities. Inferring a fixture from later
participants, kickoff, or round text would weaken the existing source-mapping
contract.

## Decision

Extend the shared lifecycle model rather than creating a UEFA-specific import
path.

- Add the canonical competition format `hybrid_tournament`.
- Treat the existing canonical `seasons` row as the edition or competition
  cycle boundary. Its project-owned `season_key` identifies one UEFA edition;
  no separate edition aggregate or provider season encoding enters the domain.
- Add provider-neutral stage kinds for qualifying, play-off, league phase,
  knockout play-off, knockout, and final stages.
- Continue to use normalized `stage` and `round_name` as the exact persisted
  reconciliation boundary. A hybrid complete stage or round must also declare
  its typed stage kind. A hybrid complete round always requires both stage and
  round identifiers.
- Keep the individual fixture as the calendar synchronization aggregate.
- Represent fixture legs as `single`, `first`, or `second`. First and second
  legs require a normalized opaque, source-scoped tie key for diagnostics, but
  neither tie key nor aggregate score becomes fixture identity.
- Represent every home and away slot as explicitly `resolved` or `unresolved`.
  A resolved slot requires a positive canonical participant ID. An unresolved
  slot has no participant ID and carries no provider placeholder label across
  the normalized boundary.
- Defer an observation containing any unresolved participant before canonical
  or Outlook writes. If the stable source fixture already maps to an event, the
  deferred observation returns that event identity without replacing its
  participants or other canonical fields.
- When the same stable source fixture later contains two resolved participants,
  it follows the existing create/update path. No title, kickoff, stage, round,
  tie, leg, or participant heuristic substitutes for stable source identity.
- Persist safe typed stage-kind, tie-key, and leg diagnostics inside the
  existing event metadata object. The `tournament_lifecycle` key is reserved
  for the import layer and cannot be supplied by provider metadata.

Source authority and completeness remain independent. A partial or incremental
hybrid observation is never removal-capable. Exact complete-stage and
complete-round observations may contribute removal evidence only after a
competition-specific source qualification proves that boundary complete and
all existing validation, authority, non-empty, replay, and two-observation
safeguards pass.

## Persistence

No schema migration is required.

- `competitions.competition_type` already stores a typed text value and can
  persist `hybrid_tournament` without rewriting existing rows.
- `sports_events.stage` and `sports_events.round_name` remain the exact
  reconciliation selectors.
- `sports_events.metadata_json` stores the safe optional tournament lifecycle
  diagnostics.
- Stable event identity remains in `source_mappings`; reconciliation state and
  Outlook mappings remain unchanged.
- Unresolved fixtures are not persisted, so no placeholder participant table
  or nullable event-participant foreign key is introduced.

A later provider implementation must open a separate migration decision if it
proves that a canonical tie aggregate is required. Source qualification alone
does not justify that schema.

## Consequences

- Phase 6 providers share the existing fixture import and synchronization path.
- A hybrid stage is both human-inspectable and typed without encoding provider
  stage codes into canonical logic.
- Complete hybrid reconciliation remains bounded by the same persisted
  stage/round dimensions already proven for cups.
- Placeholder publication is safe but intentionally produces no calendar item
  until both canonical participants are resolved.
- A provider whose fixture identifier changes when participants resolve cannot
  be authoritative without separate correlation evidence and review.
- Existing Phase 5 formats, rows, mappings, and behavior require no migration
  or backfill.

## Alternatives considered

### Treat UEFA competitions as knockout cups

Rejected because the league phase, qualifying path, and knockout path have
different lifecycle and completeness semantics. Provider strings would become
implicit capability flags.

### Create canonical placeholder teams

Rejected because placeholders are bracket references, not sports participants.
They would pollute participant mappings and make later resolution an identity
rewrite.

### Create events without participants

Rejected for Phase 6.1 because the current canonical and Outlook presentation
contracts assume a resolved home/away fixture. Deferral is deterministic and
does not require weakening those invariants.

### Add tie and tournament-bracket tables now

Rejected as premature. Calendar synchronization needs stable fixtures, not a
bracket engine or aggregate-score model. Typed fixture metadata is sufficient
for the approved contract.
