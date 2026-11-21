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
| A. Driver | the CLI over `docker exec`; the library over TCP (`STRICT_READ_NATIVE_DRIVER=library`) |
| B. Target at the fixture | right owner; other owner; unlabelled; absent |
| C. Target later | the same instance; replaced under the same name; its port reused by another instance; gone |
| D. Statement | read; write (database or role) |

The outcomes to decide are to run or stop, and where the stop is raised.

## Inputs: every finding so far

| Round | Finding | Gist | Disposition so far |
|---|---|---|---|
| 2 | A2-2 | the suite named one host's paths and defaulted to service names | fixed |
| 3 | S3-3 | any `dl077-` label accepted | fixed: exact owner |
| 4 | S4-2 | the name resolved again: a replacement under the same name | fixed: ID |
| 5 | Sol P2-1 | library TCP connections by cached port reach a replacement that reuses the port | **input** |

## Questions the design must answer

1. What is the per-instance marker? It could be a row the fixture writes in `megasamples` with a random value, read on each connection. The fixture's own write must then not need the marker.
2. Should the library driver connect through `docker exec` port forwarding tied to the ID, instead of a published host port?
3. Does `docs/validation/strict_read_clients.py`, a validation tool, take the same binding, or is it retired in favour of the suite's own client?

## Test plan

- **A table test over facts A to D,** with real containers.
- **Controls:**
  - another owner;
  - unlabelled;
  - a replacement under the same name between the fixture and the first test;
  - a replacement that takes the same host port.

  Each must stop the suite before any write, shown by a probe database that was never created on the replacement.
- **Reversals:** the marker check removed, or names resolved again, fails a control.
