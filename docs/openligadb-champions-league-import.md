# OpenLigaDB Champions League League-Phase Import

## Implemented scope

The OpenLigaDB adapter supports exactly:

- provider scope `4946/ucl/2026`;
- canonical scope `football/uefa_champions_league/2026_27`;
- normalized stage `league_phase`;
- matchdays `matchday-1` through `matchday-8`;
- 36 reviewed clubs and 144 fixtures; and
- partial, filtered, removal-disabled lifecycle handling.

Provider groups 9 through 16 and UEFA qualifying stages are not imported.

## Configuration

```env
OPENLIGADB_ENABLED=true
SOURCE_JOBS_JSON=[{"job_key":"openligadb-uefa-champions-league","source_key":"openligadb","sport_key":"football","competition_key":"uefa_champions_league","season_key":"2026_27","role":"authoritative","interval_seconds":21600}]
```

No provider credential is required. Exactly one authoritative writer may be
enabled for this competition and season. A football-data.org UCL candidate may
not run concurrently as another writer.

## Validation and mapping

The parser requires eight complete 18-fixture matchdays, 36 participants,
eight appearances per participant, and no repeated opponent pairing. It
accepts only the reviewed OpenLigaDB provider ID/name pairs. Stable fixture and
participant IDs are persisted through the source-mapping repository.

Every observation is `partial`, `complete=false`, `filtered=true`, and
`removal_eligible=false`. Missing or failed source data cannot cancel or delete
canonical fixtures or Outlook events.

Source metadata and Outlook event bodies retain:

`Fixture data provided by OpenLigaDB (ODbL 1.0): https://www.openligadb.de/`

## Verification

Normal CI is credential-free and network-free. Synthetic tests prove exact
schedule validation, wrong-scope and incomplete-response rejection, mapping,
SQLite import, Outlook creation, unchanged-cycle idempotency, rescheduling,
restart, provider outage/recovery, attribution, and non-destructive omission.

The live structural check is read-only:

```text
python -m app.operations.openligadb_qualification --competition champions-league-league-phase
```

Isolated staging against the dedicated staging SQLite database and Outlook
calendar remains a release gate. Live payloads, databases, exports, and logs
containing complete fixture inventories must not be committed or attached to
public CI or release artifacts.
