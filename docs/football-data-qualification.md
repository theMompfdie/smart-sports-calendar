# football-data.org Source Qualification

## Premier League status

**Approved with mandatory operating conditions.** `football-data.org` API v4
is the selected authoritative Premier League source for the 2026/27 season.
Public technical and contractual evidence, one complete live qualification,
and two repeat fingerprint-bearing observations passed on 2026-08-09.

The reviewed first-run evidence was:

- API version `v4`, competition code `PL`, competition ID `2021`;
- season ID `2502`, from 2026-08-21 through 2027-05-30;
- 20 distinct teams;
- 380 matches with 380 distinct positive match IDs;
- all 380 matches in `SCHEDULED` status; and
- kickoff coverage from 2026-08-21T19:00:00Z through
  2027-05-30T12:00:00Z.

No token, request header, account identifier, team name, fixture detail, raw
payload, or secret-bearing URL was recorded. The optional remaining-quota
header was not present, so its aggregate value was `null`; the command still
made exactly three read-only requests.

Two later observations, separated by 60 seconds, both reported:

- `match_ids_sha256` =
  `ef4c69d02ca2cef983ed0ec8f2046d6833468c87ed4fd08fdfc54f89ae4fe878`;
- `latest_source_update_utc` = `2026-07-09T01:25:00Z`;
- the same competition, season, 20-team, 380-match, kickoff-boundary, and
  all-`SCHEDULED` aggregates.

This proves stable identity across repeated retrievals without publishing an
individual match ID. The source-update time predates qualification by about one
month, but the season had not started and both complete snapshots were
identical; production freshness must still be monitored per run.

## Premier League public evidence reviewed on 2026-08-09

- The free plan is EUR 0/month, includes fixtures, delayed schedules, and 10
  calls per minute.
- Premier League is one of the competitions explicitly listed in the free
  tier.
- API v4 documents competition code `PL`, numeric competition/team/match IDs,
  UTC `utcDate`, `lastUpdated`, and explicit match statuses.
- Match collection limits accept up to 500 items; the qualification request
  therefore asks for the entire 380-match season in one response and rejects a
  different declared or actual count.
- Response headers expose API version, request reset, and remaining-request
  information. `X-Authenticated-Client` is deliberately excluded from evidence
  because it can identify the account.
- The terms scope an API key to one application, require credential secrecy and
  visible attribution, impose fair use, disclaim availability/accuracy, and
  prohibit referencing obtained football data after subscription cancellation.
- Team crests, logos, and profile images require separate rights and remain out
  of scope.

The required visible attribution is:

> Football data provided by the Football-Data.org API

It must appear in a visible application or operator-facing location before the
provider is enabled in staging or production. The operator accepted this
requirement and the cancellation workflow during qualification.

Before a subscription ends, retrieval must be disabled and the operator must
either re-source every served fixture from an approved replacement or remove
football-data.org-derived events from the Outlook calendar. Provider mappings
and any retained provider-derived data must then be removed through an
explicit, scoped, backed-up operation. No automatic purge is authorized.

## Bundesliga status

**Qualified with mandatory operating conditions; not implemented or
released.** football-data.org API v4 is the selected sole proposed authority
for the 2026/27 German Bundesliga. The live qualification passed on
2026-08-17, authorizing a separate implementation slice but not enabling a
source assignment, import, scheduler, database write, or Outlook operation.

Two complete secret-safe observations at
`2026-08-17T19:58:26.583334+00:00` and
`2026-08-17T20:22:07.312859+00:00`, separated by about 23 minutes and 41
seconds, both reported:

- API version `v4`, competition code `BL1`, and competition ID `2002`;
- season ID `2522`, from 2026-08-28 through 2027-05-22;
- 18 distinct teams;
- 306 matches with 306 distinct positive match IDs;
- 261 `SCHEDULED` and 45 `TIMED` matches;
- kickoff coverage from 2026-08-28T18:30:00Z through
  2027-05-22T13:30:00Z;
- latest source update `2026-08-17T05:20:33Z`;
- one complete match page and three read-only requests; and
- `match_ids_sha256` =
  `034542c2c3c5df368547f2e54108ca4810a68eed44b06860204be0e945c116a9`.

The provider omitted both the optional match-limit echo and remaining-quota
header. Missing limit metadata is accepted only because the request is fixed
to 500 and the qualifier independently proves page size, response count,
total count, unique identities, participants, matchdays, and the complete
double round robin. A present wrong limit still fails closed.

The operator confirmed the active Free plan with its documented limit of 10
requests per minute. No token, account identifier, header, team name, fixture
detail, individual match ID, raw payload, or secret-bearing URL was retained.

## Bundesliga public evidence reviewed on 2026-08-17

- Bundesliga is explicitly included in football-data.org's free-tier coverage.
- API v4 identifies the competition as code `BL1` and numeric ID `2002`.
- The official 2026/27 Bundesliga fixture announcement confirms 18 clubs, 34
  matchdays, and 306 fixtures.
- The documented match collection limit is 500, so a complete 306-match season
  fits in one response. The qualifier nevertheless supports and validates
  pagination rather than relying on that assumption.
- The public pricing page lists 10 requests per minute for the free plan. Where
  public provider pages disagree about a paid-plan limit, operation must use
  the lower documented limit until the provider clarifies it.
- The credential, attribution, fair-use, cancellation, and media-rights
  conditions documented for Premier League use apply unchanged.

The approved initial Bundesliga polling interval is six hours. At four
snapshots per day and normally three requests per complete snapshot, that is
12 requests per day with a three-request burst. Against the documented free
plan limit of 10 requests per minute, one immediate complete retry would still
leave four requests of per-minute headroom. Both live observations confirmed
three requests. The quota header was absent, so the operator separately
confirmed only the sanitized Free-plan name and 10-request-per-minute limit.

## Secret-safe live qualification commands

The repository includes a read-only command with curated profiles for Premier
League and Bundesliga. It makes two metadata requests plus one or more paged
match requests. With the current expected season sizes, each profile normally
makes exactly three requests. Free-form competition IDs and expected counts
are deliberately unsupported.

The command emits only the qualification profile, observation time, aggregate
identifiers, counts, pagination/request counts, UTC boundaries, status counts,
API version, a SHA-256 fingerprint of the sorted match IDs, the latest
source-update timestamp, and the minimum remaining request count. It never
emits the API token, raw body, authorization header, account identifier, team
names, individual match IDs, or fixture details.

In PowerShell, enter the token without echoing it or storing it in shell
history. For the already approved Premier League profile:

```powershell
$env:FOOTBALL_DATA_API_KEY = Read-Host -MaskInput "football-data.org API token"
python -m app.operations.football_data_qualification --competition premier-league --season 2026
Remove-Item Env:FOOTBALL_DATA_API_KEY
```

For Bundesliga requalification, run the following command once, review the
output locally, wait at least 60 seconds, and repeat the complete command. The
`finally` block removes the token after each observation, including failures:

```powershell
$env:FOOTBALL_DATA_API_KEY = Read-Host -MaskInput "football-data.org API token"
try {
    python -m app.operations.football_data_qualification --competition bundesliga --season 2026
}
finally {
    Remove-Item Env:FOOTBALL_DATA_API_KEY -ErrorAction SilentlyContinue
}
```

The command fails closed unless it observes:

- API version `v4` on every response;
- the selected profile's exact competition code and ID;
- a current season starting in 2026 with valid start and end dates;
- the selected profile's exact distinct-team and match counts;
- complete offset-based pagination without overlaps or gaps;
- distinct positive match IDs;
- a deterministic SHA-256 fingerprint over the sorted match IDs;
- the same competition and season identity on every match;
- two distinct known participants on every match;
- a complete double round-robin schedule with one appearance per team per
  matchday and exactly one match in each directed pairing;
- stage `REGULAR_SEASON` and the selected profile's exact matchday range;
- UTC `utcDate` and `lastUpdated` values; and
- only the documented supported status vocabulary; and
- a source-update age within the profile-independent freshness policy.

The curated invariants are:

| Profile | Code | ID | Teams | Matches | Matchdays |
| --- | --- | ---: | ---: | ---: | ---: |
| `premier-league` | `PL` | 2021 | 20 | 380 | 38 |
| `bundesliga` | `BL1` | 2002 | 18 | 306 | 34 |

Premier League output belongs to issue #79 and Bundesliga output belongs to
issue #110, in both cases only after manual review. The token, raw response,
request headers, account dashboard, and `.env` contents must never be copied
into GitHub.

## Approved operating conditions

- Absence becomes removal evidence only after two complete, successful
  authoritative snapshots for the selected profile: 380 Premier League
  matches or 306 Bundesliga matches. A filtered, short, stale, empty,
  malformed, failed, or wrong-scope response is never authoritative.
- Visible attribution is mandatory while provider-derived data is served.
- Credentials remain in the operator secret store and never enter GitHub,
  logs, screenshots, run metadata, or test artifacts.
- Normal CI uses synthetic payloads only. The public terms do not provide a
  sufficiently explicit license for committing copied live response fixtures.
- The free tier's delayed schedules are acceptable for the calendar use case;
  every run must still retain last-known-good state on failure or staleness.
- Missing optional quota headers are allowed. The scheduler must enforce the
  documented plan limit independently and classify HTTP 429 as retryable.
- Cancellation requires the scoped re-source-or-remove procedure above before
  provider-derived data may continue to be served.

These conditions qualify both curated profiles. Qualification is not
implementation: Bundesliga must remain disabled until a separate issue adds
and validates its catalog, mappings, adapter path, scheduler isolation,
SQLite-to-Graph behavior, attribution, and staging evidence.

## Sources

- [Pricing](https://www.football-data.org/pricing)
- [Coverage](https://www.football-data.org/coverage)
- [Terms and privacy](https://www.football-data.org/about)
- [API v4 resources](https://docs.football-data.org/general/v4/resources.html)
- [Competition resource](https://docs.football-data.org/general/v4/competition.html)
- [Match resource and lifecycle](https://docs.football-data.org/general/v4/match.html)
- [API policies and throttling](https://docs.football-data.org/general/v4/policies.html)
- [Lookup tables and response headers](https://docs.football-data.org/general/v4/lookup_tables.html)
- [Errors](https://docs.football-data.org/general/v4/errors.html)
- [Official 2026/27 Bundesliga fixture announcement](https://www.bundesliga.com/en/bundesliga/news/2026-27-fixture-lists-now-available-38068)
