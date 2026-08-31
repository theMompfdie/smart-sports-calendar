# UEFA Champions League Source Qualification

## Status

**Qualified for `v0.6.0-beta.1`: OpenLigaDB league `4946`, shortcut `ucl`,
season `2026`, is the selected zero-cost authority for exactly the 2026/27
UEFA Champions League league phase. Qualifying and every knockout stage remain
excluded. Every runtime observation is partial and removal-disabled.**

This decision was completed on 2026-08-31 for issue #154 after two sanitized,
read-only observations and an independent comparison with UEFA's official
league-phase structure and schedule. It replaces the earlier conditional
football-data.org selection because the free `CL` endpoint still exposed no
fixtures while the public OpenLigaDB scope passed the bounded qualification.

## Approved boundary

The canonical runtime scope is:

- competition: `uefa_champions_league`;
- season: `2026_27`;
- stage: `league_phase`;
- source: OpenLigaDB API v1 `4946/ucl/2026`;
- 36 reviewed clubs;
- eight matchdays with 18 fixtures each;
- exactly 144 fixtures from 8 September 2026 through 27 January 2027; and
- one appearance per club per matchday and eight distinct opponents per club.

OpenLigaDB already declares provider group containers for knockout play-offs,
round of 16, quarter-finals, semi-finals, and the final. Those groups are not
qualified. They are filtered before normalization and cannot write canonical
state or contribute absence/removal evidence. The separately modeled UEFA
qualifying rounds are also outside this release boundary.

## Technical evidence

Two secret-free observations on 2026-08-31 returned the same bounded
league-phase structure:

| Evidence | Observation 1 | Observation 2 |
| --- | ---: | ---: |
| Provider league | `4946/ucl/2026` | `4946/ucl/2026` |
| Included fixtures | 144 | 144 |
| Unique fixture IDs | 144 | 144 |
| Participants | 36 | 36 |
| Included matchdays | 8 | 8 |
| Fixtures per matchday | 18 | 18 |
| Missing timezone declarations | 0 | 0 |
| Finished / scheduled | 0 / 144 | 0 / 144 |
| Earliest kickoff UTC | `2026-09-08T16:45:00Z` | `2026-09-08T16:45:00Z` |
| Latest kickoff UTC | `2027-01-27T20:00:00Z` | `2027-01-27T20:00:00Z` |

The second bounded validator observation ran at `2026-08-31T07:02:51Z` and
produced fixture-ID hash
`80a0692357a6771a17abf11e5d6eef7266f9b0e1f0de85b39f2dceaf0a4be340` and
participant-ID hash
`93c1ca26cd925398d79bfb235a27b4b9c3fefa0a3ab0ade79241ef582592dbf6`.
No raw fixture inventory was retained in the repository.

UEFA independently documents 36 clubs, 144 fixtures, eight matchdays, 18
fixtures per matchday, eight single-leg opponents per club, and the same start
and end dates. The OpenLigaDB cardinalities and date boundary therefore match
the official competition structure exactly.

## Validator contract

The credential-free qualification command is:

```text
python -m app.operations.openligadb_qualification --competition champions-league-league-phase
```

The validator fails closed when it sees:

- the wrong league ID, shortcut, season, sport, group identity, or date range;
- anything other than 144 unique selected fixture IDs and 36 participants;
- an incomplete 18-fixture matchday or a participant missing from a matchday;
- a participant with anything other than eight appearances;
- repeated opponents, duplicate IDs, malformed timestamps, or future updates;
- an empty, malformed, non-JSON, throttled, or failed response; or
- an unexpected timezone declaration.

Normal CI uses synthetic schedules and never calls the live provider.

## Rights, cost, and operations

OpenLigaDB provides public, unauthenticated JSON access and publishes its
database under ODbL 1.0. It needs no account, token, credit card, subscription,
or recurring fee. The existing project-wide OpenLigaDB attribution is retained
in source metadata and every Outlook event body:

`Fixture data provided by OpenLigaDB (ODbL 1.0): https://www.openligadb.de/`

OpenLigaDB is community-maintained, not UEFA's official machine authority.
Consequently:

- every observation is `partial`, `complete=false`, and
  `removal_eligible=false`;
- only `CREATE`, `UPDATE`, and `SKIP` decisions are permitted;
- provider absence, failure, or a filtered later-stage response preserves the
  last known good canonical and Outlook state;
- logos and image URLs are not imported; and
- live payloads, fixture inventories, SQLite databases, and exports remain
  outside Git, CI artifacts, images, and releases.

## Other candidates

football-data.org `CL` / 2001 remains a possible operator-selected
verification or future alternative source. Its free 2026/27 scope exposed 36
participants but zero fixtures on 2026-08-30, so it is not the writer selected
here. It must not be enabled simultaneously as another authority. Account
creation does not change this decision automatically.

API-Football remains rejected as a new UEFA authority without competition-
specific permission. Sportmonks remains outside the zero-cost boundary.
Official UEFA pages remain the manual verification source because no
documented public fixture API or supported automated calendar contract was
identified.

## Re-evaluation triggers

Requalify before admitting any knockout group, changing provider league or
season identity, accepting a second writer, enabling removal, changing the
cost boundary, or relying on changed provider terms or schema. Later UCL
stages require their own two observations and official comparison.

## Sources

- [UEFA 2026/27 league-phase draw and structure](https://www.uefa.com/uefachampionsleague/news/02a8-215821715a96-9a3b43fad585-1000--uefa-champions-league-league-phase-draw/)
- [UEFA 2026/27 confirmed league-phase fixtures](https://www.uefa.com/uefachampionsleague/news/02a8-2174c9e9019d-f909a77bd77a-1000--2026-27-champions-league-all-the-league-phase-fixtures/)
- [UEFA Article 17: league-phase match system](https://documents.uefa.com/r/Regulations-of-the-UEFA-Champions-League-2026/27/Article-17-Match-system-league-phase-Online)
- [OpenLigaDB](https://www.openligadb.de/)
- [OpenLigaDB API](https://api.openligadb.de/)
- [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
