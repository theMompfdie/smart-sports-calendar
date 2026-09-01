# Public Repository and Runtime Data Safety

## Status and purpose

This policy is the publication boundary for SMART Sports Calendar. The source
code may be published under the repository's MIT License. Provider data,
credentials, private calendar content, generated databases, backups, exports,
and restricted source documents are separate assets and are not granted that
software licence.

Repository publication is not approved merely because the current working
tree is clean. The complete checklist below must pass immediately before any
visibility change or public release. Changing repository visibility remains a
separate operator action.

## Cost and source approval policy

An automated production authority must have EUR 0 recurring and EUR 0
mandatory one-time source cost. Free registration and a free credential are
acceptable only when no payment method, paid trial, later mandatory
subscription, usage charge, or licence fee is required.

Every competition and season needs a documented source decision covering:

- permitted automated access and the exact competition boundary;
- stable source identity and fail-closed completeness behavior;
- attribution, caching, retention, cancellation, and exit obligations;
- private-calendar use and any redistribution restrictions;
- quota and operational suitability; and
- a material-terms review date and reconsideration trigger.

If no compliant source exists, the competition remains deferred. A lawfully
obtained document may be prepared as an operator-reviewed manifest only under
issue #168. PDF, OCR, spreadsheet, or webpage extraction never writes directly
to SQLite or Outlook and never bypasses a source-specific rights review.

## Current provider boundaries

| Source | Automated use | Private persistence | Attribution and exit | Public redistribution |
| --- | --- | --- | --- | --- |
| football-data.org API v4 | Only qualified free-tier competition scopes | Operator SQLite and dedicated private Outlook calendar | Display `Football data provided by the Football-Data.org API`; stop referencing obtained data according to the reviewed cancellation terms | No raw payload, fixture inventory, database, export, or provider asset is published |
| OpenLigaDB API | Only explicitly selected competition scopes; community data remains fail-closed and normally removal-disabled | Operator SQLite and dedicated private Outlook calendar | Display the selected OpenLigaDB and ODbL 1.0 attribution; re-review an adapted-database distribution separately | No database is bundled; any future public produced work or adapted database needs a separate ODbL review |
| Official ÖFB iCalendar feed | Only the qualified private feed and bounded competition scope | Operator SQLite and dedicated private Outlook calendar | Preserve source attribution and disable collection if the reviewed private-use boundary changes | Feed URL, raw calendar, fixture inventory, database, and calendar export remain private |
| API-Football v3 | Existing integration is disabled by default and is not approval for a new authority | No unqualified production collection | Competition-specific permission and attribution must be approved before enablement | No raw response, copied catalog, fixture inventory, logo, or media asset is published |

Source-specific ADRs and qualification records remain controlling when they
are stricter than this summary. Logos, crests, photographs, and other media
rights are always separate from fixture-data rights.

## Repository boundary

The repository may contain:

- application code, schema migrations, and provider adapters;
- documentation, ADRs, aggregate evidence, and non-secret fingerprints;
- placeholders in `.env.example`; and
- synthetic, independently authored, or explicitly redistributable tests.

It must not contain:

- API keys, client secrets, tokens, authorization headers, private keys, or
  secret-bearing feed URLs;
- live or raw provider responses, copied fixture inventories, participant-ID
  exports, or account metadata;
- SQLite databases, journals, backups, calendar exports, private manifests,
  or restricted source documents;
- Outlook event IDs, calendar IDs, private event content, or production logs;
  or
- provider logos, photographs, or media assets without separate permission.

The Phase 8 media registry stores normalized binaries under the private
operator-controlled `MEDIA_ROOT` and stores source, licence, permission, and
approval records in SQLite. Neither location belongs in Git, Docker build
contexts, release assets, CI artifacts, screenshots, or public backups.
Synthetic or independently authored project artwork may be tracked only when
its provenance and redistributable licence are explicit. See
[Rights-controlled media asset registry](media-asset-registry.md).

The API-Football response-shape fixtures in `tests/fixtures/api_football` are
repository-authored deterministic test material. Their adjacent
`catalog_metadata.json` records that no live provider request was used. Any
new structured fixture must carry equivalent provenance and sanitization
evidence and must not be copied from a live response.

## Automated controls

Run the standard-library-only publication check from the repository root:

```bash
python scripts/check_publication_safety.py
```

The check inspects tracked paths, required Git and Docker exclusions, common
credential forms, sensitive configuration assignments, databases, SQLite side
files, calendar exports, private keys, backups, private manifests, and named
provider/export artifacts. Findings show a path and category but never echo a
suspected secret value. CI runs the same command.

`.gitignore` protects the normal working tree. `.dockerignore` separately
keeps private runtime classes, tests, documents, operator files, and unrelated
development artifacts out of the Docker build context. The Dockerfile copies
only `requirements.txt` and `app/`; the runtime database stays on `/data` in a
persistent operator-controlled volume. The default `/data/media` root shares
that isolated volume and is never copied into the image.

These controls reduce accidental disclosure but do not prove that Git history,
GitHub discussions, external artifacts, or an already pushed image is clean.

## Public-visibility checklist

Perform this review from the exact commit intended to become public:

1. Verify the working tree is clean and the commit is reviewed and signed.
2. Run `python scripts/check_publication_safety.py`, `ruff check .`,
   `ruff format --check .`, and `pytest`.
3. Inspect `git ls-files` for unexpected datasets, archives, generated files,
   credentials, backups, exports, documents, and media.
4. Scan the complete Git history with an approved secret scanner and manually
   review historical paths for deleted `.env`, database, calendar, backup,
   payload, manifest, archive, and export files.
5. Review open and closed issues, pull requests, comments, screenshots, and
   attachments for secrets, raw provider data, database identifiers, Outlook
   content, and restricted documents.
6. Review all GitHub release assets and Actions artifacts. Remove or replace
   any artifact that contains runtime state or provider data.
7. Build the candidate image without using operator secrets. Inspect its
   filesystem, history, labels, environment, and build provenance; confirm it
   contains application code and dependencies only.
8. Verify published backups are absent. Private operator backups stay outside
   the repository, release assets, CI, and public container registries.
9. Recheck every enabled source's current terms, cost, attribution, retention,
   cancellation, and redistribution boundary.
10. Record the review date, exact commit, tools, findings, remediations, and
    explicit operator approval before changing visibility.

Never paste a real secret into a shell command that is retained in history or
into a scanner report. A clean current-tree scan does not repair a secret that
already exists in Git history.

## Provider cancellation or material terms change

1. Disable the affected source assignment and scheduled job; do not silently
   fail over to another writer.
2. Preserve the last known good canonical state only when the reviewed terms
   permit continued retention and reference.
3. Apply the provider-specific cancellation or deletion obligation. Do not
   infer it from this general policy.
4. Keep Outlook changes fail-closed until the legal and technical boundary is
   reviewed.
5. Update the source ADR, authority matrix, operations documentation, issue,
   and release limitation before re-enablement.
6. Requalify any replacement source through two safe observations and the
   normal staging gates.

## Disclosure response

If restricted material is discovered, stop publication and new releases.
Revoke or rotate exposed credentials first, disable affected imports, preserve
private forensic evidence, identify every Git commit and external artifact,
and follow GitHub's supported sensitive-data removal process. Re-run the full
history, GitHub, image, artifact, and provider-rights audit before publication
resumes. Never publish the leaked value in the remediation issue.

This policy is an engineering and operational control, not legal advice.
Source-specific licensing questions still require a source-specific review.
