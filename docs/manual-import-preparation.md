# Preparing manual fixture manifests

Issue #249 implements a strict JSON parser, typed immutable models and an
explicit profile-validation function. It does **not** implement inbox submission,
database import, source registration or Outlook synchronization.
Issue #250 adds the [write-free preview](manual-import-preview.md);
persistence and runtime delivery follow in #251/#252 under the
[accepted architecture](adr/0015-import-reviewed-manual-fixture-manifests.md).

## Format and limits

The runtime format is UTF-8 JSON with `import_type: "fixture_schedule"` and
integer `schema_version: 1`. Results and unknown versions are rejected. The
[fixture schema](schemas/manual-fixture-schedule-v1.schema.json) assists authoring;
the Python parser remains the authoritative semantic validator. JSON Schema
cannot detect duplicate JSON fields, timezone/offset conflicts, fixture-ID
uniqueness, timestamp ordering or membership in a trusted catalog profile.
JSON Schema considers `1.0` an integer; this parser deliberately requires the
JSON integer token `1`. A schema-only check does not make a file import-ready.

| Limit | Value |
| --- | --- |
| Encoded manifest | 2 MiB (2,097,152 bytes) |
| Fixtures per package | 1-2,000 |
| Explicit stage/round boundaries | 1-256, without duplicates |
| JSON nesting | At most 12 containers |
| Pending review tasks | 1-32 for an active plan |
| Review reminder lead | 0-10,080 integer minutes (application limit) |
| Identifiers | 1-128 ASCII letters, digits, dots, underscores or hyphens |
| Text | 1-256 characters; attribution up to 512 |
| Timezone | Known IANA identifier, at most 64 characters |

Identifiers start with a letter or digit. They are case-sensitive and never
trimmed, transliterated or inferred. Text must have no surrounding whitespace,
control characters, HTML angle brackets or unpaired Unicode surrogates. Do not
put credentials or private URLs into any field. Error messages identify a field
or record index without echoing its supplied value. All objects are closed:
missing fields and unknown fields are errors. Nullable fields must be present
with `null`; omission is not a patch instruction.

## Envelope and exact scope

Required envelope fields are `import_type`, `schema_version`, `submission_id`,
`namespace`, `scope`, `boundaries`, `provenance`, `fixtures` and `review_plan`.

- `submission_id` identifies a particular immutable package. Transport retries
  retain it; an intentional corrected submission uses a new one.
- `namespace` identifies the permanent operator ledger for a competition and
  season. Do not change it when a document is revised.
- `scope` contains `sport_key`, `competition_key`, `season_key` and
  `observation_scope`. Only `partial` is accepted.
- `boundaries` lists the exact allowed combinations of `stage`, `round_name`
  and nullable `stage_kind`. Every fixture references one of these combinations.
  A declaration in a file is not authority: it must also match a trusted profile.

A namespace and fixture ID form the external ID `namespace:fixture_id` for
source key `manual`. Neither component permits a colon, making this encoding
unambiguous. Filenames, array positions, participants and kickoff times never
contribute to identity. Preserve an offline ID ledger across preparations.
Keep a new submission ID separate from unchanged fixture IDs.

## Fixture fields

Each fixture requires these fields, including explicitly nullable values:

- `fixture_id`: permanent opaque fixture identity.
- `boundary`: `stage`, `round_name`, nullable `stage_kind`.
- `home` and `away`: objects with `resolution` and `participant_key`.
- `kickoff`, `timezone`, `kickoff_confirmed`, `status`.
- `group`, `tie_key`, `leg`, `venue`, `city`.

Resolved participant slots require exact known catalog keys. Unresolved slots
must have a null key. Do not enter "winner of tie A" as a team or invent local
SQLite IDs. Two resolved slots cannot reference the same participant. Reviewed
aliases must be resolved to one canonical key before building the manifest;
this parser performs no name matching or automatic team creation.

The trusted profile owns `league`, `knockout_cup` or `hybrid_tournament` format.
League split stages use ordinary stage identifiers. Hybrid stage kinds are
`qualifying`, `playoff`, `league_phase`, `knockout_playoff`, `knockout` and `final`.
A hybrid fixture requires a kind; non-hybrid fixtures must not supply one.
Cup legs are `single`, `first` or `second`, with `null` when inapplicable. First
and second legs require a stable `tie_key`. A non-null tie requires an explicit
leg; league fixtures cannot declare ties/legs. Group and tie identifiers are
optional diagnostics, never correlation rules. Each leg is a separate fixture.
The profile must explicitly qualify the stage/round/kind combinations.

## Times and lifecycle

Confirmed kickoff uses `YYYY-MM-DDTHH:MM:SS` with `Z` or a numeric offset and a
consistent IANA timezone. The parser stores an aware UTC instant. For example,
`2030-09-14T18:00:00+02:00` in `Europe/Vienna` becomes 16:00 UTC. Operational
calendar presentation remains Europe/Vienna even if a source uses another zone.

Naive dates/times, fractional seconds, nonexistent local DST times and
zone/offset disagreements are rejected. At the repeated autumn hour an explicit
valid offset determines the instant. Unknown kickoff requires both `null` and
`kickoff_confirmed: false`; never invent midnight from a date-only publication.

Allowed statuses are `scheduled`, `postponed` and `cancelled`. Scores and live
statuses are unsupported. Valid unresolved participants or unknown times remain
explicit in the typed result; the later planner decides DEFER and preservation
of existing confirmed times according to ADR 0015. They are not parsing errors.
Cancellation requires resolved participant context here; the additional check
that it identifies an existing mapped fixture belongs to issue #250. No DELETE
operation or complete-snapshot removal claim is accepted. Omitting a fixture
from a partial package cannot cancel or delete it.

## Provenance and detached approval

`provenance` requires `issuer`, `document_ref`, `rights_ref`, `attribution`,
`document_sha256`, `checksum_unavailable_reason`, `observed_at` and `prepared_at`.
Document and rights references are safe opaque identifiers into a private
operator record, not download URLs. The parser performs no network access and
cannot establish legal permission; record that review before real data use.

Keep the original document hash when its bytes exist. Otherwise use a null hash
and an explicit reason, for example a manually transcribed text without an
original byte artifact. With a hash, the exception reason must be null. Both
hashes and approval fingerprints are lowercase SHA-256. Observation/preparation
are second-precision aware UTC timestamps; observation cannot follow preparation.

The parser fingerprints the exact submitted bytes and retains them unchanged.
Reformatting changes the fingerprint and requires fresh preview/approval, even
if fixture content is equivalent. This hash is not the calendar content hash.
A source document hash and an import manifest hash describe different artifacts.

The separate [approval schema](schemas/manual-import-approval-v1.schema.json)
requires `submission_id`, `import_type`, `schema_version`, `manifest_sha256`,
`preview_sha256`, `instance_ref`, `operator_ref` and `approved_at`. Its JSON object
must not be embedded in the manifest, avoiding a self-referential checksum.
`parse_approval` checks type/version, exact package binding, timestamp ordering
and identifier/hash syntax. It does **not** authenticate an operator or validate
current preview/target-instance state. Those mandatory checks belong to #250
and #252. Never use a syntactically valid approval as permission to apply data.

## Schedule-review reminders

A manual source needs an explicit review plan: not all league kickoffs are
confirmed at once, and cups need checks after draws and for return-leg timings.
`review_plan` is required and contains `state`, `tasks` and `completion_note`.

An `active` plan requires 1-32 tasks and a null completion note. Each task has:

- `task_id`: stable identity within the manual namespace, retained on replay
  and when rescheduling this same follow-up.
- `due_at`: second-precision aware UTC time to check the publication. It is
  displayed in Europe/Vienna by the later calendar projection.
- `reminder_minutes`: integer 0-10,080 minutes before the review appointment;
  zero means a reminder at its start, not a disabled reminder. Examples use 60.
- `reason`: `kickoff_confirmation`, `next_round_draw`, `return_leg_schedule`
  or `periodic_review`.
- `target_stage`, `target_round`: nullable identifiers for what to check;
  a target round requires a stage. Future rounds may be mentioned here without
  expanding the current fixture scope or granting source authority.
- `note`: nullable bounded plain text explaining the expected publication.

A `complete` plan explicitly requires an empty task list and a nonempty
completion note. It means the operator has no outstanding schedule checks for
this ledger; it never changes the partial observation scope or supplies
fixture-removal evidence. Unknown task fields and duplicate task IDs reject the
package. An overdue due_at remains valid: the parser uses no current clock and
must not hide overdue obligations by rejecting or silently advancing them.

The operator selected a dedicated Outlook appointment with an enabled reminder
in the configured SMART calendar. Planned titles clearly identify an operator
follow-up, for example "SMART: Spielplan aktualisieren", with competition,
reason and affected scope. These are separate from sports events, have separate
stable identity/mapping and must not enter fixture cancellation/removal logic,
team reminder rules or automatic provider updates. No meeting invitations or
additional calendar targets are implied.

The full review plan belongs to its namespace. A later accepted package replaces
that namespace's plan explicitly: preview must show new, rescheduled and retired
review appointments separately from fixture operations. Pending tasks not yet
finished must be retained in that plan. A completion or omission must never
retire another namespace's tasks. Only approved apply changes the active plan;
rejected or merely submitted data leaves reminders intact. A plan-only update
still submits the existing fixture target state unchanged, with a new submission
ID and fresh approval. It must not cause canonical fixture revision churn.

Issue #249 implements the typed plan and validation only. Issue #250 owns review
operation preview and approval binding; #251 persists active plans atomically
with accepted batches; #252 owns separate Graph projection and reliable reminder
lifecycle; #253/#254 prove replay, changes, completion, overdue/restart behavior
and isolation. Outlook delivery is not implemented by this parser. A missed due
time requires an explicitly defined, durable catch-up policy in #252, not a new
appointment on every polling cycle.

No automatic source exists to announce a new draw here: the operator records a
known publication time or a deliberate recheck date. After reviewing the source,
prepare a corrected import and its next review plan. Never infer a newly drawn
fixture, confirmed kickoff or cancellation from reaching the review date.

## Synthetic preparation examples

The examples contain fictional teams, seasons and times, not actual schedules
or approved sources. Their structural competition shapes are test cases, not
claims about current official rules. They do not provision catalog rows or
activate any competition or league. Do not submit them to a production calendar.

- [Austrian Bundesliga initial](examples/manual-import/austrian-bundesliga-initial.json)
  and [correction](examples/manual-import/austrian-bundesliga-corrected.json):
  regular and split-stage boundaries.
- [FA Cup initial](examples/manual-import/fa-cup-initial.json) and
  [correction](examples/manual-import/fa-cup-corrected.json): separate cup rounds.
- [EFL Cup initial](examples/manual-import/efl-cup-initial.json) and
  [correction](examples/manual-import/efl-cup-corrected.json): separate tie legs.
- [Conference League initial](examples/manual-import/uefa-conference-league-initial.json)
  and [correction](examples/manual-import/uefa-conference-league-corrected.json):
  league phase and unresolved knockout participants.

The additional Nations League examples cover separate B/C/D group stages:

- [League B initial](examples/manual-import/nations-league-b-initial.json) and
  [correction](examples/manual-import/nations-league-b-corrected.json).
- [League C initial](examples/manual-import/nations-league-c-initial.json) and
  [correction](examples/manual-import/nations-league-c-corrected.json).
- [League D initial](examples/manual-import/nations-league-d-initial.json) and
  [correction](examples/manual-import/nations-league-d-corrected.json).

These share the Nations League competition key and synthetic season but use
separate namespace/stage profiles. A B/C/D profile rejects League A and other
league boundaries. This validates package scope, not runtime coexistence:
the existing League A provider already owns the real competition/season.
Issues #250/#251 must establish and implement reviewed, non-overlapping stage
ownership before manual B/C/D application. Do not duplicate the canonical
competition or disable League A to bypass the current authority rule. Later
play-off stages require their own explicit qualification.

Each correction retains its namespace, fixture and review-task IDs, moves the
next publication check, changes one kickoff,
and resolves the other fixture's away slot. It uses a new submission ID and
observation/preparation times. Later-round fixtures receive new permanent IDs;
corrections to an existing fixture's round or draw information keep its ID.

## Operator preparation checklist

1. Qualify the source, rights, exact season and stage/round coverage privately.
2. Extract or transcribe text/PDF in a separate preparation job. Review every
   participant, date, offset, round and status against the original document.
3. Resolve participants against the approved catalog; retain unresolved slots
   explicitly where the publication does not yet identify the participant.
4. Preserve fixture IDs from the ledger, construct one partial-scope package,
   and complete provenance, source-document checksums and the next review plan.
5. Run structural parsing and profile validation. Any invalid record rejects
   the package; do not silently salvage the remaining fixtures.
6. Once #250-#252 exist, submit to the intended instance, review its actual
   preview, approve that fingerprint and inspect the eventual import receipt.
7. At the separately recorded refresh cadence, prepare corrections using the
   same fixture IDs. A future API handover requires explicit correlation and
   source-owner transition; do not turn on simultaneous writers.

Raw PDFs, source datasets, real manifests, approvals and receipts remain in
private storage, such as the already ignored `manifests/private/` directory.
Only synthetic examples belong in Git or normal CI. Routine source refresh,
real staging qualification and production promotion are not performed by #249.

## Python API

```python
from pathlib import Path

from app.imports.manual_manifest import parse_manifest, validate_profile

payload = Path("manifests/private/reviewed.json").read_bytes()
manifest = parse_manifest(payload)
# trusted_profile is supplied from the reviewed catalog/configuration boundary.
validate_profile(manifest, trusted_profile)
```

`ManualSourceProfile` contains the exact namespace and `ManifestScope`, the
catalog `CompetitionFormat`, a frozenset of qualified `FixtureBoundary` values
and a frozenset of canonical participant keys. The caller must obtain this from
trusted configuration, never construct it from the untrusted file as proof of
qualification. Preview/authority checks and conversion to database numeric IDs
are intentionally deferred to #250/#251. No command in this guide imports data.
