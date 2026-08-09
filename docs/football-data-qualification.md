# football-data.org Premier League Qualification

## Status

**Pending live evidence.** Public technical and contractual evidence supports
continued qualification, but `football-data.org` is not yet approved as the
Premier League authority. No `FOOTBALL_DATA_API_KEY` was present in the local
environment or ignored `.env` during this review, so the required read-only
2026/27 validation has not been executed.

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
provider is enabled in staging or production. Subscription cancellation must
disable retrieval and remove provider-derived data from the served calendar;
the exact safe purge/migration procedure must be finalized before approval.

## Secret-safe live qualification command

The repository includes a read-only command that performs exactly three HTTPS
requests: competition, teams, and matches. It emits only aggregate identifiers,
counts, UTC boundaries, status counts, API version, and the minimum remaining
request count. It never emits the API token, raw body, authorization header,
account identifier, team names, or fixture details.

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
- the same competition and season identity on every match;
- two distinct known participants on every match;
- UTC `utcDate` and `lastUpdated` values; and
- only the documented supported status vocabulary.

The output may be attached to issue #79 only after manual review. The token,
raw response, request headers, account dashboard, and `.env` contents must never
be copied into GitHub.

## Remaining approval gates

- Execute the command with a key registered for this single application.
- Confirm the live response contains the expected 20 teams and 380 fixtures.
- Repeat after a safe interval and confirm match IDs remain stable.
- Record the observed delay/freshness and quota cost without fixture details.
- Confirm with the operator that visible attribution and subscription-
  cancellation cleanup are acceptable.
- Define removal behavior: absence becomes evidence only after two complete,
  successful 380-match snapshots; a filtered or short response is never
  authoritative.
- Confirm whether minimal sanitized response shapes may be committed as test
  fixtures; until then tests must use synthetic payloads only.

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
