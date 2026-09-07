# Logo rights preparation workflow

Status: Operator guidance and templates for issue #240. No individual logo
has been researched, cleared, acquired, or enabled by this documentation.
Real logos are optional for v1.0.0; text-only presentation or reviewed
project-owned artwork remains the release fallback.

## Start with the templates

Copy the [rights catalog template](templates/logo-rights-catalog.md) into a
private records directory outside the checkout and Docker build context.
Create one record per exact asset. Use the
[permission email template](templates/logo-permission-request.md) when
clarification or permission is needed. Replace all placeholders and review
the actual deployment before sending.

These are preparation documents, not permission grants or runtime import
files. Sending requests, accepting terms, paying fees, acquiring assets and
activating them are separate operator actions.

## Review and obtain an asset

1. Select only an image you actually want. Record its subject, exact variant,
   official source page and version if known. Club crests, competition marks,
   trophy artwork and photographs are separate assets. Rights to fixture data
   do not establish rights to their images.
2. Describe the actual use in the catalog matrix. The template assumes one
   operator's private, non-commercial, unshared calendar. Include server
   storage, Microsoft 365/Outlook copies, transformations and private backups.
   Public screenshots, documentation and distribution need separate decisions.
3. Find the official rights holder's licensing or brand guidelines. Record the
   authoritative page, date, relevant terms and private evidence reference.
   An accessible download, fan site or image from a fixture provider is not
   evidence of permission for this deployment.
4. Check whether the terms or an applicable documented legal basis cover each
   intended use. Record copyright and trademark conditions, attribution,
   modification limits, territory, duration, revocation and fees. Do not infer
   approval merely from private or non-commercial use. If applicability is
   uncertain, leave the decision pending and obtain suitable clarification,
   including qualified legal advice where necessary.
5. Where coverage is unclear, find the official licensing/brand contact through
   the rights holder's website. Verify responsibility before using the email
   template. Request referral if needed. Track requests and replies privately;
   silence is not approval.
6. Record the decision for each use of the exact asset. Preserve the grant or
   relevant terms, reviewer, date and conditions. A grant for one operator is
   not transferable permission for all users of this open-source project.
7. Once acquisition and processing are covered, obtain the exact file through
   the permitted official download or rights-holder delivery channel. Record
   its original filename, version and SHA-256. Review any difference from the
   asset or terms originally approved before proceeding.
8. Follow the registry handoff only when the intended deployment is fully
   covered. Otherwise retain the fallback and keep the image inactive.

## Keep requests focused

Review existing terms first; do not request duplicate permission where
documented coverage is already sufficient. Prioritize wanted assets instead
of contacting every club. Group assets only where the same recipient actually
controls the relevant rights. A league does not automatically control club
logos or a photographer's image.

Track recipients, exact assets, request dates, replies and an operator-selected
follow-up date privately to avoid duplicate outreach. Request only the use you
need. Review later sharing or publication separately from private use.

## Evidence and privacy

Keep populated catalogs, contact details, correspondence, permission documents,
restricted images and evidence backups outside the repository, Docker build
context, release assets, CI artifacts, screenshots and logs. Connect private
evidence to registry metadata using a stable opaque record ID. Do not publish
secret-bearing source URLs.

Public documents contain only blank templates and sanitized decisions, if
later documented. Restrict private records and backups to the operator.
Retain evidence while the image is used and for any further period required
by the applicable terms; record deletion and retention conditions explicitly.

## Registry handoff and ongoing review

Use the existing [media asset registry](media-asset-registry.md) for commands.
The catalog is a manual record; it neither changes runtime approval states nor
automatically enforces licence conditions.

Confirm permission for the actual processing: PNG/JPEG input is decoded,
metadata is stripped, aspect ratio is preserved, and the image is centred on
a transparent 60 x 60 canvas and re-encoded as PNG. Outlook displays a bounded
30 x 30 image and receives a separate inline attachment per affected event.
Verify required attribution can be satisfied after metadata removal. Do not
approve unsupported conditions.

Supply the source reference, covering licence name or private permission
reference, and required attribution. Import creates a pending inactive
version. Record its normalized SHA-256 and version beside the original hash,
inspect the output, and separately approve only the reviewed version for the
configured deployment. A hash identifies content; it proves no rights.

Set an operator reminder for recheck/expiry; the registry does not enforce
licence deadlines. Recheck changed terms, replacement images, changed use,
expiry and revocation. Disable the asset when coverage ends or is uncertain
and verify synchronization removes obsolete Outlook media.

Disabling retains registry history and stored files. It does not erase
backups or previously shared copies. Handle required removal from retained
files, Microsoft 365 and backups separately under the applicable conditions.
Do not restore and reactivate an expired grant from an old backup.

## Completion and release boundary

Issue #240 delivers this guide, the catalog template and the email template.
It does not require a populated inventory, individual permissions or external
responses. Later clearance is separate operator work. Unreviewed, pending and
rejected images remain disabled and undistributed.

For the v1.0 release review, record that preparation is available and individual
third-party images remain excluded unless separately cleared. Public
repository, container, documentation and screenshot uses need their own
evidence. Existing registry enforcement and other release gates stay unchanged.
