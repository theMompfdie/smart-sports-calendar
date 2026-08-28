# ADR 0008: Select football-data.org for the Championship regular season

- Status: Accepted
- Date: 2026-08-19
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #104, #108, #123
- Follows: ADR 0005
- Complements: ADR 0004
- Supersedes in part: ADR 0005's conditional Championship gate
- Does not authorize: implementation, live staging, release, or production use

## Context

The 2026/27 EFL Championship consists of a complete 24-team, 46-matchday,
552-fixture regular season followed by a revised seven-fixture play-off. The
regular-season schedule is known in advance, while play-off participants and
fixtures become known progressively after the league table is complete.

football-data.org API v4 lists the Championship in its Free plan as competition
`ELC` / 2016. The official EFL website offers fixture pages and end-user
calendar synchronization, but no sufficiently documented automated retrieval,
stable-identity, or completeness contract was found. API-Football remains
ineligible as a new authority without written competition-specific rights
clearance. Sportmonks requires a paid provider choice and was not selected for
this regular-season scope.

The provider documents match filters, a maximum result limit of 500, offset
pagination, typed stages, UTC kickoffs, statuses, and stable-looking numeric
resource identifiers. Public coverage and documentation alone could not prove
whether the regular season and play-offs form one stable provider scope.

## Decision

Select football-data.org API v4 competition `ELC` / 2016 as the sole proposed
authoritative writer for the 2026/27 Championship `REGULAR_SEASON` stage,
subject to every condition in this ADR and the qualification record.

Use the ADR 0004 `complete_stage` lifecycle scope for the exact 552-match
regular-season double round robin. The seven Championship play-off fixtures
are explicitly excluded. They remain a separate, unqualified, progressive,
non-destructive scope until later live evidence and a follow-up decision prove
their identity and lifecycle contract.

Two operator-controlled, read-only observations at
`2026-08-19T16:22:19.452504+00:00` and
`2026-08-19T16:24:32.575705+00:00` were separated by about two minutes and 13
seconds. Both independently reported:

- API version `v4`, competition ID `2016`, code `ELC`, and season ID `2509`;
- season dates 2026-08-14 through 2027-05-01;
- 24 distinct teams and 552 distinct positive match IDs;
- matchdays 1 through 46, all with stage `REGULAR_SEASON`;
- 12 `FINISHED`, 276 `TIMED`, and 264 `SCHEDULED` matches;
- identical kickoff boundaries and latest source-update timestamp;
- one complete match response and three requests; and
- SHA-256 fixture-identity fingerprint
  `9fdf11360da92e14748234d2ab2a37a79b6176adf9e756e54d19b129a21e1842`; and
- SHA-256 participant-identity fingerprint
  `b73d761a2a6f382be662cce9377af728c503a99cd322ca1eccb8b0e846812de9`.

The provider returned all 552 matches in one response despite a requested
limit of 500. Its stage-filter metadata was not a reliable scalar echo. The
qualification contract therefore treats response filter echoes as diagnostics,
not completeness evidence. It independently validates every match stage,
identity, participant, matchday, directed pairing, UTC timestamp, status, and
source update.

An exact 552-match first response is accepted within the configured response
byte limit. Validated `500 + 52` offset pagination remains supported if the
provider starts honoring the documented limit. Any other oversized,
incomplete, duplicate, stale, malformed, or wrong-scope response fails closed.

The Free plan is operator-confirmed at 10 requests per minute. A current
observation uses three requests. The optional remaining-quota header was absent
and must not replace independent client-side throttling.

Qualification authorizes creation of a separate implementation issue. It does
not create catalog records, participant mappings, source assignments, jobs,
database writes, Outlook events, staging approval, or a release claim.

## Mandatory conditions

- Keep exactly one authoritative source assignment for Championship season
  2026/27. Alternatives may be verification sources only, never simultaneous
  writers or automatic failover.
- Bind authoritative completeness and any later removal decision to the exact
  `REGULAR_SEASON` `complete_stage` scope with 24 teams, 46 matchdays, and 552
  unique fixtures.
- Require complete schedule validation on every authoritative observation.
  Any failed, empty, partial, stale, malformed, ambiguous, throttled, or
  wrong-scope response preserves last-known-good state.
- Treat the seven play-off fixtures as unqualified and non-destructive. Their
  absence can never cancel or delete a regular-season or play-off event.
- Support both the observed exact 552-match response and validated `500 + 52`
  pagination without accepting any other page-limit violation.
- Enforce the Free-plan limit independently, classify HTTP 429 as retryable,
  and use bounded backoff without overlapping source jobs.
- Display `Football data provided by the Football-Data.org API` visibly while
  provider-derived data is served.
- Keep credentials in the operator-controlled secret store and out of source,
  logs, evidence, screenshots, issues, CI, and URLs.
- Use synthetic test payloads unless explicit fixture-reuse permission is
  obtained. Do not import logos, crests, photos, or separately protected media.
- Before subscription cancellation takes effect, disable retrieval and either
  qualify a replacement or remove derived Outlook events and retained
  provider-derived data through a scoped, backed-up operator procedure.
- Revalidate coverage, identity, stage boundaries, completeness, plan, quota,
  terms, and attribution before staging and after material provider or season
  changes.

## Consequences

- A focused Championship regular-season implementation issue may now be
  created under #104.
- Existing football-data.org infrastructure can be reused, but the runtime
  adapter must implement the observed complete-response behavior and retain
  safe offset-pagination support.
- Play-off support cannot be included silently in the implementation issue or
  release claim. It needs separate qualification once stable fixtures exist.
- No database migration is approved by this decision. The implementation must
  prove whether the existing catalog, lifecycle-scope, and source-mapping
  schema are sufficient.
- The Championship remains qualified but not implemented, staged, or released
  until its separate delivery and validation gates pass.

## Alternatives considered

### Treat the complete provider season as one 559-match scope

Rejected because the seven play-off fixtures are not present and their
participants are unknown. Their future identity and insertion behavior cannot
be inferred from the complete regular-season schedule.

### Require documented pagination before qualification

Rejected as the only permitted path because the live endpoint returned one
internally complete 552-match response despite the documented 500-item limit.
The exact count, unique identities, matchdays, pairings, and stages provide a
stronger completeness proof than the non-authoritative filter echo. Documented
pagination remains a required compatibility path.

### Use the official EFL website or calendar synchronization

Rejected as an automated authority because no sufficiently documented
machine-readable retrieval, stable-identity, and completeness contract was
found. It remains suitable for manual verification.

### Select API-Football or Sportmonks

API-Football is rejected without written competition-specific rights
clearance. Sportmonks was not selected because it requires a paid choice and a
new adapter without improving the qualified regular-season scope.

Detailed evidence and operating constraints are recorded in
[`../football-data-qualification.md`](../football-data-qualification.md).
