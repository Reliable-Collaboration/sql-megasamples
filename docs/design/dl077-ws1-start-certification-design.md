# Workstream 1: PostgreSQL start certification, the design

**Status: design, revision 6, for round 6 of the design review. No build yet.**

This revision is consolidated: one ordered check list (section 3) and **one current row table** (section 10.2), replacing the inherited tables and change lists of revisions 3 to 5 (Opus round 5, 8; Sol round 5, 6). Section 13 traces round 5's findings.

**Design rounds so far:**

| Round | Reviewed | Reviews | Traced in |
|---|---|---|---|
| 1 | revision 1, `2ab72c25` | `sol-ws1-design.md`, `opus-ws1-design.md` | revision 2's section 11 |
| 2 | revision 2, `bd9c5f26` | `sol-ws1-design2.md`, `opus-ws1-design2.md` | revision 3's section 12 |
| 3 | revision 3, `32664450` | `sol-ws1-design3.md`, `opus-ws1-design3.md` | revision 4's section 13 |
| 4 | revision 4, `4c69e81b` | `sol-ws1-design4.md`, `opus-ws1-design4.md` | revision 5's section 14 |
| 5 | revision 5, `398a9c42` | `sol-ws1-design5.md` (7 P2, 2 P3), `opus-ws1-design5.md` (2 P2, 6 P3) | section 13 here |

**The decisions applied:**
- **DL-122, Q1 to Q6,** and the items DL-122 recorded for WS1.
- **Default 2 of the accepted design, [108-5]:** no published privileged key, even on loopback. The coordinator applied it in round 2.
- **DL-124 (a):** the image's client-authentication rules only.

**Scope:**
- the PostgreSQL image's wrapper (`engines/postgres/entrypoint-wrapper.sh`);
- its build (the Dockerfile and `megasamples image`'s PostgreSQL build);
- the `read_policy` extension's format;
- the image's HBA files;
- the healthcheck and the generated Compose test;
- the README's start and authentication sections;
- the upgrade route;
- their tests.

The MySQL image appears only in 8.4.

**Facts checked on the current image (`ce3b539fb522`), read-only:**
- its `pg_hba.conf` trusts the socket and both loopbacks, and requires `scram-sha-256` elsewhere;
- `/usr/bin/perl` is present, with `Digest::SHA` and `MIME::Base64`;
- `/usr/local/bin` holds the upstream entrypoint scripts and `gosu`;
- `megasamples/credentials.py`'s `pgpass()` escapes `\` and `:`;
- the Dockerfile runs, per database, `20-grants.sql` after the load; then `10-read-profile.sql` and `15-read-views.sql`; and, for templates, `30-template-grants.sql` and `20-grants.sql` again.

## 1. Decisions and where they are applied

| Decision | Where |
|---|---|
| DL-122 Q1: the private start, made exact | 5.3; R17 |
| DL-122 Q2: non-root refused first | R0 |
| DL-122 Q3: stable codes | section 6 |
| DL-122 Q4: format 2, exact marker, digest guard | section 7 |
| DL-122 Q5: an image `HEALTHCHECK`, one source | section 8 |
| DL-122 Q6: per-role states; nothing stale | 5.4; 5.6 |
| DL-122 recorded: one message per cause | 7.3 |
| DL-122 recorded: the MySQL image | 8.4 |
| DL-122 recorded: the contract at merge | section 9 |
| Default 2, [108-5]: no loopback trust | 4.1's HBA file |
| DL-124 (a): the image's rules only | section 4; R4, R8, R9, R10 |

## 2. Routes

**One operand-aware parser** reads the argument vector as `postgres`'s `getopt` does (3.1).

**Command words:**
- `argv[1]`;
- recursively, the word in command position after each recognised wrapper.

**Recognised wrappers:** `gosu`, `su-exec`, `runuser`, `su`, `sudo`, `env`, `setpriv`, `setsid`, `chroot`, `nice`, `ionice`, `nohup`, `timeout`, `stdbuf`, `taskset`, `exec`, `time`.

**Server words:** any name or path whose basename is `postgres`, `postmaster`, `pg_ctl`, `pg_ctlcluster`, `docker-entrypoint.sh`, `docker-ensure-initdb.sh` or `docker-enforce-initdb.sh`.

| Route | Recognised by | Outcome |
|---|---|---|
| Server start | `argv[1]`'s basename is `postgres`, or `argv[1]` begins with `-` | section 3, then section 5 |
| Informational | a start whose parsed options include `-C`, `--version`/`-V`, `--describe-config` or `--help`/`-?` | after R3: remove the run's state directory, clear the traps, `exec gosu postgres …` in the pinned environment. Its exit status is its own. |
| Server mode | `--single`, `--boot`, `--check` | R1: `server-mode` |
| Ambiguous argument | a token equal to an upstream help word but parsed as an operand (`postgres -k --version`) | R1: `argument-ambiguous` |
| Wrapped server | the walk reaches a server word; or `argv[1]` is a server word other than `postgres` | R1: `wrapped-server` |
| Other command | anything else | handed to the upstream entrypoint unchanged |

**Unchecked, and always unhealthy:** an unrecognised command word, a shell string, or a replaced entrypoint. Only the handover writes the endpoint (8.3).

## 3. The checks, in order

The first failure decides. **Before the lock (R0 to R6), nothing on the volume or in `/run` is touched.** A refusal there leaves a stale endpoint, private directories and volume exactly as they were (Sol round 5, 6).

| Step | Check | Fact | Refused with |
|---|---|---|---|
| S0 | The `EXIT` trap is armed. This run's state directory is made with `mktemp -d /dev/shm/megasamples-run.XXXXXX`. Without `/dev/shm` (`--ipc=none`), the wrapper writes `internal: /dev/shm unavailable` itself and exits 1. | — | `internal` |
| R0 | The wrapper runs as root | A | `non-root` |
| R1 | The route is a start or informational | B | `wrapped-server`, `server-mode`, `argument-ambiguous` |
| R2 | `argv[1]` is the image's `postgres` | B | `foreign-binary` |
| R3 | No loader variable; no environment name that is not an identifier (read from `/proc/self/environ`); no server-read variable the design does not honour (`PGPORT`, `PGOPTIONS`, `PGDATESTYLE`, `PGTZ`, `PGCLIENTENCODING`) | J | `loader-environment`, `server-environment` |
| — | Informational routes leave here | B | — |
| R4 | The image's HBA files are sound (4.2) | — | `hba-image` |
| R5 | The override keys are well formed (5.2) | F | `key-conflict`, `key-file`, `key-value` |
| R6 | `PG_VERSION` exists. `ENOENT` means `uninitialised`; any other error (`EACCES` under `--cap-drop ALL`, where root cannot traverse the `postgres`-owned 0700 directory) is `internal`, naming the step (Sol round 5, 6) | H | `uninitialised`; `internal` |
| L | The directory lock (5.9) | — | `volume-busy`; `internal` |
| C | With the lock held, the cleanup: the endpoint removed; `/run/megasamples-private` and `/run/megasamples-probe` recreated, owned by `postgres`, mode 0700; this run's private directory made by `mktemp -d /dev/shm/megasamples-private.XXXXXX`, owned by `postgres`, mode 0700 | — | `internal` |
| R7 | The marker is the image's own, exactly | H | `policy-marker` |
| — | slice 3's build-identity check (7.3) | — | slice 3's code |
| R8 | The volume's `pg_hba.conf` is the build's stock file (4.3) | H | `hba-volume` |
| R9 | No `hba_file` or `ident_file` argument, in any spelling, on any start (Sol round 5, 3; Opus round 5, 4) | B | `hba-argument` |
| — | The ownership repair | H | — |
| R10 | The server reports its configuration with the public arguments (`-C`, as `postgres`, in the pinned environment). The `hba_file` and `ident_file` it reports must be the stock `PGDATA` paths, which also catches a `config_file` or an include that sets them (4.3) | C, D | `config-unreadable`; `hba-config` |
| R11 | `data_directory` is `PGDATA`, and `PGDATA` is the locked directory (`stat -L /proc/self/fd/9`) | C | `data-directory` |
| R12 | No quoted preload entry | E | `preload-quoted` |
| R13 | `read_policy` is preloaded | D, E | `preload-missing` |
| R14 | `dynamic_library_path` is `$libdir` | E2 | `library-path` |
| R15 | No session or local preload | E | `preload-session` |
| R16 | `unix_socket_directories` parses as a list | G | `socket-settings` |
| R17 | With overrides set: no argument names `unix_socket_directories`, `port`, `data_directory` or `config_file` (3.1). The HBA names are already R9's. | F, C, G | `override-argument` |
| R18 | With overrides set: no `standby.signal` or `recovery.signal` | H | `recovery-mode` |
| R19 | With overrides set: the private launch's values discovered, validated and rechecked (5.3) | F, C, D | R10 to R16's codes, "the private launch" |
| — | The private phase (5.3 to 5.5), step P (5.8), the endpoint (8.3), the handover (5.7) | — | section 6 |

**The order between R8, R9 and R10:**
- R9 comes before R10, so `-c hba_file=/x` is always `hba-argument`.
- R10's query then carries only arguments that set no HBA name, so a `hba_file` it reports came from the files or from a `config_file` the arguments selected. That is `hba-config`, with its own remedy (4.3).

### 3.1 The parser and R17's backstop
- **The parser** reads `getopt` with attached values, `-c name=value` and `--name=value`, with `-` read as `_` and names case-folded.
- **R17's backstop:** `-C name` with and without the arguments must agree in status and value.

### 3.2 Stated, not refused
- **Any library the configuration or a superuser loads** can replace either hook, `ProcessUtility_hook` or `object_access_hook`, without chaining. That includes other preloads, `archive_library`, `oauth_validator_libraries` and `LOAD`.
- **Catalog-kept per-role or per-database settings** are not visible to `-C` and not overridden by pins.
- **Administrator-installed hooks** may inspect statements.
- **A path retargeted beneath `PGDATA` after R11.** The launches receive the pathname.
- **A loader variable acting on Bash itself** before the wrapper's first line.
- **Root in the container** (DL-124).

## 4. Client authentication: the image's rules only (DL-124)

### 4.1 The image's files
**`/etc/megasamples/pg_hba.conf`** is root-owned, mode 0644, in the root-owned directory `/etc/megasamples` (mode 0755). It is installed by the build from the repository file `engines/postgres/hba/pg_hba.conf`:

```
local  all          all  trust
local  replication  all  trust
host   all          all  all  scram-sha-256
```

**`/etc/megasamples/pg_ident.conf`** is empty, with the same owner and mode.

**The stock volume file.** `engines/postgres/hba/pg_hba.volume.conf` is fixed in the repository (Opus round 5, 3). The build installs it into the baked data directory with `install -o postgres -g postgres -m 0600`, replacing `initdb`'s output, and ships a copy at `/usr/share/megasamples/pg_hba.volume.conf`. Its content is the same three rules, under a comment saying the server does not read it. So a base-image update that changes `initdb`'s sample cannot change it.

**All three files are inside format 2's digest** (7.2).

**The public launch pins** `hba_file=/etc/megasamples/pg_hba.conf` and `ident_file=/etc/megasamples/pg_ident.conf`.

**The private launch pins its own `hba_file`.** It does not pin `ident_file`: no rule of its own uses a map, and PostgreSQL treats an unreadable ident file as a non-fatal error (Opus round 5, 8).

### 4.2 R4: the image's files are sound
R4 reads each image file with the same safe routine as R8. That is Perl opening it with `O_RDONLY|O_NOFOLLOW|O_NONBLOCK`, an `fstat` check that it is a regular file, and a 64 KiB bound (Opus round 5, 6). It then requires:
- **the bytes** to equal the build's constants, baked into the wrapper;
- **root ownership,** with no group or other write, on each file and on `/etc/megasamples`;
- **the same filesystem:** each file's `st_dev` must equal that of `/usr/share/megasamples`, which is in the image's layers. So a file bind-mounted over the path, even with stock bytes, is refused (Sol round 5, 9).

Any failure is `hba-image`.

**What remains:** a bind mount over the whole of `/etc/megasamples` with stock, root-owned files, edited after R4. **Certification of the image's HBA ends at R4**, and the README says so, beside DL-124's "an edit to a bind mount after start followed by a reload".

### 4.3 R8, R9, R10: a customised volume
**R8** reads `$PGDATA/pg_hba.conf` with the safe routine and compares it with `/usr/share/megasamples/pg_hba.volume.conf`. Any of these is `hba-volume`:
- a symlink;
- a FIFO;
- a directory;
- an unreadable file;
- a file over 64 KiB;
- different bytes.

**`hba-volume`'s sentence** says custom rules are unsupported in version 1. It says to save the file first, to restrict access outside the image instead, and gives the exact restore command with the actual volume path printed (`PGDATA` as the wrapper saw it). Run it on the stopped volume, with the deployer's own mount:

```
docker run --rm --entrypoint /bin/sh -v VOLUME:/var/lib/postgresql IMAGE -c \
  'rm -rf -- "$1" && cp -- /usr/share/megasamples/pg_hba.volume.conf "$1" \
   && chown postgres:postgres -- "$1" && chmod 0600 -- "$1"' \
  sh /var/lib/postgresql/18/docker/pg_hba.conf
```

`rm -rf` first removes a symlink, FIFO or directory without following it, and `cp` then makes a regular file (Opus round 5, 1; Sol round 5, 2).

**R9** refuses a `hba_file` or `ident_file` argument with `hba-argument`. The sentence says to remove the argument.

**R10's `hba-config`:** the files, `postgresql.auto.conf`, an include, or a `config_file` set `hba_file` or `ident_file`.
- **The sentence** names both settings and gives the command that removes them from `postgresql.conf` and `postgresql.auto.conf`:

  ```
  docker run --rm --entrypoint /bin/sh -v VOLUME:/var/lib/postgresql IMAGE -c \
    'sed -i -E "/^[[:space:]]*(hba_file|ident_file)[[:space:]]*=/d" -- "$1"/postgresql.conf "$1"/postgresql.auto.conf' \
    sh /var/lib/postgresql/18/docker
  ```

- **A setting in an include or another `config_file`** is the deployer's to remove, and the sentence says so.

**Rows 47 to 47f** run each documented remedy against every case it applies to.

### 4.4 Where a deployer restricts access, and what the README says
- **Restricting access happens outside the image:** publish on loopback only, limit the container network, use the host firewall, or tunnel for remote use.
- **Every TCP login needs a key.** `demo`'s is published, so reaching the port means reading the samples.
- **Not offered in version 1:** custom rules, `cert`, `gss`, `ldap` and TLS. A mounted `/etc/megasamples/pg_hba.local.conf` has no effect.
- **Reach:**
  - the `local` lines admit any process that can open the public socket: the container's own processes, and containers sharing the socket directory;
  - TCP, loopback included, needs a key, so `psql -h localhost` and sidecars do.
- **[110-2]'s text** says the same.

## 5. The start

### 5.1 The interpreter and the environments
- **`#!/bin/bash -p`.** The `ENTRYPOINT` is `["/usr/local/bin/entrypoint-wrapper.sh"]`.
- **Shell settings:** `set -euo pipefail`, `shopt -s inherit_errexit execfail`, and job control off.
- **Signals:** `TERM`, `INT`, `HUP` and `QUIT` are trapped explicitly.
- **Waits:** `wait "$pid" || status=$?`.
- **`PATH`** is pinned and exported first: `/usr/lib/postgresql/18/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`.
- **Absolute paths** for `postgres`, `psql`, `pg_isready`, `gosu`, `perl`, `flock`, `setsid` and `docker-entrypoint.sh`.

**The children's environment.** Each child the wrapper starts runs under `env -i` with `PATH`, `PGDATA`, `HOME=/nonexistent`, `LANG=C.UTF-8`, and `TZ` for the server. `psql` runs as `psql -X -w -v ON_ERROR_STOP=1`, naming its whole address.

**Two lists** (Sol round 4, 4; Opus round 4, 1; Sol round 5, 4):
- **the input list:** the names the wrapper reads;
- **the handover list:** exactly the variables the pinned upstream `docker-entrypoint.sh` references, plus the image's `ENV` (`PATH`, `PGDATA`, `PG_MAJOR`, `PG_VERSION`, `GOSU_VERSION`, `LANG`), plus `LC_*` and `TZ`, minus the denylist:
  - the six key names;
  - `PGPASSWORD`, `PGPASSFILE`;
  - `POSTGRES_HOST_AUTH_METHOD`;
  - every `POSTGRES_INITDB_*`.

**How the handover's environment is built:** the wrapper unsets every exported variable not on the handover list, skipping Bash's read-only names (`SHELLOPTS`, `BASHOPTS`, `BASH_VERSINFO`, `EUID`, `PPID`, `UID`), and then `exec`s directly.

**The guards:**
- **The handover list equals** the derivation exactly: upstream's references and the image's `ENV`, minus the denylist. That is equality, not coverage, so an unrelated addition fails.
- **No denylisted name** is on it.
- **The wrapper reads no name outside** the input list and the handover list.

**Checked twice:**
- **At the `exec` (shim):** the fake upstream entrypoint records its environment, and it must hold exactly the handover-list variables that were set, with no key and no source path.
- **In the postmaster (native, row 39b):** its `/proc/PID/environ` holds no key value and no `*_FILE` path. For each key route, direct and file:
  - upstream's `file_env`, as read from the pinned script, may export `POSTGRES_PASSWORD` with an empty default;
  - so the assertion is that any such variable present is empty;
  - a test of the pinned script pins that behaviour.

**The private files** (secrets, client stderr, the private server's log, the private HBA file) live in this run's `mktemp -d` directory under `/dev/shm`, owned by `postgres`, mode 0700 (Opus round 5, 5). The unique name means a second container sharing `/dev/shm` (`--ipc=host`, `shareable`, `container:`) cannot remove or recreate it.

**Before every `exec`, on success and on failure**, the wrapper removes:
- this run's private directory;
- this run's state directory (Sol round 5, 8; Opus round 5, 5).

### 5.2 The override keys
- **The keys:** `POSTGRES_PASSWORD`, `ADMIN_PASSWORD` and `DEMO_PASSWORD`, each also as `*_FILE`.
- **R5 refuses:**
  - **`key-conflict`:** a key set both ways;
  - **`key-file`:** an unreadable file;
  - **`key-value`:** a key that, after a file's trailing LF bytes are removed, is empty, longer than 1024 bytes, or holds a byte outside 0x20 to 0x7E.
- **The sentence** names the variable and the rule, never the value.
- **The same validated bytes** feed the verifier and the confirmation.
- **The README says:**
  - CRLF files are refused;
  - trailing spaces are kept;
  - an empty direct value, which today's wrapper treats as no override, is now refused;
  - Compose's `:-` defaults are unaffected.

### 5.3 The private start
**Its address:**
- the socket directory `/run/megasamples-private`;
- port `5432`;
- `listen_addresses` empty.

**Its HBA file,** `hba.conf` in this run's private directory, written by root, mode 0640, group `postgres`:

```
local  postgres     postgres  trust
local  megasamples  all       scram-sha-256
```

**Its values:**
1. **Discovered** by `-C` with no arguments.
2. **Validated** by R11 to R16.
3. **Built into an argv array** pinning `data_directory`, `listen_addresses=`, the socket directory, `port=5432`, the `hba_file`, the discovered preload, `dynamic_library_path=$libdir`, empty session and local preloads, and stderr logging.
4. **Rechecked** by `-C` with that array.

**The process:**
- **The trap is armed first.**
- **The server is launched** with `setsid` in the background. Its PID is tracked, and its stderr goes to the private directory.
- **Readiness:** `pg_isready` every second.
  - **0:** ready.
  - **1:** wait while the child lives, logging every 30 seconds (R18 has excluded standbys).
  - **2:** give up after 60 seconds in a row.
- **Once ready,** line 1 of `postmaster.pid` must equal the tracked PID, or `private-start`.

### 5.4 The passwords
**The order:** `postgres`, `admin`, `demo`, requested roles only.

**The verifier.** Perl computes it from the validated key on stdin:
- **the salt:** 16 bytes from `/dev/urandom`, length checked;
- **PBKDF2:** HMAC-SHA-256 with 4096 iterations, `hmac_sha256($data, $key)`;
- **the keys:** by RFC 5802;
- **encoding:** `encode_base64($x, '')`;
- **the output:** pattern-checked.

**The self-test.** The build runs a throwaway cluster in its own stage. There it sets a scratch role's password from a fixed key, with `password_encryption = 'scram-sha-256'`, and records the key and the server's `rolpassword`.
- **At every start with overrides,** Perl recomputes that verifier from the key and the recorded salt, and must match exactly. Otherwise `internal`, naming the self-test.
- **A build assertion:** the baked `pg_authid` holds only the image's roles.

**The rotation session:** one `psql` per role, in the background, `wait`ed. Its stdin:

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

**The confirmation.** A libpq sign-in as ROLE to `megasamples` on the private socket, with `require_auth=scram-sha-256`. The key comes from `pgpass` in the private directory: owned by `postgres`, mode 0600, the line `*:*:megasamples:ROLE:KEY` escaped as `credentials.pgpass()` does. It is removed at once.

**The state:**

| Observed | State |
|---|---|
| no `connected` | `unattempted` |
| `connected`, no `sending`, exit not by signal | `unattempted` |
| `applied`, confirmation succeeded | `applied` |
| `sending`, no `applied`, exit 3 | `refused` |
| `applied`, confirmation failed | `uncertain` |
| `sending` without `applied` and any other exit; any death by signal without `applied`; `applied`, then interrupted before the confirmation | `uncertain` |
| not run after an earlier failure | `unattempted` |

**After a failure:**
- the first non-`applied` result stops the sequence;
- the server is stopped;
- the wrapper exits with `password-setup`, logging each requested role's state.

**A retry converges.**

### 5.5 Supervision and the stop
- **Waits:** clients and the server run in the background and are `wait`ed.
- **The trap:**
  - terminates a running client;
  - sends `SIGINT` to the server's group, waits up to 60 seconds, then `SIGQUIT` for 10 seconds, then `SIGKILL`;
  - reaps the child.
- **Codes:** a forced stop is `private-stop`; a signal during the start is `interrupted`, with each role's state.
- **One refusal line,** then `also:` lines.
- **The refusal flag** is a file in this run's state directory. A lint check forbids `refuse` inside `$(…)`.

### 5.6 The probe needs no key
The probe connects as `demo`, to `megasamples`, on the dedicated probe socket, under the image's `local … trust` line. There is no passfile.

### 5.7 The handover
```
exec /usr/local/bin/docker-entrypoint.sh postgres ARGS PINS || handover_failed
```
- **`postgres` by name,** resolved through the pinned, exported `PATH`. Upstream is not patched. A build test asserts that `command -v postgres` gives the image's binary.
- **PINS:**
  - `data_directory`;
  - the certified preload;
  - `dynamic_library_path`;
  - empty session and local preloads;
  - the socket list (8.3);
  - the certified port;
  - `hba_file` and `ident_file` (4.1).
- **`handover_failed`** removes the endpoint, writes the `handover` line itself and exits 1. The trap has already been cleared and the run's directories removed.
- **Failures after the `exec`** (upstream's `exec gosu`, or `gosu`'s `exec postgres`) leave a dead PID in the endpoint, so the probe is unhealthy.

### 5.8 Slice 3's step P
- **Where it sits:** after R19, the passwords and the private stop; before the endpoint and the handover; on both branches.
- **What it does now:** nothing. `locked` is reserved for it.
- **The lock covers it.**
- **Until slice 3,** `postgres` and `admin` sign in over TCP with published keys whenever no override applies.
- **A release condition:** [110-2] holds at P on every route. T-23 checks it with missing, published, wrong and private keys, on both loopback families, with a retained volume `pg_hba.conf` carrying a loopback `trust` rule, which R8 refuses.
- **Under slice 3's seeding,** `uninitialised` narrows to a non-empty directory.

### 5.9 One start per volume, for the server's life
- **The lock:** after R6, `exec 9<"$PGDATA"`, then `flock -x -w 30 -E 75 9`.
  - **75:** `volume-busy`.
  - **Any other failure:** `internal`, with the error.
- **Held for the server's life:** descriptor 9 is inherited through the `exec`s, so the postmaster holds the lock. It is the only interlock between containers on one volume, because `postmaster.pid` gives none across PID namespaces.
- **No fallback:** the build's first native step checks that the lock survives the `exec`s; if it does not, the build stops and the design returns.
- **Requirements** (section 9):
  - `PGDATA` on a filesystem with local `flock` semantics (NFS needs `local_lock=flock`);
  - a read-only root needs `--tmpfs /run`;
  - a container needs `/dev/shm`.

## 6. Refusal lines and codes

**The line format:** `megasamples-start: refused: CODE: SENTENCE` on stderr.

**The `EXIT` trap** is armed at S0. For any wrapper-owned exit, it makes sure a coded line was written for this run (`internal` with the last step if none was), and that the exit status is 1. It removes this run's directories.

**The rules for codes:** codes are added, never renamed or removed. An unknown code is a refusal.

| Code | Step |
|---|---|
| `non-root` | R0 |
| `wrapped-server`, `server-mode`, `argument-ambiguous` | R1 |
| `foreign-binary` | R2 |
| `loader-environment`, `server-environment` | R3 |
| `hba-image` | R4 |
| `key-conflict`, `key-file`, `key-value` | R5 |
| `uninitialised` | R6 |
| `volume-busy` | L |
| `policy-marker` | R7 |
| `hba-volume` | R8 |
| `hba-argument` | R9 |
| `config-unreadable`, `hba-config` | R10 |
| `data-directory` | R11 |
| `preload-quoted` | R12 |
| `preload-missing` | R13 |
| `library-path` | R14 |
| `preload-session` | R15 |
| `socket-settings` | R16 |
| `override-argument` | R17 |
| `recovery-mode` | R18 |
| `private-start`, `password-setup`, `private-stop`, `interrupted` | the private phase |
| `handover` | 5.7 |
| `internal` | the catch-all |

**New in revision 6:** `hba-config`, split from `hba-volume` so it has its own remedy.

## 7. The policy format

### 7.1 The pair
- **The marker:** `2`.
- **The extension:** `read_policy` version `2`, with no upgrade script.
- **Format 2 also carries** the three HBA files of 4.1.
- **The wrapper's constants** are generated from `policy-format.json`: the marker, and the HBA files' bytes.
- **There is no pair 1 in the file.** Format 1 was never released. `policy-format.json` starts with pair 2, and its marker-1 volumes are refused by R7 (Opus round 5, 7).

### 7.2 The rule and its guard
**R7:** a regular file, not a symlink, holding exactly the image's value.

**The digest covers:**
- the extension (script, control, C source);
- the init SQL: `00-users.sql`, `10-read-profile.sql`, `15-read-views.sql`, `read-routine-names.sql`, `20-grants.sql`, `30-template-grants.sql` and `40-register-template.sql`;
- `megasamples/postgres_templates.py`;
- the three HBA files of 4.1;
- `engines/postgres/apply-database-policy.sh` (7.4);
- the Dockerfile's policy and HBA steps.

**The current-digest check:** the current files' digest must equal the current pair's recorded digest.

**Released, one definition** (Sol round 5, 5; Opus round 5, 7): a pair is released from the first revision on `main`'s first-parent history whose `policy-format.json` marks it `released: true`. That flag is set in the merge to `main`.
- **The guard walks** that history with `--first-parent`. From the first released revision on, the pair's digest must not change, and it must stay present and released.
- **Release tags:** every release tag must point at a commit on `main`'s first-parent history. The guard lists the tags and fails on any that does not. So a release cut elsewhere cannot freeze a format the walk never sees.
- **The test needs full history and fails on a shallow clone.**
- **Tested:**
  - an unreleased pair's digest edited: passes;
  - a released pair edited, deleted, or changed and changed back: fails;
  - a feature branch's intermediate digests merged: passes;
  - a tag off `main`'s first-parent history: fails;
  - a tagged release followed by an edit of the same pair: fails.

**Also checked:**
- the pair matches the control file, the Dockerfile's marker and the wrapper's constants;
- the built image's databases are at `extversion` `2`.

### 7.3 One message per cause
**The order:**
1. R7, the marker;
2. slice 3's identity check;
3. R8, the volume's HBA file.

So a volume from another build is reported as a marker or identity mismatch, never as `hba-volume`.

**The integration cases,** run when slice 3 adds its check:
- both mismatched: only `policy-marker`;
- the marker matching and the identity mismatched: slice 3's refusal.

**`up`'s U-3 preflight** reports `stale-image` without invoking the image.

### 7.4 The upgrade route (Sol round 5, 1; Opus round 5, 2)
**One script for both users.** `engines/postgres/apply-database-policy.sh DB [template]` applies the image's per-database policy in the build's order: `20-grants.sql`, `10-read-profile.sql`, `15-read-views.sql`, and, for a template, `30-template-grants.sql` and `20-grants.sql` again. The Dockerfile calls it, and so does the upgrade, so they cannot diverge. It is in the digest.

**The steps:**
1. **Keep the volume.**
2. **Start the image that made it,** with no TCP published.
3. **Dump each sample database as `postgres`** with `pg_dump -Fc`.
4. **Dump the roles** with `pg_dumpall --roles-only --no-role-passwords`, and keep the roles the current image lacks.
5. **Inspect the old policy** (DL-124): read `SELECT * FROM pg_hba_file_rules` on the old image. Custom rules are not carried over. Confirm equivalent protection outside the image (4.4) before exposing the new server.
6. **Start the current image on a fresh volume,** with overrides for every privileged key.
7. **Create the deployer roles** from step 4, as `postgres`. They have no passwords, and their memberships come as dumped.
8. **For each database, as `postgres`:**
   1. **List the archive** with `pg_restore -l`. The list keeps table definitions and data, and every object owned by `admin` or a deployer role. It drops:
      - **every `ACL` and `DEFAULT ACL` entry,** because an entry holds all of an object's grants and cannot be split;
      - the `read_policy` extension and its schema;
      - the event trigger;
      - `15-read-views.sql`'s views.
   2. **For the employees database,** drop `15-read-views.sql`'s two dependent views first.
   3. **Restore:** `pg_restore -L list --clean --if-exists --exit-on-error` into the baked database, so the archive's owners are kept.
   4. **Re-run** `apply-database-policy.sh DB`, in the build's order. It reapplies format 2's grants to every table, recreated ones included, and recreates the views.
   5. **Apply the deployer grants:** render the archive's `ACL` entries with `pg_restore -f - -L acl.list`, keep only the `GRANT` statements whose grantee is a step-4 role, and run them.
   6. **A database the image lacks** is created first, owned as dumped, and gets the same three steps.
9. **Verify, before TCP is opened:**
   - healthy;
   - the extension at version 2, and the report's exact ACL;
   - the retained edit present;
   - `demo`'s rights equal the image's, **including on a recreated, edited sample table**;
   - a table owned by a deployer role keeps its owner, and its grant to a second deployer role;
   - no privileged key from before the dump signs in.

**The README gives the steps.** The rehearsal runs on both marker-1 variants. Each has an edited sample table, a deployer-owned table granted to a second deployer role, and the employees database.

## 8. Health

### 8.1 One source
- **The script:** `/usr/local/bin/megasamples-healthcheck`, from `engines/postgres/healthcheck.sh`.
- **Who runs it:** the image's `HEALTHCHECK` and the generated Compose test both name it by absolute path.
- **Timings:** `healthcheck.json` is the source. The Compose generator reads it, the Dockerfile carries the same literals, and a guard test compares the JSON, the Dockerfile, the built image and Compose.
- **The README** names orchestrators that ignore an image `HEALTHCHECK`, and gives the probe command.

### 8.2 The build route (Sol round 5, 7)
**`megasamples image` always builds to a temporary tag**, `IMAGE-candidate-RANDOM`, then inspects it through the same endpoint.

| Client | Server | Build |
|---|---|---|
| Docker's CLI | Docker | no flag |
| Docker's CLI | Podman's socket | through the compatible API. If the inspect finds no `HEALTHCHECK`, the fallback `podman build --format docker` is used only when `podman info`'s graph root equals the socket's (`docker info`'s root directory). Otherwise the build is refused. |
| `podman` or the podman-docker shim | Podman | `--format docker` |

**Detection:** `docker --version` naming Podman is the shim. Otherwise `docker version -f '{{.Client.Platform.Name}}'`; a template error or an empty name means "not Podman's client".

**Only a candidate whose `Config.Healthcheck` is the expected one is tagged** as the requested tag. The candidate is then removed. On failure the candidate is removed and **an existing good tag is left untouched**, so the requested tag never names an image without the check.

**Tested on each route:**
- with an existing good tag;
- a forced failure;
- with distinct stores for `podman` and the socket.

### 8.3 The endpoint
- **The probe socket directory:** `/run/megasamples-probe`, recreated under the lock, owned by `postgres`, mode 0700.
- **The public socket list** is the certified list plus that directory, with no empty element.
- **The endpoint file,** `/run/megasamples-health.endpoint`, mode 0644, is written just before the `exec`. It records the PID, the probe directory, the port and `PGDATA`.
- **The probe checks:**
  1. `postmaster.pid` names the recorded PID, which is alive, and the recorded port;
  2. the probe socket exists;
  3. a connection there answers `t`.
- **A server that bound its ordinary socket but not the probe socket** is unhealthy: "probe socket missing".

### 8.4 The MySQL image
- **Version 1:** no image `HEALTHCHECK`.
- **The README** says the generated Compose file supplies a probe and a hand-run container has none, under a guard test.

## 9. The contract at merge to `main`

Each item below is recorded with an impact note, a conformance test and its unknown-value rule:
- **the refusal line format and codes:** an unknown code is a refusal;
- **the per-role states,** with `locked` reserved: an unknown state means the key is not known to be the requested one;
- **the format pair,** its digest, "released" as defined in 7.2, and the release-tag rule;
- **the image's rules only** (DL-124): the image's HBA files, `hba-volume`, `hba-config`, `hba-argument` and `hba-image`, and the two remedy commands;
- **the key rule:** printable ASCII, 1 to 1024 bytes, a file's trailing LF bytes removed;
- **the two environment lists,** and the refused server-read variables;
- **the image `HEALTHCHECK`,** and the Compose test that names it;
- **deployment requirements:**
  - `PGDATA` with local `flock` semantics;
  - `--tmpfs /run` under a read-only root;
  - `/dev/shm`;
- **the narrowing of `uninitialised`** under slice 3.

## 10. Coverage

### 10.1 Generation
`tests/gates/ws1_rows.py` generates the cases from the check list of section 3 and the fact tables. **The count comes from the generator**, and the runtime is measured at the build's first step.

- **(a) Admission refusals:** each step's failing values, with earlier steps passing. **Every refusal before the lock asserts the unchanged state** with stale files present: the endpoint, the `/run` directories, the private directories, and the volume byte for byte.
- **(a′) Pairs of co-reachable failures:** the earlier step's code wins.
- **(b) Starts:** 26 role and source assignments × L by position (188) × G and logging, crossed with L but not with each other (× 7): 1,316 cases.

**Where they run:**
- **The shim harness,** in a task-owned container of the image in the isolated store, with `SYS_ADMIN` and real root, and the fakes bind-mounted over the absolute paths. A preflight fails loudly.
- **The conformance replay of the fake `-C`,** by construction (revision 4's 9.4).
- **Real containers:** every row of 10.2.

### 10.2 The current row table
- **(A)** marks a refusal before any client runs.
- **(W)** marks a failure after work began.
- **"Unchanged"** means the endpoint, the `/run` and `/dev/shm` directories and the volume are as before, with stale ones present in the fixture.
- **Keys** are checked over password-authenticated TCP. For a row with no listener, they are checked on a separate start of the same fixture.

| Row | Facts | Outcome |
|---|---|---|
| 1 | base | start; the report true; the namespace hook refuses (42501, its message, fresh names) and the positive control succeeds; probe healthy, no ERROR, through the image's and Compose's check; `postgres` and `admin` on published keys until slice 3 |
| 2 | overrides all, direct | start; each key confirmed |
| 3 | overrides all, as `*_FILE`; and `POSTGRES_PASSWORD_FILE` with direct `DEMO_PASSWORD` | start; confirmed |
| 4 | `demo` only | start; `demo` new, others published |
| 5 | `argv[1]` the absolute path | start |
| 6 | options only (`-c work_mem=8MB`) | start |
| 7 | `postgres -k /run/postgres` | start; the probe uses `/run/megasamples-probe` |
| 8 | `psql -U postgres -h db`; `pg_dump -d postgres` | other command |
| 9 | (A) `gosu postgres postgres`; `env gosu postgres postgres`; `timeout 5 postgres`; `docker-entrypoint.sh -c x=y`; `pg_ctl start` | R1 `wrapped-server`; unchanged |
| 10 | (A) row 9's forms, and plain starts, under `--user postgres` and another uid | R0 `non-root`; unchanged |
| 11 | (A) `/tmp/postgres`; another binary named `postgres` | R2 `foreign-binary`; unchanged |
| 12 | a planted `postgres` earlier on an inherited `PATH` | start of the image's own binary |
| 13 | (A) `--single`, `--boot`, `--check` | R1 `server-mode`; unchanged |
| 14 | `--version`; `--describe-config`; `-C port`; `-c work_mem=8MB -C port`; `-Cport` | informational, exit 0; unchanged; no state directory left |
| 14b | `postgres -k -C` | a start with `-C` as `-k`'s operand |
| 14c | (A) `postgres -k --version` | R1 `argument-ambiguous`; unchanged |
| 15 | (A) `LD_PRELOAD`, `LD_LIBRARY_PATH`, `LD_AUDIT`; an entry named `BASH_FUNC_exec%%` | R3 `loader-environment`; unchanged |
| 15b | (A) `PGPORT`, `PGOPTIONS` | R3 `server-environment`; unchanged |
| 15c | an imported read-only `SHELLOPTS` or `BASHOPTS` | start (skipped by the unset loop) |
| 16 | (A) the image's HBA file replaced by a layer or bind mount (with stock bytes too), writable by `postgres`, or a FIFO there | R4 `hba-image`; unchanged |
| 17 | (A) a key both ways; an unreadable file; an empty key; a NUL in a file; a non-ASCII key; an overlong key; a CRLF file | R5 `key-conflict`, `key-file`, `key-value`; unchanged |
| 18 | (A) `PG_VERSION` missing | R6 `uninitialised`; unchanged |
| 18b | (A) `--cap-drop ALL` | R6 `internal`, naming the `PG_VERSION` lookup's `EACCES`; unchanged |
| 19 | (A) a second container on the same volume, held at each boundary, including the first's public run; and `docker exec … entrypoint-wrapper.sh postgres` inside a running container | `volume-busy`; the first start's keys in force; one postmaster; the first stays healthy |
| 19b | (A) an NFS-like `flock` failure (`EBADF`) | `internal`, naming the lock |
| 20 | (A) unmarked; marker `1` (both earlier builds); `3`; empty; a symlink; on a read-only mount; owned by another uid | R7 `policy-marker`; nothing written; ownership unchanged |
| 21 | (A) a volume `pg_hba.conf`: customised (a `local` rule requiring a key; a `hostssl` rule; a loopback `trust` rule); a symlink; a FIFO; a directory; over 64 KiB | R8 `hba-volume`, before either launch |
| 21b | the `hba-volume` restore command, run on each case of row 21 | each next start succeeds; a symlink's target is not written |
| 22 | (A) `-c hba_file=/x`, `--hba-file=/x`, `-c ident_file=/x`, with and without overrides | R9 `hba-argument` |
| 23 | (A) `hba_file` or `ident_file` in `postgresql.conf`, in `postgresql.auto.conf`, in an include, and in a file selected by `-c config_file=` | R10 `hba-config` |
| 23b | the `hba-config` command, run on the `postgresql.conf` and `postgresql.auto.conf` cases | each next start succeeds |
| 24 | a file mounted at `/etc/megasamples/pg_hba.local.conf` with a `trust` rule | start; no effect: `pg_hba_file_rules` shows only the image's three rules; loopback still needs a key |
| 25 | (A) `config_file` unreadable; a non-numeric `port` | R10 `config-unreadable` |
| 26 | (A) every data-directory spelling; a moving `config_file` or include | R11 `data-directory` |
| 27 | (A) a quoted preload | R12 `preload-quoted` |
| 28 | (A) `read_policy` missing from the file, `auto.conf`, `-c` or an include | R13 `preload-missing` |
| 29 | other libraries with `read_policy` | start |
| 30 | (A) `dynamic_library_path` changed | R14 `library-path` |
| 31 | (A) a session or local preload | R15 `preload-session` |
| 32 | (A) `unix_socket_directories` malformed | R16 `socket-settings` |
| 32b | an empty certified socket list | start; the list is just the probe directory; healthy |
| 32c | a stale probe directory with the wrong owner | recreated; healthy |
| 32d | the probe directory made unwritable by a fault | serves; probe unhealthy: "probe socket missing" |
| 33 | (A) overrides with any socket, port, data or `config_file` argument | R17 `override-argument` |
| 34 | (A) overrides with `standby.signal` or `recovery.signal` | R18 `recovery-mode` |
| 35 | (A) overrides, with a preload fixed by `-c` but missing from the files | R19 `preload-missing`, "the private launch" |
| 36 | overrides, and a persisted custom socket, port or `listen_addresses` | start; the rotation reached `/run/megasamples-private` port 5432; no other listener during it |
| 37 | (W) the first role refused | `password-setup`; `refused`, then `unattempted` |
| 37b | (W) a retry where the key already works and the `ALTER` is refused (fault) | `refused` |
| 38 | (W) a lost reply: the fault relay forwards the `ALTER`, waits for `CommandComplete`, then closes before forwarding it | `uncertain`; the new key signs in on a separate start |
| 39 | (W) the connection never opens (the relay refuses) | `unattempted` for all |
| 39b | overrides, direct and as `*_FILE` | the recorded handover environment holds exactly the handover list's set variables, with no key or path; the postmaster's `/proc/PID/environ` holds no key value or `*_FILE` path, and any `POSTGRES_PASSWORD` present is empty (upstream's default, pinned) |
| 40 | retry of row 38 | start |
| 41 | overrides under persisted `log_statement=all`, per-role `log_statement=all` and `debug_print_*=on`; and row 37 under each | no key or verifier in any log, `pg_stat_statements` or the container log |
| 42 | (W) the private start fails, or no response for 60 seconds | `private-start`; the child reaped |
| 42b | an unclean previous stop, a long recovery | start, after waiting |
| 43 | (W) a signal during the private phase, during a stalled client | `interrupted`, with each role's state; stopped and reaped |
| 44 | (W) a forced private stop | `private-stop` |
| 45 | (W) row 37, then a forced stop | `password-setup`, then `also: private-stop` |
| 46 | (W) the entrypoint unexecutable just before the handover | `handover`; the endpoint removed; no state or private directory left |
| 46b | (W) `gosu` removed after the private stop (fault layer); the server binary unexecutable after the private stop | a dead PID in the endpoint; unhealthy |
| 47 | the public server exits after starting | its own exit; probe unhealthy |
| 48 | an include replaced between certification and launch | start on the pinned values |
| 49 | (A) root, `/run` read-only; the self-test failing | `internal`, naming the step |
| 49b | (A) `--ipc=none` | `internal: /dev/shm unavailable` |
| 49c | two containers sharing `/dev/shm` (`--ipc=shareable` / `container:`) on different volumes, starting with overrides at once | both start; neither's private directory touched by the other |
| 50 | a second listener reachable through each inherited `PG*` variable and a planted `.psqlrc` | start; zero connections at the second listener |
| 50b | a second healthy server on a shared socket directory, and on another port | the probe does not report it |
| 51 | marked, other owner | start after the repair |
| 52 | a replaced entrypoint; a shell string; an unlisted wrapper | unchecked; always unhealthy |
| 53 | a hand-run container | the image `HEALTHCHECK` reports |
| 54 | loopback TCP, both families, as `postgres` and `admin`, no key or a wrong key, under Docker, pasta and rootlesskit | refused by SCRAM; the right key admitted |
| 55 | keys with `'`, `\`, `:`, `$`, `"`, `;`, leading and trailing spaces, 1024 bytes, and a 1024-byte key of only `:` and `\` | start; each confirmed |
| 56 | (W) a failed rotation, then a restart of the same container hitting an early lock error | the restart prints its own `internal` line |
| 57 | the private files read under the real uids | the private server reads `hba.conf`; the client reads `pgpass`, as `postgres` |
| 58 | the image build | the baked `pg_authid` holds only the image's roles; the stock volume `pg_hba.conf` equals the repository file |
| 59 | informational and handover `exec`s, repeated in one container | no state or private directory left behind |

### 10.3 Confirmed natively
- **The `psql` exit mapping,** by the fault relay;
- **the `dynamic_library_path` report;**
- **the precedence** of pins and session `SET`s;
- **the placeholder `SET`;**
- **the lock's inheritance;**
- **the loopback rows** under each network mode;
- **upstream's `file_env` default,** from the pinned script;
- **the image's HBA file:** `pg_hba_file_rules` shows exactly its three rules, with no error;
- **the upgrade rehearsal** on both marker-1 variants.

### 10.4 Reversals
- **Each step R0 to R19,** removed in turn, fails at least one row.
- **So does each mechanism:**
  - the pinned environment, `-p`, the handover list's equality guard, each pin, the HBA pins and R4's mount check;
  - the session `SET`s, `ON_ERROR_STOP`, the verifier's self-test, the confirmation with `require_auth`, `\warn`;
  - `setsid` and the tracked PID, the interruptible waits, the lock;
  - `execfail` with `||`, the directory cleanup before `exec`, the per-run `mktemp` names;
  - the endpoint checks;
  - the removed loopback lines;
  - the candidate tag in the build.

## 11. The build order
1. **The harness and the generator,** red against today's wrapper. First, the native lock-inheritance check (5.9).
2. **Routes, the parser,** S0 and R0 to R5.
3. **Format 2:** the marker, the extension, the HBA files, the digest and the release guard, `apply-database-policy.sh`. Then R6, the lock, the cleanup, R7 and R8.
4. **R9 to R19,** and the pins.
5. **The private phase.**
6. **Health:** the probe socket, the endpoint, the script, Compose, the timings, the candidate-tag build.
7. **The handover and step P.**
8. **Real rows,** faults, network modes, and the upgrade rehearsal.

## 12. The brief's inputs
As revision 3's section 11 (at `32664450`). Round 6 S6-6's loopback masking is closed by removing the trust lines and by the pinned `hba_file`.

## 13. Design round 5, traced

| Finding | Where answered |
|---|---|
| Opus 1; Sol 2: DL-124's restore command | 4.3: `rm -rf` then `cp`, `chown` and `chmod`, with the printed path; `hba-config` and its own command; rows 21b and 23b over every case |
| Opus 2; Sol 1: the upgrade loses the image's grants | 7.4: every `ACL` and `DEFAULT ACL` dropped; `apply-database-policy.sh` re-run in the build's order; deployer grants rendered from the archive; step 9 and the rehearsal |
| Opus 4; Sol 3: R7, R14 and row 48c's order | R9 before R10; `hba-argument` before any `-C` with arguments; `hba-config` from the files or a selected `config_file`; HBA names removed from R17; row 21 "before either launch" |
| Opus 7; Sol 5: "released" | 7.2's one definition, the tag rule and its two tests; 7.1's "no pair 1" |
| Sol 4: the handover test | 5.1's equality guard; the shim's recorded environment; row 39b with upstream's empty default pinned |
| Sol 6; Opus 8: rows against the order | section 3's unchanged state before the lock; R6's `EACCES` as `internal` (row 18b); one current table (10.2) |
| Sol 7: the build fallback | 8.2's candidate tag, the same-store condition, and the tests |
| Opus 3: the stock volume file | 4.1: a repository file, installed by the build, in the digest; row 58 |
| Opus 5: `/dev/shm` | 5.1's `mktemp -d` names; S0's `--ipc=none` line; the cleanup before `exec`; rows 49b, 49c, 59 |
| Opus 6: R4's safe read and ownership | 4.2 |
| Sol 8: the flag directory at `exec` | 5.1's cleanup; 5.7; rows 14, 46 and 59 |
| Sol 9: the first HBA read under a bind mount | 4.2's same-filesystem check; the stated limit for a mount over the whole directory |
| Opus 8: wording | the consolidated table; the private launch's `ident_file` (4.1); the typo and the heading, gone with the rewrite |
