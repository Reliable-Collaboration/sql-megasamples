# Workstream 4: binding the native strict-read suite to its target

**Status:** brief, not yet built. The area went hot in rounds 2 to 5 (`tests/dl077-v1-loop.md`). It covers how `tests/test_strict_read_native.py` and its clients make sure that every statement they send, including the ones that write, reaches the container the maintainer named, and only that one.

## The rule to be designed whole

The suite sends no SQL until it has bound to one container instance:
- in the named isolated store;
- carrying the exact owner the maintainer gave.

Every later statement, over the `docker exec` route or a TCP library connection, is proved to reach that instance before it runs. A target that changes mid-run stops the suite.

## Invariants

- **N1. One store.** The suite runs only against the store named by `DL077_ISOLATED_GRAPH`, checked before anything else.
- **N2. One instance.** The target is a container ID read once, together with an exact owner label. Names are never resolved again.
- **N3. Every channel bound.** The exec route uses the ID. A TCP connection proves the instance before any statement, by a per-instance marker the fixture plants and each connection reads, and the suite stops if the marker is absent or different.
- **N4. Writes only after proof.** A test that creates or drops databases and roles runs only on a connection that has passed N3.
- **N5. Fails closed.** A missing owner, ID or marker raises, never falls back.

## Decision table

| Fact | Values |
|---|---|
| S. Store | the named isolated store; another store; `DL077_ISOLATED_GRAPH` unset |
| T. Engine | PostgreSQL; MySQL with the binary log on; MySQL with it off |
| A. Driver | the CLI over `docker exec`; the library over TCP (`STRICT_READ_NATIVE_DRIVER=library`) |
| P. Endpoint and proof | the published port reaches the checked instance; reaches another; nothing listens. The marker: bootstrapped and read back; bootstrap failed; absent; unreadable; stale (from an earlier run); copied with the volume |
| B. Target at the fixture | right owner; other owner; unlabelled; absent |
| C. Target later | the same instance; replaced under the same name; its port reused by another instance; gone. Timing: before the fixture, between the fixture and the first test, between two statements, during cleanup |
| D. Statement | read; write (database or role) |

The outcomes to decide are to run or stop, and where the stop is raised.

## Inputs: every finding so far

| Round | Finding | Gist | Disposition so far |
|---|---|---|---|
| 1 | F19 | `tests/test_strict_read_native.py` named one machine's project and paths | fixed in the suite; an input for the library helper's portability |
| 2 | A2-2 | the suite named one host's paths and defaulted to service names | fixed |
| 3 | S3-3 | any `dl077-` label accepted | fixed: exact owner |
| 4 | S4-2 | the name resolved again: a replacement under the same name | fixed: ID |
| 5 | Sol P2-1 | library TCP connections by cached port reach a replacement that reuses the port | **input** |
| 6 | Sol P2-2 (S6-2) | until the binding exists, suspend the native suite's unchecked TCP statements that can write, the direct-protocol parity cases included, because a second run on the same published port could receive database and role changes | **input**, with **no stopgap**: the coordinator's round 6 decision (`tests/dl077-v1-loop.md`, "Round 6: stopgaps"). It reopens with a native run against a store that holds a non-disposable target. The design decides which statements run before the proof |
| 6 | Sol P2-8 | the TCP proof and its bootstrap are outside the table; zero statements on the replacement must be witnessed | **input** (fact P; question 4; test plan) |
| 6 | Opus 3 | the store and engine facts, the gone and store controls, marker-read faults, F19, the H-3 scope | **input** (facts S, T; question 5; test plan) |
| 7 | Opus 2 | the table test spans only A to D | **input**: the table spans S, T, A, P, B, C and D under a stated coverage criterion, with controls for each value of P (reaches another, nothing listens, copied with the volume) and each timing of C |
| 7 | Sol 4 | the proof and its oracle disagree: a copied marker is untested, and the absence of a probe database cannot show that no read, authentication or cleanup reached the replacement | **input**: authentication, bootstrap, proof reads and test SQL as separate steps; each replacement boundary, the direct parity connection included; evidence that detects each prohibited operation; authentication before proof stays an owner decision; H-3's manifest graph check and exec-by-ID reconciled with N1 and N3 |
| 9 | Sol P3-7 | round 6 S6-2 was in the loop but not in these inputs | **input**: the S6-2 row above |

## Questions the design must answer

**Owner decision in this brief:** question 4, a security-posture question.

1. What is the per-instance marker? It could be a row the fixture writes in `megasamples` with a random value, read on each connection. The fixture's own write must then not need the marker.
2. Should the library driver connect through `docker exec` port forwarding tied to the ID, instead of a published host port?
3. Does `docs/validation/strict_read_clients.py`, a validation tool, take the same binding, or is it retired in favour of the suite's own client?
4. **Owner decision, security posture:** may the suite authenticate, with the fixture's credentials, to a listener it has not yet proved to be the checked instance? Proving the marker needs a connection first (Sol round 6, P2-8).
5. **Scope:** the H-3 probe (`tests/gates/dl077_h3_interrupts.py`) binds through `tests/gates/native.py`'s manifest and exec-by-ID only, and opens no TCP connection. It is in scope for the store and owner rules (N1, N2), not for N3. The other `tests/gates` launchers are out of scope unless they gain a TCP client.

## Test plan

- **A table test over facts A to D,** with real containers.
- **Controls:**
  - another owner;
  - unlabelled;
  - a replacement under the same name between the fixture and the first test;
  - a replacement that takes the same host port.

  Each must stop the suite before any write, shown by a probe database that was never created on the replacement.
- **Controls for the store and for gone:** `DL077_ISOLATED_GRAPH` unset or pointing at another store, and the target removed mid-run. Each must stop before any statement.
- **Faults at the marker:** its bootstrap fails, or its read returns absent, unreadable or stale. The suite stops before any write.
- **Zero statements on the replacement,** including destructive and cleanup statements, witnessed by the replacement's statement log or a probe database that never appears.
- **Portability (F19):** the library helper runs from another checkout with no host-specific path.
- **Reversals:** the marker check removed, or names resolved again, fails a control.
