# Outlook presentation, reminder, and media contract

Status: Approved design for Phase 8 implementation

Date: 2026-09-01

Related issues: #199, #206, #207, #208, #209, #210, #211, #212, #213, #214

This document defines the implementation boundary and the compatibility rules
for Phase 8. It complements
[ADR 0014](adr/0014-model-outlook-presentation-reminders-and-media.md).
Features described here remain planned until their individual implementation
issues are completed and verified.

## Goals

Phase 8 improves the Outlook projection without changing provider authority or
canonical fixture identity:

- exactly one operator-colored competition category per event;
- one trusted sport icon as the event-subject prefix;
- a safe, deterministic HTML body;
- runtime-configurable reminder selection and lead times;
- Vienna-local quiet-hour handling;
- deterministic convergence of existing mapped events; and
- optional rights-controlled inline media as the final Phase 8 slice.

Live scores, result ingestion, statistics ingestion, lineups, odds, and other
high-frequency match data remain outside Phase 8. The HTML model only reserves
optional rendering slots for canonical data that may be introduced later.

## Ownership boundaries

| Concern | Owner | Phase 8 rule |
| --- | --- | --- |
| Fixture identity and lifecycle | Authoritative provider and canonical domain | Unchanged |
| Competition category color | Outlook operator | Provisioned and colored manually |
| Category name | Canonical competition | Sent by the application |
| Sport icon | Canonical sport catalog | Trusted presentation prefix |
| Reminder preference | Local operator | Stored in SQLite and changed through an operator CLI |
| Reminder calculation | Synchronization presentation layer | Resolved deterministically for each event |
| HTML structure | Application | Fixed template with escaped dynamic data |
| Media rights and approval | Local operator | Recorded before an asset becomes renderable |
| Outlook attachment state | Graph synchronization layer | Reconciled independently from event content |

Provider text must never define HTML, an emoji/icon, a category color, a local
reminder policy, or a media attachment.

## Outlook category contract

The application sends exactly one category for a normal or cancelled event.
Its value is the canonical competition display name. The operator creates the
matching Outlook master category once and assigns its color manually.

The currently integrated competition categories are:

| Competition key | Outlook category |
| --- | --- |
| `premier_league` | `Premier League` |
| `bundesliga` | `Bundesliga` |
| `championship` | `EFL Championship` |
| `second_bundesliga` | `2. Bundesliga` |
| `dfb_pokal` | `DFB-Pokal` |
| `oefb_cup` | `UNIQA ÖFB Cup` |
| `uefa_nations_league` | `UEFA Nations League` |
| `uefa_champions_league` | `UEFA Champions League` |
| `nfl` | `National Football League` |

If an event has no resolved competition, the safe fallback is
`SMART Sports Calendar`. Cancellation does not replace the competition
category; cancellation remains visible in the subject, body, status, and
availability projection.

Phase 8 removes the current additional sport and generic categories from the
payload. Existing regional `calendar_category` catalog metadata is not part of
this contract and must be deprecated or removed under #207 rather than used as
a second category source.

The daemon does not call Outlook mailbox-category management endpoints and
does not request `MailboxSettings.ReadWrite` merely to manage category colors.

## Subject contract

The subject keeps the current participant/title derivation and adds at most one
trusted sport icon prefix:

```text
⚽ Manchester United – Liverpool
🏈 New England Patriots – Buffalo Bills
```

For a cancelled event, the existing cancellation marker remains first:

```text
[CANCELLED] ⚽ Manchester United – Liverpool
```

Rules:

1. Use the icon stored on the canonical sport, never provider text.
2. Do not add competition, team, trophy, or status icons to the subject.
3. If the icon is absent, render the existing title without an empty marker.
4. Preserve deterministic whitespace and punctuation so unchanged runs keep
   the same content hash.

## Duration contract

An authoritative provider end time remains authoritative when present. When no
end time is available, the released presentation-only fallback remains:

- American football: 180 minutes;
- all other sports: 120 minutes.

Durations are calculated from timezone-aware instants and must remain correct
across daylight-saving transitions. Phase 8 does not add competition-, stage-,
or kickoff-dependent fallback values because no verified values have been
approved. Those refinements require a separate issue with explicit data and
acceptance examples.

## HTML body contract

Microsoft Graph receives `contentType: HTML`. The application owns one fixed,
conservative fragment using simple tables, paragraphs, headings, and inline
styles supported by Outlook. It must remain useful when styles and images are
not displayed.

Required logical sections, when their data exists, are:

1. competition, season, round, and status context;
2. home and away participants;
3. local kickoff and canonical location/venue data;
4. source attribution and existing operator notices;
5. result summary; and
6. statistics or pre-match statistics.

The result and statistics sections are omitted when no canonical rows exist.
Phase 8 must not create empty placeholder database records or imply that live
statistics are implemented. The template may contain stable component slots in
code so future canonical result/statistic data can be inserted without another
body redesign.

Security and determinism rules:

- escape every dynamic string with HTML quote escaping before interpolation;
- reject arbitrary provider HTML and URLs as markup;
- use no JavaScript, forms, remote CSS, tracking pixels, or active content;
- sort repeated rows by an explicit stable key;
- format timestamps with explicit `Europe/Vienna` context where local time is
  shown;
- keep rendering free from current-clock and random values;
- retain readable textual labels even when optional inline images are absent;
- do not expose secrets, private feed URLs, internal identifiers, or raw
  provider payloads.

The complete Graph event dictionary, including HTML, category, subject,
duration, and reminder fields, remains covered by the existing deterministic
event content hash.

## Reminder rule model

Reminder policy is durable runtime configuration in SQLite. Migration 009
introduces a scoped rule table. A rule has exactly one of these scopes:

- global;
- competition;
- participant, applying to that team across competitions;
- competition participant;
- individual sports event.

Rules reference canonical foreign keys or stable canonical keys. Display names
and provider-specific IDs are not matching keys.

### Required fields

The persistence model must represent:

- scope and the exact canonical foreign keys required by that scope;
- action: `enable`, `suppress`, or `NULL` to inherit;
- preferred lead minutes;
- minimum lead minutes;
- maximum lead minutes;
- quiet-period start and end as local `HH:MM` values;
- IANA timezone name, defaulting effectively to `Europe/Vienna`;
- active flag;
- operator note;
- creation and update timestamps; and
- a deletion timestamp/tombstone for auditable removal.

Nullable policy fields inherit. Database checks require non-negative lead
values and `minimum <= preferred <= maximum` whenever the compared values are
present in one row. Resolver validation repeats these checks after inheritance.

The schema enforces one active current rule per natural scope with partial
unique indexes. A scope check ensures that exactly the expected foreign keys
are populated. There is no operator-assigned numeric priority in Phase 8.

### Resolution order

The resolver begins with a compatibility fallback and overlays non-null fields
from broad to specific:

1. built-in compatibility fallback;
2. global rule;
3. competition rule;
4. participant rule;
5. competition-participant rule;
6. event rule.

The built-in fallback is:

```yaml
action: enable
preferred_lead_minutes: 15
minimum_lead_minutes: 0
maximum_lead_minutes: null
quiet_start: null
quiet_end: null
timezone: Europe/Vienna
```

This preserves released behavior immediately after migration. It also allows
the desired selected-team model: set a global suppression rule, then enable
Manchester United and New England Patriots with participant rules.

An event can contain two participant rules at the same precedence. Identical
non-null values are compatible. Differing non-null values for the same field
are a configuration conflict; the resolver must not choose by row order. It
disables the reminder for that event, emits a safe conflict log, and exposes
the conflict in effective-preview output. A more specific unambiguous rule can
resolve the conflict.

Suppressed or invalid reminder output is normalized as:

```json
{
  "isReminderOn": false,
  "reminderMinutesBeforeStart": 0
}
```

## Target operator policy

The private runtime configuration intended after Phase 8 rollout is:

- global: suppress reminders;
- Manchester United participant: enable, preferred lead 60 minutes;
- New England Patriots participant: enable, preferred lead 60 minutes,
  minimum 60 minutes, maximum 480 minutes, quiet period `22:00`–`08:00`,
  timezone `Europe/Vienna`.

No private IDs, local database paths, or operator-specific secrets belong in
source control. Documentation and tests use stable synthetic or catalog keys.

## Quiet-period calculation

Reminder lead constraints are elapsed minutes between UTC instants. Quiet
period membership and boundary selection use the rule's IANA timezone.

For an event start instant `S`:

1. Resolve and validate the effective rule.
2. Compute candidate instant `C = S - preferred_lead` in absolute time.
3. Convert `C` to the rule timezone.
4. If `C` is allowed, keep it.
5. If `C` is inside the quiet period, move it backward to the most recent
   allowed quiet-start boundary.
6. Recompute the actual lead as elapsed minutes between the chosen instant and
   `S`.
7. Accept only an integer lead inside the inclusive minimum and maximum bounds.
8. If no valid instant exists, disable the reminder for this event.

For `22:00`–`08:00`, exactly `22:00` and `08:00` are allowed; local values
strictly after 22:00 or strictly before 08:00 are quiet. Equal start and end
means no quiet period rather than an all-day suppression.

Examples for a preferred 60-minute lead, a 60-minute minimum, an eight-hour
maximum, and Europe/Vienna:

| Event start | Candidate | Effective reminder |
| --- | --- | --- |
| 19:00 | 18:00 | 18:00, lead 60 minutes |
| 22:25 | 21:25 | 21:25, lead 60 minutes |
| 00:25 | 23:25 | previous day 22:00, lead 145 minutes |
| 02:20 | 01:20 | previous day 22:00, lead 260 minutes |
| 06:30 | 05:30 | no reminder; previous 22:00 exceeds eight hours |

DST boundary construction must be validated through a UTC round trip. If a
local boundary is ambiguous, choose the earlier absolute instant so the
notification is not moved later. If the configured local boundary does not
exist, use the latest valid local minute before it. Unit tests must cover both
Vienna DST transitions independently of the machine timezone.

## Runtime administration contract

The first operator surface is a local CLI, proposed as:

```text
python -m app.operations.reminder_rules
```

It supports `list`, `show`, `set`, `disable`, `delete`, and
`effective-preview`. Mutations are atomic and become visible to the next
synchronization cycle without restarting the service.

Operational rules:

- require an explicit database path;
- initialize/verify migrations without loading Microsoft 365 secrets;
- resolve human-friendly stable catalog keys before opening the write
  transaction;
- reject unknown and ambiguous keys;
- validate the complete effective policy before commit;
- write the rule and presentation invalidations in one transaction;
- print safe summaries only, with no secrets, provider payloads, private source
  URLs, Outlook IDs, or event titles.

A web administration API and filesystem watcher are outside Phase 8.

## Presentation convergence

Changing a reminder preference is not a canonical fixture change and must not
increment `sports_events.sync_revision`. Migration 010 adds to each persistent
calendar mapping:

- desired `presentation_revision`; and
- `last_synced_presentation_revision`.

Existing mappings start with desired revision `1` and synchronized revision
`0`, making them eligible for the initial HTML/category/icon convergence.
Later rule mutations increment only mappings in the affected scope.

A mapping is a synchronization candidate when either:

```text
sports_event.sync_revision > mapping.last_synced_revision
```

or:

```text
mapping.presentation_revision > mapping.last_synced_presentation_revision
```

The synchronizer captures both desired revisions before rendering and updates
both synchronized revisions only if neither changed concurrently. A mutation
that happens during Graph work therefore remains actionable in the next cycle.

If a presentation invalidation produces the same event content hash, the
synchronizer skips the Graph PATCH and only marks the captured revisions as
checked. This keeps scoped invalidation deterministic without unnecessary
remote writes.

Broad mutations may affect many mappings. The existing synchronization batch
limit provides bounded convergence over successive cycles; no second worker
may target the same writable database and Outlook calendar.

## Media registry contract

Migration 011 adds an asset registry. SQLite stores metadata and approval;
normalized files are stored once below a configured persistent media root,
expected to be `/data/media` in the container deployment.

An asset owner is exactly one canonical sport, competition, participant, or
project presentation owner. The model records:

- stable asset key and variant/role;
- MIME type, width, height, byte size, and SHA-256 hash;
- safe path relative to the media root;
- source reference;
- license or written-permission evidence;
- required attribution;
- approval state, reviewer, and approval time;
- active state and timestamps.

Public internet availability is not evidence of permission. Phase 8 performs
no automated logo search, scraping, or downloading. The operator imports a
local file only after reviewing its rights. Unapproved assets are never
rendered.

The import path must:

- prevent absolute paths and traversal outside the media root;
- fully decode and re-encode input rather than trusting the file extension;
- remove embedded metadata;
- reject unsupported formats and excessive input dimensions/size;
- normalize to PNG;
- retain a preferred 60x60-pixel variant for roughly 30x30 Outlook display;
- calculate and verify the stored hash.

Any new image dependency requires a maintenance, security, and license review
under #212. Tests and public artifacts use synthetic project-owned assets.
Third-party marks must not be committed, uploaded to issues, included in CI
artifacts, or published in releases without explicit compatible rights.

The database and media root form one recoverable state unit. Backup/restore
documentation and staging must verify them consistently rather than restoring
asset metadata without its files.

## Inline Outlook attachment contract

Migration 012 adds a per-calendar-event asset mapping. Although a normalized
file exists once locally, Graph stores a distinct inline attachment on every
Outlook event that uses it.

The mapping records the calendar-event mapping, local asset, semantic slot,
content ID, Outlook attachment ID, desired and synchronized hashes, state,
attempt metadata, last safe error, and timestamps.

Attachment state is not folded into the event content hash. Reconciliation is
ordered to keep the body readable:

1. ensure a valid text-only event exists;
2. upload the desired new inline attachment;
3. patch the HTML body to reference its `cid:` value;
4. remove an obsolete attachment only after the new body reference succeeds.

For replacement, add new, switch the body, then remove old. On any media
failure, retain a complete text presentation, persist retryable attachment
state, and continue core event synchronization. Missing files, hash mismatch,
unapproved assets, or rejected Graph attachment operations must never block
fixture creation, rescheduling, cancellation, or deletion.

## Migration and issue allocation

| Migration/change | Owning issue | Purpose |
| --- | --- | --- |
| Catalog/category/icon payload changes | #207 | One category and subject icon |
| HTML renderer | #208 | Safe deterministic body projection |
| Migration 009 | #209 | Runtime reminder rules and CLI |
| Quiet-hour resolver | #210 | Vienna-local constrained lead calculation |
| Migration 010 | #211 | Presentation revisions and convergence |
| Migration 011 | #212 | Rights-controlled media registry/import |
| Migration 012 | #213 | Per-event inline attachment state |
| Staging/release evidence | #214 | End-to-end qualification |

Migration numbers are reserved by this contract to prevent parallel Phase 8
work from choosing conflicting schema versions.

## Logging and observability

Logs should expose safe operational decisions:

- event source key or canonical correlation context already allowed by current
  logging policy;
- matched rule scopes without private database row IDs;
- reminder outcome and reason (`enabled`, `suppressed`, `quiet_shifted`,
  `outside_bounds`, `conflict`, or `invalid`);
- presentation candidate, Graph update/skip, and revision outcome;
- media slot state and safe failure class.

Never log tokens, credentials, authorization headers, private feed URLs,
arbitrary provider payloads, raw media bytes, or rights documents containing
private information.

## Verification requirements

Each implementation issue adds focused unit/repository/integration regression
tests. Phase 8 completion requires at least:

- exact category and subject output for every integrated sport/competition;
- deterministic and escaped HTML snapshots/semantic assertions;
- provider end-time and fallback-duration regression coverage;
- scope inheritance, suppression, selected-team, and equal-scope conflict
  tests;
- ordinary, overnight, limit, and both Vienna DST transition cases;
- transaction rollback and restart persistence for CLI rule changes;
- existing mapping convergence without duplicate Outlook events;
- concurrent canonical and presentation revision protection;
- no-op invalidation without unnecessary Graph PATCH;
- asset validation, rights approval, path safety, hash, and fallback tests;
- attachment create, replacement, retry, deletion, and partial-failure tests;
- unchanged-cycle idempotency;
- `ruff check .`, `ruff format --check .`, and `pytest` passing.

Isolated staging under #214 must use the dedicated staging database, media
volume, credentials, and Outlook calendar. It verifies normal football,
late-night NFL, suppressed events, rule changes without restart, existing event
convergence, HTML rendering in supported Outlook clients, and media fallback.

## Deferred work

The following require later issues and are not implied by the Phase 8 body
slots:

- result/statistics acquisition and high-frequency update scheduling;
- standings, lineups, odds, and live-score notifications;
- multiple reminders on one Outlook event;
- graphical or remote rule administration;
- automatic media discovery or license inference;
- competition/stage-specific fallback durations without approved evidence;
- multiple independently configured target calendars in one database.
