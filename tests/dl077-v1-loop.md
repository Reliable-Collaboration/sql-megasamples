# Version 1, slices 1 and 2: review loop status

This is the loop over `feature/dl-077-v1`, run under DL-114, DL-120 and RCC.DataIntent's `knowledge/governance/review-and-fix.md`. The per-round triage records are `tests/dl077-v1-review-{1,2,3,4}.md`; round 5's dispositions are below.

## Stop count

**0 of 2.** The loop ends after two rounds in a row with nothing to fix now outside the workstreams. Round 6 reviews:
- the fixes outside the workstreams;
- a fresh pass over everything outside them;
- the four briefs, read by Sol and Opus.

## Hot areas, now workstreams

An area is hot when the same class is found in it in two rounds running. Each of these had a finding in three rounds running, or more. **They are no longer patched round by round.** Their briefs are in `docs/design/`, and each will be built test-first, one at a time, after the loop ends, then reviewed to two clean rounds. That is all before the merge (DL-101).

| # | Area | Brief | Rounds with findings |
|---|---|---|---|
| 1 | Start certification: the wrapper, the private password start, non-root and bypass starts | `docs/design/dl077-ws1-start-certification.md` | 2, 3, 4, 5 |
| 2 | Orphan-scan completeness | `docs/design/dl077-ws2-orphan-scan.md` | 3, 4, 5 |
| 3 | Removal outcomes across engines | `docs/design/dl077-ws3-removal-outcomes.md` | 1, 2, 3, 4, 5 |
| 4 | The native suite's binding to its target | `docs/design/dl077-ws4-native-suite-binding.md` | 2, 3, 4, 5 |

## Round 5: each finding's disposition

These are the reviews of `c95ee833`: Sol (`S5-*`) and Opus (`O5-*`). A hot-area finding gets a stopgap only where DL-040 finds a realistic route to real harm, and then only the smallest one that removes it.

| ID | Sev. | Area | Disposition | Stopgap and why |
|---|---|---|---|---|
| S5-1 | P2 | 4 | Workstream input | **None.** It needs another task to replace the container and reuse its port mid-run, in the same isolated store. That route is constructed, the harm is test-time writes to a scratch container, and every target in this store is disposable. |
| S5-2 | P2 | 3 | Workstream input | **None.** It needs a filesystem I/O error right after a successful unlink. The data is gone as asked; only the reply's list is wrong, and `copy show` settles it. |
| S5-3 | P2 | 1 | Workstream input | **None.** A custom persisted socket setting makes the private start unreachable, and the start fails closed: no server accepts connections, and nothing is exposed. |
| S5-4 | P2 | 2 | Workstream input | **None.** It needs a permission change that leaves `base/` searchable but unlistable. The harm is an orphan's disk use going unreported. No data is touched, and the control is detective. |
| S5-5 | P2 | 2 | Workstream input | **None.** It needs a whole-engine reset concurrent with `reset --status`. Two operator actions; the report is wrong, the data is not. |
| S5-6 | P2 | — | **Fixed now** | — The healthcheck's ERROR every probe. It is reached on every `up`. `2c9b106` (test `bc9a900`, test-only `6d321ad`). |
| S5-7 | P3 | 1 | Workstream input | **None.** The non-root ordering fails closed. |
| S5-8 | P3 | — | **Fixed now** | — Design 2.4 lists `NO_BACKSLASH_ESCAPES` (`93a26c6`). |
| O5-1 | P3 | 3 | Workstream input (same class as S5-2) | **None**, as S5-2. |
| O5-2 | P3 | — | **Fixed now** (same as S5-6) | — |
| O5-3 | P3 | 1 | Workstream input | **A documentation stopgap.** The README sentence was inaccurate. It now says a non-root start exits before the public server starts, and that the private password start may run first on its local socket (`93a26c6`, corrected in the next commit after a run showed that start answering). |
| O5-4 | P3 | 1 | Workstream input | **A documentation stopgap.** The README now states that a replaced entrypoint or a wrapping command is unchecked, and that the healthcheck is then the only signal (`93a26c6`). |
| O5-5 | P3 | 3 | Workstream input | **None.** The exit code is right; only one copy's reason misleads. |

## Backlog

Each row can wait: there is no realistic route to harm, or the harm is stated as a limit.

| What | From | Why it can wait |
|---|---|---|
| Refused SQLite creates leave lock files | round 1, A14/F16 | No record or data is affected. Reopens with any change to the lock protocol. |
| The MySQL rewrite of a table named like its database | round 1, F12 | Fails closed; its witness is withheld. |
| Looks take the change lock; `renew` can return 6 during `list` | round 1, F15 | Callers retry 6. |
| Direct `pg_database` update without a tuple lock | round 1, F18 | No route found by either reviewer. |
| Configuration checks only at image build; the account name `megasamples_read` accepted | round 1, F20 | Start paths are slice 3+. |
| Declared MySQL writers' grants are baked before slice 3's suspension | round 1, F21 | Slice 2 does not merge without slice 3. |
| Ownership transfer after creation; `DROP OWNED` and provisioned defaults | round 1, S6 and S7 | The rules are as specified. |
| Range-type constructors keep `PUBLIC EXECUTE` | round 2, F2-8 | A stated limit: immutable built-in code. |
| MySQL `character_set_client` and `collation_connection` not restored | round 3, O3-4 | A stated limit in design 2.4. |
| The H-3 probe's client-only accounting has no reversal | round 4, S4-9 | A recorded limit of the control. |
| `test_quiescence_gate` unrelated-holder case fails, also at `e61335f` | rounds 1–5 | A baseline failure; its cause is not isolated. |
| Design 8.3's claims not yet made | rounds 2–5 | T-11 `verify`, T-15 and the kill points, the full disk, and the wider account matrix. The merge waits for each. |

## Round 5's runs

These are the runs on the candidates built from `8102f35`: PostgreSQL `9fbee1a14d05` and `9a8e07e91aca`, MySQL `87dd365119ac` and `887f1224214a`, and the fallback fault image `acd0a1d82f47`. Logs are under `build/dl114-r1-work/`.

**Passed**
- **The TCP server suite:** PostgreSQL 23 passed, 12 skipped; MySQL 32 passed, 3 skipped in each mode; the fallback case passed.
- **PostgreSQL suites:** policy OK; restore and the real reset OK; orphans OK; start OK, with the non-root case asserting the exit; health, 3 passed.
- **`test-image`, 0 failures each:** PostgreSQL `chinook`; PostgreSQL `chinook employees pubs`; MySQL in both modes.
- **The native strict-read suite:** PostgreSQL 46 passed; MySQL 7 passed in each mode.

The orphan, start, MySQL-off image and native runs were first refused for memory below 15 GiB. They were then held by DL-081's host-wide rule for DataIntent's runs, and ran after the coordinator's go, 10:36–10:38 UTC (`r5-final2.txt`).

**Failed**
- **The full suite:** 2 failed, 1,078 passed, 313 skipped (`pytest-r5.log`, 08:24:35). These are the same two baseline failures as before.

**Not run**
- the claims design 8.3 lists as not yet made;
- the workstreams themselves.

## Round 5: restoration and isolation

- **Retained isolated stack.** The fingerprint ledgers (phase `r5-final`) are byte-identical to build 1's `after` ledgers:
  - PostgreSQL `ee0f1a8b…711e`;
  - MySQL `a5c0466a…a72f`;
  - SQLite `5b0c2768…da98`.
- **Removed:**
  - every task container this round started;
  - this round's 28 anonymous volumes, each checked unused;
  - the superseded and reversal images.
- **Kept for review:**
  - the round 5 candidates `localhost/dl114-r5-pg:candidate`, `:candidate-full`, `localhost/dl114-r5-mysql:candidate-true`, `:candidate-false`;
  - the fault images `localhost/dl114-r5-pg:fault-fallback`, `localhost/dl114-r1c-pg:fault-close`;
  - the runner.
- **The isolated socket service** is stopped.
- **Isolation** (`build/dl114-r1-work/isolation-check.sh`, read-only):
  - **Live deployment:** the nine live `megasamples-*` entries are unchanged by ID, state, health, start time and image.
  - **Isolated store:** the same 20 containers.
