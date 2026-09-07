# UEFA Europa League Source Qualification

## Current Version 1.0 checkpoint - 2026-09-07

Issue [#269](https://github.com/theMompfdie/smart-sports-calendar/issues/269)
now owns delivery of the main 2026/27 competition, league phase through final.
Phase 9 issue #200 is closed and the non-draft `v0.9.0-beta.1` release was
published on 2026-09-06. Its recorded signed-release and integration evidence
satisfies the prerequisite to begin this requalification.

**Reviewed manual league-phase import is delivered to isolated staging.**
The 2026-09-06 observations did not qualify either evaluated zero-cost
automated candidate for the required league phase. The operator subsequently
approved and applied the private manual package. Earlier source qualification
and preparation checkpoints below are dated evidence, not current deployment
status. Production use and final acceptance of issue #269 remain open.

### Accepted initial staging evidence

PR [#277][uel-pr] merged as
`d4c9e41dab2b08172f7e7366b4cfbbc1b9e5750a`. Its five PR CI jobs and the five
[merge CI jobs][uel-ci] passed. The operator deployed `uel-d4c9e41` in the
existing isolated staging stack on 2026-09-06. The pre-upgrade backup passed
SQLite integrity checking; this is not a post-import restore exercise.

The [operator evidence][uel-evidence] records:

- 144 league-phase fixtures, 144 distinct Outlook mapping IDs and converged
  canonical and presentation revisions;
- eight separate UEL review appointments with Outlook IDs and applied hashes;
- seven UEL participant reminder rules, alongside two independent UECL rules;
- an unchanged import with a new submission ID, `uel-2026-27-replay-01`, whose
  APPLIED receipt contains 144 SKIP and zero CREATE, UPDATE, CANCEL or DEFER;
- 144 unique canonical IDs and 144 unique manual external IDs in that receipt.

The operator also confirmed that the calendar appointments are correct.
The replay receipt's `pending` Outlook status describes its commit-time state;
it does not establish a fresh post-replay Graph inventory. Aggregate updates
in the earlier synchronization run cannot be attributed to UEL individually.
The independent Championship failure tracked in #233 is not UEL evidence.

The trusted manual namespace is `manual-uel-2026-27`, bounded to
`LEAGUE_PHASE` / `league_phase`, rounds 1 through 8. The private package
retains the source revision, checksum, attribution, CC BY-SA 4.0 reference
and stable identity ledger. No automated UEL authority was enabled.

### Post-replay local inventory - 2026-09-07

The operator ran the scoped read-only inventory against the healthy staging
image `uel-d4c9e41`. SQLite quick check returned `ok`. The inventory confirms:

- one enabled authoritative UEL writer, source `manual`;
- 144 active scheduled league-phase fixtures, no deleted fixtures, and exactly
  18 fixtures in each of rounds 1 through 8;
- 144 source-event mappings and 144 synced calendar mappings to one target;
- 144 populated, distinct Outlook mapping IDs and zero pending revisions;
- eight active review appointments with distinct Outlook IDs and all eight
  applied hashes matching their desired hashes.

The source-event identity fingerprint is
`be782f0a858aac2db4187fed77c7b248d1defd80aee5bc1112e09583315d41f2`.
Kickoffs span `2026-09-16T16:45:00+00:00` through
`2027-01-28T20:00:00+00:00`. This is a fresh local mapping/revision check
after replay; it is not a direct Graph inventory. The previously accepted
operator calendar confirmation remains separate evidence. The subsequent
post-UEL restore and restart results are recorded below.

### Post-UEL backup, isolated restore and restart - 2026-09-07

The operator stopped only staging, copied the full data directory, and
restarted the same container. The saved image ID matched the owning staging
container before the independent restore check. The completed host report
confirms:

- all 111 files matched the saved SHA-256 inventory in both the backup and
  the separate restore copy;
- the restored SQLite database passed integrity checking;
- initialization with the saved image preserved the complete logical database
  dump, including fixture identities, source/calendar mappings, review plans
  and immutable receipts;
- the restored database contains 144 UEL fixtures, eight converged review
  appointments and two APPLIED UEL receipts;
- the owning staging container is healthy and its successful startup record
  belongs to the current container start.

The restore helper used separate storage, the saved image, `--network none`
and a read-only container root. It invoked database initialization, not the
scheduled application or Graph synchronization. This proves isolated data
restore and initialization; generic deterministic runtime recovery tests and
the owning-instance restart are separate evidence. No second calendar writer
was started. Private backup, restored data and checksum artifacts remain on
the Docker host; their paths and contents are not publication attachments.

### Offline closure checks - 2026-09-07

The local full suite passed: **1,531 tests in 350.47 seconds**. This includes
manual lifecycle, atomic rollback, replay, downstream Graph failure,
restart/restore and the UEL real-catalog preview regression. Graph/provider
boundaries are mocked; these results do not substitute for live staging.
The run used a fresh explicit pytest `--basetemp` and disabled its cache
provider after Windows denied access to the existing temporary/cache paths.
The initial setup-error run is not counted as a passing run.

`ruff check .`, `ruff format --check app scripts tests` and
`python scripts/check_publication_safety.py` passed. The tested runtime tree
matched the merged #277 candidate. These checks preceded the diagnostic fix
below; its verification is recorded separately.

`markdownlint-cli2 README.md docs/uefa-europa-league-source-qualification.md`
was run using the default rules because no repository Markdown configuration
was present. This qualification file passed. README has the same 14 existing
MD013 line-length violations observed before editing; the changed UEL content
adds none. The README as a whole is not lint-clean. Unrelated historical
README cleanup remains outside this change. `git diff --check` passed.

### Manual-authority diagnostics correction - 2026-09-07

The operator's post-replay check confirmed that `uel-d4c9e41` was healthy,
but `app.operations.staging_evidence` failed before producing its report:
manual source assignments correctly store a NULL interval, while the report
attempted `int(None)`. This failure is in diagnostics and does not establish
an import, synchronization or database failure.

The local correction preserves that absent interval as JSON `null`; timed
automated sources still report integers. A CLI regression configures a real
manual UEL profile, checks the rendered authority and verifies unchanged
database bytes. All 83 staging-evidence tests and the full suite of
**1,532 tests in 336.46 seconds** passed after the fix. Ruff lint/format and
publication-safety checks passed. The fix changes no source scheduling,
authority grants, SQLite schema or Graph operations. The operator committed
the reviewed fix as `d16155cf19d4a7b447467b6720159778196c0f80`; its contents
and valid GPG signature were verified locally on 2026-09-07.
PR #278 integrated the correction and evidence into develop as signed merge
`ade9117dfc2cdf8006933bcd011825d747f372ef` on 2026-09-07. All five PR jobs
and all five [merge CI jobs][uel-fix-ci] passed; merge CI reports 1,532 tests
passed in 215.89 seconds. Deployment of this correction to staging is not
claimed: the accepted live evidence remains tied to `uel-d4c9e41`.

[uel-fix-ci]: https://github.com/theMompfdie/smart-sports-calendar/actions/runs/34109730053

### Remaining qualification and future publication boundaries

The delivered package covers the 144-fixture league phase only. Knockout
play-offs, round of 16, quarter-finals, semi-finals and final remain in the
intended main-competition scope, but no fixtures for those stages are claimed
as imported. Qualifying rounds remain excluded. The current catalog season
dates cover the league phase; review and extend the catalog dates before
accepting any later-stage package.

The operator's read-only plan report confirms that the existing eight tasks
are `review-md-1` through `review-md-8`, each with a 60-minute reminder and
only `LEAGUE_PHASE` round targets. Their Vienna-local review dates are
September 14, October 13/20, November 3/24, December 8, January 19/26,
all at 09:00. They do not cover future knockout publication.

The operator approved and applied the review-only staging extension:
`uel-2026-27-review-through-final-01`. It preserves all eight accepted tasks
and adds 18 weekly Monday checks from February 1 through May 31, 2027, at
09:00 Europe/Vienna with 60-minute reminders. UTC timestamps account for the
summer-time transition. The unscoped `periodic_review` tasks cover published
main-competition updates; they grant no fixture-stage authority.

The [UEFA competition overview][uel-overview], checked on 2026-09-07, still
places the final on May 26, 2027. The final planned review is after that date.
Extend the accepted plan if publication or the final is delayed. Obtain and
review new stage packages when usable schedules become available; process
observed corrections promptly and preserve stable fixture IDs. Before any
new-stage apply, explicitly review catalog dates, authority/profile extension,
source provenance and the exact-file preview. Keep every still-needed task
when replacing the accepted review plan.

The extension contains zero fixtures, retains the accepted scope/boundaries
and attribution, and updates only preparation time and the review plan.
Synthetic preview/apply verification produced 18 review CREATE and eight
SKIP, zero fixture decisions and unchanged fixture/source/authority rows.
The existing reviewed source is retained as provenance; no fresh source
schedule observation is claimed. The accepted live preview contained exactly
18 review CREATE and eight SKIP, with zero fixture decisions. The operator
approved the exact preview; the returned status is APPLIED without errors,
with 26 review tasks and all fixture decision counts zero. The operator's
final read-only inventory confirms 26 active appointments, 26 populated and
distinct Outlook IDs, exactly one calendar target and all 26 applied hashes
matching their desired hashes. The weekly through-final review plan is now
applied and its local Outlook mappings are converged.

The applied manifest fingerprint is
`eab6349e1420d3a6b43d5cbb296703cd3149868785a2dfa59e9ce1f2422abfb3`;
its approved preview fingerprint is
`a9298c4048572645ce94a59dd4242c5442369df5f02b5ee15db67fc33f81d66a`.
The earlier verified backup contains the initial eight-task plan and two
receipts; it predates this extension and is not claimed to contain 26 tasks.
The September 14 API checkpoint is separate and cannot switch the writer.

[uel-overview]: https://www.uefa.com/uefaeuropaleague/news/02a6-20d57d095740-e1e0b3de85df-1000/

The operator reconfirmed the complete 144-fixture league phase in staging on
2026-09-07 and confirmed that knockout rounds follow in the new year. This
accepts the league-phase delivery without reducing the intended scope through
the final. The [UEL delivery record](uefa-europa-league-delivery.md) supplies
the current source matrix, ongoing operations, release-note entry and
production runbook. Issue #269 can close after this documentation is reviewed,
merged and its applicable CI passes; stable publication and production
promotion remain separate gates under #201 and #270.

Reuse the generic deterministic lifecycle/failure tests and accepted Phase 9
evidence where the implementation is unchanged. Do not manufacture live
fixture corrections or cancellations merely to repeat those tests. A copied
database or a successful backup alone does not prove runtime recovery.
Use the [staging backup procedure](phase-9-staging-preparation.md) and
[manual inbox recovery contract](manual-import-workflow.md). Any isolated
restore must have separate storage and no network access; it must never
become another writer to the staging calendar.

Production enablement remains separate. Its runbook must bind a verified
release revision, production backup and isolated configuration to a fresh
production preview and exact approval. Staging approval cannot be reused.
Release notes must distinguish the delivered league-phase package from
future draw-dependent updates and any still-open live qualification gate.

[uel-pr]: https://github.com/theMompfdie/smart-sports-calendar/pull/277
[uel-ci]: https://github.com/theMompfdie/smart-sports-calendar/actions/runs/34061099307
[uel-evidence]: https://github.com/theMompfdie/smart-sports-calendar/issues/269#issuecomment-5562451993

### Initial catalog and staging preparation - 2026-09-06

This preparation procedure preceded the accepted staging import above.

The application catalog now contains the UEL hybrid competition and the
2026/27 league-phase season, 16 September 2026 through 28 January 2027, with
36 reviewed participants. Seven existing club identities and their metadata
are reused; 29 additional club identities are registered. Startup uses the
existing idempotent catalog initialization; no schema migration is needed.
Catalog presence alone does not activate a source or import fixtures.

The operator-side schedule was prepared from Wikipedia contributors'
[fixed revision 1373338629][uel-wiki] under [CC BY-SA 4.0][uel-license].
The private package retains attribution, the saved revision and its checksum,
an identity ledger, 144 league-phase records and a review CSV. Match dates
and pairings stay outside the public repository. The checked-in participant
catalog contains identity metadata only. No knockout schedule is inferred.

The private `uel-2026-27-staging-profile.json` targets instance `staging`,
namespace `manual-uel-2026-27`, and exactly rounds 1 through 8 of
`LEAGUE_PHASE` (`league_phase`). The manifest and profile must be transferred
separately; copying the manifest alone cannot provision the trusted profile.
Keep the namespace and frozen fixture IDs on corrections and use a new
submission ID for each revised package.

Before live use, merge the tested catalog change into `develop`, deploy its
verified revision through the existing staging stack, and preserve the
existing database, inbox and other profiles. Install the reviewed profile
and restart the owning application as described in the
[manual inbox workflow](manual-import-workflow.md). Submit the private
manifest, inspect its actual staging preview and approve that exact preview
before applying. Confirm 144 fixtures and eight review tasks, then check
unchanged replay, Outlook convergence and stable canonical identities.
Offline validation is not evidence of this deployed acceptance.

During the same isolated staging window, record the deployed revision,
successful DFB-Pokal import, preserved identity/mapping state and independent
scheduler-job success for issue #268. The UEL file does not test that provider.
The later API transition remains a separately reviewed identity reconciliation
and authority handover under ADR 0015; this change enables no API writer.

[uel-wiki]: https://en.wikipedia.org/w/index.php?oldid=1373338629
[uel-license]: https://creativecommons.org/licenses/by-sa/4.0/

### Public documentation reviewed on 2026-09-06

The current [API documentation](https://footballdata.io/documentation/)
requires Bearer authentication. The
[season contract](https://footballdata.io/documentation/seasons/) documents
league-scoped season discovery and season match/team endpoints, with date
filters and pagination for the latter. The documented season year distinguishes
2026/27 using `20262027`. League `46` and season `90443` are historical
observed IDs to reconfirm, not blindly trusted current configuration.

The [usage contract](https://footballdata.io/documentation/rate-limits/)
provides account-specific quota inspection. Its examples are not evidence
of this operator's remaining quota or current entitlement. API documentation
alone does not establish current league-phase publication, complete pagination,
stable identities, update freshness or cancellation semantics.

The [terms](https://footballdata.io/terms/), displaying an update date of
2026-05-03, allow reasonable caching and plan-dependent derived applications.
They also state that long-term storage may require written permission and
restrict raw dataset redistribution. Therefore durable canonical SQLite state,
backups and retained private Outlook events still need a use-specific rights
and attribution decision. This review neither accepts account terms nor
establishes a blanket prohibition on private use.

### Current observations - 2026-09-06

Two Python HTTP requests to the account endpoint returned HTTP 403. The
operator then obtained HTTP 200 using PowerShell, reporting a free account
with 2,000 monthly requests and 1,998 remaining. The same PowerShell method
worked with the locally configured staging key: free plan, 2,000 limit and
1,997 remaining at that observation. No key change was required. The exact
cause of the earlier transport-dependent rejection remains unestablished;
it is not evidence of disabled credentials or missing data entitlement.

Five successful assistant requests checked quota, seasons, date-filtered
matches, teams and unfiltered matches. Including the two rejected attempts
and the operator's one successful check, eight Footballdata.io requests were
attempted within the agreed maximum of twelve. No raw responses or secrets
were stored. Quota was not re-read after the data requests.

| Footballdata.io observation | Result |
| --- | --- |
| League / season / year | `46` / `90443` / `20262027` |
| Matches, 2026-09-01 through 2027-01-31 | 0; reported pagination total 0 |
| All season matches | 80; one page, limit 100, reported total 80 |
| Unfiltered match-date bounds | 2026-07-09 through 2026-08-27 |
| Reported match status | All `complete` |
| Distinct round IDs | 4 |
| Season team directory | 86 entries; one page, reported total 86 |

The season directory marks multiple historical entries as current. Selection
must verify the explicit year and league/season identities, not rely solely
on `is_current`. The unfiltered July/August match dates confirm that the empty
September-to-January result is not sufficient main-scope coverage hidden by
the requested date window. No stable-identity or lifecycle qualification is
claimed; the required main-competition schedule is absent in this observation.
A second identity-stability observation cannot qualify missing fixtures.

One additional unauthenticated GET to the documented OpenLigaDB route
`/getmatchdata/uel2026/2026` reports league `6000`, season `2026`, 16 distinct
fixture IDs and 15 distinct participant IDs. Kickoffs span
2026-09-16T19:00:00Z through 2026-10-22T19:00:00Z.
All entries have group order 1.
This is insufficient for 36 participants and 144 league-phase fixtures.
Only aggregate evidence was retained; this request does not use the
Footballdata.io account or its quota.

The current public football-data.org
[free coverage](https://www.football-data.org/coverage) still excludes UEL.
Its [pricing](https://www.football-data.org/pricing) does not establish a new
free UEL entitlement. No other credential, paid plan or trial was used.
This is a decision on the reviewed candidates, not a claim that every possible
supplier has been exhaustively tested.

### Initial manual source decision - 2026-09-06

This checkpoint preceded package preparation and the staging import above.

The operator selected manual import if the candidate and other suitable
automated sources cannot qualify. Apply that decision to the current evidence:
prepare the main UEL competition through the existing reviewed manual workflow.
Do not implement or enable either incomplete automated feed, combine their
partial datasets or infer cancellations from omitted fixtures.

The initial preparation needs a lawfully obtained, operator-reviewed 2026/27
league-phase schedule with provenance and the applicable private-use rights
record. UEFA's published fixture overview is a source reference, not permission
to scrape or redistribute its dataset. Use the existing schema, private stable
fixture-ID ledger, exact-file preview/approval and durable import receipts.
Verify the canonical competition, season and all participant keys before
creating a trusted profile; the generic parser is not proof of UEL delivery.

Start with all eight league-phase matchdays once the reviewed source is
available. Keep knockout play-offs through final in the delivery scope, with
new reviewed packages after each draw and whenever a correction is published.
A concrete review cadence and reminder appointments must accompany the first
package. Qualifying rounds remain outside the main scope. Staging, replay,
correction, recovery, backup/restore, documentation and release acceptance
remained open at this checkpoint. The later staging evidence above supersedes
the initial absence of a manual authority grant and deployment.

## Historical Phase 6 status - 2026-08-31

UEL was deferred from `v0.6.0-beta.1`. The observations and candidate analysis
below describe the evidence on 2026-08-29 and 2026-08-31 under issue #158.
They apply the hybrid tournament contract from #151. They do not establish
current availability, approve payments or authorize runtime collection.

## Operator scope decision

On 2026-08-29 the operator approved the following competition boundary:

- missing qualifying-round coverage does not block the main Europa League
  source decision;
- an approved 2026/27 release scope may begin with the league phase and
  continue through the knockout phase play-offs, round of 16, quarter-finals,
  semi-finals, and final;
- when a provider exposes qualification under a separate competition ID or a
  materially separate lifecycle, it may be qualified later as an optional
  source/competition scope; and
- qualification and main-competition observations must never be merged
  automatically or provide removal evidence for each other.

This is a lifecycle and release-boundary decision, not a source or cost
approval. Documentation must not imply qualifying-round support unless that
separate scope later qualifies.

## Competition and lifecycle boundary

UEFA's 2026/27 regulations and competition overview define one edition from
the first qualifying round on 9 July 2026 through the final in Frankfurt on
26 May 2027. The complete edition contains:

- first, second, and third qualifying rounds;
- qualifying play-offs;
- an eight-match league phase for 36 clubs, producing 144 fixtures;
- knockout phase play-offs;
- round of 16, quarter-finals, and semi-finals; and
- a single-match final.

Qualifying, play-off, and knockout ties are played over two legs. Teams can
enter from Champions League qualification, and later-round participants and
fixtures are discovered incrementally.

The canonical `2026_27` season remains the full edition boundary. The approved
release candidate is narrower: league phase through final. A provider may be
authoritative only for that explicit scope and must not imply full-edition
coverage. The expected final main-scope shape is 189 fixtures: 144 league-phase
fixtures, 16 knockout-play-off fixtures, 16 round-of-16 fixtures, eight
quarter-finals, four semi-finals, and one final. Only the league-phase boundary
can be structurally complete before later draws and progression resolve.

## Candidate review

### Official UEFA sources

UEFA is authoritative for the competition format, participants, draws,
official schedule, and regulations. Its public pages now list the 36
league-phase participants, opponents, matchday windows, knockout dates, and
final.

No supported public fixture API or automatically updated competition feed was
found with stable machine fixture IDs, pagination, completeness semantics,
quotas, retention rules, or an automation contract for this application.
UEFA's platform terms prohibit systematic collection and automated scraping.
Public UEFA material is therefore manual verification evidence only. HTML
scraping, browser-session extraction, and undocumented endpoints remain
excluded.

The UEFA Data Products Portal, business authentication API, and Intelligence
Centre evidence reviewed for the Champions League track do not publish a
self-service Europa League fixture product or generally available usage terms.

### OpenLigaDB

OpenLigaDB is a credential-free community database rather than an official
UEFA source. Its documented model allows registered users to create and
maintain leagues, and similarly named duplicate or incomplete leagues can
exist. Stable numeric fixture, participant, league, season, sport, and group
IDs are technically useful, but a league-directory entry is not completeness
or authority evidence.

The public 2026 league directory contained a new candidate on 2026-08-29:

| Field | Observed value |
| --- | --- |
| League ID | `6000` |
| Shortcut | `uel2026` |
| Season | `2026` |
| Name | Europa League 2026/27 |
| Authentication | None |
| Cost | EUR 0 |

A sanitized read-only observation at `2026-08-29T10:37:36Z` returned:

- 16 fixtures with 16 unique fixture IDs;
- 14 unique participant IDs and no unresolved participant slots;
- one UTC kickoff value for all 16 fixtures;
- all fixtures assigned to `Ligaphase`;
- four configured group names (`Ligaphase`, `Viertelfinale`, `Halbfinale`,
  and `Finale`), omitting knockout phase play-offs and round of 16; and
- zero finished fixtures.

A second readiness observation at `2026-08-31T12:03:53Z` still returned only:

- 16 fixtures with 16 unique fixture IDs;
- 15 unique participants rather than the required 36;
- league-phase kickoffs spanning only 16 September through 22 October 2026;
- the same four configured groups, still omitting the knockout phase play-offs
  and round of 16; and
- no fixtures in the configured quarter-final, semi-final, or final groups.

The participant count changed from 14 to 15 while the fixture inventory
remained at 16. This confirms active but incomplete community maintenance, not
a stable or complete league-phase snapshot.

This observation occurred on the morning after UEFA's 28 August league-phase
draw, before the finalized dated fixture list had propagated across the
reviewed provider catalogs. It is therefore classified as `not ready`, not as
a permanent provider rejection. The response is not the official 36-team,
144-fixture league-phase boundary and cannot qualify the source, assign
authority, enable imports, or provide removal evidence. The source should be
re-observed after the finalized UEFA schedule is published and propagated,
but a later complete-looking response still requires two stable observations
and manual comparison with UEFA.

If OpenLigaDB later qualifies, its community maintenance, lack of explicit
cancellation/postponement taxonomy, and absence of a provider completeness
marker mean the initial implementation should remain permanently
removal-disabled unless stronger competition-specific evidence supports a
later ADR. Existing ODbL attribution and produced-work/adapted-database rules
would apply, and linked logos or icons would remain excluded.

### football-data.org API v4

The credential-free public catalog observation on 2026-08-29 returned two
separate provider competitions:

| Provider competition | ID | Code | Plan | Public current season |
| --- | ---: | --- | --- | --- |
| UEFA Europa League | 2146 | `EL` | `TIER_TWO` | 2025/26, ID 2455 |
| Europa League Qualification | 2183 | `ELQ` | `TIER_THREE` | 2026, ID 2532 |

This split matches the operator-approved lifecycle boundary: `ELQ` can remain
outside the release while `EL` is evaluated independently. The main `EL`
catalog had not yet advanced to 2026/27, so its league-phase fixture count,
participant resolution, stage vocabulary, later-round coverage, and stable
identity could not be validated.

`TIER_TWO` corresponds to the currently published Standard plan at EUR 49 per
month for 30 competitions. The existing football-data.org transport,
validation, retry, quota, and failure-isolation code would reduce
implementation risk, but no paid plan is approved for this track.

The API exposes stable-looking numeric fixture and participant IDs, UTC
kickoffs, statuses, stages, matchdays, and `lastUpdated`; it documents season,
stage, matchday, status, and date filters. It does not guarantee stable match
IDs across changes or expose an exact completeness marker. A paid selection
would still require two secret-safe credentialed observations after `EL`
advances to 2026/27.

The existing one-application, credential secrecy, visible attribution,
availability disclaimer, cancellation cleanup, and separate logo-rights
conditions apply.

On 2026-08-31 the operator authorized secret-safe, read-only availability
checks with an existing free credential. The authenticated competition catalog
returned HTTP 200 with 13 accessible competitions, but did not contain `EL` /
2146. The documented direct competition endpoint returned HTTP 403. No fixture
or participant endpoint was called, and no credential, header, private payload,
or account data was emitted or persisted. The free account therefore cannot
supply the main Europa League competition under the current plan boundary.

### Footballdata.io API v1

Footballdata.io is a separate provider from football-data.org. The operator's
free account dashboard explicitly includes UEFA Europa League among its five
selected leagues. Secret-safe read-only checks on 2026-08-31 confirmed:

- an active free API key with an observed monthly allowance of 2,000 requests;
- UEFA Europa League league ID `46` in the free-plan search results;
- current season ID `90443`, year `20262027`, plus 17 historical seasons;
- 69 season teams and 80 unique completed fixtures across four provider
  rounds;
- 52 unique fixture participants, with kickoffs from 9 July through 27 August
  2026; and
- zero fixtures when the current season was filtered from 1 September 2026
  through 31 January 2027.

The current response therefore covers qualifying and play-offs but none of the
official 144-fixture, 36-participant league phase. UEFA published the finalized
league-phase fixtures on 29 August and matchday 1 is on 16/17 September, about
eight days after the Champions League begins. This result is classified as
`not ready` propagation evidence, not a permanent provider rejection.

The API exposes numeric league, season, round, fixture, and team identities,
UTC-convertible match timestamps, status, update, date filtering, and
pagination. Its documented examples and live nested response shapes differ in
some details, so any adapter must validate the observed v1 contract rather
than assume the examples are exact. The free tier requires attribution;
coverage varies by league and season. The terms permit reasonable caching but
may require written permission for long-term storage or bulk replication.
Those persistence, attribution, cancellation, availability, and third-party
data-rights boundaries require explicit acceptance before authority
assignment.

### Sportmonks Football API v3

Sportmonks documents Europa League as league ID `5`. Its published model covers
seasons, three qualifying rounds, play-offs, the 36-team league phase,
knockout stages, rounds, fixtures, participants, aggregates, and
stable-looking IDs. This is the strongest documented technical fit among the
reviewed commercial candidates.

The Starter plan currently begins at EUR 29 per month for five selected
leagues and 2,000 calls per entity per hour. Its 14-day trial requires a valid
credit or debit card and automatically becomes paid unless cancelled. The
terms permit building derived applications and storing/distributing returned
data but prohibit raw resale, scope pricing per domain, disclaim completeness
and availability, and require a separate rights review for logos and photos.

Sportmonks would require a new provider integration and competition-specific
live validation. No trial, payment method, subscription, or terms acceptance
is approved.

### API-Football v3

API-Football documents a EUR 0 plan with 100 requests per day and broad
competition/fixture coverage. Its existing project integration and lifecycle
fields make it technically plausible.

API-Sports explicitly states that it does not grant the required licence to
use or publish competition data and that the user must obtain permission from
the competent league, federation, or event organizer. No UEFA-specific written
permission is recorded. API-Football therefore remains rejected as a new
Europa League authority under the current evidence.

### Other zero-cost candidates

TheSportsDB free season retrieval remains capped at 15 events without a
documented complete-pagination contract. OpenFootball does not publish a
current Europa League fixture dataset with provider-grade stable fixture IDs
and lifecycle coverage. Neither can qualify the 144-fixture league phase.

## Deferred decision

No authoritative writer is assigned for `uefa_europa_league` / `2026_27`.
The operator deferred Europa League from `v0.6.0-beta.1` on 2026-08-31 because
none of the reviewed zero-cost paths currently supplies the required
36-participant, 144-fixture league phase and no recurring paid source is
approved for this release. Footballdata.io remains the preferred later path
because free-plan access, current season identity, and qualifying data are
already observable.

The evaluated paths remain:

1. **Preferred zero-cost path — re-observe Footballdata.io.** Free access and
   the current season are confirmed, but the league phase has not propagated.
   A later complete observation still requires full technical and contractual
   qualification plus a new provider adapter.
2. **Alternative zero-cost path — wait and re-observe OpenLigaDB.** This avoids
   a new subscription and reuses the existing adapter, but current data is
   severely incomplete and any later implementation is expected to remain
   removal-disabled and community-source dependent.
3. **football-data.org paid path — EUR 49/month.** This reuses the existing
   provider integration and cleanly separates `EL` from paid `ELQ`, but costs
   more and still needs 2026/27 catalog publication plus two credentialed
   observations.
4. **Sportmonks paid path — from EUR 29/month.** This has the strongest
   documented hybrid model and lower starting price, but requires a credit
   card-backed trial, a new adapter, and full live/contractual qualification.
5. **Defer Europa League — selected for `v0.6.0-beta.1`.** Preserve the current
   unassigned state until a permitted source satisfies the operator's cost and
   evidence boundary.

API-Football is not an approvable option without separate UEFA rights
clearance. An operator selection authorizes only the next qualification gate,
not authority assignment or implementation.

## Required re-evaluation gate

Before a credentialed-validation or implementation issue can be created:

1. the operator selects the acceptable cost and provider path;
2. the selected main competition exposes the finalized 2026/27 league-phase
   schedule;
3. two sanitized read-only observations prove stable fixture identity,
   competition/season scope, 36 resolved participants, exactly 144
   league-phase fixtures, stage/matchday semantics, UTC kickoffs, pagination,
   update behavior, and reproducible fingerprints;
4. terms, attribution, persistence, cancellation, and secret handling are
   explicitly accepted for the selected private-calendar use; and
5. later rounds remain incremental and non-removal-capable until separately
   qualified as exact stage or round boundaries.

Qualification remains optional and separate. It must not block or silently
expand the main scope.

## Re-evaluation triggers

Re-evaluate this decision when:

1. Footballdata.io season `90443` publishes the complete 36-team, 144-fixture
   league phase with stable fixture identity, schedule, and update behavior;
2. OpenLigaDB `uel2026` / 6000 publishes the complete 36-team, 144-fixture
   league phase with stable identities and credible group structure;
3. football-data.org `EL` / 2146 advances to 2026/27 or changes plan tier;
4. Sportmonks changes its plan, trial, or Europa League coverage terms;
5. UEFA publishes or permits a supported API or calendar feed;
6. UEFA grants written permission for the intended API-Football use;
7. another permitted source proves stable, complete main-scope coverage; or
8. the operator selects or changes the allowed recurring-cost boundary.

## Sources

Reviewed 2026-08-29 and re-observed 2026-08-31:

- [UEFA 2026/27 Europa League overview](https://www.uefa.com/uefaeuropaleague/news/02a6-20d57d095740-e1e0b3de85df-1000/)
- [UEFA 2026/27 Europa League regulations](https://documents.uefa.com/r/Regulations-of-the-UEFA-Europa-League-2026/27/)
- [UEFA league-phase draw and opponents](https://www.uefa.com/uefaeuropaleague/accesslist/)
- [UEFA platform terms](https://www.uefa.com/termsconditions/)
- [UEFA Data Products Portal](https://data.uefa.com/products/)
- [OpenLigaDB](https://www.openligadb.de/)
- [OpenLigaDB API](https://api.openligadb.de/)
- [OpenLigaDB API behavior and maintenance model](https://github.com/OpenLigaDB/OpenLigaDB-Samples)
- [OpenLigaDB 2026 league directory](https://www.openligadb.de/Leagues?season=2026)
- [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- [football-data.org coverage](https://www.football-data.org/coverage)
- [football-data.org public competition catalog](https://api.football-data.org/v4/competitions)
- [football-data.org pricing](https://www.football-data.org/pricing)
- [football-data.org terms and attribution](https://www.football-data.org/about)
- [football-data.org competition resource](https://docs.football-data.org/general/v4/competition.html)
- [football-data.org match resource](https://docs.football-data.org/general/v4/match.html)
- [football-data.org API policies](https://docs.football-data.org/general/v4/policies.html)
- [Footballdata.io API documentation](https://footballdata.io/documentation/)
- [Footballdata.io league endpoints](https://footballdata.io/documentation/leagues/)
- [Footballdata.io season endpoints](https://footballdata.io/documentation/seasons/)
- [Footballdata.io rate limits](https://footballdata.io/documentation/rate-limits/)
- [Footballdata.io terms](https://footballdata.io/terms/)
- [Sportmonks Europa League API](https://www.sportmonks.com/football-api/europa-league-api/)
- [Sportmonks plans and pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Sportmonks terms](https://www.sportmonks.com/terms-of-service/)
- [API-Football pricing](https://www.api-football.com/pricing/)
- [API-Sports terms](https://api-sports.io/terms)
