# Workstream 1: PostgreSQL start certification, the design

**Status: design, revision 3, for round 3 of the design review. No build yet.**
- **Rounds 1 and 2:**
  - revision 1, at `2ab72c25`: `sol-ws1-design.md`, `opus-ws1-design.md`;
  - revision 2, at `bd9c5f26`: `sol-ws1-design2.md` (1 P1, 10 P2, 3 P3) and `opus-ws1-design2.md` (3 P2, 12 P3).

  Both reviewers found every round 1 finding answered. Section 12 traces each round 2 finding.
- **The coordinator's decision on the loopback trust lines:** remove them in WS1, under format 2. This applies default 2 of the accepted design, [108-5]: "No privileged account has a published password, even on loopback". It is not a new decision, so it does not go to the deciders.
- **From:** the brief, `dl077-ws1-start-certification.md` (rule, invariants I1 to I6, facts A to M, every input row), and DL-122's answers to its six owner questions (Q1 to Q6), with the items DL-122 recorded for WS1.
- **Scope:** the PostgreSQL image's wrapper (`engines/postgres/entrypoint-wrapper.sh`), its build (`engines/postgres/Dockerfile` and the build command), the `read_policy` extension's format, the baked `pg_hba.conf`, the healthcheck, the README's start section, and their tests. The MySQL image appears only in 7.4.

**Facts checked on the current image (`ce3b539fb522`), read-only:**
- the baked `pg_hba.conf` trusts the local socket and the IPv4 and IPv6 loopback, and requires `scram-sha-256` for every other host;
- `/usr/bin/perl` is present, with the core `Digest::SHA` and `MIME::Base64` modules;
- `/usr/local/bin` holds `docker-entrypoint.sh`, `docker-ensure-initdb.sh`, `docker-enforce-initdb.sh`, `gosu` and the wrapper.

## 1. Decisions this design applies

| Decision | What the design does |
|---|---|
| DL-122 Q1: keep the private start, made exact | 4.3: the private server, on its own socket, port and `hba_file`, with values discovered, validated and pinned. With overrides set, R14 refuses an argument that names a socket, port or data location. |
| DL-122 Q2: non-root refused first | R0 is the first check on every route but "other command". The README states that platforms forcing a non-root user are unsupported in version 1. |
| DL-122 Q3: a stable code per refusal | Section 5's codes, a fixed line format, and an `EXIT` trap that guarantees a coded line. Additions are allowed; an unknown code is a refusal. |
| DL-122 Q4: format 2, exact match, a digest guard | Section 6. The marker is checked before the repair and either launch. Each released pair is pinned to its digest. The upgrade route is specified and rehearsed. |
| DL-122 Q5: an image `HEALTHCHECK`, one source | Section 7. The build flag is chosen by engine detection, and the built metadata is inspected on both build routes. |
| DL-122 Q6: four per-role states, nothing stale | 4.4: the state comes from markers on unbuffered stderr, each key confirmed by a sign-in. 4.6: no passfile; the endpoint is identified to the serving process. |
| Default 2, [108-5]: no published privileged key, even on loopback | 4.6.1: the loopback `trust` lines are removed under format 2. |
| DL-122 recorded: one message per cause | 6.3. |
| DL-122 recorded: the MySQL image | 7.4. |
| DL-122 recorded: the contract at merge | Section 8. |

## 2. Routes: what counts as a server start

**One operand-aware parser** reads the argument vector, as `postgres`'s own `getopt` does (3.1). It finds command words and options with their operands. Both classification and R14 use it, so in `postgres -k -C`, `-C` is `-k`'s operand, not an option (Sol 12).

- **Command words:** `argv[1]`, and the word in command position after a recognised wrapper. Option values are never command words. `postgres` as a role or database name (`psql -U postgres`), or as part of a path (`-k /run/postgres`), is not a command word.
- **Server words:** any path or name whose basename is `postgres`, `postmaster`, `pg_ctl`, `pg_ctlcluster`, `docker-entrypoint.sh`, `docker-ensure-initdb.sh` or `docker-enforce-initdb.sh`.

| Route | Recognised by | Outcome |
|---|---|---|
| **Server start** | `argv[1]`'s basename is `postgres`, or `argv[1]` begins with `-` | R0, then section 3, then section 4. R2 refuses any `postgres` that is not the image's own path (Opus 4). |
| **Informational** | a server start whose parsed options include `-C` (as an option, not an operand), `--version`/`-V`, `--describe-config` or `--help`/`-?` | R0 to R3; then it runs as `postgres` in the pinned environment, and exits with its status. No listener, no password change, no endpoint. |
| **Server mode** | a server start with `--single`, `--boot` or `--check` | R0, then refused: `server-mode` |
| **Wrapped server** | `argv[1]` is a recognised wrapper (`gosu`, `su-exec`, `runuser`, `su`, `sudo`, `env`, `setpriv`, `setsid`, `chroot`, `nice`, `ionice`, `nohup`, `timeout`, `stdbuf`, `taskset`, `exec`, `time`) whose command word is a server word; or `argv[1]` is a server word other than `postgres` | R0, then refused: `wrapped-server` |
| **Other command** | anything else | Handed to the upstream entrypoint unchanged |

**Unrecognised command words are unchecked, and always unhealthy** (7.3):
- a shell string such as `sh -c "exec postgres"`;
- a wrapper not on the list;
- a script that later starts a server.

Only the wrapper's handover writes the endpoint (4.6), so a server started any other way is never healthy (Opus 4).

## 3. The checks, in order

The first check that fails decides. Section 9 generates the cases from this order.

| # | Check | Fact | Refused with |
|---|---|---|---|
| R0 | The wrapper runs as root (uid 0) | A | `non-root` |
| R1 | The route is a start or informational | B | `wrapped-server`, `server-mode` |
| R2 | `argv[1]` is `/usr/lib/postgresql/18/bin/postgres`, by name with `PATH` pinned, or by that path | B | `foreign-binary` |
| R3 | No loader variable is set: `LD_PRELOAD`, `LD_LIBRARY_PATH`, `LD_AUDIT` (a partial denylist, see 4.7 and 7.3) | J | `loader-environment` |
| — | Informational routes stop here and run | B | — |
| R4 | The override keys are well formed (4.2) | F | `key-conflict`, `key-file`, `key-value` |
| R5 | `PG_VERSION` exists in `PGDATA` | H | `uninitialised` |
| — | **The volume lock is taken** (4.9) | — | `volume-busy` |
| R6 | The marker is the image's own, exactly (section 6) | H | `policy-marker` |
| — | slice 3's build-identity check, when slice 3 adds it (6.3) | — | slice 3's code |
| — | The ownership repair | H | — |
| R7 | The server reports its configuration: `postgres ARGS -C …`, as `postgres`, in the pinned environment | C, D | `config-unreadable` |
| R8 | The public launch's `data_directory` is `PGDATA`, and `PGDATA`'s identity (`st_dev`, `st_ino`) is the one R6 saw | C | `data-directory` |
| R9 | Its preload list has no quoted entry | E | `preload-quoted` |
| R10 | It contains `read_policy` | D, E | `preload-missing` |
| R11 | `dynamic_library_path` is exactly `$libdir` | E2 | `library-path` |
| R12 | `session_preload_libraries` and `local_preload_libraries` are empty in files and arguments | E | `preload-session` |
| R13 | `port` is a number, and `unix_socket_directories` is a list | G | `socket-settings` |
| R14 | With overrides set: no argument names `unix_socket_directories`, `port`, `data_directory`, `config_file`, `hba_file` or `ident_file` (3.1's parser and backstop) | F, C, G | `override-argument` |
| R15 | With overrides set: the private launch's values are discovered from its base arguments, validated, and its final argument vector rechecked (4.3) | F, C, D | the same codes, with "the private launch" in the sentence |

### 3.1 The parser, and R14's backstop
- **The parser reads options as `postgres` does:**
  - `getopt` with attached values (`-k/x`, `-D/x`, `-p5433`, `-cname=value`);
  - `-c name=value` and `--name=value`, with `-` in a name read as `_`;
  - names compared case-insensitively.
- **R14's backstop:** for each named setting, `postgres -C name` with ARGS and without must agree, comparing both exit status and value. So a spelling the parser missed but the server reads is still caught.
- **R14's rows** are generated from the spelling matrix (section 9).

### 3.2 Stated, not refused
- **A later preload library that replaces a hook without chaining it.** This covers both hooks the extension installs, `ProcessUtility_hook` and `object_access_hook`.
  - **Why it is stated:** a pointer check would also flag libraries that chain correctly.
  - **Its signal:** none.
- **Per-role or per-database settings kept in the catalog** (`ALTER ROLE … SET session_preload_libraries`). `-C` cannot see them, and the command-line pins do not override them (correcting revision 2's 9.5).
- **Administrator-installed hooks that inspect statements** (a logging or auditing extension) could see the verifier in 4.4. Whoever installs one controls the server.
- **The README states all three.**

## 4. The start

### 4.1 The environment, and what reaches the wrapper
**The interpreter.** The wrapper starts as `#!/bin/bash -p`. Privileged mode makes Bash ignore `BASH_ENV` and `ENV` and import no functions from the environment, so no shell code runs before R0 (Sol 14).

**Stated limits** (README):
- a loader variable acts on Bash itself before the wrapper's first line;
- a mount or path replaced beneath `PGDATA` while the wrapper runs. R8 rechecks the directory's identity, which narrows that window but does not close it.

**The pinned environment.** Every process the wrapper starts (the `-C` reads, the private server, its clients, the verifier routine, the health probe) gets it:
- **`PATH`** is set first, to `/usr/lib/postgresql/18/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`, and exported;
- **absolute paths** for `postgres`, `psql`, `pg_isready`, `gosu`, `perl` and `docker-entrypoint.sh`;
- **`env -i`,** with only `PATH`, `PGDATA`, `HOME=/nonexistent` and `LANG=C.UTF-8`, and `TZ` for the server;
- **`psql -X -w`,** with every connection naming its socket directory, port, database and user, and `hostaddr` empty;
- **each client's stderr** goes to a private file in `/run/megasamples-private`. It never reaches the container log raw. The wrapper extracts the markers and the first error line (Sol 6).

**The handover's environment** is an allowlist (Opus 8). The handover runs `env -i` with:
- `PATH`;
- `PGDATA`;
- `LANG`, `LC_*` and `TZ`;
- the `POSTGRES_*` names the upstream entrypoint reads at an initialised cluster (`POSTGRES_USER`, `POSTGRES_DB`), and no key.

**What does not reach the public server:** the override keys, their `*_FILE` names, and any other variable (`OPENSSL_CONF`, `GCONV_PATH`, and the rest).

### 4.2 The override keys
- **The keys:** `POSTGRES_PASSWORD`, `ADMIN_PASSWORD` and `DEMO_PASSWORD`, each also in its `*_FILE` form.
- **R4 refuses:**
  - a key set both ways: `key-conflict`;
  - an unreadable `*_FILE`: `key-file`;
  - any key that is empty, contains a byte outside printable ASCII (0x20 to 0x7E), or is longer than 1024 bytes: `key-value`.
- **Reading:** a `*_FILE`'s bytes are read by the verifier routine directly (4.4), and its trailing newlines removed. Shell substitution would drop a NUL silently; the routine reads raw bytes, so a NUL is seen and refused.
- **Why printable ASCII only** (Sol 5; Opus 1): SASLprep, which libpq and the server apply before hashing, leaves such a key unchanged. So the verifier computed in 4.4 is exactly what any client's sign-in will hash. Wider keys can come later, with a port of PostgreSQL's `saslprep.c` and its fallback. The README says so.
- **"With overrides set"** means at least one key, in either form.

### 4.3 The private start
**Its address,** all explicit literals:
- the socket directory `/run/megasamples-private`, created fresh by root, owned by `postgres`, mode 0700;
- port `5432`;
- `listen_addresses = ''`, so no TCP.

**Its own `hba_file`,** written by root, mode 0640, group `postgres` (Sol 3; Opus 3):

```
local  postgres     postgres  trust
local  megasamples  all       scram-sha-256
```

So the rotation session signs in as `postgres` to database `postgres` without a key. Each confirmation (4.4) signs in to `megasamples` with the new key, by SCRAM. The volume's own `pg_hba.conf` is not read by the private server.

**Its values** come in three steps, with no circularity (Sol 4):
1. **Discover:** `postgres -D "$PGDATA" -C name`, with no arguments, for `data_directory`, `shared_preload_libraries`, `dynamic_library_path`, `session_preload_libraries` and `local_preload_libraries`. That is what the files say.
2. **Validate them** by R8 to R12. A failure here is row 29's "the private launch".
3. **Build the final argument vector:**

   ```
   argv = (/usr/lib/postgresql/18/bin/postgres -D "$PGDATA"
           -c "data_directory=$PGDATA" -c "listen_addresses="
           -c "unix_socket_directories=/run/megasamples-private" -c "port=5432"
           -c "hba_file=/run/megasamples-private/hba.conf"
           -c "shared_preload_libraries=$discovered_preload" -c "dynamic_library_path=\$libdir"
           -c "session_preload_libraries=" -c "local_preload_libraries="
           -c "log_destination=stderr" -c "logging_collector=off")
   ```

   It is an array, with no quoting by hand (Sol 4; Opus 7). Then it is **rechecked:** `-C` for each pinned name, run with `argv`, must return the pinned value.

**Process and supervision** (Sol 7; Opus 7):
- **The trap is armed first.**
- **The server is launched** with `setsid`, so it leads its own process group. Its PID is the wrapper's child. Its stderr goes to `/run/megasamples-private/server.log`, mode 0600, never on the volume.
- **Readiness:** `pg_isready` is run on the private address every second.
  - **Exit 0:** ready.
  - **Exit 1** ("rejecting connections", a recovery): keep waiting while the child lives, logging progress every 30 seconds. There is no time limit, so a large recovery is not killed into a restart loop.
  - **Exit 2** (no response): give up after 60 seconds in a row.
  - **The child exiting first:** `private-start`.

### 4.4 The passwords, one role at a time
**The order** is fixed: `postgres`, `admin`, `demo`. Only requested roles are applied.

**The verifier.** For each role, a Perl routine in the pinned environment computes the SCRAM-SHA-256 verifier:
- **its inputs on stdin:** the key, or the key file's path;
- **the salt:** 16 bytes from `/dev/urandom`, the read checked for length;
- **PBKDF2:** HMAC-SHA-256 with 4096 iterations, using `Digest::SHA::hmac_sha256($data, $key)` in that argument order;
- **the client and server keys,** by RFC 5802;
- **encoding:** `MIME::Base64::encode_base64($x, '')`, with no newline;
- **the output:** `SCRAM-SHA-256$4096:salt$stored:server`, matched against that pattern before use.

**The start-time self-test.** The build records a fixed key, a fixed salt and the verifier PostgreSQL's own sign-in accepted for them (6.2, in the build step). At every start with overrides, the routine recomputes that verifier first and must reproduce it exactly, or the start refuses with `internal`, naming the self-test.

**The rotation session,** one `psql` per role, run in the background and `wait`ed for (4.5), with stdin:

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

- **The markers** use `\warn`, to unbuffered stderr, so they cannot be lost to a pipe's buffer (Opus 5).
- **The session `SET`s** beat per-role, per-database and file settings. They include the debug parse, rewrite and plan routes (Sol 6; Opus 6).

**The confirmation.** After `applied`, a libpq sign-in as ROLE to `megasamples` on the private socket checks the key end to end, through the private `hba_file`'s SCRAM line. The key reaches libpq through a passfile written in `/run/megasamples-private` (mode 0600, removed at once), never in argv or the environment.

**The state:**

| Observed | State |
|---|---|
| no `connected` | `unattempted` (the connection never opened) |
| `connected`, no `sending`, exit not by signal | `unattempted` |
| `sending`, `applied`, and the confirmation succeeded | `applied` |
| `sending`, no `applied`, exit 3 | `refused` |
| `sending`, `applied`, and the confirmation failed | `uncertain` (the installed key does not sign in) |
| any death by signal without `applied`, or `sending` without `applied` with any other exit | `uncertain` |
| `applied` observed, then the wrapper interrupted before the confirmation | `uncertain` |
| not run, because an earlier role was not `applied` | `unattempted` |

**After the first role that is not `applied`:**
- no later role is attempted;
- the private server is stopped;
- the wrapper exits 1 with `password-setup`;
- one line per requested role is logged, name and state only.

**A retry with the same keys converges.**

### 4.5 Supervision and the private stop
- **Interruptible waits** (Sol 7). Every client and the server run in the background, and the wrapper `wait`s for them. A signal to the wrapper interrupts `wait`, so the trap runs promptly.
- **The trap:**
  - terminates a running client;
  - stops the server: `SIGINT` to its process group, then `wait` up to 60 seconds; `SIGQUIT`, up to 10 seconds; then `SIGKILL`;
  - reaps the child with `wait`. A PID read from `postmaster.pid` is never used.
- **A stop that needed `SIGQUIT` or `SIGKILL`** is `private-stop`.
- **One refusal line:** the first failure's code is the refusal line. A later failure adds `megasamples-start: also: CODE: …`.

### 4.6 Health: authentication and the endpoint

#### 4.6.1 The baked `pg_hba.conf` under format 2
**The build's `initdb` step writes it without the loopback trust lines** (the coordinator's decision; default 2):
- removed: `host all all 127.0.0.1/32 trust`, `host all all ::1/128 trust`, and the two `host replication … trust` lines;
- kept: `local all all trust` and `local replication all trust`, and `host all all all scram-sha-256` for every TCP client, loopback included.

**Their reach, stated** (README):
- **The `local` lines** admit any process that can open the public socket without a key. That means the container's own processes, and any container sharing the socket directory through a volume.
- **TCP, loopback included,** needs a key. That covers `psql -h localhost` inside the container, sidecars in a shared namespace, `--network host`, and rootless Podman's pasta, which may deliver host loopback as container loopback.
- **The README and [110-2]'s text** say so.

**Format.** The change is part of format 2: the `pg_hba` step is in the digest (6.2). A marker-1 volume keeps its own file and is refused by R6 anyway.

#### 4.6.2 The probe
- **How it connects:** as `demo`, to `megasamples`, on a dedicated probe socket, in the pinned environment.
- **What it relies on:** the public server's `local all all trust` line. A volume `pg_hba.conf` hardened to require a key on `local` makes the probe unhealthy. 7.2 says so, and row 47 shows it.
- **No passfile exists.**

#### 4.6.3 The endpoint, identified to the serving process (Sol 2)
- **The public launch pins a dedicated probe socket** in its socket list. 4.7 pins `unix_socket_directories` to the certified list plus `/run/megasamples-probe`, which is container-private and root-created. It also pins `port` to the certified port.
- **The endpoint file**, `/run/megasamples-health.endpoint`, is written just before the `exec`. It records:
  - the wrapper's PID, which is the postmaster's, because `exec` and the upstream entrypoint's `gosu` keep it;
  - the probe directory;
  - the port.
- **It is removed** first after R0, and again if the `exec` fails.
- **The probe checks three things:**
  - that `$PGDATA/postmaster.pid`'s PID equals the endpoint's, and that process is alive;
  - that its port line equals the endpoint's;
  - then it connects to `/run/megasamples-probe` at that port.
- **So** a second server on a shared socket directory, or on another port, cannot satisfy the probe.

### 4.7 The handover
```
exec env -i … /usr/local/bin/docker-entrypoint.sh /usr/lib/postgresql/18/bin/postgres ARGS PINS
```
- **PINS:**
  - `-c data_directory`;
  - `-c shared_preload_libraries` with the certified value;
  - `-c dynamic_library_path=$libdir`;
  - empty session and local preloads;
  - `-c unix_socket_directories` with the certified list plus `/run/megasamples-probe`;
  - `-c port` with the certified port.
- **The upstream entrypoint's `$1` test:** it sees the absolute path, so the image's `docker-entrypoint.sh` is adjusted to accept that path. Otherwise the wrapper passes `postgres` with the pinned, exported `PATH` (Opus 4). The build test asserts which.
- **`shopt -s execfail`:** a failed `exec` returns, the endpoint is removed, and the refusal is `handover`.
- **A public server that starts and then exits** fails with its own diagnostic, and the probe is unhealthy: the PID in the endpoint is dead.

### 4.8 Slice 3's step P (DL-110 [110-2])
- **Where P sits:** after R15 and the passwords and before 4.6.3's endpoint and the handover, on both branches.
- **In WS1, P does nothing.** Slice 3 puts [110-2] there, and the per-role log's fifth state, `locked`, is reserved (section 8).
- **The volume lock** (4.9) covers P.
- **Until slice 3,** `postgres` and `admin` sign in with their published keys over TCP whenever no override applies. That now includes loopback, which needs a key (4.6.1). It also includes Compose's `POSTGRES_PASSWORD:-root` default.
- **A version 1 release condition:** [110-2] holds at P on every start route. T-23 shows it on both loopback families, with missing, published, wrong and private keys, requiring authentication failures on a reachable listener (Sol 1).
- **Under slice 3's seeding,** `uninitialised` narrows to a non-empty directory without `PG_VERSION`.

### 4.9 One start per volume (Sol 8)
- **The lock:** after R5, the wrapper opens `$PGDATA/megasamples-start.lock` on file descriptor 9 and takes `flock -x` on it, waiting up to 30 seconds. Failing that, it refuses with `volume-busy`.
- **How long it is held:** file descriptor 9 has no close-on-exec, so the public postmaster inherits it and holds the lock for as long as it lives. The lock therefore covers:
  - R6 and the repair;
  - the private start, the passwords and the stop;
  - step P;
  - the handover;
  - the public server's whole life.
- **A second start** on the same volume waits or is refused. It never interleaves.
- **Confirmed natively, not assumed:** that file descriptor 9 survives `env -i`, `gosu` and the postmaster's own start, and keeps the lock held (row 49). If PostgreSQL closes it, the design falls back to holding the lock through the handover only, and states the interval left.

## 5. Refusal lines and codes

**The line format,** fixed at the freeze: `megasamples-start: refused: CODE: SENTENCE` on stderr, then exit 1. Codes are added, never renamed or removed, within version 1 (the accepted design's section 6, versioning). An unknown code is a refusal.

**The `EXIT` trap.** When the wrapper exits non-zero and no refusal line was written, the trap prints `internal` with the last step reached (Opus 9). This replaces revision 2's `ERR` trap.

| Code | Rule | Notes |
|---|---|---|
| `non-root` | R0 | |
| `wrapped-server` | R1 | |
| `server-mode` | R1 | |
| `foreign-binary` | R2 | |
| `loader-environment` | R3 | |
| `key-conflict`, `key-file`, `key-value` | R4 | `key-value` is new: empty, non-printable-ASCII or overlong |
| `uninitialised` | R5 | |
| `volume-busy` | 4.9 | new |
| `policy-marker` | R6 | |
| `config-unreadable` | R7 | |
| `data-directory` | R8 | |
| `preload-quoted` | R9 | |
| `preload-missing` | R10 | |
| `library-path` | R11 | |
| `preload-session` | R12 | |
| `socket-settings` | R13 | |
| `override-argument` | R14 | |
| `private-start` | 4.3 | |
| `password-setup` | 4.4 | |
| `private-stop` | 4.5 | |
| `handover` | 4.7 | |
| `internal` | the `EXIT` trap | for example a read-only `/run`, `gosu` without capabilities, or the verifier self-test |

## 6. The policy format: marker and extension version 2

### 6.1 The pair
- **The marker:** `2`, written by the build.
- **The extension:** `read_policy` version `2`, with `read_policy--2.sql` and no extension upgrade script.
- **Format 2 also carries the `pg_hba.conf` of 4.6.1.**
- **The wrapper's constant** is generated from `policy-format.json` at build.

### 6.2 The rule and its guard
**R6:** a regular file, not a symlink, holding exactly the image's value. Anything else is refused before the repair and either launch, and the volume is untouched.

**`engines/postgres/read-policy/policy-format.json`** lists every released pair with its digest. One SHA-256, in a fixed order, covers:
- **the extension:** script, control file and `read_policy.c`;
- **the init SQL:** `00-users.sql`, `10-read-profile.sql`, `15-read-views.sql`, `read-routine-names.sql`, `20-grants.sql`, `30-template-grants.sql` and `40-register-template.sql`;
- **the generator of `copy-roles.sql`:** `megasamples/postgres_templates.py`;
- **the Dockerfile's policy and `pg_hba` steps,** between `# policy:` markers (Opus 12).

**The tests:**
- **The current digest equals the current pair's recorded digest.**
- **A recorded pair never changes** (Sol 13; Opus 12):
  - for each entry, `git log -S'<entry text>' -- policy-format.json` finds the commits that touched it;
  - the oldest must record the same digest;
  - the test requires full history and fails on a shallow clone.
  - **Tested:** adding a pair, then rewriting its digest, fails.
- **The pair matches** the control file, the Dockerfile's marker write and the wrapper's constant.
- **An image test** requires `extversion` `2` in every database.
- **The verifier self-test's fixture** (a key, a salt, and the verifier the real server accepted for them) is recorded by the build: it sets a scratch role to the Perl routine's verifier, then signs in with the key through libpq. It is outside the digest: it records the routine, not the format.

### 6.3 One message per cause
- **The order:** slice 3's identity check sits after R6, before the repair and either launch. When both mismatch, only `policy-marker` appears.
- **The integration cases,** run when slice 3 adds its check:
  - both mismatched: only `policy-marker`;
  - the marker matching and the identity mismatched: slice 3's refusal.
- **`megasamples up`'s U-3 preflight** reports `stale-image` before invoking the image.

### 6.4 The upgrade route (Sol 9; Opus 13)
1. **Keep the volume.**
2. **Start the image that made it** on that volume, with no TCP published.
3. **Dump each sample database** with `pg_dump -Fc`, as `admin`.
4. **Dump the roles** with `pg_dumpall --roles-only --no-role-passwords`, and keep only roles the current image lacks. The baked roles are never replayed.
5. **Start the current image on a fresh volume,** with overrides for every privileged key.
6. **For each database:** `pg_restore --clean --if-exists --exit-on-error` into the baked database of the same name, as `admin`. A database the image lacks is created by `admin` first.
7. **Verify:**
   - the healthcheck is healthy;
   - an edit made before the dump is present;
   - `demo`'s rights equal the image's;
   - no privileged key from before the dump signs in;
   - TCP is opened only after these pass.

**The README gives the steps.** The test plan rehearses them once on a marker-1 volume made by `ce3b539fb522`, with a retained edit.

## 7. Health

### 7.1 One source
- **The probe script:** `engines/postgres/healthcheck.sh`, installed as `/usr/local/bin/megasamples-healthcheck`. It does 4.6.2 and 4.6.3, and succeeds only on `t`. A healthy probe logs nothing at ERROR.
- **The timings** live in `engines/postgres/healthcheck.json`:
  - **the Compose generator reads them;**
  - **the Dockerfile's `HEALTHCHECK` line carries the same values as literals,** because build arguments are not expanded there (Opus 14);
  - **a guard test compares** the literals, the JSON, the built image's `Config.Healthcheck` and the generated Compose service.
- **The build flag** (Sol 11):
  - `megasamples image` builds through `docker build`, against whichever engine answers;
  - Docker builds Docker-format images and has no `--format` option;
  - Podman's compatible build endpoint is asked for Docker format where `container_engine.podman()` says Podman answers;
  - the test builder's direct `podman build` passes `--format docker`.

  **On both routes, a test inspects the built image's `Config.Healthcheck`.**
- **The README** names orchestrators that ignore an image `HEALTHCHECK`.

### 7.2 What the probe reports
- **It reports:** the policy library loaded in the serving process this wrapper handed over to, at its dedicated socket.
- **It does not report:** a hook replacement (3.2), or whether TCP listens.
- **A volume `pg_hba.conf` requiring a key on `local`** makes the probe unhealthy, so such hardening is incompatible with the image's health signal (Sol 3; Opus 3).

### 7.3 Unchecked routes, and their signal

| Route | Detected? | Signal |
|---|---|---|
| A replaced entrypoint; an unrecognised command word; a shell string | no | always unhealthy: no endpoint |
| A later library replacing either hook | no | none, stated |
| Catalog-kept session or local preloads | no | none, stated |
| Code-loading variables other than R3's (`OPENSSL_CONF`, `GCONV_PATH`) | **not reached**: the handover's allowlist drops them | — |
| A loader variable acting on Bash before line 1 | no | stated |
| `PGDATA` replaced beneath a mount mid-start | narrowed by R8's identity check | stated |
| `read_policy` planted on `dynamic_library_path` | refused, R11; the report false (9.5) | the refusal |

### 7.4 The MySQL image
- **Version 1:** no image `HEALTHCHECK`.
- **The README** says the generated Compose file supplies a probe and a hand-run MySQL container has none, under a guard test.

## 8. The contract at merge to `main`

Each item below is recorded with an impact note, a conformance test and its unknown-value rule:
- **the refusal line format and codes:** an unknown code is a refusal;
- **the per-role states:** `applied`, `refused`, `uncertain`, `unattempted`, with `locked` reserved for slice 3. An unknown state means the key is not known to be the requested one;
- **the format pair** and its bump and append-only rules, including the `pg_hba` change of 4.6.1;
- **the key rule:** printable ASCII, 1 to 1024 bytes;
- **the image `HEALTHCHECK`,** its command and its timings;
- **the narrowing of `uninitialised`** under slice 3.

## 9. Coverage

### 9.1 The criterion, and how cases are generated
`tests/gates/ws1_rows.py` generates the cases from fact tables:
- **(a) Admission refusals:** each rule's every failing value, with all earlier checks passing at the base.
- **(a′) Pairs of co-reachable failures**, two checks failing at once, so a swapped precedence is caught (Sol 10). For each pair of rules (Ri, Rj) with i < j, both failing, the result must be Ri's code.
- **(b) Starts,** generated per requested role, each with its own source (Sol 10). For each subset of {`postgres`, `admin`, `demo`}, each role's source is direct or file. The other axes are:
  - G: default, persisted socket, persisted port, persisted `listen_addresses`;
  - L, by position: all applied; the k-th refused, lost, or never connected, for each k up to the subset's size;
  - logging: default, persisted `log_statement=all`, per-role `log_statement=all`, persisted `debug_print_parse=on`.

**Size:** about 75 (a), about 130 (a′) and about 1,700 (b), all run in the shim harness (9.3) in under a minute.

**Left out of the product, with the argument** (Opus 10):
- **J's non-loader values** (`PG*`, `.psqlrc`): `env -i` and `-X` make every client independent of them. One row (43) shows it per value.
- **The passing argument forms** (`-k`, `-c work_mem`, the absolute path, other libraries): they reach only the public launch, not the private one or the passwords. Each is one row against the base.

**On real containers** (isolated store, one at a time, a fresh volume per row):
- every row of 9.2;
- every fact value against the base;
- the named interactions: G × F, A × F, E2 × D, L × F, H × F, logging × L, and pasta and rootlesskit × loopback.

### 9.2 The decision table
- **"Old" and "new" keys** are checked over password-authenticated TCP. For a row with no listener, they are checked on a separate start of the same fixture.
- **(A)** marks an admission refusal: no client run, no key changed.
- **(W)** marks a failure after work began.

| Row | Facts | Outcome | Keys after | Endpoint | Listener |
|---|---|---|---|---|---|
| 1 | base | start; report true; the namespace hook refuses (42501, its message, fresh names); positive control; probe healthy, no ERROR; `postgres` and `admin` on published keys until slice 3 | published | written | yes |
| 2 | overrides all, direct | start; each key confirmed by sign-in | new | written | yes |
| 3 | overrides all, as `*_FILE`; and `POSTGRES_PASSWORD_FILE` with direct `DEMO_PASSWORD` | start | new | written | yes |
| 4 | `demo` only | start | `demo` new | written | yes |
| 5 | `argv[1]` the absolute path | start | as F | written | yes |
| 6 | options only | start | as F | written | yes |
| 7 | `postgres -k /run/postgres` | start; the probe uses `/run/megasamples-probe` | as F | written | yes |
| 8 | `psql -U postgres -h db`; `pg_dump -d postgres` | other command | — | — | — |
| 9 | (A) `gosu postgres postgres`; `timeout 5 postgres`; `docker-entrypoint.sh -c x=y`; `pg_ctl start` | `wrapped-server` | old | removed | no |
| 10 | (A) row 9, under `--user postgres` | `non-root` | old | — | no |
| 11 | (A) `--user postgres`; another uid | `non-root` | old | — | no |
| 12 | (A) `/tmp/postgres`; another binary named `postgres` by path | `foreign-binary` | old | removed | no |
| 12b | a planted `postgres` earlier on an inherited `PATH` | start of the image's own binary (`PATH` is pinned) | as F | written | yes |
| 13 | (A) `--single` / `--boot` / `--check` | `server-mode` | old | removed | no |
| 14 | `--version`; `--describe-config`; `-C port`; `-c y=z -C port`; `-Cport` | informational, exit 0 | old | removed | no |
| 14b | `postgres -k -C` | a start with `-C` as the socket operand, then section 3 | as F | as F | as F |
| 15 | (A) `LD_PRELOAD` / `LD_LIBRARY_PATH` / `LD_AUDIT` | `loader-environment` | old | removed | no |
| 16 | (A) a key both ways; an unreadable file; an empty key; a NUL in a file; a non-ASCII key; an overlong key | `key-conflict`; `key-file`; `key-value` | old | removed | no |
| 17 | (A) `PG_VERSION` missing | `uninitialised` | — | removed | no |
| 18 | (A) unmarked; marker `1` (both earlier builds); `3`; empty; a symlink; unmarked and owned by another uid | `policy-marker`, ownership unchanged | old | removed | no |
| 19 | (A) `config_file` unreadable | `config-unreadable` | old | removed | no |
| 20 | (A) every data-directory spelling (3.1); a moving `config_file` or include | `data-directory` | old | removed | no |
| 21 | (A) a quoted preload | `preload-quoted` | old | removed | no |
| 22 | (A) `read_policy` missing from the file, `auto.conf`, `-c` or an include | `preload-missing` | old | removed | no |
| 23 | other libraries with `read_policy` | start | as F | written | yes |
| 24 | (A) `dynamic_library_path` changed | `library-path` | old | removed | no |
| 25 | (A) session or local preload in a file or argument | `preload-session` | old | removed | no |
| 26 | (A) `unix_socket_directories` malformed; `port` not a number | `socket-settings` | old | removed | no |
| 27 | (A) overrides with any spelling of a socket, port or data argument | `override-argument` | old | removed | no |
| 28 | overrides, and a persisted custom socket, port or `listen_addresses` | start; the rotation reached `/run/megasamples-private` port 5432; no TCP and no persisted path or port had a listener during it | new | written | yes |
| 29 | (A) overrides, with a preload fixed by `-c` but missing from the files | `preload-missing`, "the private launch" | old | removed | no |
| 30 | (W) the first role refused | `password-setup`; `refused`, `unattempted` | old | removed | no |
| 31 | (W) the second role's reply lost: a fault relay on the private socket forwards the `ALTER` and closes before the reply | `password-setup`; `applied`, `uncertain`, `unattempted`. The committed change is witnessed by the new key signing in on a separate start | first new; second new; third old | removed | no |
| 32 | (W) the connection never opens (the fault relay refuses) | `unattempted` for all | old | removed | no |
| 33 | retry of row 31 | start | new | written | yes |
| 34 | overrides under persisted `log_statement=all`, per-role `log_statement=all`, and persisted `debug_print_parse`/`_rewritten`/`_plan=on`; and row 30 under each | the key and its verifier in no server log, `pg_stat_statements` or container log | as the row | — | — |
| 35 | (W) the private start fails, or no response for 60 seconds | `private-start`; the child reaped | old | removed | no |
| 35b | an unclean previous stop, a long recovery | start, after waiting while `pg_isready` says "rejecting" | new | written | yes |
| 36 | (W) the wrapper terminated during a password call, and during a stalled client | the client and the server stopped promptly; nothing listens | as applied | removed | no |
| 37 | (W) a forced private stop | `private-stop` | new | removed | no |
| 38 | (W) row 30, then a forced stop | `password-setup`, then `also: private-stop` | old | removed | no |
| 39 | (W) the `exec` fails | `handover` | as applied | removed | no |
| 40 | the public server exits after starting | its own exit; probe unhealthy (dead PID) | as applied | dead PID | no |
| 41 | an include replaced between certification and launch | start on the pinned values; report true | as F | written | yes |
| 42 | (A) root, `/run` read-only; `--cap-drop ALL`; the verifier self-test failing | `internal`, naming the step | old | — | no |
| 43 | a second listener reachable through each inherited `PG*` variable and a planted `.psqlrc` | start; zero connections at the second listener; the probe reports this server | new | written | yes |
| 43b | a second healthy server on a shared socket directory, and on another port | the probe does not report it (PID and port mismatch) | — | — | — |
| 44 | marked, other owner | start after the repair | as F | written | yes |
| 45 | a replaced entrypoint; a shell string; an unlisted wrapper | unchecked; always unhealthy | — | — | as started |
| 46 | a hand-run container | the image `HEALTHCHECK` reports | — | — | — |
| 47 | a volume `pg_hba.conf` requiring a key on `local` | with overrides: start (the private `hba_file` is used); probe unhealthy, as 7.2 states | new | written | yes |
| 48 | loopback TCP, IPv4 and IPv6, as `postgres` and `admin` with no key; with a wrong key; under Docker, rootless Podman with pasta, and with rootlesskit | refused by SCRAM; with the right key, admitted | — | — | yes |
| 49 | (A) a second start on the same volume, held at each boundary (after R6, during the passwords, between the stop and the handover, during the public run) | waits, then `volume-busy`; the first start's keys are the ones in force | first start's | first's | first's |
| 50 | keys with `'`, a backslash, leading and trailing spaces, 1024 bytes, `$`, `"` and `;` | start; each confirmed by sign-in | new | written | yes |

### 9.3 The shim harness
- **The seam is outside the image's reach** (Opus 2). The harness runs the wrapper in a user and mount namespace (`unshare -Urm`), mapping uid 0. Inside it:
  - the fakes are bind-mounted over the absolute paths: `postgres`, `psql`, `pg_isready`, `gosu`, `perl` and `docker-entrypoint.sh`;
  - `/run` and `PGDATA` are tmpfs.
- **The wrapper reads no seam variable.** A guard test checks that the built wrapper names no environment variable outside an allowlist.
- **Each fake records its calls.** Every row asserts:
  - the code or the start;
  - for (A) rows, no client;
  - for (W) rows, the states and the calls in order;
  - the endpoint;
  - no process left.

### 9.4 The fakes checked against the real server, by construction (Opus 11; Sol 10)
- **The recording:** during the shim run, the fake `postgres -C` records every query it answered, as (fixture files, ARGS, name), with its status and value. It covers both launch vectors and the rejected arguments.
- **The replay:** each query is replayed against the real `postgres -C` in a throwaway container of the image, on the same fixture files written into a scratch `PGDATA`, with no server started. Status and value must agree.
- **What the replay cannot check:** authentication, catalog-kept settings and listener binding. Real rows check those.

### 9.5 Confirmed natively
- **The `psql` exit mapping:** a connection that never opens gives `unattempted`; a reply dropped after `sending`, by the fault relay on the real socket, gives `uncertain`; a server error gives `refused`.
- **A planted `read_policy` on `dynamic_library_path`, with R11 disabled for the test:** the report is false.
- **Precedence:** command-line pins beat files and includes. Session `SET`s beat per-role logging.
- **The loopback rows (48)** under each network mode.
- **The upgrade rehearsal (6.4).**

### 9.6 Reversals
- Each rule R0 to R15 removed fails at least one row.
- So does each of these: the pinned environment, `-p` (privileged mode), the handover allowlist, each pin, the private `hba_file`, the session `SET`s, the verifier and its self-test, the confirmation sign-in, `\warn`, `setsid`, the interruptible waits, the lock, `execfail`, the endpoint's PID check, and the removed loopback lines.

## 10. The build order
1. The shim harness in its namespace, the row generator, and the conformance recording and replay. Red against today's wrapper.
2. Routes, the parser, and R0 to R4.
3. Format 2 (marker, extension, `pg_hba`) and its guard, then R5, the lock and R6 before the repair.
4. R7 to R15, discovery and the pins.
5. The pinned environment, the private start, the verifier, the passwords and the confirmation, supervision, the stop.
6. Health: the probe socket, the endpoint, the timings and the build flag.
7. The handover's allowlist and step P.
8. Real rows, faults, loopback under each network mode, and the upgrade rehearsal.

## 11. The brief's inputs, traced

| Input | Where |
|---|---|
| Round 1 S3; round 2 S2-2 | R6, R8; rows 18 and 20 |
| Round 3 S3-1, O3-1 | R7 to R10 by `-C`; 3.1; rows 20 to 22 |
| Round 4 S4-1 | R15; row 29 |
| Round 4 S4-7 | R9; row 21 |
| Round 4 O4-1 | R2, R0; rows 5, 11, 12 |
| Round 4 O4-4 | section 5; the repair after R6; row 44 |
| Round 4 S4-6/O4-2; round 5 S5-6/Opus P3-2 | 7.1; row 1 |
| Round 5 S5-3 (P2-3) | 4.3; row 28 |
| Round 5 S5-7 (P3-7) | R0; row 11 |
| Round 5 O5-3, O5-4 | section 5's sentences and 7.3, under the README guard |
| Round 6 S6-5 (P2-5) | 4.4 to 4.7; rows 30 to 40 |
| Round 6 S6-6, O6-1 | a fresh volume per row; keys over SCRAM TCP; loopback trust removed (4.6.1) |
| Round 6 O6-4, O6-P3-2 | R6 format 2; section 7; R11; 3.2; R1 |
| Round 7 O7-1 | 9.1 |
| Round 7 S7-1 | 4.7; section 2; 4.4; 4.6; rows 14, 31, 40 |
| Round 7 S7-8, O7-P3-3; round 8 S8-5 | row 1 and 9.3 |
| Round 7 S7-7/O7-P3-7; round 8 S8-6, O8-P3-3 | row 18; rows 31 and 32 |

## 12. Design round 2, traced

| Finding | Where answered |
|---|---|
| Sol 1 (P1), Opus 3: loopback trust | 4.6.1 (removed under format 2); 4.8's T-23 condition; rows 47 and 48 |
| Sol 2: endpoint identity | 4.6.3, 4.7; rows 40 and 43b |
| Sol 3: HBA the clients rely on | 4.3's private `hba_file`; 4.6.2; 7.2; row 47 |
| Sol 4, Opus 7: R15 without circularity; quoting; the private address | 4.3's three steps and argv array; row 28 |
| Sol 5, Opus 1: the verifier | 4.2's ASCII rule; 4.4's routine, self-test and confirmation; rows 16, 42, 50 |
| Sol 6, Opus 6: debug logging; raw client diagnostics; inspecting hooks | 4.4's `SET`s; 4.1's private stderr; 3.2; row 34 |
| Sol 7, Opus 7: cancellation; process group; recovery; native lost reply | 4.3, 4.5; rows 31, 35b, 36 |
| Sol 8: two starts on one volume | 4.9; row 49 |
| Sol 9, Opus 13: the upgrade recipe | 6.4 |
| Sol 10, Opus 10, Opus 11: generated coverage; conformance by construction; independence | 9.1, 9.4 |
| Sol 11: the build flag | 7.1 |
| Sol 12: `-C` as an operand; a real GUC | section 2's parser; rows 14 and 14b |
| Sol 13, Opus 12: the digest guard's history; full clone; the files | 6.2 |
| Sol 14: `BASH_ENV`; path replacement | 4.1's `bash -p` and limits; R8's identity check |
| Opus 2: the harness's seam | 9.3 |
| Opus 4: routes and R2; row 12; `PATH` to the handover; unlisted wrappers | section 2; rows 9, 12, 12b, 45; 4.7 |
| Opus 5: buffered markers | 4.4's `\warn`; the signal rule |
| Opus 8: the public server's environment | 4.1's handover allowlist; 7.3 |
| Opus 9: `ERR` versus `EXIT` | section 5's `EXIT` trap |
| Opus 14: `HEALTHCHECK` values | 7.1 |
| Opus 15: the cross-reference | removed with section 13 of revision 2 |

## 13. Points for round 3
1. **The printable-ASCII key rule** (4.2) refuses keys some deployers use. It is the coordinator's first option, and a SASLprep port can lift it later. Is the rule acceptable for version 1? It is a visible contract (section 8).
2. **The upstream entrypoint's `$1` test** (4.7). The design adjusts the image's copy of `docker-entrypoint.sh` to accept the absolute path. The alternative is to rely on the exported pinned `PATH`. The build test decides which, and the design takes the second if the upstream script already resolves its `$1` that way.
3. **The volume lock held for the public server's life** (4.9). It is inherited through `exec`, which also blocks a deliberate second server on the same volume. PostgreSQL's own `postmaster.pid` lock already refuses that, so the lock adds nothing harmful there.
