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
- **R2. Exit by the command's effect.** 3 (a connection lost, or the engine unreachable) or 5 (a refusal) only if no write was issued at all. 8 if any write was issued and the command did not finish as asked. 6 as 3.3 lists it. 0 only if everything finished.
- **R3. Same outcomes on every engine.** PostgreSQL, MySQL and SQLite report the same state and reason for the same step failing. That covers:
  - the ledger row or sidecar;
  - the retained link;
  - the lock file;
  - the directory sync.
- **R4. Identity preserved.** Every exit 3 or 8 carries the identity a caller recovers by.
- **R5. Dry runs change nothing,** so they say 0, 3 (connection lost) or 5 (refused), never 6 or 8. This reconciles with R2: a dry run issues no write.

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
| A. Outcome of the step | not issued; confirmed done; confirmed refused (engine error); busy (a session or lock, within or past the wait); contended (the change lock held); **unknown** (the connection lost after sending, as for a committed `DROP` whose reply is lost); partly done (an interrupted PostgreSQL `DROP DATABASE` leaving an invalid row; MySQL's non-atomic `DROP DATABASE`); an OS error (SQLite) |
| A2. The copy at selection | its phase, format, identity, revision, lease and proof; `unmanaged`; already gone; `not-exclusive` |
| B. Earlier copies in this sweep | none; removed; kept busy after a rollback write; kept unchanged |
| C. This copy's earlier writes | none; `dropping` written; `ready` rolled back |
| D. Command | `drop`; `drop --wait N`; `sweep`; `sweep --dry-run` |
| E. Concurrent command on the same copy | none; `renew`; `drop`; `create` reusing the name |
| F. Sweep progress | the copy reached; not reached because the sweep stopped earlier |

The outcomes to decide are the exit, this copy's list and reason, and the result fields: state, ledger, identity.

## Inputs: every finding so far

| Round | Finding | Gist | Disposition so far |
|---|---|---|---|
| 1 | A2 | SQLite sweep exit 5 after a deletion | fixed |
| 1 | A8, F5 | unmanaged objects missing from the inventory; kept by the sweep | fixed; an input for fact A2 |
| 1 | A9, F17 | the busy drop: `--wait`, the rollback and exit 6's promise | fixed and narrowed; an input for fact A (busy, contended) |
| 1 | A6, A7 | dropping recovery; lost replies | fixed |
| 2 | A2-3, F2-4 | a server sweep lost its completed removals | fixed |
| 2 | A2-7 | connection lost at the metadata read | fixed |
| 2 | A2-8 | exit 6's promise | narrowed |
| 2 | F2-5 | a proven `dropping` copy in a sweep | fixed; an input for fact A2 |
| 2 | A2-12 | `gone` for a name with neither row nor object | fixed; an input for fact A2 |
| 3 | S3-4, O3-2 | a copy both removed and kept; a dry run giving 8; a busy rollback giving 5 | fixed |
| 3 | S3-5 | loss after initialisation | fixed |
| 4 | S4-4 | the ledger delete failing after `DROP` | fixed (servers) |
| 4 | S4-5 | the proof-read loss | fixed |
| 5 | Sol P2-2, Opus P3-1 | SQLite: a failed sidecar or link removal after the file is gone | **input** |
| 5 | Opus P3-5 | the per-copy reason taken from the command-wide `wrote` flag | **input** |
| 6 | Sol P2-4 | the table cannot derive the reply for a lost reply to a committed `DROP`, a dry-run loss, or a busy copy then an unlock loss (which can list it kept twice) | **input** (fact A; R2 and R5 reconciled; test plan) |
| 6 | Opus 2 | busy and contended, already gone, partly done, sweep selection and unreached copies, concurrent commands | **input** (facts A, A2, E, F; questions 5, 6) |
| 7 | Opus 1 | the full product of 9 steps and facts A to F is not buildable; no coverage criterion | **input**: state the criterion, as for WS1, with the full product only in the fault-switch harness |
| 7 | Sol 3 | rollback and cleanup are not steps; a skipped dry-run step and an unsent request share `not issued`; R1's "exactly once" against unreached copies | **input**: selection, rollback and cleanup as steps; step execution separate from what the caller can confirm; object and ledger state asserted with the reply; question 6 in the owner summary if skipping a `not-exclusive` copy is considered |
| 7 | Opus P3-5 | fact E (two parties changing the same copy) is an owner category under `AGENTS.md` | **input**: keep the change lock's semantics, or make E's outcomes part of question 5 |

## Questions the design must answer

**Owner decisions in this brief:** questions 2 and 5, and any change to a public exit code or to the meaning of `removed` and `kept`.

1. Is there one shared removal state machine, with engine adapters for steps 4 to 8, rather than three hand-written `remove()` functions?
2. What is the result field for an unsettled cleanup step? `ledger: unsettled` today. Should it name the step (sidecar, retained link, sync)? **Owner decision:** it is an interface field before freeze.
3. After a lost connection on unlock, is 8 `connection-lost` right when the copy was fully removed, or should the copy be listed removed with `lock: unsettled`?
4. Is SQLite's directory sync failure "removed" or "unsettled"?
5. **Owner decision:** is there a third per-copy outcome (unknown, or partly removed), and a list for the copies a stopped sweep never reached? Today R1's "exactly once" does not hold for them: they are in no list.
6. A `not-exclusive` copy aborts a real sweep with exit 5 before any write. Should the sweep skip it and continue instead?

## Test plan

- **A table test generated from the decision table,** for all three engines. A fault switch plants each step's failure: engine error, connection loss, OS error. The real CLI runs, and the reply is asserted: exit, lists, reasons and result. This replaces the per-round point tests, which stay as regressions.
- **Sweeps with two and three copies,** to cover facts B and F, including a stop before the last copy.
- **Faults on both sides of each durable effect:** before the step is sent, after it is confirmed, and with its reply lost. The steps are selection, the phase write, the busy rollback, the engine removal, SQLite's move, compare, unlink and sync, the ledger or sidecar delete, and unlock.
- **Concurrent commands** from a second process, gated at each step (fact E).
- **Reversals:** each rule of R1 to R5 removed fails at least one row on each engine.
