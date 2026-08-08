# Phase 4 Release Checklist

## Release identity

- Release: `v0.4.0-alpha.1`
- Phase: Phase 4 – Initial Football Provider and Premier League Import
- Package version: `0.4.0a1`
- Release branch: `release/v0.4.0-alpha.1`
- Target branch: `main`
- Release type: GitHub pre-release

The release branch must be created from the exact reviewed `develop` commit
after Phase 4.8 is merged. “Phase 4” belongs in the pull-request and release
titles, not in the Git branch name.

## Before creating the release branch

- [ ] Issues #43, #45, #47, #49, #51, #53, #55, and #57 are closed through
  merged pull requests.
- [ ] `develop` contains every Phase 4 merge and has no uncommitted changes.
- [ ] The Phase 4.8 pull request has green GitHub Actions and no unresolved
  review comments or merge conflicts.
- [ ] `pyproject.toml` reports `0.4.0a1`.
- [ ] README reports `v0.3.0-alpha.1` as the currently published release and
  `v0.4.0-alpha.1` as the next pre-release until publication.
- [ ] `RELEASE_NOTES_v0.4.0-alpha.1.md` matches the final diff.
- [ ] `.env.example` contains placeholders only and `.env` remains ignored.
- [ ] Deployment, upgrade, rollback, and live-validation guidance is reviewed.

## Required verification

Run from the clean Phase 4.8/release candidate:

```bash
ruff format --check .
ruff check .
pytest -q
docker compose config --quiet
git diff --check
```

Also verify:

- [ ] all local commands pass;
- [ ] all GitHub Actions jobs pass on the Phase 4.8 pull request;
- [ ] internal Markdown links resolve to tracked files;
- [ ] no credential-like value or secret-bearing URL was added;
- [ ] the Docker image builds successfully in the intended release
  environment;
- [ ] the manual live-validation outcome is recorded as passed, skipped with a
  reason, or deferred as an explicit alpha limitation; and
- [ ] no known critical regression remains open.

## Create and review the release branch

After explicit authorization:

```bash
git switch develop
git pull --ff-only origin develop
git switch -c release/v0.4.0-alpha.1
git push -u origin release/v0.4.0-alpha.1
```

On the release branch, create one focused release-preparation commit that:

- changes README `Current release` to `v0.4.0-alpha.1`;
- marks Phase 4 completed and removes the now-published “next pre-release”
  wording;
- finalizes release-note and validation wording against the exact branch diff;
- removes or replaces the completed Phase 4.8 boundary in `AGENTS.md`; and
- changes no application behavior unless a separately reviewed release blocker
  requires it.

Rerun the complete verification commands after that commit and before opening
the release pull request.

Open a pull request from `release/v0.4.0-alpha.1` to `main` titled:

```text
release: v0.4.0-alpha.1 – Phase 4
```

The pull request must summarize Phase 4, link #42, include the validation
record, explain live-validation status, and state the deployment and rollback
limitations. Do not use `Closes #42` until the release publication sequence is
ready to complete.

Before merge, verify the release PR is conflict-free, all checks are green,
there are no unresolved review comments, and the head commit is the intended
release commit.

## Tag and publish the pre-release

Only after the release PR is merged and the resulting `main` commit is
verified:

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.4.0-alpha.1 -m "v0.4.0-alpha.1 - Phase 4"
git push origin v0.4.0-alpha.1
gh release create v0.4.0-alpha.1 \
    --prerelease \
    --title "v0.4.0-alpha.1 - Phase 4" \
    --notes-file RELEASE_NOTES_v0.4.0-alpha.1.md
```

Verify that the tag points to the intended `main` commit and that GitHub marks
the release as a pre-release. Release creation is a GitHub mutation and always
requires explicit user authorization.

## After publication

- [ ] Verify the tagged README reports `v0.4.0-alpha.1` as the current release
  and Phase 4 as completed.
- [ ] Update and close master issue #42 only after the tag and pre-release are
  verified.
- [ ] Confirm milestone and child-issue state is accurate.
- [ ] Merge any release-only metadata change back into `develop` if necessary.
- [ ] Remove obsolete remote feature/test/docs branches only after confirming
  they are merged and with explicit authorization.
- [ ] Preserve the release notes, validation record, and upgrade limitations.

Phase 4 is not complete merely because its implementation PRs are merged. It is
complete only after the reviewed `main` merge, immutable tag, GitHub
pre-release, documentation update, and tracker verification all succeed.
