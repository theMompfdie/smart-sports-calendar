# Champions League Isolated Staging Validation

## Purpose and boundary

This operator-run procedure is the remaining live gate for the OpenLigaDB UEFA
Champions League 2026/27 league-phase authority. It extends the seven-authority
Nations League candidate with exactly one additional job:

`openligadb-uefa-champions-league`

The accepted UCL boundary is 144 active fixtures, 144 event source mappings,
36 participant source mappings, 144 Outlook mappings, one calendar target,
zero pending revisions, stage `league_phase=144`, and eight `matchday-*`
rounds with 18 fixtures each. The latest provider run must report
`authoritative=true`, `filtered=true`, `complete=false`,
`scope_kind=partial`, `scope_stage=league_phase`,
`scope_stage_kind=league_phase`, and `removal_eligible=false`.

Qualifying and provider groups 9 through 16 must remain absent. This procedure
does not authorize production promotion, a tag, or a broader UCL scope.

## Isolation preconditions

- Use only the dedicated staging stack, volume, SQLite database, mailbox,
  Outlook calendar, credentials, configuration, and logs.
- Stop if any writable staging resource is shared with production.
- Freeze staging to the reviewed candidate revision for the validation window.
- Back up the stopped staging database before failure or restore exercises.
- Keep `.env` and `.env.portainer-staging` ignored and outside Git artifacts.
- Never publish raw provider payloads, event titles, participant lists,
  provider IDs, Outlook IDs, calendar IDs, credentials, or rendered Compose
  configuration.

Confirm locally:

```text
git check-ignore .env .env.portainer-staging
git status --short --branch
docker compose --env-file .env.portainer-staging config --quiet
```

## Configuration

Append this eighth job to the existing staging `SOURCE_JOBS_JSON` array:

```json
{"job_key":"openligadb-uefa-champions-league","source_key":"openligadb","sport_key":"football","competition_key":"uefa_champions_league","season_key":"2026_27","role":"authoritative","interval_seconds":21600}
```

Required non-secret settings include:

```env
INSTANCE_NAME=staging
DATABASE_PATH=/data/sports.db
GRAPH_STARTUP_VALIDATION_ENABLED=true
OPENLIGADB_ENABLED=true
OPENLIGADB_BASE_URL=https://api.openligadb.de
OPENLIGADB_MINIMUM_REQUEST_INTERVAL_SECONDS=1
```

Exactly one authoritative writer may exist for UCL `2026_27`.
football-data.org must not be enabled as a concurrent UCL writer.

## Fresh provider qualification

Run from the reviewed checkout or application image:

```text
python -m app.operations.openligadb_qualification --competition champions-league-league-phase
```

Require league `4946/ucl/2026`, 144 unique included fixtures, 36 participants,
eight 18-fixture matchdays, no missing timezone declarations, and no structural
failure. Compare the secret-safe identity hashes with the reviewed evidence.
Any changed hash requires explicit investigation.

## Converged candidate evidence

After all eight provider jobs and calendar batches complete, run:

```text
docker compose exec -T calendar-sync python -m app.operations.staging_evidence --database /data/sports.db --limit 120 --validate-champions-league-candidate
```

The command reads SQLite in query-only mode and emits only aggregate keys,
counts, lifecycle flags, run summaries, UTC boundaries, and SHA-256 hashes.
It fails unless the exact eight-authority candidate and all UCL invariants are
converged.

## Validation sequence

1. Confirm Graph startup validation accepts only the dedicated staging
   calendar.
2. Require 144 UCL creates, 144 synchronized mappings, no pending revisions,
   exact stage/round counts, and visible OpenLigaDB ODbL attribution.
3. Manually sample staging events for participants and kickoff times; confirm
   qualifying and knockout rounds are absent.
4. Allow an unchanged provider and calendar cycle. Require 144 unchanged UCL
   items and no Graph writes.
5. Restart only the staging application, rerun evidence, and require stable
   source and Outlook mapping identities.
6. After a backup, set only the staging
   `OPENLIGADB_BASE_URL=https://127.0.0.1`, observe one bounded failed cycle,
   and confirm every OpenLigaDB last-known-good scope remains unchanged while
   unrelated jobs continue.
7. Restore `https://api.openligadb.de`, redeploy staging, and require successful
   unchanged convergence.
8. Restore the backup only into a new recovery volume with Graph and all
   providers disabled; require `database_quick_check=ok` and stable aggregate
   fingerprints.

Do not edit live SQLite or provider responses to manufacture changes. Cite
`tests/integration/test_openligadb_champions_league_to_outlook.py` for the
deterministic reschedule, omission, restart, outage, and recovery proofs when
no natural provider update occurs during the window.

## Secret-safe evidence record

Record only the candidate Git reference, UTC validation window, pass/fail for
isolation, fresh qualification, exact UCL boundary, initial convergence,
attribution, excluded stages, unchanged-cycle idempotency, restart, controlled
failure/recovery, backup/restore, and the reviewed aggregate JSON. Any failed
gate needs a focused blocking issue before release.
