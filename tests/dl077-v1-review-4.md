# Version 1, code review round 4: triage and evidence

These are the reviews of `03dc3f80` by Sol (`S4-1`–`S4-9`) and Opus (`O4-1`–`O4-4`), under DL-120. They are in the coordinator's `.local/megasamples-build/`.
- **Opus** found nothing to fix now.
- **Sol** raised five P2s.

Each is triaged under DL-040 below. **None was judged constructed**, so each P2 was fixed, test first. Where the two readings differed, a test decided. Logs are under the ignored `build/dl114-r1-work/`, and times are UTC, 2026-11-21.

Round 4's commits are `2632f68`..`c30a52d` and this record. The candidates were built from `c30a52d`:
- PostgreSQL `441905e40cef` (`chinook`) and `23a3adbe2e8e` (`chinook employees pubs`);
- MySQL `3a95064ec7db` (binary log on) and `0513f6494c20` (off);
- the fallback fault image `91a4c6db4614`.

## Triage

Overlaps are one row: S4-6 = O4-2.

| ID | Sev. | Actor and route | Disposition | Where | Red / green / reversal |
|---|---|---|---|---|---|
| S4-1 | P2 | A deployer with password overrides, whose preload change was persisted by `ALTER SYSTEM` and is restored on the command line | **Fixed. The two readings, reconciled by test.** Opus is right that the public launch was certified. Sol is right that the private password start reads only the files, so it ran without `read_policy`. With overrides, the wrapper now certifies the private start's configuration too: directory and preload, without the command-line arguments. | `2632f68`, `003a0b7` | Red on `8b6bd7e5bdf6`: that start was not refused (`start-r4-red2.log`). Green: refused; without overrides the same command starts with the hook and refuses the owner's out-of-namespace `CREATE DATABASE` (`start-r4-green3.log`). The red image is the reversal. |
| S4-2 | P2 | A maintainer's native run while another task reuses the checked container's name | **Fixed.** The suite records the ID it checked, with a nonempty exact owner, and uses that ID for every exec and endpoint lookup. | `41d1ab6` | Control: a checked ID refers to nothing after its container is replaced under the same name (`native-name-reuse-control.log`, 07:42). |
| S4-3 | P2 | An operator's `reset --status` with a tablespace mount inaccessible | **Fixed.** `du`'s status is checked on its own. A location or `PG_*` directory that cannot be listed prints `unreadable`. A catalogued tablespace the listing never acknowledged makes the scan incomplete. | `9d73fe2`, `c96a606` | Red: 5 unit cases; natively an unreadable tablespace location gave `complete` (`policy-r4-orphans-red.log`). Green: 14 unit cases running the real listing under `sh`, and natively (`policy-r4-orphans.log`). |
| S4-4 | P2 | A namespace owner's sweep whose ledger delete fails after the engine dropped the copy | **Fixed.** The ledger delete is its own step, `forget()`. After a confirmed drop, its failure is exit 8, `drop-unsettled`, with the copy reported `gone` and `ledger: unsettled`: in a sweep under `removed`, never `kept`, and in a single `drop` as its result. | `c3f976a`, `9c34c9f` | Red: not reported removed. Green: both servers. Reversal: the entry in `removed` taken out fails (`tcp-r4-copy-reversal-ledger.log`). |
| S4-5 | P2 | A namespace owner's `drop` losing its connection at the removal's proof read | **Fixed.** Exit 3 with the identity, and the copy stays `ready` at its revision. The drop itself now counts as a write, also when resuming a `dropping` record. | `c3f976a`, `9c34c9f` | Red: exit 8. Reversal: the classification removed fails (`tcp-r4-copy-reversal-loss.log`). |
| S4-6, O4-2 | P3 | A placeholder `read_policy.loaded` on a server without the library | **Fixed.** The healthcheck also asks the server to change the setting and requires its refusal, `55P02`, which only the registered setting gives. `demo` cannot read `pg_settings`, because `pg_show_all_settings` is outside its allow-list. | `e8d0b21`, `6baaf51` (test only), `b23c59b` | Red: with the wrapper bypassed and a `demo` role default, the old probe passed. Green: that probe fails, and on the image it passes (`health-r4.log` 07:36:43). |
| S4-7 | P3 | A quoted preload entry | **Fixed.** Refused, not split on its commas. | `2632f68`, `003a0b7` | In `start-r4-green3.log`. |
| S4-8 | P3 | A program created under `NO_BACKSLASH_ESCAPES` | **Fixed.** Withheld as `not-replayable`, like `ANSI_QUOTES`. | `f5ecd84`, `405da31` | Red: create exit 8 (`tcp-r4-nbe-red.log`). Green: exit 4 before any reservation. |
| S4-9 | P3 | Round 3's controls | **Recorded and run:**<ul><li>**Closure:** a fault that leaves the trigger enabled and makes its function do nothing fails the privilege assertion: `'t' != 'f'`, 4 failures (`policy-r4-closure-reversal2.log`).</li><li>**`template1`:** a query that drops template databases fails the set assertion (`policy-r4-template1-reversal.log`).</li><li>**The H-3 probe's client-only accounting:** its output columns separate the counts. Only a run with a cell lacking server interrupts would fail it, and none was planted. That stays a recorded limit of the control.</li></ul> | — | — |
| O4-1 | P3 | A path-form command | **Reconciled by test and fixed.** As a non-root user the image already fails closed before any start, because its health passfile under `/run` is root's to write. As root, the path form is now accepted only for the image's own `postgres` and run by name, so the overrides apply. | `2e060f8` (test only), `003a0b7` | Red: as root, refused by `postgres` itself. Green: it starts with the override applied. |
| O4-3 | P3 | The concurrent-drop case | **Fixed.** It is a behaviour test now: the real listing under `sh`, with a `du` shim that removes the directory. The README, the module and design 3.5a now say a drop in progress can appear once. | `9d73fe2`, `c30a52d` | — |
| O4-4 | P3 | The start refusals | **Fixed.** The README states each one, the ownership repair (now made before the check, as root) and the healthcheck's condition. | `003a0b7`, `c30a52d` | The ownership case is in `start-r4-green3.log`. |

## Test runs

**Passed**
- **The TCP server suite** at `c30a52d` (`tcp-r4-final-*.log`):
  - PostgreSQL: 23 passed, 12 skipped;
  - MySQL on: 32 passed, 3 skipped;
  - MySQL off: 32 passed, 3 skipped;
  - the fallback fault case passed.
- **PostgreSQL suites:** the policy suite OK (1 skipped); restore and the real reset OK; orphans OK, with the unreadable tablespace case; start OK, with every route of rounds 2 to 4; the healthcheck, unit and native placeholder cases, 2 passed.
- **`test-image`, 0 failures each:** PostgreSQL `chinook`; PostgreSQL `chinook employees pubs`; MySQL in both modes.
- **The native strict-read suite:** PostgreSQL 46 passed; MySQL 7 passed in each mode.
- **The H-3 regression**, 480 attempts on `441905e40cef` (committed / server-interrupted / client-only):
  - WAL_LOG timeout 88/32/0, cancel 72/33/15;
  - FILE_COPY timeout 35/85/0, cancel 34/73/13;
  - other 0, no orphan seen at any point, and every cell has a server interrupt (`h3-r4-regression.log`, 07:58:25).
  - The first attempt in the batch did not start: MemAvailable was below 15 GiB, and the runner refused. It was rerun.

**Failed**
- **The full suite:** 2 failed, 1,078 passed, 312 skipped (`pytest-r4.log`, 07:48:19). These are the same two baseline failures as before, and both fail at `e61335f` too.

**Not run**
- T-11's `verify` against a copy;
- WideWorldImportersDW;
- T-15 and the kill points;
- the full disk;
- DataIntent C1.

Each is listed in design 8.3 as not claimed.

**Unsupported**
- MySQL copies of trigger, stored-function, `ANSI_QUOTES` and `NO_BACKSLASH_ESCAPES` programs;
- restoring the character set and collation;
- a session-aware dry run;
- a bundled libpq;
- a non-root start of the PostgreSQL image.


## Restoration and isolation

- **Retained isolated stack.** The eight `dl077-feasibility` containers are untouched. The fingerprint ledgers (phase `r4-final`) are byte-identical to build 1's `after` ledgers:
  - PostgreSQL `ee0f1a8b…711e`;
  - MySQL `a5c0466a…a72f`;
  - SQLite `5b0c2768…da98`.
- **Removed:**
  - every task container this round started;
  - this round's 41 anonymous volumes, each checked unused;
  - the superseded round 3 and intermediate images.
- **Kept for review:**
  - the round 4 candidates `localhost/dl114-r4-pg:candidate`, `:candidate-full`, `localhost/dl114-r4-mysql:candidate-true`, `:candidate-false`;
  - the fault images `localhost/dl114-r4-pg:fault-fallback`, `localhost/dl114-r1c-pg:fault-close`;
  - the runner.
- **The isolated socket service** was stopped; its socket no longer answers.
- **Isolation** (`build/dl114-r1-work/isolation-check.sh`, read-only):
  - **Live deployment:** the nine live `megasamples-*` entries match the session's start by ID, state, health, start time and image.
  - **Isolated store:** the same 20 containers as at the start.
