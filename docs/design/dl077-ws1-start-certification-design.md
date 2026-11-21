# Workstream 1: PostgreSQL start certification, the design

**Status: design, revision 15, for round 15 of the design review. No build yet.**

This document stands alone: one ordered check list (section 3), one current row table with an outcome rule per class (section 10.2), and the conformance replay and the brief's inputs inline. Section 13 traces rounds 5 to 14.

**The coordinator's decisions on the upgrade, applying DL-122 Q4:**
- **Round 6:** the automated, grant-reconstructing restore was removed, in favour of a documented manual route. Round 6's P1 (both reviewers) was a confidentiality regression the restore introduced.
- **Round 8:** version 1 ships **no scripted upgrade recipe**. It names the route in the `policy-marker` message and the README, and keeps the volume (7.4). The reason: no release has shipped, so only disposable pre-release volumes carry marker 1, and the scripted recipe had findings in every round from 3 to 8.

**Design rounds so far:**

| Round | Reviewed | Reviews | Traced in |
|---|---|---|---|
| 1 | revision 1, `2ab72c25` | `sol-ws1-design.md`, `opus-ws1-design.md` | revision 2's section 11 |
| 2 | revision 2, `bd9c5f26` | `sol-ws1-design2.md`, `opus-ws1-design2.md` | revision 3's section 12 |
| 3 | revision 3, `32664450` | `sol-ws1-design3.md`, `opus-ws1-design3.md` | revision 4's section 13 |
| 4 | revision 4, `4c69e81b` | `sol-ws1-design4.md`, `opus-ws1-design4.md` | revision 5's section 14 |
| 5 | revision 5, `398a9c42` | `sol-ws1-design5.md` (7 P2, 2 P3), `opus-ws1-design5.md` (2 P2, 6 P3) | revision 6's section 13, kept in 13.1 |
| 6 | revision 6, `5fc84471` | `sol-ws1-design6.md` (1 P1, 9 P2, 1 P3), `opus-ws1-design6.md` (2 P2, 7 P3) | 13.2 |
| 7 | revision 7, `0131bf53` | `sol-ws1-design7.md` (1 P1, 7 P2, 1 P3), `opus-ws1-design7.md` (1 P2, 4 P3) | 13.3 |
| 8 | revision 8, `ab40130d` | `sol-ws1-design8.md` (8 P2, 1 P3), `opus-ws1-design8.md` (3 P2, 4 P3) | 13.4 |
| 9 | revision 9, `63c9d1b4` | `sol-ws1-design9.md` (4 P2, 1 P3), `opus-ws1-design9.md` (1 P2, 5 P3) | 13.5 |
| 10 | revision 10, `7d4abdf3` | `sol-ws1-design10.md` (4 P2, 1 P3), `opus-ws1-design10.md` (4 P3) | 13.6 |
| 11 | revision 11, `08fbe9aa` | `sol-ws1-design11.md` (2 P2, 2 P3), `opus-ws1-design11.md` (4 P3) | 13.7 |
| 12 | revision 12, `218a6eae` | `sol-ws1-design12.md` (4 P2, 1 P3), `opus-ws1-design12.md` (1 P2, 3 P3) | 13.8 |
| 13 | revision 13, `95a87498` | `sol-ws1-design13.md` (3 P2, 2 P3), `opus-ws1-design13.md` (7 P3) | 13.9 |
| 14 | revision 14, `58838ec8` | `sol-ws1-design14.md` (3 P2, 3 P3), `opus-ws1-design14.md` (6 P3) | 13.10 |

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
- the pre-release volume's message (the route named, not scripted);
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
| DL-122 Q4: format 2, exact marker, digest guard; the route for pre-release volumes named, not scripted (the coordinator's round 8 decision) | section 7; 7.4 |
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
| R0 | The wrapper runs as root (`id -u`), before anything else; it writes its own refusal line, needing no state directory (DL-122 Q2; Sol round 6, 11) | A | `non-root` |
| S0 | The `EXIT` trap is armed. This run's state directory is made with `mktemp -d /dev/shm/megasamples-run.XXXXXX`. Without `/dev/shm` (`--ipc=none`), the wrapper writes `internal: /dev/shm unavailable` itself and exits 1. | — | `internal` |
| R1 | The route is a start or informational | B | `wrapped-server`, `server-mode`, `argument-ambiguous` |
| R2 | `argv[1]` is the image's `postgres` | B | `foreign-binary` |
| R3 | No loader variable; no environment name that is not an identifier (read from `/proc/self/environ`); no server-read variable the design does not honour (`PGPORT`, `PGOPTIONS`, `PGDATESTYLE`, `PGTZ`, `PGCLIENTENCODING`) | J | `loader-environment`, `server-environment` |
| — | Informational routes leave here | B | — |
| R4 | The image's HBA files are sound (4.2) | — | `hba-image` |
| R5 | The override keys are well formed (5.2) | F | `key-conflict`, `key-file`, `key-value` |
| R6 | `PG_VERSION` exists and is not empty, as upstream's `-s` test requires (Sol round 11, 3). `ENOENT` or an empty file means `uninitialised`; any other error (`EACCES` under `--cap-drop ALL`, where root cannot traverse the `postgres`-owned 0700 directory) is `internal`, naming the step (Sol round 5, 6) | H | `uninitialised`; `internal` |
| L | The directory lock (5.9) | — | `volume-busy`; `internal` |
| C | With the lock held, the cleanup: the endpoint removed; `/run/megasamples-private` and `/run/megasamples-probe` recreated, owned by `postgres`, mode 0700; this run's private directory made by `mktemp -d /dev/shm/megasamples-private.XXXXXX`, owned by `postgres`, mode 0700 | — | `internal` |
| R7 | The marker is the image's own, exactly | H | `policy-marker` |
| — | slice 3's build-identity check (7.3) | — | slice 3's code |
| R8 | The volume's `pg_hba.conf` is the build's stock file (4.3) | H | `hba-volume` |
| R9 | No `hba_file` or `ident_file` argument, in any spelling, on any start (Sol round 5, 3; Opus round 5, 4) | B | `hba-argument` |
| R9b | No data-directory argument (`-D`, `--pgdata`, `-c data_directory`, any spelling) naming anything but `PGDATA` itself (Sol round 6, 3). It comes before R10, because a `-D` naming another cluster also moves the default HBA paths. | C | `data-directory` |
| — | The ownership repair | H | — |
| R10 | The server reports its configuration with the public arguments (`-C`, as `postgres`, in the pinned environment). The `hba_file` and `ident_file` it reports must be the stock `PGDATA` paths, which also catches a `config_file` or an include that sets them (4.3) | C, D | `config-unreadable`; `hba-config` |
| R11 | `data_directory` is `PGDATA`, and `PGDATA` is the locked directory (`stat -L /proc/self/fd/9`) | C | `data-directory` |
| R12 | No quoted preload entry | E | `preload-quoted` |
| R13 | `read_policy` is preloaded | D, E | `preload-missing` |
| R14 | `dynamic_library_path` is `$libdir` | E2 | `library-path` |
| R15 | No session or local preload | E | `preload-session` |
| R16 | `unix_socket_directories` parses as a list | G | `socket-settings` |
| R17 | With overrides set: no argument names `unix_socket_directories`, `port`, `data_directory` or `config_file` (3.1), even when it names the default (`-D "$PGDATA"`, `-p 5432`). The HBA names are R9's, and another directory is R9b's. | F, C, G | `override-argument` |
| R18 | With overrides set: no `standby.signal` or `recovery.signal` | H | `recovery-mode` |
| R19 | With overrides set: the private launch's values discovered, validated and rechecked (5.3) | F, C, D | R10 to R16's codes, "the private launch" |
| — | With overrides set: the verifier self-test (5.4), after R19 and before the private start and the per-role states (Opus round 9, 4) | — | `internal`, naming the self-test |
| — | The private phase (5.3 to 5.5), step P (5.8), the endpoint (8.3), the handover (5.7) | — | section 6 |

**The order between R8, R9, R9b, R10, R11 and R17** (Sol round 6, 3):
- R9 comes before R10, so `-c hba_file=/x` is always `hba-argument`.
- R9b comes before R10, so a `-D` naming another cluster is always `data-directory`, never `hba-config` through that cluster's default HBA paths.
- R10's query then carries only arguments that set no HBA name and move no directory. So a `hba_file` it reports came from the files or from a `config_file` the arguments selected. That is `hba-config`, with its own remedy (4.3).
- R11 still checks the resolved `data_directory`, which an include or a `config_file` can move.
- R17 refuses a socket, port, data or `config_file` argument with overrides, including one that names the default.

### 3.1 The parser and R17's backstop
- **The parser** reads `getopt` with attached values, `-c name=value` and `--name=value`, with `-` read as `_` and names case-folded.
- **A terminal `--`** (Sol round 12, 5): generated options, the certification query's `-C name` and the handover's pins, are always inserted **before** the first `--`, never appended after it. Row 6b passes `postgres -c work_mem=8MB --` through certification and the handover.
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
R4 reads each image file with the same safe routine as R8. That is Perl opening it with `O_RDONLY|O_NOFOLLOW|O_NONBLOCK`, an `fstat` check that it is a regular file, and a 64 KiB bound. The files are `/etc/megasamples/pg_hba.conf`, `/etc/megasamples/pg_ident.conf` and `/usr/share/megasamples/pg_hba.volume.conf`, the restore command's source. R4 then requires:
- **the bytes** to equal the build's constants, baked into the wrapper;
- **root ownership,** with no group or other write, on each file and on its directory;
- **no mount:** each opened file's mount ID, from `/proc/self/fdinfo/FD`'s `mnt_id`, and that of its directory, must equal the mount ID of `/`, the image's root mount (Sol round 6, 5; Opus round 6, 3).
  - So a bind mount over a file or over `/etc/megasamples` is refused, even one from the same device, and even with stock bytes.
  - Comparing mount IDs, not devices, also stays correct on overlayfs with `xino=off`, where a file reports its lower layer's device.

Any failure is `hba-image`.

**A derived image** that copies the same bytes, owner and mode into a layer of its own is the image, as far as R4 can tell. It is not a mount, so R4 does not refuse it. A derived layer with different bytes or permissions is refused.

**What remains, stated:** root in the container, which can remount or edit anything (DL-124). The README says so, beside DL-124's "an edit to a bind mount after start followed by a reload".

### 4.3 R8, R9, R10: a customised volume
**R8** reads `$PGDATA/pg_hba.conf` with the safe routine and compares it with **the build's constant** baked into the wrapper (Opus round 6, 4), not with a runtime file. Any of these is `hba-volume`:
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
    'sed -i -E "/^[[:space:]]*(hba_file|ident_file)([[:space:]]*=|[[:space:]]+)/Id" -- "$1"/postgresql.conf "$1"/postgresql.auto.conf' \
    sh /var/lib/postgresql/18/docker
  ```

  The pattern matches what PostgreSQL accepts: any case, and the `=` optional (Sol round 6, 4; Opus round 6, 8).

- **A setting in an include or another `config_file`:** the sentence gives the same `sed`, applied to that file, named by the deployer. Rows 23 and 23b run it on an include and on a selected `config_file` too.
- **A spelling the `sed` does not match,** a name directly followed by a quoted value (`hba_file'x'`), is still refused by R10. It is a stated limit: the sentence says to remove the setting by hand when the command leaves it (Opus round 7, 5).
- **Configuration supplied outside the volume** (Sol round 7, 7; round 8, 8):
  - **a file bind-mounted over the volume's `pg_hba.conf`:** the helper would edit the volume file beneath the mount. `hba-volume`'s sentence therefore says to remove that mount first;
  - **any configuration file mounted into the container from outside the volume:** edit it at its source, on the host. That covers a selected `config_file`, a file mounted over the volume's `postgresql.conf`, and a file read through `include`, `include_if_exists` or `include_dir`. The volume-only helper cannot see the mount.

  `hba-config`'s sentence names what the wrapper knows, since `-C` reports a setting's value, not the file it came from (Sol round 9, 3; Opus round 9, 1):
  - the `config_file` that `-C` reports;
  - whether that file, or the volume's `postgresql.conf`, is on a mount other than `PGDATA`'s, by the same `mnt_id` comparison as R4;
  - and, in every case: "the setting may be in a file it includes; if that file is mounted from outside the volume, edit it at its source."

  The file itself is found by the deployer, as for an include on the volume.

  Rows 21c and 23c rehearse these cases, and require the next start to succeed.

**Rows 21b, 21c, 23b and 23c** run each documented remedy against every case it applies to (Opus round 7, 2).

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
- **the handover list, one derivation** used both here and by the guard (Opus round 6, 5): (the variables the pinned upstream `docker-entrypoint.sh` references ∪ the image's `ENV`, that is `PATH`, `PGDATA`, `PG_MAJOR`, `PG_VERSION`, `GOSU_VERSION` and `LANG` ∪ `LC_*` ∪ `TZ`) minus the denylist:
  - the six key names;
  - `PGPASSWORD`, `PGPASSFILE`;
  - `POSTGRES_HOST_AUTH_METHOD`;
  - every `POSTGRES_INITDB_*`.

**How the handover's environment is built:** the wrapper unsets every exported variable not on the handover list, skipping Bash's read-only names (`SHELLOPTS`, `BASHOPTS`, `BASH_VERSINFO`, `EUID`, `PPID`, `UID`), and then `exec`s directly.

**The guards:**
- **The handover list equals** that one derivation exactly. That is equality, not coverage, so an unrelated addition fails.
- **No denylisted name** is on it.
- **The wrapper reads no name outside** the input list and the handover list.

**Checked twice:**
- **At the `exec` (shim):** the fake upstream entrypoint records its environment. **The execution-level contract** (Sol round 6, 8) is exactly:
  - the handover-list variables that were set;
  - `_`, which Bash adds for the executed command;
  - any of Bash's read-only names that arrived exported and that the unset loop therefore skipped.

  It holds no key and no source path. The shim exercises inherited exported `SHELLOPTS` and `BASHOPTS`.
- **In the postmaster (native, row 39b):** its `/proc/PID/environ` holds no key value and no `*_FILE` path. For each key route, direct and file:
  - upstream's `file_env`, as read from the pinned script, may export `POSTGRES_PASSWORD` with an empty default;
  - so the assertion is that any such variable present is empty;
  - a test of the pinned script pins that behaviour.

**The private files** (secrets, client stderr, the private server's log, the private HBA file) live in this run's `mktemp -d` directory under `/dev/shm`, owned by `postgres`, mode 0700 (Opus round 5, 5). The unique name means a second container sharing `/dev/shm` (`--ipc=host`, `shareable`, `container:`) cannot remove or recreate it.

**Shared-IPC limits, stated** (Opus round 6, 7):
- under `--ipc=host`, the private directory (owned by `postgres`, uid 999, mode 0700) and `pgpass` sit briefly in the host's `/dev/shm`, where a host account with uid 999 could read them;
- a run killed by `SIGKILL` or the OOM killer leaves its directory in a shared `/dev/shm`, and nothing sweeps it.

The README lists both with the `/dev/shm` requirement.

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
- **The server is launched** in the background through 5.4's gated start. Its PID is tracked once its group is confirmed, and its stderr goes to the private directory.
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

**The role report: decided by evidence** (the coordinator's round 11 and round 12 decisions; Sol round 12, 1 and 2; Opus round 12, 1). The report is not decided by where a signal landed, since a client can advance between the signal and its reap. It is not decided by a marker's absence either, since a lost write (a full `/dev/shm`) looks the same as no send. So:
1. **A role's state is computed only from evidence observed after its clients are reaped:** R's exit status, R's evidence file, and the confirmation's result and record.
2. **Every state other than `uncertain` needs positive evidence.** The absence of evidence is never evidence.

**The two clients and their evidence:**
- **The gated start** (the coordinator's round 13 decision; Sol round 13, 1; Opus round 13, 7a). R, C and the private server each start through a small start step:
  1. it makes its own session with `setsid --wait`, so its group is its own PID and a terminal's `SIGINT` cannot reach it;
  2. it blocks reading one byte from a release pipe held by the wrapper.

  The start step is `setsid --wait` running the program's gate script, `exec`ed in the background child, so `$!` is its PID. **The pipes:** the wrapper holds the release pipe's write end and a ready pipe's read end; every child is launched with both closed (`N>&-`), so only the wrapper holds the release write end and end-of-file reaches the child when the wrapper closes it (Opus round 14, 1c; Sol round 14, 1).

  **The confirmation, bounded** (Opus round 14, 1d and 6d): after `setsid`, the gate script writes one ready byte. The wrapper reads it with `read -t 2`, then reads the child's process group from `/proc/PID/stat`, parsing the fields after the last `)` (the fifth field overall), and requires it to equal the PID. A missing byte or another group is `internal`, naming the gated start; a `setsid` that forked fails this check.

  Only then does the wrapper set the role's **release flag** in memory and write the release byte. The child then `exec`s its program. If the trap runs before the release, it closes the pipe; the child reads end-of-file and exits without running its program, and the trap reaps it.

  **Signals during the launch:**
  - **`PIPE`** (Opus round 14, 2): it has the same recording handler as the other signals, never set to ignored. A release write to a gate child that died before the release fails as an ordinary error: `internal`, naming the gated start, with the role E5.
  - **Group `kill`s** tolerate `ESRCH` under `set -e`.
- **An interrupted `wait`:** a `wait` that returns above 128 because a trapped signal arrived is never taken as the child's status, in the main path or in the trap (Sol round 14, 2; Opus round 14, 5). The child's status is only what a `wait PID` returns with no signal recorded during the call. The trap repeats `wait PID`, against the same shutdown deadline, until such a return, and reads no evidence before it.
- **The rotation client (R):** the `psql` above, run with `\set VERBOSITY sqlstate` so that a server error appears as `ERROR:  SQLSTATE`. Its stderr, which carries its `\warn` markers, psql's own messages and the server's errors, goes to a per-role evidence file in this run's state directory. Its exit status is kept.
- **The confirmation client (C):** the libpq sign-in, also in its own process group. Only its exit status is used, and only to decide `applied` against `uncertain`, after R exited 0 with `megasamples-applied`. **C's output never decides the rotation's state.**
- **The spawn and release flags:** in the wrapper's memory. The spawn flag is set immediately before R is forked for a role. The release flag is set immediately before the release byte is written.
- **The record and the refusal flag:** **authoritative in memory**. The state directory's files are checked copies, written for the private server's children and the trap's cleanup, and a failed copy write never changes a state or adds a refusal line (Opus round 13, 6). The record holds `applied` only once C has succeeded.
- **Complete evidence only** (Sol round 13, 2; Opus round 13, 4): E3 and E4 match only complete, LF-terminated lines in exactly these forms, observed natively from psql 18.7 in the image (2026-11-21):
  - **E3's error line:** `ERROR:  ` followed by five characters from `[0-9A-Z]` and the LF, for example `ERROR:  42704`;
  - **E4's start-up failure:** the evidence file's **first** line, beginning `psql: error: connection to server on socket "/run/megasamples-private/.s.PGSQL.5432" failed: ` and ending in an LF. A mid-session loss prints `connection to server was lost` without that prefix, and is E5.

  Anything partial, unterminated or unlisted is E5.

**The decision table, indexed by evidence.** The first matching row decides.

| # | Evidence after the reap | State |
|---|---|---|
| E1 | the spawn flag is unset, **or** the release flag is unset: R was never forked, or never released to run psql (an earlier role failed, or the run stopped first) | `unattempted` |
| E2 | the record says `applied`: R exited 0 with `megasamples-applied`, C then succeeded, and that was recorded | `applied` |
| E3 | R exited 3 by itself; its evidence file holds a complete `megasamples-sending` line, followed by a complete error line in E3's form, and no `megasamples-applied` | `refused` |
| E4 | R exited 2 by itself; its evidence file's first line is a complete start-up failure in E4's form, and nothing in it precedes that line | `unattempted` (the connection never opened) |
| E5 | anything else | `uncertain` |

**E5's cases**, for the row 43 test and for the reader, none of them a separate rule:
- R killed by any signal, whatever its file holds;
- R exited 3 with no SQLSTATE line (psql's exit on `SIGINT` after a commit; Opus round 12, 1);
- R exited 0 without `megasamples-applied`;
- R exited 1, or 2 after `megasamples-connected` (a connection lost mid-session, row 38);
- the evidence file unreadable, truncated or missing, or a line partial (a full `/dev/shm`; Sol round 12, 2). The lost-evidence case's refusal is `password-setup`, one line, since the in-memory record and flag hold;
- a mid-session connection loss, `connected` written or lost;
- C failed, was killed, or succeeded without being recorded.

**A spawned client that was killed is never `unattempted`.**

**The records.** Before the private start, every requested role's spawn flag is unset and its record empty. A start with no override requests no role. Before the private start has begun (the checks, the self-test), no per-role line is printed. After it has begun, every exit prints one line per requested role, computed by the table.

**The trap's order** (the coordinator's round 12 decision; Sol round 12, 3):
0. **the first statement of every signal handler and of the `EXIT` trap** (Opus round 14, 5): point the `TERM`, `INT`, `HUP`, `QUIT` and `PIPE` traps at a handler that only records the signal in memory and returns, never setting any to ignored (Opus round 13, 5). An in-memory guard lets the report be printed once only. **Its second act** closes the release pipe's write end (Opus round 14, 1c);
1. choose the child, then send `SIGTERM` to **both its PID and its group**. It is never `SIGINT`, and psql has no `SIGTERM` handler. **The trap's choice of PID** (Opus round 14, 1a): the saved PID; or `$!`, only when the spawn flag is set, the saved PID is empty, and `$!` differs from every PID already saved. Bash sets `$!` before any trap can run, so a signal between the fork and the save still finds the child, and a signal before the fork never takes the private server's PID;
2. wait up to 2 seconds, then **always** `SIGKILL` the group (and the PID), even after an `ESRCH` on step 1, and reap the child by 5.4's interrupted-wait rule;
3. compute every requested role's state by the table;
4. write the refusal line, then the per-role lines;
5. only then stop the private server (5.5), with any `also:` lines after.

**The bound:** the report is printed within 2 seconds of the signal, plus the time to compute and write it, well inside Docker's default 10-second grace. Bash runs a trap only after the current foreground command ends, so **every foreground command in the private phase is bounded** (Opus round 13, 7b): `pg_isready -t 1`, `sleep 1`, and no unbounded read; the clients and the server run in the background and are `wait`ed. A private shutdown that outlasts the grace can still be killed by the runtime, but only after the report is in the log. The next start recovers the cluster (row 42b).

A failure with no signal (`password-setup`, `private-start`, an `internal` after the private start began) takes the same order from step 3.

**The handover steps:**
1. the endpoint written;
2. a snapshot taken of the in-memory record (Sol round 14, 5);
3. the run's directories removed;
4. the trap cleared: **`trap - EXIT TERM INT HUP QUIT`**, restoring the default dispositions and never setting any to ignored (Opus round 11, 3);
5. the lines printed from memory;
6. `exec`.

Row 43 names a signal landing during step N, or after it and before the next, as **HN**. **H6b** is step 6's `exec` failing.

**A signal during the handover:**
- **before step 4:** it reaches the trap. From step 2 on, the trap computes from the in-memory record and takes the refusal flag from memory, so it writes `interrupted`, not `internal`. It removes the endpoint if step 1 wrote it.
- **after step 4:** only step 5 prints.
- **A stated limit,** between step 4 and step 6: Bash cannot block signals.
  - Outside PID 1, a signal there ends the wrapper. The per-role lines are absent or cut short, and the outcome is row 43's "none".
  - As PID 1, a signal with the default action is ignored, and the start proceeds. A `docker stop` landing there is therefore discarded: the container is killed at the end of the grace period, and the next start recovers (row 42b).
  - The window is a few statements wide.

**Printing exactly once.** The per-role lines are printed once per run:
- by the `EXIT` trap, on every wrapper-owned exit after the private start began, directly after the refusal line and before any `also:` line from the shutdown. The refusal code (`private-start`, `password-setup`, `interrupted`, `private-stop`, `internal`) names the exit;
- or by step 5, before the `exec`. `handover_failed` adds only the `handover` line after them.

The rows assert the count (one line per requested role) and the order.

**After a failure:**
- the first non-`applied` result stops the sequence;
- the wrapper exits with `password-setup`. The `EXIT` trap writes the refusal line and each requested role's state, then stops the server.

**A retry converges.**

### 5.5 Supervision and the stop
- **Waits:** clients and the server run in the background and are `wait`ed.
- **The trap,** in 5.4's order:
  - ends a running client with `SIGTERM` to its process group, then `SIGKILL` after 2 seconds, and reaps it;
  - computes and prints the role report;
  - only then sends `SIGINT` to the server's group, waits up to 60 seconds, then `SIGQUIT` for 10 seconds, then `SIGKILL`, and reaps it.
- **Codes:** a forced stop is `private-stop`; a signal during the start is `interrupted`, with each role's state.
- **One refusal line,** then `also:` lines.
- **The refusal flag** is held in memory (5.4). Its file in the state directory is a checked copy that the trap never reads (Sol round 14, 5; Opus round 14, 3). A lint check forbids `refuse` in every subshell context: `$(…)`, `( … )`, a pipeline stage and process substitution.

### 5.6 The probe needs no key
The probe connects as `demo`, to `megasamples`, on the dedicated probe socket, under the image's `local … trust` line. There is no passfile.

### 5.7 The handover
```
exec /usr/local/bin/docker-entrypoint.sh postgres ARGS PINS || handover_failed
```

PINS go before the first `--` in ARGS, if there is one (3.1):

```
exec /usr/local/bin/docker-entrypoint.sh postgres ARGS-BEFORE-- PINS -- ARGS-AFTER-- || handover_failed
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
- **`handover_failed`** removes the endpoint, writes the `handover` line, and exits 1. The per-role lines were already printed, once, just before the `exec` (5.4). The trap has already been cleared and the run's directories removed.
- **Failures after the `exec`** (upstream's `exec gosu`, or `gosu`'s `exec postgres`) leave a dead PID in the endpoint, so the probe is unhealthy.

### 5.8 Slice 3's step P
- **Where it sits:** after R19, the passwords and the private stop; before the endpoint and the handover; on both branches.
- **What it does now:** nothing. `locked` is reserved for it.
- **The lock covers it.**
- **Until slice 3,** `postgres` and `admin` sign in over TCP with the key in force after this run's rotation: the new key where this run applied an override, and otherwise 10.2's baseline, the published key unless an earlier run applied one (Opus round 9, 4; Sol round 10, 5).
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

**The `EXIT` trap** is armed at S0. For any wrapper-owned exit, it makes sure a coded line was written for this run (`internal` with the last step if none was), and that the exit status is 1. It removes this run's directories, and the endpoint if this run wrote it (5.4's step 1).

**The rules for codes:** codes are added, never renamed or removed. An unknown code is a refusal.

**`policy-marker`'s sentence** depends on what was found (DL-122 Q4; Sol round 6, 11; Opus round 7, 4):
- **marker `1`:** a pre-release volume. The sentence carries 7.4's items in short form: not upgraded in place; kept untouched; export your own work with `pg_dump` using the old image and load it yourself on a fresh volume; copy the volume first; run the old image socket-only (`listen_addresses=''`, no network) and export from inside its container with `docker exec`; not carried over (sample data, passwords, custom client-authentication rules, which you should inspect first, and grants: export with `pg_dump --no-acl --no-owner`, pass `--no-owner` to `pg_restore` too, and review default privileges); on the new image, tables `admin` creates in `public` are readable by `demo`; how to get the old image back. It names the README section with the full text;
- **a newer marker** (`3` or more): the volume was made by a newer image. Use that image;
- **no marker:** not a megasamples format-2 volume. If it is an earlier megasamples volume, the marker-`1` advice applies; otherwise, start this image on a fresh volume;
- **any other content:** the value found and the image's own, and the same advice as for no marker.

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
**R7:** a regular file, not a symlink, holding exactly the image's value. **Format 2's bytes are `2\n`**: the digit and one LF, two bytes in all, read and compared as bytes, not through `$(<…)`, which strips trailing newlines (Sol round 9, 5; Opus round 9, 4).

**The digest covers:**
- the extension (script, control, C source);
- the init SQL: `00-users.sql`, `10-read-profile.sql`, `15-read-views.sql`, `read-routine-names.sql`, `20-grants.sql`, `30-template-grants.sql` and `40-register-template.sql`;
- `megasamples/postgres_templates.py`;
- the three HBA files of 4.1;
- the Dockerfile's policy and HBA steps.

**The current-digest check:** the current files' digest must equal the current pair's recorded digest.

**Released, one definition** (Sol round 5, 5; Opus round 5, 7): a pair is released from the first revision on `main`'s first-parent history whose `policy-format.json` marks it `released: true`. That flag is set in the merge to `main`.
- **The guard walks** that history with `--first-parent`. From the first released revision on, the pair's digest must not change, and it must stay present and released.
- **The candidate is compared with released history** (Sol round 6, 9): for every pair released anywhere in that history, the working tree's manifest must hold the same digest **and still mark it `released: true`** (Sol round 7, 9). The current files' digest is checked against the manifest. So a feature branch that edits a released policy file and refreshes its digest fails, and so does one that only flips a released pair back to `false`.
- **A new format bumps both members** (DL-122 Q4): a pair added to the manifest must differ from every earlier pair in its marker and in its version.
- **Release tags** match `v[0-9]*` (Opus round 6, 6). Each must point at a commit on `main`'s first-parent history where every pair in that commit's manifest is `released: true`. The guard lists the tags and fails otherwise. So a tag cannot precede the flag, and a release cut elsewhere cannot freeze a format the walk never sees.
- **The test needs full history and fails on a shallow clone.**
- **Tested:**
  - an unreleased pair's digest edited: passes;
  - a released pair edited, deleted, or changed and changed back: fails;
  - a feature branch's intermediate digests merged: passes;
  - a tag off `main`'s first-parent history: fails;
  - a tagged release followed by an edit of the same pair: fails;
  - a tag at a commit where a pair is still `released: false`: fails;
  - a branch editing a released policy file with its manifest digest refreshed: fails;
  - a new pair that bumps only the marker or only the version: fails;
  - a candidate that flips a released pair to `released: false` and keeps its digest: fails.

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

### 7.4 A pre-release volume: the route is named, not scripted (the coordinator's round 8 decision, applying DL-122 Q4)
**The decision.** Version 1 ships **no scripted upgrade recipe**. It names the route, as DL-122 Q4 requires, and keeps the volume.

**The reason.** No release has shipped, so only disposable pre-release volumes carry marker 1. The scripted recipe had findings in every design round from 3 to 8:
- access lists replayed;
- a schema that already existed;
- the old server reachable over TCP;
- a load that could commit partway;
- sequences and references that could not load;
- readiness races and colliding role names.

A recipe megasamples would have to certify buys nothing a deployer of a disposable volume needs. Revision 8's commands, its stated limits and its rehearsal (old row 61) are removed.

**What the `policy-marker` sentence for marker `1` and the README's section say:**
- this volume was made by a pre-release build, and is not upgraded in place;
- it is kept untouched. R7 refuses before any write, the ownership repair included;
- to carry your own work, export it with PostgreSQL's own tools (`pg_dump`) using the old image, then start this image on a fresh volume and load it yourself;
- **copy the volume first** if you need it unchanged: running the old image on it is an ordinary server start, and writes to it (Opus round 9, 5);
- **run the old image socket-only while you export,** with `listen_addresses=''` and no network (`--network none`), and export from inside its container with `docker exec`: it trusts both loopbacks and serves the published privileged keys, and a peer on any network it joins could reach it (Sol round 10, 1);
- what is not carried over, since the fresh image carries nothing forward:
  - the sample data, which the new volume has fresh;
  - passwords;
  - custom client-authentication rules: inspect the old policy first, on the old image, and put equivalent protection outside the image before exposing the new server (DL-124);
  - grants. **Export with `pg_dump --no-acl --no-owner`**, so no grant comes back; a default restore replays access lists (Sol round 9, 1). For an archive dump, pass `--no-owner` to `pg_restore` as well. Default privileges need the deployer's own review on the new image;
- **on the new image, tables `admin` creates in `public` are readable by `demo`, whose key is published.** Load private work into another schema, or as another owner (Opus round 10, 3);
- how to get the old image back: `megasamples image` at an earlier revision, or a retained image digest.

The README section holds the full text; the sentence carries each item in short form and names the section.

**A stated limit:** the export and the load are the deployer's own, done with PostgreSQL's tools. megasamples does not certify them, their commands or their result.

**Row 61** asserts the message, not a recipe. Naming the two flags is a sentence, not a command.

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
| Docker's CLI | Podman's socket | through the compatible API. If the inspect finds no `HEALTHCHECK`, the fallback is `podman --url <the same socket> build --format docker`. Podman's remote client builds on the service behind the selected endpoint, so the store is the same by construction, not by a matching path (Sol round 6, 10). Without a Podman client that can use the socket, the build is refused. |
| `podman` or the podman-docker shim | Podman | `--format docker` |

**Detection:** `docker --version` naming Podman is the shim. Otherwise `docker version -f '{{.Client.Platform.Name}}'`; a template error or an empty name means "not Podman's client".

**Only a candidate whose `Config.Healthcheck` is the expected one is tagged** as the requested tag. The candidate is then removed. On failure the candidate is removed and **an existing good tag is left untouched**, so the requested tag never names an image without the check.

**Tested on each route:**
- with an existing good tag;
- a forced failure;
- with a local `podman` whose store reports the same graph-root path as the socket's but is a different store: the fallback builds only through `--url`, and nothing lands in the local store.

### 8.3 The endpoint
- **The probe socket directory:** `/run/megasamples-probe`, recreated under the lock, owned by `postgres`, mode 0700.
- **The public socket list** is the certified list plus that directory, with no empty element.
- **The endpoint file,** `/run/megasamples-health.endpoint`, mode 0644, is written just before the `exec`. It records the PID, the probe directory, the port and `PGDATA`.
- **The probe's own environment** (Sol round 10, 2): the image's and Compose's healthchecks run outside the wrapper, so the probe clears libpq's environment itself before it connects: `PGHOST`, `PGHOSTADDR`, `PGPORT`, `PGSERVICE`, `PGSERVICEFILE`, `PGPASSFILE`, `PGPASSWORD`, `PGUSER`, `PGDATABASE`, `PGOPTIONS`, `PGSSLMODE`, `PGREQUIRESSL`, `PGCONNECT_TIMEOUT`, `PGTARGETSESSIONATTRS`, `PGSYSCONFDIR` and every other `PG*` libpq reads. It runs `psql -X` and names the recorded socket directory, port, user and database explicitly.
- **The probe checks:**
  1. `postmaster.pid` names the recorded PID, which is alive, and the recorded port;
  2. the probe socket exists;
  3. a connection there, as `demo` to `megasamples`, runs `SELECT pg_catalog.megasamples_policy_loaded()` and gets exactly `t` (Opus round 6, 2; Sol round 6, 6).
- **The negative control, through the wrapper and the real endpoint** (Sol round 7, 6): a fault image whose `megasamples_policy_loaded()` is built to return false, started normally. The wrapper certifies it and writes a real endpoint, the PID is live and the probe socket exists, so the probe reaches its query, gets `f`, and is unhealthy. **Its reversal:** with only the query's result check removed from the probe, the same fixture is reported healthy.
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
- **The conformance replay of the fake `-C`,** by construction:
  - the fake `postgres -C` records every query it answered, with the fixture's whole tree: working directory, absolute paths outside `PGDATA` (includes, `config_file`), owners and modes;
  - each query is replayed, as `postgres`, against the real `postgres -C` in a throwaway container of the image, with the fixture tree reproduced exactly;
  - status and value must agree.

**Left out of the product, with the reason:**
- **J's admitted client variables** (`PGHOSTADDR`, `PGHOST`, `PGSERVICE`, `PGPASSFILE`, `PGUSER`, a `.psqlrc`): `env -i` and `-X` make every client independent of them. Row 50 shows each once.
- **The passing argument forms** (`-k`, `-c work_mem`, the absolute path, other libraries): they reach only the public launch. Each is one row against the base.
- **Real containers:** every row of 10.2.

### 10.2 The current row table
**Each row asserts** (restored; Opus round 6, 2; Sol round 6, 6): the code or the start; the fakes' calls (shim); the per-role states; the keys; the endpoint; the `/run` and `/dev/shm` directories; the listener; health; and that no process of the run is left. **Each row runs on its own fixture.**

**The outcome rule per class,** which every row of its class asserts unless the row says otherwise:

| Class | Endpoint | Keys | `/run` and `/dev/shm` | Listener and health |
|---|---|---|---|---|
| **(A) before or at the lock** (R0 to R6, and L: `volume-busy` or the lock's `internal`) | unchanged (a stale one stays) | old | unchanged; no state directory left | none; a stale endpoint's dead PID keeps the probe unhealthy |
| **(A) at the cleanup** (C fails, for example a read-only `/run`) | removed if C reached it, otherwise unchanged; the row names which | old | what C completed, named by the row; no state directory left | none; unhealthy |
| **(A) after the lock** (R7 onwards, before any client) | removed | old | `/run/megasamples-*` recreated; no private or state directory left | none; unhealthy |
| **(W) before the rotation** (the private server failed before any client: `private-start`) | removed | old; every requested role `unattempted`; the per-role lines once each, after the refusal line and before any `also:` line from the shutdown | no private or state directory left | none; unhealthy |
| **(W) after the rotation began** | removed | per each role's recorded state; the per-role lines once each, after the refusal line and before any `also:` line from the shutdown, except for `handover`, where they come before it (5.4) | no private or state directory left | none; unhealthy |
| **(P) after the handover** (upstream's `exec gosu`, `gosu`'s `exec postgres`, or the public server's own exit) | names a dead PID | as before the handover: per each role's recorded state, every role `applied` or not requested; the per-role lines once each, before the `exec` | no private or state directory left | the child's nonzero exit; no surviving server; unhealthy |
| **Start** | written | each `applied` role's new key; every other role keeps the key in force before the attempt | no private or state directory left | listening; healthy by `SELECT pg_catalog.megasamples_policy_loaded()` = `t`; for each `applied` role whose new key differs from its key before the attempt, that prior key refused by SCRAM; on every native Start, row 36 and 36b included, row 1's out-of-namespace `CREATE DATABASE` refused with `42501` and its in-namespace control succeeding (Sol round 10, 4) |

- **The key baseline** (Sol round 8, 7): "old" and "the key in force before the attempt" mean what each role signed in with immediately before this start. That is the published key on a fresh volume, or whatever an earlier run applied on a retained one. A witness start or an ordinary restart with no overrides is a Start whose baseline is the keys left by the previous run.
- **Keys** are checked over password-authenticated TCP on a start.
- **A socket-only public start** (`listen_addresses=''`, which the public launch keeps; Sol round 9, 4): the Start rule's listener and key cells become: no TCP listener at all, and healthy through the probe socket. Keys over the socket are no evidence, since the image's `local … trust` lines admit any key. If the row must prove its keys, it stops that server and runs a TCP witness start on the same volume.
- **A row with no listener, after work began,** checks them on a **witness start** of the same fixture: clear only the row's injected fault, start with no overrides (rotation disabled), and check each key over SCRAM TCP. Before that, the row proves the failed launch left no listener.
- **An (A) row** proves its keys old by proving no server ran: no `postmaster.pid` was written, and the volume's content (`pg_authid` included) is byte for byte unchanged, apart from the ownership repair for refusals after it (Sol round 7, 5; Opus round 7, 3). A witness start cannot be used there, since the same fixture refuses again.
- **"Unchanged"** means byte for byte, with stale files present in the fixture.

| Row | Facts | Outcome |
|---|---|---|
| 1 | base | start; the report true; the namespace hook refuses (42501, its message, fresh names) and the positive control succeeds; probe healthy, no ERROR, through the image's and Compose's check; `postgres` and `admin` on published keys until slice 3 |
| 2 | overrides all, direct | start; each key confirmed |
| 3 | overrides all, as `*_FILE`; and `POSTGRES_PASSWORD_FILE` with direct `DEMO_PASSWORD` | start; confirmed |
| 4 | `demo` only | start; `demo` new, others published |
| 5 | `argv[1]` the absolute path, with overrides, on a fresh volume | start; the new key works and the old one is refused by SCRAM (the existing control, `tests/test_v1_postgres_start.py`) |
| 6 | options only (`-c work_mem=8MB`) | start |
| 6b | Start: options ending in a terminal `--` (`-c work_mem=8MB --`) | the Start rule; the certification query's `-C` and the launch's pins both inserted before the parsed `--`, shown by the recorded query arguments and `/proc/PID/cmdline`; the pins in effect by `SHOW` (Sol round 13, 5; Opus round 13, 1) |
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
| 15c | an imported read-only `SHELLOPTS` or `BASHOPTS` | start (skipped by the unset loop); the handover environment meets 5.1's execution-level contract, with that name present as inherited |
| 16 | (A) a derived layer with different bytes in `/etc/megasamples/pg_hba.conf` | R4 `hba-image`; unchanged |
| 16b | (A) a bind mount over the file with stock bytes, from the same device; and from another device | R4 `hba-image` (mount ID); unchanged |
| 16c | (A) a bind mount over `/etc/megasamples` | R4 `hba-image`; unchanged |
| 16d | (A) the file writable by `postgres`; a FIFO at the path; a mount over `/usr/share/megasamples/pg_hba.volume.conf` | R4 `hba-image`; unchanged |
| 16e | a correct start under rootless Podman's overlay storage (`xino=off` layers) | start; R4 passes by mount ID |
| 17 | (A) a key both ways; an unreadable file; an empty key; a NUL in a file; a non-ASCII key; an overlong key; a CRLF file | R5 `key-conflict`, `key-file`, `key-value`; unchanged |
| 18 | (A) `PG_VERSION` missing; `PG_VERSION` empty | R6 `uninitialised`; unchanged |
| 18b | (A) `--cap-drop ALL` | R6 `internal`, naming the `PG_VERSION` lookup's `EACCES`; unchanged |
| 19 | (A) a second container on the same volume, held at each boundary, including the first's public run; and `docker exec … entrypoint-wrapper.sh postgres` inside a running container | `volume-busy`; the first start's keys in force; one postmaster; the first stays healthy |
| 19b | (A) an NFS-like `flock` failure (`EBADF`), and `ENOLCK` | `internal`, naming the lock and the error, never `volume-busy` |
| 20 | (A) the marker file, case by case: absent (unmarked); containing `1`, on volumes from both earlier builds; containing `3`; empty; a symlink to a file containing `2`; containing `1` on a read-only mount; containing `x` on a volume owned by another uid; and the near matches `2` with no LF, `2\n\n` and ` 2\n` | R7 `policy-marker`, with each case's sentence from section 6: absent gives the no-marker sentence; `1`, on both builds and the read-only mount, the marker-`1` sentence; `3` the newer-marker sentence; empty, the symlink, `x` and each near match the other-content sentence, naming what was found, and each near match leaves the volume byte for byte unchanged. Nothing written; ownership unchanged (no repair before R7) (Sol round 8, 9; Opus round 8, 5) |
| 21 | (A) a volume `pg_hba.conf`: customised (a `local` rule requiring a key; a `hostssl` rule; a loopback `trust` rule); a symlink; a FIFO; a directory; over 64 KiB | R8 `hba-volume`, before either launch |
| 21b | the `hba-volume` restore command, run on each case of row 21 | each next start succeeds; a symlink's target is not written |
| 21c | a file bind-mounted over the volume's `pg_hba.conf` | `hba-volume`; after removing the mount, as the sentence says, the next start succeeds |
| 22 | (A) `-c hba_file=/x`, `--hba-file=/x`, `-c ident_file=/x`, with and without overrides | R9 `hba-argument` |
| 23 | (A) `hba_file` or `ident_file` in `postgresql.conf`, in `postgresql.auto.conf`, in an include, and in a file selected by `-c config_file=`; spelled `HBA_FILE = 'x'` and `hba_file 'x'` (no `=`) | R10 `hba-config` |
| 23b | the `hba-config` command, run on every case of row 23, on the named file for an include or a `config_file` | each next start succeeds |
| 23c | configuration mounted from outside the volume that sets `hba_file`: a `-c config_file=` file; a file mounted over the volume's `postgresql.conf`; and a mounted file among several in a directory read by `include_dir` | `hba-config`, its sentence naming the reported `config_file`, whether it or `postgresql.conf` is on another mount, and the include sentence; after the deployer edits the setting at its source, the next start succeeds, for each case (Sol round 9, 3; Opus round 9, 1) |
| 24 | a file mounted at `/etc/megasamples/pg_hba.local.conf` with a `trust` rule | start; no effect: `pg_hba_file_rules` shows only the image's three rules; loopback still needs a key |
| 25 | (A) `config_file` unreadable; a non-numeric `port` | R10 `config-unreadable` |
| 26 | (A) a `-D`, `--pgdata` or `-c data_directory` naming another valid cluster, in every spelling | R9b `data-directory`, never `hba-config` |
| 26b | (A) a `config_file` or include that moves `data_directory` | R11 `data-directory` |
| 27 | (A) a quoted preload | R12 `preload-quoted` |
| 28 | (A) `read_policy` missing from the file, `auto.conf`, `-c` or an include | R13 `preload-missing` |
| 29 | other libraries with `read_policy` | start |
| 30 | (A) `dynamic_library_path` changed | R14 `library-path` |
| 31 | (A) a session or local preload | R15 `preload-session` |
| 32 | (A) `unix_socket_directories` malformed | R16 `socket-settings` |
| 32b | an empty certified socket list | start; the list is just the probe directory; healthy |
| 32c | a stale probe directory with the wrong owner | recreated; healthy |
| 32d | the probe directory made unwritable by a fault | serves; probe unhealthy: "probe socket missing" |
| 33 | (A) overrides with `-k /run/postgres`, `-p 5432`, `-D "$PGDATA"`, `-c config_file=$PGDATA/postgresql.conf`: arguments that pass every earlier check | R17 `override-argument` |
| 34 | (A) overrides with `standby.signal` or `recovery.signal` | R18 `recovery-mode` |
| 35 | (A) overrides, with a preload fixed by `-c` but missing from the files | R19 `preload-missing`, "the private launch" |
| 36 | overrides, and a persisted custom socket, port or `listen_addresses` | start; the rotation reached `/run/megasamples-private` port 5432; no other listener during it |
| 36b | overrides, and `-c listen_addresses=''` | start; no TCP listener, during the private phase or after it; healthy through the probe socket; keys proved on a TCP witness start after that server is stopped |
| 37 | (W) the first role refused | `password-setup`; `refused`, then `unattempted` |
| 37b | (W) a retry where the key already works and the `ALTER` is refused (fault) | `refused` |
| 38 | (W) overrides for all three roles; the second role's reply lost: the fault relay forwards its `ALTER`, waits for `CommandComplete`, then closes before forwarding it | `password-setup`; `postgres` `applied`, `admin` `uncertain`, `demo` `unattempted`; the per-role lines once each, after the refusal line. Keys, on a witness start with no overrides, whose baseline is this run's result: `postgres` and `admin` sign in with their new keys and their prior keys are refused; `demo` signs in with its prior key |
| 39 | (W) the connection never opens (the relay refuses) | `unattempted` for all |
| 39b | overrides, direct and as `*_FILE` | the recorded handover environment meets 5.1's execution-level contract exactly: the set handover-list variables, `_`, and any read-only name that arrived exported, with no key or path (Sol round 7, 8). Separately, the postmaster's `/proc/PID/environ` holds no key value or `*_FILE` path, and any `POSTGRES_PASSWORD` present is empty (upstream's default, pinned) |
| 40 | retry of row 38 | start |
| 41 | overrides under persisted `log_statement=all`, per-role `log_statement=all` and `debug_print_*=on`; and row 37 under each | no key or verifier in any log, `pg_stat_statements` or the container log |
| 42 | (W) the private start fails, or no response for 60 seconds | `private-start`; the child reaped; the per-role lines once each, every requested role `unattempted`, after the refusal line; keys old (the (W)-before-the-rotation rule) |
| 42c | (A) the ownership repair fails (a fault on `chown`) | `internal`, naming the repair; keys old |
| 42d | (W) the endpoint write fails just before the handover (a read-only endpoint path, by fault) | `internal`, naming the endpoint, then the per-role lines once each; keys as applied; no listener |
| 42b | an unclean previous stop, a long recovery | start, after waiting |
| 43 | (W) one table test of 5.4's evidence table. **Inputs:** held landing points (the test's fault **holds**, not the wrapper's gated start; Opus round 14, 6c), each mapped to the evidence it produces: before a role's spawn; R spawned, before `megasamples-connected`; after `connected`; after `sending`; the `ALTER` committed with `CommandComplete` held by the fault relay, then `SIGINT` to R's process group and the reply forwarded; after `megasamples-applied`; during C; after C, before the record; after the record; each handover step, H1 to H6b. **Races:** at each boundary, the hold releases the client after the signal, so it advances before the reap. **Lost evidence:** `/dev/shm` filled during `\warn megasamples-sending`. **Server refusal:** an `ALTER` the server rejects, giving exit 3 and a SQLSTATE; and the same with its error line truncated, injected by a fault on that one descriptor: R's stderr passes through a fault writer that stops before the line's LF (Opus round 14, 6b). **Connection failure:** row 39's relay refusal; a mid-session loss with `connected` lost; an exit-2 start-up failure whose line lacks only its final LF (Sol round 14, 4). **Gated start:** a signal after the fork and before `$!` is saved, and after it but before the release, for R, C and the private server, each asserting that the program never ran and that this specific child was reaped (Sol round 14, 1); the gate child killed before the release, so the release write meets `PIPE` (Opus round 14, 2). **A second signal:** during the reap, proving the reap as well as the single report, and during the private stop. **The wrapper's normal private stop,** after the rotation, interrupted | **Before the `exec` (the points before the handover, H1 to H3):** the state from the evidence actually produced; the refusal code; the per-role lines once each, after the refusal line; **H6b:** row 46's outcome, the per-role lines once each, then the `handover` line only, endpoint removed, no listener; the (W) class; stopped and reaped; no listener. **Keys,** on a witness start: for each `unattempted` or `refused` role, the prior key works and the new one fails; for `applied`, the reverse. **For each `uncertain` case the hold decides whether the `ALTER` reached the server, and the row states the key it implies** (Opus round 13, 2): the new key works and the distinct prior key fails over SCRAM where the commit passed the relay (after `sending` released; the `SIGINT` case; during C; after C, before the record; the lost-evidence case, since psql does not stop on a failed `\warn`; C's gated start before its release); the reverse where the relay held the `ALTER` back, and for the truncated-error case (the server refused), the unterminated start-up line and the gate child killed before the release (psql never ran); and where a race leaves it uncontrolled, exactly one of the two keys works. **The wrapper's normal private stop, interrupted:** every role `applied` by E2, the new keys, the code `interrupted` (Sol round 14, 6; Opus round 14, 4). **Codes:** the gate child killed before the release is `internal`, naming the gated start; the `SIGINT` case, a signal to R's group only, leaves the wrapper on the `password-setup` path; the gated-start and race cases are `interrupted`; the lost-evidence and truncated-error cases are `password-setup`, one line; a second signal adds no line and loses no cleanup. **H4, H5 and H6 as PID 1:** the Start rule, readiness checked before teardown. **H6, in three parts** (Sol round 13, 3; Sol round 14, 3): (i) **the upstream handoff** (after the `exec`, before PostgreSQL installs its handlers): ignored as PID 1 and the start proceeds; outside PID 1 the process ends with the (P) outcome. (ii) **PostgreSQL's startup, before readiness** (handlers installed, for example during row 42b's long recovery): a `SIGTERM` makes PostgreSQL shut down without becoming ready; the per-role lines already printed once, before the `exec`; the keys as applied, on a witness start; the endpoint names a dead PID; no surviving server; unhealthy. (iii) **ready service:** scoped to the signal sent: `SIGTERM`, `SIGINT` or `SIGQUIT` is PostgreSQL's shutdown, its exit status, the endpoint then naming a dead PID; `SIGHUP` is a reload, and the server stays ready and healthy. **"None", outside PID 1 at H4 and H5:** the endpoint names a dead PID; no private or state directory left; no listener; unhealthy; the per-role lines absent or a prefix of them; the wrapper ended by the signal |
| 43c | (W) a real `docker stop` (10-second grace) during the rotation, with the private server's shutdown delayed past the grace by a fault | the refusal line and the per-role lines in the log, once each, **within 3 seconds of the stop signal** by the log's timestamps (the 2-second client bound plus writing); then the runtime kill: exit 137, no server survives, the endpoint removed; the next start recovers (row 42b) |
| 43b | (W) a signal while a client stalls | as row 43, promptly |
| 44 | (W) a forced private stop | `private-stop` |
| 45 | (W) row 37, then a forced stop | `password-setup`, then `also: private-stop` |
| 46 | (W) overrides; the entrypoint unexecutable just before the handover | the per-role lines once each, all `applied`, then the `handover` line, with no second printing; keys new; endpoint removed; no state or private directory left; no listener |
| 46c | (W) overrides; a signal after step 3 and before step 4 | row 43's H3 case, kept by number |
| 46b | (P) `gosu` removed after the private stop (fault layer); the server binary unexecutable after the private stop | the (P) rule: the child's nonzero exit; a dead PID in the endpoint; no surviving server; unhealthy; the per-role lines once each, before the `exec`; keys as applied (witness start) |
| 47 | (P) the public server binds, then exits after starting | the (P) rule: its own nonzero exit; the per-role lines once each, before the `exec`; keys as applied; the endpoint names a dead PID; no surviving server; unhealthy |
| 47b | (P) the public server fails to bind its port before readiness (port in use) | the (P) rule: its own FATAL exit; the per-role lines once each, before the `exec`; keys as applied; the endpoint names a dead PID; no listener; unhealthy |
| 48 | an include replaced between certification and launch | start on the pinned values |
| 49 | (A) root, `/run` read-only | `internal` at the cleanup, naming `/run`; the (A)-at-the-cleanup rule: the endpoint unchanged (C fails before removing it, since its first act is opening `/run`) |
| 49d | (A) the verifier self-test failing | `internal`, naming the self-test; the (A)-after-the-lock rule |
| 49b | (A) `--ipc=none` | `internal: /dev/shm unavailable` |
| 49c | two containers sharing `/dev/shm` (`--ipc=shareable` / `container:`) on different volumes, starting with overrides at once | both start; neither's private directory touched by the other |
| 50 | a second listener reachable through each admitted inherited client variable (`PGHOSTADDR`, `PGHOST`, `PGSERVICE`, `PGPASSFILE`, `PGUSER`) and a planted `.psqlrc` (`PGPORT` and `PGOPTIONS` are row 15b's refusals) | start; zero connections at the second listener |
| 50c | the probe's environment: (a) the image's and Compose's healthchecks in a container started with `PGHOSTADDR` aimed at a second listener whose `megasamples_policy_loaded()` answers the opposite of the local server's; (b) the same healthchecks with an inherited `PGHOST`; (c) the probe run by hand with `docker exec -e PGPORT=…` (a container started with `PGPORT` is refused at R3) | the probe judges the local server in both directions; zero connections at the second listener. **The redirect reversal** is (a)'s: with the environment clearing removed, `PGHOSTADDR` sends the probe to the second listener. (b) and (c) are independence checks: the explicit socket and port already hold (Sol round 11, 2; Opus round 11, 2) |
| 50b | a second healthy server on a shared socket directory, and on another port | the probe does not report it |
| 51 | marked, other owner | start after the repair |
| 52 | a replaced entrypoint; a shell string; an unlisted wrapper | unchecked; always unhealthy |
| 53 | a hand-run container | the image `HEALTHCHECK` reports |
| 54 | loopback TCP, both families, as `postgres` and `admin`, no key or a wrong key, under Docker, pasta and rootlesskit | refused by SCRAM; the right key admitted |
| 55 | keys with `'`, `\`, `:`, `$`, `"`, `;`, leading and trailing spaces, 1024 bytes, and a 1024-byte key of only `:` and `\` | start; each confirmed |
| 56 | (W) a failed rotation, then a restart of the same container hitting an early lock error | **each attempt its own class** (Sol round 11, 4): the first, (W) after the rotation began: its refusal, the per-role lines once each, its cleanup; the restart, (A) at the lock: its own `internal` line, the endpoint and `/run` unchanged from the first attempt's end. The restart's key baseline is the keys the first attempt left, proved on a witness start |
| 57 | the private files read under the real uids | the private server reads `hba.conf`; the client reads `pgpass`, as `postgres` |
| 58 | the image build | the baked `pg_authid` holds only the image's roles; the stock volume `pg_hba.conf` equals the repository file |
| 59 | informational and handover `exec`s, repeated in one container | no state or private directory left behind |
| 60 | the probe's negative control: a fault image whose loaded report returns false, started through the wrapper | a real endpoint, live PID and probe socket; the probe reaches its query, gets `f`, unhealthy. Reversal: the probe without its result check calls it healthy |
| 61 | the pre-release message: a marker-`1` volume from each earlier build | the `policy-marker` sentence carries each item of 7.4 (not upgraded in place; kept untouched; `pg_dump` with the old image, then load on a fresh volume; copy the volume first; run the old image socket-only (`listen_addresses=''`, no network) and export from inside its container with `docker exec`; not carried over: sample data, passwords, custom client-authentication rules with the inspection first, grants, with `pg_dump --no-acl --no-owner` named, `--no-owner` for `pg_restore` too, and default privileges left to the deployer's review; tables `admin` creates in `public` readable by `demo`; how to get the old image back) and names the README section; that section holds each item in full; the volume byte for byte unchanged |

### 10.3 Confirmed natively
- **The `psql` exit mapping,** by the fault relay;
- **E3's and E4's line forms** from the image's psql, re-checked on any base-image change (the Dockerfile pins `postgres:18.7-trixie`): `ERROR:  ` with a five-character SQLSTATE; the start-up `psql: error: connection to server on socket "…" failed: ` line; a mid-session loss's `connection to server was lost` without that prefix (Opus round 14, 6a);
- **Bash's behaviour** that 5.4 relies on: `$!` set before any trap runs; an untrapped `SIGPIPE` ending Bash without its `EXIT` trap; re-entry of a handler for the same signal;
- **the `dynamic_library_path` report;**
- **the precedence** of pins and session `SET`s;
- **the placeholder `SET`;**
- **the lock's inheritance;**
- **the loopback rows** under each network mode;
- **upstream's `file_env` default,** from the pinned script;
- **the image's HBA file:** `pg_hba_file_rules` shows exactly its three rules, with no error;
- **the pre-release message** on volumes from both earlier builds (row 61).

### 10.4 Reversals
- **Each step R0 to R19,** removed in turn, fails at least one row.
- **So does each mechanism:**
  - the pinned environment, `-p`, the handover list's equality guard, each pin, the HBA pins and R4's mount check;
  - the session `SET`s, `ON_ERROR_STOP`, the verifier's self-test, the confirmation with `require_auth`, `\warn`;
  - `setsid` and the tracked PID, the interruptible waits, the lock;
  - `execfail` with `||`, the directory cleanup before `exec`, the per-run `mktemp` names;
  - the endpoint checks;
  - the removed loopback lines;
  - the candidate tag in the build and the `--url` fallback;
  - R9b's place before R10;
  - the per-role lines printed exactly once on every exit after the private start began: a second printing in `handover_failed`, or none from the trap, fails rows 42, 45, 46 and 47; dropping the final print fails rows 46, 46b, 47 and 47b;
  - **each state boundary of 5.4's table, in both directions** (Opus round 12, 4), each failing a case of row 43:
    - `unattempted` / `uncertain`: a killed R with no `sending` reported `unattempted` (absence used as evidence) fails "after `connected`" and the full `/dev/shm` case; every spawned role reported `uncertain` (revision 10's conservative rule) fails the never-spawned and connection-failure cases; E1 without the release flag fails the gated-start-before-release case (Opus round 14, 4);
    - `uncertain` / `applied`: an unrecorded confirmation reported `applied` fails "after C, before the record"; a recorded `applied` reported `uncertain` fails "after the record";
    - `uncertain` / `refused`: a bare exit 3 reported `refused` fails the `SIGINT` case; a SQLSTATE refusal reported `uncertain` fails the server-refusal case;
    - C's output deciding the rotation fails "during C";
  - the state decided by the landing point instead of the evidence fails the race cases;
  - R in the wrapper's process group fails the `SIGINT` case, whose code becomes `interrupted` instead of `password-setup`;
  - the trap ending R with `SIGINT` instead of `SIGTERM` fails the wrapper-stop cases, where a fault psql shim records the signal its group received (Sol round 13, 4);
  - the gated start removed (R running before its group is confirmed) fails the gated-start cases;
  - E3 or E4 accepting a partial or unlisted line fails the truncated-error and mid-session-loss cases; E4 without its LF check fails the unterminated start-up case (Sol round 14, 4);
  - the trap taking `$!` without its three conditions, or skipping the group `SIGKILL` after an `ESRCH`, fails the gated-start cases; the trap's `wait` taken once, not repeated, fails the second-signal-during-the-reap case; no `PIPE` handler fails the gate-killed case;
  - the trap's re-entry handler removed fails the second-signal cases;
  - the report printed after the server's shutdown fails row 43c;
  - the trap reading the removed record fails H3; step 4 clearing only `EXIT` fails H4 as PID 1;
  - generated options appended after `--` fail row 6b.

## 11. The build order
1. **The harness and the generator,** red against today's wrapper. First, the native lock-inheritance check (5.9).
2. **Routes, the parser,** R0, S0, R1 to R3 and R5.
3. **Format 2:** the marker, the extension, the HBA files and their constants, the digest and the release guard. Then R4 (which needs the constants), R6, the lock, the cleanup, R7 and R8 (Opus round 6, 8).
4. **R9 to R19,** and the pins.
5. **The private phase.**
6. **Health:** the probe socket, the endpoint, the script, Compose, the timings, the candidate-tag build.
7. **The handover and step P.**
8. **Real rows,** faults and network modes.

## 12. The brief's inputs, traced

| Input | Where |
|---|---|
| Round 1 S3; round 2 S2-2: a pre-policy volume; `-D` elsewhere | R7; R9b, R11; rows 20, 26 |
| Round 3 S3-1, O3-1: literal parsing bypassed; the preload replaced | R10 to R13 by `-C`; 3.1; rows 26 to 28 |
| Round 4 S4-1: the private start on files alone | R19; row 35 |
| Round 4 S4-7: a quoted preload | R12; row 27 |
| Round 4 O4-1: the path form; non-root | R2, R0; rows 5, 10, 11 |
| Round 4 O4-4: refusals undocumented; the repair | section 6; the repair after R9b; row 51 |
| Round 4 S4-6/O4-2; round 5 S5-6/Opus P3-2: the healthcheck | 8.1, 8.3; rows 1 and 60 |
| Round 5 S5-3 (P2-3): the private socket | 5.3; row 36 |
| Round 5 S5-7 (P3-7): non-root runs the private start first | R0; row 10 |
| Round 5 O5-3, O5-4: the README stopgaps | section 6's sentences and 3.2, under the README guard |
| Round 6 S6-5 (P2-5): failures after a password change | 5.4 to 5.7; rows 37 to 47b |
| Round 6 S6-6, O6-1: a shared volume; the trusted loopback | a fixture per row; keys over SCRAM TCP; loopback trust removed and the HBA pinned (section 4) |
| Round 6 O6-4, O6-P3-2: another build's volume; the healthcheck's place; `dynamic_library_path`; other libraries; server modes | R7 with format 2; section 8; R14; 3.2; R1 |
| Round 7 O7-1: the coverage criterion | 10.1 |
| Round 7 S7-1: a failed public start; informational commands; a lost reply; keys after failure | 5.7; section 2; 5.4; rows 14, 38, 47, 47b |
| Round 7 S7-8, O7-P3-3; round 8 S8-5: the start suite's assertions | row 1 and 10.2's rule |
| Round 7 S7-7/O7-P3-7; round 8 S8-6, O8-P3-3: retained volumes; fact H's builds; fact L | row 20; rows 38 and 39 |

**The README also lists** (restored; Opus round 6, 2): the stated limits of 3.2, and the environment variables the handover drops (`KRB5_KTNAME`, LDAP's TLS variables and the rest), as a contract change.

## 13. Design rounds traced

### 13.1 Design round 5

| Finding | Where answered |
|---|---|
| Opus 1; Sol 2: DL-124's restore command | 4.3: `rm -rf` then `cp`, `chown` and `chmod`, with the printed path; `hba-config` and its own command; rows 21b and 23b over every case |
| Opus 2; Sol 1: the upgrade loses the image's grants | **superseded in round 6** by the documented manual route (7.4). At the time, 7.4: every `ACL` and `DEFAULT ACL` dropped; `apply-database-policy.sh` re-run in the build's order; deployer grants rendered from the archive; step 9 and the rehearsal |
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

### 13.2 Design round 6

| Finding | Where answered |
|---|---|
| Sol 1 (P1), Opus 1 (P2): the upgrade grants `demo` access to deployer tables | **the coordinator's decision:** the automated restore removed; 7.4's documented manual route and its one rehearsal (row 61) |
| Sol 2: the shared policy script cannot complete the restore | removed with the automated restore |
| Opus 2; Sol 6: assertions lost in consolidation | 10.2's "each row asserts" and outcome rule per class; rows 5, 38, 43, 46, 47, 47b; the probe query (8.3) and its negative control (row 60); `ENOLCK` (row 19b); 10.1's replay and "left out" inline; section 12 inline |
| Sol 3: alternate `-D`; R10, R11 and R17 | R9b before R10; R17's fixtures (row 33); rows 26 and 26b; row 50 split from 15b |
| Sol 4; Opus 8: the `hba-config` remedy's spellings | 4.3's `sed` with the `I` flag and the optional `=`; rows 23 and 23b |
| Sol 5; Opus 3: R4 by mount, not device | 4.2's mount IDs, covering the volume copy too; rows 16 to 16e |
| Sol 7: per-role states | 5.4's ordered rules and the record printed on every post-rotation exit; rows 43 and 46 |
| Sol 8; Opus 5: the handover's environment and its derivation | 5.1's one derivation and execution-level contract |
| Sol 9; Opus 6: the format guard and tags | 7.2's candidate-against-history check, the bump-both rule, and the tag rule |
| Sol 10: the Podman fallback's store | 8.2's `podman --url` |
| Sol 11: `non-root` first; row 20; `policy-marker`'s route | R0 before S0; row 20; section 6's sentence |
| Opus 4: R8 against the constant | 4.3 |
| Opus 7: shared IPC | 5.1's stated limits |
| Opus 8: buildability | `apply-database-policy.sh` removed; R4 moved to build step 3; rows 16 to 16d listed separately |

### 13.3 Design round 7

The 7.4 commands this round's answers name were removed in revision 9, by the coordinator's round 8 decision (13.4).

| Finding | Where answered |
|---|---|
| Sol 1 (P1), Sol 2, Opus 1: the manual route's commands | 7.4: dumps with `-x -O --no-comments` (checked natively on `pg_dump` 18.7), three variants with exact commands, roles by query with no memberships, loading as a checked non-superuser through `SET ROLE` and `psql --single-transaction` with `ON_ERROR_STOP` (direct `pg_restore --role` fails on the image's revoked `set_config`, checked natively); "not carried over" extended; row 61 per variant |
| Sol 3: the old server reachable during the upgrade | 7.4's maintenance runs: `--network none`, `listen_addresses=''`, dumps through `docker exec` over the socket; row 61 |
| Sol 4: role states lost on a public failure | 5.4: the per-role lines printed once before the final `exec`; rows 46b, 47, 47b |
| Sol 5; Opus 3: failure boundaries in the class rules | 10.2: classes for the lock, the cleanup, and before the rotation; the (A) key proof and the witness start; rows 42, 42c, 42d, 46b, 49, 49d |
| Sol 6: the negative control bypassing the wrapper | 8.3; row 60 with its reversal |
| Sol 7: HBA remedies with mounts | 4.3; rows 21c and 23c |
| Sol 8: row 39b against the contract | rows 15c and 39b |
| Sol 9: the release flag in the candidate | 7.2 and its new test |
| Opus 2: the stale reference | 4.3 |
| Opus 4: the message per case; the old image; the inspection step | section 6's `policy-marker` cases; 7.4's step 2 |
| Opus 5: `hba_file'x'` | 4.3's stated limit |

### 13.4 Design round 8

**The coordinator's decision:** version 1 ships no scripted upgrade recipe; it names the route and keeps the volume (7.4, with the reason). That removes the route class whole.

| Finding | Where answered |
|---|---|
| Opus 1 to 3; Opus P3 4, 6 and 7; Sol 1 to 5: the scripted recipe's commands, readiness, quoting, atomicity, sequences, references and row 61 | **removed by the decision:** 7.4's recipe, its stated limits and old row 61 are gone. 7.4 now gives the message, and row 61 asserts it. The export and the load are stated as the deployer's own, not certified |
| Sol 6; Opus P3 5 (the second printing): the role-log rules on failure | 5.4: states initialised before the private start; printed exactly once per run, by one rule; `handover_failed` prints none (5.7); rows 38, 42, 42d, 46, 46b, 47, 47b assert count and order |
| Sol 7: the witness start's key baseline | 10.2: the baseline is the keys in force before the attempt; the Start rule refuses a prior key only where it differs; the new (P) class for failures after the `exec`; rows 38, 46b, 47, 47b |
| Sol 8: a mounted file chosen through `include_dir` | 4.3: any configuration file mounted from outside the volume is edited at its source; row 23c covers a `config_file`, a mounted `postgresql.conf` and an `include_dir` file |
| Sol 9; Opus P3 5 (row 20): each case's sentence | row 20, with each fixture's marker content and its sentence |
| Opus P3 5 (row 61's variant (a)); Opus P3 5 (10.4's reversals for 7.4) | removed with the recipe |

### 13.5 Design round 9

| Finding | Where answered |
|---|---|
| Sol 3; Opus 1: `hba-config` cannot name the file that set `hba_file` | 4.3: the sentence names the reported `config_file`, whether it or `postgresql.conf` is on another mount (`mnt_id`), and the include sentence; row 23c, with several files in the `include_dir` |
| Sol 1: the named route replaying grants | 7.4 and section 6's marker-`1` sentence name `pg_dump --no-acl --no-owner` and leave default privileges to the deployer's review; row 61. No commands |
| Sol 2: a stale state on an interrupted rotation | 5.4: `in progress` before each role's client starts, reported as `uncertain`; row 43's new cases |
| Sol 4: a socket-only public start | 10.2: no TCP listener and health through the probe socket; keys over the socket are no evidence; row 36b with a TCP witness |
| Sol 5; Opus P3 4: exact marker bytes | 7.2: `2\n`, compared as bytes; row 20's near matches |
| Opus P3 2: the final print's sequence | 5.4's six steps |
| Opus P3 3: the log count in the class rules; the third reversal | 10.2's (W) and (P) rules; 10.4 |
| Opus P3 4: the self-test's place; 5.8's wording | section 3's table; 5.8 |
| Opus P3 5: using the old image | 7.4's two sentences; row 61 |

### 13.6 Design round 10

| Finding | Where answered |
|---|---|
| Sol 1: exposure during export | 7.4 and section 6's marker-`1` sentence: run the old image socket-only, with no network, and export with `docker exec`; row 61. Advice, not a recipe |
| Sol 2: the healthcheck reaching another server | 8.3: the probe clears libpq's environment itself and names its socket; row 50c (numbered 50b in revision 11) with its reversal |
| Sol 3; Opus P3 1: a stop during the handover | 5.4: the trap prints from the in-memory copy once step 2 ran, and removes the endpoint; the step 4 to 6 window stated as a limit; section 6's trap; row 46c |
| Sol 4: the namespace assertion | 10.2's Start rule, for every native Start |
| Sol 5: 5.8's key | 5.8: the key in force after this run's rotation |
| Opus P3 2: the trap and the marker-only rules | superseded in revision 12 by 5.4's decision table (13.7). At the time: 5.4's `in progress` paragraph; row 43's case after `connected`, and its first case's injection point |
| Opus P3 3: the new image's defaults; `pg_restore --no-owner` | 7.4's two sentences, the marker-`1` sentence, row 61 |
| Opus P3 4: the `handover` exception | 10.2's (W) rule |

### 13.7 Design round 11

**The coordinator's decision:** the role report under interruption is a hot area (rounds 9, 10 and 11 each found the gap at a neighbouring point). The per-role state rules in 5.4 are replaced by one decision table, written once, and row 43 becomes one table test over every row of it.

| Finding | Where answered |
|---|---|
| Sol 1: a stop during the confirmation reported `unattempted` | 5.4's decision table: the markers and exit status are R's; C's output never decides the rotation; T6 is `uncertain`; row 43 over every row, with a reversal per boundary |
| Sol 2; Opus P3 2: the healthcheck reversal | row 50c: `PGHOSTADDR` the redirect reversal; `PGHOST` and `PGPORT` independence checks, `PGPORT` by `docker exec -e` |
| Sol 3: an empty `PG_VERSION` | R6; row 18 |
| Sol 4: row 56's two attempts | row 56, each attempt its own class; the first attempt's keys the restart's baseline |
| Opus P3 1: the duplicate `50b` | the probe-environment row renumbered `50c`; 13.6 updated |
| Opus P3 3: step 4's traps | 5.4's step 4, `trap - EXIT TERM INT HUP QUIT`; row 43's reversal at H4 |
| Opus P3 4: "after R9" | section 12 |

### 13.8 Design round 12

**The coordinator's decision:** the role report is still the hot area, for the fourth round. A state decided by where a signal landed is racy, and one decided by a marker's absence is defeated by a lost write. So the state is computed only from evidence observed after the reap, the table is indexed by that evidence, every state but `uncertain` needs positive evidence, R runs in its own process group and is ended by `SIGTERM`, and the trap prints the report before stopping the private server.

| Finding | Where answered |
|---|---|
| Sol 1: the client advances between the landing and the reap | 5.4's evidence table; row 43's race cases |
| Sol 2: a full `/dev/shm` truncates the `sending` marker | E5: missing or truncated evidence is `uncertain`; row 43's lost-evidence case |
| Sol 3: a slow shutdown inside Docker's grace loses the report | 5.4's trap order and its bound; 5.5; row 43c |
| Sol 4; Opus P3 3: row 43's blanket outcome | row 43: the (W) outcome for the points before the handover, H1 to H3 and H6b; the Start rule for H4 to H6 as PID 1; "none" defined outside PID 1; the post-rotation witness keys; the H4 limit's `docker stop` sentence |
| Sol 5: a terminal `--` | 3.1; 5.7; row 6b |
| Opus 1: exit 3 after a commit read as `refused` | E3 needs a SQLSTATE `ERROR` after `sending`; a bare exit 3 is E5; R in its own group, ended by `SIGTERM`; row 43's `SIGINT` case |
| Opus P3 2: the table's gaps (a) to (d); the printers | by evidence: (a) and (c) are E5, (b) is E4 or E5, (d) no line before the private start; the printer is always the `EXIT` trap or step 5, named by the refusal code |
| Opus P3 4: reversals in both directions | 10.4 |

### 13.9 Design round 13

**The coordinator's decision:** the evidence table stands (Opus confirms one state per point and positive evidence for every state but `uncertain`). What was left, how the clients start and how evidence is captured, is fixed by construction.

| Finding | Where answered |
|---|---|
| Sol 1; Opus P3 7a: a stop before the client is trackable | 5.4's gated start for R, C and the private server (`setsid --wait`, the group confirmed, the release pipe); E1 by the release flag; `ESRCH` tolerated; an interrupted `wait` never taken as a status; 5.3; row 43's gated-start cases |
| Sol 2; Opus P3 4, P3 6: incomplete evidence | 5.4: complete, LF-terminated lines in the listed forms, observed natively; E4 anchored to the start-up form as the first line; the in-memory record and flag authoritative; the lost-evidence code; row 43's truncated-error and mid-session cases |
| Sol 3; Opus P3 2, P3 3: row 43's outcomes | row 43: H6b as row 46; H6 split; the wrapper's private stop interrupted; the key implied by each `uncertain` case; row 43c's runtime kill and the 3-second check |
| Opus P3 5: a second signal | 5.4's step 0; row 43's second-signal cases |
| Opus P3 7b: the 2-second bound | 5.4: every foreground command bounded |
| Sol 4: the termination reversal | 10.4: a fault shim records the signal R's group received; the `SIGINT` case's `password-setup` code |
| Sol 5; Opus P3 1: row 6b | 10.2 after row 6, as a Start row; the misplaced line removed |

### 13.10 Design round 14

Every fix is a specification sentence or a row 43 case, with no new mechanism (the coordinator's round 14 instruction).

| Finding | Where answered |
|---|---|
| Sol 1; Opus P3 1: the trap's reap | 5.4: the trap's choice of PID; both the PID and the group signalled, the group `SIGKILL` always; the pipe closed as step 0's second act, its write end closed in every child; the confirmation bounded by a ready byte and `/proc/PID/stat`, its failure `internal`; row 43's gated-start cases assert the program never ran and this child was reaped |
| Sol 2; Opus P3 5: the trap's own `wait` | 5.4: repeated until a return with no signal recorded during the call; step 0 the first statement of every handler and of the `EXIT` trap; row 43's second-signal case proves the reap |
| Sol 3: H6 during recovery | row 43's H6 in three parts, with the startup case's outcome and `SIGHUP` as a reload |
| Opus P3 2: `SIGPIPE` | 5.4: the recording handler for `PIPE`; row 43's gate-killed case |
| Sol P3 5; Opus P3 3: one refusal flag | 5.5: held in memory, the file never read by the trap, the lint over every subshell context; handover step 2 a snapshot |
| Sol P3 6; Opus P3 4: row 43's keys and labels | row 43: the three keys; the private stop `applied` with `interrupted`; 10.4's E1-without-release reversal |
| Sol P3 4: E4's reversal | row 43's unterminated start-up case; 10.4 |
| Opus P3 6 (a) to (d) | 10.3's native forms; the truncated-error injection; the test's "holds"; `/proc/PID/stat` after the last `)` |
