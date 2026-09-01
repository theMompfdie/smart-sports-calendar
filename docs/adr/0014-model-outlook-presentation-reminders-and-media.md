# ADR 0014: Model Outlook presentation, runtime reminders, and media separately

- Status: Accepted
- Date: 2026-09-01
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #199, #206, #207, #208, #209, #210, #211, #212, #213
- Builds on: ADR 0004, migration 008, and the provider integration contract

## Context

The released synchronization path has stable provider identities, canonical
SQLite events, persistent Outlook mappings, deterministic payload hashing, and
sport-aware fallback durations. Its Outlook presentation is intentionally
basic: every event has one enabled 15-minute reminder, subjects contain no
sport marker, bodies are plain text, and events receive several categories.

The operator wants competition color to be visible through manually managed
Outlook categories, sport to be visible through a compact subject icon, and the
body to use safe HTML. Reminder preferences must be changeable while the
service is running and must support canonical competition and team scopes. A
Vienna-local quiet period must prevent late-night NFL reminders. Approved
competition, team, trophy, and final images are the last functional Phase 8
slice.

These are calendar-presentation concerns. They must not change provider
authority, canonical fixture identity, source mappings, or provider-owned
fields merely to make an Outlook event eligible for another synchronization.
They also introduce two independent mutable states: a sports event may change
while a presentation rule changes, and an event body may be valid while an
optional image attachment is temporarily unavailable.

## Decision

Adopt the provider-neutral contract in
[`../outlook-presentation-reminder-media-contract.md`](../outlook-presentation-reminder-media-contract.md)
and enforce these boundaries:

1. **Competition color is operator-owned.** The application assigns exactly
   one category using the canonical competition display name. It does not
   create or color Outlook master categories and does not require mailbox-
   settings permission.
2. **Sport identity is canonical presentation data.** The trusted icon stored
   on the canonical sport prefixes the existing derived event title. Provider
   text never supplies an icon or HTML.
3. **HTML is a deterministic projection.** Every dynamic value is escaped.
   The renderer uses a conservative fixed template, retains notices and source
   attribution, and emits optional result/statistic sections only when data is
   present. Phase 8 does not ingest results or statistics.
4. **Reminder preferences are durable runtime state.** SQLite rules use
   canonical foreign keys, one natural rule per scope, and field-by-field
   inheritance from broad to specific scopes. No arbitrary numeric priority is
   introduced.
5. **Quiet-hour decisions use operator local time.** Resolution uses an IANA
   timezone, defaults to `Europe/Vienna`, handles DST explicitly, and yields
   either one integer Graph lead or a disabled reminder.
6. **Presentation invalidation is mapping-specific.** Calendar mappings gain
   desired and last-synchronized presentation revisions. Rule mutations bump
   only affected mappings. Canonical `sports_events.sync_revision` remains
   reserved for canonical Outlook-visible sports data.
7. **Media is optional and rights-controlled.** Metadata and approval live in
   SQLite; normalized files live once in a persistent runtime media root.
   Public availability is not usage permission. Unapproved, missing, or failed
   media always degrades to a complete text-only event.
8. **Attachment state is independent.** Each Outlook event receives its own
   inline attachment copy. Persistent attachment mappings track the remote ID,
   content ID, desired asset hash, status, retry state, and last error without
   conflating them with the event content hash.

Existing provider end times remain authoritative. When no canonical end is
available, the released presentation-only fallback stays two hours for generic
events and three hours for American football. Phase 8 regression-protects
these values rather than silently inventing competition-specific durations.

## Persistence and migration order

The implementation uses deterministic forward migrations:

- migration 009: scoped reminder rules;
- migration 010: desired and last-synchronized presentation revisions on
  calendar event mappings;
- migration 011: rights-controlled media asset registry;
- migration 012: per-Outlook-event asset attachment mappings.

Migration 010 initializes every existing mapping as presentation-actionable so
the first Phase 8 deployment converges old text events to the new projection in
bounded batches. Later scoped rule changes update only matching mapping
revisions. A synchronization completion compares both the captured canonical
event revision and captured desired presentation revision so a concurrent rule
change cannot be overwritten as already synchronized.

The reminder migration preserves released behavior with a built-in effective
fallback of one enabled 15-minute reminder and no quiet period. Operators can
then atomically set a global suppression rule and more specific team rules.
This prevents an upgrade from silently removing every existing reminder.

## Consequences

### Positive

- Presentation can evolve without corrupting canonical fixture ownership.
- Runtime rule changes survive restarts and need no unauthenticated web API.
- Canonical team identity works across competitions without display-name
  matching.
- Quiet-hour behavior is deterministic for NFL and future global sports.
- Existing mappings converge without duplicate Outlook events.
- Optional media failure cannot block core event creation or updates.
- Rights, provenance, hashes, and approval are reviewable before any mark is
  rendered.

### Negative

- Four migrations and two synchronization revisions add persistence and test
  complexity.
- An inline image stored once locally is still uploaded separately to every
  Outlook event that uses it.
- Media reconciliation needs an additional Graph state machine and retry path.
- Operators must create and color competition categories manually using exact
  canonical competition names.
- Runtime rule administration initially requires a local operator CLI rather
  than a graphical interface.

## Alternatives considered

### Keep reminder rules in environment variables

Rejected because changing them requires deployment mutation or restart and
cannot atomically invalidate only affected mapped events.

### Increment canonical event revisions for preference changes

Rejected because personal Outlook preferences are not provider or sports
domain changes. Mixing them would weaken field ownership and complicate future
multi-calendar behavior.

### Add numeric rule priorities

Rejected for Phase 8. A fixed scope order plus one natural rule per scope is
easier to validate, explain, and test. Equal-scope conflicts fail at the unique
constraint instead of depending on operator-assigned numbers.

### Provision Outlook category colors through Graph

Rejected for the current deployment. Manual one-time provisioning is already
complete and avoids expanding the daemon's mailbox-settings permissions.

### Store media as SQLite BLOBs

Rejected because databases, backups, and queries would carry duplicated binary
state. SQLite stores metadata and hashes; the persistent runtime volume stores
the normalized file once.

### Use provider-hosted or arbitrary remote image URLs

Rejected because availability, tracking, secret-bearing URLs, Outlook remote-
image blocking, and rights cannot be controlled reliably.

### Make attachments part of the existing event content hash only

Rejected because attachment creation and deletion are separate Graph
operations. A partial attachment failure must be retryable without invalidating
an otherwise correct calendar event.

## Re-evaluation triggers

Revisit this decision before adding multiple target calendars per database, a
remote administration API, more than one Outlook reminder per event, automatic
asset discovery, public redistribution of third-party marks, or live-score
update frequencies. Each materially changes the security, rights, or
synchronization model.
