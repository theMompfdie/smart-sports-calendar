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

## Championship regular-season status

**Qualified for the 2026/27 `REGULAR_SEASON` stage with mandatory operating
conditions; play-offs remain unqualified.** football-data.org API v4 is the
selected sole proposed authority for the 552-match Championship regular
season. The live qualification passed on 2026-08-19, authorizing a separate
implementation issue but not enabling a source assignment, import, scheduler,
database write, removal decision, or Outlook operation.

Two complete secret-safe observations at
`2026-08-19T16:22:19.452504+00:00` and
`2026-08-19T16:24:32.575705+00:00`, separated by about two minutes and 13
seconds, both reported:

- API version `v4`, competition code `ELC`, and competition ID `2016`;
- season ID `2509`, from 2026-08-14 through 2027-05-01;
- 24 distinct teams;
- 552 matches with 552 distinct positive match IDs;
- all 552 matches in `REGULAR_SEASON` across matchdays 1 through 46;
- 12 `FINISHED`, 276 `TIMED`, and 264 `SCHEDULED` matches;
- kickoff coverage from 2026-08-14T19:00:00Z through
  2027-05-01T00:00:00Z;
- latest source update `2026-08-19T05:20:30Z`;
- one complete match response and three read-only requests; and
- `match_ids_sha256` =
  `9fdf11360da92e14748234d2ab2a37a79b6176adf9e756e54d19b129a21e1842`; and
- `team_ids_sha256` =
  `b73d761a2a6f382be662cce9377af728c503a99cd322ca1eccb8b0e846812de9`.

The provider returned all 552 matches in one response despite the requested
documented maximum limit of 500. The declared count, actual count, unique-ID
count, stage distribution, matchday range, and complete double round robin all
agreed. The qualifier accepts only this exact complete first response or the
documented `500 + 52` pagination form; any other oversized, incomplete, or
wrong-scope response fails closed. The optional remaining-quota header was
absent, consistently with the other Free-plan observations.

The seven revised 2026/27 Championship play-off fixtures are not present in
the observed regular-season scope. Their participants become known only after
the league table is complete, so they remain a separate progressive lifecycle
scope comparable to a cup draw. They require later stage-specific live
qualification and must not contribute removal evidence under this decision.

## Champions League readiness status

**Conditional and not ready.** The curated
`champions-league-league-phase` profile supports the bounded 2026/27
qualification track in issue #155. It requires competition `CL` / 2001,
36 teams, exactly 144 `LEAGUE_STAGE` fixtures, eight complete matchdays, and
one fixture appearance per team on every matchday.

A secret-safe read-only check at `2026-08-30T08:40:34Z` observed the correct
season ID 2557 and all 36 participants, but the match collection returned zero
fixtures. The qualifier therefore failed closed without emitting evidence.
This is not the first of the two required successful observations, and it does
not assign authority or permit runtime implementation.

## Secret-safe live qualification commands

The repository includes a read-only command with curated profiles for Premier
League, Bundesliga, the Championship regular season, and the Champions League
league phase. It makes two metadata requests plus one or more paged match
requests. Premier League, Bundesliga, and a complete Champions League league
phase normally require three requests. The Championship endpoint was observed
returning all 552 regular-season fixtures in one response despite the requested
limit of 500, so its current observation also makes three requests. The
qualifier still supports pages of 500 and 52 if the provider starts honoring
its documented pagination contract. Free-form competition IDs and expected
counts are deliberately unsupported.

The command emits only the qualification profile, observation time, aggregate
identifiers, counts, pagination/request counts, UTC boundaries, status counts,
stage counts, API version, SHA-256 fingerprints of the sorted match and team
IDs, the latest source-update timestamp, and the minimum remaining request
count. It never emits the API token, raw body, authorization header, account
identifier, team names, individual IDs, or fixture details.

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

For issue #123, the Championship candidate is deliberately restricted to the
documented `REGULAR_SEASON` stage. Run this command once, review the output
locally, wait at least 60 seconds, and repeat the complete command:

```powershell
$env:FOOTBALL_DATA_API_KEY = Read-Host -MaskInput "football-data.org API token"
try {
    python -m app.operations.football_data_qualification --competition championship --season 2026
}
finally {
    Remove-Item Env:FOOTBALL_DATA_API_KEY -ErrorAction SilentlyContinue
}
```

This stage filter establishes a stable 552-fixture regular-season boundary.
The seven 2026/27 Championship play-off fixtures are not part of that
observation and remain a separate, unqualified, non-destructive lifecycle
scope. The provider's stage-filter echo is non-authoritative and can use a
different representation from the match resources. Qualification therefore
checks the stage on every returned match and must fail if either page has the
wrong offset or the response is not the complete 24-team double round robin.
An exact 552-match first response is accepted within the configured byte limit;
any other response above the requested 500-item page limit fails closed.

For issue #155, the Champions League candidate is deliberately restricted to
the league phase. Run this command only after a readiness check indicates that
football-data.org has populated the fixture collection:

```powershell
$env:FOOTBALL_DATA_API_KEY = Read-Host -MaskInput "football-data.org API token"
try {
    python -m app.operations.football_data_qualification --competition champions-league-league-phase --season 2026
}
finally {
    Remove-Item Env:FOOTBALL_DATA_API_KEY -ErrorAction SilentlyContinue
}
```

An empty response, any count other than 144, a stage other than
`LEAGUE_STAGE`, an incomplete matchday, or an unresolved participant fails
closed. Qualification rounds belong to paid `CLQ` / 2174 and are never queried
or merged by this profile.

The command fails closed unless it observes:

- API version `v4` on every response;
- the selected profile's exact competition code and ID;
- a current season starting in 2026 with valid start and end dates;
- the selected profile's exact distinct-team and match counts;
- complete offset-based pagination without overlaps or gaps;
- distinct positive match IDs;
- deterministic SHA-256 fingerprints over the sorted match and team IDs;
- the same competition and season identity on every match;
- two distinct known participants on every match;
- the selected profile's exact schedule with one appearance per team per
  matchday and no duplicate directed pairing;
- the selected profile's exact stage and matchday range;
- UTC `utcDate` and `lastUpdated` values; and
- only the documented supported status vocabulary; and
- a source-update age within the profile-independent freshness policy.

The curated invariants are:

| Profile | Code | ID | Teams | Matches | Matchdays |
| --- | --- | ---: | ---: | ---: | ---: |
| `premier-league` | `PL` | 2021 | 20 | 380 | 38 |
| `bundesliga` | `BL1` | 2002 | 18 | 306 | 34 |
| `championship` | `ELC` | 2016 | 24 | 552 | 46 |
| `champions-league-league-phase` | `CL` | 2001 | 36 | 144 | 8 |

Premier League output belongs to issue #79, Bundesliga output to issue #110,
Championship output to issue #123, and Champions League output to issue #155,
in every case only after manual review. The token, raw response, request
headers, account dashboard, and `.env` contents must never be copied into
GitHub.

## Approved operating conditions

- Absence becomes removal evidence only after two complete, successful
  authoritative snapshots for the selected profile: 380 Premier League
  matches, 306 Bundesliga matches, or the explicitly bounded 552-match
  Championship `REGULAR_SEASON` stage. Championship play-offs remain
  non-destructive. A short, stale, empty, malformed, failed, or wrong-scope
  response is never authoritative.
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

These conditions qualify the Premier League, Bundesliga, and Championship
regular-season profiles. Qualification is not implementation: no Championship
source assignment, catalog entry, mapping, runtime collection, scheduler job,
database write, or Outlook operation is authorized by this command. The
Championship play-off scope remains unqualified.

## Sources

- [Championship authority decision](adr/0008-select-football-data-for-championship-regular-season.md)

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
- [EFL Championship competition](https://www.efl.com/competitions/efl-championship/)
- [2026/27 Championship play-off format](https://www.efl.com/news/2026/march/05/efl-statement--sky-bet-championship-play-off-format/)
