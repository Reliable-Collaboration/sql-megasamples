# Version 1, slices 1 and 2: review loop status

This is the loop over `feature/dl-077-v1`, run under DL-114, DL-120 and RCC.DataIntent's `knowledge/governance/review-and-fix.md`. The per-round triage records are `tests/dl077-v1-review-{1,2,3,4}.md`. The dispositions of rounds 5 to 9 are below.

## Stop count

**1 of 2.** Round 9 had no P1 or P2, so it counts clean, the coordinator's decision. Rounds 6, 7 and 8 had kept the count at 0. The loop ends after two rounds in a row with nothing to fix now outside the workstreams.

**Scope from round 8, the coordinator's decision:** a workstream brief is an input to that workstream's own design, which is reviewed in its own loop after this one ends. So findings about a brief's content are recorded there as that workstream's inputs, not fixed now here. That covers its facts, its test plan's coverage and its questions.

This loop judges two things:
- what lies outside the four areas: code, tests, documentation and records;
- whether each brief carries every input faithfully.

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
| Configuration checks only at image build; the account name `megasamples_read` accepted | round 1, F20 | Start paths are slice 3+. |
| Declared MySQL writers' grants are baked before slice 3's suspension | round 1, F21 | Slice 2 does not merge without slice 3. |
| Ownership transfer after creation; `DROP OWNED` and provisioned defaults | round 1, S6 and S7 | The rules are as specified. |
| Range-type constructors keep `PUBLIC EXECUTE` | round 2, F2-8 | A stated limit: immutable built-in code. |
| MySQL `character_set_client` and `collation_connection` not restored | round 3, O3-4 | A stated limit in design 2.4. |
| The H-3 probe's client-only accounting has no reversal | round 4, S4-9 | A recorded limit of the control. |
| `test_quiescence_gate` unrelated-holder case fails, also at `e61335f` | rounds 1–5 | A baseline failure; its cause is not isolated. |
| MySQL `/*+ */` optimizer hints are treated as comments, so a schema name inside one is not rewritten | round 8, S8-8's class check | Not checked on a server. A hint names tables and query blocks, and no shipped template carries one. Reopens if a template does. |
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

## Owner questions, for the two deciders (DL-104) once the briefs pass review

| # | Workstream | Question |
|---|---|---|
| 1 | WS1 | Is the private password start kept, or are passwords applied another way? It changes when a credential takes effect. |
| 2 | WS1 | Are non-root starts supported (move the health passfile), or refused before any launch? |
| 3 | WS1 | Is each start refusal's one-line message a stable, supervisor-facing code? |
| 4 | WS1 | **On-disk format:** how are the read-policy marker and the extension's version bumped and migrated for retained volumes? |
| 5 | WS1 | Does the image carry its own `HEALTHCHECK`, so a hand-run container has the signal? |
| 6 | WS1 | What may a failed start leave behind after a password change, and must it roll the change back? |
| 7 | WS2 | Does `reset --status` exit non-zero when the scan is incomplete? |
| 8 | WS2 | Does `up` block or fail on an incomplete scan, and are partial warnings shown? |
| 9 | WS2 | Is an invalid database (an interrupted drop) reported, and how? |
| 10 | WS3 | What is the result field for an unsettled cleanup step: `ledger: unsettled`, or one that names the step? |
| 11 | WS3 | Is there a third per-copy outcome (unknown or partial), and a list for the copies a stopped sweep never reached? Any change to a public exit or to `removed`/`kept`. |
| 12 | WS4 | **Security posture:** may the suite authenticate to a listener it has not yet proved to be the checked instance? |

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
