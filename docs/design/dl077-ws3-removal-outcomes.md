# Workstream 3: copy removal outcomes across the three engines

**Status:** brief, not yet built. The area went hot in rounds 3, 4 and 5 (`tests/dl077-v1-loop.md`). It covers what `copy drop` and `copy sweep` report, on PostgreSQL, MySQL and SQLite, when an engine change succeeded and a later step fails, or when the connection is lost.

## The rule to be designed whole

Every removal command's reply describes what changed, copy by copy, with an exit code that keeps design 3.3's promise:
- 3 or 5: nothing changed;
- 6: only what 3.3 lists;
- 8: something may have changed, and the reply says what.

A copy whose object the engine confirmed removed is reported as removed. The steps after that may be unsettled, and the reply says which.

## Invariants

- **R1. Per-copy truth.** Each copy appears exactly once: in `removed` if its object is confirmed gone, in `kept` otherwise. Its reason comes from what happened to that copy, not from the command's earlier history.
- **R2. Exit by the command's effect.** 3 or 5 only if no write was issued at all. 8 if any write was issued and the command did not finish as asked. 6 as 3.3 lists it. 0 only if everything finished.
- **R3. Same outcomes on every engine.** PostgreSQL, MySQL and SQLite report the same state and reason for the same step failing. That covers:
  - the ledger row or sidecar;
  - the retained link;
  - the lock file;
  - the directory sync.
- **R4. Identity preserved.** Every exit 3 or 8 carries the identity a caller recovers by.
- **R5. Dry runs change nothing and say 5 or 0,** never 8.

## Decision table

The rows are over each removal step, per engine:
1. lock;
2. load;
3. state and proof read;
4. phase write `dropping`;
5. engine removal (`DROP`, or SQLite's move aside and compare);
6. retained-link removal (SQLite);
7. ledger or sidecar delete;
8. directory sync (SQLite);
9. unlock.

Each step is crossed with:

| Fact | Values |
|---|---|
| A. Outcome of the step | succeeds; fails with an engine error; the connection is lost; an OS error (SQLite) |
| B. Earlier copies in this sweep | none; removed; kept busy after a rollback write; kept unchanged |
| C. This copy's earlier writes | none; `dropping` written; `ready` rolled back |
| D. Command | `drop`; `sweep`; `sweep --dry-run` |

The outcomes to decide are the exit, this copy's list and reason, and the result fields: state, ledger, identity.

## Inputs: every finding so far

| Round | Finding | Gist | Disposition so far |
|---|---|---|---|
| 1 | A2 | SQLite sweep exit 5 after a deletion | fixed |
| 1 | A6, A7 | dropping recovery; lost replies | fixed |
| 2 | A2-3, F2-4 | a server sweep lost its completed removals | fixed |
| 2 | A2-7 | connection lost at the metadata read | fixed |
| 2 | A2-8 | exit 6's promise | narrowed |
| 3 | S3-4, O3-2 | a copy both removed and kept; a dry run giving 8; a busy rollback giving 5 | fixed |
| 3 | S3-5 | loss after initialisation | fixed |
| 4 | S4-4 | the ledger delete failing after `DROP` | fixed (servers) |
| 4 | S4-5 | the proof-read loss | fixed |
| 5 | Sol P2-2, Opus P3-1 | SQLite: a failed sidecar or link removal after the file is gone | **input** |
| 5 | Opus P3-5 | the per-copy reason taken from the command-wide `wrote` flag | **input** |

## Questions the design must answer

1. Is there one shared removal state machine, with engine adapters for steps 4 to 8, rather than three hand-written `remove()` functions?
2. What is the result field for an unsettled cleanup step? `ledger: unsettled` today. Should it name the step (sidecar, retained link, sync)? **Owner decision:** it is an interface field before freeze.
3. After a lost connection on unlock, is 8 `connection-lost` right when the copy was fully removed, or should the copy be listed removed with `lock: unsettled`?
4. Is SQLite's directory sync failure "removed" or "unsettled"?

## Test plan

- **A table test generated from the decision table,** for all three engines. A fault switch plants each step's failure: engine error, connection loss, OS error. The real CLI runs, and the reply is asserted: exit, lists, reasons and result. This replaces the per-round point tests, which stay as regressions.
- **Sweeps with two and three copies,** to cover fact B.
- **Reversals:** each rule of R1 to R5 removed fails at least one row on each engine.
