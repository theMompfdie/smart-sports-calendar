# Pytest runtime measurements

Issue [#265][issue] tracks full-suite runtime optimization for Version 1.0.
All existing test scenarios and release gates remain required.

## Baseline and target

The baseline source is `1f83d0147dfdce9b98b4bfa75ae9c6d71dcea0ca`
on `develop`. The initial suite contains 1,516 tests.

Before changing the test setup, the target was set to at least a 50% reduction
in full-suite pytest wall time on the same environment. For the recorded CI
baseline, this means at most 252.32 seconds. Compare local measurements with
local measurements and CI measurements with CI measurements; they are not
interchangeable. The local target is at most 644.45 seconds.

| Environment | Before | After | Result |
| --- | --- | --- | --- |
| Ubuntu CI, Python 3.13 | 504.63 s | 227.83 s | 1,519 passed |
| Windows 11, Python 3.13.15 | 1,288.90 s | 510.95 s | 1,519 passed |

The verified [PR CI run][verified-ci] on commit `f7fbb3a` reports 1,519
passing tests in 227.83 seconds. This saves 276.80 seconds (54.85%) against
the 504.63-second CI baseline and meets the 252.32-second target. All five
CI jobs passed: code quality, publication safety, unit tests, Python
validation and Docker validation. The longest reported test call is 10.27
seconds (Second Bundesliga restart/provider failure); initial catalog
template setup is 3.71 seconds. No teardown appears in the top 40 phases.

The verified local run saves 777.95 seconds (60.36%) and
meets the local target. All 1,516 original cases pass, with three additional
fixture regression tests. No cases were skipped. The earlier trial with two
missing fixture arguments was corrected and is excluded from this comparison.

The successful [baseline CI run][baseline-ci] used the existing serial
`python -m pytest` job. Its total includes collection, setup, test calls and
teardown, but excludes dependency installation and other CI jobs. The old CI
command did not publish individual pytest durations, so its per-test and
fixture timings cannot be reconstructed precisely. The updated CI command
prints the slowest 40 setup, call and teardown phases on every run.

The local reference machine has an Intel Core i9-12900K, 16 cores and 24
logical processors, Windows 11 Pro build 26200, and SQLite 3.50.4. The checkout
is under OneDrive; pytest databases for these measurements are in a fresh
local temporary directory. No Docker container or parallel pytest workers
are used. Brief editing and lint commands ran during the baseline, so these
are representative development measurements, not an isolated hardware
benchmark.

## CI repeat and variability

The documentation-only commit `3c1bdc0` leaves the tested Python code
unchanged. Its [CI repeat][repeat-ci] passes all five jobs and all 1,519 tests,
but pytest takes 511.17 seconds. This is 1.30% slower than the original
504.63-second baseline. The first optimized result of 227.83 seconds is
therefore not a reproducible CI speedup claim. The cause of the variation
has not been established. Repeated comparable baseline and optimized runs
are needed before claiming the CI target is consistently achieved.

## Local duration evidence

Measurements were taken on 2026-09-06 with pytest 9.1.1. These are the
largest baseline module totals from JUnit, including setup, call and teardown:

| Test module | Before | Verified after |
| --- | --- | --- |
| [API-Football fixture import][api-import] | 224.10 s | 11.17 s |
| [NFL to Outlook][nfl-e2e] | 106.69 s | 55.03 s |
| [Application bootstrap][bootstrap] | 98.21 s | 66.71 s |
| [PL/BL/Championship to Outlook][regional-e2e] | 89.19 s | 62.99 s |
| [API-Football catalog][api-catalog] | 78.48 s | 9.90 s |
| [Second Bundesliga to Outlook][second-e2e] | 77.12 s | 51.28 s |

The unchanged bootstrap module also ran faster, showing host/cache variation.
These single-run totals do not isolate every environmental effect. The
API-Football fixture-import group drops from 224.10 to 11.17 seconds, which
provides direct evidence for the targeted removal of repeated setup. The
first CI comparison exceeds the 50% target, but its repeat does not.

The five slowest baseline test calls compare as follows:

| Scenario | Before call | After call |
| --- | --- | --- |
| [PL/Bundesliga identity][regional-e2e] | 34.85 s | 25.65 s |
| [Second Bundesliga restart][second-e2e] | 32.31 s | 24.53 s |
| [Championship stage boundaries][regional-e2e] | 30.08 s | 21.19 s |
| [PL snapshot/kickoff correction][pl-e2e] | 25.72 s | 16.62 s |
| [Champions League restart][cl-e2e] | 25.17 s | 17.58 s |

All baseline top-40 entries are call phases, down to 10.74 seconds. The
expensive initialization helpers ran inside test functions, so this cost
appeared as test call time rather than pytest fixture setup time. No setup
or teardown phase appeared among those 40 entries. The new session template
moves its one-time construction cost into the first requesting test's setup.
The verified run reports 7.86 seconds for template setup in
`test_service_maps_provider_catalog_to_existing_canonical_rows`. No teardown
phase appears in the verified top 40, whose final entry is 2.37 seconds.
Use `--durations=0 --durations-min=0` when all phase timings are needed.

Additional validation passed 48 representative tests in reversed collection
order, covering catalog copies, catalog services, normalization, fixture
imports, provider-to-Outlook integration and provider contracts. A temporary
`pytest_collection_modifyitems` hook reversed the selected items. This is
focused order-independence evidence, not a full-suite randomized-order claim.

## Chosen optimization

Repeated full catalog setup is expensive: provider service and integration
tests repeatedly populate all sports, competitions, seasons, participants
and 470 season memberships before exercising their own behavior.

The opt-in `initialize_test_catalog` fixture builds a template once per pytest
session, using the actual production migrations and catalog initializers.
Each fresh test database receives a SQLite backup of that template. The
template is opened read-only for copying, and both backup connections are
closed explicitly. The fixture accepts the test's own destination path,
including multiple independent databases within one test.

The template contains only the base catalogs. Provider registrations,
mappings, fixture imports, synchronization, mocked Graph operations and
test-specific mutations still execute separately in each test. No mutable
repository, connection, environment, clock or mock is shared between tests.
There is no persistent cache to become stale across runs or source changes.

Existing destination databases take the original migration and catalog
initialization path. This preserves restart and recovery scenarios, including
reapplying catalog entries while retaining existing application data.
Dedicated database, migration, catalog and application bootstrap tests keep
their real initialization paths. No production database settings, durability
guarantees or synchronization behavior are changed.

Three regression tests check complete schema/data equivalence, isolation
between copies and the template, and preservation of existing rows during
reinitialization. All original test names, parametrizations and assertions in
the converted files are retained.

## Integration profiling follow-up

A focused `cProfile` run of the three Second Bundesliga integration tests
on the same Windows host passes in 58.00 seconds (58.97 seconds including
profiler/module startup). SQLite execution accounts for 31.02 seconds,
connection context exit for 11.51 seconds, and connection creation for
10.19 seconds of internal time. The run opens 12,735 SQLite connections.
`CalendarEventMappingsRepository.mark_checked` accounts for 14.58 seconds
of cumulative time across 1,835 unchanged-event checks. These categories
must not be added to the cumulative repository timings because they overlap.
The measurements locate database work, not real sleeps, as the main cost
in this selection. They do not establish the cause of CI variability.

The PL/Bundesliga/Championship test harness previously normalized all three
provider snapshots before every test solely to obtain competition and season
IDs for source assignments. Read those IDs from the initialized catalog
instead. Keep all three configured providers and assignments, all full-season
imports, real SQLite transactions, pagination, lifecycle checks and Graph
operation assertions. The first tested import now also creates its own
provider mappings without a preliminary normalization warming them up.

Comparable profiled runs of the three tests give:

| Measurement | Before | After |
| --- | --- | --- |
| Passing tests | 3 | 3 |
| Pytest wall time | 70.05 s | 66.90 s |
| Harness cumulative time | 5.76 s | 0.30 s |
| Snapshot normalization calls | 20 | 11 |
| SQLite connections | 15,795 | 14,191 |

All three test functions, decorators and assertions are AST-equivalent to
the previous revision. Nine redundant snapshot normalizations and 1,604
connection creations are removed. The observed module wall-time reduction
is 4.50%; single-run host variation and profiling overhead still apply.
This is a focused setup improvement, not another measured full-suite
50% reduction. No production persistence settings or code are changed.

The subsequent unprofiled full Windows suite passes all 1,519 tests in
494.20 seconds, with no failures, errors or skips. Ruff lint and formatting,
publication safety and Markdownlint for this report pass. The full-suite
time difference from the preceding 510.95-second run includes host variation
and must not be attributed entirely to this small harness change. CI for
this follow-up remains pending until the operator-signed commit is pushed.

To profile this selection on either revision, use a fresh output directory
and the same options (PowerShell):

```powershell
$profileRoot = Join-Path $env:TEMP ('ssc-profile-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $profileRoot | Out-Null
python -m cProfile -o "$profileRoot/tests.prof" -m pytest `
    tests/integration/test_bundesliga_football_data_to_outlook.py `
    -p no:cacheprovider --basetemp "$profileRoot/tests" --durations=10
python -m pstats "$profileRoot/tests.prof"
```

In the pstats prompt, use `sort cumulative`, `stats 30`, then `quit`.
Use the Second Bundesliga test file instead to reproduce the first profile.

## Reproduce a measurement

Install the pinned development requirements and use the same Python version,
machine and storage location for both revisions. Avoid simultaneous full
test runs. Record the commit, test count, result and final elapsed time.

```bash
python -m pytest --durations=40
python -m ruff check .
python -m ruff format --check .
```

For a detailed local report on Windows, this PowerShell command creates a new
directory for each run. Pytest's `--basetemp` may remove an existing directory;
always use a fresh path and never point it at a checkout or runtime data.

```powershell
$runRoot = Join-Path $env:TEMP ('ssc-pytest-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runRoot | Out-Null
python -m pytest -p no:cacheprovider --basetemp "$runRoot/tests" `
    --durations=40 --junitxml="$runRoot/results.xml" *> "$runRoot/pytest.log"
$testExitCode = $LASTEXITCODE
Get-Content "$runRoot/pytest.log" -Tail 50
if ($testExitCode -ne 0) { throw "pytest failed ($testExitCode)" }
```

This also avoids reusing a previously inaccessible pytest cache or temporary
directory. It does not change Windows permissions. The normal command should
be preferred when the default directories are accessible. Use matching
options for the before and after runs. JUnit case durations aggregate the
test phases; the pytest duration table distinguishes setup, call and teardown.

During development, run the affected test files first for quick feedback:

```bash
python -m pytest tests/application/test_api_football_fixture_import_service.py
```

A focused selection does not replace the complete suite before handoff or
the required CI and release gates.

## Parallel execution and remaining limits

Pytest remains serial. Fixture reuse removes repeated work without adding
pytest-xdist, changing CI check names or introducing scheduling dependencies.
A session template would be built separately in each future worker. Before
enabling workers or sharding, audit subprocesses, locks, environment changes
and temporary paths and demonstrate equivalent full-suite results.

Full catalog bootstrap tests, existing-database restarts and large real
fixture import/synchronization scenarios retain their original cost. Windows
filesystem behavior, endpoint protection and machine load can affect local
timings; Linux CI results must be measured independently. Docker Desktop is
not needed to run this suite. A container benchmark is optional additional
evidence and must not be compared directly with native Windows timings.

The implementation commit has passed the local and CI verification gates
for [PR #275][pull-request] against `develop`. The CI repeat above qualifies
the initial performance result. Repeated comparable CI measurements remain
outstanding.
Parallel execution and production transaction changes require separate
evaluation; merging remains an operator action.

[issue]: https://github.com/theMompfdie/smart-sports-calendar/issues/265
[baseline-ci]: https://github.com/theMompfdie/smart-sports-calendar/actions/runs/34037762727
[api-import]: ../tests/application/test_api_football_fixture_import_service.py
[nfl-e2e]: ../tests/integration/test_nflverse_to_outlook_end_to_end.py
[bootstrap]: ../tests/application/test_container.py
[regional-e2e]: ../tests/integration/test_bundesliga_football_data_to_outlook.py
[api-catalog]: ../tests/application/test_api_football_catalog_service.py
[second-e2e]: ../tests/integration/test_openligadb_second_bundesliga_to_outlook.py
[pl-e2e]: ../tests/integration/test_football_data_to_outlook_end_to_end.py
[cl-e2e]: ../tests/integration/test_openligadb_champions_league_to_outlook.py
[verified-ci]: https://github.com/theMompfdie/smart-sports-calendar/actions/runs/34043888040
[pull-request]: https://github.com/theMompfdie/smart-sports-calendar/pull/275
[repeat-ci]: https://github.com/theMompfdie/smart-sports-calendar/actions/runs/34044321033
