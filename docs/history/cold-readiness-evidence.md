# Cold-readiness gate for every engine

This follow-up starts at PR #11 head `c854f399dfc2e81845b1691f71f094e2746b2dec`.
The pre-dataset main is `d97445d2c9d9d4b0c81697f5acb7408b7ae6364e`. No engine, client,
dataset input, expected count or fingerprint is changed by this follow-up.

The same startup policy now applies to MySQL, PostgreSQL and SQLite in
[image_startup.py](../../megasamples/engines/image_startup.py). Cold copy/run means elapsed
time until detached run returns, including fresh-volume materialization and runtime launch
overhead. Its limit is `ceil(2 * observed maximum / 10) * 10`, considering both compared
images where available. This is the earlier PostgreSQL rule, unchanged. The server clock
starts at run return and keeps its independent **30-second** limit. Both must pass.
A late copy still gets a full server probe window and reaches data checks if a query succeeds.
PostgreSQL also gains a true independent copy limit rather than a combined copy/query cap.

The measured maxima derive limits of **170 s MySQL, 180 s PostgreSQL, 150 s SQLite**.
The limits were derived before running the complete image checks; no failed full-image
timing result was used to tune them. The clock is monotonic.

## Measurements

Six fresh anonymous-volume starts were measured for each PR #11 image and six each for
the retained main MySQL and SQLite images: **30 starts**. Runs were sequential and paired;
engine and main/PR order were reversed on alternate rounds (counterbalanced AB/BA pairs).
No ports were published and host caches were not dropped. Every sample had a distinct
volume; each sample container and volume was removed after recording it. The retained main
image IDs match the [client receipt](../validation/client-upgrade-2026-11-17.json) inventory.
PR image IDs match the [dataset receipt](../validation/dataset-upgrade-2026-11-17.json).

| Engine / image | Samples | Copy/run min–max (s) | Copy/run median (s) | Query after run min–max (s) | Reported ready to query min–max (s) |
|---|---:|---:|---:|---:|---:|
| mysql / main | 6 | 31.803–69.677 | 54.697 | 1.433–2.111 | 0.080–0.271 |
| mysql / pr11 | 6 | 32.071–83.762 | 63.606 | 1.431–2.205 | 0.039–0.347 |
| sqlite / main | 6 | 28.310–65.938 | 54.438 | 0.095–0.140 | 0.102–0.153 |
| sqlite / pr11 | 6 | 30.926–71.862 | 60.685 | 0.073–0.172 | 0.080–0.183 |
| postgres / pr11 | 6 | 40.372–85.274 | 65.410 | 0.414–0.607 | 0.273–0.324 |

Reported ready means the server-ready log timestamp for MySQL/PostgreSQL. SQLite is a
file container with no database daemon; its process-start timestamp is the corresponding
event. Queries were polled immediately after run return, so polling/exec latency is included.
The server gate begins before the reported-ready event, retaining the stronger 30-second
expectation. Each raw record includes wall time, immutable image ID, fresh volume name,
registry and both query intervals.

| Engine / image | Immutable data regular-file bytes | Allocated file bytes | Complete image bytes |
|---|---:|---:|---:|
| mysql / main | 21,653,516,735 | 21,653,839,872 | 22,414,660,184 |
| mysql / pr11 | 22,953,654,938 | 22,953,992,192 | 23,714,853,606 |
| sqlite / main | 19,008,032,768 | 19,008,065,536 | 19,045,846,804 |
| sqlite / pr11 | 19,179,147,264 | 19,179,188,224 | 19,216,963,860 |
| postgres / pr11 | 22,443,408,360 | 22,443,835,392 | 22,931,498,793 |

Data files were inspected in immutable image mounts inside the isolated rootless user
namespace, without starting a server. Hard links are counted once, directories and symlinks
are excluded from the regular-file totals, and allocated blocks are filesystem dependent.
Image mounts created by the size inspection were unmounted. Query-ready directory sizes
are also retained per sample and include small startup writes.

MySQL adds `bts_ontime`, `wideworldimporters` and `wideworldimporters_dw`: 27 → 30 physical
databases, with no removed database. SQLite adds `wideworldimporters_dw`: 27 → 28.
The PR PostgreSQL registry consistently lists 28 physical databases. Logical append
selectors share databases, so these are not logical-dataset counts.

MySQL data file bytes grow about 6.0%; median copy/run time grows from 54.697 to 63.606 s.
SQLite data bytes grow about 0.9%; median copy/run grows from 54.438 to 60.685 s.
The broad overlap and variation do not establish a stable linear time-per-byte relationship
or a clean causal slope for the added content. All images require copying the entire baked
corpus; server/query times remain small. No change to the existing twice-maximum rule is
justified by these measurements. See the raw sample values rather than treating the medians
as a live startup guarantee.

## Regression cases

Before the code change, the eleven engine-specific cases produced **Failed: 4; Passed: 7**.
The four expected failures were:

- MySQL: a 65-second copy and query at 66 seconds should pass and still check data.
- SQLite: a 35-second copy and query at 36 seconds should pass and still check data.
- PostgreSQL: a 95-second copy and query at 115 seconds should pass the independent limits.
- SQLite: a 1000-second copy must fail its copy gate while still checking data after a prompt query.

After the shared helper and measured limits, **Passed: 26 regression cases**. The PostgreSQL
independent-limit case follows the measured copy limit so it still exceeds a combined cap.
The tests retain slow-server and excessive-copy rejection, add exact-limit/just-over-limit
coverage for every engine, and prove an absent server gets a finite 30-second probe window
even after an excessive copy. MySQL and SQLite integration cases verify counts and
integrity checks still execute after a late copy. No data assertion was weakened.

Tests live in `tests/test_image_startup.py` and the three `test_*_image_startup.py` files.
Unabridged before/after logs are retained under `build/cold-readiness/` with hashes in the receipt.

## Validation and isolation

<!-- final-validation:start -->
All requested current image and repository gates **Passed**. The earlier failures remain
historical evidence and do not represent the final result.

| Validation | Status | Result |
|---|---|---|
| Complete mysql image | Passed | 428.81 s; 33 configured dataset count checks; zero failures |
| Complete postgres image | Passed | 248.63 s; 31 configured dataset count checks; zero failures |
| Complete sqlite image | Passed | 760.34 s; 31 configured dataset count checks; zero failures |
| Repository gate and whole test suite | Passed | 211 tests; 28.06 s total |
| Startup regressions after change | Passed | 26 cases; expected before-change failures retained |
| Runbook syntax | Passed | 8 shell blocks; 5 embedded Python fragments |
| Isolated and default-store comparison | Passed | Twelve expected isolated project containers; three live containers match baseline exactly |
| GitHub CI | Not run | No checks reported on this branch |
| BTS / WWI OLTP on PostgreSQL / SQLite | Unsupported | Existing four dispositions retained |
| Oracle native verification | Not run | Pending owner; no terms accepted |

30 unloaded port records were Not run in the current repository gate; prior reproduction
evidence remains intact. The final full-image startup observations were:

| Engine | Copy/run (s) | Query after run (s) | Limits (s) |
|---|---:|---:|---:|
| mysql | 21.3 | 1.7 | 170 / 30 |
| postgres | 22.6 | 0.4 | 180 / 30 |
| sqlite | 26.1 | 0.1 | 150 / 30 |

The [committed receipt](../validation/cold-readiness-2026-11-17.json) records commands, raw
measurements, image IDs, implementation/log hashes, initial infrastructure failures and
final results. Only this run's recorded test volumes and API process were cleaned up.
Default-store inspection was read only; no forwarding service was operated. Merge is
authorized after verifying PR #11 matches the validated head, using a merge commit.

<!-- final-validation:end -->

The first complete-check attempt was **Failed** before any test container started: the
isolated Docker API socket was unavailable. Native Podman had handled the measurements.
The three failures and the separate repository-gate pass are retained under
`build/cold-readiness/api-unavailable/`. A new API process was started for this isolated
store, and the container-side client confirmed its graph root before the full rerun.
This recovery changes no gate or expectation.

The four existing Unsupported pairs remain BTS and WWI OLTP on PostgreSQL and SQLite.
The [generated-expression guard](https://github.com/Reliable-Collaboration/sql-megasamples/blob/d97445d2c9d9d4b0c81697f5acb7408b7ae6364e/megasamples/port/ddl.py#L192-L207)
was read locally at **2026-11-17T11:11:24.360297+00:00**. The translator was not extended;
prior attempted-command evidence remains in the dataset receipt. These pairs were not
attempted again. Oracle native verification stays **Not run**, pending the owner; no terms
were accepted by this run.

The [live runbook](live-upgrade-runbook.md) records per-engine data sizes, copy/server
times and limits, the old/new comparisons, and maintenance-window exclusions. The 590 s
sum of copy/server ceilings for serialized starts is not a measured outage: cold backups,
shared SQLite console publication, health scheduling, fingerprint checks, DataIntent and
rollback require separate time.

Live cutover/rollback, DataIntent suites, Docker/BuildKit execution, other architectures
and fresh canonical fingerprints for the earlier 90-pair matrix are **Not run** here.
The earlier fingerprint receipts remain intact; complete configured image checks are
the requested current data gate. No engine/client release was selected or publisher
support status reassessed in this task; earlier vendor URLs/read times remain in the locks.
