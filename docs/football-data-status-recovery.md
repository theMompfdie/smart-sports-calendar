# Championship status incident: recovery checkpoint

Issue [#233][incident] tracks intermittent timestamp-shaped values in the
football-data.org match `status` field. This checkpoint records operator-supplied
staging evidence from 2026-09-07. It does not close the incident or authorize
production promotion.

## Observed recovery

The operator ran the existing read-only qualification at
`2026-09-07T18:53:44.936595+00:00`. Three requests returned one match page with
552 unique Championship regular-season fixtures and 24 teams. Status counts
were 60 `FINISHED`, 264 `SCHEDULED` and 228 `TIMED`. Strict validation passed.
The fixture-ID digest matched the preceding staging database evidence.

Successful canonical imports 9617 and 9639 processed all 552 fixtures. The
first was unchanged; the second updated one fixture. Calendar run 9646 then
reported one update and no failures. These are observations from the supplied
window, not a guarantee of permanent upstream correctness.

A read-only comparison with the backup taken before the retirement upgrade
retained all 552 canonical fixture IDs and all source and calendar identities.
No identities were added or removed. Exactly one fixture changed scheduling
fields: its canonical status moved from `postponed` to `scheduled`, with a new
kickoff. The provider modification time advanced. This explains the later
successful update; it does not identify the earlier malformed-response match.
No private payloads, calendar identifiers or credentials are published here.

A second read-only comparison used the retained pre-candidate backup from
2026-09-02, before the reported recurrence. Both database integrity checks
passed. Backup and current state each contained 552 Championship fixture IDs,
552 calendar identities and 552 source identities, with zero additions,
removals or identity changes in every set. This establishes identity retention
between those checkpoints. It does not establish unchanged fixture content
throughout the intervening period or identify the malformed-response fixture.

## Diagnostic correction

An unsupported string status still rejects the entire snapshot before import.
The exception now identifies the validated numeric competition, season and
match IDs. It suppresses the raw `KeyError` chain so untrusted status contents
are not printed in ordinary tracebacks. No timestamp is inferred as a status or
kickoff, no malformed fixture is skipped, and no partial response is accepted.
A legitimate `POSTPONED` to `TIMED` change continues to read kickoff from
`utcDate` and preserve fixture identity.

The diagnostic correction must be built and deployed to staging before relying
on the new message. A successful qualification cannot retroactively recover
fields from a discarded malformed response.

## Remaining acceptance

- Identify the original malformed-response match from retained incident
  evidence, or capture its validated ID on recurrence with the new diagnostic.
  Do not equate the later rescheduled fixture with that match without evidence.
- Identity retention against the pre-incident backup is verified above.
  Any claim of unchanged canonical content during the precise failure window
  still requires contemporaneous evidence; legitimate intervening updates
  must not be classified as data loss.
- Reassess current successful imports, freshness and calendar convergence for
  final acceptance under [#201][release] and documentation [#270][docs].
- Keep strict rejection and independent-job processing on future failures.
  No heuristic status repair or automatic authority failover is approved.

For a later read-only qualification on the Docker host:

```bash
docker exec smart-calendar-staging-calendar-sync-1 \
  python -m app.operations.football_data_qualification \
  --competition championship --season 2026
```

Use the actual staging container name. This command performs provider reads and
does not import into SQLite or mutate Outlook. Retain any diagnostic fixture ID
privately for a bounded, operator-reviewed source observation; never publish
raw provider responses or secret-bearing logs.

[incident]: https://github.com/theMompfdie/smart-sports-calendar/issues/233
[release]: https://github.com/theMompfdie/smart-sports-calendar/issues/201
[docs]: https://github.com/theMompfdie/smart-sports-calendar/issues/270
