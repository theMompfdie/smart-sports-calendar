# NFL 2026 Regular-Season Source Qualification

## Decision

**Qualified for implementation:** use the nflverse `schedules` release as the
sole proposed authority for the NFL 2026 regular season, subject to explicit
operator enablement and the non-destructive boundary below.

The approved source asset is:

`https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv`

The approved scope is exactly 272 regular-season games, 32 teams, and weeks
1–18 for season `2026`. Preseason and postseason are excluded. Although the
272-game structure is complete, observations remain `partial`,
`complete=false`, and `removal_eligible=false` because nflverse is a
community-maintained source, late-season kickoff times are subject to NFL flex
scheduling, and the feed has no authoritative snapshot-completeness marker.

## Operator boundary

The operator selected this path on 2026-08-30 under these conditions:

- recurring source cost must remain EUR 0;
- runtime data is used only in the operator's private SQLite database and
  dedicated private Outlook calendar;
- the public repository contains only source code, configuration examples,
  synthetic tests, aggregate evidence, and attribution;
- raw nflverse files, NFL fixture inventories, database files, Outlook
  exports, team logos, and other media assets are not published;
- generated Outlook events visibly credit nflverse and link to the source and
  CC BY 4.0 licence; and
- a deployment outside this private-use boundary requires a fresh rights and
  redistribution review.

This qualification is an engineering and source-policy decision, not legal
advice and not an assertion of NFL endorsement.

## Source and automation contract

The nflverse project publishes automated data releases on GitHub for access by
different programming languages. The `schedules` release provides CSV, gzip,
Parquet, RDS, and timestamp assets. The CSV release was current and reachable
without an account or credential during qualification.

The runtime contract is deliberately narrower than the source dataset:

- fixed HTTPS origin and path for the `games.csv` release asset;
- redirects only through GitHub-controlled release delivery hosts;
- final HTTP status `200`;
- an allowlisted CSV/octet-stream content type;
- a bounded response size;
- UTF-8 CSV parsed with the Python standard library;
- required columns only; unrelated scores, betting, weather, coaching,
  stadium, roster, and media fields are ignored;
- filter `season=2026` and `game_type=REG` before normalization;
- reject mixed, duplicate, malformed, or unexpected selected-scope rows; and
- preserve the last known good state on every transport, schema, identity,
  scope, or mapping failure.

nflverse documents schedule updates every five minutes during the season.
SMART Sports Calendar should use a substantially slower operator-configured
polling interval because fixture-calendar updates do not require near-live
collection.

## Sanitized live observations

Two separate read-only observations were made on 2026-08-30. The raw file and
fixture inventory were not retained in the repository or attached to GitHub.

| Property | Observation 1 | Observation 2 |
| --- | --- | --- |
| Selected season/type | `2026` / `REG` | `2026` / `REG` |
| Selected games | 272 | 272 |
| Unique `game_id` values | 272 | 272 |
| Duplicate `game_id` values | 0 | 0 |
| Unique teams | 32 | 32 |
| Weeks | 1–18 | 1–18 |
| Missing dates | 0 | 0 |
| Missing kickoff times | 0 | 0 |
| Missing ESPN secondary IDs | 0 | 0 |
| Earliest selected date | 2026-09-09 | 2026-09-09 |
| Latest selected date | 2027-01-10 | 2027-01-10 |
| Fixture-ID SHA-256 | `dfad7658d8ec34c973f522d3b175492f6bb6def2e7a114db7b8c12a2292d7d05` | same |

Observation 2 completed at `2026-08-30T14:23:02Z` with HTTP `200`, an
`application/octet-stream` response, and a 2,177,169-byte asset. Its selected
identity, date, kickoff, and participant scope fingerprint was
`a80528d677d71593aa41d824567a37975c8aca9ce284a9fc0ed3808cf598f5d9`.

The NFL independently describes the 2026 regular season as 272 games across
18 weeks. This proves structural agreement without copying the official
fixture inventory into the repository.

## Identity contract

`game_id` is the selected provider fixture identity. nflverse describes it as
the primary game identifier used throughout its datasets. The current format
combines season, two-digit week, away-team abbreviation, and home-team
abbreviation.

The adapter must also retain available `espn`, `old_game_id`, and `gsis`
values as diagnostic source metadata, not as competing primary identities.
Current future fixtures may not yet have every secondary identifier.

Normal NFL flex scheduling changes the date or kickoff within a week and does
not change `game_id`. If nflverse changes the selected identity set, moves a
game to a different week, changes participants, or rekeys an existing game,
the observation fails closed for operator review. The runtime must not merge
fixtures heuristically from teams and timestamps.

## Teams and scope validation

The implementation must include one reviewed mapping for each of the 32
current nflverse abbreviations. Logos, colors, venue imagery, and other media
are excluded.

Every accepted observation must prove:

- exactly 272 selected rows and 272 unique `game_id` values;
- exactly 32 admitted teams;
- only `REG` games for season `2026`;
- weeks 1 through 18 with no value outside that set;
- each team appears in exactly 17 games;
- every row has two different admitted participants;
- valid Eastern date and kickoff fields; and
- no duplicate pairing identity or conflicting source ID.

The 272-game check is structural admission, not removal permission. A missing
or additional selected row rejects the entire observation.

## Timezone and flex-scheduling contract

nflverse documents `gametime` as 24-hour Eastern time regardless of the game
venue. The adapter must combine `gameday` and `gametime` in
`America/New_York`, resolve daylight-saving rules with `zoneinfo`, convert to
UTC, and then rely on the existing Outlook presentation timezone.

Naive output timestamps, nonexistent local times, ambiguous local times,
invalid dates, invalid clock values, and missing values fail closed.

NFL flex scheduling can change dates and kickoff times during the season.
Weeks 16–18 contain additional scheduling uncertainty, and Week 18 times are
announced late. The current nflverse rows may therefore represent provisional
calendar positions. Events must visibly state that the schedule is subject to
NFL flex scheduling, and later observations update the existing event by
stable `game_id`.

This qualification does not permit inferring a kickoff, converting a blank or
unknown time to a default, or treating a provisional position as removal
evidence.

## Lifecycle boundary

The initial adapter needs only calendar-relevant lifecycle behavior:

- future rows normalize to `SCHEDULED`;
- changed dates or times update the existing fixture;
- played scores are ignored because live results are out of scope;
- an explicit, documented cancelled or postponed representation may be added
  only after focused evidence and tests; and
- an omitted row never cancels or deletes a canonical or Outlook event.

Preseason is excluded by `game_type`. Wild card, divisional, conference, and
Super Bowl rows are draw-dependent progressive scopes and require a separate
qualification and source-job boundary before import.

## Licensing and publication safety

The nflverse-data release repository applies Creative Commons Attribution 4.0
International to its published material. CC BY 4.0 permits reproduction and
adaptation subject to attribution and notices. It does not grant trademark
rights or rights the licensor does not control.

nflverse separately states that NFL data belongs to its respective owners and
is governed by their terms. The approved private-calendar boundary therefore
uses only the minimum factual schedule fields and does not publish the source
dataset or a derived fixture database.

Required event attribution:

> NFL schedule data provided by nflverse (CC BY 4.0):
> https://github.com/nflverse/nflverse-data

Documentation must also link to the CC BY 4.0 licence. The application must
not display NFL or club logos, imply endorsement, or redistribute raw source
rows. If nflverse removes the release, changes its licence, stops maintaining
the schedule, or requests attribution changes, the source job must be disabled
until the exit conditions are reviewed. Last-known-good private calendar state
is preserved non-destructively during that review.

## Alternatives

### NFL.com pages or calendar controls

Rejected as an automated runtime source. NFL pages remain authoritative manual
verification evidence, but this project has no documented public fixture API
or permission to scrape them.

### ESPN endpoints

Rejected because the commonly used schedule endpoints are undocumented and no
approved automated-use or redistribution contract was identified.

### Commercial sports APIs

Rejected for the initial track because they introduce recurring cost and are
unnecessary while a qualified zero-cost candidate exists. No trial or payment
plan is an automatic fallback.

### Operator-assisted manifest

Retained as a fallback under issue #168 if nflverse later becomes unavailable
or unsuitable. It is not an automatic second writer.

## Implementation gate

Qualification permits a separate implementation issue. It does not enable a
source job, perform live staging, or approve production deployment.

Implementation must add:

1. a bounded GitHub-release CSV transport profile;
2. strict NFL schedule parsing and timezone conversion;
3. the 32-team catalog and mapping;
4. exact 272-game structural validation with permanent removal disablement;
5. attribution and flex-scheduling language in Outlook events;
6. synthetic unit, repository, integration, mocked-Graph, failure, and
   idempotency coverage; and
7. isolated live staging before release inclusion.

## Primary references

- [nflverse-data repository](https://github.com/nflverse/nflverse-data)
- [nflverse schedules release](https://github.com/nflverse/nflverse-data/releases/tag/schedules)
- [nflverse-data CC BY 4.0 licence](https://github.com/nflverse/nflverse-data/blob/main/LICENSE.md)
- [nflverse schedule update documentation](https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html)
- [nflverse schedule loader](https://github.com/nflverse/nflreadr/blob/main/R/load_schedules.R)
- [nflverse schedule field documentation](https://github.com/nflverse/nfldata/blob/master/DATASETS.md#games)
- [NFL schedule structure](https://operations.nfl.com/gameday/nfl-schedule/creating-the-nfl-schedule)
- [NFL 2026 flex-scheduling procedures](https://www.nfl.com/news/2026-flexible-scheduling-procedures-and-scheduling-for-week-18)
- [NFL 2026 official schedule](https://www.nfl.com/schedules/2026/by-team)

