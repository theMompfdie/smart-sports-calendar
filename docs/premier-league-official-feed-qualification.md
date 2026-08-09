# Premier League Official Calendar Feed Qualification

## Decision

The Premier League digital calendar delivered by ECAL is **rejected as an
automated server-side source** for SMART Sports Calendar as of 2026-08-09.

The offering is official and useful for its intended end-user subscription
workflow, but the published ECAL Terms of Use limit the service to personal use
and prohibit data-mining, robots, scraping, and similar data-gathering methods.
Polling the personalized iCalendar subscription from this application would be
an automated data-gathering workflow. No public permission for that use was
found, and no written permission has been obtained.

This is a usage-contract rejection, not a claim that the calendar is
technically defective. The application must not subscribe to, poll, parse, or
persist an ECAL Premier League feed unless ECAL or the Premier League grants
explicit written permission covering the intended server-side workflow.

## Official origin and delivery operator

- The Premier League publishes the digital-calendar entry point on its own
  website and states that subscribers can receive all 380 Premier League
  fixtures and automatic updates when matches are rescheduled.
- The official entry point links to `pl.ecal.com` and `ecal.premierleague.com`.
- ECAL, operated by HyperKu Pte Ltd and its operating entities, is the
  third-party delivery operator. ECAL describes the product as delivery of
  publisher schedules into an end user's personal digital calendar.

The Premier League endorsement establishes provenance, but it does not replace
the ECAL end-user licence for the delivery service.

## Evidence and safe inspection boundary

The review used only public pages and documentation. It did not submit a form,
create an ECAL subscription, download a personalized feed, call a private API,
or retain a feed URL or payload.

| Requirement | Result | Evidence or consequence |
| --- | --- | --- |
| Official offering | Confirmed | The Premier League's 2026/27 article links to the ECAL calendar and promises all 380 matches plus automatic reschedule updates. |
| Delivery operator | Confirmed | The linked service is ECAL; ECAL identifies HyperKu and its operating entities as operator. |
| Automated private-calendar use | Rejected | ECAL limits end-user use to personal use and prohibits robots, scraping, data mining, and similar collection. Written permission would be required. |
| Complete season in an acquired feed | Not inspected | Acquiring and polling a personalized feed was not authorized. The marketing claim alone is not snapshot evidence. |
| Stable `UID` across reschedules | Not established | No authorized payload pair or documented stability guarantee was available. A mutable title or kickoff must never be used as identity. |
| Timezone semantics | Not established | No authorized payload was acquired. An implementation may not infer a source timezone from club, venue, or server locale. |
| `SEQUENCE`, `DTSTAMP`, `LAST-MODIFIED`, `STATUS` | Not established | Public product claims do not define the exact iCalendar lifecycle contract. |
| Redirect and conditional HTTP behavior | Not inspected | A personalized URL was not generated. `ETag`, `Last-Modified`, redirects, and cache policy remain unverified. |
| Cancellation and removal semantics | Not established | Automatic updates are advertised, but cancellation, deletion, and complete-snapshot behavior are not documented sufficiently. |

The unverified technical properties independently prevent authoritative use even
if the terms issue were later resolved.

## Conditions for reconsideration

Reconsideration requires all of the following before implementation:

1. written permission from ECAL or the relevant rights holder for automated,
   recurring, private server retrieval and use in a Microsoft 365 calendar;
2. confirmation of allowed caching, retention, attribution, derived use, and
   prohibited redistribution;
3. a secret-safe test subscription created by the operator outside GitHub;
4. two or more authorized snapshots demonstrating stable `UID` values across
   an unchanged fetch and a real update or controlled publisher test;
5. evidence for full-season scope, timezone representation, lifecycle fields,
   redirects, size limits, content type, `ETag`, `Last-Modified`, and conditional
   requests; and
6. a documented support contact and revocation procedure.

Permission evidence must be retained privately by the operator. GitHub may
record only that permission was reviewed, its scope, review date, and expiry or
revalidation date.

## Contract that any future iCalendar adapter must satisfy

An authorized iCalendar source is authoritative only after the complete HTTP
response and every `VEVENT` have validated. A complete snapshot must have:

- an expected HTTPS origin after a bounded redirect chain;
- a successful final status and an allowlisted iCalendar content type;
- a configured byte and event-count limit;
- one `VCALENDAR`, no conflicting duplicate `UID` values, and a non-empty set
  within the expected competition and season;
- exactly the expected competition scope, with the expected participant set or
  another independently verified completeness invariant;
- a stable non-empty `UID` for every fixture;
- timezone-aware `DTSTART` values, or a documented `TZID` resolvable from
  included `VTIMEZONE` data or the IANA database; and
- supported lifecycle values with no validation errors.

Only such a snapshot may update canonical rows or contribute removal evidence.
Malformed, truncated, over-limit, empty, stale, unexpectedly reduced, wrong-
season, wrong-competition, or conditionally inconsistent responses fail closed.
They retain the last-known-good canonical state and cannot cause cancellation,
deletion, or Outlook writes. `304 Not Modified` may reuse the previously
validated snapshot identity; it is not a new removal observation.

Source URLs are deployment secrets because ECAL-style subscription URLs contain
subscriber identifiers. They must be supplied through the deployment secret
store and excluded from logs, exceptions, run metadata, evidence, screenshots,
tests, and GitHub. Diagnostics may contain only an internal source key and a
sanitized origin label.

## Time and identity rules

- Correlation identity is the exact validated `UID`, namespaced by the internal
  source registration. `SUMMARY`, teams, kickoff, and venue are mutable data.
- UTC timestamps remain UTC. Offset-aware timestamps are converted to UTC.
- A `TZID` must resolve deterministically; floating and naive date-times are
  rejected for football fixtures.
- `SEQUENCE`, `DTSTAMP`, and `LAST-MODIFIED` are update hints only. They do not
  replace content comparison or stable identity.
- A reschedule updates the same canonical event only when its `UID` is
  unchanged.
- `STATUS:CANCELLED` is explicit cancellation evidence. Absence is removal
  evidence only under the complete-snapshot policy and the existing two-
  observation rule.

## Parser dependency decision

Do not implement an RFC 5545 parser with the standard library. If an authorized
iCalendar source is approved later, use the maintained `icalendar` package,
pinned through the project dependency lock process. At review time, version
7.2.0 is production/stable, BSD-licensed, requires Python 3.10 or newer, and
lists Python 3.13 support.

The adapter must still enforce application-level size, component-count,
timezone, duplicate-identity, recurrence, and lifecycle constraints. Parsing
success alone does not establish source integrity. Recurrence expansion is not
required for a normal fixture feed; an unexpected `RRULE` or
`RECURRENCE-ID` fails qualification unless a dedicated, tested policy is added.
No dependency is added by this documentation issue because the ECAL source is
rejected and adapter implementation is out of scope.

## Next permitted source

`football-data.org` v4 is the next candidate for the Premier League authority.
Its public documentation exposes the `PL` competition, stable numeric match
identifiers, UTC kickoff values, match statuses, `lastUpdated`, server-side
token authentication, and a free Premier League tier. Its published terms
permit registered API use for a single application, require credential
confidentiality and visible attribution, and prohibit retaining/reference use
after subscription cancellation.

This identification is not implementation approval. A follow-up qualification
must confirm current-season completeness, schedule freshness, removal
semantics, retention implications, attribution placement, and the exact
subscription suitable for staging and production. Until that succeeds,
API-Football remains the implemented legacy source and no new provider is
authorized to write Premier League canonical events.

## Authoritative sources

Sources were accessed on 2026-08-09.

- [Premier League digital calendar announcement](https://www.premierleague.com/en/news/1235133/download-the-202627-premier-league-fixtures-to-your-calendar/)
- [ECAL Terms of Use](https://ecal.com/terms-of-use/)
- [ECAL Privacy Policy](https://ecal.com/privacy-policy/)
- [ECAL subscriber API documentation](https://docs.ecal.com/reference/apiv2/subscriber.html)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org terms and privacy](https://www.football-data.org/about)
- [football-data.org v4 competition reference](https://docs.football-data.org/general/v4/competition.html)
- [football-data.org v4 lookup tables](https://docs.football-data.org/general/v4/lookup_tables.html)
- [`icalendar` package metadata](https://pypi.org/project/icalendar/)
- [`icalendar` 7.2 documentation](https://icalendar.readthedocs.io/en/stable/)
