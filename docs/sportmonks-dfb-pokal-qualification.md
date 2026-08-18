# Sportmonks DFB-Pokal Source Qualification

## Status

**Conditional; read-only live qualification and operator plan approval are
still required.**

Issue #118 evaluates Sportmonks Football API v3 league `109` as the candidate
authority for the 2026/27 DFB-Pokal. Public documentation and deterministic
offline tests support a controlled live observation, but they do not prove
that the operator's account can access the competition, that the current
season is complete, or that any round is removal-capable.

The maximum accepted observation scope remains `partial`. A successful command
must not be interpreted as `complete_round`, `complete_stage`, catalog
implementation, source enablement, staging approval, or release approval.

## Public evidence reviewed on 2026-08-18

### Product and cost

- The Starter plan starts at EUR 29/month when paid monthly or EUR 24/month
  when paid yearly, before any applicable tax.
- Starter permits five operator-selected leagues and advertises 2,000 API
  calls per entity per hour.
- Paid plans include a 14-day trial. Activating the trial requires a payment
  method and it converts to a paid subscription unless cancelled in time.
- Subscriptions renew automatically and processed fees are normally
  non-refundable. Cancellation prevents the next renewal while access
  continues through the current paid period.
- The operator must confirm in MySportmonks that league `109` is selectable
  and included in the active plan. Repository code cannot make that commercial
  choice.

The pricing page and the dedicated rate-limit page currently disagree about
the Growth and Pro per-entity limits. Starter is consistently documented at
2,000. The live response's sanitized `rate_limit` metadata and the operator's
account dashboard must be recorded before any runtime budget is approved.

### Usage, storage, and exit boundary

The public terms allow applications built from returned data and allow
storage/distribution of returned data, but prohibit reselling the Sportmonks
product or raw service. Use is domain-scoped. Logos, images, website material,
and other media are not approved by this qualification.

Sportmonks disclaims guaranteed completeness, accuracy, and availability and
may change its terms. No mandatory attribution wording was found in the public
terms reviewed for this issue. The operator must check the order, dashboard,
and account-specific terms for any attribution or domain-registration
requirement before approval.

Before access ends, retrieval must be disabled and the operator must choose a
qualified replacement or remove Sportmonks-derived Outlook events, mappings,
and retained provider data through a scoped, backed-up procedure. Automatic
cleanup is not authorized by this qualification.

### API contract

- API v3 accepts the token in an `Authorization` header. The qualification
  command deliberately forbids `api_token` in request URLs.
- League lookup uses `/v3/football/leagues/109?include=currentSeason` and
  resolves the season ID from the response rather than accepting free-form
  operator input.
- Fixture lookup uses `/v3/football/fixtures/seasons/{season_id}` with
  `participants`, `stage`, `round`, and `state` includes.
- Fixture pages default to 25 and support at most 50 normal results per page.
  The command requests 50 and follows the provider's `has_more` flag using
  locally constructed page paths.
- Every page consumes a request from its entity-specific limit. League and
  Fixture limits are separate buckets.
- Fixtures expose stable league, season, stage, round, state, fixture, and
  participant IDs. Home and away are taken from `participant.meta.location`,
  never array order.
- Participant `placeholder` and fixture `placeholder` values are retained as
  aggregate evidence. An unscheduled non-placeholder fixture fails closed.
- Provider timestamps are interpreted as UTC only when every response declares
  timezone `UTC`.

## Secret-safe qualification command

Do not run this command until the operator has explicitly confirmed the active
plan, league selection, cost, and trial/renewal implications.

The command is read-only. It does not open SQLite, call Microsoft Graph, create
calendar events, or persist raw provider responses. Enter the token without
echoing it or storing it in command history:

```powershell
$env:SPORTMONKS_API_TOKEN = Read-Host -MaskInput "Sportmonks API token"
try {
    python -m app.operations.sportmonks_qualification
}
finally {
    Remove-Item Env:SPORTMONKS_API_TOKEN -ErrorAction SilentlyContinue
}
```

Review the output locally before sharing it. The report intentionally contains
only:

- the qualification profile, API version, observation timestamp, and fixed
  `partial` scope;
- competition and season identity plus season date boundaries;
- aggregate fixture, participant, page, request, placeholder, and unscheduled
  counts;
- SHA-256 fingerprints of sorted fixture and participant IDs rather than the
  individual IDs;
- UTC kickoff boundaries;
- aggregate state and leg counts;
- stage/round identities, names, counts, and placeholder counts needed to
  review the lifecycle mapping; and
- the minimum sanitized remaining-request value.

It does not emit the API token, authorization header, subscription/account
metadata, raw response, request URL containing a token, individual fixture or
participant IDs, fixture names, or participant names.

## Fail-closed rules

The command rejects the observation before emitting evidence when it sees:

- a missing token or token-bearing request URL;
- an HTTP error, oversized body, non-JSON content type, malformed JSON, or
  non-object response root;
- a non-UTC response timezone;
- the wrong league, sport, current season, season name, or season boundary;
- an inactive competition or already-finished current season;
- an empty season fixture collection;
- an inconsistent page number, page size, page count, empty intermediate page,
  or pagination beyond the safe cap;
- duplicate fixture identity across any page;
- a fixture from another competition or season;
- missing or inconsistent stage, round, or state identity;
- invalid leg syntax;
- missing, duplicate, or ambiguous home/away participants;
- a non-placeholder fixture without a kickoff or a kickoff outside the season;
  or
- malformed or wrong-entity rate-limit metadata.

Normal CI uses synthetic payloads and never calls Sportmonks.

## Required observations and decision gate

1. Confirm the account, selected league `109`, billing interval, price, tax,
   trial end, renewal date, domain boundary, and any account-specific terms.
2. Run the complete command once and retain only its sanitized output.
3. Compare the observed season and first-round schedule with the official DFB
   season plan and round dates.
4. Repeat the complete observation after a meaningful interval. Compare the
   fixture and participant fingerprints, counts, pages, boundaries, stages,
   rounds, legs, placeholders, states, and quota metadata.
5. Keep the source `partial` unless separate evidence proves that one exact
   provider stage or round is complete and stable. A full list of currently
   known fixtures is not a complete cup season.
6. Record the approve/reject decision in a focused ADR and update the Phase 5
   source matrix.
7. Only an approved decision may create a separate DFB-Pokal implementation
   issue.

## Official comparison boundary

The DFB publishes six competition rounds for 2026/27: first round, second
round, round of 16, quarter-finals, semi-finals, and final. The first round is
scheduled for 21-24 August plus 1-2 September 2026, and the final for 29 May
2027. The DFB season plan is the comparison source for known fixtures and
round dates; it is not an automatically retrieved authority in this project.

## Sources

- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms of service](https://www.sportmonks.com/terms-of-service/)
- [Sportmonks authentication](https://docs.sportmonks.com/v3/welcome/authentication)
- [Sportmonks pagination](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/introduction/pagination)
- [Sportmonks rate limits](https://docs.sportmonks.com/v3/api/rate-limit)
- [Sportmonks fixture entity](https://docs.sportmonks.com/v3/endpoints-and-entities/entities/fixture)
- [Sportmonks participant include](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/includes/participants)
- [DFB-Pokal 2026/27 round dates](https://www.dfb.de/maenner/wettbewerbe/dfb-pokal/rahmentermine)
- [DFB-Pokal 2026/27 season plan](https://datencenter.dfb.de/en/competitions/33/seasons/current?datacenter_name=data-center)
