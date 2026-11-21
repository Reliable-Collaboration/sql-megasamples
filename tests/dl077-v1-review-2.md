# Version 1, code review round 2: triage and evidence

Reviews of `550a6d9a`: Astra (`A2-1`–`A2-12`), Fable (`F2-1`–`F2-8`) and the independent extension review (`S2-1`–`S2-3`), in the coordinator's `.local/megasamples-build/`. Also DL-119, the deciders' answer on H-3. The bar is DL-040's, as in round 1. Logs are under the ignored `build/dl114-r1-work/`. Times are UTC, 2026-11-21, from the clock or the log.

Round 2's commits are `390b992`..`2bcfc82` and this record.

The candidates were built from `2bcfc82`:
- PostgreSQL `a214030eefa3` (`chinook`) and `305c9038a205` (`chinook employees pubs`);
- MySQL `6de89917b972` (binary log on) and `a6d42c9ad432` (off);
- the fallback fault image `ed34ffb336c7`.

## Triage

Overlaps are one row:
- A2-1 = F2-1 = S2-1;
- A2-6 = F2-2;
- A2-3 = F2-4;
- A2-12 = F2-5's `absent` part.

| ID | Sev. | Actor and route | Disposition | Where | Red / green / reversal |
|---|---|---|---|---|---|
| A2-1, F2-1, S2-1 | P1 | A maintainer runs `megasamples reset postgres:chinook` | **Fixed.** The extension script makes `megasamples_policy` again, so it is a member that `pg_dump` never emits. The control file installs the extension in `pg_catalog`, which no copy owner can drop. **The class:** every connectable database the image ships is dumped and restored with `--exit-on-error` into a database from `template0`. Rows, extension, trigger and routine closure are checked afterwards. | `390b992` (test), `ab2bf45` | Red: three databases failed with "already exists", and so did the real reset (`policy-restore-red.log` 05:44:06, `policy-restore-red3.log` 05:44:33). Green: `policy-restore-green3.log` 05:46:47 and `policy-r2-final-restore.log`. Reversals, one on each side: the schema outside the extension is the red; the extension in `public` fails the drop-`public` case (`policy-p1-reversal-public.log` 05:47:25). |
| S2-2 | P2 | A deployer passes `postgres -D` (or a `data_directory` setting) pointing at a retained pre-policy cluster | **Fixed.** The wrapper refuses every option that names a data directory other than `PGDATA`, and any other configuration file. | `1b1df38`, `e970e42` | Red: all five forms started the old cluster (`start-override-red.log` 05:56:43). Green: `start-override-green.log` 05:57:46 and `start-r2-final.log` 06:17:14. The red image is the reversal. |
| S2-3 | P2 | A copy owner's cancel or timeout at the commit boundary | **Decided by DL-119:** it joins the stated limit. Built here:<ul><li>the detective control in `up` and `reset --status postgres`;</li><li>the README's removal route;</li><li>the planted-orphan test;</li><li>the 480-attempt regression.</li></ul> | `c09dfef`, `c774fea`, `5ab5588` | See DL-119 below. |
| A2-2 | P2 | A maintainer runs the H-3 probe, or the native suite, against the wrong container | **Fixed.**<ul><li>**The probe:** it takes a target manifest and refuses an unlabelled container before any SQL. It requires every read to succeed and be whole, accepts only the server's own interrupt messages, and fails on any orphan seen at any point.</li><li>**The native suite:** it requires named containers carrying a task's label, and takes its store from `DL077_ISOLATED_GRAPH`.</li></ul> | `5ab5588`, `9427d87` | Controls: refused unlabelled (`h3-unlabelled.log` 06:07:19); planted orphan, exit 1 (`h3-plant.log` 06:07:29). |
| A2-3, F2-4 | P2 | A sweep after which an outside change makes the next copy unreadable or not exclusive | **Fixed.** Once a removal has completed, exit 8 with the removals and the copy where it stopped. A row removed by someone else is reported `gone`. | `552ebfe`, `8deea1f` | Red: exit 5, result null. Green: both servers. Reversal: partial handling removed (`tcp-r2-reversal-partial.log`). |
| A2-4 | P2 | An owner creates in a namespace holding a newer-format record, or from a newer-tagged template | **Fixed.** Admission reads every record under the namespace lock and refuses with `format-unknown`, leaving the ledger unchanged. A newer PostgreSQL template tag is exit 5, not 4. | `552ebfe`, `8deea1f` | Red: create exited 0; exit 4. Reversals: admission read removed; version check removed. |
| A2-5 | P2 | An owner copies a procedure or event created without `NO_AUTO_VALUE_ON_ZERO` | **Fixed.** The build records each stored program's `sql_mode`. Replay sets the zero-keeping mode only for the row copy. | `3cdf356`, `a585d4a` (tests), `4e7eaf1` | Red: the copy's routine and event modes differed (`tcp-sqlmode-red2.log` 05:58:55). Green: 22 MySQL cases, binary log on and off (`tcp-r2-final-mysql-*.log`). The red is the code without the change. |
| A2-6, F2-2 | P2 | A consumer without the system's libpq runs `copy … postgres` | **Narrowed** by stating the requirement (design 3.1, 3.3, T-28; README). Its absence is exit 3, `client-library`, with no server contacted. `psycopg[binary]` was not taken: it needs its own licence review. | `8deea1f`, `f75608a`, `2bcfc82` | Red: exit 1 `internal`. Green: in-suite, and on clean Python 3.11.18 without `libpq5`: exit 3 `client-library`. With `libpq5`, the first `copy list` exits 0 against the candidate (`t28-r2.log`, 06:22). Reversal: the import guard removed. |
| A2-7 | P2 | The connection drops while `renew` reads its metadata | **Fixed.** Exit 3 with the supplied identity, since only reads have run. §3.3's exit 8 is narrowed: a lost create reply may leave no row, and `copy list --label` settles it. | `552ebfe`, `8deea1f`, `f75608a` | Red: exit 5, no identity. Reversal: the `connection_lost` branch removed. |
| A2-8 | P2 | An owner's drop meets lock contention, or a busy already-`dropping` copy | **Narrowed.** §3.3 now promises what each case does: contention reads and changes nothing; a copy that was `dropping` stays `dropping` at its revision. Pinned by `test_busy_drop_promises_only_what_it_wrote`. | `552ebfe`, `f75608a` | A regression of existing behaviour, green on both servers. |
| A2-9 | P2 | A consumer under another UID reads a shared template directory | **Fixed.** The manifest is published 0444, like the templates. The template's mode is now asserted too (F2-7). | `6e332a7` (test), `cff2e60` | Red: the manifest was 0600. Green: as uid 4242 in a container against the build's output, `copy create` exits 0 (`sqlite-other-uid-fixed.log`). Reversal: 0600 gives exit 5 (`sqlite-other-uid-0600.log` 06:01:33). |
| A2-10 | P2 | A maintainer qualifying the candidate | **Fixed or narrowed:**<ul><li>**The writer test:** its direct sequence grant is gone. Reversal: the writer group's sequence default removed fails it (`policy-writer-reversal.log` 06:03:25).</li><li>**The owner's confinement (G-11b, G-11c) through the image:** reversal, the owner's pattern grant unescaped, fails it (`tcp-owner-reversal.log`).</li><li>**Narrowed in design 8.3:** T-11 verification, T-15 and the kill points, the full disk, and the wider account matrix are not claimed for this build, and the merge waits for them.</li></ul> | `f85e9d6`, `552ebfe`, `f75608a` | — |
| A2-11 | P3 | — | **Corrected below.** | this file | — |
| A2-12, F2-5 | P3 | A script after a volume replacement | **Fixed.** §3.5 says `gone`; a never-made name shows `gone`. | `f75608a`, `552ebfe` | Regression on both servers. |
| F2-3 | P3 | A grant of `TRUNCATE` or `ALL` to the read group | **Fixed.** The allow-list is restored. Reversal: `TRUNCATE` added, 2 failures. | `83ecf28` | — |
| F2-5 | P3 | — | **Fixed.** §2.2's sweep row admits a proven `dropping` copy, and §3.3's exit 6 is scoped. | `f75608a` | — |
| F2-6 | P3 | — | **Corrected below.** | this file | — |
| F2-7 | P3 | — | **Fixed** with A2-9. | — | — |
| F2-8 | P3 | A copy owner's `CREATE TYPE … AS RANGE` | **Recorded** as a stated limit in design 4.3. **Reopens:** a rule that every routine in a copy is closed. | `f75608a` | — |

## DL-119

| Item | Built | Evidence |
|---|---|---|
| 1. The detective control | `megasamples.postgres_orphans`: directories under `base/` and each tablespace are listed before `pg_database` is read. Each warning gives tablespace, OID, name (none), path and KiB. A failed or empty read is `orphan-scan-incomplete`. Reported by `megasamples up` (to stderr, after the stack starts) and by `megasamples reset --status postgres` (one JSON document). No new command. | 7 unit cases. Natively on `a214030eefa3`: 40 planted directories reported (`policy-r2-final-orphans.log`). Reversals: nothing reported, and a failed read treated as complete, each fail. |
| 2. The README | The removal route (quiesce, recheck the OID, shut down cleanly, quarantine, then delete); that the next volume replacement clears it; that the evidence is not proof. | `5ab5588` |
| 3. The planted-orphan test | Five later creates succeed at OIDs above every planted one. Every planted directory keeps only its own file. The report clears after removal. | `tests/test_v1_postgres_orphans.py` |
| 4. The 480-attempt regression | WAL_LOG timeout 88/32 and cancel 68/52; FILE_COPY timeout 52/68 and cancel 50/70 (committed/interrupted). Other: 0. No orphan seen at any point. | `h3-regression.log` 06:10:31 |

## Corrections to round 1's record (A2-11, F2-6)

- **`289dcf0` did have a contemporaneous red.** Its message records it, and `build/dl114-r1-previous-session/tcp-mysql-red3-result.log` shows `copy create mysql:sample` returning 8. What was missing was a committed test; this session's reversal adds attribution.
- **`7666e25` had no contemporaneous red** for `auto.cnf`. The earlier image red concerned grants and unkeyed accounts. Its evidence is the T-30 reversal (`image-test-reversal-t30.log`, 04:55:19).
- **Commit order versus red order.** All 15 previous-session commits were made between 21:57 and 22:13 CST, after their reds. `0427057` and `6eb440e` carry test and code together, so the order is in the logs, not the history.

## Test runs

**Passed**
- **The TCP server suite** at `2bcfc82`:
  - PostgreSQL: 16 passed, 9 skipped;
  - MySQL on: 22 passed, 3 skipped;
  - MySQL off: 22 passed, 3 skipped;
  - the fallback fault case passed.
- **PostgreSQL suites:** the policy suite OK (1 skipped); restore and the real reset OK; orphans OK; start, with the overrides, OK.
- **`test-image`, 0 failures each:** PostgreSQL `chinook`; PostgreSQL `chinook employees pubs`; MySQL in both modes.
- **The native strict-read suite:** PostgreSQL 46 passed; MySQL 7 passed in each mode.
- **T-28 on Python 3.11.18:** exit 0 with libpq, exit 3 `client-library` without.
- **The H-3 regression and its controls.**

**Failed**
- **The full suite:** 2 failed, 1,070 passed, 297 skipped (`pytest-r2.log`, 06:23:32). Both are round 1's baseline failures, which fail at `e61335f` too.

**Not run**
- T-11's `megasamples verify` against a copy;
- WideWorldImportersDW;
- T-15 and the kill points;
- the full disk;
- DataIntent C1.

They are now narrowed in design 8.3 as not claimed for this build.

**Unsupported**
- MySQL trigger and stored-function copies (DL-112, DL-113);
- a session-aware PostgreSQL dry run (round 1, A9);
- a bundled libpq.

## Restoration and isolation

- **Retained isolated stack.** The eight `dl077-feasibility` containers are untouched. The fingerprint ledgers were re-taken with `build/dl077-v1-work/fingerprints.py` (phase `r2-final`), and `cmp` with build 1's `after` ledgers returned 0:
  - PostgreSQL `ee0f1a8b…711e`;
  - MySQL `a5c0466a…a72f`;
  - SQLite `5b0c2768…da98`.
- **Removed:**
  - **Containers:** every task container this round started. None remains, and none is a `megasamples-reset-*` pristine container.
  - **Volumes:** the 19 anonymous volumes this round's image tests and reset runs left, each checked unused.
  - **Images:** the superseded round-1 candidates and this round's reversal images.
- **Kept for review:**
  - the round 2 candidates `localhost/dl114-r2-pg:candidate`, `:candidate-full`, `localhost/dl114-r2-mysql:candidate-true`, `:candidate-false`;
  - the fault images `localhost/dl114-r2-pg:fault-fallback`, `localhost/dl114-r1c-pg:fault-close`;
  - the runner.
- **The isolated socket service** was started for `docker` clients and stopped at the end.
- **Isolation** (`build/dl114-r1-work/isolation-check.sh`, read-only):
  - **Live deployment:** the nine live `megasamples-*` entries match the session's start by name, ID, state and health. The three live engines' IDs, start times and images are unchanged.
  - **Isolated store:** the same 20 containers with the same IDs, states, images and start times. Its volumes are the starting set less the previous session's three.
