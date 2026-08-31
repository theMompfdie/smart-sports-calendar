# Phase 5 Multi-Competition Staging Validation

This operator-run procedure is the live validation gate for issue #122, the
remaining DFB-Pokal staging criteria in issue #119, the 2. Bundesliga gate in
issue #132, the Championship gate in issue #135, and the ÖFB-Cup gate in issue
#145. It validates the 2026/27 Premier League, Bundesliga, Championship regular
season, DFB-Pokal, 2. Bundesliga, and ÖFB-Cup together in one isolated staging
deployment. It does not authorize production promotion, a tag, or a release.

This document and `--validate-phase-5-candidate` intentionally remain bound to
the six released Phase 5 authorities. The separate seven-authority Nations
League extension is documented in
[`nations-league-a-staging-validation.md`](nations-league-a-staging-validation.md)
and validated with `--validate-nations-league-a-candidate`.

## Candidate boundary

The only enabled authoritative jobs are:

| Job | Authority | Canonical scope | Maximum lifecycle scope |
| --- | --- | --- | --- |
| `football-data-premier-league` | football-data.org `PL` / 2021 | `football/premier_league/2026_27` | `complete_season` |
| `football-data-bundesliga` | football-data.org `BL1` / 2002 | `football/bundesliga/2026_27` | `complete_season` |
| `football-data-championship` | football-data.org `ELC` / 2016 | `football/championship/2026_27` | `complete_stage` for `REGULAR_SEASON` only |
| `openligadb-dfb-pokal` | OpenLigaDB `4945/dfb/2026` | `football/dfb_pokal/2026_27` | permanently `partial` |
| `openligadb-second-bundesliga` | OpenLigaDB `4938/bl2/2026` | `football/second_bundesliga/2026_27` | initially removal-disabled `partial` |
| `oefb-ical-oefb-cup` | official private ÖFB iCalendar feed | `football/oefb_cup/2026_27` | permanently `partial` |

Both OpenLigaDB jobs and the ÖFB iCalendar job must report `complete=false`,
`scope_kind=partial`, and `removal_eligible=false`. Missing fixtures from these
partial authorities never cancel or delete canonical or Outlook events.

Stop immediately if staging shares a database, volume, calendar, credentials,
stack name, or writable resource with production. Never print the effective
environment or copy raw logs, provider responses, event details, external IDs,
or deployment identifiers into GitHub evidence.

## Prerequisites

- The reviewed #122 tooling commit is available to the isolated staging stack.
- Ruff, pytest, Compose, Docker, and GitHub Actions pass for that commit.
- Staging automatic updates are disabled for the validation window.
- A dedicated non-production Microsoft 365 mailbox and calendar are selected.
- The staging database has a verified backup before recovery exercises.
- The operator can edit only the staging provider base URLs for controlled
  failure exercises.
- The football-data.org token covers all three approved competition profiles.

Confirm locally that the secret file is ignored and that no unrelated changes
are present:

```bash
git check-ignore .env
git status --short --branch
```

## Secret-safe staging configuration

Set real identifiers and credentials only in Portainer or another ignored
operator secret store. The source-job JSON must remain on one line.

```env
INSTANCE_NAME=staging
IMAGE_TAG=<reviewed-public-git-reference>
DATABASE_PATH=/data/sports.db
GRAPH_STARTUP_VALIDATION_ENABLED=true
API_FOOTBALL_ENABLED=false
API_FOOTBALL_API_KEY=
FOOTBALL_DATA_ENABLED=true
FOOTBALL_DATA_API_KEY=<deployment-secret>
FOOTBALL_DATA_REQUESTS_PER_MINUTE=10
FOOTBALL_DATA_MINIMUM_REQUEST_INTERVAL_SECONDS=6.1
OPENLIGADB_ENABLED=true
OPENLIGADB_MINIMUM_REQUEST_INTERVAL_SECONDS=1
OEFB_ICAL_ENABLED=true
OEFB_ICAL_FEED_URL=<deployment-secret>
OEFB_ICAL_MINIMUM_POLL_INTERVAL_SECONDS=21600
SOURCE_JOBS_JSON=[{"job_key":"football-data-premier-league","source_key":"football_data","sport_key":"football","competition_key":"premier_league","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"football-data-bundesliga","source_key":"football_data","sport_key":"football","competition_key":"bundesliga","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"football-data-championship","source_key":"football_data","sport_key":"football","competition_key":"championship","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"openligadb-dfb-pokal","source_key":"openligadb","sport_key":"football","competition_key":"dfb_pokal","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"openligadb-second-bundesliga","source_key":"openligadb","sport_key":"football","competition_key":"second_bundesliga","season_key":"2026_27","role":"authoritative","interval_seconds":21600},{"job_key":"oefb-ical-oefb-cup","source_key":"oefb_ical","sport_key":"football","competition_key":"oefb_cup","season_key":"2026_27","role":"authoritative","interval_seconds":21600}]
```

Keep the official provider base URLs unchanged except during the controlled
failure exercises. Do not paste the complete rendered Compose configuration
into an issue because it contains deployment-specific values.

Validate and start only the staging project:

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

## Fresh provider qualification

Run the existing read-only qualification commands before accepting live import
evidence. Enter the football-data.org token only through the approved secret
handoff described in
[`football-data-qualification.md`](football-data-qualification.md).

```bash
python -m app.operations.football_data_qualification --competition premier-league --season 2026
python -m app.operations.football_data_qualification --competition bundesliga --season 2026
python -m app.operations.football_data_qualification --competition championship --season 2026
python -m app.operations.openligadb_qualification
python -m app.operations.openligadb_qualification --competition 2-bundesliga
python -m app.operations.oefb_ical_catalog_candidates
```

Retain only the generated aggregate JSON. Compare counts, season boundaries,
status totals, request counts, and SHA-256 fingerprints with the approved
qualification records. The 2. Bundesliga observation must retain its exact
306-fixture, 18-participant, 34-matchday contract. The DFB-Pokal observation
may report missing timezone declarations only when every affected fixture
retains an explicit UTC kickoff; an unexpected non-empty timezone must fail.
A changed DFB-Pokal count can be valid as later rounds become known, but its
competition, season, six-group inventory, participant mapping, and
permanent-partial boundary must remain valid.
The ÖFB observation must contain exactly 48 current-season fixtures and the 64
reviewed participant identities. The operator enters the opaque feed URL only
at the interactive prompt; the URL and raw payload must not be retained.

## Read-only candidate evidence

Run the evidence command inside the application container after provider and
calendar cycles have completed:

```bash
docker compose exec -T calendar-sync python -m app.operations.staging_evidence --database /data/sports.db --limit 50 --validate-phase-5-candidate
```

The command fails unless it finds exactly the six approved authorities, 380
Premier League fixtures, 306 Bundesliga fixtures, 552 Championship
regular-season fixtures, 306 2. Bundesliga fixtures, 48 ÖFB-Cup fixtures, a
non-empty DFB-Pokal scope, one source mapping and one synchronized calendar
mapping per fixture, zero revision-pending mappings, one calendar target per
competition, and safe lifecycle flags on the latest run of each job. It emits
only aggregate counts, public canonical keys, timestamps, status totals,
sanitized run fields, and SHA-256 hashes of sorted source IDs.

Review the JSON before copying it outside staging. The command intentionally
excludes calendar IDs, Outlook IDs, event titles, participants, external IDs,
provider metadata, error messages, URLs, tokens, and raw payloads.

## Validation sequence

### 1. Initial convergence and attribution

1. Confirm the container is healthy and Graph startup validation accepted the
   dedicated staging calendar without logging its immutable identifier.
2. Wait for all six independent provider jobs and calendar synchronization
   to complete. After the `008_add_calendar_sync_revisions` upgrade, existing
   mappings intentionally require one bounded reconciliation sweep; continue
   through calendar batches until the revision-pending count reaches zero.
3. Run the candidate evidence command. Do not continue on validation failure.
4. Manually sample events from each competition in the staging calendar.
5. Confirm football-data.org events show
   `Football data provided by the Football-Data.org API`.
6. Confirm DFB-Pokal and 2. Bundesliga events show
   `Fixture data provided by OpenLigaDB (ODbL 1.0): https://www.openligadb.de/`.
7. Confirm ÖFB-Cup events show the reviewed official ÖFB attribution without
   exposing the private feed URL.

### 2. Unchanged-cycle idempotency

Allow another complete cycle without provider changes, then rerun the evidence
command. Verify fixture, source-mapping, calendar-mapping, and fingerprint
aggregates remain stable. Latest provider runs must report unchanged items, and
the calendar run must issue no unnecessary create, update, or delete operation.

Do not edit live SQLite or provider payloads to manufacture a reschedule. If no
natural provider update is observed, record that the controlled update proof is
the deterministic SQLite-to-mocked-Graph coverage in
`tests/integration/test_bundesliga_football_data_to_outlook.py` and
`tests/integration/test_openligadb_dfb_pokal_to_outlook.py`, plus
`tests/integration/test_openligadb_second_bundesliga_to_outlook.py`.

### 3. Restart and interrupted-run recovery

Restart the staging container normally:

```bash
docker compose restart calendar-sync
docker compose ps
```

After convergence, rerun candidate evidence. `startup_records` must increase;
fixture fingerprints, source mappings, and Outlook mappings must retain their
identity. A live interrupted write must not be manufactured. Use the automated
recovery tests for unsafe interruption points and record their exact test names.

### 4. Controlled provider failures

Perform one provider exercise at a time only after a successful baseline and
backup. In the staging configuration, temporarily replace exactly one provider
base URL with `https://127.0.0.1`, redeploy, and observe one bounded failed
cycle:

1. Set `FOOTBALL_DATA_BASE_URL=https://127.0.0.1`; keep OpenLigaDB unchanged.
   All three football-data.org jobs must fail closed while both OpenLigaDB jobs
   and synchronization of committed state remain operational.
2. Restore `FOOTBALL_DATA_BASE_URL=https://api.football-data.org`, redeploy,
   and require successful unchanged convergence.
3. Set `OPENLIGADB_BASE_URL=https://127.0.0.1`; keep football-data.org
   unchanged. DFB-Pokal and 2. Bundesliga must preserve last-known-good state
   while all three football-data.org jobs and calendar synchronization remain
   operational.
4. Restore `OPENLIGADB_BASE_URL=https://api.openligadb.de`, redeploy, and
   require successful unchanged convergence.

Never alter tokens, job scopes, authority roles, or the production stack for a
failure exercise. Review logs locally for the expected safe error category, but
do not paste unreviewed error text into GitHub.

### 5. Backup and isolated restore

Follow the scoped SQLite backup procedure in
[`deployment.md`](deployment.md). Resolve and verify the exact staging volume
before copying. Restore the backup only into a new explicitly named recovery
volume with Graph and every provider disabled. Never overwrite staging or
production and never connect the restored database to a calendar.

Run the read-only evidence command against the restored database without the
candidate validator. Confirm `database_quick_check=ok`, the expected authority
and fixture aggregates, and stable fingerprints. Then stop the temporary
recovery container. Volume removal remains a separate explicit operator action.

## Evidence template for #122, #119, #132, and #145

```markdown
### Phase 5 multi-competition staging record

- Candidate commit/tag: `<public Git reference>`
- Validation window (UTC): `<start>` to `<end>`
- Staging/production isolation: `<pass/fail>`
- Exact six-authority configuration: `<pass/fail>`
- Fresh Premier League qualification: `<pass/fail and aggregate comparison>`
- Fresh Bundesliga qualification: `<pass/fail and aggregate comparison>`
- Fresh DFB-Pokal qualification: `<pass/fail and aggregate comparison>`
- Fresh 2. Bundesliga qualification: `<pass/fail and aggregate comparison>`
- Fresh ÖFB-Cup contract observation: `<pass/fail and aggregate comparison>`
- Initial SQLite and Outlook convergence: `<pass/fail>`
- Provider attribution: `<pass/fail>`
- Unchanged-cycle idempotency: `<pass/fail>`
- Restart recovery: `<pass/fail>`
- Interrupted-run deterministic evidence: `<test names and result>`
- football-data.org failure and recovery: `<pass/fail>`
- OpenLigaDB failure and recovery: `<pass/fail>`
- ÖFB iCalendar failure and recovery: `<pass/fail>`
- Backup integrity and isolated restore: `<pass/fail>`
- Secret and identifier review: `<pass/fail>`
- Follow-up defects: `<issue numbers or none>`

#### Secret-safe candidate evidence

`<paste reviewed staging_evidence JSON>`
```

Issue #122 may close only after every failed gate has a focused follow-up issue
and the sanitized evidence is reviewed. The relevant evidence is then copied or
cross-referenced in #119 so its remaining staging criteria can close. Successful
staging does not authorize production promotion or release publication.
