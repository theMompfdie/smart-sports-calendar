# Version 1.0 repository audit

Issue #270 reviews the publication candidate based on develop `59dd553`.
This is a purpose and publication-boundary audit, not a claim that all historical
Git objects have been exhaustively scanned or that release publication occurred.

## Inventory and decisions

The baseline contains 432 tracked files; the candidate contains 437 files. The companion
[file inventory](repository-file-inventory.tsv) lists every retained candidate
path, its classification, action and reason, including the new documentation.
No runtime source, migration, test, dependency manifest or CI file is removed.

- `app/`: retain production services, providers, Graph boundaries, repositories
  and all 15 deterministic migrations. Deleting older migrations would break
  reproducible upgrades and is not cleanup.
- `tests/`: retain synthetic tests and fixtures. These supply offline lifecycle,
  idempotency, migration, locking, failure and restore evidence.
- `scripts/`: retain publication safety, startup readiness, staging preflight
  and multi-instance validation; each has operational or CI callers.
- `.github/`: retain CI and issue/PR templates. CI deliberately installs
  `requirements-dev.txt`, which includes `requirements.txt` and adds pytest/Ruff.
- Root build/config files: retain Dockerfile, Compose, pyproject, dependency
  manifests, ignored-secret example, ignore boundaries, MIT license and project
  instructions. `config/.gitkeep` remains an empty configuration placeholder;
  it contains no credentials and is excluded from the application package.
- `docs/`: retain ADRs, qualification evidence, schemas, synthetic examples and
  historical phase checklists. Their dated scope is historical, not permission
  to activate new providers or seasons.
- Release notes: move eight root notes and the v1 draft into `docs/releases/`.
  Repair links and command/file references. Historical publication status is
  retained; no private release assets are added. Reflow long historical prose
  and configuration tables where needed for Markdown validation.
- README: replace the phase-by-phase landing page with the supported product,
  first-calendar path, ongoing duties and exclusions. Detailed history remains
  in the versioned notes and historical checklists. The requested JARVIS credit
  is an HTML comment, not a product claim.
- Add installation, release-gate and audit records. Update the accepted #233
  evidence limitations and #267 lifecycle result without inventing missing
  historical observations or a published stable release.

The inventory is generated documentation intentionally included in the source
release; runtime-generated databases, calendars, provider responses and media
are not. No sensitive material was found by the current candidate safety scan.
That scanner uses explicit filename/content patterns, not a proof against every
possible secret encoding. No history rewrite or credential rotation is implied.

## Publication boundaries

`.gitignore` excludes SQLite/sidecars, private directories, environment files,
feed exports and key material while retaining `.env.example`. `.dockerignore`
excludes private runtime state, docs, tests, configuration and development-only
requirements from the context. Dockerfile copies only `requirements.txt` and
`app/`, installs runtime requirements and runs as UID 10001 with no privileged
mode or exposed application port. Compose stores state in a project volume.

Setuptools discovery includes only `app` and excludes test/config/data packages.
The supported deployment installs `requirements.txt` inside Docker. A generic
`pip install .` is not documented as a complete deployment: project metadata's
dependency subset and migration package-data handling are not a qualified wheel
installation path. Do not publish a wheel as a verified v1 artifact on this basis.
Changing packaging is outside this documentation delivery unless wheel support
becomes an explicit release requirement.

Private backup/audit files from live #267 remain outside this repository. No
raw source schedule or third-party image is attached to this PR or release.
Public source-rights references and synthetic manifests are intentional docs.
Optional image fallback and target-specific source review remain documented.

## Validation record

- Ruff lint and formatting passed for unchanged production/test/tooling code.
- Publication safety passed for the candidate, including untracked new docs.
- Local Markdown file and fragment links are parsed and resolved against the
  candidate. External links are not treated as automatically verified by this
  check; release and Microsoft provisioning references are reviewed separately.
- Changed Markdown is checked with markdownlint-cli2 0.23.2 default rules.
  The repository has no Markdownlint configuration. Pre-existing long tables
  in touched deployment/release files are reformatted without disabling rules.
- Full pytest: 1,556 passed in 555.31 seconds on Python 3.13.15 (Windows).
  No skips or test failures in the completed rerun.
- Markdownlint: all 24 changed Markdown files passed default rules.
- Link validation: 97 Markdown files, 209 local file/fragment links, no errors.
- The one-provider clean-install Compose configuration passed `config --quiet`
  using external placeholder credentials; no provider/Graph call was made.
- The first pytest attempt hit an inaccessible Windows temporary directory.
  The rerun uses a fresh explicit `--basetemp` and `cache_dir`; no test is skipped
  and no failure is hidden or converted into a pass.
- Docker Desktop's Linux daemon is unavailable locally. No local Docker build
  success is claimed. Required PR CI supplies fresh build/startup, SQLite and
  three-instance validation. PR #284 passed these checks in run 34165368974;
  all five jobs passed, including 1,556 tests in 221.71 seconds. The operator
  merged the identical tested tree into develop as `4e47bb8`.
- Existing live staging accepted the additive upgrade and the actual Graph
  lifecycle on `59dd553`. These docs introduce no production-code/schema change.
  Final candidate CI, current operational readiness and release merge/tag
  verification remain explicit checklist gates.

## Reproduction

From the repository root:

```bash
ruff check .
ruff format --check app scripts tests
python -m pytest --durations=15
python scripts/check_publication_safety.py
```

For changed Markdown, run `markdownlint-cli2` with the changed `.md` paths
(including moved notes) as explicit arguments. Local link validation uses a
one-off Markdown parser probe, checking resolved file paths and GitHub-style
heading fragments across all candidate Markdown. Its output is retained with
the review evidence; it adds no runtime dependency or CI replacement.

Complete the [release checklist](v1.0.0-release-checklist.md) before publication.
The audit does not authorize a merge, release or production deployment.
