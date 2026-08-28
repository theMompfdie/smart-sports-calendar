# ÖFB-Cup Source Qualification

## Status

**Qualified by ADR 0010 for private, non-destructive `partial` observations
from the official ÖFB iCalendar feed.**

Issue #128 evaluates one permitted authoritative source for the 2026/27
ÖFB-Cup. SMART Sports Calendar is a hobby project, so the official no-cost
calendar is preferred over paid aggregators even though it requires a new,
bounded iCalendar provider integration.

Qualification assigns the official ÖFB calendar as the only proposed
authoritative writer for `oefb_cup` / `2026_27`. It does not implement or
enable the source. A separate issue must add the adapter, catalog, reviewed
mappings, source job, tests, and isolated staging proof before any release
claim.

## Competition lifecycle boundary

The ÖFB-Cup has 64 participants and six single-match knockout rounds. Draws
publish later rounds incrementally. The 2026/27 first round contains 32
fixtures and the second round contains 16 fixtures; later participants and
fixtures are not yet known.

The official calendar is therefore not a complete-season snapshot. Its maximum
qualified scope is permanently `partial` under this decision. Observations may
create and update known fixtures but absence may never cancel or remove a
canonical or Outlook event. A future `complete_round` decision requires a new
qualification and ADR with provider-side completeness evidence.

## Official ÖFB calendar

The public ÖFB-Cup page offers a `Spielkalender` subscription for the complete
competition and for individual teams. The competition selector resolves to
public competition ID `232362`, title `UNIQA ÖFB Cup`, and the 2026/27 season.
The page currently exposes 64 participating teams, 32 first-round fixtures,
and the published second-round boundary.

The browser flow creates a public `webcal` subscription through an ÖFB-owned
endpoint. The returned calendar is served as `text/calendar` from
`www.fussballoesterreich.at` and declares `X-PUBLISHED-TTL:PT6H`. The feed is
therefore explicitly designed for automatic calendar refresh rather than HTML
scraping.

The generated subscription URL contains an opaque identifier. It is treated as
a deployment secret even though no account or API key is required. The
operator must create it manually through the public ÖFB calendar control and
supply the HTTPS form through the deployment secret store. The application
must not call the subscription-creation endpoint during startup or polling.

The public ÖFB privacy notice does not grant a general redistribution license.
This approval is consequently limited to the operator's private,
non-commercial calendar synchronization. Raw feed redistribution, public
fixture databases, logos, images, and commercial reuse are not approved. A
materially public deployment requires a new rights review or written ÖFB
permission.

## Secret-safe live evidence

Two complete read-only observations were performed on 2026-08-28 at
13:36:25 UTC and 13:38:51 UTC, separated by about two minutes and 26 seconds.
Both reported:

- HTTP 200 and one valid `VCALENDAR` served as `text/calendar`;
- 111 `VEVENT` components with 111 unique numeric seven-digit `UID` values;
- a 47,380-byte response whose body length matched `Content-Length`;
- identical UID fingerprint
  `29c31e86b302769b3a8515e253a69c843a8c8c8c40d4a09080597e334cb1cbc1`;
- dates from 2025-07-25 through 2026-09-06;
- 63 prior-season events and 48 currently published 2026/27 events;
- 32 current `round-1` and 16 current `round-2` fixtures;
- 96 populated participant references resolving to 64 unique numeric
  participant identities across those current fixtures;
- one UTC `DTSTART` and `DTSTAMP` per event;
- one `SUMMARY`, `DESCRIPTION`, `LOCATION`, `URL`, `DURATION`, `X-CATEGORY`,
  home identity, and away identity per event;
- present but consistently blank `X-HOMEABC` and `X-AWAYABC` hint fields;
- no recurrence rules or recurrence instances; and
- the six-hour publication TTL.

The feed exposed `Last-Modified`; a request using `If-Modified-Since` returned
HTTP 304. It exposed no `ETag`. The implementation can therefore avoid parsing
an unchanged body, but a 304 response only reuses the previously validated
snapshot identity and is not a new observation or removal signal.

All 95 events that already exposed an official match-report ID used that same
numeric value as the iCalendar `UID`. The remaining 16 future second-round
events already had unique numeric UIDs before match-report URLs were present.
This establishes provider-issued fixture identity independently of mutable
titles, teams, kickoff times, venues, and report URLs.

The feed contained no `STATUS`, `SEQUENCE`, `LAST-MODIFIED`, or `CREATED`
properties. `DTSTAMP` is an update hint only. Event links consistently used
HTTPS on `www.oefb.at` below `/cup`, with query parameters and no fragments.
Current summaries consistently separated the two display names with ` : `.
Content comparison by stable UID is mandatory, explicit cancellation is
unavailable, and missing events cannot be interpreted destructively.

No subscription URL, raw payload, fixture list, venue, result, or account value
is retained in this repository or GitHub tracking. Qualification evidence
contains only approved aggregates, boundaries, timestamps, and a SHA-256
identity fingerprint. The implementation catalog contains only the reviewed
64 public team identities and provider mappings required for deterministic
correlation.

## Required implementation contract

The follow-up implementation must satisfy all of these rules:

1. Configure one operator-created HTTPS subscription URL only through a secret
   environment variable. Redact the complete URL from logs, exceptions, run
   metadata, tests, screenshots, issues, and pull requests.
2. Allowlist the final official feed host, reject user information, query
   strings, fragments, non-HTTPS redirects, and redirects outside
   `www.fussballoesterreich.at`.
3. Use a maintained RFC 5545 parser rather than a handwritten parser. Pin and
   review the dependency through the normal lock and security process.
4. Enforce a maximum two-MiB response and 256 events, one `VCALENDAR`, a
   non-empty current-season subset, unique non-empty UIDs, UTC `DTSTART`,
   supported properties, and no `RRULE` or `RECURRENCE-ID`.
5. Filter the multi-season feed to the explicit canonical 2026/27 season date
   window before normalization. Historical events remain outside persistence.
6. Use exact `UID` as fixture identity. Resolve home and away identities from
   the structured ÖFB fields and a reviewed 64-team mapping; never correlate
   by title, kickoff, or fuzzy name matching.
7. Parse the documented round text into `round-1` through `round-6` and reject
   an unknown, missing, contradictory, or out-of-range round.
8. Keep every observation `partial`, `complete=false`, and removal-ineligible.
   Missing, empty, reduced, malformed, stale, oversized, ambiguous, or failed
   observations preserve last-known-good state.
   The accepted current-season UID set may grow as draws are published, but it
   must never shrink or replace an identity automatically.
9. Update mutable fixture content only when the same UID remains mapped to the
   same competition and participants. A participant identity change must fail
   closed until explicitly reviewed.
10. Poll no more frequently than the feed's six-hour TTL, use conditional HTTP
    requests when supported, apply bounded retries, and isolate job failures.
11. Ignore logos and images. Render transparent source attribution in the
    Outlook event body:

    > Fixture data provided by the Austrian Football Association (ÖFB):
    > <https://www.oefb.at/cup>

12. Prove deterministic import, unchanged-cycle idempotency, restart recovery,
    provider-failure isolation, secret redaction, and SQLite-to-mocked-Graph
    behavior in credential-free tests before isolated staging.

## Candidate review

### Official HTML and internal data services

The public cup page is the manual verification reference. Its embedded page
model and internal JSON services are not selected as production sources.
Automated HTML scraping and undocumented private endpoints remain excluded.
Only the explicitly offered iCalendar subscription is approved.

### OpenLigaDB

A secret-free review of the current league directory found no 2026/27
ÖFB-Cup competition. Historical Austrian league records do not provide cup
identity, fixtures, rounds, or participants for this scope.

### football-data.org

football-data.org lists Austrian Cup ID `2027` without a competition code on
the Pro tier, while the reviewed public catalog remains stale at 2020/21. No
paid plan was approved and current 2026/27 coverage is not established.

### Sportmonks

Sportmonks documents Austrian Cup league `187` with strong fixture, season,
stage, round, participant, state, and pagination capabilities. Its permanent
free plan does not include the competition; the Starter plan begins at EUR 29
per month for selected leagues. The official no-cost ÖFB feed makes this paid
candidate unnecessary for the current private scope.

### TheSportsDB

TheSportsDB identifies Austrian Cup league `5883` and season `2026-2027`, but
the free V1 season response returned only 15 events while the official first
round contains 32. The free endpoint has no pagination for the missing events;
the V2 full schedule requires a paid key. It cannot establish a complete
current observation.

### API-Football

API-Football offers broad technical coverage and a limited free plan, but its
terms leave competition data permissions with the customer. No ÖFB-specific
written clearance is recorded. Existing legacy mappings do not authorize a
new ÖFB-Cup writer.

### OpenFootball datasets

OpenFootball publishes CC0 Austrian datasets and includes historical ÖFB-Cup
files, but the current repository ends at `2025-26/cup.txt`. It has no 2026/27
schedule, provider-issued stable fixture identities, or authoritative update
contract.

## Revalidation triggers

Reopen qualification when any of these conditions changes:

- the ÖFB removes or materially changes the competition calendar service;
- the feed host, URL-generation flow, fields, UID behavior, TTL, season window,
  round format, participant identity, or terms change;
- a fixture UID is replaced or reassigned across a schedule update;
- explicit cancellation or postponement semantics become available;
- public redistribution or commercial use is proposed; or
- the operator wants to promote the source beyond permanent `partial` scope.

## Sources

- [Official ÖFB-Cup page](https://www.oefb.at/cup)
- [ÖFB privacy notice](https://www.oefb.at/datenschutz)
- [OpenLigaDB API](https://api.openligadb.de/)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [Sportmonks football coverage](https://www.sportmonks.com/football-api/coverage/)
- [Sportmonks free plan](https://www.sportmonks.com/football-api/free-plan/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [TheSportsDB API guide](https://www.thesportsdb.com/docs_api_guide)
- [TheSportsDB pricing](https://www.thesportsdb.com/docs_pricing.php?billing=annual)
- [TheSportsDB terms](https://www.thesportsdb.com/docs_terms_of_use.php)
- [API-Sports terms](https://api-sports.io/terms)
- [OpenFootball Austria repository](https://github.com/openfootball/austria)
