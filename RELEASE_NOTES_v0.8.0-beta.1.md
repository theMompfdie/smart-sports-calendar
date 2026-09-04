# v0.8.0-beta.1 - Outlook Presentation and Reminder Beta

## Release status

Release preparation for #199 and #214. This candidate is not yet published.
Live qualification and the operator-controlled Git and publication gates in
[the release checklist](docs/v0.8.0-beta.1-release-checklist.md) remain open.
The published baseline is v0.7.0-beta.1; production promotion is a separate
explicit operator decision.

## Added and changed

- Exactly one canonical competition category and a sport icon in each subject,
  with cancellation semantics preserved. Category colors are provisioned
  manually in Outlook.
- Escaped, deterministic HTML with participants, fixture metadata, notices,
  source attribution, and readable text-only fallback.
- Outlook event start/end projection in the Vienna-compatible timezone, while
  canonical instants remain timezone-aware and source end times are retained.
  Football and NFL fallback durations remain two and three hours respectively.
- Persistent runtime reminder rules with global, competition, participant,
  competition-participant, and event scopes. The operator CLI supports setting,
  previewing, disabling, deleting, and recreating rules without restarting.
- Deterministic field inheritance, conflict detection, Europe/Vienna quiet
  hours, daylight-saving handling, and bounded reminder leads. A reminder is
  suppressed when no allowed instant satisfies the configured bounds.
- Separate presentation revisions so policy changes converge affected mappings
  without changing fixture identity or creating duplicate appointments.
- A rights-controlled media registry with explicit approval, provenance,
  version history, hashes, and safe local PNG/JPEG normalization using Pillow.
- Optional inline competition, home/away participant, and eligible-final
  artwork through persistent Graph attachment mappings. Matching attachments
  are reused; replacements, cleanup, and interrupted operations are retryable.

## Fixes and operational changes

- Event-attachment listing omits the unsupported Graph projection (#224).
- Staging attachment evidence counts materialized remote attachments (#228).
- Competition and participant artwork is placed alongside its corresponding
  header/detail content; the synthetic trophy is outside the title banner.
- Presentation invalidation durably queues media refresh even when the core
  event hash is unchanged. Missing remote attachments are recovered (#234).
- Docker CI waits for both health and a committed startup record from the
  current container start, with bounded retries and failure logs (#232).
  Existing SQLite and three-instance isolation assertions remain mandatory.

## Authority and data boundary

The nine qualified authorities from v0.7.0-beta.1 remain unchanged. Phase 8
adds no competition, automatic failover, provider scraping, live results,
standings, statistics, or external media discovery. Existing source
attribution, lifecycle, completeness, and removal restrictions still apply.

Media is optional and requires operator-reviewed permission for the exact
asset version. Public availability is not approval. Staging visual samples use
synthetic test artwork; no third-party logos, fixture inventories, databases,
rights records, credentials, or tenant exports are included in this release.
Optional real-image rights review for v1.0 remains separate in #240.

## Upgrade and rollback

Package version: `0.8.0b1`. Python 3.13 remains the baseline.

1. Stop only the intended isolated instance and verify a complete backup of
   its database and media directory from the same point in time.
2. Deploy the reviewed immutable candidate. Deterministic forward migrations
   009–012 add reminder rules, presentation revisions, media assets, and
   calendar attachment mappings while preserving existing domain data.
3. Keep `MEDIA_ROOT` on the same persistent, instance-specific storage plan
   as SQLite. Never share a writable database or target calendar.
4. Converge the one-time presentation backlog and verify the effective
   reminder profile, approved media, and unchanged cycles. Follow the
   [Phase 8 staging runbook](docs/phase-8-staging-validation.md); do not repeat
   presentation invalidation while the same candidate is converging.
5. Rollback requires stopping the instance and restoring the matching
   pre-upgrade database/media snapshot before running the previous image.
   There is no in-place schema downgrade. Database rollback alone does not
   undo Outlook HTML, reminders, or attachments already written; reconcile
   those through the reviewed calendar recovery procedure.

See [deployment](docs/deployment.md),
[reminder administration](docs/runtime-reminder-rules.md), and
[media recovery](docs/media-asset-registry.md).

## Validation and remaining limitations

Offline tests cover migrations, reminder precedence and quiet hours,
presentation convergence, media reconciliation, failure/recovery, and
SQLite-to-mocked-Graph behavior. Local results and final CI evidence belong
in the release checklist and must be rechecked on the committed candidate.

Partial live acceptance in #214 includes competition/home/away/NFL/trophy
visual samples, six remote attachment/CID samples, displayed 60-minute and
quiet-hour reminders, suppression and competition-only enable samples, and
a zero-backlog/unchanged-attachment checkpoint. These observations do not
replace the outstanding mutation/restart, synthetic-test cleanup,
media replacement/fallback/recovery, backup/restore, full duplicate audit,
or final provider-state checks.

Recurring malformed football-data.org status values are tracked in #233.
Later Premier League and Bundesliga observations succeeded, but final
canonical/Outlook integrity and current provider-state evidence are still
required. Strict parsing remains fail-closed; no timestamp-to-status
heuristic or failover was added.

Actual reminder delivery and rendering in every Outlook client are not
guaranteed by sample-level UI checks. The aggregate staging gate cannot
independently prove the exact six-rule policy, remote attachment uniqueness
across the whole calendar, or absence of optional media writes. Those remain
explicit operator acceptance checks. No production promotion is implied.
