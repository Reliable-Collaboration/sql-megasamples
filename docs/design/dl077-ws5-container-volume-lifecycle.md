# Workstream 5: container and volume lifecycle

**Status:** brief, not yet built. The area went hot in rounds 9, 10 and 11 (`tests/dl077-v1-loop.md`): the round 9 batch found `test-image` leaving its anonymous volume; round 10 found Compose's routes leaving every engine's data volume; round 11 found the failure path of a recreate stranding the volume it replaced. It is built test-first after the review loop ends, and reviewed to two clean rounds, before the merge (DL-101).

It covers every megasamples command that creates, recreates or removes a container, and what happens to the named and anonymous volumes on success, failure and interruption. That includes which containers megasamples owns (name-matched containers), how it decides an image is stale, and how the class test knows the whole class.

## The rule to be designed whole

A megasamples command that removes or replaces a container leaves no volume of that container behind that megasamples created and no one can reach again, and removes no volume it does not own or that holds data the user is told survives. On failure or interruption it reports what it left, and a later command can find and remove it.

## Invariants

- **L1. No stranded anonymous volume.** After any command, on any outcome, every anonymous volume a megasamples container had is either still mounted by a container megasamples manages, removed, or reported by name with how to remove it.
- **L2. Named volumes stay.** The named volumes megasamples declares (today `megasamples-sqlite`) are never removed by a routine command, and what each command does to their contents is stated.
- **L3. Ownership before removal.** A container or volume is removed only with evidence megasamples made it: its label, its project, or an image of megasamples' own. An ambiguous match is reported, not removed.
- **L4. Failure is returned and reported.** A failed create, recreate or removal returns its failure and names any resource it could not settle.
- **L5. Staleness by what will run.** An engine is recreated as stale only when the image Compose would run differs from the running one, as Compose resolves it (`.env` overrides included).
- **L6. The class is known.** One test enumerates every site that creates, recreates or removes a container, in any form the code can take, and checks each against this table.

## Decision table

Rows: each command, by its route, by its outcome, by the volume kind.

| Fact | Values |
|---|---|
| A. Command | `up`; `down`; `status clean`; `status clean --all`; `reset` (whole engine; single datasets, with their pristine containers); `test-image` (each engine, main and override containers); the build servers' `start`, `fresh` and `stop`; the source verifiers (MSSQL, Oracle); `audit`; one-off `run --rm` (console configuration, loaders, `compose run --rm`) |
| B. Route | `docker rm` (any spelling); `docker run --rm`; Compose `rm`, `down`, `up` (plain, `--force-recreate`, `--renew-anon-volumes`), `run --rm` |
| C. Outcome | success; the create or recreate fails before replacing; it fails after replacing (Compose renewed the volume, then `--wait` gave up); the removal fails; interrupted between steps; the daemon unreachable |
| D. Volume kind | the image's declared (anonymous) volume; a named volume megasamples declares; a bind mount; a volume another project owns |
| E. Ownership of the container | labelled transient; in megasamples' Compose project; matched only by a pre-label name; another project's |
| F. Image | current; rebuilt under the same tag; overridden in `.env`; overridden in the environment |

Each row's outcome: which containers and volumes remain, what is reported, and the exit.

## Inputs: every finding so far

| Round | Finding | Gist | Disposition so far |
|---|---|---|---|
| 9 | batch finding | `test-image` and 16 other `docker rm -f` calls left the image's anonymous volume | fixed: `-fv` everywhere (`53a2d1e`) |
| 10 | Opus P2-1 | Compose `down`, `clean --all` and `up`'s stale recreate left every engine's data volume | fixed on success: `data_volumes.down()` and `recreate()` (`c917a1f`) |
| 10 | Sol P2-1 | `test-image` could check its overrides against an old container after a failed launch | fixed: the leftover goes first, the launch is checked, queries use the returned ID (`a27880a`, `c4745ba`) |
| 11 | Opus 1, Sol 1 | a recreate that fails after Compose renewed the volume strands the replaced one | **stopgap**: `remove_replaced` on every exit, in `recreate` and `reset_engines` (`2482eaf`); **input** for fact C and the interruption rows |
| 11 | Opus 2, Sol 5 | the class test does not see an argv held in a variable (`cmd = [...]`, as `audit.py` and `mssql.py` build them), and accepts a cleanup call anywhere in the function, even after a return that bypasses it | **input** for L6 |
| 11 | Opus 3, Sol 9 | a name-only match is still force-removed: a foreign container loses its container and its volume dangles; megasamples' own pre-label container leaks its volume | **input** for L3 and fact E |
| 11 | Opus N1 | the main image-test containers still query by their fixed name; only a concurrent run could redirect them | **input** for fact A |
| 11 | Opus N2 | `docker run --rm` and `compose run --rm` are removals too, outside the record; Docker and Podman document that `--rm` takes anonymous volumes | **input** for fact B and L6 |
| 11 | Opus N3, Sol 4 | the override checks' `or NAME + "2"` fallback exists only for a fake that prints no ID; it should require an ID, with the fakes giving one | **input** for fact A |
| 11 | Sol 2 | the stale check compared with Python's default tag, not the image Compose resolves from `.env`, and recreated with a fresh volume | **stopgap**: Compose's resolved image (`f769ff3` test, `36c7b0f`); **input** for L5 and fact F |
| 11 | Sol 3 | `clean --all` exits 0 while the stack is still up when Compose's removal fails | **input** for L4 |
| 11 | Sol 6 | the `clean --all` regression failed first on the fake's `-f` assertion, before modelling the volumes; file selection should be checked separately | **input** for the test plan |
| 11 | Sol 10 | the round 10 record's counts: 23 direct removals and four Compose calls, not 24 sites; 26 class-test cases, not 27; the fix order | **input** for L6's enumeration; the record is corrected in the loop file |

## Questions the design must answer

**Owner decisions in this brief:** questions 2 and 4.

1. Is cleanup after a failed recreate a `finally` in each command (today's stopgap), or a reconciliation any later command performs from a record of what it replaced?
2. **Owner decision, what a person sees:** what `make down` and `make clean-all` promise about working data, and whether a command that would discard changes asks first or offers a keep option. The README states today's behaviour.
3. Where do volumes megasamples could not remove get reported: each command's output only, or also `make status`, so a later run finds them?
4. **Owner decision, on a shared daemon:** what ownership evidence permits removal (label, project, image of megasamples' own), and what happens to a pre-label match: listed with a hint, or removed when its image is megasamples' own.
5. Is staleness decided by Compose's resolved image (today's stopgap), by the container's recorded image reference, or both?
6. Does the class test enumerate by syntax (an AST walk, with assigned argvs resolved) or by a single execution seam every container command must use, so the fake daemon sees the whole class?

## Test plan

- **A fake daemon that models the documented behaviour** of Docker, Podman and Compose for each route in fact B, including a renewal followed by a failed `--wait`, a failed create, a failed removal and an interruption between steps. A table test generated from the decision table runs each command against it and asserts the remaining containers and volumes, the report and the exit.
- **A real cycle in the isolated store** on a project of its own (as round 10's `cycle-r10`): every command in fact A that can run there, on success and on a planted failure (an image that exits, a healthcheck that never passes), with the store's volume set compared before and after.
- **Ownership:** a foreign container under a pre-label name, and one in another Compose project, on the same daemon; neither is removed or loses a volume.
- **Staleness:** the image overridden in `.env` only, in the environment only, and rebuilt under the same tag.
- **The class test,** with planted rows for each form the code can take, including an assigned argv and a cleanup bypassed by an early return.
- **Reversals:** each invariant L1 to L6 removed fails at least one row.
