# Version 1, slices 1 and 2: review loop status

This is the loop over `feature/dl-077-v1`, run under DL-114, DL-120 and RCC.DataIntent's `knowledge/governance/review-and-fix.md`. The per-round triage records are `tests/dl077-v1-review-{1,2,3,4}.md`. The dispositions of rounds 5 to 14 are below.

## Stop count

**2 of 2: the loop is closed** (rounds 13 and 14). Round 14 had no P1 or P2, so it counts clean, the coordinator's decision, and the slice 1 and 2 review loop ends here. Its P3s were applied as one set, which WS1's first review round also reviews. The owner questions were answered by DL-122. The workstreams now run one at a time, in the coordinator's order: WS1, WS4, WS2, WS3, WS5. Each is designed from its brief and DL-122, reviewed as a design by Sol and Opus, built test-first, and reviewed to two clean rounds.

Round 13 counted clean, the coordinator's decision: its one P2 (Sol P2-1) is in WS4's area, a WS4 input with no stopgap, and nothing else was fix-now outside the five areas. Round 12 had found a P2 (Sol) and kept the count at 0. Round 11 had found a P2 (both reviewers). Round 10 had found two P2s, fix-now, and returned it to 0, the coordinator's decision. Round 9 had counted clean (1 of 2); rounds 6, 7 and 8 had kept it at 0. The loop ends after two rounds in a row with nothing to fix now outside the workstreams.

**Scope from round 8, the coordinator's decision:** a workstream brief is an input to that workstream's own design, which is reviewed in its own loop after this one ends. So findings about a brief's content are recorded there as that workstream's inputs, not fixed now here. That covers its facts, its test plan's coverage and its questions.

This loop judges two things:
- what lies outside the five areas: code, tests, documentation and records;
- whether each brief carries every input faithfully.

## Hot areas, now workstreams

An area is hot when the same class is found in it in two rounds running. Each of these had a finding in three rounds running, or more. **They are no longer patched round by round.** Their briefs are in `docs/design/`, and each will be built test-first, one at a time, after the loop ends, then reviewed to two clean rounds. That is all before the merge (DL-101).

| # | Area | Brief | Rounds with findings |
|---|---|---|---|
| 1 | Start certification: the wrapper, the private password start, non-root and bypass starts | `docs/design/dl077-ws1-start-certification.md` | 2, 3, 4, 5 |
| 2 | Orphan-scan completeness | `docs/design/dl077-ws2-orphan-scan.md` | 3, 4, 5 |
| 3 | Removal outcomes across engines | `docs/design/dl077-ws3-removal-outcomes.md` | 1, 2, 3, 4, 5 |
| 4 | The native suite's binding to its target | `docs/design/dl077-ws4-native-suite-binding.md` | 2, 3, 4, 5 |
| 5 | Container and volume lifecycle: every command that creates, recreates or removes a container, and its volumes on success, failure and interruption; ownership of name-matched containers; image staleness; the class test | `docs/design/dl077-ws5-container-volume-lifecycle.md` | 9 (batch), 10, 11 |

## Round 5: each finding's disposition

These are the reviews of `c95ee833`: Sol (`S5-*`) and Opus (`O5-*`). A hot-area finding gets a stopgap only where DL-040 finds a realistic route to real harm, and then only the smallest one that removes it.

| ID | Sev. | Area | Disposition | Stopgap and why |
|---|---|---|---|---|
| S5-1 | P2 | 4 | Workstream input | **None.** It needs another task to replace the container and reuse its port mid-run, in the same isolated store. That route is constructed, the harm is test-time writes to a scratch container, and every target in this store is disposable. |
| S5-2 | P2 | 3 | Workstream input | **None.** It needs a filesystem I/O error right after a successful unlink. The data is gone as asked, and `copy show` confirms each copy's own state. *Corrected in round 6:* `copy show` cannot reconstruct which copies the sweep removed, so the reply's lists stay wrong until WS3. **Reopens the stopgap decision:** a supported caller that acts on the sweep's lists without `copy show`, or a reproduction of the I/O error on a supported filesystem. |
| S5-3 | P2 | 1 | Workstream input | **None.** A custom persisted socket setting makes the password setup miss the private server, and the start fails closed: the container exits and no public server starts. *Corrected in round 6:* until then the private server accepts connections on its custom local socket. No TCP address listens, and the wrapper, which is PID 1, stops it on exit. **Reopens:** a route by which another process reaches that socket in the window. |
| S5-4 | P2 | 2 | Workstream input | **None.** It needs a permission change that leaves `base/` searchable but unlistable. The harm is an orphan's disk use going unreported. No data is touched, and the control is detective. |
| S5-5 | P2 | 2 | Workstream input | **None.** It needs a whole-engine reset concurrent with `reset --status`. Two operator actions; the report is wrong, the data is not. |
| S5-6 | P2 | — | **Fixed now** | — The healthcheck's ERROR on every probe, reached on every `up`. `2c9b106` (test `bc9a900`, test-only `6d321ad`). *Corrected in round 6:* the report was also callable by `admin`, through the default privileges; `ae61776` revokes it, so only `demo` and the superuser may call it (test `aedd5e6`). |
| S5-7 | P3 | 1 | Workstream input | **None.** The non-root ordering fails closed. |
| S5-8 | P3 | — | **Fixed now** | — Design 2.4 lists `NO_BACKSLASH_ESCAPES` (`93a26c6`). |
| O5-1 | P3 | 3 | Workstream input (same class as S5-2) | **None**, as S5-2, with the same round 6 correction. |
| O5-2 | P3 | — | **Fixed now** (same as S5-6) | — |
| O5-3 | P3 | 1 | Workstream input | **A documentation stopgap.** The README sentence was inaccurate. It now says a non-root start exits before the public server starts, and that the private password start may run first on its local socket (`93a26c6`, corrected in the next commit after a run showed that start answering). |
| O5-4 | P3 | 1 | Workstream input | **A documentation stopgap.** The README now states that a replaced entrypoint or a wrapping command is unchecked, and that the healthcheck, which only the generated Compose file defines, is then the only signal (a hand-run container has none) (`93a26c6`). |
| O5-5 | P3 | 3 | Workstream input | **None.** The exit code is right; only one copy's reason misleads. |

## Backlog

Each row can wait: there is no realistic route to harm, or the harm is stated as a limit.

| What | From | Why it can wait |
|---|---|---|
| Refused SQLite creates leave lock files | round 1, A14/F16 | No record or data is affected. Reopens with any change to the lock protocol. |
| The MySQL rewrite of a table named like its database | round 1, F12 | Fails closed; its witness is withheld. |
| Looks take the change lock; `renew` can return 6 during `list` | round 1, F15 | Callers retry 6. |
| Direct `pg_database` update without a tuple lock | round 1, F18 | No route found by either reviewer. |
| Configuration checks only at image build | round 1, F20 | Start paths are slice 3+. The account name `megasamples_read` is now refused (round 14, S14-6). |
| Declared MySQL writers' grants are baked before slice 3's suspension | round 1, F21 | Slice 2 does not merge without slice 3. |
| Ownership transfer after creation; `DROP OWNED` and provisioned defaults | round 1, S6 and S7 | The rules are as specified. |
| Range-type constructors keep `PUBLIC EXECUTE` | round 2, F2-8 | A stated limit: immutable built-in code. |
| MySQL `character_set_client` and `collation_connection` not restored | round 3, O3-4 | A stated limit in design 2.4. |
| The H-3 probe's client-only accounting has no reversal | round 4, S4-9 | A recorded limit of the control. |
| `test_quiescence_gate` unrelated-holder case fails, also at `e61335f` | rounds 1–5 | A baseline failure; its cause is not isolated. |
| MySQL `/*+ */` optimizer hints are treated as comments, so a schema name inside one is not rewritten | round 8, S8-8's class check | Not checked on a server. A hint names tables and query blocks, and no shipped template carries one. Reopens if a template does. |
| A versioned executable comment above the server's version (`/*!99999 x*/`) is read as code by the replay, though MySQL ignores its content, so `source/*!99999 x*/.t` keeps `source` | round 10, Opus N3 | Constructed; no shipped template carries one. It sits with the optimizer-hint row and reopens with it. |
| The catalogue generator's docstring and generated header say it reads `megasamples.datasets` from a running image; it reads the repository | round 13, S13-6 | The README is corrected; the header is in `CATALOGUE.md`, which a change would regenerate. Reopens with the next catalogue change. |
| Design 8.3's claims not yet made | rounds 2–5 | T-11 `verify`, T-15 and the kill points, the full disk, and the wider account matrix. The merge waits for each. |

## Round 5's runs

These are the runs on the candidates built from `8102f35`: PostgreSQL `9fbee1a14d05` and `9a8e07e91aca`, MySQL `87dd365119ac` and `887f1224214a`, and the fallback fault image `acd0a1d82f47`. Logs are under `build/dl114-r1-work/`.

**Passed**
- **The TCP server suite:** PostgreSQL 23 passed, 12 skipped; MySQL 32 passed, 3 skipped in each mode; the fallback case passed.
- **PostgreSQL suites:** policy OK; restore and the real reset OK; orphans OK; start OK, with the non-root case asserting the exit; health, 3 passed. *Corrected in round 6:* the start suite's path-form password check could not fail. The non-root case ran first on the same volume, and the key probe used the image's trusted loopback. `b65234f` gives each credential case its own volume and probes over scram; a planted skip of the override then fails it.
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


## Round 6: stopgaps, the disagreement and its reasoning

**Sol's view (round 6, P2-2 and P2-3):**
- **S5-1:** suspend the native suite's unchecked TCP statements that can write until WS4 binds them, because a second run on the same published port could receive database and role changes.
- **S5-4 and S5-5:** add the smallest stopgap that reports `incomplete`, because DL-119 relies on the scan to disclose a gap.

**Opus's view:** no stopgap is needed. Both routes need two concurrent operator or task actions, or an unusual permission state.

**The coordinator's decision: none.**
- Both routes need a second concurrent run or operator, so they are constructed under DL-040.
- The harm falls on a disposable test store (S5-1), or is a missed report that the README's removal route already guards: it stops creates and drops and rechecks the OID before acting (S5-4, S5-5).
- WS2 and WS4 fix both before the merge (DL-101).

**Reopens with:** a supported caller acting on the scan's `complete` without the README's route, or a native run against a store that holds a non-disposable target.

## Owner questions, for the two deciders (DL-104): answered by DL-122

The two deciders answered all fourteen in **DL-122** (RCC.DataIntent `docs/work/decision-log.md`, 2026-11-21), on the options paper `docs/design/dl077-v1-owner-questions.md`. They differ from its recommendations on Q4 (bump to 2 now, refuse any marker but the image's own, a digest guard), Q6 (four per-role states), Q7 (exit 5, `orphan-scan-incomplete`), Q8 (narrowed to same-instance, catalog-matched findings, 3.5a amended) and Q14 (removal by observed full container ID). Each brief's question carries its answer. Also recorded: console volumes to be established; the runbook's `make down` wording is DataIntent's; the contract at merge with impact notes and conformance tests; one message per cause; WS3's contended copy stays `kept` and `not-exclusive` still aborts; the MySQL image's healthcheck to be decided by WS1.

| # | Workstream | Question |
|---|---|---|
| 1 | WS1 | Is the private password start kept, or are passwords applied another way? It changes when a credential takes effect. **DL-122:** Keep the private password start, made exact. With overrides set, an argument that would move the socket or data directory is refused before any launch. |
| 2 | WS1 | Are non-root starts supported (move the health passfile), or refused before any launch? **DL-122:** Non-root starts are refused before any launch, as the wrapper's first check; the README says platforms that force a non-root user are unsupported in version 1. |
| 3 | WS1 | Is each start refusal's one-line message a stable, supervisor-facing code? **DL-122:** Each start refusal carries a stable code in its line, exit 1 kept. Tokens are fixed at the freeze; additions are allowed; a matcher treats an unknown code as a refusal. |
| 4 | WS1 | **On-disk format:** how are the read-policy marker and the extension's version bumped and migrated for retained volumes? **DL-122:** Bump the marker and the extension to 2 before the freeze, and both on any later script or grant change. Before either server starts, refuse any marker but the image's exact own (newer, older or unrecognised), keep the volume, and name the upgrade route. A test pins a digest of the extension script and its grants to the marker and version. |
| 5 | WS1 | Does the image carry its own `HEALTHCHECK`, so a hand-run container has the signal? **DL-122:** The PostgreSQL image carries its own HEALTHCHECK, from one source shared with Compose; a test checks it survives the Podman build format; the README notes orchestrators that ignore it. |
| 6 | WS1 | What may a failed start leave behind after a password change, and must it roll the change back? **DL-122:** Applied keys stay as applied. The log reports each requested role, by name only, as confirmed applied, confirmed refusal, unattempted or uncertain. A stale or partial health passfile is never usable after a failure. A retry with the same keys converges. |
| 7 | WS2 | Does `reset --status` exit non-zero when the scan is incomplete? **DL-122:** Exit 0 on an incomplete scan, with an opt-in --fail-on-incomplete that exits 5 with reason orphan-scan-incomplete. The JSON is identical with or without it; a complete scan with orphans exits 0. |
| 8 | WS2 | Does `up` block or fail on an incomplete scan, and are partial warnings shown? **DL-122:** up warns only. An orphan is shown under incomplete only when its location was listed and matched against a catalog read from the same pinned instance; otherwise the banner with its reason and no directories. reset --status follows the same rule, and 3.5a is amended. |
| 9 | WS2 | Is an invalid database (an interrupted drop) reported, and how? **DL-122:** Its own invalid-database warning. For a managed copy the route is copy drop again; raw DROP DATABASE is for an unmanaged database only. |
| 10 | WS3 | What is the result field for an unsettled cleanup step: `ledger: unsettled`, or one that names the step? **DL-122:** One always-present unsettled list with a documented vocabulary (ledger, sidecar, link, sync, lock); ledger agrees with it; an unknown step name is treated as unsettled. |
| 11 | WS3 | Is there a third per-copy outcome (unknown or partial), and a list for the copies a stopped sweep never reached? Any change to a public exit or to `removed`/`kept`. **DL-122:** Two new lists, unknown and unreached, always present. Exit codes and the meanings of removed and kept unchanged. An unknown entry carries its recovery identity. |
| 12 | WS4 | **Security posture:** may the suite authenticate to a listener it has not yet proved to be the checked instance? **DL-122:** No authenticating to an unproven listener: every native-suite connection is bound to the checked container ID before authentication. Without such a transport for a driver, its cases are Not run before any credential is sent, and the question returns to the deciders. |
| 13 | WS5 | **What a person sees, in the interim until slice 3** (which decides that `down` keeps named data volumes, [114-2F]): whether today's `make down` should warn or refuse before discarding changes; this does not reopen [114-2F] **DL-122:** Before slice 3, make down states what it discards and prints one warning line before the discard. |
| 14 | WS5 | **On a shared daemon:** what ownership evidence permits `status clean` to remove a container, and whether a pre-label name match (build, test and audit names) is listed with a hint or removed when its image is megasamples' own. Slice 3's U-5 does not decide it **DL-122:** status clean removes only labelled transients, by the observed full container ID. Name-only matches are listed with ID, image, creation time and a hint. --all follows the same rule. |

## Round 6's runs

No large container batch was run, because DataIntent's gateway `--all` was running. The container runs were focused PostgreSQL tests, one container at a time. The full `pytest` suite ran on the host, with no container; its opt-in container tests skip there. The image is `ce3b539fb522`, built from `ae61776` (PostgreSQL `chinook`), and `cf7325f4f9be` (`chinook employees pubs`). Logs are under `build/dl114-r1-work/`.

**Passed**
- The health tests, 3 passed: only `demo` and `postgres` may call the report, healthy probes raise no ERROR, and the placeholder case fails.
- The start suite (`start-r6-start2.log`), and its reversal: a skipped path-form override fails (`start-r6-path-reversal2.log`).
- The PostgreSQL policy suite (`policy-r6-policy.log`).
- `test-image` on `chinook`.
- The native PostgreSQL suite, 46 passed (`native-r6-pg-full.log`).

**Failed**
- The full suite (host only): 2 failed, 1,078 passed, 313 skipped (`pytest-r6.log`, 11:03:52). These are the same two baseline failures as before, both also failing at `e61335f` (`tests/dl077-v1-review-1.md`, "Baseline"):
  - `tests/test_quiescence_gate.py::test_readable_unrelated_holder_refuses_with_reversal`;
  - `tests/test_rollback_preparation.py::test_whole_rollback_preserves_frozen_retained_file_list_and_digests`.

**Not run**
- The MySQL suites and images, and the TCP copy suite. Round 6 changed no MySQL or copy code; their last runs are round 5's.

## Round 6: restoration and isolation

- **Retained isolated stack.** The fingerprint ledgers (phase `r6-final`) are byte-identical to build 1's `after` ledgers:
  - PostgreSQL `ee0f1a8b…711e`;
  - MySQL `a5c0466a…a72f`;
  - SQLite `5b0c2768…da98`.
- **Removed:**
  - every task container this round started;
  - 32 anonymous volumes, each checked unused, from round 5's runs and this round's;
  - this round's reversal image.
- **Kept for review:**
  - the ACL images `localhost/dl114-r6-pg:acl` and `:acl-full`;
  - the round 5 candidates;
  - the fault images;
  - the runner.
- **The isolated socket service** is stopped.
- **Isolation** (`build/dl114-r1-work/isolation-check.sh`, read-only):
  - **Live deployment:** the nine live `megasamples-*` entries are unchanged by ID, state, health, start time and image.
  - **Isolated store:** the same 20 containers.


## Round 6: each finding's disposition

These are the reviews of `53334d4c`: Sol (`S6-*`) and Opus (`O6-*`).

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| S6-1 | P2 | — | **Fixed now**: `admin` could call the loaded report | `aedd5e6` (test), `ae61776` |
| S6-2 | P2 | 4 | Workstream input; **no stopgap**, the coordinator's decision recorded above | WS4 |
| S6-3 | P2 | 2 | Workstream input; **no stopgap**, as S6-2 | WS2 |
| S6-4 | P2 | 3 | Workstream input: the table could not derive the reply | WS3 (round 6 rows) |
| S6-5 | P2 | 1 | Workstream input: failures after a password change | WS1 (round 6 rows) |
| S6-6 | P2 | — | **Fixed now**: the start suite's masked path-form check | `b65234f` (test only) |
| S6-7 | P2 | 2 | Workstream input: a restart, `pg_tblspc`, malformed results | WS2 (round 6 rows) |
| S6-8 | P2 | 4 | Workstream input: the TCP proof and its bootstrap | WS4 (round 6 rows) |
| S6-9 | P3 | — | **Fixed now**: the S5-2 and S5-3 rationales corrected, with what reopens them; the README's Compose-only healthcheck | `2670900`, `bf7ce84` |
| S6-10 | P3 | — | **Fixed now**: the healthy-probe test's anonymous volume | `aedd5e6` |
| O6-1 | P2 | — | **Fixed now**, the same as S6-6 | `b65234f` |
| O6-2 | P2 | 3 | Workstream input | WS3 (round 6 rows) |
| O6-3 | P2 | 4 | Workstream input | WS4 (round 6 rows) |
| O6-4 | P2 | 1 | Workstream input | WS1 (round 6 rows) |
| O6-5 | P2 | 2 | Workstream input | WS2 (round 6 rows) |
| O6-6 | P2 | — | **Fixed now**: S5-3 and S5-6 records corrected | `2670900` |
| O6-P3-1 | P3 | — | **Fixed now**, the same as S6-1 | `ae61776` |
| O6-P3-2 | P3 | 1 | Workstream input: the extension changed without a version or marker bump | WS1, question 7 |

## Round 7: each finding's disposition

These are the reviews of `c0179c8d`: Sol (`S7-*`) and Opus (`O7-*`). Findings about a brief's content are that workstream's inputs, under the scope recorded above.

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| S7-1 | P2 | 1 | Workstream input: a failed public start, informational commands, lost password replies | WS1 (round 7 rows) |
| S7-2 | P2 | 2 | Workstream input: the directory-to-catalog match | WS2 (round 7 rows) |
| S7-3 | P2 | 3 | Workstream input: rollback and cleanup steps; unsent versus skipped | WS3 (round 7 rows) |
| S7-4 | P2 | 4 | Workstream input: the proof and its oracle | WS4 (round 7 rows) |
| S7-5 | P2 | — | **Fixed in round 8**, not round 7: `644d949` carried P-8 but overwrote PR #14's evidence and left the reconciliation record stale (S8-1, O8-1). PR #14's inventory is restored, v1's is published under its own name, and IA-01 is reconciled by signature | `1cd35b8`, `644d949`; round 8: `9fd97e8` (test), `66bda86` |
| S7-6 | P2 | — | **Fixed now**: the strict-read guide's MySQL grants, and three more drifts found by checking it against the image | `ffddb0c` (test), `319294d`, `e5d6f23` |
| S7-7 | P3 | 1 | Workstream input for retained volumes (WS1 question 7). **Fixed now** for the rights test's scope: every non-built-in role (outside `pg_*`), in every connectable database of the image tested and in the databases the restore matrix restores (S8-3) | `97cbd24`; WS1 |
| S7-8 | P3 | — | **Fixed now**: start-test assertions witness their messages; a namespace positive control | `6ed9e2b` |
| S7-9 | P3 | — | **Fixed in round 7 for one of the three start tests**, `test_round_four_start_routes`, and for the two health tests (Opus round 9, N4). The other two start tests, a failure before the scope, and anonymous volumes were fixed in round 8 (O8-P3-2, S8-4) | `6ed9e2b`; round 8: `d8b2616`, `f23ec19` |
| S7-10 | P3 | — | **Fixed now**: the verification-scope wording and the bypass disposition | this file |
| O7-1 | P2 | 1, 3 | Workstream input: the coverage criterion | WS1, WS3 (round 7 rows) |
| O7-2 | P2 | 4 | Workstream input: the table spanning S, T, A, P, B, C and D | WS4 (round 7 rows) |
| O7-3 | P2 | — | **Fixed now**: this round 6 table, the stale header | this file |
| O7-P3-1 | P3 | — | **Fixed now**, the same as S7-7's rights scope | `97cbd24` |
| O7-P3-2 | P3 | — | **Fixed in round 8**, the same as S7-5 | `66bda86` |
| O7-P3-3 | P3 | — | **Fixed now**, the same as S7-8, with the new probe's reversal recorded | `6ed9e2b` |
| O7-P3-4 | P3 | 1 | Workstream input: question 6 in the owner list | WS1 |
| O7-P3-5 | P3 | 3 | Workstream input: fact E as an owner category | WS3 (round 7 rows) |
| O7-P3-6 | P3 | — | **Fixed now**: the header, and the README's non-root clause | this file, `fcc122b` |
| O7-P3-7 | P3 | 1 | Workstream input, the same as S7-7's retained volumes | WS1, question 7 |

## Round 8: each finding's disposition

These are the reviews of `9fa27c3a`: Sol (`S8-*`) and Opus (`O8-*`). Both found the same P2.

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| S8-1, O8-1 | P2 | — | **Fixed now.** PR #14's inventory and script are restored at their paths, byte for byte, so its evidence page, its links, its exported receipt and the canary receipt are true again. v1's set is published as `dl-077-v1-public-routines.{json,md}` only. The IA-01 comparison is redone signature by signature: four additions, none removed, the fourth a direct grant to `demo` outside `PUBLIC`. "A fresh login" is corrected | `9fd97e8` (test), `66bda86`; `tests/dl077-v1-read-profile.md` |
| S8-2 | P3 | — | **Fixed now**: the guard regenerates every published row from the shared reasons, and the generator's refusals are tested with fixture rows | `9fd97e8`, `66bda86` |
| S8-3 | P3 | — | **Fixed now**: the guide test takes MySQL's privileges and scopes from the grant generator; the guide names the superuser's access to the report; S7-7's record is scoped | `9439d9b` (test), `c273bb8`; this file |
| S8-4 | P3 | — | **Fixed now**, with O8-P3-2: one labeled cleanup scope for all three start tests | `d8b2616` (test), `4c4461a`, `f23ec19` |
| S8-5 | P3 | — | **Fixed now**: SQLSTATE `42501` and the hook's own message, with fresh names | `a4f430e` (test), `f23ec19` |
| S8-6 | P3 | 1, 2, 3 | **Fixed now** (faithfulness): WS2's S4 and S2-3 rows; WS3's A4/F6 removal part; WS1's fact H names the pre-report and pre-revoke builds | `57cb0ec` |
| S8-7 | P3 | — | **Fixed now**: the README's non-root sequence is qualified | `f28022d` |
| S8-8 | P3 | — | **Fixed now for the reported case and part of its class**: `--`, executable comments and identifier characters, checked on a MySQL server. Round 9 found the rest of the class (non-ASCII spaces, comments around the dot, case) and fixed it | `bf104ff` (test), `8cf268f`; round 9: `5212c3b`, `7e514ab` |
| O8-P3-1 | P3 | — | **Fixed now** for signature, namespace, kind and volatility, in every database the native suite covers. Round 9 added the name, the operator or cast, and the publication's databases list (S9-3) | `f2b33b9`; round 9: `93b4cf7` |
| O8-P3-2 | P3 | — | **Fixed now**, the same as S8-4 | `f23ec19` |
| O8-P3-3 | P3 | 1, 2 | **Fixed now** (faithfulness): WS1's round 7 Sol 1 row says where each input is carried, and fact L, the outcomes and question 9 carry them; WS2's S4 row | `57cb0ec` |
| O8-P3-4 | P3 | — | **Fixed now**: the MySQL init comment, `ARCHITECTURE.md`, and the unused variable (gone with PR #14's script restored) | `f28022d`, `66bda86` |

No finding was deferred. One note from S8-8's class check went to the backlog: MySQL optimizer hints.

## Round 9: each finding's disposition

These are the reviews of `cda80f25`: Sol (`S9-*`) and Opus (`O9-*`, and its notes `O9-N*`). Neither had a P1 or P2. Each P3 below was cheap and in hand, so all were fixed. None was deferred.

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| O9-1, S9-1 | P3 | — | **Fixed now**: `--` is a comment only before one ASCII space or control byte; the qualifier search skips comments; schema names match exactly (this image keeps `lower_case_table_names=0`). All checked on a MySQL server. A replayed procedure with these traps is added to the MySQL copy suite, which runs in the batch | `5212c3b` (test), `789bb8d` (copy-suite test), `7e514ab` |
| O9-2, S9-2 | P3 | — | **Fixed now**: the receipt's untracked set must be exactly the PR body, and every other path is compared, so a deletion fails | `dd8c369` |
| O9-3 | P3 | — | **Fixed now**: the guide says PR #14 left the MySQL engine and views unchanged, and that version 1 changed the engine but not the views | `483b7cb` (test), `f44b6c7` |
| S9-3 | P3 | — | **Fixed now**: the native comparison covers every published field of each row, and the publication's databases list and count | `93b4cf7` |
| S9-4 | P3 | — | **Fixed now**, with O9-N5: the cleanup scope checks each inventory query's status and compares volume sets; a labeled leftover and the SQLSTATE are tested on their own | `6f820a8` (test), `40375c9` |
| S9-5 | P3 | — | **Fixed now**: the guide test ties the escaping claim to the generator's exact patterns | `90cd4ab` |
| S9-6 | P3 | — | **Fixed now**: the round 8 record now says the MySQL image takes the tokenizer, so its build, `test-image` and the copy suite are in the batch | this file |
| S9-7 | P3 | 2, 4 | **Fixed now** (faithfulness): S6-2 in WS4 and S6-3 in WS2, each with the no-stopgap decision and its reopening criterion | `052d256` |
| O9-N1 | P3 | — | **Fixed now**: the class check's list of files | this file |
| O9-N2 | P3 | 2 | **Fixed now** (faithfulness): WS2's S4 row carries the closed copies and the return to the deciders | `052d256` |
| O9-N3 | P3 | — | **Fixed now**: the `__main__` block is last, so a script run reaches all 15 tests | `6f820a8` |
| O9-N4 | P3 | — | **Fixed now**: S7-9's wording | this file |
| O9-N5 | P3 | — | **Fixed now**, the same as S9-4 | `40375c9` |

## Round 10: each finding's disposition

These are the reviews of `0909856a`: Sol (`S10-*`) and Opus (`O10-*`, with its notes `O10-N*`). Both P2s were fix-now, so the stop count is 0 of 2.

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| O10-P2-1 | P2 | — | **Fixed now on the success paths** (corrected in round 11: a failed recreate still stranded the replaced volume, O11-1 and S11-1, now WS5 with a stopgap): `megasamples/data_volumes.py` takes the engines' anonymous volumes on the Compose routes. `down` and `clean --all` run Compose `rm --stop --force --volumes` before `down`, which keeps the named SQLite volume; `up`'s stale recreate removes what it replaced by name, the helper `reset_engines` now shares. A real down/up cycle and a renewed recreate in the isolated store left only the named volume; round 9's commands left 4 | `9d38710` (test), `c917a1f` |
| S10-P2-1 | P2 | — | **Fixed now**: both image tests remove a leftover override container with its volumes, check the launch, query only the ID it returned and remove that ID. Every other `docker run` in `megasamples/` already checks its result | `b511dc0` (refactor), `e0e482a` (test), `a27880a`, and the fit to the existing fakes after it |
| O10-P3-2, S10-P3-2 | P3 | — | **Fixed now for the forms listed** (corrected in round 11: an argv held in a variable, and a cleanup bypassed by an early return, are not seen; WS5 inputs): the class test walks the syntax tree (both Docker spellings, podman, the helpers, shell strings, split calls, any flag spelling, the Compose forms), with exemptions by file and function | `86a5a84` |
| O10-N2 | P3 | — | **Fixed now, reopened in round 11** (O11-3, S11-9; a WS5 input): name-only matches keep their volumes, an exemption with its reason | `86a5a84` (test), `e247d73` |
| S10-P3-3 | P3 | — | **Fixed now**: publication qualification is an explicit run (`STRICT_READ_V1_PUBLICATION=1`), and ordinary runs accept a dataset selection (corrected in round 12: the selection check rejected an append dataset until it compared per database, S12-1) | `3143e9c` |
| S10-P3-4 | P3 | — | **Fixed now**: every tracked receipt path must exist | `ed6d1a3` |
| S10-P3-5 | P3 | — | **Fixed now**: the guide calls the MySQL boundary probe PR #14's evidence that fails on version 1, and points at the current checks | `ee32122` (test), `465c16b` |
| S10-P3-6 | P3 | — | **Fixed now**: `demo` holds the whole set in every session; a role relying only on `PUBLIC` lacks one | `ee32122` (test), `465c16b` |
| S10-P3-7 | P3 | 2 | **Fixed now** (faithfulness): WS2's S4 row marks DL-113's escalation historical and names DL-119 as the current rule | this round's records commit |
| O10-N1 | P3 | — | **Fixed now**: the tokenizer test's comments | `65beaee` |
| O10-N3 | P3 | — | **Backlog**, beside the optimizer-hint row: constructed, no shipped witness | this file |
| O10-N4 | P3 | — | **Fixed now**: a failed store-wide listing, at the close and at the open | `65beaee` |

## Round 11: each finding's disposition

These are the reviews of `5a75c237`: Sol (`S11-*`) and Opus (`O11-*`, with its notes `O11-N*`). Both found the same P2, so the stop count stays 0 of 2.

**The coordinator's decision: container and volume lifecycle is hot.** The same class was found in three rounds running: round 9's batch, round 10's Compose routes, and round 11's failure path. It becomes workstream 5 (`docs/design/dl077-ws5-container-volume-lifecycle.md`), built after this loop and before the merge. Only the smallest stopgaps for realistic harm are made now.

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| O11-1, S11-1 | P2 | 5 | **Stopgap**: `remove_replaced` on every exit after the renewing `up`, in `recreate` and `reset_engines`. Fake-daemon rows cover a failure after renewal and one before it. On red only the two "after" rows failed; the "before" rows are guards that cannot fail as the fake stands (Opus round 12, N1, a WS5 input). The design is WS5's | `00bbf89` (test), `2482eaf` |
| S11-2 | P3 | 5 | **Stopgap**, triaged under DL-040: `.env.example` documents an image override in `.env`, so an operator reaches it on an ordinary route, and every `make up` would discard the working data. Staleness now uses the image Compose resolves. A WS5 input for L5 | `f769ff3` (test), `36c7b0f` |
| S11-8 | P3 | 5 | **Fixed now** (what a person sees): the README says what `make down` and `make clean-all` discard, and what the named SQLite volume keeps | `913f3d4` (test), `d1151a1` |
| S11-7 | P3 | — | **Fixed now**: the native suite follows the image's own dataset selection. The checkout's configuration must match the image's registry, and the employee-view and parity cases follow the selection. Run on a real chinook-only image | `f6a44e4` |
| S11-11 | P3 | 2 | **Fixed now** (faithfulness): WS2's table carries S10-P3-7 | this round's records commit |
| O11-2, S11-5 | P3 | 5 | WS5 input (L6): an assigned argv, and a cleanup bypassed by an early return | WS5 |
| O11-3, S11-9 | P3 | 5 | WS5 input (L3): name-only matches and ownership | WS5 |
| S11-3 | P3 | 5 | WS5 input (L4): `clean --all` exits 0 when Compose's removal fails | WS5 |
| S11-4, O11-N3 | P3 | 5 | WS5 input: the override checks' fallback to the fixed name | WS5 |
| S11-6 | P3 | 5 | WS5 input (test plan): the `clean --all` regression's order | WS5 |
| S11-10 | P3 | 5 | **Records corrected now**: the counts (23 direct removals and four Compose calls; 26 class-test cases) and `c4745ba` named. A WS5 input for L6's enumeration | this file |
| O11-N1 | P3 | 5 | WS5 input: the main image-test containers query by fixed name | WS5 |
| O11-N2 | P3 | 5 | WS5 input (fact B): the `--rm` removals; recorded in the batch section now | WS5; this file |

## Round 12: each finding's disposition

These are the reviews of `9fe11377`: Sol (`S12-*`) and Opus (`O12-*`, with its notes `O12-N*`). Sol's P2 keeps the stop count at 0 of 2. **What the reviews found of the stopgaps at `9fe11377`** (corrected in round 13): Opus found stopgaps 1 and 2 remove their harms with no new harm, and stopgap 3 only partly, since the help still said "stop" (O12-2). Sol found stopgap 2 could still discard data when Compose's resolution failed (S12-3). Both are closed by this round's fixes below.

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| S12-1 (P2), O12-1 (P3) | P2, P3 | — | **Fixed now**: the native selection check compares per database (`unique_databases`), with a host table (a base with its append dataset, without it, a base missing on either side). The guide and README say the registry is per database. Run natively on PostgreSQL and, for the first time, MySQL | `94a7b65` (test), `a10d1eb` |
| O12-2 | P3 | 5 | **Fixed now**: `make help`, the CLI list, `down`'s description and workspace's usage name each engine's working data, under the README's test. The runbook's list is a WS5 input (question 2): DL-086's procedure, unchanged by version 1, never runs `make down` | `63a29fb` (test), `3067e07`, `4aebac5` (the test's own index corrected) |
| S12-3 | P3 | 5 | **Stopgap** extended: no renewal for a service whose image Compose cannot resolve, with a message; a row with distinct IDs and exactly one stale service | `54e792c` (test), `922ee62` |
| S12-6 | P3 | — | **Fixed now**: PostgreSQL `test-image`'s write probes name a real column and need a permission refusal. Run natively | `3cf1f10` (refactor), `70405d9` (test), `8eb964b` |
| S12-2 | P3 | — | **Fixed now**: MySQL output compared in the batch form on both client paths. Native red and green, CLI and library modes | `e6ed4ef` |
| S12-5 | P3 | 5 | **Fixed now**: the README's SQLite restart sentence, tested exactly | `5477d49` (test), `c3a3acd` |
| S12-9, O12-N5 | P3 | — | **Fixed now**: the header's five areas; the recreate row's reds stated exactly; each round 11 host result with its revision; `c4745ba`'s order; owner questions and round sections in order | this file |
| O12-3, S12-7 | P3 | 5 | **Fixed now** (faithfulness): WS5 carries S11-8, O10-N2 (reopened), S10-P3-2, S12-4, O12-N1 to N4, the guard cases, and a "decided elsewhere" section citing slice 3's [114-2F] and its U-table; questions 2 and 5 say they apply it, not reopen it. The stopgaps are interim | the brief |
| S12-4 | P3 | 5 | WS5 input (test plan): collateral deletion | WS5 |
| O12-N1 to N4 | P3 | 5 | WS5 inputs | WS5 |
| S12-8 | P3 | 1 | **Fixed now** (faithfulness): WS1 carries S7-8 and O7-P3-3 | the brief |
| O12-N6 | P3 | — | **Fixed now**: the selection test's MySQL row ran natively | `a10d1eb` |

## Round 13: each finding's disposition

These are the reviews of `6ddb40de`: Sol (`S13-*`) and Opus (`O13-*`, with its notes `O13-N*`). **The coordinator's decision: Sol's P2-1 is in WS4's area** (fact T: on a single-engine stack, the native suite indexes the absent engine's target), and its harm is a visible test error, not data. So it is a WS4 input with no stopgap. **Nothing else was fix-now outside the five areas, so round 13 counts clean: stop count 1 of 2.**

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| S13-1 | P2 | 4 | **WS4 input, no stopgap** (the coordinator's decision) | WS4 |
| O13-3, S13-2 | P3 | — | **Fixed now** (in hand): MySQL `test-image`'s write probes need MySQL's refusal (1142, 1370 or "denied"); PostgreSQL's gain a zero-row INSERT probe; the fake checks each probe's database and account. Run natively on both engines | `e6786e5` (refactor), `4a54c2f` (test), `ba78dee` |
| S13-3 | P3 | 5 | **Fixed now** (in hand): the top-level listing and `clean --help` name the working data and the named SQLite volume, under a test of the rendered help | `c047fe7` (test), `8b81c46` |
| S13-5 | P3 | — | **Fixed now** (in hand): a parity case with an escaped underscore on every selection; `batch_text`'s docstring says it emulates only backslash doubling (O13-N1) | `fdbe661` |
| S13-6 | P3 | — | **Fixed now** (in hand): the README describes the catalogue as the repository's, and databases per database. The generator's own header is a backlog row | `a19c037` (test), `16521d0` |
| O13-2, S13-9 | P3 | — | **Fixed now**: the round 12 record says what each review found of the stopgaps at `9fe11377`; S12-1 and O12-1 keep their own ratings; owner question 13 (and 14) use WS5's narrowed wording | this file |
| O13-1, S13-7 | P3 | 5 | **Fixed now** (faithfulness): WS5's "decided elsewhere" summarises slice 3's rule (corrected in round 14: a summary, not exact, with the omissions S14-8 and O14-N2 named now carried; U-3 refused without `--discard engine` and replaced only with it, U-4, U-5, the replacement rules [114-2A] [114-2B] [115-7] [115-W]); questions 1 and 4 say they apply it | the brief |
| S13-4, S13-8, O13-N2 to N4 | P3 | 5, 1 | **Workstream inputs**: WS5 the staleness cases, the teardown controls of rounds 6 to 9, the warning's noise, SQLite siblings, the O12-N2 credit; WS1 S8-5 | the briefs |
| O13-N1 | P3 | — | **Fixed now**, with S13-5 | `fdbe661` |

## Round 14: each finding's disposition, and the loop's close

These are the reviews of `ab6448de`: Sol (`S14-*`) and Opus (`O14-*`, with its notes `O14-N*`). Neither had a P1 or P2, so round 14 counts clean and **the loop closes at 2 of 2** (rounds 13 and 14). The in-hand P3s were applied as one set of commits (`a06eea3` tests, `05f663d` fixes), which WS1's first review round also reviews.

| ID | Sev. | Area | Disposition | Commit or brief |
|---|---|---|---|---|
| S14-1, O14-N1 | P3 | — | **Fixed**: MySQL's probes need the operation's own refusal, 1142 or 1370, and reject 1045, 1044 and others. Run natively | `a06eea3`, `05f663d` |
| S14-2 | P3 | — | **Fixed**: both probe fakes answer only SQL naming the real fixtures, so a wrong column or routine fails | `a06eea3` |
| S14-3, O14-N3 | P3 | — | **Fixed**: a native guard runs a value with an escaped underscore through `query()` in both modes. The earlier reversal covered the direct parity path; this one covers library mode | `05f663d` |
| S14-4 | P3 | 5 | **Fixed**: the help test needs exit 0 and stdout, and checks `clean`'s `--all` option. The listing names the working data; each command's own help names the kept SQLite volume | `a06eea3` |
| S14-5, O14-2 | P3 | — | **Fixed**: the landing page's PostgreSQL note and the README explain the shared database, under a test that needs the explanations; the registry paragraph says live datasets carry a verified snapshot | `a06eea3`, `05f663d` |
| S14-6 | P3 | — | **Fixed**: accounts may not take the PostgreSQL service's roles (closing round 1's F20 for `megasamples_read`) | `a06eea3`, `05f663d` |
| O14-1 | P3 | 5 | **Input**: U-5 does not govern `status clean`; WS5 question 4 and owner question 14 restated | WS5 |
| O14-N2, S14-8 | P3 | 5 | **Input**: the "decided elsewhere" section's omissions carried; it now says it summarises | WS5 |
| S14-7 | P3 | 5 | **Input**: S12-3's and S12-5's own cases | WS5 |

## Round 8: the class check for overwritten evidence

The question: did any version 1 change overwrite an evidence file, or make one untrue? Two comparisons were made:
- **Against `e61335f`**, `main`'s merge of PR #16. No file under `docs/` or any record in `tests/` that `e61335f` has was modified or deleted since. The files changed since are code, tests, `README.md`, `ARCHITECTURE.md`, `.env.example`, `.dockerignore`, `pyproject.toml` and `uv.lock` (Opus round 9, N1: the last two were missing here). None is an evidence file.
- **Against PR #14's head, `2879fc472ad1`**, from which this branch carries PR #14's evidence. The commits after it that are in neither `e61335f` nor PR #14 changed:
  - **Evidence files:** `strict-read-executable-routines.{json,md}` and `strict-read-inventory.py`, by `644d949`. These were restored in `66bda86`.
  - **Living documents and code:** twelve files the canary receipt hashed. They are the strict-read guide, `.dockerignore`, and the PostgreSQL Dockerfile, read profile and routine names. Also the read_policy extension's SQL, C and control files, both image tests, the MySQL image startup test, and the native suite. Their receipt hashes describe `2879fc472ad1`. The read-profile record and the guide say so, and `tests/test_v1_public_routines.py` names the twelve and requires every other file the receipt hashed to match it.
  - **v1's own records and design:** the design, the briefs, the gates document, the loop and review records, and `dl-077-v1-public-routines.json`. Their changes are this branch's own.
- **Other evidence pages** that differ from PR #14's head: `credential-prerequisite-evidence.md`, `live-upgrade-runbook.md` and `lts-upgrade-evidence.md`. Each came from `main`'s merges, not from a version 1 commit.

The result: `644d949` was the only overwrite.

## Round 7's runs

No large container batch was run: DataIntent's gateway `--all` comes first, and any batch is cleared with the coordinator. The container runs were focused PostgreSQL tests, one container at a time, on `ce3b539fb522` (`chinook`) and `cf7325f4f9be` (`chinook employees pubs`), built from `ae61776`. Logs are under `build/dl114-r1-work/`.

**Passed**
- **The health tests:** 3 passed. Only `demo` and `postgres` may call the report, over every role and every connectable database.
  - Reversal: on round 5's image, `admin,demo,postgres`.
- **The restore matrix and the real reset**, with the report's rights in every restored database (`policy-r7-restore.log`).
- **The start suite** (`start-r7-start.log`).
  - Reversal of the new key probe: on the trusted loopback it fails (`start-r7-probe-reversal.log`).
- **The inventory generator** on `cf7325f4f9be`: 1,667 signatures, identical in 6 databases (11:22:17).
- **The documentation guard tests.**

**Failed**
- **The full suite (host only, no container):** 2 failed, 1,080 passed, 313 skipped (`pytest-r7.log`, 11:29:41). These are the two baseline failures named in round 6's record.

**Not run**
- The MySQL suites and images, and the TCP copy suite. Round 7 changed no MySQL or copy code.

## Round 7: restoration and isolation

- **Retained isolated stack.** The fingerprint ledgers (phase `r7-final`) are byte-identical to build 1's `after` ledgers:
  - PostgreSQL `ee0f1a8b…711e`;
  - MySQL `a5c0466a…a72f`;
  - SQLite `5b0c2768…da98`.
- **Removed:**
  - every task container this round started;
  - 16 anonymous volumes, each checked unused. They came from the start suite's override probes, whose removal now takes their volume (the class of S7-9). A later start run left the count unchanged.
- **Kept:**
  - the ACL images;
  - the round 5 candidates;
  - the fault images;
  - the runner.
- **The isolated socket service** is stopped.
- **Isolation** (`build/dl114-r1-work/isolation-check.sh`, read-only):
  - **Live deployment:** the nine live `megasamples-*` entries are unchanged.
  - **Isolated store:** the same 20 containers.

## Round 8's runs

No large container batch was run: DataIntent's gateway `--all` comes first, and any batch is cleared with the coordinator. The container runs were focused, one container at a time, on `cf7325f4f9be` and `ce3b539fb522` (PostgreSQL, built from `ae61776`; no PostgreSQL engine file changed since) and `87dd365119ac` (MySQL). Logs are under `build/dl114-r1-work/`.

**Passed**
- **The v1 inventory generator** on `cf7325f4f9be`: 1,667 signatures, identical in 6 databases (11:57:55, `inventory-r8c.log`).
- **The native PostgreSQL suite:** 52 passed, 3 deselected (`native-r8-pg-full.log`). The new inventory test passed in all 6 databases; its reversal (the inventory without `megasamples_policy_loaded()`) failed in all 6.
- **The start suite** on `ce3b539fb522`: 3 tests OK, the store's 37 volumes unchanged (`start-r8-start.log`). Reversal: with anonymous probe volumes and `rm -f`, the teardown failed with "store volume count 37 before, 45 after" (`start-r8-scope-reversal.log`). The 8 volumes were checked unused and removed.
- **MySQL's lexical rules on a server** (`87dd365119ac`, the client sending comments): `SELECT 1--1` is 2; `--` before a space, tab, CR or `\x01` is a comment; `#` is a comment; `/*! */` and `/*!50001 */` are code; `x$y` and `ésource` are identifiers; backslash escapes and doubled quotes hold (`mysql-lexer-r8.log`, `mysql-lexer-r8b.log`).
- **Host tests:** inventory 9, tokenizer 26, cleanup scope 11, documentation 10, each with its reversals as recorded in the commits.

**Failed**
- **The host-only full suite:** 2 failed, 1,126 passed, 344 skipped (`pytest-r8.log`, 12:11:09). These are the two baseline failures: `test_quiescence_gate`'s unrelated holder and `test_rollback_preparation`'s whole rollback.
- **Setup, before the green runs:** the generator refused twice because its manifest was not private (exit 1, nothing written). The first native run of the new test failed in all 6 databases on an ambiguous `text || "char"` in its own query; the query was corrected before the green run.

**Not run**
- The MySQL suites and images, and the TCP copy suite. The tokenizer change (`megasamples/mysql_templates.py`) is exercised natively only by the MySQL copy suite. **That needs a large batch, cleared with the coordinator first.**
- The health, policy and restore suites, and PostgreSQL's `test-image`: no PostgreSQL image, policy or reset code changed.
- **Corrected in round 9 (Sol 6):** the MySQL image does change. Its Dockerfile copies `megasamples/mysql_templates.py`, and `mysql_template_build.py` uses the tokenizer to bake the `_start` schemas. So MySQL's image build and `test-image` must rerun, with the copy suite, in the MySQL batch.

## Round 8: restoration and isolation

- **Retained isolated stack.** The fingerprint ledgers (phase `r8-final`, 12:11:46 to 12:17:16) are byte-identical to build 1's `after` ledgers: PostgreSQL `ee0f1a8b…711e`, MySQL `a5c0466a…a72f`, SQLite `5b0c2768…da98`.
- **Removed:** every task container this round started, and the 8 volumes of the planted leak. The isolated socket service is stopped.
- **Isolation** (`isolation-check.sh`, read-only): the nine live `megasamples-*` entries are unchanged by ID, state and health, and the three live engines by ID, start time and image. The isolated store holds the same 20 containers as at the session's start, and the same 37 volumes as at round 7's end.
- **Git:** two unpushed commits were amended before the push: one to remove files staged by mistake, one to correct its message. No pushed commit was changed.

## Round 9's runs

Round 9's focused runs, before the batch:
- **The native inventory checks** on `cf7325f4f9be`: 7 passed (`native-r9-pg-inventory-green.log`). Their planted controls failed: a wrong database, 1 failed; a renamed routine, 6 failed.
- **The start suite** on `ce3b539fb522`: 3 tests OK, the store's 37 volumes unchanged (`start-r9-start.log`).
- **MySQL's lexical rules on a server** for round 9's cases (`mysql-lexer-r9.log`).
- **The host-only full suite** (Failed): 2 failed, 1,141 passed, 345 skipped (`pytest-r9.log`). These are the two baseline failures.

## The MySQL batch, round 9

On the coordinator's go, after DataIntent's gateway `--all` ended at 13:07 UTC. It ran from `4bb6616` with a clean tree, 13:16:23 to 13:19:53 UTC, one run at a time, each waiting for at least 15 GiB available (`build/dl114-r1-work/batch-r9.sh`, `batch-r9.log`).

**Passed**
- **Both MySQL images rebuilt:** binary log on `58d4b695a90c`, off `b3d6d569ed6d`. The template bake step ran afresh, with the changed tokenizer; the off build reused the on build's fresh builder layers.
- **`test-image`** (`chinook adventureworks_lt oracle_hr sakila`): 0 failures in each mode.
- **The native MySQL suite:** 7 passed in each mode.
- **The TCP copy suite:** 32 passed, 3 skipped in each mode. That includes the replayed procedure with `1--1` and a comment before the dot, read from the copy.
- **The reversal:** with round 8's tokenizer planted in the working tree, the lifecycle test failed at `CALL read_lexed()` with "SELECT command denied to user 'copier' … for table 'parent'". The copy's program still named `sample_start`, the case the finding describes. The tokenizer was restored (`git status` clean).

**Found by the batch** (fixed before round 10; see below). `megasamples test-image` removes its containers with `docker rm -f`, without `-v`. So each MySQL run left the image's anonymous data volume behind: 4 this batch, checked unused and removed. It is the S7-9 class in product code: `megasamples/engines/mysql/image_test.py` and 17 such calls across `megasamples/`, unchanged since `e61335f`.

## Round 9: restoration and isolation

- **Retained isolated stack.** The fingerprint ledgers (phase `r9-final`, 13:20:45 to 13:26:29) are byte-identical to build 1's `after` ledgers: PostgreSQL `ee0f1a8b…711e`, MySQL `a5c0466a…a72f`, SQLite `5b0c2768…da98`.
- **Removed:** every task container the batch started, and the 4 anonymous volumes `test-image` left. The socket service is stopped.
- **Kept for review:** the round 9 MySQL images.
- **Isolation** (`isolation-check.sh`, read-only): the nine live `megasamples-*` entries are unchanged, and so are the three live engines by ID, start time and image. The isolated store holds the same 20 containers as at the session's start, and the same 37 volumes as at round 7's end.

## The batch's finding: container removals leaving anonymous volumes

**Fix now**, the coordinator's decision: a defect found in use under `review-and-fix.md`. It is realistic, since any user running `test-image` hits it; it is cheap and in hand; and it lies outside the four areas.

**The class, as first recorded (corrected in round 10 below):** the 20 direct `docker rm` calls in `megasamples/`; 3 already used `-v` (`reset.py`, and the PostgreSQL image test's two later removals). Each of the other 17 was decided:

| Removal | Container | Decision |
|---|---|---|
| `audit.py` (2) | the image audit's MySQL container | `-v` |
| `engines/mysql/image_test.py` (3) | the image test's containers | `-v` |
| `engines/mysql/server.py` (2) | the build server; dumps go to a bind mount | `-v` |
| `engines/postgres/image_test.py` (1) | the image test's first removal | `-v` |
| `engines/postgres/server.py` (2) | the build server; output to a bind mount | `-v` |
| `engines/sqlite/image_test.py` (2) | the image test's containers | `-v` |
| `sources/mssql.py` (2) | the MSSQL source container; bind mounts only | `-v` |
| `sources/verify_oracle.py` (2) | the Oracle verifier's container | `-v` |
| `workspace.py` `clean` (1) | the transient (labeled) containers | `-v` |

**Why none keeps its volumes:** once a container is removed, no later `docker run` reattaches its anonymous volumes, so leaving them keeps nothing reachable. `-v` removes anonymous volumes only. Bind mounts and named volumes stay, so data that must persist is not affected. `tests/test_v1_container_removal.py` read every `docker rm` in `megasamples/` and required `-v`. **Round 10 (Opus P2-1) found the record incomplete:** the class also holds the Compose routes that remove or replace containers, `megasamples down`, `status clean --all`, `up`'s stale-image recreate (all leaking each engine's data volume) and `reset_engines` (which removed by name already). With them the class is 23 direct removal calls (the exemption included) and four Compose calls that remove or renew containers (Sol round 11, 10; it said 24 sites). The `--rm` launches are removals too and take their anonymous volumes (Opus round 11, N2); they are named in WS5. The test now reads the syntax tree, and one exemption is listed, `workspace.remove_unlabelled` (Opus round 10, N2).

**Commits:** `5bf374e` (test), then `53a2d1e` (the fix).

**Runs** (focused, one at a time, each with the 15 GiB check; volume sets compared by `build/dl114-r1-work/image-test-volumes.sh`):
- **Red:** the class test found 17. One MySQL `test-image` run (binary log on, `58d4b695a90c`) added 2 volumes, with 0 test failures.
- **Green:** the class test, 2 passed. `test-image` with the store's volume set unchanged, 0 failures each, on MySQL with the binary log on (`58d4b695a90c`), with it off (`b3d6d569ed6d`), and on PostgreSQL (`ce3b539fb522`).
- **Reversal:** the MySQL image test's old removals added 2 volumes again. `workspace.py`'s old removal alone fails the class test.
- **Host full suite** (Failed): 2 failed (the two baselines), 1,143 passed, 345 skipped (`pytest-r10.log`).
- **Not run:** SQLite's `test-image`, the MSSQL and Oracle verifiers, the build servers and `workspace clean`. They are covered by the class test only.

**Restoration and isolation:** the 4 volumes of the red and reversal runs were checked unused and removed, so the store's volume set is the same 37 as before. The socket service is stopped. `isolation-check.sh` passed: the live entries are unchanged, and the store has the same 20 containers. The retained stack was not touched after the batch's fingerprint proof (13:20 to 13:26 UTC), so it was not fingerprinted again.

## Round 10's runs

Focused runs, one at a time, each with the 15 GiB check, while DataIntent's `test-changes` lane was the host's large run.

**Passed**
- **The real Compose cycle** (`build/dl114-r1-work/cycle-r10/`, `driver.py`), on a project of its own, `dl114-r10-cycle`. It used the policy-free PostgreSQL image (`localhost/sql-megasamples-postgres:dev`, which declares `/var/lib/postgresql`) with a named volume beside it. The isolated store's `megasamples-upgrade` project was never addressed.
  - Through `data_volumes`, two down/up cycles, a renewed recreate and a final down left only the named volume.
  - With round 9's plain commands, the same sequence left 4 anonymous volumes. That is the native red and reversal.
  - All 5 volumes were checked unused and removed. The store is at its 37 again.
- **The native publication checks** on `cf7325f4f9be`:
  - an ordinary run, 6 passed, 1 skipped;
  - a qualifying run, 7 passed;
  - the selection case: round 9's test failed it (1 failed); this one passes it, and fails it only when qualifying (2 failed).
- **Host tests:** override 4, the Compose routes 4, the removal class 26 (`tests/test_v1_container_removal.py` at `5a75c23`; it said 27), the cleanup scope 16, tokenizer 37, inventory 9, documentation 10. Their reds and reversals are in the commits.

**Failed**
- **The host-only full suite, first run:** 7 failed. `a27880a` had broken five existing image-test fakes; it was committed without a full run. Fixed in `c4745ba`, which records it: nine commits came between them, so it is the tenth after `a27880a`.
- **The host-only full suite, final run:** 2 failed, the two baselines; 1,176 passed, 345 skipped (`pytest-r11.log`).

**Not run**
- A real `make up` of the product stack. It would address the isolated store's own `megasamples-*` containers, which this task keeps unchanged. The cycle above runs the same helpers on a project of its own.
- The other routes the class test covers: `clean --all`, SQLite's `test-image`, the verifiers and the build servers.
- The MySQL batch. No MySQL code changed this round outside the image test's override function, which the fakes cover. A `test-image` run would exercise it natively; it is queued for the coordinator's next batch.

## Round 10: restoration and isolation

- **Isolation** (`isolation-check.sh`, read-only): the nine live `megasamples-*` entries and the three live engines are unchanged. The isolated store holds the same 20 containers as at the session's start, and the same 37 volumes as at round 7's end. The cycle's project left no container, network or volume.
- **The retained stack** was not addressed this round, so it was not fingerprinted again. Its last proof is round 9's, 13:20 to 13:26 UTC.
- **The socket service** is stopped.

## Round 11's runs

These were focused runs, one at a time, each after the 15 GiB check.

**Passed**
- **The native suite on a real subset:**
  - Red: `ce3b539fb522` (chinook only) with a chinook configuration and round 10's suite failed 2, the employee views and parity on `pubs` (`native-r11-pg-subset-red.log`).
  - Green: the same image passed 36 and skipped 2; the full candidate `cf7325f4f9be` passed 53 and skipped 1.
  - Reversal: a chinook configuration against the full image fails the selection test.
- **Compose's resolution with a real `.env`** (`config-r11/`, a synthetic `.env` holding only an image name): with the override in `.env`, `published-mysql:9.7`; without it, `sql-megasamples-mysql:dev`.
- **Host tests:**
  - the Compose routes, with the failure rows and the `.env` row: 9, at `36c7b0f`;
  - the Compose routes (then 8), `test_reset` and the class test: 70, at `2482eaf`, before the `.env` row was added;
  - documentation: 11, at `d1151a1`.
  - The reds and reversals are in the commits.

**Failed**
- **The host-only full suite:** 2 failed, the two baselines; 1,182 passed, 347 skipped (`pytest-r12.log`).

**Not run**
- A real recreate whose `--wait` fails. Only the fake models it. It is WS5's real-cycle row.

## Round 11: restoration and isolation

- **Isolation** (`isolation-check.sh`, read-only): the live entries and the three live engines are unchanged. The isolated store holds the same 20 containers and 37 volumes.
- **Every task container** this round started is removed. The socket service is stopped.
- **The retained stack** was not addressed this round. Its last proof is round 9's.

## Round 12's runs

These were focused runs, one at a time, each after the 15 GiB check. Each names the revision it ran.

**Passed**
- **The selection check, natively:** PostgreSQL on `cf7325f4f9be` and MySQL on `58d4b695a90c` (its first native run, as `root`), each 1 passed, at `a10d1eb`. Neither image carries an append dataset; the host table covers that case.
- **MySQL native, CLI and library mode,** on `58d4b695a90c`:
  - red, at `922ee62`: the CLI failed parity on `SHOW GRANTS` (1 failed, 7 passed); library mode failed 6, with 2 passed;
  - green, at `e6ed4ef`'s tree: 8 passed in each mode.
- **PostgreSQL `test-image`** on `ce3b539fb522` (chinook), at `8eb964b`'s tree: each write probe refused, 0 failures, the store's volume set unchanged.
- **Host tests,** each at its own commit as the commits record. The selection table, 6; the help and README, 12; the Compose routes, 11; the write probes, 7.

**Failed**
- **The host-only full suite,** at `c3a3acd` with this file's edits: 2 failed, the two baselines; 1,198 passed, 347 skipped (`pytest-r13.log`).

**Not run**
- An append-dataset image, natively.
- A real recreate whose `--wait` fails (WS5).

## Round 12: restoration and isolation

- **Isolation** (`isolation-check.sh`, read-only): the live entries and engines are unchanged. The store holds the same 20 containers and 37 volumes.
- **Every task container** this round started is removed. The socket service is stopped.
- **The retained stack** was not addressed. Its last proof is round 9's.

## Round 13's runs

These were focused runs, one at a time, each after the 15 GiB check. Each names its revision.

**Passed**
- **`test-image`, natively,** with the new write probes at `ba78dee`'s tree. MySQL on `58d4b695a90c` and PostgreSQL on `ce3b539fb522`: each probe refused, 0 failures, the store's volume set unchanged (`image-test-r13-*-write-probes.log`).
- **MySQL parity, natively,** at `fdbe661`'s tree, on `58d4b695a90c`.
  - Green: 1 passed.
  - Reversal: without the normalisation and without `SHOW GRANTS`, the fixed escaped-underscore case fails (1 failed).
- **Host tests,** each at its own commit as the commits record:
  - the write probes, 16, or 34 with the image-test host tests;
  - the rendered help and README, 14.

**Failed**
- **The host-only full suite,** at `16521d0` with this file's edits: 2 failed, the two baselines; 1,209 passed, 347 skipped (`pytest-r14.log`).

**Not run**
- A single-engine native run. It is WS4's input (S13-1).

## Round 13: restoration and isolation

- **Isolation** (`isolation-check.sh`, read-only): the live entries and engines are unchanged. The store holds the same 20 containers and 37 volumes.
- **Every task container** this round started is removed. The socket service is stopped.
- **The retained stack** was not addressed. Its last proof is round 9's.

## Round 14's runs

These were focused runs, one at a time, each after the 15 GiB check.

**Passed**
- **MySQL `test-image` with the per-operation refusals,** at `05f663d`'s tree, on `58d4b695a90c`: each probe refused by its own code, 0 failures, the store's volume set unchanged (`image-test-r14-mysql-write-probes.log`).
- **The library-mode guard, natively,** at `05f663d`'s tree. Green: 1 passed. Reversal: without `batch_text` in library mode, 1 failed.
- **Host tests:** 72 with the image-test host tests, at `05f663d`.

**Failed**
- **The host-only full suite,** at `05f663d` with this file's edits: 2 failed, the two baselines; 1,238 passed, 348 skipped (`pytest-r15.log`).

**Not run**
- PostgreSQL `test-image`: its probes are unchanged this round; only the fake changed.
- A single-engine native run: WS4.

## Round 14: restoration and isolation

- **Isolation** (`isolation-check.sh`, read-only): the live entries and engines are unchanged. The store holds the same 20 containers and 37 volumes.
- **Every task container** is removed. The socket service is stopped.
- **The retained stack** was not addressed. Its last proof is round 9's.

## After the loop

The owner questions are in `docs/design/dl077-v1-owner-questions.md`, an options paper for the two deciders (DL-104): each question with its facts, two to four options and their consequences, and a recommendation. The workstreams start after their answers, one at a time, each designed, built test-first, and reviewed to two clean rounds, before the merge (DL-101).

## The workstreams after the loop

They run one at a time, in the coordinator's order: WS1, WS4, WS2, WS3, WS5. Each is designed from its brief and DL-122, reviewed as a design by Sol and Opus, built test-first, and reviewed to two clean rounds.

| # | Workstream | State |
|---|---|---|
| 1 | Start certification | **Design revision 2**, `docs/design/dl077-ws1-start-certification-design.md`, answering the design review of `2ab72c25` (Sol 1 P1, 8 P2, 3 P3; Opus 4 P2, 15 P3), each finding traced in its section 11; waiting for the re-review. No build has started. |
| 4 | Native suite binding | waiting for WS1 |
| 2 | Orphan scan | waiting |
| 3 | Removal outcomes | waiting |
| 5 | Container and volume lifecycle (interim until slice 3) | waiting |
