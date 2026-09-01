# Rights-controlled media asset registry

Status: Implemented registry, validation, normalization, local operator
administration, and Outlook inline-attachment reconciliation for Phase 8.7 and
Phase 8.8 (#212 and #213).

SMART Sports Calendar keeps media metadata and approval history in SQLite while
storing normalized binary content below the persistent `MEDIA_ROOT`. The
default container path is `/data/media`, so the registry and its files share
the same project-scoped persistent volume without storing binary data in
SQLite.

## Rights and publication boundary

Public availability is not permission to copy or use a logo. Fixture-data
rights never imply rights to a competition mark, club crest, photograph, or
other media. Every import therefore requires both a source reference and at
least one of:

- a named licence whose terms cover the intended use; or
- a private permission-record reference maintained by the operator.

An imported version is pending and inactive until an operator separately
approves it. Only one version of an asset key can be active. Replacing an asset
creates a new pending version and leaves the current approved version active
until the replacement is approved. Approval then atomically deactivates the
old version and preserves the complete version history. `disable` deactivates
an asset without deleting its audit record or stored content.

Source and permission references can contain private operational information.
They remain in the private SQLite database and its backups. The CLI reports
only whether a permission reference exists; it does not print that value, the
source reference, storage path, database path, or source file path.

Generic trophy and final artwork may use independently authored project assets
under the repository's MIT licence. Provider or team artwork must never be
labelled as project-owned. No command performs an internet search or downloads
a remote logo.

## Outlook selection and reconciliation

Only approved active assets are eligible. Selection uses canonical database
owners, never provider display text or insertion order:

- competition owner plus `logo` variant for the event header;
- participant owner plus `logo` variant for the canonical `home` and `away`
  roles;
- project owner `smart_sports_calendar`, preferring `final` and falling back to
  `trophy`, for an exact normalized final-stage name.

The final allowlist is deliberately exact (`final`, `finale`, `finals`,
`grand_final`, `championship`, `championship_game`, and `super_bowl`). A
semifinal is not a final. Ambiguous active assets for one owner and variant
fail closed instead of being selected by row order. Approval and disable
operations atomically increment only the affected calendar mappings'
presentation revisions so the scheduler converges them promptly.

Migration `012_create_calendar_event_asset_attachments` stores one row per
calendar mapping and semantic slot. It retains desired, pending, synchronized,
and obsolete asset/attachment identity plus hashes, content IDs, attempts,
timestamps, status, and a sanitized failure class. The local normalized file
is stored once, while Microsoft Graph receives a distinct inline attachment
for every Outlook event.

Reconciliation always keeps the text event authoritative and uses this order:

1. create or update the complete text event;
2. recover an already uploaded attachment by its stable pending content ID, or
   upload the approved PNG;
3. patch the HTML body with a bounded 30 x 30 `cid:` image reference;
4. delete the obsolete attachment only after the body switch succeeds.

An unchanged cycle performs no attachment upload, event patch, or deletion.
Replacement uploads new content before switching the body and removes the old
attachment afterward. A restart between those steps resumes from SQLite and
remote content-ID evidence. Missing, disabled, corrupt, oversized, ambiguous,
or Graph-rejected media leaves a complete text presentation and retryable
state; it never changes the core fixture synchronization result.

Inline uploads are restricted to PNG and must remain below the Microsoft Graph
3 MB simple-attachment boundary. Registry normalization already enforces a
stricter 1 MiB output limit. Attachment listing is page-bounded, and HTTP 429,
503, and 504 responses use bounded retries with `Retry-After` support. Logs
contain only slot and failure class, never bytes, rights records, tokens, or
secret-bearing URLs.

## Registry identity and storage

Each stable `asset_key` belongs to exactly one canonical owner and variant:

- `project`, with an operator-defined project key;
- `sport`, resolved by canonical `sport_key`;
- `competition`, resolved by canonical `competition_key`; or
- `participant`, resolved by canonical `participant_key`.

Keys use lowercase ASCII letters, digits, dots, underscores, and hyphens, and
must begin with a letter or digit. Ownership and variant cannot change across
versions of one asset key. Use a new key when the semantic identity changes.

The importer accepts a local PNG or JPEG, decodes it, rejects animation, strips
metadata, preserves aspect ratio, centres it on a transparent canvas, and
re-encodes it as a deterministic 60 x 60 PNG. Default limits are 10 MiB and
4096 x 4096 pixels for input and 1 MiB for normalized output. Malformed,
unsupported, oversized, decompression-dangerous, and path-traversing inputs
fail closed.

Normalized files use a content-addressed path below `MEDIA_ROOT`:

```text
assets/<first-two-sha256-characters>/<sha256>.png
```

Identical normalized content is stored once even when multiple logical assets
reference it. Approval verifies the stored size and SHA-256 again. A missing,
changed, non-file, symlinked, or out-of-root target cannot become active.

## Operator CLI

Run the commands against explicit paths. The CLI initializes pending database
migrations but does not contact Microsoft Graph, a sports provider, or the
internet.

Import project-owned final artwork as a pending version:

```console
python -m app.operations.media_assets --database /data/sports.db --media-root /data/media import --asset-key project.final.trophy --owner-type project --owner-key smart_sports_calendar --variant trophy --file /operator-input/final-trophy.png --source-reference "SMART Sports Calendar project artwork" --license-name MIT --attribution "SMART Sports Calendar"
```

Import a team logo whose private permission is recorded outside the
repository:

```console
python -m app.operations.media_assets --database /data/sports.db --media-root /data/media import --asset-key team.manchester_united.logo --owner-type participant --owner-key manchester_united --variant logo --file /operator-input/manchester-united.png --source-reference "Private rights review record" --permission-reference "rights-record-2026-001" --attribution "Used with permission"
```

Review the pending output, then approve and activate the exact version:

```console
python -m app.operations.media_assets --database /data/sports.db --media-root /data/media approve --asset-key team.manchester_united.logo --version 1 --reviewer operator-name
```

`replace` follows the same arguments as `import` and creates the next pending
version when its normalized content or rights metadata differs:

```console
python -m app.operations.media_assets --database /data/sports.db --media-root /data/media replace --asset-key team.manchester_united.logo --owner-type participant --owner-key manchester_united --variant logo --file /operator-input/manchester-united-2027.png --source-reference "Private replacement review" --permission-reference "rights-record-2027-004" --attribution "Used with permission"
```

List active assets, inspect all retained versions, or disable one active key:

```console
python -m app.operations.media_assets --database /data/sports.db --media-root /data/media list
python -m app.operations.media_assets --database /data/sports.db --media-root /data/media list --include-inactive
python -m app.operations.media_assets --database /data/sports.db --media-root /data/media disable --asset-key team.manchester_united.logo
```

Keep source files and private rights records outside the repository, Docker
build context, release assets, CI artifacts, screenshots, and logs.

## Dependency decision

Image decoding and safe re-encoding are not provided by the Python standard
library. Phase 8 therefore pins Pillow `12.3.0` for one bounded purpose:
decoding PNG/JPEG inputs and writing normalized PNG files. Pillow publishes
CPython 3.13 wheels, uses the permissive HPND/MIT-CMU licence, and maintains
security fixes in current releases. Dependency updates still require the
normal review, test, and image-verification workflow.

Primary references:

- [Pillow project metadata and release files](https://pypi.org/project/pillow/)
- [Pillow releases and security notes](https://github.com/python-pillow/Pillow/releases)
- [Pillow licence](https://github.com/python-pillow/Pillow/blob/main/LICENSE)
- [Microsoft Graph: add attachment to an event](https://learn.microsoft.com/en-us/graph/api/event-post-attachments?view=graph-rest-1.0)
- [Microsoft Graph: fileAttachment resource](https://learn.microsoft.com/en-us/graph/api/resources/fileattachment?view=graph-rest-1.0)
- [Microsoft Graph: delete attachment](https://learn.microsoft.com/en-us/graph/api/attachment-delete?view=graph-rest-1.0)
- [Microsoft Graph throttling guidance](https://learn.microsoft.com/en-us/graph/throttling)

## Backup, restore, and rollback

The SQLite registry and `MEDIA_ROOT` form one recoverable state unit. Stop the
exact application instance and copy the complete project-scoped `/data`
contents, not only `sports.db`. Keep the backup outside the Docker volume and
all public artifacts. Record a private integrity manifest for the database and
every media file, and run SQLite `PRAGMA quick_check` against the copied
database.

Test restoration in an isolated volume with no active instance targeting the
same Outlook calendar. Restore the database and media directory from the same
snapshot, verify the integrity manifest, initialize one application instance,
and list all media versions. Never combine a current database with an older
media directory or the reverse.

Migrations `011_create_media_assets` and
`012_create_calendar_event_asset_attachments` are forward-only, deterministic,
and preserve all existing application data. There is no destructive downgrade.
If rollback to pre-migration code is required, stop the instance and restore
both the verified pre-upgrade database and media directory from their matching
snapshot before starting the previously verified application version. Restore
the Outlook calendar from the matching operational backup if the rollback must
also reverse already synchronized inline attachments.
