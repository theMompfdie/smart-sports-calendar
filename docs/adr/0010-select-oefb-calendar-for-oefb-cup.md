# ADR 0010: Select the official ÖFB calendar for the ÖFB-Cup

- Status: Accepted
- Date: 2026-08-28
- Related issues: #104, #108, #128

## Context

Phase 5 needs one permitted authority for the 2026/27 ÖFB-Cup. The previous
matrix named paid Sportmonks league `187` as a conditional candidate, while
football-data.org exposed only a stale 2020/21 catalog entry. The operator has
not approved a paid plan and requires trustworthy no-cost sources to be
preferred for this hobby project.

The official ÖFB-Cup page offers a competition-wide `Spielkalender`
subscription. It generates an automatically refreshed iCalendar feed from the
ÖFB platform, declares a six-hour publication TTL, and is intended to place
fixture updates in a user's calendar. This matches the project's private
Outlook-calendar purpose more closely than a general public data export.

Two secret-safe observations separated by about two minutes and 26 seconds
returned 111 unique events and the same UID fingerprint. The feed contains the
complete previous season plus 48 currently published 2026/27 fixtures: 32 in
round one and 16 in round two. All current events have unique numeric fixture
UIDs, UTC kickoffs, structured home and away identities, round text, and
official URLs.

The feed has no explicit cancellation status, sequence, last-modified value,
or complete-season marker. Later cup rounds are added after each draw. Absence
can therefore never be destructive evidence.

## Decision

Select the official ÖFB competition iCalendar feed as the only automated
authority for `football/oefb_cup/2026_27`, subject to these mandatory limits:

- every observation is authoritative `partial`, `complete=false`, and
  removal-ineligible;
- observations may create and update known fixtures but never infer
  cancellation or removal from absence;
- exact iCalendar `UID` is the external fixture identity;
- the accepted current-season UID set may grow but must not shrink or replace
  an identity automatically;
- only events inside the explicit canonical 2026/27 date window are eligible;
- home and away identities require exact structured-field mapping to a
  reviewed 64-team canonical catalog;
- round text must resolve exactly to `round-1` through `round-6`;
- UTC `DTSTART` is the kickoff authority;
- only `www.fussballoesterreich.at` is accepted as the final feed host;
- feed URL, raw content, opaque identifiers, and event details remain secret or
  private and never enter source control, logs, CI, or GitHub;
- polling respects `X-PUBLISHED-TTL:PT6H` and uses bounded retries and
  `If-Modified-Since`; a 304 response reuses the last validated snapshot and is
  not a new observation;
- logos and images are excluded; and
- public redistribution, a public fixture database, or commercial use requires
  a separate rights review or written ÖFB permission.

The operator creates the subscription URL manually through the official public
calendar control. The application consumes the configured HTTPS feed and must
not generate new subscriptions automatically.

The Outlook event body must include:

> Fixture data provided by the Austrian Football Association (ÖFB):
> <https://www.oefb.at/cup>

## Consequences

- A separate implementation issue is mandatory and must add the iCalendar
  transport/parser boundary, catalog, reviewed mappings, partial import
  runtime, tests, documentation, and isolated staging proof.
- The implementation introduces a new provider integration but no paid plan,
  account, API key, automatic failover, or second writer.
- Multi-season feed content must be filtered before normalization; historical
  fixtures cannot enter the 2026/27 canonical scope.
- Unknown properties, identities, teams, rounds, recurrence, timezone forms,
  oversized responses, duplicate UIDs, empty/reduced observations, HTTP
  failures, and parsing failures preserve last-known-good state.
- A reschedule updates the existing canonical and Outlook events only while the
  UID and participant mapping remain stable.
- The source cannot be promoted to `complete_round`, `complete_stage`, or
  `complete_season` without a new qualification and ADR.

## Rejected alternatives

### Scrape the official ÖFB page or internal JSON services

Rejected. The page remains a manual verification source and undocumented
internal data services are outside the source policy. The explicitly offered
iCalendar subscription is sufficient and narrower.

### Sportmonks

Rejected for the current private scope because it requires a paid plan. It
remains a future alternative only after explicit operator approval and new
qualification.

### football-data.org

Rejected because Austrian Cup coverage requires a paid Pro plan and the public
catalog observation is stale at 2020/21.

### TheSportsDB

Rejected because the free season endpoint returned only 15 of at least 32
current-season first-round fixtures and exposes no pagination for the missing
records. Full schedule access requires payment.

### API-Football

Rejected because no ÖFB-specific data-rights clearance is recorded.

### OpenLigaDB and OpenFootball

Rejected because neither currently provides a 2026/27 ÖFB-Cup authority with
the required fixture identity and update scope.

Detailed evidence and implementation gates are recorded in
[`../oefb-cup-source-qualification.md`](../oefb-cup-source-qualification.md).
