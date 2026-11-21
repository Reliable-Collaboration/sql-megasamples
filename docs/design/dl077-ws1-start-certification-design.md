# Workstream 1: PostgreSQL start certification, the design

**Status: design, revision 4, for round 4 of the design review. No build yet.**

**Design rounds so far:**

| Round | Reviewed | Reviews |
|---|---|---|
| 1 | revision 1, `2ab72c25` | `sol-ws1-design.md`, `opus-ws1-design.md` |
| 2 | revision 2, `bd9c5f26` | `sol-ws1-design2.md`, `opus-ws1-design2.md` |
| 3 | revision 3, `32664450` | `sol-ws1-design3.md` (1 P1, 8 P2, 2 P3); `opus-ws1-design3.md` (no P1 or P2; 21 P3s, four of them not caught by the planned rows) |

Section 13 traces each round 3 finding; sections 12 and 11 of revision 3 hold the earlier rounds' tracing.

**The decisions applied:**
- **Default 2 of the accepted design, [108-5]:** "No privileged account has a published password, even on loopback". The coordinator applied it in round 2: the loopback trust lines go, under format 2.
- **Round 3, Sol's P1:** this revision pins the public server's `hba_file` to an image-owned file (4.6.1).
- **DL-122's answers to the brief's owner questions (Q1 to Q6),** with the items DL-122 recorded for WS1.

**Scope:**
- the PostgreSQL image's wrapper (`engines/postgres/entrypoint-wrapper.sh`);
- its build (`engines/postgres/Dockerfile` and the build command);
- the `read_policy` extension's format;
- the image's `pg_hba.conf`;
- the healthcheck, including the generated Compose test;
- the README's start section;
- their tests.

The MySQL image appears only in 7.4.

**Facts checked on the current image (`ce3b539fb522`), read-only:**
- the baked `pg_hba.conf` trusts the local socket and both loopbacks, and requires `scram-sha-256` elsewhere;
- `/usr/bin/perl` is present, with core `Digest::SHA` and `MIME::Base64`;
- `/usr/local/bin` holds the upstream entrypoint scripts, `gosu` and the wrapper;
- `megasamples/credentials.py`'s `pgpass()` escapes `\` and `:`.

## 1. Decisions this design applies

| Decision | What the design does |
|---|---|
| DL-122 Q1: the private start, made exact | 4.3. R14 refuses, with overrides set, an argument naming a socket, port or data location. |
| DL-122 Q2: non-root refused first | R0, first on every route but "other command". |
| DL-122 Q3: stable codes | Section 5's codes. The `EXIT` trap guarantees a coded line, and exit 1. |
| DL-122 Q4: format 2, exact match, digest guard | Section 6: the marker checked before the repair and either launch; every revision of the pair file checked; the upgrade route specified and rehearsed. |
| DL-122 Q5: an image `HEALTHCHECK`, one source | Section 7; the Compose test becomes the same script. |
| DL-122 Q6: four per-role states, nothing stale | 4.4, 4.6. |
| Default 2, [108-5] | 4.6.1: no loopback trust, and the public `hba_file` pinned to an image-owned file. |
| DL-122 recorded: one message per cause; MySQL; the contract | 6.3; 7.4; section 8. |

## 2. Routes

**One operand-aware parser** reads the argument vector as `postgres`'s `getopt` does (3.1). Classification and R14 both use it.

**Command words:**
- `argv[1]`;
- recursively, the word in command position after each recognised wrapper, so `env gosu postgres postgres` is walked to `postgres` (Sol 10).

Option values are never command words.

**Server words:** any name or path whose basename is one of:
- `postgres`, `postmaster`;
- `pg_ctl`, `pg_ctlcluster`;
- `docker-entrypoint.sh`, `docker-ensure-initdb.sh`, `docker-enforce-initdb.sh`.

| Route | Recognised by | Outcome |
|---|---|---|
| **Server start** | `argv[1]`'s basename is `postgres`, or `argv[1]` begins with `-` | R0, section 3, section 4. R2 refuses a `postgres` that is not the image's own path. |
| **Informational** | a start whose parsed options include `-C`, `--version`/`-V`, `--describe-config` or `--help`/`-?` | R0 to R3; then it runs as `postgres` in the pinned environment and exits with its status |
| **Server mode** | a start with `--single`, `--boot` or `--check` | refused: `server-mode` |
| **Ambiguous argument** | a start where a token equals one of upstream's help words (`-?`, `--help`, `--describe-config`, `-V`, `--version`) but the parser reads it as an operand, for example `postgres -k --version` | refused: `argument-ambiguous`. Upstream's `_pg_want_help` would read it as help and run the server as root (Opus 10). |
| **Wrapped server** | the walk through recognised wrappers reaches a server word; or `argv[1]` is a server word other than `postgres` | refused: `wrapped-server` |
| **Other command** | anything else | handed to the upstream entrypoint unchanged |

**Recognised wrappers:** `gosu`, `su-exec`, `runuser`, `su`, `sudo`, `env`, `setpriv`, `setsid`, `chroot`, `nice`, `ionice`, `nohup`, `timeout`, `stdbuf`, `taskset`, `exec`, `time`.

**An unrecognised command word, a shell string, or a replaced entrypoint** is unchecked. It is always unhealthy, because only the wrapper's handover writes the endpoint (7.3).

## 3. The checks, in order

The first check that fails decides.

| # | Check | Fact | Refused with |
|---|---|---|---|
| R0 | The wrapper runs as root | A | `non-root` |
| R1 | The route is a start or informational | B | `wrapped-server`, `server-mode`, `argument-ambiguous` |
| R2 | `argv[1]` is `/usr/lib/postgresql/18/bin/postgres` (by name under the pinned `PATH`, or by path) | B | `foreign-binary` |
| R3 | No loader variable (`LD_PRELOAD`, `LD_LIBRARY_PATH`, `LD_AUDIT`), and no server-read variable the design does not honour (`PGPORT`, `PGOPTIONS`, `PGDATESTYLE`, `PGTZ`, `PGCLIENTENCODING`) | J | `loader-environment`, `server-environment` |
| — | Informational routes stop here | B | — |
| R4 | The override keys are well formed (4.2) | F | `key-conflict`, `key-file`, `key-value` |
| R5 | `PG_VERSION` exists | H | `uninitialised` |
| — | **The directory lock** (4.9) | — | `volume-busy` on timeout; any other lock error `internal` |
| — | The endpoint and stale private files are removed (only now, while the lock is held) | — | — |
| R6 | The marker is the image's own, exactly | H | `policy-marker` |
| — | slice 3's build-identity check (6.3) | — | slice 3's code |
| — | The ownership repair | H | — |
| R7 | The server reports its configuration, by `-C`, as `postgres` | C, D | `config-unreadable`, which also covers a value the server cannot parse, such as a non-numeric `port` |
| R8 | `data_directory` is `PGDATA`, and `PGDATA`'s identity is the locked descriptor's (`stat -L /proc/self/fd/9`) | C | `data-directory` |
| R9 | No quoted preload entry | E | `preload-quoted` |
| R10 | `read_policy` is preloaded | D, E | `preload-missing` |
| R11 | `dynamic_library_path` is `$libdir` | E2 | `library-path` |
| R12 | No session or local preload in files or arguments | E | `preload-session` |
| R13 | `unix_socket_directories` parses as a list | G | `socket-settings` |
| R14 | With overrides set: no argument names a socket, port or data location (3.1) | F, C, G | `override-argument` |
| R15 | With overrides set: no `standby.signal` or `recovery.signal` (rotation cannot succeed on a standby) | H | `recovery-mode` |
| R16 | With overrides set: the private launch's values discovered, validated and rechecked (4.3) | F, C, D | R7 to R13's codes, "the private launch" |
| R17 | The extra HBA file, if present, has no `trust`, `password` or `ident` method and is readable (4.6.1) | — | `hba-local` |

**Changes from revision 3:**
- **R3** now also refuses the server-read variables. A set `PGPORT` was silently dropped by the pinned environment (Opus 11). The sentence says to use `-p` or `-c port`.
- **R15** is new. It removes the unbounded wait's standby case (Opus 9).
- **R17** is new (4.6.1).
- **Non-numeric `port`** is R7's, as the server's parse decides (Sol 8; Opus 12).

### 3.1 The parser and R14's backstop
- **The parser:** `getopt` with attached values; `-c name=value` and `--name=value`, with `-` read as `_` and names case-folded.
- **R14's backstop:** `-C name` with and without ARGS must agree in status and value.
- **R14's rows** are generated from the spelling matrix.

### 3.2 Stated, not refused
- **Any library that the configuration or a superuser loads** can replace either hook the extension installs (`ProcessUtility_hook`, `object_access_hook`) without chaining it, while the report stays true (Opus 14). That includes:
  - other `shared_preload_libraries`;
  - `archive_library`;
  - PostgreSQL 18's `oauth_validator_libraries`;
  - a superuser's `LOAD`.

  Some of these accept absolute paths, so R11's pin does not bind them. Whoever sets them controls the server.
- **Catalog-kept per-role or per-database settings** (session preloads) are not visible to `-C`. Pins do not override them.
- **Administrator-installed hooks** that inspect statements could see the verifier.
- **The README states all three.**

## 4. The start

### 4.1 What reaches the wrapper, and what it passes on
- **The interpreter:** `#!/bin/bash -p` ignores `BASH_ENV` and `ENV`, and imports no functions.
- **The entry points are absolute:** the Dockerfile's `ENTRYPOINT ["/usr/local/bin/entrypoint-wrapper.sh"]` and its `HEALTHCHECK` command (Sol 10; Opus 19).
- **Stated limits:**
  - a loader variable acting on Bash before line 1;
  - a path replaced beneath `PGDATA` mid-start. R8 ties `PGDATA` to the locked descriptor.

**The pinned environment:**
- **`PATH`** is set first and exported: `/usr/lib/postgresql/18/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`.
- **Absolute paths** for `postgres`, `psql`, `pg_isready`, `gosu`, `perl`, `flock`, `setsid` and `docker-entrypoint.sh`.
- **Each child** runs under `env -i` with `PATH`, `PGDATA`, `HOME=/nonexistent`, `LANG=C.UTF-8`, and `TZ` for the server.
- **`psql`:** `psql -X -w -v ON_ERROR_STOP=1`, naming the whole address (Sol 3; Opus 5).

**The shell's own rules:**
- `set -euo pipefail` and `shopt -s inherit_errexit execfail`;
- job control off;
- `TERM`, `INT`, `HUP` and `QUIT` trapped explicitly, since PID 1 ignores unhandled signals (Opus 8);
- `wait "$pid" || status=$?`.

**The secret-bearing private files** live in `/dev/shm/megasamples-private` (tmpfs under Docker and Podman), mode 0700, never in the writable layer (Opus 7). They are:
- the confirmation passfile;
- the key handoff to the verifier;
- the clients' stderr;
- the private server's log.

The directory is removed at the start and before the handover.

**The handover's environment** is built by unsetting, in the wrapper itself, every exported variable not on an allowlist, then `exec`ing directly. There is no `env -i` process, so `execfail` sees the real target (Sol 5; Opus 8). The allowlist:
- **derived** from the variables the pinned upstream `docker-entrypoint.sh` references, plus the image's own `ENV` (`PATH`, `PGDATA`, `PG_MAJOR`, `PG_VERSION`, `GOSU_VERSION`, `LANG`), plus `LC_*` and `TZ`;
- **guarded:** a test greps the pinned upstream script and the image's `ENV` and requires the allowlist to cover them (Opus 11);
- **dropped:** everything else, including `KRB5_KTNAME` and LDAP's TLS variables. The README lists that as a contract change.

### 4.2 The override keys
- **The keys:** `POSTGRES_PASSWORD`, `ADMIN_PASSWORD` and `DEMO_PASSWORD`, each also as `*_FILE`.
- **R4 refuses:**
  - **`key-conflict`:** a key set both ways;
  - **`key-file`:** an unreadable file;
  - **`key-value`:** a key that, after a file's trailing LF bytes are removed, is empty, longer than 1024 bytes, or holds a byte outside 0x20 to 0x7E.
- **The sentence** names the variable and the rule, never the value or the bad byte's position (Opus 20).
- **The README says:**
  - a CRLF file is refused;
  - trailing spaces are kept;
  - an empty direct value, which today's wrapper treats as "no override", is now a refusal;
  - Compose's `:-` defaults are unaffected.
- **Why printable ASCII:** SASLprep leaves it unchanged, so the verifier matches every client. A later SASLprep port can widen it.
- **The same validated bytes** feed the verifier and the confirmation passfile (Sol 11).

### 4.3 The private start
**Its address:**
- the socket directory `/run/megasamples-private`, recreated, owned by `postgres`, mode 0700;
- port `5432`;
- `listen_addresses` empty.

**Its own HBA file:** `/dev/shm/megasamples-private/hba.conf`, written by root, mode 0640, group `postgres`:

```
local  postgres     postgres  trust
local  megasamples  all       scram-sha-256
```

**Its values:**
1. **Discovered** by `-C` with no arguments.
2. **Validated** by R8 to R13.
3. **Built into an argv array** pinning `data_directory`, `listen_addresses=`, the socket directory, `port=5432`, the `hba_file`, the discovered preload, `dynamic_library_path=$libdir`, empty session and local preloads, and stderr logging.
4. **Rechecked:** `-C` with that array returns each pinned value.

**Process:**
- The trap is armed first.
- The server is launched as `setsid` + `postgres …` in the background, its PID kept.
- **Readiness:** `pg_isready` each second.
  - **0:** ready;
  - **1** (recovering): wait while the child lives, with progress every 30 seconds (R15 has excluded standbys);
  - **2:** give up after 60 seconds.
- **Once ready,** line 1 of `postmaster.pid` must equal the tracked PID, or the start refuses with `private-start` (Opus 8).

### 4.4 The passwords
**The order:** `postgres`, `admin`, `demo`, requested roles only.

**The verifier.** A Perl routine reads the validated key on stdin and computes the SCRAM-SHA-256 verifier:
- a 16-byte salt from `/dev/urandom`, length checked;
- PBKDF2-HMAC-SHA-256 with 4096 iterations, `hmac_sha256($data, $key)`;
- the RFC 5802 keys;
- `encode_base64($x, '')`;
- the output pattern-checked.

**The self-test, against the server's own oracle** (Opus 6). The build sets a scratch role's password from a fixed key, with `password_encryption = 'scram-sha-256'`, and reads `rolpassword`, which carries the server's own salt. The fixture records that key and that verifier.
- **At every start with overrides,** the routine computes the verifier from the fixture's key and the salt parsed from the recorded verifier, and must reproduce the recorded verifier exactly. Otherwise the start refuses with `internal`, naming the self-test.

**The rotation session:** one `psql -X -w -v ON_ERROR_STOP=1` per role, in the background, `wait`ed. Its stdin:

```
\warn megasamples-connected
SET log_statement = 'none'; SET log_min_error_statement = 'panic'; SET log_min_duration_statement = -1;
SET log_min_duration_sample = -1; SET log_statement_sample_rate = 0; SET log_transaction_sample_rate = 0;
SET log_parameter_max_length_on_error = 0; SET debug_print_parse = off; SET debug_print_rewritten = off;
SET debug_print_plan = off; SET pg_stat_statements.track_utility = off;
\warn megasamples-sending
ALTER ROLE "ROLE" PASSWORD 'SCRAM-SHA-256$4096:…';
\warn megasamples-applied
```

- **`ON_ERROR_STOP`:** a failed `SET` stops the script before the `ALTER`, and a refused `ALTER` exits 3 without printing `applied` (Sol 3).
- **Checked natively:** the `pg_stat_statements` placeholder `SET` raises no error on the image (Opus 21).

**The confirmation:**
- **What it does:** a libpq sign-in as ROLE to `megasamples` on the private socket, with `require_auth=scram-sha-256`, so no trust line can satisfy it.
- **Its passfile:** `/dev/shm/megasamples-private/pgpass`, owned by `postgres` (the client's OS user), mode 0600. It holds `*:*:megasamples:ROLE:KEY`, escaped as `credentials.pgpass()` escapes, `\` and `:` (Sol 11; Opus 4). It is removed at once.

**The state:**

| Observed | State |
|---|---|
| no `connected` | `unattempted` |
| `connected`, no `sending`, exit not by signal | `unattempted` |
| `applied`, and the confirmation succeeded | `applied` |
| `sending`, no `applied`, exit 3 | `refused` |
| `applied`, and the confirmation failed | `uncertain` |
| `sending` without `applied` and any other exit; any death by signal without `applied`; `applied` then interrupted before the confirmation | `uncertain` |
| not run after an earlier failure | `unattempted` |

**After a failure:**
- the first non-`applied` result stops the sequence;
- the server is stopped;
- the wrapper exits 1 with `password-setup`;
- each requested role is logged with its state.

**A retry converges.**

### 4.5 Supervision and the stop
- **Waits:** clients and the server run in the background and are `wait`ed, so a signal interrupts promptly.
- **The trap:**
  - terminates a running client;
  - sends `SIGINT` to the server's group (`setsid` made it a group leader), waits up to 60 seconds, then `SIGQUIT` for 10 seconds, then `SIGKILL`;
  - reaps with `wait`.
- **Codes:**
  - a forced stop is `private-stop`;
  - a signal received during the start is `interrupted`, new, logged with each role's state so far (Opus 8).
- **One refusal line.** The first failure's code, then `also:` lines.
- **Whether a refusal was written** is recorded as a file in the private directory, not a shell variable. So a refusal inside a `$(…)` is not followed by a second `internal` line. A lint check forbids `refuse` inside a substitution all the same (Opus 8).

### 4.6 Authentication and health

#### 4.6.1 The public HBA, pinned (Sol's P1)
**The choice: pinning.**
- The image ships `/etc/megasamples/pg_hba.conf`, root-owned, mode 0644. It is part of format 2 and inside the digest.
- The public launch pins `-c hba_file=/etc/megasamples/pg_hba.conf`. So **the volume's `pg_hba.conf` is never read** by either server, whatever it holds, including a retained file with a loopback `trust` rule.

**The image's file:**

```
include_if_exists /etc/megasamples/pg_hba.local.conf
local  all          all  trust
local  replication  all  trust
host   all          all  all  scram-sha-256
```

**How a deployer adds rules:**
- **Where:** mount a file at `/etc/megasamples/pg_hba.local.conf`, for example `hostssl` lines, `reject` lines, a narrower `host` rule, or `cert`, `gss` or `ldap` methods.
- **Its place:** it is included first, so its rules come before the image's catch-all.
- **R17 certifies it before either launch:** it must be readable and contain no `trust`, `password` or `ident` method. A violation is refused with `hba-local`, naming the line.
- **Include directives** inside it are refused too, so the certification sees every rule.
- **R17's parser** is checked natively against PostgreSQL's own `pg_hba_file_rules` view in the tests (9.4).

**What a deployer who customised the volume's `pg_hba.conf` sees:**
- **The log line:** `megasamples-start: note: the volume's pg_hba.conf is not used; add rules in /etc/megasamples/pg_hba.local.conf`. It is printed whenever the volume's file differs from the format-2 file the build wrote. It is not a refusal.
- **The README:** a section on authentication says the same, with the mount example.

**Reach:**
- **The `local` lines** admit any process that can open the public socket: the container's own processes, and containers sharing the socket directory through a volume.
- **TCP, loopback included,** needs a key, under Docker, pasta and rootlesskit alike.
- **The README and [110-2]** say that `psql -h localhost` and sidecars need a key.
- **The private server** uses its own `hba_file` (4.3), so a hardened `local` rule in a deployer's extra file does not affect rotation.

**The probe** needs the image's `local … trust` line for `demo`. A deployer's extra `reject` for `demo` on `local` makes it unhealthy, and the README says so.

#### 4.6.2 The probe
**What it does:** connects as `demo`, to `megasamples`, on the dedicated probe socket, in the pinned environment, and runs `SELECT pg_catalog.megasamples_policy_loaded()`.

**No passfile exists.**

#### 4.6.3 The endpoint, bound to the serving process
**The probe socket directory:** `/run/megasamples-probe`, recreated at every start, owned by `postgres`, mode 0700 (Sol 7; Opus 3).

**The public launch's socket list** is the certified list plus `/run/megasamples-probe`, built without an empty element: a TCP-only empty list becomes just the probe directory.

**The endpoint file,** `/run/megasamples-health.endpoint`, mode 0644, is written just before the `exec`. It records:
- the PID, which is the postmaster's (`exec`, then upstream's `exec gosu`, then `exec "$@"`);
- the probe directory;
- the port;
- `PGDATA`.

It is removed while the lock is held, and again if the `exec` fails.

**The probe checks, in order:**
1. `postmaster.pid` under the recorded `PGDATA` names the recorded PID, which is alive, and the recorded port.
2. The socket `/run/megasamples-probe/.s.PGSQL.PORT` exists.
3. It connects to that socket and gets `t`.

A server that bound its ordinary socket but not the probe socket is unhealthy, with the reason "probe socket missing".

### 4.7 The handover
```
# every non-allowlisted variable unset; PATH pinned and exported
exec /usr/local/bin/docker-entrypoint.sh postgres ARGS PINS || handover_failed
```
- **`postgres` by name,** resolved through the pinned, exported `PATH`. Upstream's `[ "$1" = 'postgres' ]` and `exec "$@"` work unpatched (Opus 10). A build test asserts that `command -v postgres` under the pinned `PATH` is the image's binary.
- **PINS:** `data_directory`, the certified preload, `dynamic_library_path`, empty session and local preloads, the socket list of 4.6.3, the certified port, and `hba_file=/etc/megasamples/pg_hba.conf`.
- **`execfail` with `|| handover_failed`:** if the entrypoint cannot be executed, the wrapper removes the endpoint and refuses with `handover`.
- **Failures after the `exec`:** upstream's `exec gosu`, or `gosu`'s `exec postgres`, are upstream processes. Their failure leaves a dead PID in the endpoint, so the probe is unhealthy, and the next start removes the endpoint. The README states it.
- **Tested at each `exec` boundary:** the entrypoint missing, `gosu` missing, the server binary failing to execute, and the server exiting after start.

### 4.8 Slice 3's step P
- **Where it sits:** after R16, the passwords and the private stop; before the endpoint and the handover; on both branches.
- **What it does now:** nothing. Slice 3 puts [110-2] there, and the state `locked` is reserved.
- **The lock covers it.**
- **Until slice 3,** `postgres` and `admin` sign in over TCP with published keys whenever no override applies, and loopback now needs a key.
- **A release condition:** [110-2] holds at P on every route. T-23 checks it with missing, published, wrong and private keys, on both loopback families, and **with a retained volume `pg_hba.conf` carrying a loopback `trust` rule** (Sol's P1).
- **Under slice 3's seeding,** `uninitialised` narrows to a non-empty directory.

### 4.9 One start per volume, for the server's life
**The lock** (Sol 2; Opus 1, 2):
- After R5: `exec 9<"$PGDATA"`, the directory opened read-only, then `flock -x -w 30 9`.
- It writes nothing to the volume and works on a read-only mount. So a refused volume stays untouched.
- **A timeout** is `volume-busy`. **Any other `flock` failure** (`ENOLCK` on a filesystem without locks) is `internal`, naming the step.

**How long it is held:**
- Descriptor 9 is inherited through the `exec`s, so the postmaster holds the lock for its whole life.
- This is the only interlock between containers on one volume. `postmaster.pid` does not provide one: a second container's postmaster is usually PID 1, the PID the first container recorded, and treats the file as its own stale lock. The shared-memory interlock is not visible across IPC namespaces either.
- **There is no fallback.** The build's first native step checks that the lock survives the `exec`s and the postmaster's start. If PostgreSQL closed the descriptor, the build stops and the design returns for review, because holding the lock only through the handover would reopen the race.

## 5. Refusal lines and codes

**The line format:** `megasamples-start: refused: CODE: SENTENCE` on stderr.

**The `EXIT` trap.** For any wrapper-owned exit, it makes sure that:
- a coded line was written, `internal` with the last step if none was;
- the exit status is 1.

**The rules for codes:** codes are added, never renamed or removed. An unknown code is a refusal.

**The codes:**

| Codes | Where |
|---|---|
| `non-root` | R0 |
| `wrapped-server`, `server-mode`, `argument-ambiguous` | R1 |
| `foreign-binary` | R2 |
| `loader-environment`, `server-environment` | R3 |
| `key-conflict`, `key-file`, `key-value` | R4 |
| `uninitialised` | R5 |
| `volume-busy` | 4.9 |
| `policy-marker` | R6 |
| `config-unreadable` | R7 |
| `data-directory` | R8 |
| `preload-quoted` | R9 |
| `preload-missing` | R10 |
| `library-path` | R11 |
| `preload-session` | R12 |
| `socket-settings` | R13 |
| `override-argument` | R14 |
| `recovery-mode` | R15 |
| `hba-local` | R17 |
| `private-start`, `password-setup`, `private-stop`, `interrupted` | the private phase |
| `handover` | 4.7 |
| `internal` | the catch-all |

**New in revision 4:** `argument-ambiguous`, `server-environment`, `recovery-mode`, `hba-local` and `interrupted`.

## 6. The policy format

### 6.1 The pair
- **The marker:** `2`.
- **The extension:** `read_policy` version `2`, with no upgrade script.
- **Format 2 also carries:**
  - the image-owned `/etc/megasamples/pg_hba.conf`;
  - the volume `pg_hba.conf` the build writes, which the server no longer reads but the start compares against for the note in 4.6.1.
- **The wrapper's constant** is generated from `policy-format.json`.

### 6.2 The rule and its guard
**R6:** a regular file, not a symlink, holding exactly the image's value, checked before the repair and either launch.

**`policy-format.json`** lists every released pair with its digest. The digest covers:
- the extension (script, control, C source);
- the init SQL (`00-users.sql`, `10-read-profile.sql`, `15-read-views.sql`, `read-routine-names.sql`, `20-grants.sql`, `30-template-grants.sql`, `40-register-template.sql`);
- `megasamples/postgres_templates.py`;
- the image `pg_hba.conf`;
- the Dockerfile's policy and HBA steps.

**The history check** (Sol 9; Opus 17):
- The test walks every revision of `policy-format.json` (`git log --format=%H -- …`, then `git show REV:…`) and parses each.
- Each pair, keyed by its marker and version, must have the same digest in every revision where it appears.
- A pair present in any revision must be present in every later one.
- The test needs full history and fails on a shallow clone.
- **Tested:** rewriting a released pair's digest fails; deleting a released pair fails; changing a digest and changing it back fails, because the middle revision differs.

**Also checked:**
- the pair matches the control file, the Dockerfile's marker write and the wrapper's constant;
- the built image's databases have `extversion` `2`.

### 6.3 One message per cause
- **The order:** slice 3's identity check sits after R6, before the repair and either launch. When both mismatch, only `policy-marker` appears.
- **The integration cases, run when slice 3 adds its check:**
  - both mismatched: only `policy-marker`;
  - the marker matching and the identity mismatched: slice 3's refusal.
- **`up`'s U-3 preflight** reports `stale-image` without invoking the image.

### 6.4 The upgrade route (Sol 4; Opus 18)
1. **Keep the volume.**
2. **Start the image that made it,** with no TCP published.
3. **Dump each sample database** as `admin`, with `pg_dump -Fc --no-acl --no-owner`.
4. **Dump roles** with `pg_dumpall --roles-only --no-role-passwords`, keeping only roles the current image lacks.
5. **Start the current image on a fresh volume,** with overrides for every privileged key.
6. **For each database, restore a filtered list:**
   - `pg_restore -l` lists the archive;
   - the list keeps only table data and objects owned by `admin` or a deployer role. It drops:
     - the `read_policy` extension and its schema;
     - the event trigger;
     - `15-read-views.sql`'s views, which `postgres` owns;
     - every `DEFAULT ACL` and `ACL` entry.
   - `pg_restore -L list --no-acl --no-owner --clean --if-exists --exit-on-error` runs as `admin`, into the baked database.
7. **Verify, before TCP is opened:**
   - the healthcheck is healthy;
   - the extension is at version 2;
   - the report's exact ACL;
   - the retained edit is present;
   - `demo`'s rights equal the image's;
   - no privileged key from before the dump signs in.

**The README gives the steps.** The rehearsal runs on both marker-1 variants: a volume from before the report, and one from before `admin`'s revoke.

## 7. Health

### 7.1 One source
- **The script:** `/usr/local/bin/megasamples-healthcheck`, from `engines/postgres/healthcheck.sh`.
- **The image's `HEALTHCHECK`** names it by absolute path.
- **The generated Compose service's test** becomes `["CMD", "/usr/local/bin/megasamples-healthcheck"]`, replacing today's `127.0.0.1` and passfile test (Opus 19).
- **The timings:** `healthcheck.json` is the source. The Compose generator reads it, and the Dockerfile carries the same literals. A guard test compares the JSON, the Dockerfile, the built image's `Config.Healthcheck` and the generated Compose service.

**The build route** (Sol 6). The format decision depends on **the client**, not the server.

| Client | Server | Build |
|---|---|---|
| Docker's CLI | Docker | the Docker format is the default, so no flag |
| Docker's CLI | Podman's socket, the documented route | the CLI rejects `--format`. The build goes through Podman's compatible API. **Whether that API keeps `HEALTHCHECK`** is checked by the inspect test on this route. If it does not, `megasamples image` runs `podman build --format docker` against the same store, where `podman` is installed and `container_engine.podman()` says Podman answers. |
| `podman` (or the podman-docker shim) | Podman | `--format docker` |

**Detection:** `docker --version` and `docker version -f '{{.Client.Platform.Name}}'` tell the client apart.

**The inspect test** runs `megasamples image` on each route and asserts `Config.Healthcheck`.

### 7.2 What the probe reports
- **It reports:** the policy library loaded in the postmaster this wrapper handed over to, through its dedicated socket.
- **It does not report:** a hook replaced by a loaded library (3.2), or whether TCP listens.
- **A deployer's `reject` for `demo` on `local`** makes it unhealthy.

### 7.3 Unchecked routes

| Route | Detected? | Signal |
|---|---|---|
| Replaced entrypoint; unrecognised command word; shell string | no | always unhealthy: no endpoint |
| Any library the configuration or a superuser loads replacing a hook | no | none, stated |
| Catalog-kept session or local preloads | no | none, stated |
| Code-loading variables other than R3's | dropped by the handover's allowlist | — |
| A loader variable acting on Bash itself | no | stated |
| A path replaced beneath `PGDATA` | R8 against the locked descriptor | the refusal |
| `read_policy` on `dynamic_library_path` | refused, R11 | the refusal |
| A retained volume `pg_hba.conf` with `trust` | not read: the pinned `hba_file` | the note in 4.6.1 |

### 7.4 The MySQL image
- **Version 1:** no image `HEALTHCHECK`.
- **The README** says the generated Compose file supplies one and a hand-run MySQL container has none, under a guard test.

## 8. The contract at merge to `main`

Each item below is recorded with an impact note, a conformance test and its unknown-value rule:
- **the refusal line format and codes:** an unknown code is a refusal;
- **the per-role states,** with `locked` reserved: an unknown state means the key is not known to be the requested one;
- **the format pair and its rules,** including the image-owned HBA file;
- **the key rule:** printable ASCII, 1 to 1024 bytes, a file's trailing LF bytes removed;
- **the extra HBA file's location and certification;**
- **the dropped environment variables** (4.1) and the refused server-read ones (R3);
- **the image `HEALTHCHECK`** and the Compose test that names it;
- **the narrowing of `uninitialised`.**

## 9. Coverage

### 9.1 Generation
`tests/gates/ws1_rows.py` generates the cases. **The count comes from the generator and is checked by it;** the runtime is measured at the build's first step (Sol 8; Opus 15).

- **(a) Admission refusals:** each rule's failing values, with earlier checks passing. The lock is a rule here.
- **(a′) Pairs of co-reachable failures:** the earlier rule's code must win.
- **(b) Starts:**
  - **Per requested role and source:** for each non-empty subset of the three roles, each role direct or file. That is 26 assignments.
  - **L by position,** 1 + 3k for a subset of size k. Summed over subsets, that is 188 cases of role, source and L.
  - **G and logging are crossed with L, but not with each other,** because neither affects role or source. G has 4 values and logging 4, which share the default, so 188 × 7 = 1,316 cases.

**Left out of the product:** J's non-loader values, and the passing argument forms. Each gets its own row; the reason is in revision 3's 9.1.

**On real containers:** every row of 9.2, every fact value against the base, and the named interactions.

### 9.2 The decision table
- **"Old" and "new" keys** are checked over password-authenticated TCP. For a row with no listener, they are checked on a separate start of the same fixture.
- **(A)** marks an admission refusal: no client run, no key changed.
- **(W)** marks a failure after work began.
- **Rows 1 to 50 are as in revision 3** (`git show 32664450:docs/design/dl077-ws1-start-certification-design.md`, section 9.2), **with these changes:**

| Row | Facts | Outcome |
|---|---|---|
| 1 | base | As revision 3, plus: the Compose service and a hand-run container both healthy through the same script |
| 9 | (A) adds `env gosu postgres postgres` (nested) | `wrapped-server` |
| 14 | `--version`; `--describe-config`; `-C port`; `-c work_mem=8MB -C port`; `-Cport` | informational, exit 0 |
| 14c | (A) `postgres -k --version` | `argument-ambiguous` |
| 15b | (A) `PGPORT`, `PGOPTIONS` set | `server-environment` |
| 18 | (A) as revision 3, on a read-only mount too | `policy-marker`; nothing written; ownership unchanged |
| 26 | (A) `unix_socket_directories` malformed | `socket-settings`. A non-numeric `port` moves to row 19's `config-unreadable`. |
| 26b | an empty certified socket list (TCP only) | start; the socket list is only the probe directory; healthy |
| 26c | a stale `/run/megasamples-probe` from an earlier start in the same container, with the wrong owner | recreated; healthy |
| 26d | the probe directory not writable by the server (a fault) | the server serves; probe unhealthy: "probe socket missing" |
| 30 | (W) the first role refused | `password-setup`; **`refused`**, then `unattempted` |
| 30b | (W) a retry where the requested key already works, and the `ALTER` is refused (fault) | `refused`, not `applied` |
| 31 | (W) a lost reply: the fault relay forwards the `ALTER`, **waits until it has seen the server's `CommandComplete`**, then closes both directions before forwarding it | `uncertain`; the new key signs in on a separate start |
| 35c | (A) overrides with `standby.signal` or `recovery.signal` | `recovery-mode` |
| 36 | (W) a signal during the private phase | `interrupted`, with each role's state; the child stopped and reaped |
| 39 | (W) the entrypoint missing; `gosu` missing; the server binary failing to execute | the first: `handover`; the others: a dead PID in the endpoint, unhealthy |
| 42 | (A) root, `/run` read-only; `--cap-drop ALL`; the self-test failing; `ENOLCK` | `internal`, naming the step, exit 1 |
| 47 | a volume `pg_hba.conf` with `local` requiring a key | start; the note; healthy (the volume file is not read) |
| 48 | loopback TCP, both families, as `postgres` and `admin`, no key or a wrong key, under Docker, pasta and rootlesskit; **and with a retained volume `pg_hba.conf` carrying `host all all 127.0.0.1/32 trust`** | refused by SCRAM; right key admitted |
| 48b | (A) an extra HBA file with `trust`, `password` or `ident`, or an `include` | `hba-local` |
| 48c | an extra HBA file with a `hostssl … scram-sha-256` rule and a `reject` | start; the rules apply (checked against `pg_hba_file_rules`) |
| 49 | (A) a second **container** on the same volume, held at each boundary, including during the first's public run | waits, then `volume-busy`; the first's keys in force; one postmaster on the volume |
| 50 | keys with `'`, `\`, `:`, `$`, `"`, `;`, leading and trailing spaces, and 1024 bytes | start; each confirmed |

### 9.3 The shim harness
**Where it runs** (Sol 8; Opus 16):
- in a task-owned container of the image, in the isolated store, with `--cap-add SYS_ADMIN`;
- real root inside, the image's real `postgres` uid, and the image's filesystem;
- the fakes bind-mounted over the absolute paths;
- `/run`, `/dev/shm` and `PGDATA` on tmpfs.

**A preflight** fails loudly if a bind mount or the uid is missing. It does not run on a bare host.

**The guard:** the wrapper names no environment variable outside the allowlist of 4.1.

**Each row asserts:** the code, the calls, the states, the endpoint and the processes.

### 9.4 Conformance, by construction
**The `-C` recording:**
- The fake `postgres -C` records every query it answered, with the fixture's whole tree: working directory, absolute paths outside `PGDATA` (includes, `config_file`), owners and modes.
- Each query is replayed, as `postgres`, against the real `postgres -C` in a throwaway container. The fixture tree is reproduced exactly, and status and value must agree (Opus 13).

**R17's HBA parser** is checked the same way, against `pg_hba_file_rules` on a scratch server.

### 9.5 Confirmed natively
- the `psql` exit mapping, by the fault relay;
- the `dynamic_library_path` report;
- the precedence of pins and session `SET`s;
- the placeholder `SET`;
- the lock's inheritance (4.9);
- the loopback rows under each network mode;
- the upgrade rehearsal on both marker-1 variants.

### 9.6 Reversals
- **Each rule R0 to R17,** removed in turn, fails at least one row.
- **So does each mechanism:**
  - the pinned environment, `-p`, the handover allowlist, each pin, the public and private `hba_file` pins;
  - the session `SET`s, `ON_ERROR_STOP`, the verifier's self-test against the server oracle, the confirmation with `require_auth`, `\warn`;
  - `setsid` and the tracked-PID check, the interruptible waits, the directory lock;
  - `execfail` with `||`, the endpoint's PID, port and socket checks;
  - the removed loopback lines.

## 10. The build order
1. **The harness and the generator, red against today's wrapper.** First, the native check that the lock survives the `exec`s; on failure the build stops (4.9).
2. **Routes, the parser, and R0 to R4.**
3. **Format 2** (marker, extension, both HBA files) and its guard, then R5, the lock and R6.
4. **R7 to R17,** and the pins.
5. **The private phase:** environment, start, verifier and self-test, passwords, confirmation, supervision, stop.
6. **Health:** the probe socket, the endpoint, the script, the Compose test, the timings, the build routes.
7. **The handover and step P.**
8. **Real rows,** faults, network modes, and the upgrade rehearsal.

## 11. The brief's inputs, traced
As revision 3's section 11 (at `32664450`). Also, round 6 S6-6's loopback masking is now closed twice: by removing the trust lines, and by the pinned `hba_file`.

## 12. Design round 2, traced
As revision 3's section 12 (at `32664450`).

## 13. Design round 3, traced

| Finding | Where answered |
|---|---|
| Sol 1 (P1): a retained public HBA | 4.6.1 (pinned `hba_file`, extra file certified by R17); 4.8's T-23 case; rows 47, 48, 48b, 48c |
| Sol 2; Opus 1, 2: the lock | 4.9 (directory descriptor, no fallback, the cross-container premise corrected); R8 on the descriptor; endpoint removed after the lock; `ENOLCK` to `internal`; row 49 as a second container |
| Sol 3; Opus 5: `ON_ERROR_STOP` | 4.1, 4.4; rows 30, 30b; the relay waits for `CommandComplete` (row 31) |
| Sol 4; Opus 18: the upgrade recipe | 6.4 |
| Sol 5; Opus 8: `execfail` and the exit status | 4.1 (no `env -i` process), 4.7 (`exec … || handover_failed`); section 5's `EXIT` trap; row 39 |
| Sol 6: the Docker CLI against Podman | 7.1's route table |
| Sol 7; Opus 3: the probe directory | 4.6.3; rows 26b, 26c, 26d |
| Sol 8; Opus 12, 13, 15, 16: the harness, replay and rows | 9.1, 9.3, 9.4; rows 14, 19, 26 |
| Sol 9; Opus 17: the format history | 6.2 |
| Sol 10: nested wrappers; an absolute entrypoint | section 2's recursive walk; 4.1; row 9 |
| Sol 11; Opus 4: the passfile | 4.4; row 50 |
| Opus 6: the self-test's oracle | 4.4 |
| Opus 7: secrets on tmpfs | 4.1's `/dev/shm` |
| Opus 8: signals, subshells, Bash patterns, the tracked PID | 4.1, 4.3, 4.5; `interrupted` |
| Opus 9: unbounded waits | R15; row 35c |
| Opus 10: 13.2 settled; the help scan | 4.7 (by name, pinned `PATH`, no patch); `argument-ambiguous`; row 14c |
| Opus 11: `PGPORT` and the allowlist | R3's `server-environment`; 4.1's derived allowlist and guard; row 15b |
| Opus 14: the hook limit | 3.2; 7.3 |
| Opus 19: the Compose test | 7.1 |
| Opus 20: `key-value` stated | 4.2 |
| Opus 21: the placeholder `SET` | 4.4; 9.5 |

**Section 13 of revision 3, settled:**
1. **The printable-ASCII rule:** agreed by both reviewers. It is a recorded contract item (section 8).
2. **The upstream `$1` test:** by name with the pinned `PATH`, no patch.
3. **The lock's lifetime:** held for the server's life, with the premise corrected (4.9).
