# Private logo rights catalog template

Copy this template outside the repository and Docker build context before
filling it in. Duplicate the record for each exact asset. Follow the
[operator workflow](../logo-rights-workflow.md). All entries are placeholders,
not actual permissions. This is not a registry import file.

## Asset and evidence record

- Record ID: [Private stable ID]
- Subject and priority: [Club, competition, trophy or other image; priority]
- Exact asset/variant/version: [Description; unknown until supplied if needed]
- Official source page: [Authoritative page]
- Rights holder: [Verified entity; do not infer from the hosting website]
- Official contact and verification date: [Private contact record]
- Operator/deployment/territory: [Actual intended scope]
- Original filename/version/SHA-256: [After permitted acquisition]
- Normalized registry version/SHA-256: [After permitted import]
- Terms or permission evidence: [Private reference and terms version]
- Basis and reasoning: [Relevant provisions or express grant for each use]
- Reviewer and review date: [Name; YYYY-MM-DD]
- Overall decision: unreviewed

## Intended-use matrix

Use `unreviewed`, `pending`, `approved`, `rejected` or `not-needed` per row.
`pending` means clarification or permission is outstanding. `approved` requires
evidence for the specified scope. `not-needed` excludes that use; it does not
grant permission. Overall approval requires all intended uses to be covered.
Add rows when the deployment changes.

| Use | Intended? | Decision | Evidence and boundaries |
| --- | --- | --- | --- |
| Private server storage | Yes | unreviewed | [Reference] |
| Personal unshared calendar | Yes | unreviewed | [Reference] |
| Microsoft 365/Outlook inline copies | Yes | unreviewed | [Reference] |
| Private backup and restoration | Yes | unreviewed | [Reference] |
| Resize, padding, PNG conversion | Yes | unreviewed | [Reference] |
| Metadata removal | Yes | unreviewed | [Reference] |
| Shared or public calendar | No | not-needed | Excluded |
| Public screenshots/documentation | No | not-needed | Excluded |
| Repository/container distribution | No | not-needed | Excluded |

## Conditions and follow-up

- Attribution and placement: [Exact wording and supported placement]
- Copyright/trademark/brand conditions: [Restrictions or evidence reference]
- Transformations: [Confirm current registry processing]
- Territory and permitted recipients: [Scope]
- Start, expiry, renewal: [Dates or documented absence of a fixed term]
- Revocation and removal/retention: [Include stored copies and backups]
- Fees or acceptance requirements: [None stated, unknown or exact conditions]
- Recheck triggers and next review date: [Owner and reminder]
- Unresolved questions: [Keep pending until resolved]
- Fallback: [Text-only or exact reviewed project-owned artwork]

## Private request tracking

- Request ID and assets included: [Reference]
- Verified recipient and responsibility: [Private record]
- Draft reviewed by/date: [Name; YYYY-MM-DD]
- Operator authorization and send date: [Unsent until authorized]
- Reply date and correspondence reference: [Private record]
- Follow-up owner/date: [Avoid duplicate requests]
- Final decision and evidence: [No response means pending]

## Later registry handoff

- Asset key, canonical owner/type and variant: [Registry identity]
- Source/licence/permission references and attribution: [Import metadata]
- Original and normalized image reviewed: [Reviewer/date]
- Approved registry version and deployment: [After separate approval]
- Disable/recheck/expiry action owner: [Operator]
- Public-use exclusion checked: [No restricted bytes in public artifacts]

Keep evidence and actual registry approval consistent. Catalog approval does
not activate an asset; registry approval does not expand rights.
