# Workstream 1: PostgreSQL start certification

**Status:** brief, not yet built. The area went hot in review rounds 3, 4 and 5 (`tests/dl077-v1-loop.md`). This brief comes before any further patch. It covers what the PostgreSQL image checks before, during and after it lets a server accept connections.

## The rule to be designed whole

A server built from this image that accepts connections does so only:
- on the data directory the image certified, which is `PGDATA` carrying the read-policy marker;
- with `read_policy` loaded during preload;
- with any password overrides applied by a server that was itself certified.

Anything else is refused before any connection is accepted, or named in the README as an unchecked route whose only signal is the healthcheck.

## Invariants

- **I1. Same server.** Every launch the wrapper makes or hands over, whether the private password start or the public start, uses the directory and preload list it certified. Each is read from that launch's own arguments, files and environment.
- **I2. Certified before accepting.** No launch accepts a connection, on a socket or over TCP, before I1 holds for it.
- **I3. Private means private.** The password setup reaches the server it started, by a socket only it and `postgres` can use, and stops that server on every exit path.
- **I4. Refusal is visible, and a failure leaves a stated state.** A refusal exits non-zero, before any password change or catalog write, and logs one line saying which rule refused. A failure after a password change (passfile write, handover, public start) leaves a state the README states: which keys are then in force, and that no server listens.
- **I5. What is unchecked is stated.** A route the wrapper cannot see is named in the README together with its signal:
  - an entrypoint replaced;
  - a wrapping command;
  - a library planted through `dynamic_library_path`.
- **I6. Health tells the truth without noise.** The healthcheck passes only when the preloaded library is in the serving process, and a healthy probe logs nothing at ERROR. Round 5 built this; the workstream keeps it.

## Decision table

These are the facts behaviour depends on. The design fills in the outcome of every row, and the test plan exercises every row.

| Fact | Values |
|---|---|
| A. Who starts | root; postgres (`--user`); another uid |
| B. Command form | `postgres`; this image's postgres by path; another binary named `postgres`; a wrapping command (`gosu …`, `sh -c …`); `-*` options only; the server's other modes given by the user (`--single`, `--check`, `-C`, `--version`, `--describe-config`) |
| C. Data directory source | `PGDATA` only; `-D` or `--pgdata`; `-c data_directory` (any case or spelling); `config_file` naming another file; `include` directives |
| D. Preload source | the baked `postgresql.conf`; `postgresql.auto.conf` (`ALTER SYSTEM`); `-c` on the command line; an included file |
| E. Preload value | contains `read_policy` alone; with other libraries (one that replaces `ProcessUtility_hook` without chaining it); lacks it; quoted entries; empty |
| E2. Library resolution | `$libdir/read_policy`; another `read_policy` reached by `dynamic_library_path` |
| F. Password overrides | none; some; all |
| G. Socket settings | default; custom `unix_socket_directories` (persisted or on the command line); `listen_addresses` |
| H. Volume | marked by this build, owned by postgres; marked, other owner; **marked by another build of this image** (same marker `1`, a different extension script). Two earlier builds differ: one before the loaded report (before `2c9b106`, rounds 1 to 4), whose healthcheck call fails; and one with the report but before `admin`'s revoke (`2c9b106` to before `ae61776`, round 5's candidates from `8102f35`), where `admin` can call it; unmarked (pre-policy); `PG_VERSION` missing |
| I. Entrypoint | the image's; replaced (`--entrypoint`) |
| J. The client the wrapper runs | effective user; the socket it reaches; the authentication it gets |
| K. `/run` | writable by the wrapper's user; not (non-root) |
| L. Each password change | applied and confirmed; refused; applied but its reply lost (the server changed the key, the wrapper did not see it); the connection lost mid-way (some keys changed, some not) |
| M. Where the healthcheck is defined | the generated Compose file; none (a hand-run container); an image `HEALTHCHECK` (not today) |

Required outcomes to decide, row by row:
- **start** with the hook;
- **refuse**, naming the rule;
- **unchecked and stated**;
- a **failed public start** after certification (the port does not bind, or the server exits): what the container reports, and what it leaves behind (Sol round 7, 1);
- an **informational exit**: a server mode given by the user (fact B) that exits 0 without a listener, and whether that counts as a start (Sol round 7, 1).

For example:
- A=root, B=path to own postgres, C=`PGDATA`, D=auto.conf lacking `read_policy`, F=some, G=custom socket → refuse (I1). If D is corrected on the command line, the private start must still be refused or be made to use the same arguments.
- A=postgres (non-root), F=some → decide: refuse before any launch (Sol round 5, P3-7), or support non-root starts by moving the health passfile.

## Inputs: every finding so far

| Round | Finding | Gist | Disposition so far |
|---|---|---|---|
| 1 | S3 (hook review) | pre-policy volume starts without the policy | fixed: marker |
| 2 | S2-2 | `-D` points the server at another directory | fixed by literal parsing (superseded) |
| 3 | S3-1, O3-1 | literal parsing bypassed (case, path form); the preload list replaced (`-c`, `ALTER SYSTEM`) | fixed: ask the server with `-C`, `read_policy.loaded` |
| 4 | S4-1 | the private password start ran on files alone | fixed: both launches certified |
| 4 | S4-7 | quoted preload entry split on commas | fixed: refused |
| 4 | O4-1 | path form, non-root | reconciled; root path form runs by name |
| 4 | O4-4 | refusals undocumented; ownership repair | fixed: README, repair before check |
| 4 | S4-6, O4-2 | healthcheck placeholder | fixed; replaced in round 5 |
| 5 | Sol P2-3 | the private start may listen on a custom socket that `psql` does not reach; it is not stopped on failure | **input** |
| 5 | Sol P3-7 | a non-root start runs the private start before failing | **input** |
| 5 | Opus P3-3 | the README's non-root sentence | stopgap: wording corrected |
| 5 | Opus P3-4 | bypass routes not stated | stopgap: one README sentence |
| 5 | Sol P2-6, Opus P3-2 | healthcheck ERROR every probe | fixed outside the workstream |
| 6 | Sol P2-5 | failures after a password change are outside the plan | **input** (I4, facts J–L, question 9) |
| 6 | Sol P2-6, Opus 1 | the start suite's shared volume and trusted-loopback probe masked the path-form check | fixed in the tests; the plan requires a fresh volume per row |
| 6 | Opus 4 | facts missing: another build's volume, healthcheck location, `dynamic_library_path`, other libraries, server modes | **input** (facts B, E, E2, H, M; questions 7, 8, 10, 11) |
| 6 | Opus P3-2 | the extension script changed without a version or marker bump | **input** (question 7) |
| 7 | Opus 1 | the test plan asks for every combination of 14 facts on real targets, with no rule for which count | **input**: state the coverage criterion (precedence that makes later facts moot; the full product in a cheap model under shimmed `postgres -C` and `pg_ctl`; real targets for each value against a base row and for named interactions; impossible combinations with reasons) |
| 7 | Sol 1 | no outcome for a failed public start (the port does not bind) or for an informational command that exits 0 without a listener; a confirmed password change versus one whose reply was lost; each role's key and the passfile after each failure | **input**: carried as fact L's applied-but-reply-lost value and the two outcomes above (a failed public start, an informational exit); each role's key and the passfile after each failure are question 9 |
| 7 | Opus P3-4 | question 6 is missing from the owner list | **input**: question 6 is an owner decision |
| 7 | Sol P3-8 (S7-8), Opus P3-3 (O7-P3-3) | the start suite's assertions accepted any failed command as a refusal, and its listener checks could not tell a public server from the private start | fixed in the tests (`6ed9e2b`): a key refusal must be exit 2 with scram's message, so a failed exec or connection does not pass; the listener-log assertions witness the public server only, as the private start logs to `/dev/null`; the namespace check has a positive control; the probe's reversal (the trusted-loopback probe fails "the probe did not reach scram authentication") is recorded. **Input**: the design keeps these controls |
| 7 | Sol P3-7, Opus P3-7 | retained volumes from round 5 or 6 images keep `admin`'s EXECUTE or lack the routine, under marker `1` | **input** (question 7) |
| 8 | Opus P3-3 | the round 7 Sol 1 row said question 9 covered the passfile, and the facts and outcomes lacked its inputs | **input**: carried in fact L, the required outcomes and question 9 |
| 8 | Sol P3-6 | fact H said round 5's image lacked the loaded report; its build includes the report and lacks `admin`'s revoke | **input**: fact H names the pre-report and pre-revoke builds separately |
| 12 | Sol 8 | the round 7 start-probe findings were not in this table | **input**: the S7-8 and O7-P3-3 row above |
| 8 | Sol P3-5 (S8-5) | the namespace assertion accepted a duplicate-name error that names the database | fixed in the tests (`a4f430e`, `f23ec19`): SQLSTATE `42501` with the hook's own message, and fresh names for both attempts; **input**: the design keeps the control |
| 13 | Sol 8 | S8-5 was not in this table | **input**: the row above |

## Questions the design must answer

**Owner decisions in this brief:** questions 1, 2, 6, 7, 8 and 9.

1. Is the private password start kept at all, or are passwords applied another way (for example by the public server's first boot, before it listens)? **Owner decision:** it changes when a credential takes effect.
   - **Answered, DL-122 Q1:** Keep the private password start, made exact. With overrides set, an argument that would move the socket or data directory is refused before any launch.
2. Are non-root starts supported (move the health passfile), or refused before any launch? **Owner decision:** it is a supported-deployment question.
   - **Answered, DL-122 Q2:** Non-root starts are refused before any launch, as the wrapper's first check; the README says platforms that force a non-root user are unsupported in version 1.
3. Does the private start take the public launch's arguments verbatim, with an image-chosen socket directory, or is any argument that changes sockets or data refused when overrides are set?
4. Which unchecked routes are stated, and which are refused because they are detectable? A wrapping command whose argv contains this image's postgres could be refused.
5. Is the `PG_VERSION`-missing path (upstream `initdb`) refused explicitly?
6. What exactly does the one-line refusal say for each rule, and is it a stable code a supervisor can match? **Owner decision** once it is a supervisor-facing contract (Sol round 6, P2-5).
   - **Answered, DL-122 Q3:** Each start refusal carries a stable code in its line, exit 1 kept. Tokens are fixed at the freeze; additions are allowed; a matcher treats an unknown code as a refusal.
7. **Owner decision, an on-disk format:** how the read-policy marker and the extension's version are bumped and migrated for retained volumes. Today the marker stays `1` while the version-1 script changed in round 5, so a volume from an earlier build certifies and then fails every probe (Opus round 6, 4; P3-2).
   - **Answered, DL-122 Q4:** Bump the marker and the extension to 2 before the freeze, and both on any later script or grant change. Before either server starts, refuse any marker but the image's exact own (newer, older or unrecognised), keep the volume, and name the upgrade route. A test pins a digest of the extension script and its grants to the marker and version.
8. **Owner decision:** whether the image carries its own `HEALTHCHECK`, so a hand-run container has the signal too (Opus round 6, 4; Sol round 6, P3-9).
   - **Answered, DL-122 Q5:** The PostgreSQL image carries its own HEALTHCHECK, from one source shared with Compose; a test checks it survives the Podman build format; the README notes orchestrators that ignore it.
9. **Owner decision:** what a failed start may leave behind. That is the keys in force after a failure that follows a password change, each role's key and the health passfile after each failure, a change whose reply was lost, and whether such a failure must roll the change back (Sol round 6, P2-5; Sol round 7, 1).
   - **Answered, DL-122 Q6:** Applied keys stay as applied. The log reports each requested role, by name only, as confirmed applied, confirmed refusal, unattempted or uncertain. A stale or partial health passfile is never usable after a failure. A retry with the same keys converges.
10. Is a later preload library that replaces the utility hook without chaining detectable (for example, the report checks that the hook is still installed), or is it a stated limit?
11. Is a library reached through `dynamic_library_path` detected by the report? Opus's reading says it is, because the call loads `$libdir/read_policy` and answers false. That must be confirmed by test, and then moved from stated to detected.

**Also recorded in DL-122:** WS1 states which refusal appears first when both the marker and slice 3's build identity mismatch (one message per cause); whether the MySQL image gets the same `HEALTHCHECK`, or the README states the difference; and the contract at merge to `main` (the refusal codes, the format pair) recorded with consumer impact notes, conformance tests and the unknown-value rule.

## Test plan

- **A fresh volume per row,** and a row whose outcome is a credential checks keys over password-authenticated TCP, never the image's trusted loopback. Round 6 showed both maskings in the round 4 suite.
- **A table test over every row of the decision table:** a real container per row, the outcome asserted. A start must accept connections with `megasamples_policy_loaded()` true and the namespace owner's out-of-namespace `CREATE DATABASE` refused. A refusal must exit before any password change, checked by the old key still working. An unchecked route must be named in the README.
  - The rows are generated from the facts, so a new fact adds rows, not one case.
- **Fault planting at each step of the wrapper:**
  - the ownership repair;
  - the `-C` reads failing;
  - the marker read;
  - the private start failing to start;
  - the password SQL failing, and failing after some keys changed;
  - the private stop failing;
  - the health passfile write;
  - the handover `exec`.

  After each, no server remains and the exit is non-zero.
- **The private socket:** a custom persisted `unix_socket_directories`, with an assertion that the password change landed on the private server and that nothing listened on the custom socket.
- **Reversals:** each rule removed in turn fails at least one row.
