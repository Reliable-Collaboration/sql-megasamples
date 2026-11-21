# Workstream 5: container and volume lifecycle

**Status:** brief, not yet built. The area went hot in rounds 9, 10 and 11 (`tests/dl077-v1-loop.md`): the round 9 batch found `test-image` leaving its anonymous volume; round 10 found Compose's routes leaving every engine's data volume; round 11 found the failure path of a recreate stranding the volume it replaced. It is built test-first after the review loop ends, and reviewed to two clean rounds, before the merge (DL-101).

It covers every megasamples command that creates, recreates or removes a container, and what happens to the named and anonymous volumes on success, failure and interruption. That includes which containers megasamples owns (name-matched containers), how it decides an image is stale, and how the class test knows the whole class.

## The rule to be designed whole

A megasamples command that removes or replaces a container leaves no volume of that container behind that megasamples created and no one can reach again, and removes no volume it does not own or that holds data the user is told survives. On failure or interruption it reports what it left, and a later command can find and remove it.

## Decided elsewhere: slice 3's accepted design

Slice 3's accepted design already decides most of this area, in `docs/design/templates-copies-and-accounts.md`, "Starting and stopping" [114-2F] (near line 538), its U-1 to U-5 table, and the replacement rules after it:
- each engine's data is on a **named volume** of the deployment, with names no earlier version used;
- **`megasamples down` removes containers and keeps volumes**, and so does stopping the Compose project directly;
- **staleness is decided by the volume's build identity**, which the image compares with its own at start: an image starts only on data it seeded;
- **a stale engine (U-3)** is refused by plain `megasamples up` (exit 5, `stale-image`), with nothing recreated, and is **replaced only with `megasamples up --discard engine`**, under the replacement rules below; started directly through Compose, the image refuses to start on it;
- **a volume whose seeding cannot be read (U-4)** is refused (`unidentified-volume`), even with `--discard engine`;
- **an earlier deployment (U-5):** where an earlier version's container, or a volume or Compose file it left, is detectable, plain `up` refuses before serving fresh data (exit 5, `earlier-deployment`, naming what it found and the README's upgrade route). `up --discard engine` removes an earlier container if there is one, **leaves every earlier volume in place and names those it can,** and starts on a new volume;
- **replacing a whole engine's volume** [114-2A] [114-2B] [115-7] is refused before any change without `--discard engine`, and is one act under the engine's deployment lock: a record of the old volume's identity, the replacement, the record completed with the new one's. It has **no phases and nothing to reconcile.** Each replacement takes a fresh `--discard engine`, and no command resumes an interrupted one: `reset --status` says what the record and the store show, and `up` then acts by the table. **Nothing is removed that cannot be identified, even with consent,** except a volume the replacement's own record shows it created and never seeded. It is refused while any reset on that engine is running, unsettled or unreadable [115-W].

Slice 2 does not merge without slice 3 (loop file, backlog row F21). So this workstream **applies** that decision: the invariants below govern today's anonymous volumes until slice 3 replaces them, and must not design a lifecycle slice 3 then discards. **Today's stopgaps are interim**: removing the replaced volume on every exit of a recreate, staleness by the image Compose resolves, refusing to renew what Compose cannot resolve, and the README's statement of what `down` discards. Where a question below would change [114-2F], it says so and is an owner decision.

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
| 10 | Opus N2 (O10-N2) | name-only matches could be another project's containers | an exemption, `remove_unlabelled` (`e247d73`), **reopened** by Opus round 11, 3 and Sol 9 (above) |
| 10 | Sol P3-2 (S10-P3-2) | the class test missed `container rm`, `--force`, split calls and `-f -v`; and the Compose `down` paths leave anonymous volumes, "while the named-volume transition belongs to slice 3" | the forms fixed in the AST class test (`86a5a84`); the guard cases to keep: `--force`, no option, `container rm`, podman, a split call, a shell string, the Compose forms, `-f -v`, `-vf`, `--volumes --force`; **input**: the slice 3 pointer is the "decided elsewhere" section above |
| 11 | Sol 8 (S11-8) | the README did not say what `make down` and `make clean-all` discard, or that the named SQLite volume survives while its contents are overwritten | **stopgap 3**: the README (`d1151a1`), the SQLite sentence corrected in round 12 (`c3a3acd`), the help in round 12 (`3067e07`); **input** for question 2 |
| 12 | Sol 4 | the failed-recreate tests cannot see collateral deletion: the fake has no unrelated detached volume, and the early-failure rows pass if cleanup tries to remove a mounted volume the fake refuses | **input** for the test plan: an unrelated detached volume, exact survivors, removal attempts inspected |
| 12 | Opus N1 | the "before" rows cannot fail: the fake refuses `volume rm` on an in-use volume whatever the flags, and Podman's `volume rm -f` removes the containers using it | **input** for the test plan: model `-f` as Podman documents it, and assert the "before" volume survives |
| 12 | Opus N2 | the staleness stopgap is tested in one direction only; an override that differs while `:dev` matches should be stale | **input** for L5 and fact F (round 12 added a row with distinct IDs and one stale service, `54e792c`'s test; the other direction stays open) |
| 12 | Opus N3 | `reset_engines` duplicates `recreate` rather than calling it, so the stopgap exists twice | **input** for fact A |
| 12 | Opus N4 | Compose `rm --volumes` also takes any volume a console image declares; whether CloudBeaver or DbGate do is unchecked | **input** for question 2 |
| 12 | Sol 7 | the table lacked the guard cases above, the exemption's reason and S11-8 | **input**: the rows above |
| 12 | Opus 2 | the help said "stop"; the runbook's "do not run" list predates version 1 | help fixed (`63a29fb`, `3067e07`, `4aebac5`); the runbook is **input** for question 2 |
| 12 | Opus 3 | slice 3's accepted design [114-2F] decides this area | **input**: the "decided elsewhere" section, and questions 2 and 5 |
| 6, 7, 8, 9 | S6-10; S7-9; S8-4 and O8-P3-2; S9-4 and O9-N5 | the start and health tests' teardown: resources made before the cleanup scope, removals unchecked, anonymous volumes leaked although removal exited 0, a failed inventory query read as an empty one | fixed in the tests (`tests/gates/start_scope.py`: registration before each command, checked removals, inventory status checked, volume sets compared); **input**: controls a design keeps for any test that makes containers |
| 13 | Sol 4 | the staleness tests lack a partial Compose answer (one service unresolved, one provably stale) and the opposite override (the override changed, the default still matching the running image) | **input** for L5 and fact F |
| 13 | Sol 8 | the teardown findings of rounds 6 to 9 were not in this table | **input**: the row above |
| 13 | Opus N2 | the unresolved warning prints for every engine, even with no container to recreate; with `config` failing while `up` works, a rebuilt image is never renewed, only warned about; the message could name `make reset R=<engine>` | **input** for question 5 |
| 13 | Opus N3 | the SQLite start copy leaves a `-wal`, `-shm` or hot `-journal` a stopped console wrote, which SQLite would replay into the freshly copied database | **input** for L2 |
| 13 | Opus N4 | the O12-N2 row credited the wrong commit and the other direction is untested | corrected above; **input** stays open |
| 13 | Opus 1, Sol 7 | the "decided elsewhere" section overstated "never recreated" and omitted the replacement rules and U-5 | **input**: the section restated, and questions 1 and 4 say they apply it |

## Questions the design must answer

**Owner decisions in this brief:** questions 2 and 4.

1. **Applying [114-2A] and [114-2B] until slice 3:** slice 3 replaces a volume as one recorded act with nothing to reconcile, and no command resumes an interrupted one. Until then, is today's `finally` in each command enough for the anonymous volumes, or should a command also keep a record of what it replaced, so `make status` can name a volume a failure left? Neither reopens slice 3's rule.
2. **Owner decision, what a person sees, applying [114-2F] until slice 3:** slice 3 decides that `down` keeps the engines' data on named volumes. Until then, with anonymous volumes, today's `down` discards working data, and the README and help say so. The question is only the interim: whether `make down` should warn or refuse before discarding changes. This does not reopen [114-2F]. It also covers whether DL-086's live-upgrade runbook (`docs/live-upgrade-runbook.md`, its "do not run" list, which predates version 1 and drives raw Podman and Compose) should name version 1's `make down`, and whether console images' declared volumes (CloudBeaver, DbGate) hold state `down` now removes.
3. Where do volumes megasamples could not remove get reported: each command's output only, or also `make status`, so a later run finds them?
4. **Owner decision, on a shared daemon, applying U-5 until slice 3:** slice 3 removes an earlier version's container only with `--discard engine`, and keeps every earlier volume. Until then, what ownership evidence permits today's `status clean` to remove a container (label, project, image of megasamples' own)? And is a pre-label match listed with a hint, or removed when its image is megasamples' own? The second, removing without `--discard`, would go beyond U-5, and says so.
5. **Applying [114-2F]:** slice 3 decides staleness by the volume's build identity and refuses a stale engine instead of recreating it. Until then, is today's interim, Compose's resolved image with no renewal when it cannot be resolved, enough? Or should `up` already refuse a stale engine rather than renew its volume? The second brings slice 3's rule forward and does not reopen it.
6. Does the class test enumerate by syntax (an AST walk, with assigned argvs resolved) or by a single execution seam every container command must use, so the fake daemon sees the whole class?

## Test plan

- **A fake daemon that models the documented behaviour** of Docker, Podman and Compose for each route in fact B, including a renewal followed by a failed `--wait`, a failed create, a failed removal and an interruption between steps. A table test generated from the decision table runs each command against it and asserts the remaining containers and volumes, the report and the exit.
- **A real cycle in the isolated store** on a project of its own (as round 10's `cycle-r10`): every command in fact A that can run there, on success and on a planted failure (an image that exits, a healthcheck that never passes), with the store's volume set compared before and after.
- **Ownership:** a foreign container under a pre-label name, and one in another Compose project, on the same daemon; neither is removed or loses a volume.
- **Staleness:** the image overridden in `.env` only, in the environment only, and rebuilt under the same tag.
- **The class test,** with planted rows for each form the code can take, including an assigned argv and a cleanup bypassed by an early return.
- **Reversals:** each invariant L1 to L6 removed fails at least one row.
