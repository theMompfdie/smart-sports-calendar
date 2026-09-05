# ADR 0015: Import reviewed manual fixture manifests through the canonical lifecycle

- Status: Accepted (architecture only; implementation not yet available)
- Date: 2026-09-05
- Acceptance: Operator-approved merge of PR #256 on 2026-09-05
- Decision owners: SMART Sports Calendar maintainers
- Related issues: #168, #200, #249, #250, #251, #252, #253, #254, #255
- Follows: ADR 0004, ADR 0011

## Context

Phase 9 targets Austrian Bundesliga, FA Cup, EFL Cup and UEFA Conference
League fixtures without a qualified usable automated authority. A separately
obtained document may contain useful fixtures but does not establish stable
identity, complete coverage or permission to publish the source dataset.
Europa League remains on the later API track (#157/#158); API availability is
not assumed and it is not a fifth required manual target.

The application already has normalized fixture contracts, source mappings,
partial observation scopes, atomic fixture persistence and recoverable Outlook
synchronization. Reuse these boundaries. PDF/OCR/LLM extraction, spreadsheet
conversion and transcription remain operator-side preparation jobs. Only a
reviewed manifest enters the runtime. This ADR specifies the contract; it
neither enables a competition nor approves a source document.

## Decision

### One input format and one bounded writer

Use a UTF-8 JSON envelope with import_type fixture_schedule and schema_version 1
as the only v0.9 runtime exchange format.
Issue #249 owns the executable schema, parser, concrete templates and numeric
input
limits. Optional CSV authoring must convert to the same JSON contract before
review. Do not add PDF parsers or new dependencies in this architecture step.

One manifest belongs to exactly one sport, competition and season and one
configured manual source namespace. Stage/round restrictions are explicit
allowlists within that boundary; an omitted allowlist is not permission for
unqualified stages. Validate every fixture against the approved source profile.
All v1 manual observations are PARTIAL and removal-ineligible, even if the
operator believes the supplied schedule is complete. Reject completeness or
DELETE requests. A future destructive import mode needs a separate ADR and
source qualification; it is not required for v0.9.

Register an explicit manual authority for the selected competition/season.
Its enabled assignment is independent of periodic scheduling: no dummy timer
or automatically repeated file import. The manual command must not replace
all other source assignments during bootstrap. The scheduler must recognize
and preserve manual assignments on restart while scheduling only automated
sources. #251/#252 own this explicit extension to current registration and
assignment contracts. The manifest cannot grant itself authority or alter
configuration. Refuse apply if an automated writer owns that scope. Bootstrap
and verification data cannot overwrite an authoritative source or delete data.

### Phase 9.3 stage-authority extension (#250/#251)

The operator added Nations League B/C/D to the four original manual targets.
The seven target scopes share the same import contract. Nations League A/B/C/D
use one canonical competition and season; creating duplicate competitions
would conceal conflicting ownership and is rejected.

The operator reviewed this extension by merging PR #259 for #250. Issue #251
implements its migration, persisted grants and canonical enforcement; #252
adds the inbox worker. Existing broad grants remain broad until explicitly
reconfigured. Live source/stage qualification still belongs to #254.

Use explicit authority grants within one competition/season:

- A broad grant owns the entire season and conflicts with every other writer.
- A bounded grant owns a nonempty set of exact stage identifiers. No wildcard,
  implicit future stage or stage inferred from a job name is allowed.
- An automated writer uses its configured assignment identity. A manual writer
  includes its stable namespace, so B/C/D can share source_key `manual` while
  retaining separate ownership and review plans.
- Bounded grants may coexist only when their stage sets are disjoint. The same
  writer must consolidate its stages into one grant rather than duplicate it.
- Every fixture and an existing mapped event must remain within the writer's
  grant. A future round on a reminder task never extends that grant.
- Stage ownership must also constrain complete-snapshot removal evidence from
  automated providers. Manual imports remain PARTIAL and never remove by
  omission, even within their owned stages.

Legacy assignments migrate as broad grants, never automatically as stage A
because a current adapter happens to fetch A. Narrowing the existing League A
assignment requires explicit reviewed configuration and validation of existing
mappings and provider observation boundaries. Unknown or overlapping grants
fail closed. No production configuration is changed by this ADR extension.

Issue #251 must provide a deterministic non-destructive migration preserving
assignment identities, mappings and existing events. It must replace the
current one-authority-per-season uniqueness model with transactional broad
and stage-overlap enforcement, and account for multiple manual namespaces
sharing the same data source. Configuration synchronization must retain manual
assignments and verify old and new event boundaries; non-periodic manual jobs
must not require fabricated refresh intervals. Issue #252 must schedule only
actual automated jobs and the bounded inbox worker.

The pure `validate_stage_authorities` contract checks one proposed scope here.
The read-only preview still rejects a competing broad assignment;
passing that pure validator does not enable a second runtime writer. Tests
must prove League A remains untouched before B/C/D can be qualified in #254.

The preview shares the existing canonical target-value comparison, but does
not invoke its heuristic cross-source correlation. Issue #251 must integrate
manual operations using exact mappings only and verify preview/apply parity
inside the same write transaction. Otherwise a newly planned return fixture
could be correlated to a different existing match by the provider importer.

### Identity and catalog resolution

Use source_key `manual` and a permanently assigned `namespace` identifying the
operator-managed competition/season ledger. Give each fixture an opaque
`fixture_id` once and preserve it across every later document and correction.
Compose the source external ID from the namespace and fixture ID with an
unambiguous encoding selected in #249. Reject blank IDs, duplicate IDs and
collisions; never silently trim or case-fold identities. Namespace and fixture
ID are not filenames, timestamps, row numbers, round labels or team names.

Use existing source_mappings for the resulting stable external identity.
Resolve manifest sport/competition/season and participant keys through the
project catalog and explicit reviewed aliases/mappings. Portable manifests
must not contain staging/production SQLite numeric IDs. Unknown keys are
errors, not an instruction to create teams. Catalog additions use a separate
reviewed configuration/catalog step within the relevant implementation scope.
Derive display titles from the resolved canonical participants; source text
cannot supply arbitrary HTML or reserved application metadata.

For an existing stable fixture, correcting kickoff, participants, stage,
round, tie or leg preserves its canonical event and Outlook mapping. Changing
the namespace or fixture ID does not correct an existing event: it is a new
identity and requires explicit correlation review when a collision is
suspected. A pre-existing fixture from another source must not be matched by
title, teams or kickoff. Reject conflicting ownership until a reviewed mapping
and handover resolves it.

### Field and validation matrix

The following are semantic fields, not a ready-to-import example. #249 fixes
the exact JSON nesting, lengths and executable schema without weakening these
rules. Optional values use explicit null; omission must not act as an implicit
patch of an existing event. Each fixture describes its reviewed target state.

#### import_type, schema_version

Only fixture_schedule with integer version 1; reject unknown versions, unknown
fields, duplicate JSON keys, non-finite numbers and invalid types.

#### namespace, fixture_id

Nonempty stable opaque identifiers; unique fixture IDs per manifest; reject
duplicates even if their content agrees.

#### sport_key, competition_key, season_key

Resolve one configured catalog scope; reject missing, wrong-season or
mixed-competition input.

#### scope/profile

Explicit qualified stage/round coverage; PARTIAL only; empty fixture lists are
rejected as accidental input, not interpreted as deletion.

#### competition format

Catalog-owned league, knockout_cup or hybrid_tournament; input cannot override
it.

#### stage, round_name, stage_kind

Use approved normalized identifiers. Hybrid rounds require stage; typed stage
kind follows ADR 0011. League splits use stage identifiers without illegal
hybrid-only stage kinds.

#### group, tie_key, leg

Optional approved diagnostics; first/second legs require a stable source-scoped
tie key. Group, tie and leg never replace fixture identity. Unqualified
combinations fail validation.

#### home, away

Exactly one slot per role. Resolved slots require known distinct participant
keys; unresolved slots have no participant key. Never create placeholder teams
or infer winners.

#### kickoff, timezone, kickoff_confirmed

Confirmed kickoff requires an ISO 8601 timestamp with offset and a known IANA
zone consistent with that instant. Normalize to UTC; render operationally in
Europe/Vienna. Reject naive times, nonexistent local times and offset/zone
disagreement. An explicit offset disambiguates a repeated DST hour. Unknown
kickoff uses null and false, never midnight invented from a date.

#### status

Allow scheduled, postponed and cancelled for this calendar-import scope. Reject
unknown/live-score states. A cancellation must identify an existing mapped
fixture. A correction restoring cancelled to scheduled is an explicit reviewed
UPDATE, never inferred from omission.

#### venue/city

Optional bounded plain text; explicit null semantics and normalized comparison
must be documented. No arbitrary event metadata or HTML passthrough.

#### source reference and attribution

Record a non-secret document identifier, issuer and rights/attribution decision
reference. Runtime must not fetch source URLs. Private source artifacts stay
outside Git and public logs.

#### source document checksum

SHA-256 of the retained original when available; otherwise record the
preparation provenance and why no original byte artifact exists. Never fabricate
evidence.

#### observed_at, prepared_at

Aware UTC timestamps for source observation and preparation; reject invalid
ordering. Re-import time is not source observation time.

#### approval

Local operator identity and aware UTC approval time bound to the exact manifest
SHA-256 and preview fingerprint; stored outside the manifest to avoid a
self-referential hash. Reject missing/mismatched approval at apply.

#### manifest fingerprint

SHA-256 of the exact bytes read once. Formatting changes require fresh
preview/approval; compare canonical fixture fields separately for idempotency.

Any malformed, conflicting or ambiguous record rejects the whole manifest
before canonical changes. An explicitly unresolved slot or intentionally
unknown kickoff is valid incomplete information, not ambiguous extraction.
Report DEFER separately from validation errors. Do not silently drop it.

Follow the existing lifecycle for unresolved participants: DEFER the fixture
without changing its canonical event if one exists. With resolved participants
and unknown kickoff, defer a new fixture; an existing fixture may retain its
last confirmed time while recording a reviewed postponement. Explicit
cancellation must carry resolved identity/participant context and must not be
silently deferred. Preview explains retained timestamps. No unconfirmed time
may invent a new Outlook event. #250/#251 must test this mapping against the
existing repository behavior before exposing apply.

### Preview, apply and local atomicity

Preview performs schema, catalog, scope, authority and lifecycle validation
against a read-only snapshot without initialization migrations, receipts,
source-assignment writes or Graph calls. It reports CREATE, UPDATE, SKIP,
CANCEL and DEFER per fixture with reasons and summary counts. DELETE is always
unavailable. The preview function returns a report without writes; the worker
may subsequently persist that report as private staging bookkeeping.

Bind the report to exact manifest bytes, schema/validator version, target
instance/database identity, effective configuration/authority profile and a
deterministic digest of the relevant catalog, mapping and canonical state.
Include absence of proposed new mappings, not only revisions of existing rows.
Do not use database mtime or an unrelated full-database hash as a correctness
check. The approval explicitly covers this plan and these bytes.

Apply reads the file once, verifies approval, acquires the database write
transaction, revalidates the relevant preconditions and recalculates the plan.
If the reviewed state or intended operations changed, abort without canonical
writes and require another preview. Never silently substitute a fresh plan.
All accepted canonical mutations, source mappings, staged APPLIED state and the
successful import
receipt are committed on one SQLite connection/transaction. Roll back the
entire batch on any error. DEFER records are explicit accepted outcomes with
no corresponding canonical mutation; they do not permit partial acceptance
of invalid records.

The existing FixtureImportRepository.import_observation owns BEGIN IMMEDIATE
and commit internally. A separate receipt repository called afterwards would
not be atomic. #251 must provide a focused transaction-owned extension so the
receipt and fixture import share the same commit, retaining ordinary provider
behavior and repository isolation. New durable receipt storage requires a
deterministic migration and idempotent initialization, not table recreation.

A receipt, linked to its staged batch, records manifest/plan fingerprints,
namespace and scope, source and
approval provenance, accepted/deferred operation counts and per-ID results,
commit time and the canonical outcome. Observation/receipt metadata must not
enter event content hashes and cause Outlook updates. An unchanged replay is
SKIP for unchanged eligible fixtures and can record another audited attempt;
receipt growth is permitted, canonical revision churn is not. Distinguish
canonical committed from Outlook converged. Before-commit failure is not a
successful receipt; sanitized external diagnostics may report the failure.
A crash after commit can be resolved by looking up the committed receipt.

Microsoft Graph is outside the SQLite transaction. After canonical commit,
reuse existing synchronization selection, mappings and retry behavior. A Graph
failure does not roll back committed canonical data or report convergence.
Backups include the database with receipts/mappings and private manifests and
approvals under operator-controlled retention. Validate restore on an isolated
instance with no shared writable database or calendar.

### Durable staging and Docker-host execution

Accept submissions at any time into a persistent import inbox. The host command
writes an immutable manifest to a temporary file and atomically renames it into
the ready inbox on the same filesystem. Incomplete uploads are never consumed.
The command writes no canonical database rows and starts no second scheduler
or Graph client. Use private mounted storage, bounded file sizes, generated
safe filenames and checksums; do not follow symlinks or manifest-supplied paths.

Add an import_batches table as durable package-level staging. Store the exact
accepted manifest bytes and fingerprint, import type/version, scope, state,
preview/precondition
fingerprint, approval reference, attempt/error summary and receipt reference.
The filesystem is a transport inbox; after acceptance the database copy is the
immutable processing input. A deterministic migration creates this storage.
Do not duplicate every fixture into another relational staging table in v0.9:
strict parsing can produce transient normalized rows from the retained package.
Per-row editing and an import editor are outside scope; corrections submit a
new immutable package. Submission identity deduplicates transport redelivery;
an intentional replay is a new submission and still causes no canonical churn.

Use this state machine:

- RECEIVED: durable package accepted, no canonical mutation.
- AWAITING_APPROVAL: validation and write-free canonical preview succeeded;
  the private preview and its fingerprint are available to the operator.
- REJECTED: malformed/ambiguous input, no automatic acceptance of valid rows.
- APPROVED: an explicit operator approval command references the package,
  exact manifest hash, target instance and current preview fingerprint.
- NEEDS_REVIEW: authority/state changed after preview; generate another preview
  and require fresh approval, never silently approve a recalculated plan.
- APPLIED: canonical batch, receipt and this state commit in one transaction.
- RETRYABLE_FAILURE: bounded transient failure before commit; preserve the
  approved input and retry with precondition validation. Permanent failures
  require operator action and do not loop indefinitely.

The approval command uses the same atomic inbox transport for a small approval
record; only the application worker writes batch state. This is a local operator
workflow protected by host/volume permissions, not a remote authentication API.
No public HTTP endpoint, message broker or extra service is needed.

Register one bounded import-worker job in the existing scheduler. Its current
run_jobs loop calls jobs sequentially, so manual canonical application can run
between provider and calendar jobs in the same process. Process a bounded
number/size of packages per turn and preserve unrelated jobs after failures.
Manual authority is non-periodic; the inbox worker's polling interval is not an
authoritative source refresh interval. No file is reapplied merely by polling.

Claim and revalidate an approved batch inside BEGIN IMMEDIATE, and commit its
APPLIED state with the canonical changes and receipt. No persistent PROCESSING
state is needed when the whole operation is one transaction: interruption
rolls back to the prior durable state. On restart reconcile inbox redeliveries
by submission ID, resume pending batches, and inspect APPLIED before any retry.
A crash after commit but before inbox cleanup must not apply the batch twice.
An absent or modified inbox file cannot change an already accepted payload.

Submission/status commands must not initialize or synchronize assignments,
recover runs, create canonical rows or acquire Graph credentials. Package
validation may persist queue state and its report, but preview itself performs
no canonical or Graph writes; a standalone preview remains database read-only.
This explicitly distinguishes staging bookkeeping from importing fixtures.

One application instance still owns each writable database and calendar. The
worker does not make arbitrary concurrent direct database import safe, and
threading.Lock alone is not a cross-process guarantee. No additional writer
container is introduced. Stopping the instance remains necessary for the
existing backup/upgrade procedures, not for routine file submission. The
worker must wait for migrations/bootstrap to complete before processing.

Exact submission, status and approval commands and mounted inbox paths belong
to #252. A rejected package remains inspectable privately; retention/cleanup
must preserve audit references and distinguish database acceptance from later
Outlook convergence. Tests cover partial uploads, duplicate delivery, stale
approval, FIFO fairness across packages, restart and commit/cleanup crashes.

### Extension boundary for future result imports

Separate the immutable import envelope from its domain payload. The envelope
contains `import_type`, `schema_version`, submission identity, scope,
provenance,
fingerprints and approval context. v0.9 accepts only `fixture_schedule` schema
version 1.
Reject unsupported types or type/version combinations before approval or
canonical mutation; do not infer the type from payload fields or silently route
it to the fixture importer.

Package transport, durable state transitions, approval binding, retry and audit
may be reused by a later result-import handler. Dispatch through an explicit
allowlist in the application container. A simple type-to-handler mapping is
sufficient; no plugin framework or generic field-merging engine is needed.
Each handler owns parsing, domain validation, planning and transaction-scoped
persistence, and must declare its supported payload version. Preview/approval
fingerprints include the type, so a schedule approval cannot authorize results.

A future `fixture_result` type must correlate through the existing stable
fixture/source identity and a reviewed ownership contract. It must not create
another fixture, replace a manual fixture ID, overwrite schedule fields or
change Outlook content merely because scores were submitted. Result revisions,
corrections, final/provisional semantics, source authority and optional calendar
presentation need a separate domain decision and tests before activation.
Receipt metadata remains separate from event-content hashing.

Source ownership for schedules is not automatically ownership for results.
Do not add result tables, score columns, result status enums, active result
handlers or result-source permissions in Phase 9. The extension point preserves
the future option without asserting that the current sports_events status field
or provider contract can represent a result. A later issue must define that
model and its interaction with the existing single-writer schedule rule.

### Target qualification and examples

#### Austrian Bundesliga (#125)

League with explicit regular/split-stage identifiers; no inference of later
participants or fixtures from standings.

#### FA Cup (#126)

Round-based cup; new draws and any source-qualified replay fixtures get separate
stable identities.

#### EFL Cup (#127)

Cup rounds and source-qualified single/two-leg ties; each fixture leg keeps its
own ID.

#### UEFA Conference League (#160/#161)

Hybrid stages, league phase and draw-dependent knockout/tie/leg data within the
approved season/stage profile.

These are modeling requirements, not assertions of a current season's official
format or source availability. #254 verifies exact competition rules, source
rights, coverage and refresh responsibility before each target's real import.
A successful pilot does not qualify the other three. Release notes must expose
any delivery gap rather than silently reduce the four-target commitment.

Synthetic walkthrough: namespace demo-cup-2030, fixture ID m001, resolved
catalog participants demo-home/demo-away. These are illustrative identifiers,
not provisioned catalog entries or a real dataset.

1. Initial approved scheduled fixture: CREATE once; record canonical mapping
   and receipt. Ordinary synchronization creates its Outlook event.
2. Exact unchanged replay after fresh preview: SKIP; retain event/mapping and
   content revision. A new receipt is allowed; no unnecessary Graph update.
3. Correct the kickoff or resolved participant for m001: UPDATE that event,
   retaining its stable mapping. A later round-label correction also keeps ID.
4. Publish m002 with an explicitly unresolved away slot: DEFER without a
   placeholder team. When resolved and timed, the same ID can CREATE once.
5. Explicitly cancel mapped m001 with valid participant context: CANCEL.
   An unchanged cancellation replay is SKIP. Reinstatement needs a separately
   reviewed scheduled state and produces UPDATE.
6. Omit m001 from the next partial document: no operation on m001. Its absence
   is never evidence of cancellation or deletion.
7. A later API becomes qualified: stop the writer, review a one-to-one mapping
   of old manual IDs to stable provider IDs, preserve canonical/Outlook IDs,
   deactivate manual ownership, activate the qualified provider, and verify
   preview/replay behavior before restart. Conflicting or ambiguous mappings
   block handover. No automated handover implementation is included in v0.9;
   it requires a separate reviewed change and staging evidence.

### Source provenance and publication

Preparation records issuer, observation date, source/document reference and
operator rights review. A machine extraction is only a candidate transcription:
review participants, dates, timezones, rounds and status against the document.
Never put private PDFs, full licensed datasets, credentials, secret-bearing
URLs or raw source inventories in Git, CI, issues or release artifacts. Public
examples are synthetic. Logs use safe counts and error categories; detailed
receipts and approvals remain private to the configured instance. Source URLs
are references only and never a runtime download instruction.

Production use follows publication of verified v0.9.0-beta.1, separate manual
promotion authorization and closure of applicable production blockers. #233
is still an independently tracked blocker; a beta tag alone does not clear it.

## Implementation map and acceptance ownership

### Issue #249

app/providers/contracts.py and app/domain/competition_lifecycle.py: strict
manifest parser and portable catalog mapping contract

Schema/limits, duplicate fields, DST, synthetic examples for four targets

### Issue #250

Read-side repositories plus focused application planning service

No DB/Graph writes; deterministic decisions; stale plan and wrong-target
rejection

### Issue #251

app/application/api_football_fixture_import_service.py,
app/database/fixture_import_repository.py, source_mappings_repository.py and
source_assignments_repository.py

Durable import_batches and shared transaction for
APPLIED/receipt/mappings/events; migration/rollback, replay and manual authority

### Issue #252

app/application/container.py, source_registry.py and inbox
submission/status/approval commands and scheduled worker

Atomic inbox delivery, bounded sequential processing, stale approvals,
restart/deduplication and no extra writer; Compose instructions

### Issue #253

Existing repository/application/synchronization tests and
app/synchronization/synchronization_orchestrator.py

SQLite-to-mocked-Graph lifecycle, four-profile isolation, failure/restart and
backup/restore regression coverage

### Issue #254

Isolated staging runbook and per-source qualification matrix

All four approved scopes, real reviewed data, Outlook readback and periodic
refresh responsibilities

### Issue #255

README, operations/security/source policy and release documentation

Exact candidate gates, accurate limitations and separately authorized signed
publication/promotion

The ApiFootballFixtureImportService name is historical: the container already
constructs it with several source keys. Reuse its provider-neutral behavior;
a broad rename or synchronization-engine redesign is not needed for this ADR.
Each implementation issue owns its own tests; #253 adds cross-component
coverage and is not a reason to defer regression tests.

## Alternatives and consequences

- Direct PDF-to-SQLite or PDF-to-Outlook writes bypass review and stable
  correlation and are rejected.
- Title/time matching and generated IDs per file would duplicate rescheduled
  fixtures and are rejected.
- Inferring removal from a missing row is unsafe for partial schedules and is
  rejected for all v1 manifests.
- A stopped-instance one-shot import is simpler, but interrupts routine
operation.
  Durable staging with an in-process worker meets the requirement to submit at
  any time. A separate broker/service or per-fixture editing database adds no
  necessary value for the v0.9 package workflow.
- JSON is less convenient than a spreadsheet for authoring but gives one typed,
  versioned runtime contract. Separate converters preserve that boundary.
- This decision requires a small receipt migration and assignment/transaction
  extensions in later issues. This ADR adds no runtime code, dependency, schema
  migration or production configuration in #168.

## Phase 9.4 implementation checkpoint (#251)

The transactional backend now persists immutable import batches and receipts,
accepted review plans and durable database identity. The canonical importer
exposes a caller-owned transaction and disables heuristic correlation for manual
namespaces. Configuration, attribution lookup and revision triggers honor the
stage grants described above, while preserving legacy broad ownership.
See [atomic manual import persistence](../manual-import-apply.md) for the actual
service lifecycle and remaining #252-#254 operational qualification boundaries.
No inbox worker, update-appointment delivery or production rollout is claimed.

## Inbox and review-appointment implementation checkpoint

Issue #252 implements the optional in-process worker and file-only operator CLI.
The [workflow guide](../manual-import-workflow.md) documents persistent mounts,
trusted startup profiles, explicit approval, status exports and retention.
An OS lifetime lock rejects a second application process on the same database.
It does not establish distributed locking or authorize shared writable volumes.

Migration 014 stores separate review-appointment mappings and creation intent.
Overdue catch-up time is persisted once; unchanged replay/restart does not move
it. Graph calls follow committed canonical imports and retain retryable intent.
Cross-component and live seven-scope qualification remain #253/#254 work.
