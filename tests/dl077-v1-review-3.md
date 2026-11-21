# Version 1, code review round 3: triage and evidence

These are the reviews of `13b41892` by Sol (`S3-1`–`S3-8`) and Opus (`O3-1`–`O3-6`), under DL-120. They are in the coordinator's `.local/megasamples-build/`. The bar is DL-040's, as before. Logs are under the ignored `build/dl114-r1-work/`, and times are UTC, 2026-11-21.

Round 3's commits are `43a8fca`..`9b3d779` and this record.

The candidates were built from `9b3d779`:
- PostgreSQL `8b6bd7e5bdf6` (`chinook`) and `53fa47381ee0` (`chinook employees pubs`);
- MySQL `84f8337827e6` (binary log on) and `af595e15d6f7` (off);
- the fallback fault image `7b61952fbf34`.

## Triage

Overlaps are one row: S3-1 = O3-1; S3-2 = O3-5; S3-4 = O3-2; S3-7 = O3-6's probe part; S3-8 = O3-4.

| ID | Sev. | Actor and route | Disposition | Where | Red / green / reversal |
|---|---|---|---|---|---|
| S3-1, O3-1 | P2 | A deployer starts with `DATA_DIRECTORY` in upper case, a command given by path, or a preload list without `read_policy` (set by `-c` or persisted by `ALTER SYSTEM`) | **Fixed, by class.** For any command whose basename is `postgres`, the wrapper asks the server itself (`-C data_directory`, `-C shared_preload_libraries`, run as `postgres` with the same arguments). That reads every file and option together. It refuses unless the directory is the marked `PGDATA` and the list holds `read_policy`. **In depth:** the library defines `read_policy.loaded` (`PGC_INTERNAL`), and the compose healthcheck requires it to be `on`. The old literal `config_file` refusal is gone, because `-C` covers it. | `43a8fca`, `040886b` (test-only), `ca6edc1` | Red on round 2's `a214030eefa3`: the upper-case, mixed-case and path forms got past, a replaced preload started, `read_policy.loaded` was unrecognised, and its healthcheck exited 1 (`start-r3-red.log`, `policy-r3-red.log` 06:42:37, `health-r3.log`). Green: every form refused; with `read_policy` among others the server reports it loaded and refuses the owner's out-of-namespace `CREATE DATABASE`; healthcheck 0 (`start-r3-green2.log`, `policy-r3-green.log`, `health-r3.log` 06:46:05). The red image is the reversal. |
| S3-2, O3-5 | P2 | An operator runs `reset --status postgres` or `up` while a database is dropped | **Fixed.** Each directory is measured with a checked `du`. One gone since the glob is skipped; one that cannot be measured makes the scan incomplete. A malformed line is incomplete, never a traceback. The reported path is the one inspected, with `PG_*` for a tablespace. | `e3e2de6`, `3d7b627` | Red: 4 unit cases; natively the tablespace path lacked `PG_*` (`policy-r3-orphans-red.log`). Green: 11 unit cases, and natively a real tablespace orphan is reported with its path (`policy-r3-orphans.log` 06:47:10). |
| S3-3 | P2 | A maintainer points the native suite at another task's container | **Fixed.** The label must equal `STRICT_READ_OWNER` exactly. | `265aba3` | Control: a target with another owner refused (see Test runs). |
| S3-4, O3-2 | P2 | A sweep whose unlock fails after a removal; a dry run meeting an unreadable record; a sweep after a busy rollback | **Fixed.** A dry run re-raises exit 5. Exit 8 with the partial result follows any removal or any written rollback. A removed copy is never also listed as kept. | `79d1ebf` (tests), `887cc92` | Red: dry run exit 8; busy, then unreadable, exit 5; the copy listed both removed and kept (`tcp-r3-sweep-red-*.log`). Green: both servers. Reversals: each rule removed fails its case (`tcp-r3-reversal-*.log`). |
| S3-5 | P2 | A namespace owner's `renew` or `list` loses its connection while reading a record | **Fixed.** Each engine notes when it issues a write. A connection lost before any write is exit 3 with the identity; after one it stays 8. | `887cc92` | Red: exit 8. Reversal: the `wrote` check removed fails both cases. |
| S3-6 | P3 | The restore matrix missing `template1` | **Fixed.** `template1` is included, and the suite's `v1_` fixtures are excluded by name. | `0afce63` | Green: `policy-r3-restore.log` 06:57:49. |
| S3-7, O3-6 | P3 | The H-3 probe crediting a client-only exit as a server interrupt | **Fixed.** Client-only exits are counted apart. Each strategy and method must see at least one server interrupt. The change rode in `9b3d779`, together with that commit's design text. | `9b3d779` | Regression, 480 attempts: WAL_LOG timeout 93 committed / 27 server-interrupted / 0 client-only, cancel 82/23/15; FILE_COPY timeout 70/50/0, cancel 70/34/16. Other 0; no orphan seen at any point; every cell has a server interrupt (`h3-r3-regression2.log` 07:05:05). |
| S3-8, O3-4 | P3 | An owner copying programs with distinct modes, an event with its own time zone, an `ANSI_QUOTES` program, or a template of an older format | **Fixed or stated.** The fixture builds `sample_start` through the build's own `offer()`. Procedure and event have distinct modes, and the event its own time zone; all are restored per program. An `ANSI_QUOTES` database is withheld (`not-replayable`). An older template is `format-unknown` before any reservation. `character_set_client` and `collation_connection` are recorded, not restored: a stated limit (design 2.4). | `544272a`, `9f9270f` (tests), `5d1590a`, `9b3d779` | Red: event zone `SYSTEM`; ANSI create exit 8; older template accepted (`tcp-r3-mysql-red.log`). Green: 29 MySQL cases (`tcp-r3-mysql-green.log`). Reversals: zone, ANSI and format each fail (`tcp-r3-mysql-reversal-*.log`). |
| O3-3 | P3 | The restore test's closure probe | **Fixed.** The probe's creator has no default ACL, so only the trigger can close the routine. | `0afce63` | Reversal: the trigger disabled before the probe fails every database (`policy-r3-restore-reversal.log`). |
| O3-6 | P3 | The records | **Fixed.** `reset --status ENGINE` has design section 3.5a. The `config_file` refusal no longer exists. The probe wording is corrected here. | `9b3d779` | — |

## Test runs

**Passed**
- **The TCP server suite** at `9b3d779` (`tcp-r3-final-*.log`):
  - PostgreSQL: 21 passed, 11 skipped;
  - MySQL on: 29 passed, 3 skipped;
  - MySQL off: 29 passed, 3 skipped;
  - the fallback fault case passed.
- **PostgreSQL suites:** the policy suite OK (1 skipped); restore, with `template1`, and the real reset OK; orphans OK, with the real tablespace case; start OK, with every directory form and both preload routes.
- **`test-image`, 0 failures each:** PostgreSQL `chinook`; PostgreSQL `chinook employees pubs`; MySQL in both modes.
- **The native strict-read suite:** PostgreSQL 46 passed; MySQL 7 passed in each mode.
  - Control: the same suite with `STRICT_READ_OWNER=dl077-another-task` errored on all 7 cases, refusing the label `dl077-r1c-native` (`native-r3-owner-control.log`).
- **T-28 on Python 3.11.18 against `8b6bd7e5bdf6`:** exit 0 with libpq, exit 3 `client-library` without (`t28-r3.log`).
- **The H-3 regression**, as above.

**Failed**
- **The full suite:** 2 failed, 1,075 passed, 307 skipped (`pytest-r3.log`, 07:11:03). These are the same two baseline failures as rounds 1 and 2, and both fail at `e61335f` too.

**Not run**
- T-11's `verify` against a copy;
- WideWorldImportersDW;
- T-15 and the kill points;
- the full disk;
- DataIntent C1.

Each is listed in design 8.3 as not claimed for this build.

**Unsupported**
- MySQL trigger, stored-function and `ANSI_QUOTES` program copies;
- restoring `character_set_client` and `collation_connection`;
- a session-aware PostgreSQL dry run;
- a bundled libpq.


## Restoration and isolation

- **Retained isolated stack.** The eight `dl077-feasibility` containers are untouched. The fingerprint ledgers (phase `r3-final`) are byte-identical to build 1's `after` ledgers:
  - PostgreSQL `ee0f1a8b…711e`;
  - MySQL `a5c0466a…a72f`;
  - SQLite `5b0c2768…da98`.
- **Removed:**
  - every task container this round started;
  - this round's 37 anonymous volumes, each checked unused;
  - the superseded round 2 and reversal images.
- **Kept for review:**
  - the round 3 candidates `localhost/dl114-r3-pg:candidate`, `:candidate-full`, `localhost/dl114-r3-mysql:candidate-true`, `:candidate-false`;
  - the fault images `localhost/dl114-r3-pg:fault-fallback`, `localhost/dl114-r1c-pg:fault-close`;
  - the runner.
- **The isolated socket service** was stopped at the end.
- **Isolation** (`build/dl114-r1-work/isolation-check.sh`, read-only):
  - **Live deployment:** the nine live `megasamples-*` entries match the session's start by ID, state, health, start time and image.
  - **Isolated store:** the same 20 containers. Its volumes are the starting set less the previous session's three.
