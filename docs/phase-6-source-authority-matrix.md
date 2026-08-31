# Phase 6 Source and Authority Matrix

## Status and decision boundary

This matrix tracks the five candidate competitions in Phase 6 master issue
 #150. It is initialized by the UEFA Champions League source qualification in
 #154 and must be extended one competition at a time through the corresponding
competition tracker.

Evidence was first reviewed on 2026-08-28, extended to the Europa League,
Conference League, and Nations League on 2026-08-29, and updated with the
Champions League readiness observation and Nations League authority decision
on 2026-08-30. The OpenLigaDB Champions League league-phase authority was
qualified and staged on 2026-08-31, and the Europa League was deferred after
fresh zero-cost availability checks on the same day. The Conference League
was also deferred on 2026-08-31 because no zero-cost 2026/27 source was
available and no recurring paid plan was approved. EURO 2028 qualification
remains deferred to its December 2026 milestone. Provider coverage,
terms, plans, competition formats, and season data can change. Every outcome
requires a dated competition-specific qualification record before
implementation.

The operator requires the selected UEFA Champions League fixture source to
cost EUR 0. Free registration and a free API credential are permitted. This
constraint is recorded for the Champions League track only; later competition
tracks must record their own operator boundary rather than infer one.

For the Europa League, the operator approved a possible 2026/27 boundary from
the league phase through the final, but deferred the competition from
`v0.6.0-beta.1` on 2026-08-31. OpenLigaDB remained severely incomplete and a
free football-data.org credential received HTTP 403 for `EL` / 2146. A
separate Footballdata.io free account includes UEL and exposes the current
season, but currently contains only qualifying/play-off fixtures. It remains
the preferred zero-cost re-evaluation candidate. No paid provider is approved.

The same main-boundary rule applies to the Conference League: league phase
through final may be evaluated without requiring qualification. The operator
deferred this competition from `v0.6.0-beta.1`; no provider or recurring-cost
boundary is selected, and no zero-cost 2026/27 automated candidate is
currently observable.

For the Nations League, the active edition is 2026/27. The operator selected
the zero-cost OpenLigaDB League A group-phase authority on 2026-08-30 after two
stable technical observations and an exact manual UEFA comparison. The release
boundary is exactly 48 fixtures and 16 participants; every other league and
later stage remains excluded.

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
| UEFA Champions League | 2026/27 | Qualified | OpenLigaDB `ucl` / 4946, free and credential-free | Sole bounded league-phase authority when explicitly enabled | Exactly 144 league-phase fixtures and 36 participants; qualifying and all knockout stages excluded | [Champions League qualification](uefa-champions-league-source-qualification.md) |
| UEFA Europa League | 2026/27 | Deferred | Footballdata.io free plan is the preferred re-evaluation candidate but its league phase is not ready; OpenLigaDB remains incomplete | Unassigned; runtime and release inclusion disabled | Excluded from `v0.6.0-beta.1`; league phase through final remains the future candidate boundary | [Europa League qualification](uefa-europa-league-source-qualification.md) |
| UEFA Conference League | 2026/27 | Deferred | No zero-cost 2026/27 candidate currently exists; Sportmonks league 2286 and football-data.org `UCL` / 2154 remain paid future alternatives | Unassigned; runtime and release inclusion disabled | Excluded from `v0.6.0-beta.1`; league phase through final remains the future candidate boundary | [Conference League qualification](uefa-conference-league-source-qualification.md) |
| UEFA Nations League | 2026/27 | Qualified | OpenLigaDB `nla` / 5978, free and credential-free; selected 2026-08-30 | Sole bounded League A group-phase authority when explicitly enabled | Exactly 48 League A group-phase fixtures and 16 participants; B/C/D and all later stages excluded | [Nations League qualification](uefa-nations-league-source-qualification.md) |
| UEFA European Championship Qualification | EURO 2028 cycle | Deferred | Re-evaluate after the 6 December 2026 draw | Unassigned; runtime and release inclusion disabled | Excluded from `v0.6.0-beta.1`; tracked by the December 2026 milestone | [Delivery track #176](https://github.com/theMompfdie/smart-sports-calendar/issues/176) |

## Champions League candidate summary

| Candidate | Cost fit | Technical fit | Rights/terms fit | Current decision |
| --- | --- | --- | --- | --- |
| Official UEFA public pages and regulations | Free | No documented automation contract or stable machine fixture identity | Authoritative manual evidence only | Manual verification; not an automated writer |
| OpenLigaDB `ucl` / 4946 | Free and credential-free | Two stable 144-fixture/36-team observations; exact eight-matchday structure and official UEFA date boundary | ODbL attribution applies; community-maintained rather than official | Selected authority for the league phase only; permanently removal-disabled |
| football-data.org `CL` / 2001 | Free registration and free tier | Correct 2026/27 season and 36 teams observed; fixture collection still empty on 2026-08-30 | One-application use, secret key, attribution, cancellation exit obligation | Verification or future explicit alternative; not the selected writer |
| football-data.org `CLQ` / 2174 | Paid tier | Separate qualification competition | Same football-data.org terms | Rejected by zero-cost constraint |
| API-Football | Free registration, 100 requests/day | Broad technical coverage and existing transport | Provider grants no competition-data licence; UEFA permission not recorded | Rejected as authority under current evidence |
| Sportmonks | Champions League requires paid plan | Strongest documented hybrid lifecycle model | Paid plan terms would require separate acceptance | Rejected by zero-cost constraint |

## Europa League candidate summary

| Candidate | Cost fit | Technical fit | Rights/terms fit | Current decision |
| --- | --- | --- | --- | --- |
| Official UEFA public pages and regulations | Free | No documented automation contract or stable machine fixture identity | Authoritative manual evidence; automated collection prohibited | Manual verification only |
| Footballdata.io league 46 / season 90443 | Free account, UEL included, observed limit 2,000 requests/month | Current season and stable-looking numeric IDs are exposed, but only 80 completed qualifying/play-off fixtures and zero league-phase-window fixtures were available on 2026-08-31; new adapter required | Free attribution required; reasonable caching allowed; long-term storage, third-party rights, cancellation, and availability need explicit acceptance | Preferred zero-cost re-evaluation candidate; not ready for `v0.6.0-beta.1` |
| OpenLigaDB `uel2026` / 6000 | Free and credential-free | Existing adapter and stable-looking IDs, but the 2026-08-31 re-observation still exposed only 16 fixtures, 15 participants, and incomplete round structure | ODbL attribution applies; community-maintained rather than official | Not ready; reconsider only after a complete stable observation and keep removal disabled if later selected |
| football-data.org `EL` / 2146 | Standard plan, currently EUR 49/month | Existing integration; main competition cleanly separated from `ELQ` / 2183; the authenticated free catalog omitted `EL` and direct access returned HTTP 403 on 2026-08-31 | One-application use, secret key, attribution, and cancellation exit obligation | Not available at zero cost; no paid plan approved |
| Sportmonks league 5 | Starter from EUR 29/month; card-backed trial | Strongest documented full hybrid lifecycle; new adapter required | Subscription/domain terms, no raw resale, completeness disclaimer, separate media rights | Paid conditional candidate pending operator approval and live evidence |
| API-Football | Free registration, 100 requests/day | Broad technical coverage and existing transport | Provider grants no competition-data licence; UEFA permission not recorded | Rejected as authority under current evidence |

## Conference League candidate summary

| Candidate | Cost fit | Technical fit | Rights/terms fit | Current decision |
| --- | --- | --- | --- | --- |
| Official UEFA public pages and regulations | Free | No documented automation contract or stable machine fixture identity; final league-phase calendar still propagating | Authoritative manual evidence; automated collection prohibited | Manual verification only |
| OpenLigaDB | Free and credential-free | Existing adapter, but no 2026/27 Conference League entry was present on 2026-08-29 | ODbL would apply; community-maintained rather than official | Reconsider only if a stable 2026/27 entry appears |
| football-data.org `UCL` / 2154 | Pro plan, currently EUR 199/month | Existing integration; main competition separated from `COLQ` / 2185; public catalog still exposes 2025/26 | One-application use, secret key, attribution, and cancellation exit obligation | Paid conditional candidate pending operator approval and live evidence |
| Sportmonks league 2286 | Starter from EUR 29/month; card-backed trial | Strongest documented qualification-through-final lifecycle; new adapter required | Subscription/domain terms, no raw resale, completeness disclaimer, separate media rights | Preferred paid technical candidate pending operator approval and live evidence |
| API-Football | Free registration, 100 requests/day | Broad technical coverage and existing transport | Provider grants no competition-data licence; UEFA permission not recorded | Rejected as authority under current evidence |

## Nations League candidate summary

| Candidate | Cost fit | Technical fit | Rights/terms fit | Current decision |
| --- | --- | --- | --- | --- |
| Official UEFA public pages and regulations | Free | Complete manual 2026/27 league-phase fixture evidence; no stable machine contract | Authoritative manual evidence; automated collection prohibited | Manual verification only |
| OpenLigaDB `nla` / 5978 | Free and credential-free | Two stable 48-fixture/16-team observations and exact manual UEFA pairing/kickoff match; later rounds remain excluded | ODbL accepted for the bounded private-calendar use; community-maintained rather than official | Selected authority for League A group phase only; implementation #170 |
| OpenLigaDB `unl` / 4955 | Free and credential-free | Zero fixtures and zero participants despite a current catalog entry | Same OpenLigaDB conditions | Rejected as current all-leagues or removal evidence |
| football-data.org `UNL` / 2182 | Pro plan, currently EUR 199/month | Existing integration; public season 2507 covers the 2026 league phase | One-application use, secret key, attribution, and cancellation exit obligation | Paid conditional candidate pending scope approval and live evidence |
| Sportmonks season 27797 | Starter from EUR 29/month; card-backed trial | Documents all four leagues and exactly 156 league-phase fixtures; new adapter required | Subscription/domain terms, no raw resale, completeness disclaimer, separate media rights | Preferred paid full-league-phase candidate pending operator approval |
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

On 2026-08-31 OpenLigaDB `ucl` / 4946 passed the zero-cost, technical,
structural, identity, and official-comparison gates for exactly the 2026/27
league phase. It replaces the earlier conditional football-data.org path as
the selected writer. Qualifying and every knockout stage remain excluded.

## Champions League staging outcome

Isolated staging on 2026-08-31 imported 144 UCL fixtures and converged to 144
synchronized Outlook mappings, one calendar target, and zero pending
revisions. Subsequent calendar cycles performed no Graph writes. Deterministic
SQLite-to-mocked-Graph coverage proves restart, reschedule, provider
failure/recovery, attribution, and non-destructive omission behavior. The
reused staging database retained 272 already-tested Phase 7 NFL records; this
explained the global candidate-count difference without violating any UCL
scope invariant. The operator accepted the UCL release evidence.

## Europa League operator decision and re-evaluation gate

On 2026-08-29 the operator approved a candidate boundary beginning with the
league phase. Separately exposed qualification may be evaluated later and does
not block the main track. On 2026-08-31 OpenLigaDB still exposed only 16 of 144
required league-phase fixtures and 15 of 36 participants, while a configured
free football-data.org credential received HTTP 403 for `EL` / 2146. The
separate Footballdata.io free plan includes UEL and exposes season 90443 /
20262027, but currently contains 80 completed qualifying/play-off fixtures and
zero fixtures in the league-phase date window. The operator therefore deferred
Europa League from `v0.6.0-beta.1`; Footballdata.io remains the preferred
zero-cost re-evaluation candidate, but no provider or authority is approved.

The Europa League track cannot resume credentialed-validation or implementation
work until:

1. Footballdata.io publishes the complete league-phase boundary, or the
   operator selects another acceptable provider and exact recurring-cost
   boundary;
2. the selected main competition exposes the 2026/27 league-phase schedule;
3. two sanitized observations prove 36 participants, 144 league-phase
   fixtures, stable identity, structure, pagination, update behavior, and
   reproducible fingerprints; and
4. selected-provider terms, attribution, persistence, cancellation, and secret
   handling are accepted explicitly.

The Footballdata.io and OpenLigaDB observations on 2026-08-31 were
structurally incomplete and are not qualification evidence. Qualification
remains separate and non-blocking.

## Conference League operator decision and re-evaluation gate

The operator-approved UEFA club-competition boundary permits a future 2026/27
Conference League track to begin with the league phase. Qualification is a
separate optional scope and cannot supply cross-scope removal evidence. On
2026-08-31 the operator deferred the competition from `v0.6.0-beta.1`: no
provider, paid plan, trial, registration, authority, or runtime is approved.

The Conference League track cannot create credentialed-validation or
implementation work until:

1. the finalized UEFA league-phase calendar has propagated;
2. the operator selects an acceptable source and recurring-cost boundary:
   wait for a credible OpenLigaDB entry at EUR 0, approve Sportmonks at the
   then-current price, or approve football-data.org at the then-current price;
3. the selected main competition exposes the 2026/27 season and two sanitized
   observations prove 36 participants, 108 league-phase fixtures, stable
   identity, structure, pagination, update behavior, and reproducible
   fingerprints; and
4. selected-provider terms, attribution, persistence, cancellation, and secret
   handling are accepted explicitly.

No 2026/27 OpenLigaDB competition existed on 2026-08-29, and both reviewed API
paths require payment. Qualification remains separate and non-blocking.

## Nations League operator decision and required next gate

On 2026-08-30 the operator selected OpenLigaDB `nla` / 5978 at EUR 0 for only
the League A group phase and accepted its ODbL conditions. Issue #170 owns the
catalog, mapping, runtime, lifecycle, tests, attribution, documentation, and
isolated-staging work. Runtime assignment remains opt-in configuration.

The implementation must preserve the exact four-group, 48-fixture,
16-participant contract and permanent removal-disabled behavior. Leagues B, C,
D, later play-offs, and finals need independent qualification and cannot reuse
this authority implicitly. OpenLigaDB `unl` / 4955 remains empty and cannot
provide completeness or removal evidence. Paid plans, trials, and automatic
fallback writers remain unapproved.
