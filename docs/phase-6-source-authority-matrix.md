# Phase 6 Source and Authority Matrix

## Status and decision boundary

This matrix tracks the five candidate competitions in Phase 6 master issue
#150. It is initialized by the UEFA Champions League source qualification in
#154 and must be extended one competition at a time through the corresponding
competition tracker.

Evidence was first reviewed on 2026-08-28. Provider coverage, terms, plans,
competition formats, and season data can change. Every outcome requires a
dated competition-specific qualification record before implementation.

The operator requires the selected UEFA Champions League fixture source to
cost EUR 0. Free registration and a free API credential are permitted. This
constraint is recorded for the Champions League track only; later competition
tracks must record their own operator boundary rather than infer one.

Decision meanings:

- `Qualified`: the named zero-cost source and exact scope have passed every
  stated gate and may proceed to a separate operator release-inclusion
  decision.
- `Conditional`: implementation is blocked by every listed unmet condition.
- `Deferred`: the competition is outside the current release boundary, with
  explicit reconsideration triggers.
- `Rejected`: the evaluated source path is unsuitable under the stated
  constraints.
- `Pending`: the competition-specific qualification issue has not been
  created or completed.

This matrix does not enable a provider, assign an authority, accept terms,
create credentials, or approve release inclusion.

## Competition decisions

| Competition | Intended edition/cycle | Outcome | Preferred candidate | Authority assignment | Release boundary | Qualification record |
| --- | --- | --- | --- | --- | --- | --- |
| UEFA Champions League | 2026/27 | Conditional | football-data.org API v4 `CL` / 2001, free tier; operator-selected 2026-08-28 | Unassigned pending credentialed qualification | League phase through final; 2026/27 qualifying rounds explicitly excluded | [Champions League qualification](uefa-champions-league-source-qualification.md) |
| UEFA Europa League | 2026/27 | Pending | Not evaluated for Phase 6 | Unassigned | Not approved | Future competition track |
| UEFA Conference League | 2026/27 | Pending | Not evaluated for Phase 6 | Unassigned | Not approved | Future competition track |
| UEFA Nations League | Exact active edition pending | Pending | Not evaluated for Phase 6 | Unassigned | Not approved | Future competition track |
| UEFA European Championship Qualification | Exact active cycle pending | Pending | Not evaluated for Phase 6 | Unassigned | Not approved | Future competition track |

## Champions League candidate summary

| Candidate | Cost fit | Technical fit | Rights/terms fit | Current decision |
| --- | --- | --- | --- | --- |
| Official UEFA public pages and regulations | Free | No documented automation contract or stable machine fixture identity | Authoritative manual evidence only | Manual verification; not an automated writer |
| football-data.org `CL` / 2001 | Free registration and free tier | Promising main-competition fixture identity and lifecycle fields; 2026/27 credentialed evidence pending | One-application use, secret key, attribution, cancellation exit obligation | Preferred conditional candidate for league phase and later |
| football-data.org `CLQ` / 2174 | Paid tier | Separate qualification competition | Same football-data.org terms | Rejected by zero-cost constraint |
| API-Football | Free registration, 100 requests/day | Broad technical coverage and existing transport | Provider grants no competition-data licence; UEFA permission not recorded | Rejected as authority under current evidence |
| Sportmonks | Champions League requires paid plan | Strongest documented hybrid lifecycle model | Paid plan terms would require separate acceptance | Rejected by zero-cost constraint |

## Shared Phase 6 invariants

1. Exactly one enabled authoritative writer may exist per competition and
   edition.
2. A source qualified for only part of an edition must be described and
   configured with that exact boundary; it cannot imply full-edition coverage.
3. Provider fixture IDs remain the primary correlation key.
4. Partial and incremental observations never create removal evidence.
5. Complete stage or round observations require competition-specific proof and
   two distinct successful observations.
6. Missing, stale, malformed, filtered, empty, failed, or ambiguous evidence
   preserves last-known-good canonical and Outlook state.
7. Paid trial access is not a zero-cost production authority.
8. Public competition pages are not machine authorities without documented
   permitted automated access and stable identity.
9. Normal CI remains credential-free and network-free.
10. Secrets, account metadata, raw private payloads, and secret-bearing URLs
    never enter source control or GitHub evidence.

## Champions League operator decision

On 2026-08-28 the operator selected football-data.org and approved a bounded
2026/27 release scope beginning with the league phase. The already completed
qualifying rounds are deliberately excluded for this season. This resolves the
scope-choice gate but does not yet qualify the provider or assign authority.

## Required next gate

The Champions League track cannot create an implementation issue until:

1. the free football-data.org `CL` scope exposes 2026/27 data;
2. two sanitized credentialed observations prove identity, structure,
   pagination, quota fit, and stable fingerprints; and
3. the operator accepts the current terms and attribution requirement when
   registering or using the free credential.

The 2026/27 qualification stage is not an implementation blocker because it is
outside the approved release boundary. It must not be presented as imported,
implemented, or released.
