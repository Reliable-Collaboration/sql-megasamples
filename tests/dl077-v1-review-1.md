# Version 1, code review round 1: triage and evidence

Reviews of `6c5b614`: Astra (`A1`–`A14`), Fable (`F1`–`F21`) and the independent hook review (`S1`–`S7`), in the coordinator's `.local/megasamples-build/`. The bar is DL-040's: actor, supported entry point, precondition, observable outcome; a deferral has its witness and what reopens it. Every P1 and P2 below is fixed or narrowed. Logs are under the ignored `build/dl114-r1-work/` (this session) and `build/dl114-r1-previous-session/` (the stopped session's `.review1/`, moved unchanged). Times are UTC, 2026-11-21, from the clock or the log.

The work is in two parts. The previous session made 15 commits over `6c5b614` (`5027bf0`..`18ef570`) and left uncommitted work. This session took over at `18ef570` and made `47eddf0`..`9b825ca` and this record.

## Triage

Overlaps are one row: A1 = S1; A12 = F4; A13 = F2 = F10 (evidence); A8 = F5; A9 = F17; A4 = F6; A7 = F13; A14 = F16; A10 = F1; A11 = F2's expectation part.

| ID | Sev. | Actor and route | Disposition | Where | Red / green / reversal |
|---|---|---|---|---|---|
| A1, S1 | P1 | A copy owner, by SQL in its own copy, makes a temporary `pg_proc`, then a routine | **Fixed.** The trigger is `SET search_path = pg_catalog, pg_temp`; every relation, type, operator and function is schema-qualified. | `0427057` | Red at `6c5b614`: the reader executed the routine (`pg-trigger-red.log`, 21:54 CST). Green on the candidate (`policy-cand2.log`, 04:50:39). Reversal: the red is the code without the fix. |
| S2 | P1 | A copy owner drops `public` with `CASCADE` in a disposable copy | **Fixed.** The extension is created `WITH SCHEMA megasamples_policy`, a schema `postgres` owns and the extension does not; the control file pins it. | `0427057` | Red at `6c5b614` (`pg-trigger-red.log`). Green (`policy-cand2.log`). |
| S3 | P1 | A deployer mounts a pre-policy PostgreSQL 18 volume under the new image | **Fixed.** The build writes `megasamples-read-policy` = `1` into `PGDATA`; the wrapper refuses to start without it (regular file, not a link). | `0427057` | Red: the old cluster started (`pg-start-red.log`, 21:56 CST). Green on the candidate against the `e61335f` image `41ab1eb7a345` (`policy-start.log`, 05:00:06). |
| A2 | P1 | A script sweeps a directory holding an expired copy and, later in name order, an unknown-version sidecar | **Fixed.** Every record is classified before the first deletion; a record that changes after deletions began is exit 8 with the partial `removed`/`kept`. A previous-format sidecar is classified before its phase and only an explicit `drop` removes it. | `6eb440e` | Red: 10 SQLite CLI cases (`sqlite-red.log`, 21:54 CST). Green: 27 (`sqlite-green.log`). In the final suite. |
| A3 | P2 | A script supplies a value after `--password-stdin`; JSON stdout is retained | **Fixed.** Usage errors never echo argv. Every server TCP test also asserts the fixture's key is absent from both streams, by file and by standard input. | `6eb440e`; `tests/test_v1_server_copy.py` `copy_command` | Red: three canary cases (`sqlite-red.log`). |
| A4, F6 | P2 | An administrator grants `DROP` on `copy\_%`; or a deployer declares `reader_b` with scope `copy`; or a table-level grant exists | **Fixed.** `create` classifies as `show`; the grant view excludes exactly a declared reader's `SELECT, SHOW VIEW` on the pattern, and adds table, column and routine grants as warnings. | `31a87a9` | Red (`tcp-red-mysql.log`, 04:33). Green (`tcp-k5k6-green-mysql.log`, 04:43:01). Reversals: view without the exclusion and the narrower grants (`tcp-k5-reversal-mysql.log`); `create` always `ready` (`tcp-k5-reversal-create-mysql.log`). |
| A5 | P2 | A deployer offers WideWorldImportersDW, whose key `0` means Unknown | **Fixed** by `289dcf0` (`NO_AUTO_VALUE_ON_ZERO` around replay, restored after). Its test came with the committed fixture's zero row. | `289dcf0`, `ab3cb77`, `1134496` | Its commit had no committed test. Established here: with `289dcf0` reverted, `copy create` of the zero-key fixture exits 8, `create-unsettled` (`tcp-reversal-289dcf0.log`). Green in every MySQL run since. WWI itself was not built (see Not run). |
| A6 | P2 | An owner's `drop` is killed after the durable `dropping` write | **Fixed.** A real sweep finishes an expired, proven `dropping` copy, on both servers (SQLite: `6eb440e`). | `d92a308` | Red (`tcp-red-pg2.log`, `tcp-red-mysql.log`). Green (`tcp-k2-green-*.log`, 04:35). The one hunk is the change. |
| A7, F13 | P2 | The reply to a committed reservation or lease write is lost | **Fixed.** Exit 8 with the issued or supplied identity (`create-unsettled`, `lease-unsettled`, `connection-lost`). | `cc3dc49` | Red: exit 1, null identity, four cases each engine. Green (`tcp-k3-green-*.log`). Reversals: identity not carried (`tcp-k3-reversal-identity-pg.log`); all errors internal (`tcp-k3-reversal-exit-mysql.log`). |
| A8, F5 | P2 | An administrator, or a MySQL owner, makes `copy_scratch` | **Fixed** on all three engines: listed and kept as `unmanaged`. | `6eb440e`, `ce52c2a` | Red and green on both servers; reversal: the copy-form filter restored, both failed (`tcp-k1-reversal-*.log`). |
| A9, F17 | P2 | An owner drops a copy a session is using, with or without `--wait` | **Fixed and narrowed.** One deadline spans the lock and the engine wait; MySQL honours a wait above five seconds. Design narrowed: exit 6 promises data and sessions as they were and the record `ready` again, with its revision advanced; a dry run reports the selection, and a copy the engine refuses is kept `busy` by the real sweep only. | `6ac25b2` (test only), `1d9bace` | Red: 6.03 s for a 4 s wait and a refused 15 s wait (MySQL); 20.3 s for 12 s (PostgreSQL, `tcp-k4-red2-pg.log`). Green (`tcp-k4-green2-*.log`). Reversal: MySQL's five-second cap (`tcp-k4-reversal-cap-mysql.log`). **Reported, not built:** a session-aware preview needs `pg_stat_get_db_numbackends(oid)` granted to the owner, outside the reviewed allow-list. That adds surface. |
| A10, F1 | P2 | A maintainer runs `megasamples test-image` on the candidate | **Fixed** by test-only commits `dcfd952`, `0796fe7`, `5208581`, `f9b4fbf`, `7666e25`, `18ef570`, each with its reason. | — | Red: 5 PostgreSQL and 2 MySQL failures (`pg-image-red.log`, `mysql-image-red.log`, 21:58 CST). Green on this session's candidates: PostgreSQL `chinook`, and `chinook employees pubs`; MySQL in both log modes (`image-test-cand-*.log`). |
| A11, F2 | P2 | An accidental schema-level write grant to MySQL `demo` | **Fixed.** `demo`'s exact grant set is pinned in the image test and the native suite (`5208581`). T-9's reversals: `*.*` restored, and one underscore left unescaped, each fail `test-image` (`image-test-reversal-t9-*.log`, 04:53–04:54). The documentation expectations changed in the test-only `15f5ced`. | `5208581`, `15f5ced` | The build-1 history's expectation edits inside implementation commits stay as they are, recorded here. |
| A12, F4 | P2 | A consumer installs the package and runs `copy list postgres` | **Fixed.** Licence reviewed first (`5027bf0`, corrected in `47eddf0`: the project is Apache-2.0, not MIT). Psycopg 3.3.9 is `LGPL-3.0-only`, a separately installed requirement. No image installs the package. Runtime dependencies are the two drivers (`9403495`). | `5027bf0`, `47eddf0`, `9403495`, `0c2069e`, `972c673` | Red: metadata (`package-red.log`). T-28: a wheel from a `git archive` on Python 3.11.18, 3.12.16, 3.13.18 and 3.14.10 installs only the drivers and their dependencies, with no pipeline module importable (`t28-clean-install.log`). The first `copy list postgres` from that install, with no checkout and no container runtime, exits 0 against the candidate (`t28-first-command.log`, 05:08:17). Reversal: `import yaml` planted in `copying.py` fails the in-suite check (`t28-reversal.log`). `uv lock --check` passes with uv 0.12.21 and 0.13.8, and 0.13.8's `uv lock` changes nothing (`uv-0.13.8-check.log`). |
| A13, F2, F10 | P2 | The record of test-first evidence | **Narrowed to a recorded gap plus new reversals.** The positive MySQL replay test and several build-1 expectation edits came after their code; that history stays. This round adds a red or a reversal for each rule it touches, listed under "Classes" below. | this file | — |
| A14, F16 | P3 | A script retrying a refused SQLite create | **Recorded.** Each refusal leaves a lock file. No record or data is affected; a sweep ignores them. **Reopens:** a lock-file count that matters to a deployer, or any change to the lock protocol. | — | — |
| F3 | P2 | A reader of README or `.env.example` | **Fixed.** The MySQL guard reads the image's generator, `demo_read_grants`, and the bootstrap SQL holds no `demo` grant; the text is corrected for both engines. | `a557cb3`, `15f5ced`, `bfb336b` | `a557cb3` had no recorded red, and its test came after it. Established here: with `GRANT SELECT, SHOW VIEW ON *.*` restored in `00-users.sql`, the guard fails "Review additional MySQL bootstrap grants" (`reversal-a557cb3-bootstrap-grant.log`). The documentation red is `docs-red.log`. |
| F7 | P2 | A builder selects a MySQL database near 512 MiB | **Fixed.** Allocated tablespace bytes, plus non-InnoDB files. | `566ce73` | Red: 1,654,784 against 2,777,088 allocated (`tcp-red-mysql.log`). Green. Reversal (`tcp-k6-reversal-mysql.log`). |
| F8 | P2 | Anyone rerunning slice 2's evidence | **Fixed.** The fixture, the fault switch (`insert`/`change` disconnects, `short-fill`, `renew-first`) and the PostgreSQL close faults are committed. The probes are now assertions: the SELECT-only grant, the drop after `DROP` is revoked, a marker removed (`test_drop_refuses_a_copy_whose_proof_changed`), `auto.cnf` (`7666e25`). | `ab3cb77`, `652cb7f`, `ab3f35c`, `9b825ca` | The SQLite template's mode 0444 is set by the fixture, not asserted. Still open, as F8 named it. |
| F9 | P2 | `test-image` on the MySQL image | **Fixed** (`7666e25`). T-30's reversal, the removal taken out of the build, fails it (`image-test-reversal-t30.log`, 04:55:19). | `7666e25` | — |
| F11 | P2 | The full suite's failures | **Attributed.** The two PostgreSQL documentation cases are fixed (`15f5ced`, `bfb336b`). The eight rollback cases fail identically at `e61335f`: see "Baseline". | — | — |
| S4 | P2 | A copy owner sets a statement timeout or sends a cancel during `copy`'s `CREATE DATABASE` | **Handled as DL-113 says.** 480 caller interrupts across both strategies left no directory without a catalog row, and every committed copy was closed. The README states the accepted limit. A caller-caused leftover has not been seen; if one is, it returns to the deciders. | `20b1281` | `h3-interrupts-committed.log` (05:04–05:07); control: a planted `base/424242` is reported, exit 1 (`h3-interrupts-control.log`). Not a proof that the window is closed. |
| S5 | P2 | The built-image regression for G-29b | **Fixed** (`0427057`: the unregistered source has its own valid destination). Reversal: `registered_template()` removed from the hook. Both the `megasamples` and the owner-database cases fail (`policy-s5-reversal.log`, 04:51:09). | `0427057` | Green (`policy-cand2.log`). |
| S6 | P3 | `v1_other` creates a database, then `ALTER DATABASE … OWNER TO` a role it does not inherit | **Recorded.** Rule 1 is specified at creation only. **Reopens:** a decision that transfers are confined too. | — | — |
| S7 | P3 | A copy owner with separately provisioned default ACLs runs `DROP OWNED` | **Recorded.** Version 1 provisions defaults only for `admin` and `postgres`. **Reopens:** any provisioned default for an owner. | — | — |
| F12 | P3 | A view in a database with a table named like the database | **Recorded.** The build fails closed. Witness `employees`.`employees`, withheld. **Reopens:** S-8 or a new dataset. | — | — |
| F14 | P3 | A caller reads the state of a name with neither row nor object | **Recorded.** The design's state table (2.2) and the code both say `gone`. Fable's `absent` is in no current section. | — | — |
| F15 | P3 | `renew` while someone runs `copy list` | **Recorded.** Looks take the change lock briefly; `renew`/`release` return 6. **Reopens:** a caller that cannot retry 6. | — | — |
| F18 | P3 | — | **Recorded.** The direct `pg_database` update is of the creating transaction's own uncommitted row. No route found by either reviewer. | — | — |
| F19 | P3 | Another machine runs the native suite | **Recorded.** `tests/test_strict_read_native.py` still names this host's isolated paths. The new fixture takes them from `DL077_ISOLATED_ENV` and `DL077_ISOLATED_GRAPH`. **Reopens:** the native suite's own run elsewhere. | — | — |
| F20 | P3 | A configuration with an error, or an account named `megasamples_read` | **Recorded.** Checked at image build only, as an uncaught `ValueError`. **Reopens:** the start paths (slice 3+). | — | — |
| F21 | P3 | — | **Recorded.** Declared MySQL writers' grants are baked before the reset's suspension exists. Slice 2 is not to merge without slice 3. | — | — |

## Classes closed this round, with their red, green and reversal

All runs used the committed fixture against task-owned containers in the isolated store. The candidate images were built from `HEAD` with `build/dl114-r1-work/build-image.sh`: PostgreSQL `86035d2c9b9e` (`chinook`) and `0f10f9575066` (`chinook employees pubs`); MySQL `bcc8e0fe01df` (binary log on) and `072c50e5aac3` (off), both `chinook adventureworks_lt oracle_hr sakila` with `reader_b` declared.

| Class | Red | Green | Reversal |
|---|---|---|---|
| Unmanaged inventory, both servers | `('copy_scratch','unmanaged')` absent | `tcp-k1-green-*` | filter restored: fails, both engines |
| Sweep finishes proven `dropping` | not removed | `tcp-k2-green-*` | the hunk is the change |
| Exit 8 and identity on lost replies | exit 1, null identity | `tcp-k3-green-*` | identity not carried; errors internal |
| One drop deadline | 6.03 s, refused 15 s wait, 20.3 s | `tcp-k4-green2-*` | MySQL five-second cap |
| MySQL outside grants agree, readers excluded | `ready` vs `not-exclusive`; reader warned | `tcp-k5k6-green-mysql` | view; `create` state |
| MySQL allocated bytes | 1,654,784 vs 2,777,088 | same | statistics sum |
| Proof at removal, both servers | (regression) | `tcp-final-*` | proof not compared (PostgreSQL), marker not read (MySQL): both fail |
| MySQL count and checksum; interrupted kept | (regression) | `tcp-shortfill-green2` | check disabled: exit 0; `created` read as `stale` |
| MySQL definer is the owner | (regression) | lifecycle | `remove_definer=False`: create exits 8 |
| PostgreSQL closure check and grant last, via `copy create` | (regression) | `tcp-unclosed-green` on the fallback fault image | check removed: exit 0; grant first: grant present |
| Sweep across a renewal | (regression) | `tcp-renewed-green2-*` | either guard alone passes; both removed fails |
| Hook rule 2's registered source | (`0427057`) | `policy-cand2` | `registered_template` removed: fails |
| T-9 | — | `image-test-cand-mysql-*` | `*.*` restored; underscore unescaped: both fail |
| T-30 | — | same | removal taken out: fails |
| T-28 | metadata | four Pythons, first command | `import yaml` planted |

## The previous session's 15 commits

Read with `git log -p 6c5b614..18ef570`. None was amended or rewritten.

- **Red recorded in the message and in a log:** `0427057`, `6eb440e`, `dcfd952`, `0796fe7`, `5208581`, `f9b4fbf`, `7666e25`, `15f5ced` (for `bfb336b`'s text) and `9403495`. The logs are in `build/dl114-r1-previous-session/`.
- **No red recorded:**
  - `289dcf0`. Its test was uncommitted. The red was established here, as A5 above.
  - `a557cb3`. Code before its test. Established here, as F3 above.
  - `bfb336b` and `5027bf0` are prose.
  - `0c2069e` and `18ef570` are test-only follow-ups, with their reasons, to tests that `9403495` and `7666e25` broke.
- **No assertion weakened.** The expectation changes in `dcfd952` (`pg_database_size(oid)`, the reconciled IA-01 addition), `0796fe7`/`f9b4fbf` (unkeyed accounts must be declared, locked or refused), `15f5ced` (the old "every database" text) and `0c2069e` follow the policy. Each is in a test-only commit with its reason. `5208581` tightens.
- **Corrected:** `5027bf0` named the project's licence as MIT. `47eddf0` corrects it to Apache-2.0.
- **Noted:** `9403495` rewrote `uv.lock` at revision 3 (host uv 0.12.21) from revision 5. Both uv versions accept it unchanged.

## The uncommitted changes

They were set aside as `git stash push -u -m "dl114-r1-wip-previous-session-20261121T0420Z"`, SHA `9e32cae6c21edfbe2a5acb9fdfa8614c28fc8143`, with its patch in `build/dl114-r1-work/wip.patch`. Taken back test-first:

- **Tests:** the fixture and fault switch (`ab3cb77`) and the server tests (`1134496`), each corrected in its own test-only commit.
- **Code, one behaviour per commit,** after its red: `ce52c2a`, `d92a308`, `cc3dc49`, `1d9bace`, `31a87a9`, `566ce73`.
- **Not taken:**
  - the session-aware preview and its `pg_stat_get_db_numbackends` grant, which add surface (A9);
  - a reworded usage message.

The stash is kept and was not dropped.

## Baseline: the eight rollback failures

`tests/test_rollback_preparation.py` was run at `e61335f`, in a detached worktree, in the same environment (host Python 3.14.4, the checkout's site-packages, uid 1000).

| Run | `e61335f` | `HEAD` |
|---|---|---|
| `--basetemp` under the checkout's `build/` | 8 failed, 6 passed (`rollback-e61335f-build-pt.log`, 04:22) | the same 8 |
| default temporary directory | 1 failed, 13 passed (`rollback-e61335f-default-tmp.log`) | the same 1 |

**Baseline failures, environmental.**
- Seven bind a Unix socket at `tmp_path/runtime/podman/podman.sock`. Under a long base path this exceeds the 107-byte limit (`OSError: AF_UNIX path too long`).
- `test_whole_rollback_preserves_frozen_retained_file_list_and_digests` copies a read-only file over its own earlier copy. `cp` refuses that as a non-root user (`Permission denied`). It passes only with root's override.

No product code is involved.

`tests/test_quiescence_gate.py::test_readable_unrelated_holder_refuses_with_reversal` failed in the final suite, at `e61335f` as well, three times each. It passed in this session's first suite run (04:21). It is recorded as a baseline, environment-dependent failure; its cause was not isolated.

## Test runs

All runs are in the isolated store, against task-owned containers, with MemAvailable checked at 15 GiB before every build and start.

**Passed**
- **The TCP server suite** at `9b825ca`, on the candidates:
  - PostgreSQL: 10 passed, 8 skipped. The skips are MySQL-only cases and the fault-image case.
  - MySQL, binary log on: 16 passed, 2 skipped.
  - MySQL, binary log off: 16 passed, 2 skipped.
  - PostgreSQL fallback fault image: the left-open case passed.
  - Logs: `tcp-final-*.log`.
- **`megasamples test-image`, 0 failures each:**
  - PostgreSQL `chinook` (`image-test-cand-pg.log`);
  - PostgreSQL `chinook employees pubs` (`image-test-cand-pg-full.log`);
  - MySQL on and off, `chinook adventureworks_lt oracle_hr sakila` (`image-test-cand-mysql-*.log`).
- **The native strict-read suite:**
  - PostgreSQL: 46 passed on `0f10f9575066` (`native-cand-pg-full3.log`);
  - MySQL: 7 passed in each log mode (`native-cand-mysql-*.log`).
  - Its runner ran in a container with libpq. The host has none.
- **`tests/test_v1_postgres_policy.py` on the candidate:** 12 passed, 1 skipped (the close-fault case). On the close-fault image that case passed (`policy-cand2.log`, `policy-fault-close.log`).
- **`tests/test_v1_postgres_start.py`:** passed (`policy-start.log`).
- **T-28's clean install** on four Pythons, and its first command.
- **H-3's caller interrupts and their control.**

**Failed**
- **The full suite** at `9b825ca`: 2 failed, 1,061 passed, 287 skipped (`pytest-final2.log`, 05:26:47). The default temporary directory was used. Both failures also fail at `e61335f` (see "Baseline"). The skips are the opt-in native and TCP targets, each run above against its candidate.

**Unsupported**
- MySQL copies of trigger and stored-function datasets are withheld in both log modes (DL-112, DL-113).
- A PostgreSQL dry run that knows of sessions is not built (A9).


Not run in this round:

- `megasamples verify` against a MySQL copy of each offered dataset (T-11's own assertion);
- WideWorldImportersDW and every other unbuilt dataset;
- the full account-by-database, concurrency, kill-point and disk-full matrices (T-15, G-9);
- DataIntent C1.

## Restoration and isolation

- **Retained isolated stack.** The eight `dl077-feasibility` containers are running on the `e61335f` images. None was restarted or rebuilt. The fingerprint ledgers were re-taken with `build/dl077-v1-work/fingerprints.py` at 05:24:13, and `cmp` with build 1's `after` ledgers returned 0:
  - PostgreSQL `ee0f1a8b4e17…711e`;
  - MySQL `a5c0466a5479…a72f`;
  - SQLite `5b0c2768dc41…da98`.

  These are the gates record's values.
- **Removed, after confirming they were task-owned in the isolated store:**
  - **Containers:** the previous session's `dl077-v1-tcp-b0ee5a74…`, `dl077-v1-tcp-c63eccfb…` and `megasamples-test-mysql`. Each was created after its session started, from its own `dl114-r1-*` images.
  - **Volumes:** their anonymous volumes, and the ten anonymous volumes this session's image tests left between 04:52 and 04:55. Each was checked unused.
  - **Images:** this session's reversal images.
- **Kept for review:**
  - the candidate images `localhost/dl114-r1c-pg:candidate`, `:candidate-full`, `localhost/dl114-r1c-mysql:candidate-true`, `:candidate-false`;
  - the fault images `localhost/dl114-r1c-pg:fault-close`, `:fault-fallback`;
  - the runner image.

  The previous session's `dl114-r1-*` images are left as they were.
- **The isolated socket service** this session started for `docker` clients was stopped at the end.
- **Isolation** (`build/dl114-r1-work/isolation-check.sh`, read-only):
  - **Live deployment:** the nine live `megasamples-*` entries match the session's start by name, ID, state and health. The three live engines' IDs, states, start times and image IDs are unchanged. The only other live differences are another task's `dataintent-dev-*` containers.
  - **Isolated store:** it holds the same 20 containers with the same IDs, states, images and start times. Its volumes are the starting set less the three previous-session volumes.
