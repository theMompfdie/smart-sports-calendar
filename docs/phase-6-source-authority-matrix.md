# Phase 6 Source and Authority Matrix

## Status and decision boundary

This matrix tracks the five candidate competitions in Phase 6 master issue
 #150. It is initialized by the UEFA Champions League source qualification in
 #154 and must be extended one competition at a time through the corresponding
competition tracker.

Evidence was first reviewed on 2026-08-28 and extended to the Europa League on
2026-08-29. Provider coverage, terms, plans, competition formats, and season
data can change. Every outcome requires a dated competition-specific
qualification record before implementation.

The operator requires the selected UEFA Champions League fixture source to
cost EUR 0. Free registration and a free API credential are permitted. This
constraint is recorded for the Champions League track only; later competition
tracks must record their own operator boundary rather than infer one.

For the Europa League, the operator approved a possible 2026/27 release
boundary from the league phase through the final. Qualification may be
evaluated later as a separate optional competition/source scope and is not a
main-track blocker. No Europa League provider or recurring-cost boundary is
selected yet.

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
| UEFA Europa League | 2026/27 | Conditional | OpenLigaDB `uel2026` / 6000 is the zero-cost candidate but currently incomplete; football-data.org `EL` / 2146 and Sportmonks league 5 are paid alternatives pending operator decision | Unassigned pending source, cost, and live qualification | League phase through final is the approved candidate boundary; qualification is separate and optional | [Europa League qualification](uefa-europa-league-source-qualification.md) |
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

## Europa League candidate summary

| Candidate | Cost fit | Technical fit | Rights/terms fit | Current decision |
| --- | --- | --- | --- | --- |
| Official UEFA public pages and regulations | Free | No documented automation contract or stable machine fixture identity | Authoritative manual evidence; automated collection prohibited | Manual verification only |
| OpenLigaDB `uel2026` / 6000 | Free and credential-free | Existing adapter and stable-looking IDs, but only 16 fixtures, 14 participants, one placeholder kickoff, and incomplete round structure observed | ODbL attribution applies; community-maintained rather than official | Conditional zero-cost candidate; not ready and removal-disabled if later selected |
| football-data.org `EL` / 2146 | Standard plan, currently EUR 49/month | Existing integration; main competition cleanly separated from `ELQ` / 2183; public catalog still exposes 2025/26 | One-application use, secret key, attribution, and cancellation exit obligation | Paid conditional candidate pending operator approval and live evidence |
| Sportmonks league 5 | Starter from EUR 29/month; card-backed trial | Strongest documented full hybrid lifecycle; new adapter required | Subscription/domain terms, no raw resale, completeness disclaimer, separate media rights | Paid conditional candidate pending operator approval and live evidence |
| API-Football | Free registration, 100 requests/day | Broad technical coverage and existing transport | Provider grants no competition-data licence; UEFA permission not recorded | Rejected as authority under current evidence |

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
11. Separately exposed qualifying and main-competition sources cannot merge
    automatically or contribute removal evidence across scope boundaries.

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

## Europa League operator decision and required next gate

On 2026-08-29 the operator approved a candidate boundary beginning with the
league phase. Separately exposed qualification may be evaluated later and does
not block the main track. This does not approve a provider or paid plan.

The Europa League track cannot create credentialed-validation or implementation
work until:

1. the operator selects the acceptable provider and exact recurring-cost
   boundary: wait for OpenLigaDB at EUR 0, approve football-data.org at the
   then-current price, approve Sportmonks at the then-current price, or defer;
2. the selected main competition exposes the 2026/27 league-phase schedule;
3. two sanitized observations prove 36 participants, 144 league-phase
   fixtures, stable identity, structure, pagination, update behavior, and
   reproducible fingerprints; and
4. selected-provider terms, attribution, persistence, cancellation, and secret
   handling are accepted explicitly.

The OpenLigaDB observation on 2026-08-29 was structurally incomplete and is not
qualification evidence. Qualification remains separate and non-blocking.
