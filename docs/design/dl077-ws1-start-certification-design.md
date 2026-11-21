# Workstream 1: PostgreSQL start certification, the design

**Status: design, for review by Sol and Opus before any build.**
- **From:** the brief, `dl077-ws1-start-certification.md` (its rule, invariants I1 to I6, facts A to M, and every input row), and DL-122's answers to its six owner questions (Q1 to Q6) with the items DL-122 recorded for WS1.
- **Next:** once reviewed, it is built test-first in the order of section 9, then reviewed to two clean rounds.
- **Scope:** the PostgreSQL image's wrapper (`engines/postgres/entrypoint-wrapper.sh`), its build (`engines/postgres/Dockerfile`), the `read_policy` extension's format, the healthcheck, the README's start section, and their tests. The MySQL image appears only in 7.3.

## 1. Decisions this design applies

| DL-122 | What the design does |
|---|---|
| Q1: keep the private start, made exact | 4.3 runs it on an image-chosen socket. 3.1 refuses, before any launch, an argument that would move the socket or the data directory when overrides are set (`override-argument`). |
| Q2: non-root refused first | Rule R2 is the wrapper's first check on a server command. The README states that platforms forcing a non-root user are unsupported in version 1. |
| Q3: a stable code per refusal | Every refusal line carries a code from section 5. The codes are fixed at the freeze, additions are allowed, and the README tells a matcher to treat an unknown code as a refusal. |
| Q4: format 2, exact match, a digest guard | Section 6: marker `2`, extension version `2`; any other marker is refused before either server starts; a guard test pins the digest. |
| Q5: an image `HEALTHCHECK` from one source | Section 7: one script, used by the image and by the generated Compose file; a test inspects the built image. |
| Q6: four per-role states, a passfile never stale | Section 4.4: each role is logged as `applied`, `refused`, `unattempted` or `uncertain`. Section 4.6: the passfile is removed first and written atomically last. |
| Recorded: one message per cause | 6.3: when the marker and slice 3's build identity both mismatch, only the marker refusal appears. |
| Recorded: the MySQL image | 7.3: it states the difference in the README for version 1. |
| Recorded: the contract at merge | Section 8 lists what is recorded, with impact notes and conformance tests. |

## 2. Commands: what counts as a server start

The wrapper first classifies its argument vector:

| Class | Recognised by | Outcome |
|---|---|---|
| **Server start** | `argv[1]` is `postgres` by name or this image's binary by path, or begins with `-` (the image's own default) | The checks of section 3, then section 4 |
| **Informational** | a server start whose options are only `--version`/`-V`, `--describe-config`, `--help`/`-?`, or `-C NAME` | R1 to R3, then run as `postgres` and exit with its status. No listener, no password change, no passfile. |
| **Server mode** | a server start with `--single`, `--boot` or `--check` | Refused, `server-mode`. These run SQL on the data without a listener and outside the start this image certifies. |
| **Wrapped server** | any later argument whose basename is `postgres`, or that resolves to this image's binary (for example `gosu postgres postgres`) | Refused, `wrapped-server` |
| **Other command** | anything else (`bash`, `psql`) | Handed to the upstream entrypoint unchanged. It starts no server from this image's checks. |

A server started inside a shell string (`sh -c "exec postgres"`) or behind a replaced entrypoint is not detectable. 7.2 states those routes and their signal.

## 3. The checks, in order

The checks run in this order. **The first that fails decides**, so each later fact matters only when every earlier check passed. That precedence is what makes the decision table of section 9 finite.

| # | Check | Fact | Refused with |
|---|---|---|---|
| R1 | The command is not a wrapped server | B | `wrapped-server` |
| R2 | The wrapper runs as root (uid 0) | A, K | `non-root` |
| R3 | `argv[1]` is this image's own `postgres` | B | `foreign-binary` |
| R4 | No server-mode option | B | `server-mode` |
| — | Informational commands stop here (section 2) | B | — |
| R5 | `PG_VERSION` exists in `PGDATA` | H | `uninitialised` (no upstream `initdb` on a megasamples volume) |
| — | **The stale health passfile is removed** (4.6) | — | — |
| — | The ownership repair, as the upstream entrypoint makes it, as root | H | — |
| R6 | The server can report its configuration (`postgres ARGS -C …` as `postgres`) | C, D | `config-unreadable` |
| R7 | The public launch's `data_directory` is `PGDATA` | C | `data-directory` |
| R8 | The marker is the image's own, exactly (section 6) | H | `policy-marker` |
| R9 | The public launch's preload list has no quoted entry | E | `preload-quoted` |
| R10 | It contains `read_policy` | D, E | `preload-missing` |
| R11 | `dynamic_library_path` is exactly `$libdir` | E2 | `library-path` |
| R12 | With overrides set: no argument names a socket or data location (`-k`, `-D`, `--pgdata`, and `-c` or `--` forms of `unix_socket_directories`, `data_directory`, `config_file` or `hba_file`, in any case) | F, C, G | `override-argument` |
| R13 | With overrides set: the private launch (no arguments) passes R6, R7 and R9 to R11 | F, C, D | the same codes |

**R11, new:**
- A `read_policy` planted in another directory on `dynamic_library_path` would load at preload, while the report function resolves `$libdir/read_policy`.
- The brief's question 11 expects the report to answer false in that case. 9.4 tests that.
- Refusing a non-default path closes the route before the server starts. It is cheap, and it costs nothing a version 1 deployment needs.

**Not refused, and stated** (the brief's question 10):
- **What:** a later preload library that replaces `ProcessUtility_hook` without chaining it.
- **Why it is stated, not refused:** a pointer comparison cannot tell replacing the hook from chaining it. Whoever can set `shared_preload_libraries` already controls the server, as the guide says ("not a sandbox against administrators").
- **Its signal:** the healthcheck does not see it.
- The README says so.

## 4. The start

### 4.1 Without overrides

After R1 to R11:
1. the passfile is written (4.6);
2. the wrapper hands over: `exec docker-entrypoint.sh postgres ARGS`.

The public server is the certified launch.

### 4.2 With overrides

The overrides are `POSTGRES_PASSWORD`, `DEMO_PASSWORD` and `ADMIN_PASSWORD`. After R1 to R13:
1. the private start (4.3);
2. the passwords (4.4);
3. the private stop (4.5);
4. the passfile (4.6);
5. the handover.

### 4.3 The private start: a socket only it uses

- **The socket directory:** `/run/megasamples-private`, created fresh by root, owned by `postgres`, mode 0700.
- **The launch:** `pg_ctl -D "$PGDATA" -w -o "-c listen_addresses='' -c unix_socket_directories=/run/megasamples-private" start`, as `postgres`.
  - The two `-c` options override anything the files persist, so a custom `unix_socket_directories` in `postgresql.auto.conf` cannot move it (Sol round 5, P2-3).
- **Its log:** `$PGDATA/megasamples-private-start.log`, owner-only. It is not `/dev/null`, so a failure can be diagnosed. On a successful handover it is removed.
- **The client:** `psql -h /run/megasamples-private`, as `postgres`. It reaches that socket and no other.
- **Stopping:** a `trap` on every exit path stops the private server (4.5).
- **Failure:** a failure to start is `private-start`. Nothing has changed.

### 4.4 The passwords, one role at a time

**Q6.** Each requested role is applied in its own `psql` call, one statement, `ON_ERROR_STOP`. The value goes to `psql` on standard input, never in argv or the log. The state the log records comes from what that call returned:

| The call returned | State | Meaning |
|---|---|---|
| exit 0 | `applied` | Confirmed: the role's key is the new one. |
| exit 3 (the server's ERROR) | `refused` | Confirmed: the server refused, and the key is unchanged. |
| exit 2 (the connection lost), exit 1 (`psql`'s own failure) or a signal | `uncertain` | The reply was lost or unseen, so the key may be either. |
| not run, because an earlier role failed | `unattempted` | Unchanged. |

- **The order** is fixed: `postgres`, `admin`, `demo`.
- **The first non-`applied` result stops the sequence.** The remaining roles are `unattempted`. Once anything is `uncertain`, nothing further is sent on a connection whose state is unknown.
- **The log:** one line per requested role, name and state only, for example `megasamples-start: password admin applied`.
- **After a failure,** the wrapper stops the private server and exits 1 with `password-setup`. No public listener ever starts.
- **The keys stay as applied** (Q6). A retry with the same `.env` converges:
  - an `applied` role's statement sets the same key again;
  - an `uncertain` role's statement settles it.
- **DL-110 [110-2]** is slice 3's start-path rule: every start names each account still on its published password, and keeps privileged accounts locked. When slice 3 builds it, it composes at this step, after the requested roles. WS1 neither builds nor contradicts it.

### 4.5 The private stop

`pg_ctl -m fast stop`, waited for.
- **If it fails:** `pg_ctl -m immediate stop`; if the postmaster still lives, `kill -KILL` its PID from `postmaster.pid`.
- Either way, exit 1 with `private-stop`, and no handover.
- The trap runs this on every exit after 4.3, including a signal.

### 4.6 The health passfile: never stale, never partial

- **Removed first,** after R5. So a container whose start fails at any later step leaves no passfile at all. That is the case of a restart of the same container, whose `/run` persists.
- **Written last,** after a successful 4.5, or after R11 when there are no overrides:
  - as root, to a temporary file in `/run`, mode 0600;
  - then moved into place.
- **If the write fails:** `health-passfile`, no handover.
- **What it holds:** `demo`'s current key: the override if one was applied, otherwise the published one.

### 4.7 The handover

`exec docker-entrypoint.sh postgres ARGS`, with the override variables unset.
- **A failed public start** (the port in use, the server exiting) is the server's own failure: its diagnostic, its exit, and no listener. It is not a wrapper refusal, and it has no code.
- **What it leaves:** the passfile holds the current key, so it is not stale; it is removed again on the next start.
- The README states this outcome (the brief's required outcome for a failed public start).

## 5. Refusal lines and codes

**The line format,** fixed at the freeze: `megasamples-start: refused: CODE: SENTENCE`, on stderr, then exit 1.
- **The sentence** says what was found and what to do. It may improve; the code may not change meaning.
- **Codes:** added, never renamed or removed, within version 1 (design section 6). The README tells a matcher to treat an unknown code as a refusal.

| Code | Rule | The sentence says |
|---|---|---|
| `wrapped-server` | R1 | the server must be the command, not wrapped |
| `non-root` | R2 | the wrapper must run as root inside the container; platforms that force a non-root user are unsupported in version 1 |
| `foreign-binary` | R3 | only this image's postgres runs |
| `server-mode` | R4 | single-user, bootstrap and check modes are not started by this image |
| `uninitialised` | R5 | the data directory has no cluster; this image starts only its own data |
| `config-unreadable` | R6 | the server could not report its configuration, with its first error line |
| `data-directory` | R7 | the data directory resolved, and that it is not `PGDATA` |
| `policy-marker` | R8 | the marker found (absent, or its value) and the image's own value, and the upgrade route |
| `preload-quoted` | R9 | a quoted preload entry |
| `preload-missing` | R10 | the preload list found |
| `library-path` | R11 | the `dynamic_library_path` found |
| `override-argument` | R12 | the argument that names a socket or data location |
| `private-start` | 4.3 | the private start failed, with its log's last line |
| `password-setup` | 4.4 | the first role that was not `applied`, and its state |
| `private-stop` | 4.5 | the private server did not stop cleanly |
| `health-passfile` | 4.6 | the passfile could not be written |

Each per-role line of 4.4 is a log line, not a refusal: `megasamples-start: password ROLE STATE`.

## 6. The policy format: marker and extension version 2

### 6.1 The pair
- **The marker:** `$PGDATA/megasamples-read-policy` holds `2` and a newline, written by the build.
- **The extension:** `read_policy` at version `2`.
  - The script is `read_policy--2.sql`; the control file's `default_version` is `'2'`.
  - No upgrade script from `1`: there is nothing to migrate (Q4).

### 6.2 The rule
- **R8:** a regular file, not a symlink, whose whole content is exactly the image's value. Anything else is refused before either server starts: absent, `1`, `3`, empty or unreadable.
- **The volume** is kept, untouched apart from the ownership repair.
- **The sentence** names the upgrade route: the README's, and slice 3's general route (5.3).

**Later changes** bump both the marker and the version together.

**The guard:**
- `engines/postgres/read-policy/policy-format.json` records the marker, the version, and one SHA-256 over the files that define what a volume carries, in a fixed order:
  - the extension's script and control file;
  - the init SQL that sets the read policy's grants: `10-read-profile.sql`, `read-routine-names.sql`, `20-grants.sql`, `30-template-grants.sql`.
- A host test recomputes the digest and requires:
  - the recorded pair to equal the control file's version and the Dockerfile's marker;
  - the digest to match.
- So changing one of those files fails until the digest is updated. The test's message says that updating it means bumping the pair.

### 6.3 One message per cause
Slice 3 adds a build identity that the image compares with its data at start ([114-2F]).
- **R8 runs first.** So when both mismatch, only `policy-marker` appears.
- **The cause is the same,** another build's volume, and its sentence already names the upgrade route.
- Slice 3's identity check runs only on a volume whose marker matches. It is slice 3's to build; WS1 fixes the order and documents it.

## 7. Health

### 7.1 One source
- **The script:** `engines/postgres/healthcheck.sh`, copied to `/usr/local/bin/megasamples-healthcheck`. It runs the probe used today:
  - `psql -w` as `demo`, over `127.0.0.1`, with the passfile;
  - `SELECT pg_catalog.megasamples_policy_loaded()`;
  - success only on `t`.
- **The Dockerfile's** `HEALTHCHECK CMD ["megasamples-healthcheck"]`, and the generated Compose file's `test: ["CMD", "megasamples-healthcheck"]`, both run it. Interval and retries stay in Compose; the Dockerfile has its own matching values.
- **The Podman build format:** the image is built with `--format docker`, because the OCI format drops `HEALTHCHECK`. A test inspects the built image's `Config.Healthcheck` and fails if it is missing.
- **The README** says that orchestrators which ignore an image `HEALTHCHECK` (Kubernetes) need their own probe, and gives the command.

### 7.2 What is unchecked, and its signal (I5)

| Route | Detected? | Its signal |
|---|---|---|
| A replaced entrypoint | no | the healthcheck (unhealthy without the policy) |
| A server started inside a shell string | no | the healthcheck |
| A later library that replaces the utility hook without chaining | no | none: stated (section 3) |
| `read_policy` planted on `dynamic_library_path` | **refused**, R11; and the report answers false (9.4) | the refusal |

### 7.3 The MySQL image
- **Decision for version 1:** no image `HEALTHCHECK`. MySQL has no policy library to report on, and its Compose healthcheck stays.
- **The README** states the difference: a hand-run MySQL container has no health signal.
- This can be added later from the same one-source pattern.

## 8. The contract at merge to `main`

These are recorded, each with a consumer impact note, a conformance test, and its unknown-value rule (DL-122):
- **The refusal line format and codes** (section 5). Unknown rule: an unknown code is a refusal.
- **The per-role log states** (4.4). Unknown rule: an unknown state is `uncertain`.
- **The policy format pair** `2`/`2`, and the bump rule (section 6).
- **The image `HEALTHCHECK`** and its command (7.1).

## 9. The decision table, the coverage criterion and the test plan

### 9.1 The coverage criterion
- **By precedence:** because the first failing check decides (section 3), a row is a prefix of passing checks plus one failing value. For a start, it is every check passing, with the start's own facts (F, G, L).
- **Every value of every fact appears in at least one real-container row,** against a base row that passes everything (the base: root, `postgres`, `PGDATA`, baked preload, marker 2, no overrides).
- **The full product of facts A to L runs in a shim harness:** the wrapper under test with `postgres -C`, `pg_ctl`, `psql`, `gosu` and `docker-entrypoint.sh` replaced by recording fakes on `PATH`. The harness asserts:
  - the code;
  - each fake's calls;
  - the per-role log;
  - the passfile's absence or content;
  - that no "server" was left running.
- **Impossible combinations** are listed with their reason, for example R12 without overrides.
- **Named interactions run on real containers too:**
  - a custom persisted socket with overrides (G × F);
  - a non-root start with overrides (A × F);
  - a planted `dynamic_library_path` (E2 × D);
  - a lost reply mid-sequence (L × F);
  - another build's marker with overrides (H × F).

### 9.2 The decision table

Each row names the outcome. "Old key" means the key in force before the start, checked over password-authenticated TCP, never the trusted loopback.

| Row | Facts (the rest as the base) | Outcome | Keys after | Passfile | Listener |
|---|---|---|---|---|---|
| 1 | base | start; report true; namespace hook refuses an out-of-namespace create | published | `demo`'s | yes |
| 2 | base, overrides all | start | new | new `demo` key | yes |
| 3 | B: `gosu postgres postgres` | `wrapped-server` | old | none | no |
| 4 | A: `--user postgres`, overrides some | `non-root` | old | none (`/run` untouched) | no |
| 5 | A: another uid | `non-root` | old | none | no |
| 6 | B: another binary named postgres | `foreign-binary` | old | none | no |
| 7 | B: `--single` / `--boot` / `--check` | `server-mode` | old | none | no |
| 8 | B: `--version` / `--describe-config` / `-C x` | informational exit 0, its output | old | stale one, if any, kept (R5 not reached) | no |
| 9 | H: `PG_VERSION` missing | `uninitialised` | — | none | no |
| 10 | C: `config_file` unreadable | `config-unreadable` | old | removed | no |
| 11 | C: `-D`, `--pgdata`, `-c data_directory` in any case or spelling, `config_file` naming another file, an `include` moving it | `data-directory` (or `config-unreadable` where the server refuses the option) | old | removed | no |
| 12 | H: unmarked; marker `1` (both earlier builds); `3`; empty; a symlink | `policy-marker` | old | removed | no |
| 13 | E: a quoted entry | `preload-quoted` | old | removed | no |
| 14 | D × E: lacking `read_policy` from the baked file, auto.conf, `-c`, an include | `preload-missing` | old | removed | no |
| 15 | E: with other libraries, `read_policy` among them | start | as F | as F | yes |
| 16 | E2: `dynamic_library_path` changed | `library-path` | old | removed | no |
| 17 | F × G: overrides and `-k` or `-c unix_socket_directories` | `override-argument` | old | removed | no |
| 18 | F × C: overrides and `-D` naming `PGDATA` itself | `override-argument` (a rule on the argument, not its value) | old | removed | no |
| 19 | F × G: overrides, and a custom socket persisted in auto.conf | start; the change landed on the private server; nothing listened on the custom path during it | new | new | yes |
| 20 | F × D: overrides, a preload fixed on the command line but not in the files | `preload-missing` (R13) | old | removed | no |
| 21 | L: the first role refused | `password-setup` | all old; per-role `refused`, rest `unattempted` | removed | no |
| 22 | L: the second role's reply lost | `password-setup` | first new, second either, third old; `applied`, `uncertain`, `unattempted` | removed | no |
| 23 | L: a retry of row 22 with the same keys | start | new | new | yes |
| 24 | fault: the private start fails | `private-start` | old | removed | no |
| 25 | fault: the private stop fails | `private-stop`; the server killed | new (as applied) | removed | no |
| 26 | fault: the passfile write fails | `health-passfile` | as applied | none | no |
| 27 | the public start fails (port in use) | the server's own exit | as applied | current key | no |
| 28 | H: marked, other owner | start after the ownership repair | as F | as F | yes |
| 29 | I: a replaced entrypoint | unchecked; unhealthy without the policy | — | — | as started |
| 30 | M: a hand-run container | the image `HEALTHCHECK` reports | — | — | — |

### 9.3 The tests
- **The shim harness** (host, no containers): the full product under 9.1, plus every row of 9.2 that has a code.
  - Each fake records its calls.
  - Every refusal row also asserts that no `psql` ALTER was sent and that no server process was left.
  - It runs in seconds.
- **Real containers** (isolated store, one at a time, a fresh volume per row): every row of 9.2, with keys checked over password-authenticated TCP. The start suite's cleanup scope (`tests/gates/start_scope.py`) carries over.
- **Fault planting** at each step in 9.2's rows 24 to 26, and at the ownership repair, the `-C` reads and the marker read. After each: no server remains, the exit is non-zero, and the passfile is absent.
- **The guard tests:**
  - the policy-format digest (6.2);
  - the image's `Config.Healthcheck` (7.1);
  - Compose's healthcheck naming the same script;
  - the README stating each route of 7.2 and the unsupported non-root platforms.
- **Reversals:**
  - each rule R1 to R13 removed in turn fails at least one row;
  - so does each of 4.3 to 4.6;
  - the shim harness and the real rows record which.

### 9.4 Confirmed by test, not assumed
- **A planted `read_policy` on `dynamic_library_path`, with R11 disabled for the test:** the report answers false and the healthcheck fails. The brief's question 11; R11 then refuses it anyway.
- **Option precedence:** a persisted `unix_socket_directories` does not win over the private start's `-c`.

## 10. The brief's inputs, traced

Each input row of the brief maps to this design:
- **The private start's socket and stop** (Sol round 5, P2-3): 4.3, 4.5; rows 17 and 19.
- **Non-root** (Sol round 5, P3-7): R2; row 4.
- **Failures after a password change** (Sol round 6, P2-5; Sol round 7, 1): 4.4 to 4.7; rows 21 to 27.
- **Another build's volume** (Opus round 6, 4 and P3-2; round 7's retained volumes; fact H's two earlier builds): R8 with format 2; row 12.
- **The healthcheck's location** (Opus round 6, 4): section 7; row 30.
- **`dynamic_library_path`, other libraries, server modes** (Opus round 6, 4): R11, section 3's stated limit, R4; rows 7, 15 and 16.
- **The coverage criterion** (Opus round 7, 1): 9.1.
- **A failed public start and informational commands** (Sol round 7, 1): 4.7 and section 2; rows 8 and 27.
- **The start suite's assertions** (S7-8, O7-P3-3, S8-5): carried into 9.3. Keys are checked over scram TCP, listener lines witness the public server only, and the namespace control uses fresh names and requires `42501` with the hook's own message.
- **The shared volume and the trusted loopback** (S6-6, O6-1): a fresh volume per row; keys never over loopback.
