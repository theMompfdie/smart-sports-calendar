# football-data.org Premier League Qualification

## Status

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

## Public evidence reviewed on 2026-08-09

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

## Secret-safe live qualification command

The repository includes a read-only command that performs exactly three HTTPS
requests: competition, teams, and matches. It emits only aggregate identifiers,
counts, UTC boundaries, status counts, API version, a SHA-256 fingerprint of
the sorted match IDs, the latest source-update timestamp, and the minimum
remaining request count. It never emits the API token, raw body, authorization
header, account identifier, team names, match IDs, or fixture details.

In PowerShell, enter the token without echoing it or storing it in shell
history:

```powershell
$env:FOOTBALL_DATA_API_KEY = Read-Host -MaskInput "football-data.org API token"
python -m app.operations.football_data_qualification --season 2026
Remove-Item Env:FOOTBALL_DATA_API_KEY
```

The command fails closed unless it observes:

- API version `v4` on all three responses;
- competition code `PL` and a current season starting in 2026;
- exactly 20 distinct team IDs;
- exactly 380 matches and 380 distinct positive match IDs;
- a deterministic SHA-256 fingerprint over the sorted match IDs;
- the same competition and season identity on every match;
- two distinct known participants on every match;
- UTC `utcDate` and `lastUpdated` values; and
- only the documented supported status vocabulary.

The output may be attached to issue #79 only after manual review. The token,
raw response, request headers, account dashboard, and `.env` contents must never
be copied into GitHub.

## Approved operating conditions

- Absence becomes removal evidence only after two complete, successful
  380-match authoritative snapshots. A filtered, short, stale, empty,
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
