# UEFA Europa League delivery and operations

## Accepted scope - 2026-09-07

Issue [#269][issue] delivers the 2026/27 main competition incrementally through
the existing reviewed manual-import workflow. The operator reconfirmed all
144 league-phase fixtures in staging, covering all eight rounds. Knockout
rounds follow in 2027 through reviewed packages when schedules are available.
The intended boundary remains league phase through final; qualifying rounds
are excluded. Unpublished future fixtures are not missing imported fixtures.

The [qualification record](uefa-europa-league-source-qualification.md) retains
the dated source decision, rights/provenance references and staging evidence.
The operator owns source review, corrections, package approval and the update
appointments. Completing this delivery issue does not end those duties.

## Current UEL source matrix

This is the Version 1.0 UEL decision. Earlier phase matrices remain historical.

| Boundary | Selected path | Delivered state |
| --- | --- | --- |
| League phase, rounds 1-8 | Reviewed manual import | 144 fixtures in staging |
| Knockout play-offs through final | Reviewed manual updates | Future packages |
| Qualifying rounds | None in this delivery | Excluded |
| Automated UEL source | None qualified for required scope | No enabled writer |

The current authority is source `manual`, namespace `manual-uel-2026-27`,
competition `uefa_europa_league`, season `2026_27`. Its approved boundary is
`LEAGUE_PHASE` / `league_phase`, rounds 1-8. Future-stage intent and unscoped
review tasks grant no additional fixture authority. Exactly one authoritative
writer remains active; an API availability check cannot switch that writer.

The private reviewed source package retains its revision, checksum,
attribution, CC BY-SA 4.0 reference and stable identity ledger. Publication of
this repository does not publish that dataset. Later packages require their
own reviewed provenance; an earlier source decision is not blanket approval
of new material or of an automated source.

## Ongoing updates through the final

There are 26 converged review appointments in the staging calendar: the eight
league-phase reviews plus 18 Mondays from February 1 through May 31, 2027,
at 09:00 Europe/Vienna, with 60-minute reminders. The weekly plan covers the
recorded May 26 final and its immediate follow-up. Extend the plan if the
competition or publication is delayed. Process observed corrections promptly;
a scheduled reminder is not automatic source retrieval.

For each review, use the [manual preparation guide][preparation] and
[Docker-host workflow][workflow]:

1. Check lawfully obtained schedules and retain the review outcome privately.
   If no update is available, keep current fixtures and the next review.
2. Prepare a versioned package outside the runtime. Preserve stable manual
   fixture IDs for corrections and reschedules. Missing items in partial
   packages never imply cancellation or deletion.
3. Before the first later-stage package, review and extend catalog season
   dates and the trusted profile/authority boundary explicitly. Current dates
   cover September 16, 2026 through January 28, 2027 only. Include qualified
   participant mappings and stage/round identifiers for the incoming package.
   Catalog changes follow the normal code review and test workflow.
4. Retain every still-needed task when replacing a review plan. Review-only
   packages must have zero fixture decisions; they cannot extend authority.
5. Submit to the intended owning instance, inspect the accepted preview and
   approve its exact manifest and preview hashes. Investigate unexpected
   CREATE, UPDATE or CANCEL decisions before approval.
6. Inspect the durable APPLIED receipt, then check downstream convergence,
   unique Outlook mappings, pending revisions and review-appointment hashes.
   APPLIED alone is not proof that Outlook writes have completed.
7. Retain the package, provenance, identity ledger and receipts privately.
   Back up the current complete persistent state under the existing recovery
   procedure, including the accepted review plan and inbox.

A later automated transition requires a newly qualified source, explicit
identity correlation and authority handover under [ADR 0015][authority].
There is no automatic failover or concurrent writer.

## UEL entry for Version 1.0 release notes

The following describes the delivered feature for inclusion in the final
release notes under #270; it does not announce an already published v1.0.0.

- Added the 2026/27 UEFA Europa League catalog and qualified reviewed manual
  delivery of all 144 league-phase fixtures to isolated staging.
- Verified unchanged replay without duplicate canonical identities, fixture
  and review mapping convergence, isolated backup/restore and healthy restart.
- Added an accepted 26-appointment review plan covering league-phase updates
  and weekly checks through the final. Later knockout fixtures are delivered
  incrementally through separately approved packages and scope extensions.
- Fixed the staging diagnostic report for manual authorities without a timer:
  their interval is reported as JSON `null` instead of raising `TypeError`.
- Automated UEL retrieval, qualifying-round delivery and production promotion
  are not included in these staging acceptance claims.

## Production enablement runbook

This is the UEL-specific sequence layered on the [owning-instance workflow][workflow]
and [backup procedure][backup]. Production use requires a separate operator
release/promotion decision after the applicable #201 gates pass. No production
import or deployment is claimed by #269 or by this document.

1. Select the verified immutable release revision containing the UEL catalog
   and diagnostic correction. Confirm the applicable production blockers and
   release checks are satisfied; develop and a staging image are not the
   production release selection.
2. Confirm production has its own Compose project, credentials, instance name,
   volume, database and target Outlook calendar. Run only one owning writer.
   Keep private configuration and source packages outside source control.
3. Stop the owning production instance and back up its complete persistent
   state, including SQLite/WAL state and the manual inbox. Record the previous
   immutable image and configuration. Verify the backup using the documented
   isolated restore procedure before performing the approved upgrade.
4. Upgrade using the chosen release and verify startup, migrations and health.
   Configure the inbox and a separately reviewed production trusted profile
   whose instance reference and stage boundary match the intended target.
   Follow the workflow's profile installation and restart commands.
5. Prepare the current reviewed UEL package and an appropriate review plan for
   the actual promotion date. Do not blindly copy expired staging reminders.
   Do not copy staging database IDs, Outlook mappings or approval artifacts
   into production. Retain stable source identities and reviewed provenance.
6. Submit and preview on production using the workflow's commands. Verify the
   target, scope, expected fixture decisions and reminder tasks. Obtain a fresh
   exact-file approval for that production preview before applying it.
7. Check the APPLIED receipt and subsequent Outlook convergence. For the
   unchanged initial league-phase package, expect 144 active fixtures, 18 per
   round and distinct populated mappings; assess later-stage totals against
   their reviewed previews. Verify review-task convergence and no unintended
   changes to other competitions, then back up the accepted current state.
8. On failure, preserve receipts and follow the workflow's recovery contract.
   Stop before restoring state; never start a second calendar writer. If Graph
   writes occurred, reconcile their outcome before replaying an older database
   backup. A filesystem restore does not roll back Outlook events.

The accepted staging restore verified 111 files, 144 fixtures and the initial
8-task plan. It preceded the extension to 26 tasks and does not replace a
fresh production backup or prove that the extended plan is in that old backup.

## Completion evidence and ownership

PR #277 supplied the catalog. PR #278 integrated the diagnostic fix and dated
evidence as signed develop merge `ade9117`; all five [merge CI jobs][ci] passed,
including 1,532 tests. The live staging evidence uses `uel-d4c9e41`; deployment
of the later diagnostic correction is not claimed. The operator accepted the
complete league phase and confirmed future knockout delivery in the new year.

This documentation completes the UEL source/operations/release/runbook
cross-check for review. Final closure of #269 follows its signed documentation
commit, reviewed merge and passing applicable CI. The general README audit,
canonical release-notes organization and final product documentation remain
under #270, which consumes this record. Stable publication remains under #201.
Neither broader task is a prerequisite to the UEL documentation merge itself.

[issue]: https://github.com/theMompfdie/smart-sports-calendar/issues/269
[ci]: https://github.com/theMompfdie/smart-sports-calendar/actions/runs/34109730053
[preparation]: manual-import-preparation.md
[workflow]: manual-import-workflow.md
[authority]: adr/0015-import-reviewed-manual-fixture-manifests.md
[backup]: phase-9-staging-preparation.md
