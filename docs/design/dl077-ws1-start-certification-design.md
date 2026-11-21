# Workstream 1: PostgreSQL start certification, the design

**Status: design, revision 2, for re-review by Sol and Opus before any build.**
- **Revision 1** was reviewed at `2ab72c25`: `sol-ws1-design.md` (1 P1, 8 P2, 3 P3) and `opus-ws1-design.md` (4 P2, 15 P3). Section 11 traces each finding to where this revision answers it.
- **From:** the brief, `dl077-ws1-start-certification.md` (its rule, invariants I1 to I6, facts A to M and every input row), and DL-122's answers to its six owner questions (Q1 to Q6) with the items DL-122 recorded for WS1.
- **Next:** once re-reviewed, it is built test-first in the order of section 10, then reviewed to two clean rounds.
- **Scope:** the PostgreSQL image's wrapper (`engines/postgres/entrypoint-wrapper.sh`), its build (`engines/postgres/Dockerfile` and the build command that runs it), the `read_policy` extension's format, the healthcheck, the README's start section, and their tests. The MySQL image appears only in 7.4.

**Facts checked for this revision, on the current image (`ce3b539fb522`), read-only:**
- the baked `pg_hba.conf` trusts the local socket and the IPv4 and IPv6 loopback, and requires `scram-sha-256` for every other host;
- `/usr/bin/perl` is present, with the core `Digest::SHA` and `MIME::Base64` modules;
- `/usr/local/bin` holds `docker-entrypoint.sh`, `docker-ensure-initdb.sh`, `docker-enforce-initdb.sh`, `gosu` and the wrapper.

## 1. Decisions this design applies

| DL-122 | What the design does |
|---|---|
| Q1: keep the private start, made exact | 4.3 runs the private server on an image-chosen socket and port, with the certified settings pinned on its command line. With overrides set, R14 refuses before any launch an argument that names a socket or data location. |
| Q2: non-root refused first | R0 is the wrapper's first check on every server route (section 2), before any other. The README states that platforms forcing a non-root user are unsupported in version 1. |
| Q3: a stable code per refusal | Every refusal line carries a code from section 5, including a catch-all `internal`. The codes are fixed at the freeze, additions are allowed, and a matcher treats an unknown code as a refusal. |
| Q4: format 2, exact match, a digest guard | Section 6: marker `2`, extension version `2`. Any other marker is refused before the ownership repair and before either server starts, with the volume untouched. A guard pins each released pair to its digest. 6.4 specifies and rehearses the upgrade route. |
| Q5: an image `HEALTHCHECK` from one source | Section 7: one script and one set of timings, used by the image and the generated Compose file. The build uses Docker format, and a test inspects the built image. |
| Q6: four per-role states, nothing stale | 4.4: each role's state comes from observed markers, not exit codes alone. 4.6: the probe needs no key, so there is no passfile to go stale. |
| Recorded: one message per cause | 6.3: the marker check comes first, then slice 3's build-identity slot; an integration case for each order. |
| Recorded: the MySQL image | 7.4: no image `HEALTHCHECK` in version 1; the README says the generated Compose file supplies one and a hand-run container has none, under a guard test. |
| Recorded: the contract at merge | Section 8, with impact notes, conformance tests and the unknown-value rules, including the reserved state for slice 3. |

## 2. Routes: what counts as a server start

The wrapper classifies its argument vector by **command words only**: `argv[1]`, and any later word in command position after a known wrapper. Option values are never command words. `postgres` as a role or database name (`psql -U postgres`, `pg_dump -d postgres`), or inside a path (`-k /run/postgres`), is not a command word.

| Route | Recognised by | Outcome |
|---|---|---|
| **Server start** | `argv[1]` is `postgres` by name, or `/usr/lib/postgresql/18/bin/postgres`, or begins with `-` | R0, then the checks of section 3, then section 4 |
| **Informational** | a server start with `-C` anywhere, attached (`-Cname`) or separate; or with `--version`/`-V`, `--describe-config` or `--help`/`-?` | R0 to R3; then the command runs as `postgres` with the pinned environment, and exits with its status. No listener, no password change. |
| **Server mode** | a server start with `--single`, `--boot` or `--check` | R0, then refused: `server-mode` |
| **Wrapped server** | `argv[1]` is a known wrapper (`gosu`, `su-exec`, `runuser`, `su`, `env`, `setpriv`, `chroot`, `nice`, `nohup`, `exec`, `time`) whose command word is a server word; or `argv[1]` is itself a server word other than a start (`pg_ctl`, `pg_ctlcluster`, `postmaster`, `docker-entrypoint.sh`, `docker-ensure-initdb.sh`, `docker-enforce-initdb.sh`) | R0, then refused: `wrapped-server` |
| **Other command** | anything else (`bash`, `psql …`, `pg_dump …`) | Handed to the upstream entrypoint unchanged. It starts no server through this image's checks. |

**Server words** are `postgres`, `postmaster`, `pg_ctl`, `pg_ctlcluster` and the upstream entrypoint scripts, by name or by any path resolving to them.

**R0 runs first on every route but "other command",** so a non-root wrapped start reports `non-root`, as Q2 requires.

**What is not detectable, and stated (7.3):**
- a server started inside a shell string (`sh -c "exec postgres"`);
- an "other command" that later starts a server (a script, `bash` followed by a typed command);
- a replaced entrypoint.

## 3. The checks, in order

The first check that fails decides. So each later fact matters only when every earlier check passed, which is what makes section 9's pruned product small.

| # | Check | Fact | Refused with |
|---|---|---|---|
| R0 | The wrapper runs as root (uid 0) | A | `non-root` |
| R1 | The route is a start or informational, not a wrapped server or server mode | B | `wrapped-server`, `server-mode` |
| R2 | `argv[1]` resolves to `/usr/lib/postgresql/18/bin/postgres` (by absolute comparison; `PATH` is pinned first) | B | `foreign-binary` |
| R3 | No loader variable is set: `LD_PRELOAD`, `LD_LIBRARY_PATH`, `LD_AUDIT` | J | `loader-environment` |
| — | Informational routes stop here and run (section 2) | B | — |
| R4 | The override keys are well formed (4.2): not both `X` and `X_FILE`; each `_FILE` readable and non-empty; no key containing a NUL | F | `key-conflict`, `key-file` |
| R5 | `PG_VERSION` exists in `PGDATA` | H | `uninitialised` |
| R6 | The marker is the image's own, exactly (section 6) | H | `policy-marker` |
| — | **slice 3's build-identity check, when slice 3 adds it** (6.3) | — | slice 3's code |
| — | The ownership repair, as the upstream entrypoint makes it | H | — |
| R7 | The server can report its configuration: `postgres ARGS -C …` as `postgres`, with the pinned environment | C, D | `config-unreadable` |
| R8 | The public launch's `data_directory` is `PGDATA` | C | `data-directory` |
| R9 | Its preload list has no quoted entry | E | `preload-quoted` |
| R10 | It contains `read_policy` | D, E | `preload-missing` |
| R11 | `dynamic_library_path` is exactly `$libdir` | E2 | `library-path` |
| R12 | `session_preload_libraries` and `local_preload_libraries` are empty | E | `preload-session` |
| R13 | `unix_socket_directories` names at least one directory, and `port` is a number | G | `socket-settings` |
| R14 | With overrides set: no argument names a socket, port or data location (`unix_socket_directories`, `port`, `data_directory`, `config_file`, `hba_file`, `ident_file`, by the parser of 3.1) | F, C, G | `override-argument` |
| R15 | With overrides set: the private launch's exact options (4.3) pass R7 to R13, read by `-C` with those options | F, C, D | the same codes; the sentence says "the private launch" |

**Changes from revision 1:**
- **R0 is first** (Q2), and R1 uses command words only (Opus 2; Sol 4).
- **R5 and R6 run before the ownership repair.** R6 reads `$PGDATA/megasamples-read-policy` as root and needs no `-C`. A refused volume is not re-owned (Opus 3). R8 still confirms `data_directory = PGDATA` after the repair.
- **New checks:** R3 (Opus 8), R4 (Opus 4), R12 (Opus 9) and R13 (port and socket, Sol 4; Opus 7).

### 3.1 R14's parser
R14 parses the arguments as `postgres` does (Opus 6).
- **The option forms:**
  - `getopt` with attached values (`-k/x`, `-D/x`, `-p5433`, `-cname=value`);
  - `-c name=value` and `--name=value`, with `-` in a name read as `_`, and names compared case-insensitively.
- **The backstop:** for each named setting, `postgres -C name` with ARGS and without must agree. A spelling the parser missed but the server reads is still caught.
- **The rows** are generated from this spelling matrix (section 9).

### 3.2 Stated, not refused
- **A later preload library that replaces a hook without chaining it.** This applies to both hooks the extension installs, `ProcessUtility_hook` and `object_access_hook` (Sol 12).
  - **Why stated:** a check on the hook pointers would also flag every library that chains correctly, `pg_stat_statements` among them (Opus's corrected reason). Whoever can set `shared_preload_libraries` already controls the server; the guide says the policy is not a sandbox against administrators.
  - **Its signal:** none. The report stays true. The README says so.
- **Per-role or per-database settings kept in the catalog** (`ALTER ROLE … SET session_preload_libraries`) are not visible to `-C`. R12 covers only the configuration files and arguments. The README states it beside the hook limit (Opus 9).

## 4. The start

### 4.1 The environment the wrapper's own processes get
**Applies to every process the wrapper starts:** the `-C` reads, the private server, its client and the health probe (Sol 1, 5; Opus 8).
- **`PATH`** is set at the top of the wrapper to `/usr/lib/postgresql/18/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`.
- **Absolute paths** for `postgres`, `psql`, `pg_isready`, `gosu` and `docker-entrypoint.sh`.
- **Each child** runs under `env -i` with only:
  - `PATH`;
  - `PGDATA`;
  - `HOME=/nonexistent`;
  - `LANG=C.UTF-8`;
  - for the server, `TZ` if set.

  So no inherited `PG*` variable reaches libpq: `PGHOSTADDR`, `PGHOST`, `PGPORT`, `PGSERVICE`, `PGSERVICEFILE`, `PGOPTIONS`, `PGPASSFILE`, `PGSSL*` and `PGTARGETSESSIONATTRS`. Nor does any `PGOPTIONS` reach the server.
- **`psql`** always runs with `-X` (no `.psqlrc` from the volume, which is `postgres`'s home) and `-w` (never prompts).
- **Every connection names its whole address:**
  - the socket directory, as `host=/run/megasamples-private`;
  - `port`;
  - `dbname=postgres`;
  - `user=postgres`;
  - `hostaddr=` set empty.
- **Authentication** is the baked `local all all trust` line, on a socket directory only root and `postgres` can enter.

### 4.2 The override keys
- **The keys:** `POSTGRES_PASSWORD`, `ADMIN_PASSWORD` and `DEMO_PASSWORD`, each with its `*_FILE` form, as the upstream image documents (Opus 4).
- **A `*_FILE` value** is the file's content with trailing newlines removed, as the upstream entrypoint reads it.
- **Refusals:** a key set both ways is `key-conflict`. An unreadable or empty file is `key-file`.
- **"With overrides set"** means at least one key, in either form.
- **The values** are held only in the wrapper's memory and unset before the handover.

### 4.3 The private start
- **Its socket directory:** `/run/megasamples-private`, removed and created fresh by root, owned by `postgres`, mode 0700.
- **The launch:** the wrapper's own child, started directly, not through `pg_ctl`, so its PID is known from the moment it is launched (Sol 7):

  ```
  postgres -D "$PGDATA" -c data_directory="$PGDATA" -c listen_addresses='' \
    -c unix_socket_directories=/run/megasamples-private -c port=$CERTIFIED_PORT \
    -c shared_preload_libraries='$CERTIFIED_PRELOAD' -c dynamic_library_path='$libdir' \
    -c session_preload_libraries='' -c local_preload_libraries='' \
    -c log_destination=stderr -c logging_collector=off
  ```

  It runs as `postgres`, in the pinned environment. Its stderr goes to `/run/megasamples-private/server.log`, mode 0600, never on the volume (Sol 8; Opus 1).
- **Bound to what was certified** (Sol 2; Opus 7):
  - The certified values are the data directory, the preload list, the library path and the port. They come from R15's `-C` reads, made with these same options.
  - They are pinned on the command line, which beats every configuration file, include and `postgresql.auto.conf`.
  - So a file replaced between certification and launch cannot change what the private server loads. The public launch is pinned the same way (4.7).
- **The trap is armed before the launch.** It kills the recorded PID's process group on any exit (4.5).
- **Readiness:** `pg_isready` on the private address, up to 60 seconds.
  - A timeout, or the child exiting first, is `private-start`. The trap then stops the child.
  - The last line of `server.log` goes into the refusal's sentence, after passwords are scrubbed from it (none should be there; 4.4).

### 4.4 The passwords, one role at a time

**The order** is fixed: `postgres`, `admin`, `demo`. Only requested roles are applied.

**Each role** gets its own `psql` call, in the pinned environment, on the private address, with `ON_ERROR_STOP`. The script arrives on standard input:

```
\echo megasamples-connected
SET log_statement = 'none'; SET log_min_error_statement = 'panic'; SET log_min_duration_statement = -1;
SET log_min_duration_sample = -1; SET log_statement_sample_rate = 0; SET log_transaction_sample_rate = 0;
SET log_parameter_max_length_on_error = 0; SET pg_stat_statements.track_utility = off;
\echo megasamples-sending
ALTER ROLE "ROLE" PASSWORD 'SCRAM-SHA-256$4096:…';
\echo megasamples-applied
```

**Keeping the key out of the server** (Sol 8; Opus 1):
- **The wrapper computes the SCRAM-SHA-256 verifier itself** with Perl's core `Digest::SHA` (PBKDF2 with HMAC-SHA-256, 4096 iterations, a random 16-byte salt). It sends only the verifier, so the plaintext never reaches the server.
- **The session `SET`s keep even the verifier out of the log.** Session settings beat per-role and per-database settings (`ALTER ROLE postgres SET log_statement = 'all'`), the files and `-c`, and `pg_stat_statements`' record of utility statements. A `SET` of a setting whose module is not loaded only creates a placeholder, and is harmless.
- **The value** is passed in the script on standard input, never in argv, and never echoed: `-X` has no `\set ECHO`.

**A role's state comes from the markers `psql` printed and from its exit,** not from the exit alone (Sol 8; Opus 16):

| Observed | State | Meaning |
|---|---|---|
| no `megasamples-connected` | `unattempted` | The connection never opened, so nothing was sent. |
| `connected`, but no `sending` | `unattempted` | The session failed before the `ALTER` was sent. |
| `sending` and `applied`, exit 0 | `applied` | Confirmed. |
| `sending`, no `applied`, exit 3 | `refused` | The server returned an error to the `ALTER`, and the key is unchanged. |
| `sending`, no `applied`, any other exit or a signal | `uncertain` | The `ALTER` may have run. |
| not run, because an earlier role was not `applied` | `unattempted` | Unchanged. |

**After the first role that is not `applied`:**
- no later role is attempted;
- the private server is stopped;
- the wrapper exits 1 with `password-setup`.

**The log:** one line per requested role, name and state only: `megasamples-start: password ROLE STATE`.

**The keys stay as applied** (Q6). A retry with the same keys converges: each role's statement sets that key again, under a fresh salt.

### 4.5 The private stop
- **Signals:** `SIGINT` (fast shutdown) to the recorded PID, then `wait` up to 60 seconds; then `SIGQUIT`, wait up to 10 seconds; then `SIGKILL` to the process group.
- **The exit is verified by `wait`** on the child itself. A PID read from `postmaster.pid` is never used.
- **On any wrapper exit,** including a signal, the trap runs this.
- **A stop that needed `SIGQUIT` or `SIGKILL`** is `private-stop`, and there is no handover.

**One line when two things fail** (Sol 7; Opus 17):
- The refusal line carries the **first** failure's code.
- A later failure on the same exit adds one log line: `megasamples-start: also: CODE: …`, which is not a refusal line.
- So `password-setup` followed by a forced stop shows `password-setup`, then `also: private-stop`.

### 4.6 Health without a key
**The probe needs no password.**
- **How it connects:** over the public server's Unix socket, in the pinned environment, as `demo`, under the baked `local … trust` line.
- **So:** there is no health passfile, and nothing can be stale or partial after a failure. This meets Q6's passfile clause by construction (Sol 6; Opus 12).

**The endpoint:** the certified socket directory and port are written at handover to `/run/megasamples-health.endpoint`.
- It is removed first, right after R0, on every server route. So a start that fails at any later step leaves no endpoint.
- The probe reads it. Without it, or with nothing listening there, the probe is unhealthy.
- **Binding:** a second listener cannot satisfy the probe for this server. The probe reaches only this container's own socket path, and the endpoint names the certified port (Sol 5).

**Socket-only starts** (`listen_addresses = ''`) are probed the same way and can be healthy. Health means the serving process has the policy, not that TCP is open.

**Stated limit, shared namespace** (Opus 12):
- The baked `pg_hba.conf` trusts the IPv4 and IPv6 loopback for every role.
- Any process sharing the container's network namespace can sign in as `postgres`: a sidecar in a pod, or the host under `--network host`.
- The README states this. Whether the loopback trust lines should be removed is raised as review point 12.1, a security-posture question.

### 4.7 The handover

`exec docker-entrypoint.sh postgres ARGS PINS`:
- **PINS** are the same command-line pins as 4.3, for the public launch: `-c data_directory`, `-c shared_preload_libraries` with the certified value, `-c dynamic_library_path='$libdir'`, and empty session and local preloads.
- **It runs with `shopt -s execfail`**, so an `exec` that cannot run returns to the wrapper, which refuses with `handover` (Sol 6).
- **A public server that starts and then exits** (a port in use) is the server's own failure: its diagnostic, its exit, and no listener. It is not a wrapper refusal and has no code. The endpoint file names a socket where nothing listens, so the probe is unhealthy.

### 4.8 Slice 3's pre-public-launch step (DL-110 [110-2])

**Where it sits:** WS1 defines one step, P, after R15 and the passwords and before 4.6's endpoint and the handover, **on both branches**: with overrides, after the private stop; without overrides, before the handover (Sol 3; Opus 15).

**What happens there:**
- **In WS1, P does nothing.**
- **Slice 3 puts [110-2] there:** each account still on its published password is named, and each privileged account is kept locked while its key is missing or published.
  - Slice 3 bakes privileged accounts with no usable password ([110-2], G-35p). So P can lock without a private start on the no-override branch, or run one if slice 3 needs it.
  - The per-role log gains a fifth state, `locked` (published or missing key, kept locked), reserved now (section 8).

**Until slice 3:**
- `postgres` and `admin` sign in over TCP with their published keys whenever no override applies.
- That includes the generated Compose file's `POSTGRES_PASSWORD:-root` default, which applies the published value as an override.
- Row 1 and the README say so.

**A version 1 release condition:** [110-2] holds at step P on every start route, shown by T-23 with missing and explicitly published privileged keys, on loopback too. DL-110 permits `demo`'s published key on a hand-run image.

**R5 under slice 3:**
- Slice 3's "an empty volume it seeds" changes what a volume without `PG_VERSION` means. An empty data directory is seeded, not refused.
- `uninitialised` stays the code for a non-empty directory without `PG_VERSION`. Section 8 records the narrowing.

## 5. Refusal lines and codes

**The line format,** fixed at the freeze: `megasamples-start: refused: CODE: SENTENCE`, on stderr, then exit 1.
- **The sentence** says what was found and what to do. It may improve; the code may not change meaning.
- **Codes:** added, never renamed or removed, within version 1 (the accepted design's section 6, versioning; Opus 19's cross-reference). A matcher treats an unknown code as a refusal.

| Code | Rule | The sentence says |
|---|---|---|
| `non-root` | R0 | the wrapper must run as root inside the container; platforms that force a non-root user are unsupported in version 1; rootless Podman is unaffected |
| `wrapped-server` | R1 | the server must be the command, not wrapped or started by another tool |
| `server-mode` | R1 | single-user, bootstrap and check modes are not started by this image |
| `foreign-binary` | R2 | only this image's postgres runs |
| `loader-environment` | R3 | the loader variable found |
| `key-conflict` | R4 | the key set both directly and as a file |
| `key-file` | R4 | the key file that is unreadable or empty |
| `uninitialised` | R5 | the data directory has no cluster |
| `policy-marker` | R6 | the marker found (absent, or its value) and the image's own; the volume is untouched; the upgrade route (6.4) |
| `config-unreadable` | R7 | the server could not report its configuration, with its first error line |
| `data-directory` | R8 | the data directory resolved, and that it is not `PGDATA` |
| `preload-quoted` | R9 | a quoted preload entry |
| `preload-missing` | R10 | the preload list found, and which launch (public, or "the private launch") |
| `library-path` | R11 | the `dynamic_library_path` found |
| `preload-session` | R12 | the session or local preload found |
| `socket-settings` | R13 | the socket directory or port found |
| `override-argument` | R14 | the argument that names a socket, port or data location |
| `private-start` | 4.3 | the private start failed or timed out, with its log's last line |
| `password-setup` | 4.4 | the first role that was not `applied`, and its state |
| `private-stop` | 4.5 | the private server needed a forced stop |
| `handover` | 4.7 | the upstream entrypoint could not be executed |
| `internal` | an `ERR` trap | the step that failed unexpectedly (a read-only `/run`, `gosu` without its capabilities, a failed `mkdir`), so no failure leaves a line without a code (Opus 11) |

**Fact K's root cases** come out as follows:
- a read-only `/run`: `internal` at the step that writes it;
- `--cap-drop ALL`: `internal` at `gosu`, not a misleading `config-unreadable`. R7 runs `gosu` first and maps its own failure to `internal`.

## 6. The policy format: marker and extension version 2

### 6.1 The pair
- **The marker:** `$PGDATA/megasamples-read-policy` holds `2` and a newline, written by the build.
- **The extension:** `read_policy` at version `2`.
  - The script is `read_policy--2.sql`; the control file's `default_version` is `'2'`.
  - **No extension upgrade script** from `1`: version 1 never shipped, and a marker-1 volume is moved by the upgrade route of 6.4, not migrated in place (Q4).
- **The wrapper's own expected value** is one constant, read from the same `policy-format.json` at build time and baked into the wrapper (Opus 13).

### 6.2 The rule
- **R6:** a regular file, not a symlink, whose whole content is exactly the image's value.
  - Anything else is refused before the ownership repair and before either server starts: absent, `1`, `3`, empty or unreadable.
  - The volume is not touched at all.
- **Any later change** to a guarded file bumps both the marker and the version together.

**The guard** (Sol 10; Opus 13). `engines/postgres/read-policy/policy-format.json` lists every released pair with its digest: one SHA-256 over these files, in a fixed order.
- **The extension:**
  - `read_policy--N.sql`;
  - `read_policy.control`;
  - `read_policy.c`, because its SQL-callable symbols are what a volume's catalog names, round 5's class.
- **The init SQL that shapes what `demo` and the roles may do:**
  - `00-users.sql` (the roles and their memberships);
  - `10-read-profile.sql`, `15-read-views.sql`, `read-routine-names.sql`, `20-grants.sql`, `30-template-grants.sql`;
  - `40-register-template.sql` (its template tag, which the C code matches).
- **The Dockerfile's policy step:** the lines between its `# policy:` markers.

**The tests:**
- **The current pair's digest must equal the recorded digest.** So changing a guarded file fails until a new pair is recorded.
- **A recorded pair's digest may never change.** For each pair, the test reads the commit that added it (`git log --diff-filter=A -S`) and requires the same digest. So refreshing the digest under the same pair fails.
- **The pair must match** the control file's `default_version`, the Dockerfile's marker write and the wrapper's constant.
- **An image test** requires the built image's databases to have `read_policy` at version `2`, from `pg_extension.extversion`.

### 6.3 One message per cause
- **The order:** slice 3's build-identity check sits immediately after R6 and before the ownership repair and either launch (Sol 11).
- **When both mismatch,** only `policy-marker` appears. The cause is the same, another build's volume, and its sentence names the upgrade route.
- **The integration cases,** run when slice 3 adds its check:
  - a volume with both mismatches yields only `policy-marker`;
  - a matching marker with a mismatched identity reaches slice 3's refusal.
- **`megasamples up`'s U-3 preflight** reports `stale-image` before invoking the image at all. So under `up`, a stale volume shows U-3's refusal, and the image's marker check is not reached. The image's R6 is what a hand-run or direct Compose start meets.

### 6.4 The upgrade route, specified and rehearsed
For a volume refused with `policy-marker` (Opus 14):
1. **Keep the volume.** R6 has not touched it.
2. **Start the image that made it**, the build whose marker it carries, on that volume.
3. **Dump each database** with that image's `pg_dump`, plus the roles with `pg_dumpall --roles-only`.
4. **Start the current image on a fresh volume.**
5. **Restore the dumps.** The current image's event trigger and policy apply as objects are created.
6. **Verify:** the healthcheck is healthy, an edit made before the dump is present, and `demo`'s rights match the image's.

The README gives these steps. The test plan rehearses them once on a marker-1 volume made by round 9's image (`ce3b539fb522`).

## 7. Health

### 7.1 One source
- **The script:** `engines/postgres/healthcheck.sh`, copied to `/usr/local/bin/megasamples-healthcheck`.
  - It reads `/run/megasamples-health.endpoint`.
  - It runs `psql -X -w` in the pinned environment over that socket and port, as `demo`, with `SELECT pg_catalog.megasamples_policy_loaded()`.
  - It succeeds only on `t`, and a healthy probe logs nothing at ERROR (I6).
- **The timings** (interval, timeout, retries, start period) are in one file, `engines/postgres/healthcheck.json`. Both users read it:
  - the Dockerfile's `HEALTHCHECK` is generated from it at build;
  - the Compose generator reads the same values.

  A guard test compares the built image's `Config.Healthcheck` with the generated Compose service (Opus 18).
- **The Podman build format:** the image is built with `--format docker`, passed by `megasamples image`'s PostgreSQL build command (`megasamples/engines/postgres/__init__.py`'s build) and by the test builder. Docker ignores the flag. A test inspects the built image's `Config.Healthcheck` and fails if it is missing.
- **The README** says that orchestrators which ignore an image `HEALTHCHECK` (Kubernetes) need their own probe, and gives the command.

### 7.2 What the probe reports
- **The policy library is loaded in the serving process,** at this container's certified socket and port (4.6).
- **It does not report** a later hook replacement (3.2), nor whether TCP listens.

### 7.3 Unchecked routes, and their signal (I5)

| Route | Detected? | Its signal |
|---|---|---|
| A replaced entrypoint | no | the healthcheck, when the replacement starts a server without the policy |
| A server started inside a shell string, or by an "other command" | no | the healthcheck |
| A later library that replaces either hook without chaining | no | none, and stated |
| Per-role or per-database session or local preloads | no | none, and stated |
| `read_policy` planted on `dynamic_library_path` | refused, R11; the report would answer false (9.5) | the refusal |
| Loader variables | refused, R3 | the refusal |

### 7.4 The MySQL image
- **Version 1:** no image `HEALTHCHECK`. MySQL has no policy library to report on.
- **The README** says that the generated Compose file supplies a probe and a hand-run MySQL container has none, under a guard test (Sol 12; Opus 18).
- It can be added later from the same one-source pattern.

## 8. The contract at merge to `main`

These are recorded, each with a consumer impact note, a conformance test, and its unknown-value rule (DL-122):
- **The refusal line format and codes** (section 5). Unknown rule: an unknown code is a refusal.
- **The per-role log states** (4.4): `applied`, `refused`, `uncertain`, `unattempted`, and **`locked` reserved for slice 3**'s [110-2]. Unknown rule: an unknown state means the role's key is not known to be the requested one (Opus 15).
- **The policy format pair** `2`/`2`, and the bump and append-only rules (section 6).
- **The image `HEALTHCHECK`,** its command and its timings (7.1).
- **The narrowing of `uninitialised`** under slice 3's seeding (4.8).

## 9. Coverage

### 9.1 The criterion
**By precedence.** Because the first failing check decides (section 3), the cases are:
- **(a) Admission refusals:** for each rule, its every failing value, with every earlier check passing at the base.
- **(b) Starts:** every combination of the facts that act after all checks pass.

**The base row:** root, `postgres`, `PGDATA`, the baked preload, marker 2, no overrides, the default port and socket.

**The pruned product, generated by `tests/gates/ws1_rows.py` from the fact tables** (Opus 16):

| Part | Facts | Values | Cases |
|---|---|---|---|
| (a) | each rule R0 to R15, by its failing values (section 9.2's refusal rows, with R14's spelling matrix of 3.1, 24 spellings) | — | about 70 |
| (b) | F (none, `postgres` only, `admin` only, `demo` only, two, all) × key source (direct, file) × G (default, persisted custom socket, persisted port, persisted `listen_addresses`) × L (all applied, first refused, second refused, second's reply lost, connection never opened) × logging (default, persisted `log_statement=all`, per-role `log_statement=all`) | 6 × 2 × 4 × 5 × 3 | 720, less the impossible ones (L with no overrides; key source with no overrides), about 600 |

**Where they run:**
- **In the shim harness, all of them:** about 670 cases, in seconds. The harness is the wrapper with recording fakes on `PATH` for `postgres -C`, `postgres` (as a process), `pg_isready`, `psql`, `gosu` and `docker-entrypoint.sh`.
- **On real containers,** in the isolated store, one at a time, with a fresh volume per row:
  - every row of 9.2;
  - every value of every fact against the base;
  - the named interactions: G × F, A × F, E2 × D, L × F, H × F, and logging × L (where a failure would log the statement).

### 9.2 The decision table

**How a row is checked:**
- "Old" and "new" keys are checked over password-authenticated TCP, never the trusted loopback.
- For a row that ends with no listener, the keys are checked on a **separate** start of the same fixture, after proving the failed launch left no listener (Sol 9).
- **(A)** marks an admission refusal: no `psql` was run and no key changed.
- **(W)** marks a failure after work began: its keys are as stated.

| Row | Facts (the rest as the base) | Outcome | Keys after | Endpoint | Listener |
|---|---|---|---|---|---|
| 1 | base | start; report true; namespace hook refuses an out-of-namespace create (42501, the hook's message, fresh names); positive control succeeds; probe healthy with no ERROR logged. **`postgres` and `admin` sign in with their published keys until slice 3** | published | written | yes |
| 2 | base, overrides all, direct | start | new | written | yes |
| 3 | overrides all, as `*_FILE` | start | new | written | yes |
| 4 | overrides `demo` only | start | `demo` new, others published | written | yes |
| 5 | `argv[1]` the absolute path of postgres | start | as F | written | yes |
| 6 | options only (`-c work_mem=8MB`) | start | as F | written | yes |
| 7 | `postgres -k /run/postgres` | start; socket in `/run/postgres`; endpoint names it | as F | written | yes |
| 8 | `psql -U postgres -h db`, `pg_dump -d postgres` | other command, passed through | — | — | — |
| 9 | (A) `gosu postgres postgres`; `docker-entrypoint.sh -c x=y`; `pg_ctl start` | `wrapped-server` | old | removed | no |
| 10 | (A) as row 9, under `--user postgres` | `non-root` | old | — | no |
| 11 | (A) `--user postgres` (overrides some); another uid | `non-root` | old | — | no |
| 12 | (A) another binary named postgres; a planted `postgres` earlier on `PATH` | `foreign-binary` | old | removed | no |
| 13 | (A) `--single` / `--boot` / `--check` | `server-mode` | old | removed | no |
| 14 | `--version`, `--describe-config`, `-C x`, `-c y=z -C x`, `-Cx` | informational, exit 0, its output | old | removed | no |
| 15 | (A) `LD_PRELOAD` / `LD_LIBRARY_PATH` / `LD_AUDIT` set | `loader-environment` | old | removed | no |
| 16 | (A) `POSTGRES_PASSWORD` and `POSTGRES_PASSWORD_FILE` both; an unreadable or empty `*_FILE` | `key-conflict`; `key-file` | old | removed | no |
| 17 | (A) `PG_VERSION` missing | `uninitialised` | — | removed | no |
| 18 | (A) unmarked; marker `1` (both earlier builds); `3`; empty; a symlink; and an unmarked volume owned by another uid | `policy-marker`; **ownership unchanged** | old | removed | no |
| 19 | (A) `config_file` unreadable | `config-unreadable` | old | removed | no |
| 20 | (A) `-D`, `--pgdata`, `-c data_directory`, every spelling of 3.1, a `config_file` or `include` moving it | `data-directory` (or `config-unreadable` where the server rejects the option) | old | removed | no |
| 21 | (A) a quoted preload entry | `preload-quoted` | old | removed | no |
| 22 | (A) `read_policy` missing from the baked file, `auto.conf`, `-c` or an include | `preload-missing` | old | removed | no |
| 23 | with other libraries, `read_policy` among them | start | as F | written | yes |
| 24 | (A) `dynamic_library_path` changed | `library-path` | old | removed | no |
| 25 | (A) `session_preload_libraries` or `local_preload_libraries` set in a file or argument | `preload-session` | old | removed | no |
| 26 | (A) `unix_socket_directories = ''` | `socket-settings` | old | removed | no |
| 27 | (A) overrides, and any spelling of a socket, port or data argument (3.1) | `override-argument` | old | removed | no |
| 28 | overrides, and a persisted custom socket, port or `listen_addresses` | start; the change landed on the private server; nothing listened on the persisted path or port, or on TCP, during it | new | written | yes |
| 29 | (A) overrides, with a preload fixed by `-c` but missing from the files | `preload-missing`, "the private launch" | old | removed | no |
| 30 | (W) the first role refused | `password-setup`; `refused`, then `unattempted` | old | removed | no |
| 31 | (W) the second role's reply lost (fault) | `password-setup`; `applied`, `uncertain`, `unattempted` | first new; second either; third old | removed | no |
| 32 | (W) the connection never opens (fault) | `password-setup`; `unattempted` for all | old | removed | no |
| 33 | a retry of row 31 with the same keys | start | new | written | yes |
| 34 | overrides, with persisted `log_statement=all`, or per-role `log_statement=all`; and row 30 under each | the synthetic key and its verifier appear in no server log, `pg_stat_statements` or container log | as the row | — | — |
| 35 | (W) the private start fails, or times out after spawning | `private-start`; the child is gone (verified by `wait`) | old | removed | no |
| 36 | (W) termination of the wrapper during a password call | the trap stops the child; nothing listens | as applied | removed | no |
| 37 | (W) the private stop needs a forced stop | `private-stop` | new | removed | no |
| 38 | (W) password-setup then a forced stop | `password-setup`, then `also: private-stop` | as row 30 | removed | no |
| 39 | (W) the handover `exec` fails (fault: the upstream entrypoint unexecutable) | `handover` | as applied | removed | no |
| 40 | the public server exits after starting (port in use) | the server's own exit; probe unhealthy | as applied | names a dead socket | no |
| 41 | an include replaced between certification and launch with one lacking `read_policy` or moving the data directory | start on the certified values (the pins win); report true | as F | written | yes |
| 42 | (A) root, `/run` read-only; `--cap-drop ALL` | `internal`, naming the step | old | — | no |
| 43 | a second PostgreSQL listener, reachable through every inherited `PG*` variable (`PGHOSTADDR`, `PGHOST`, `PGPORT`, `PGSERVICE`, `PGOPTIONS`) and a planted `.psqlrc` | start; the second listener receives **zero connections** (its connection log); the probe reports this server | new | written | yes |
| 44 | marked, other owner | start after the ownership repair | as F | written | yes |
| 45 | a replaced entrypoint; a shell-string start | unchecked; unhealthy when the policy is missing | — | — | as started |
| 46 | a hand-run container | the image `HEALTHCHECK` reports | — | — | — |

### 9.3 The fakes checked against the real server
**The risk:** the shim's fake `postgres -C` encodes PostgreSQL's precedence, which is where rounds 2 and 3 broke (Opus 16).

**The check,** a conformance table:
- **What it covers:** every value of facts C, D, E, E2 and G, their pairs, and 3.1's spelling matrix.
- **How it runs:** the real `postgres ARGS -C name`, in a throwaway container of the image, with no server started, is compared with the fake's answer for the same inputs.
- **A disagreement** fails the shim harness's run.

### 9.4 The tests
- **The shim harness, on the host,** runs every case of 9.1. Each fake records its calls. Every row asserts:
  - the code, or the start;
  - (A) rows: no `psql` call at all;
  - (W) rows: the per-role states and the calls in order;
  - the endpoint file's absence or content;
  - no fake server process left behind.
- **Real containers,** in the isolated store:
  - every row of 9.2 and the named interactions of 9.1;
  - the start suite's cleanup scope (`tests/gates/start_scope.py`) carries over;
  - keys checked as 9.2 says;
  - **the faults:** a fault layer replaces `psql` with a wrapper that passes the script through and then, by a switch, drops the connection before `megasamples-sending` (row 32) or after the server has run the `ALTER` but before `megasamples-applied` is read (row 31).
- **The exit-code mapping, confirmed natively:**
  - a connection that never opens gives `unattempted`;
  - a dropped connection after `sending` gives `uncertain`, never `refused`;
  - a server error to the `ALTER` gives `refused`.
- **The guard tests:**
  - the policy-format digests and their append-only rule (6.2);
  - the built extension's version;
  - the image's `Config.Healthcheck` against Compose's (7.1);
  - the README stating each route of 7.3, the unsupported non-root platforms, the shared-namespace limit, the MySQL difference, and the upgrade route.
- **The upgrade route, rehearsed** on a marker-1 volume (6.4).
- **Reversals:**
  - each rule R0 to R15 removed in turn fails at least one row;
  - so do the pinned environment, the pins of 4.3 and 4.7, the session `SET`s, the verifier, the markers of 4.4, the trap, `execfail`, and the endpoint's early removal;
  - the harness and the real rows record which.

### 9.5 Confirmed by test, not assumed
- **A planted `read_policy` on `dynamic_library_path`, with R11 disabled for the test:** the report answers false and the probe fails (the brief's question 11).
- **Precedence:** command-line pins beat a persisted setting, an include and a per-role setting, for every pinned name. Session `SET`s beat per-role logging.

## 10. The build order
1. The shim harness, the conformance table (9.3) and the row generator, red against today's wrapper.
2. Routes and R0 to R4 (sections 2 and 3).
3. Format 2 and its guard (section 6), then R5 and R6 before the repair.
4. R7 to R15 and the pins.
5. The pinned environment, the private start, the passwords, the stop and the trap (4.1 to 4.5).
6. Health (4.6 and section 7).
7. The handover and step P (4.7 and 4.8).
8. The real-container rows, the faults, and the upgrade rehearsal.

## 11. The review of revision 1, traced

| Finding | Where answered |
|---|---|
| Sol 1 (P1): the client reaching another server | 4.1; row 43 |
| Sol 2: certification versus launch | 4.3 and 4.7's pins; R15; row 41 |
| Sol 3, Opus 15: DL-110 on both branches; `locked`; `root` and `admin` until slice 3; R5 under seeding | 4.8; section 8; row 1 |
| Sol 4, Opus 2, 5, 9, 10: classification | section 2; R0 first; rows 7 to 14 |
| Sol 5: the probe on another listener | 4.6; row 43 |
| Sol 6, Opus 12: the passfile, the probe, the failed `exec` | 4.6 (no passfile); 4.7 (`execfail`); rows 39 and 40 |
| Sol 7: tracking the private process; one line | 4.3, 4.5; rows 35 to 38 |
| Sol 8, Opus 1: keys in the server log | 4.4's verifier and session `SET`s; the log in `/run`; row 34 |
| Sol 9, Opus 16: coverage | 9.1's pruned product, 9.3's conformance table, 9.4's faults and mapping, the (A) and (W) split |
| Sol 10, Opus 13: the digest guard | 6.2 |
| Sol 11: marker-first integration | 6.3 |
| Sol 12, Opus 18: both hooks; MySQL wording; health's one source | 3.2, 7.1, 7.4 |
| Opus 3: the repair before R8 | R5 and R6 before it; row 18 |
| Opus 4: `*_FILE` | 4.2, R4; rows 3 and 16 |
| Opus 6: R12's (now R14's) spelling | 3.1 |
| Opus 7: the private socket's port; R13's (now R15's) exact options | 4.3; R13, R15; row 28 |
| Opus 8: pinning client and tools; loader variables | 4.1; R2, R3; rows 12, 15, 43 |
| Opus 11: catch-all code; fact K | `internal`; row 42 |
| Opus 14: the upgrade route | 6.4 |
| Opus 17: two failures; R15's sentence | 4.5; section 5 |
| Opus 19: tracing; the cross-reference | section 12; section 5 |

## 12. The brief's inputs, traced

| Input | Where |
|---|---|
| Round 1 S3; round 2 S2-2: pre-policy volume; `-D` elsewhere | R6, R8; rows 18 and 20 |
| Round 3 S3-1, O3-1: literal parsing bypassed; preload replaced | R7 to R10 read by `-C`; 3.1's parser and backstop; rows 20 to 22 |
| Round 4 S4-1: the private start on files alone | R15; row 29 |
| Round 4 S4-7: a quoted preload | R9; row 21 |
| Round 4 O4-1: path form, non-root | R2, R0; rows 5 and 11 |
| Round 4 O4-4: refusals undocumented; the repair | section 5's codes; the repair after R6; row 44 |
| Round 4 S4-6/O4-2, round 5 S5-6/Opus P3-2: the healthcheck, I6 | 7.1; row 1's no-ERROR assertion |
| Round 5 S5-3 (P2-3), "reopens": the private socket | 4.3's 0700 directory and pins; row 28 |
| Round 5 S5-7 (P3-7): non-root runs the private start first | R0 first; row 11 |
| Round 5 O5-3, O5-4: the README stopgaps for the non-root sentence and bypass routes | replaced by section 5's sentences and 7.3's table, under the README guard |
| Round 6 S6-5 (P2-5): failures after a password change | 4.4 to 4.7; rows 30 to 40 |
| Round 6 S6-6, O6-1: shared volume, trusted loopback | a fresh volume per row; keys over scram TCP |
| Round 6 O6-4, O6-P3-2: another build's volume; healthcheck location; `dynamic_library_path`; other libraries; server modes | R6 with format 2; section 7; R11; 3.2; R1; rows 13, 18, 23, 24 |
| Round 7 O7-1: the coverage criterion | 9.1 |
| Round 7 S7-1: failed public start; informational; lost reply; keys and passfile after failure | 4.7; section 2; 4.4's markers; 4.6; rows 14, 31, 40 |
| Round 7 S7-8, O7-P3-3; round 8 S8-5: the start suite's assertions | 9.2's row 1 and 9.4 |
| Round 7 S7-7/O7-P3-7: retained volumes of earlier builds | R6; row 18 |
| Round 8 S8-6, O8-P3-3: fact H's two builds; fact L's lost reply | row 18; rows 31 and 32 |

## 13. Points for the re-review

1. **The loopback trust lines** (4.6). Removing them from the baked `pg_hba.conf` would close the shared-namespace route for `postgres`. But it changes what a hand-run or sidecar client gets, so it is a security-posture question. The design states the limit, and asks whether it goes to the deciders.
2. **The verifier computed in the wrapper** (4.4). It keeps the plaintext out of the server entirely. The cost is a small Perl routine on the start path, tested against PostgreSQL's own verification by signing in with the key.
3. **Dropping the health passfile** (4.6). The probe relies on the baked local trust line, which the image already has. The passfile then adds nothing that a stale one could undo.
