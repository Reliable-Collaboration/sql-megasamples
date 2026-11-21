# Templates, copies, the scripting CLI and the account model: version 1

**Design record · 2026-11-21 · round 8, the drafter's part. Status: the specification for a test-first build (DL-114). Nothing here is built. Its 58 feasibility gates have run on an isolated stack; no regression of section 8.2 has.**

- **What this is.** The design of **version 1** of sql-megasamples' pristine templates, per-test copies, the commands that scripts drive them with, and the account model that goes with them. It carries the strict PostgreSQL read profile of pull request #14.
- **Version 1 only.** The two deciders staged the design (DL-108): one bounded version 1, merged and rolled out once, and later stages as new work. This record holds exactly the list of DL-108 items 5 and 8 to 11, at the placements of its items 1 to 3. Its surface is frozen (section 0).
- **The fuller design is kept in Git history,** at `e0c2f935` of this file, as the source for the later stages. Section 11 names each stage, what waits in it, and every deferred finding against it.
- **What sql-megasamples is.** A stand-alone offering: sample database servers that someone spins up, in any network setting (DL-107). Sections 2 to 6 describe that product. A deployment is configuration; DataIntent's development instance is one, in section 7.
- **Rounds.** Round 1 is `2a15387`; round 2 `bdd9033`, with `9fe0bbd`; round 3 `e0c2f935`; round 4, the cut, `e8af920`; round 5 `0896ebc`, the revision the gates ran on; round 6 `84d2c96`, revised from the gates. **Astra's review 5, on round 6, found eleven P1s, nine P2s and a P3** (`astra-r5.md`). Section 12.1 gives each a disposition; the rest of section 12 keeps what the gates changed and the earlier reviews' answers. **Round 7 is `d578f755`.** Astra's one check of it accepted 14 dispositions and disputed 7, with two readings, in ten findings (`astra-check-r7.md`); the deciders ruled on them (DL-115). **Round 8 holds only those rulings, and one direction of the owner's** (DL-116): declared writers on MySQL's working databases are back in version 1. Each is a changed rule and its test row. Section 15 lists them. The reviews are in the coordinator's ignored `.local/megasamples-design/` in DataIntent.
- **Where it stands** (DL-108 item 12): **version 1's gates have run,** all 58, each with its control shown. 55 Passed at once and three Failed; the deciders ruled on the three (DL-111, DL-112), and their re-runs Passed. **No gate that version 1 rests on is unrun.**
- **How it proceeds** (DL-114): the paper loop has ended. **Round 7 was the one bounded revision.** Astra checked it once, and the deciders ruled on what she disputed (DL-115). **Round 8 applies those rulings, and the owner's direction on MySQL's writers (DL-116), and nothing else; the coordinator confirms it against section 15, as a checklist and not a review.** Then the build is test-first on the isolated stack, **with the four P1 routes of 8.2 as the first tests of its reset slice,** and Astra and Fable review the code and tests to two rounds in a row with nothing to fix now. The gates do not count toward those rounds.
- **The design stays the specification.** [114-4] Each amendment from the build lands with its code and its reason. One that adds to section 0's surface returns to the deciders; one that narrows is free. **Every claim here and in the README traces to a test through the real commands, or is removed before the merge** (8.3).
- **The bar for a finding** (DL-040, DL-114 item 1) is in section 13, with the table of ordinary routes that each disposition cites.
- **Method.** This record's own work is reading only: no container, no database connection, and no credential file. **What it says of how an engine behaves is what the gates' record shows, and nothing more.** The gates were run by another task, on a task-owned isolated stack.
- **Marks.** Each claim carries one:
  - **[R]** read in the cited file and line;
  - **[G-n]** observed: gate *n* of section 8.1 Passed on the isolated stack. It is a kind of **[R]**: read in the gates' record, `GR:`, at that gate's row. Section 8.1 says what each showed, and what it was run on;
  - **[I]** inferred, and not load-bearing;
  - **[D]** decided here, with the reason;
  - **[108-n]** decided by the two deciders in DL-108, item *n*. Likewise **[109-n]** to **[115-n]** for DL-109 to DL-115; **[114-2A]** is narrowing A of DL-114's item 2. **[115-W]** is DL-115's ruling on the whole-engine escape, and **[115-U]** its ruling on an upgrade after an older `down`. **[116-n]** is the owner's DL-116.
  - A table or list whose heading line carries a mark is marked as a whole. A file and line cited inside any row is **[R]**.
- **Citations.**
  - `SM:` is sql-megasamples at `main`, `e61335f`. `PR14:` is its branch `fix/strict-read-account` at `2879fc4`.
  - `GR:` is `docs/validation/dl-077-v1-gates.md` on sql-megasamples' branch `gates/dl-077-v1` at `d805539d`: the first run's rows at `:15-72`, the re-runs' at `:144-148`. Each gate's launcher is `tests/gates/<gate>` there.
  - `DL:` is DataIntent's `docs/work/decision-log.md` on `origin/coordinator/journal-during-full`: DL-070 to DL-103 at `d02f7384`; DL-104 to DL-108 at `5831ef43`; DL-109 to DL-112 at `a0a23d23`; DL-113 and DL-114 at `bee37661`; DL-040 there too; DL-115 at `7c5773e9`; DL-116 at `f24e929c`. `LR:` is `docs/work/lines-register.md` there.
  - `ED:` is DataIntent's `docs/work/samples-service-editing-requirements.md`, `MR:` its `docs/work/samples-service-requirements-and-architecture.md`, and `DI:` any other DataIntent file, all at `4a8aad61` (`origin/coordinator/samples-p1`).

## 0. Version 1's surface

**This is the whole of it.** [108-7] Nothing below may be added to without the deciders. Anything may be removed or narrowed.

| Kind | Version 1 has |
|---|---|
| **Commands** | `megasamples copy create`, `show`, `list`, `drop`, `renew`, `release`, `sweep`. `megasamples reset`, `megasamples up` and `megasamples down`, as today, with the options below. No other command is new. [109-1: no `template` and no `interface` command.] |
| **Options** | For `copy`: `--host`, `--port`, `--user`, `--connect-timeout`; `--password-file` or `--password-stdin`; `--prefix`, `--label`, `--lease`, `--identity`, `--wait`, `--dry-run`; for SQLite `--templates` and `--dir`. For `reset`: `--json`, `--operation`, `--discard sessions`, `--discard engine`, `--unattended`, `--status`, `--reconcile`. For `up`: `--discard engine`. |
| **Configuration keys** | `engines.<engine>.templates`; `engines.mysql.binary_log` [109-2]; `copies.namespaces` (each: `prefix`, `owner`, `max_copies`); `copies.foreign` (each: `prefix`, `demo_reads`); `accounts.readers` and `accounts.writers` (each: `name`, `scopes`). |
| **`.env` keys** | Today's four. `MYSQL_DEMO_PASSWORD`. One for each namespace's owner and each declared account: its name in upper case, then `_PASSWORD`. |
| **Formats** | The JSON document's `schema`. The `interface` number. Four records with a tag each: the service's, a template's, a copy's, an operation's. For SQLite, a manifest and a sidecar. |
| **Service accounts** | `postgres`, `root`, `admin` and `demo`, as today. A namespace's owner. A declared reader; **a declared writer, on both servers** [116-1]. On PostgreSQL, the groups of 4.1. |
| **Hook rules** | Four (4.3): the creator must hold the new owner's rights; a namespace's owner is confined to its namespace and to registered templates; a new database is closed to `PUBLIC`; a role without `CREATEROLE` cannot alter roles or default privileges. |

- **`--discard` is one option with a named value.** [109-3] `--discard sessions` ends people's sessions on a database's reset. `--discard engine` authorises replacing a whole engine's volume. A whole engine's reset refuses `--discard sessions` and requires `--discard engine`; so does `megasamples up` before it replaces a stale engine's volume (3.5).
- **Round 4's `reset --wait` is removed.** It was defined for `copy drop` only. [D: review 4's finding 18.]

**What version 1 contains, by DL-108's list:**

| DL-108 | In version 1 | Where |
|---|---|---|
| Item 5, first | Templates, copies and the scripting CLI on all three engines: create, show, list, drop, renew, release and sweep, with the lease as the protection. | 2; 3 |
| Item 5, second | Nothing ambiguous is ever removed: an interrupted create is kept and reported. | 2.2 |
| Item 5, third | One unsettled operation for each target, on every reset path. | 3.5 |
| Item 5, fourth | Pull request #14's corrected read profile, under every condition of DL-085, with the lines register's two items of line 10. | 4.2; 4.4; 4.5; 7.2 |
| Item 5, fifth | The hook's confinement of namespace owners. | 4.3 |
| Item 5, sixth | Privileged credentials private by default, even on loopback; bundled consoles that require sign-in before privileged access; `demo` still published. | 5.1 |
| Item 5, seventh | Reader and writer grants on both servers, declared in the configuration, locked until keyed, applied at start, and held through each reset: a reader's confirmed before `done`; **a MySQL writer's suspended before any change and restored only after `done`** [116-2]. | 4.6; 3.5 |
| Item 5, eighth | A safe service-side image restore. | 3.5 |
| Item 5, ninth | The CLI's contract for the formats version 1 has; the reset's session decision; the runbook's split. | 6; 3.5; 5.3 |
| Item 9 | A whole engine's reset refuses unless told to discard, and the service's record carries an identity for each volume. | 3.5 |

**What version 1 does not contain** is section 11: seven named stages and one ready addition. **What round 7 narrowed** [114-2]: no guarantee across a volume's replacement (A); no phases or reconciliation for a whole engine's reset (B). **Narrowing C, no declared writer on MySQL, was reversed by the owner** [116-1]: MySQL's declared writers are in version 1, and add to this surface by that direction.

## 1. What the design rests on

### 1.1 The product, as it is today

| # | Fact | Where | Mark |
|---|---|---|---|
| F-1 | **Every command of today's CLI that contacts a running engine does it through `docker exec`.** The reset starts a second container of the running image, and pipes a dump from it. | `SM:megasamples/credentials.py:29-70`; `SM:megasamples/reset.py:156-197`, `:245-304` | [R] |
| F-2 | **The CLI's output is text for a person,** and a command returns 0, 1 or 2. An unknown command is 2. | `SM:megasamples/cli.py:68-82`; `SM:megasamples/reset.py:384` | [R] |
| F-3 | **Resets exclude each other by a lock file** for one user on one host, one for each engine named, taken before anything changes. A whole engine's reset and a reset of one of its databases take the same file. | `SM:megasamples/reset.py:101-116`, `:370`; `SM:README.md:323-325` | [R] |
| F-4 | **PostgreSQL's reset of one database drops it with force, and only then restores it.** MySQL's pipes a dump that drops and reloads the schema in place, then compares row counts with the image's. SQLite's stops the consoles that read its files. | `SM:megasamples/reset.py:254-262`, `:294-302`, `:336-354` | [R] |
| F-5 | **Accounts today.** PostgreSQL: `admin` has `CREATEDB` and `CREATEROLE` and owns each sample database and what is in it; `demo` has `SELECT` on the tables. MySQL: `admin` and `root@'%'` hold all privileges with the grant option; `demo` holds `SELECT, SHOW VIEW ON *.*`. | `SM:engines/postgres/init/00-users.sql:10-12`; `SM:engines/postgres/init/20-grants.sql:4-7`; `SM:engines/mysql/init/00-users.sql:9-19` | [R] |
| F-6 | **Each health probe signs in as `demo`.** Passwords are applied at each start from the container's environment. | `SM:megasamples/engines/postgres/__init__.py:80`; `SM:megasamples/engines/mysql/__init__.py:139`; `SM:engines/postgres/entrypoint-wrapper.sh:17-35`; `SM:engines/mysql/entrypoint-wrapper.sh:19-40` | [R] |
| F-7 | **The registry has one row per database,** with a build id that is `dev` unless `MEGASAMPLES_BUILD_ID` is set. | `SM:megasamples/registry.py:52-88`, `:111` | [R] |
| F-8 | **A large configuration is large:** one bakes 22.712 GiB on MySQL, 20.902 GiB on PostgreSQL and 17.862 GiB of SQLite files. | `SM:docs/live-upgrade-runbook.md:97`, `:101-105` | [R] |
| F-9 | **Sizes on record are old, and of two kinds,** and none counts a dataset that appends to a core database. Three do: `nyc_taxi_yellow`, `chicago_crimes_full`, `dvdstore_reviews`. | `SM:ARCHITECTURE.md:170-171`; `SM:knowledge/decisions/tier-assignments.md:32-88` | [R] |
| F-10 | **MySQL's binary log grew to 10.9 GB** after a rehearsal of logical resets. The shipped server's configuration does not turn it off. | `SM:docs/live-upgrade-runbook.md:109`; `SM:engines/mysql/my.cnf:1-11` | [R] |
| F-11 | **One dataset reaches into another database:** `oracle_oe` depends on `oracle_hr`. | `SM:datasets/oracle_oe/dataset.yaml:8`; `SM:README.md:212` | [R] |
| F-12 | **Pull request #14** revokes `TEMPORARY` and routine `EXECUTE` from `PUBLIC` in every database and both templates, grants `admin` what it had, and grants `demo` an allow-list. A compiled hook closes `TEMPORARY` on each new database. A `SECURITY DEFINER` event trigger closes `EXECUTE` on each new routine. | `PR14:engines/postgres/init/10-read-profile.sql:4-35`; `PR14:engines/postgres/read-policy/read_policy.c:29-40`; `PR14:engines/postgres/read-policy/read_policy--1.sql:1-20` | [R] |
| F-13 | **Its grant to `admin` carries no grant option.** | `PR14:engines/postgres/init/10-read-profile.sql:10-13` | [R] |
| F-14 | **Its evidence:** 254 native cases Passed on an isolated stack; MySQL is not claimed strict, and `demo` there can take a named lock. **Its native guard names one machine's project and paths.** | `PR14:docs/strict-read-evidence.md:16-18`, `:30`; `PR14:tests/test_strict_read_native.py:20-30` | [R] |
| F-15 | **It merges into `main` without conflict.** | `git merge-tree origin/main fix/strict-read-account` | [R] |
| F-20 | **Each server accepts every account from every address that reaches its port.** | `SM:engines/postgres/Dockerfile:33`; `SM:engines/mysql/init/00-users.sql:9-18` | [R] |
| F-22 | **The reset reads its passwords in the host's own process,** by a reader under which an exported value wins over the file's. It hands them to the container it starts as that container's environment. | `SM:megasamples/reset.py:172-183`, `:246`, `:290`; `SM:megasamples/config.py:155-167` | [R] |
| F-28 | **The generated Compose file publishes every port on `127.0.0.1`.** That says who reaches the published port; it says nothing of who reaches the engine inside the stack's own network, nor of an image someone runs by hand. **Every password has a published default,** `admin`'s and the superusers' among them. | `SM:megasamples/compose.py:10-11`, `:30-31`, `:40`; `SM:megasamples/engines/postgres/__init__.py:76`; `SM:.env.example:5-9`, `:25-31` | [R] |
| F-29 | **The README and the runbook hold one deployment's story:** a dated account of "the maintained deployment", its LAN forwards, and a runbook headed "coordinator only". | `SM:README.md:16-20`, `:258-270`; `SM:docs/live-upgrade-runbook.md:1-3` | [R] |
| F-31 | **The bundled consoles and the generated pages hold administrator access.** phpMyAdmin signs a browser in with no form, and offers `admin` beside `demo`. DbGate and CloudBeaver are given `admin`'s password as a stored connection. **The landing page and the Adminer help page print `admin`'s configured password** to whoever opens them. | `SM:consoles/phpmyadmin/config.user.inc.php:15-27`; `SM:megasamples/engines/postgres/__init__.py:91-100`; `SM:megasamples/console_config.py:27-44`; `SM:megasamples/console_page.py:120`, `:127`, `:197-198`, `:246`, `:257`, `:286`, `:297`, `:311` | [R] |
| F-32 | **`megasamples up` replaces an engine's data volume by itself,** when the running container is not on the current image: it recreates that engine with its anonymous volumes renewed. | `SM:megasamples/job.py:166-177` | [R] |
| F-33 | **Callers of today's reset that expect it to succeed with no option:** the Makefile's shim; **six validation scripts, at seven call sites,** which between them reset whole engines, every engine at once, every configured pair, and single MySQL and SQLite databases; the README's examples, a single SQLite database among them. | `SM:Makefile:62`; `SM:docs/validation/probe-reset-flags.py:47`; `SM:docs/validation/rehearse-lts-resets.py:89`, `:121`; `SM:docs/validation/probe-approved-datasets.py:135`; `SM:docs/validation/rehearse-lts-append-reset.py:32`; `SM:docs/validation/rehearse-lts-persistence.py:55`; `SM:docs/validation/validate-credential-prerequisite.py:43`; `SM:README.md:294-298`, `:416` | [R] |

| F-34 | **Today's MySQL image bakes a server identifier.** Its data directory is initialized in the build and copied whole, `auto.cnf` included, so every volume seeded from it reports the same server UUID. | `SM:engines/mysql/Dockerfile:32`, `:63`; `GR:` G-33a, `:67` | [R] |
| F-35 | **MySQL databases known to carry triggers, from the repository's own sources:** `adventureworks_lt`, `oracle_oe`, `oracle_hr` and `sakila`. Datasets loaded from upstream dumps were not counted. | `SM:datasets/adventureworks_lt/objects.sql:37-65`; `SM:datasets/oracle_oe/objects.sql:123`; `SM:datasets/oracle_hr/PROVENANCE.md:45`; `SM:datasets/sakila/tests/triggers.yaml:7-27` | [R] |

### 1.2 One consumer, DataIntent

Facts about one consumer. Section 7.2 is where they are used.

| # | Fact | Where | Mark |
|---|---|---|---|
| F-16 | **Its fixture** makes `di_reader` and `di_analyst` as `admin`, and each `di_…` database from `di_template`, `template1` or `template0`. It gives each of its roles to `admin`, inherited. | `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureServer.cs:27-32`, `:131-134`, `:224-230`, `:403-409` | [R] |
| F-17 | **Its provider, as a read account,** lists databases `WHERE NOT d.datistemplate`, and calls `pg_database_size(oid)`, `pg_export_snapshot()` and `pg_current_snapshot()`. It imports the snapshot in another transaction. | `DI:src/DataIntent.Adapters/Postgres/PostgresSourceServer.cs:237-240`, `:347`; `DI:src/DataIntent.Adapters/Postgres/PostgresSnapshot.cs:136` | [R] |
| F-18 | **Of those built-ins, none of the three is in pull request #14's allow-list.** | a search of `PR14:engines/postgres/init/read-routine-names.sql` | [R] |
| F-24 | **Its comparison before an upgrade has five parts, C1 to C5.** C5 asks that an export be refused, with nothing in its stream, after an elevation **and** when the fresh check cannot be made. | `MR:` section 3, "The comparison as designed" | [R] |
| F-25 | **One rollout rebuilds its instance from a build of `main`.** Each engine image copies `README.md`. | `DL:` DL-103; `SM:engines/postgres/Dockerfile:13` | [R] |
| F-26 | **What must hold before pull request #14 merges:** C1 passed against its candidate; the other roles settled; **its allow-list reconciled with DataIntent's own routine inventory (IA-01); one independent review covering its compiled hook and its `SECURITY DEFINER` event trigger;** the account model; permissions kept. It stays unmerged until the instance's first cutover is accepted, and the read account's native admission on the candidate comes after that. | `DL:` DL-085 items 1, 3 and 4 | [R] |
| F-27 | **DL-078 asks that the README lead with the project's purpose,** and cover the LTS engines and clients, and the datasets. | `DL:` DL-078 item 1 | [R] |
| F-30 | **Its instance is forwarded to a LAN** by two socket units outside the product. It keeps the prefix `di` for databases and roles of its own, and plans an administrator account on MySQL that manages accounts. | `DL:` DL-075; `MR:` A-02, 2.10 | [R] |

## 2. Capabilities: templates, copies and the sweep

### 2.1 Names and namespaces

| Thing | Name |
|---|---|
| The template | `<database>_start`, where `<database>` is the registry's name for the physical database (F-7) |
| The working copy | `<database>` |
| A test copy | `<prefix>_<database>_<token>`: the token is twelve hexadecimal digits that the CLI issues |
| A PostgreSQL reset's transient | `<database>__new_<8 hex>`, `<database>__old_<8 hex>` |

- **The CLI names a copy; the caller does not.** The token is the first twelve digits of the copy's identity, 128 random bits. The caller's label is in the record, and is unique among a namespace's live copies: a caller that lost a reply finds its copy by its label. [D]
- **What is promised of a name, and no more.** A name is never issued while its record or its object exists: both are confirmed absent under the namespace's lock before a row is written. **A name may come again once both are gone,** by a collision of twelve digits. Version 1 makes no grant by a copy's name on MySQL, so nothing of its own can wait there for a later copy. **A grant an administrator made by hand on such a name, or on a pattern over it, is not the product's.** The product reports it, makes no claim that such a copy has one writer (4.7), and does not remove such a copy where the grant lets its holder replace the schema (2.2). [D]
- **Characters and length.** A prefix matches `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` and is at most 16 bytes. A label matches `^[a-z0-9]{1,24}$`. A whole name is at most 63 bytes on both engines; the build refuses a database name longer than 33. [D]
- **Reserved:** the suffix `_start`, a double underscore, the name `megasamples`, **and the prefix `working`,** which is the built-in scope of every working copy (4.6). [D: review 5's finding 17.]

**A namespace** is one prefix with one owning account, baked into the image:

```yaml
copies:
  namespaces:
    - {prefix: copy, owner: copier, max_copies: 32}   # the default
  foreign:
    - {prefix: P, demo_reads: false}                   # a prefix a consumer keeps for objects of its own
```

- **Any number of namespaces, each with an owner of its own.** An owner is locked until its key is set, so a namespace can be baked ahead of need.
- **Every prefix that is *defined* is checked against everything it must not reach.** The build refuses a configuration in which the prefix `P` of a namespace or of a foreign namespace:
  - equals, or is followed by an underscore at the start of, the name of any registered database, any template, `megasamples`, or an engine's own schema;
  - equals another defined prefix, or one begins with the other followed by an underscore.
- **A declared account's scope is a *reference*, not a definition.** It names `working`, or the prefix of a namespace that is defined; anything else is refused. So a reader of the namespace `copy` is declared with the scope `copy`. [D: review 4's finding 16: round 4's rule refused that.]
- **On MySQL every underscore in a grant's schema pattern is escaped,** in a prefix and in a database's own name. [G-11a]

### 2.2 A copy's record, its proof, and what is ever removed

The same on all three engines. [D]

**The record.** Each namespace has a ledger: on the servers a table in `megasamples` that the namespace's owner and the administrators can write; for SQLite a sidecar beside each file. A row holds the copy's `name` and `identity`, its `label` and `database`, its `phase`, a `revision` raised by every change, `lease_until`, and its `proof`.

**The phase is written before the step it announces:** `reserved`, then `issuing`, then `created`, then `ready`; and `dropping`.

**The proof is a retained identity, tied to the exclusive creation of the object.**

| Engine | Exclusive creation | What is retained |
|---|---|---|
| PostgreSQL | `CREATE DATABASE`, which fails on an existing name | the database's OID, recorded at `created`, and a comment on it that carries the identity [G-24p] |
| MySQL | `CREATE DATABASE`, never `IF NOT EXISTS` | **a marker inside the schema: a disabled event named `megasamples_copy_<identity>`,** made as the first statement after the schema. It goes when the schema goes, and no other schema has it. [G-24m] |
| SQLite | a hard link to the final name, which fails if it exists | a second link to the same file, kept for the copy's whole life in `.megasamples/` under the identity. While it is kept, the inode cannot be given to another file. [G-19b] |

- **Round 4's MySQL proof is withdrawn.** It was a fingerprint of the tables' creation times, which a second can repeat. [D: review 4's finding 6.] The marker is one more object in a MySQL copy: a consumer that lists a copy's events sees it, and the README says so.

**Locks.**
- **The change lock** of a name is held for the whole of any change to that copy: a session's advisory lock on PostgreSQL, taken in the `megasamples` database [G-7a, G-7b]; a named lock on MySQL [G-15a]; a `flock` on SQLite, on a lock file of its own that is never the sidecar and never removed while its copy's record exists [G-20].
- **The session that runs a change is the session that holds its lock,** and a command never reconnects (3.5).
- **A namespace lock** is held only while a reservation is counted and written.

**Creating,** under the name's change lock:
1. **The reservation, atomic:** under the namespace lock, the live copies are counted against `max_copies`, an identity is issued, the name and its row are confirmed absent, and a row is written: `reserved`.
2. `issuing` is written. The object is made (2.3, 2.4, 2.5).
3. The proof is made and recorded: `created`. The object is filled.
4. `ready` is written. The lock is released.

**Nothing ambiguous is ever removed.** [108-5] **An interrupted create is kept and reported, by every command, on every engine.**

**What a copy's state is, and who may act on it, are two things.** [D: review 5's finding 16.]
- **`copy show`, `copy list` and `copy sweep --dry-run` classify and report. They change nothing:** no row, no object, no lease.
- **Recovery is done only by a command that was asked to change that copy:** `copy drop` of it, or a sweep that is not a dry run.

| The row's phase | The change lock | The object | State, as every command reports it | What `copy drop` of it, or a real sweep, may do |
|---|---|---|---|---|
| none | — | present, in the namespace | `unmanaged` | nothing |
| any | held | — | `changing` | nothing |
| `reserved`, `issuing` | free | absent | `stale` | remove the row |
| `reserved`, `issuing`, `created` | free | present | **`interrupted`** | **nothing.** No command removes it. |
| `ready` | free | present, proof matches | `ready` | the rules below |
| `ready`, `dropping` | free | absent, and nothing set aside | `gone` | remove the row |
| `dropping` | free | present, proof matches; or, on SQLite, set aside and the same file as the retained link | `dropping` | finish the drop |
| `ready`, `dropping` | free | present or set aside, **proof does not match** | `inconsistent` | nothing is removed. On SQLite a file that was set aside is put back by a link that cannot overwrite, or left aside. |
| `ready`, `dropping` | free | present, proof matches, **but another account could replace it** (MySQL, below) | `not-exclusive` | nothing: exit 5 |

- **The state is decided by the row's durable phase and by what is observed,** never by the error a step returned (2.6).
- **A create that was killed after `ready` was written is `ready`.** Its caller finds it by its label.
- **Where the CLI cannot establish which object it would change, it keeps the object and the record, reports it, and attempts no further removal of that copy.** [114-2] An `interrupted`, `unmanaged`, `inconsistent` or `not-exclusive` object is an administrator's to resolve, by hand. `copy show`, `copy list` and a dry run stay safe ways to look at it.

**Removing a copy: the proof is checked at the removal itself.** [D: review 4's finding 6; review 5's findings 6 and 11.]

| Engine | The removal | What stays possible |
|---|---|---|
| PostgreSQL | Under the change lock: the OID, the comment and the owner are read; then `DROP DATABASE` by name, plain. | PostgreSQL has no drop by OID. Between the read and the drop, a database could be put under the name only by someone who can first drop the old one: its owner or a superuser. No other account can enter that window. [G-24w] |
| MySQL | Under the change lock: **first, who else could replace it.** The service keeps a view, readable by a namespace's owner, of every grant that another account holds on a name or pattern inside its namespace. If one of them gives create or drop on this copy's name, nothing is dropped: `not-exclusive`. Any other is reported with the copy, as a warning. **Then the marker is read in the schema.** If it is not there, nothing is dropped: `inconsistent`. Then `DROP DATABASE`. | Between the reads and the drop, only the namespace's owner or an administrator could replace the schema. [G-24w] An account that holds those rights on every schema is an administrator in effect, and is within that limit. |
| SQLite | **The sidecar first records `dropping`, and where the file will be set aside.** Then the final name is moved there, inside `.megasamples/`, and what was moved is compared with the retained link. The same file: both are removed, then the sidecar. Not the same: it is put back by a link that cannot overwrite, or kept aside, and reported. **A later command looks aside before it calls a copy `gone`.** | Nothing: the file compared is the file removed, and a crash at any point leaves a record of where the file is. |

- **The proof guards against accident and against a late or repeated command. It does not guard a principal against itself:** the owner of a copy, acting outside the CLI at the same moment, can defeat it on the two servers. That is said, and [G-24w] shows that nobody else can.
- **SQLite's adjacent files are not removed.** A `-wal`, `-shm` or `-journal` beside a dropped copy carries no identity; it is left and reported. No later copy takes that name while its record exists.

**Every command that changes a copy names the identity it expects.** `copy drop`, `renew` and `release` take `--identity`. Under the change lock the row is read again:

| Command | Requires |
|---|---|
| `renew`, `release` | the identity named; `ready` |
| `drop` | the identity named; `ready` or `dropping`; the proof. **Any lease:** an owner may drop its own leased copy. |
| a sweep's removal | the identity **and the revision** it selected; `ready`, or `dropping` (the recovery row); the proof; **a lease that has ended, read again now** |

Otherwise exit 5, and nothing was changed.

**The lease is the protection.** [108-5] [108-8]
- A copy is created with a lease, 24 hours by default. A run that lasts longer renews it.
- **A sweep removes a copy only when:** its state is `ready`, or `dropping` with its proof matching (the recovery row above); its lease has ended, read again under the lock; its change lock is taken without waiting; its identity and revision are as selected and its proof matches; and the engine lets it go. On PostgreSQL that last is a plain `DROP DATABASE`, which refuses while any session is connected [G-8b]; on MySQL a drop that gives up after five seconds on a lock [G-15b]. [Build round 1: a sweep finishes a proven `dropping` copy whose lease has ended, as the recovery row says.]
- **What that does not protect, said plainly.** A copy whose lease has ended is the sweep's to take. On PostgreSQL a connected session still saves it. **On MySQL an idle session does not, and for SQLite an open file does not.** The product claims that a sweep never removes a copy inside its lease, and no more.
- **`copy hold` waits** for a later stage (section 11).

### 2.3 PostgreSQL

**The template.**
- **It is `<database>_start`, with `datistemplate` true, `datallowconn` false, and the superuser `postgres` as its owner.** [D] It refuses every connection [G-1a]; a role that may create databases can copy it, two at once [G-1b]; only the superuser can alter, rename or drop it [G-1c].
- **It is registered by its comment,** which only its owner can set: the tag `megasamples-template/1` and a JSON object with the database, its allocated bytes, the copy strategy, the build id and the SHA-256 of its registry row. [G-8a]
- **It is frozen before it is closed:** `VACUUM (FREEZE, ANALYZE)` in the image build. [D]

**How the image makes it.** [D]
1. The private builder loads the dataset under its working name, as `admin`. This reuses the loader for databases with and without a template.
2. The read grants of 4.1 and the read profile are applied there. **No write grant to any group is.**
3. The builder freezes the selected database, then renames it to `<database>_start`, gives it to `postgres`, registers it and closes it before the image is published.
4. The working copy is made from it, and given its own grants (4.1).
5. A database with no template is loaded straight into `<database>`, as today, with the same grants.

**A copy,** as the namespace's owner, on one connection to the `megasamples` database:
- `CREATE DATABASE <copy> TEMPLATE <database>_start STRATEGY <strategy>`. The hook confines the name and the template, and closes the new database to `PUBLIC` (4.3).
- Its OID is recorded, and its comment written: `megasamples-copy/1` and the identity.
- **Last,** `GRANT CONNECT` on it to the namespace's read group. Until then only its owner can connect.
- **Its owner is the one ordinary account that can write it** (4.1). [G-23]
- **What it carries from its template** is 4.1's, each a gate of its own. [G-2a to G-2d]

**A drop** is a plain `DROP DATABASE`, never with force [G-8b]. With `--wait` a refusal is retried within the wait budget. **One deadline covers taking the change lock and the removal.** PostgreSQL's own `DROP DATABASE` waits up to five seconds for other sessions before it refuses, so a drop gives up at the first refused attempt that ends past the deadline. [Build round 1.] If the engine reports the database is in use, the CLI checks the proof again and can restore a previously ready record. The target data and sessions are preserved. The ledger's revision advances for the durable dropping and ready writes. The namespace owner needs no access to the activity view for this route.

### 2.4 MySQL

**The template.**
- **It is the schema `<database>_start`, set `READ ONLY = 1`.** [D] Every account's write to it is refused [G-10a]; it can be read by several copies at once [G-10b]; changing the option needs `ALTER` on it, which `admin` and `root` hold and a namespace's owner does not [G-10c].
- **MySQL has no "accepts no connections" for a schema.** What stands in its place: `demo` holds no privilege there; a namespace's owner holds `SELECT` only; `admin` and `root` can read it, and can change the option. [D]

**How the image makes it.** After the dumps are loaded (`SM:engines/mysql/Dockerfile:39-42`), for each templated database, as `root`:
1. Its definitions are recorded in `megasamples.template_ddl`: tables, then routines, views in dependency order, triggers and events, each without its definer; and the insertable columns and the `CHECKSUM TABLE … EXTENDED` of each table. [G-13]
2. The template is made from the loaded database by the copy below, with each original definer kept.
3. Each table's row count and checksum are compared with the loaded database's.
4. The template is set `READ ONLY = 1`.
5. **After the server's final shutdown, the build removes its identifier file, `auto.cnf`,** so that each fresh volume makes its own (3.5; F-34). An image test asserts that the file is absent. [111-2] [G-33a]

**A copy,** as the namespace's owner, on one connection, all of it inside the server:
1. `CREATE DATABASE <copy>`, with the template's character set and collation. **Then the marker event** (2.2).
2. Each table's recorded definition, with foreign-key checks off for the session.
3. `INSERT INTO <copy>.<table> (…) SELECT … FROM <database>_start.<table>`, a table at a time.
4. The routines, the views and the events. A templated database has no trigger, and no function its owner would be refused (below).
5. Each table's row count and checksum compared with the template's record.
6. The row is set `ready`.

- **A copy has no grant of its own.** A namespace's owner is the one ordinary account that can write its copies; a declared reader of the namespace can read them (4.6).
- **The definer of everything in a copy is the namespace's owner.** [D]
- **A replayed definition belongs to the copy and not to its source.** With the source's rows changed afterwards, a replayed view, procedure and function returned the copy's data, and a write through the copy's trigger landed in the copy alone. [G-13]
- **But a namespace's owner cannot replay every kind while the binary log is on.** The engine refuses it a trigger (`1419`), and a stored function that declares none of `DETERMINISTIC`, `NO SQL` and `READS SQL DATA` (`1418`). With the log off, both replay. [G-13] Version 1 does not work around the engine's rule: it offers no copy of a database that needs either (below).

**What gets no MySQL template.** [D]

| Database | In version 1 | Why |
|---|---|---|
| Above 512 MiB of allocated bytes, measured at build | no template, no copies: exit 4, `too-large` | A logical copy's time and undo grow with its rows. The number is fixed by the build's measurements before the freeze. |
| `oracle_hr` and `oracle_oe` (2.6) | no template, no copies: exit 4, `dependency-group` | A copy of one would point at the other's shared working copy (F-11). |
| **A database whose recorded definitions hold a trigger, or a stored function of a kind not yet shown to replay** | no template, no copies: exit 4, `not-replayable`, **before any reservation or change** [111-3] [112-1] [113-2] | The engine's own rule, above. The one setting that lifts it, `log_bin_trust_function_creators`, is deprecated (warning `1287`), so version 1 leaves it unset. **Withheld in both log modes:** a copy that exists only while the log is off is not offered. The namespace's owner stays the definer, and is given no wider privilege. |

- **What a copy's stored programs keep.** [Build rounds 2 and 3.]
  - **Restored:** each procedure's and event's `sql_mode`, and each event's `time_zone`, recorded at build.
  - **Recorded, not restored, as a stated limit:** `character_set_client` and `collation_connection`. A copy's programs carry the copying session's `utf8mb4` values.
  - **Withheld:** a database with a program created under `ANSI_QUOTES`, as `not-replayable`, because the schema rewrite does not rename double-quoted identifiers.
  - **Refused:** a template whose objects lack these recorded settings, as `format-unknown`, before any reservation.
- **A database is offered only for the kinds of definition shown to replay as its owner, under the shipped settings.** [113-2] Shown so far: tables, views, procedures and events [G-13]. **A stored function that declares `DETERMINISTIC`, `NO SQL` or `READS SQL DATA` has not been shown with the log on:** its only successful replay was with the trust setting. So a database with any stored function is withheld until T-11 has tried each declaration on the candidate. **A declaration that replays is then offered; one the engine refuses stays withheld, listed with its reason. Both are correct outcomes.** [115-3]
- **The build finds the withheld databases from the definitions it records** (step 1), upstream dumps included, and prints each with its reason: a trigger, or a function. From the repository's sources they are at least `adventureworks_lt`, `oracle_oe`, `oracle_hr` and `sakila` (F-35); the build's list is the authority, and the README names it. [112-2]
- **These databases are whole in every other way:** their working copies, their reset from the image, and their PostgreSQL and SQLite copies are unaffected.
- **Lifting it is a ready later addition** (section 11, S-8). [112-3]

**A MySQL working copy still resets from the image.** A reset from a template waits (section 11). Its gap against DL-077 item 1 is recorded. [108-10]

**The binary log is configurable, and the image keeps it on:** `engines: {mysql: {binary_log: false}}`. Every logical copy is written to it a second time (F-10). The image starts and passes its own tests with the log off and with it on [G-18a, G-18b], so the key is in version 1. [109-2]

### 2.5 SQLite

- **The template is the image's file,** and "read-only" is its mode. There is no server and no account.
- **The build writes a manifest** beside the files it already writes: `build/sqlite/templates.json`, with the tag `megasamples-manifest/1` and each file's name, size and SHA-256 (`SM:README.md:173`). A caller elsewhere works from a copy of that directory. No command stages it. [D]
- **A copy,** in the caller's directory:
  1. the name's lock file is locked; the sidecar is made with exclusive creation: `reserved`, then `issuing`;
  2. the template is copied to its retained name in `.megasamples/`, synced, and held to the manifest's SHA-256;
  3. it is published by a hard link to its final name, which fails if that name exists. **The retained link stays.** [G-19a, G-19b]
- **A drop** is 2.2's: record, move aside, compare, remove.
- **The service's own working files are another thing: one set, in the service's volume.** [114-2] [D: review 5's finding 9.]
  - **Today there are two.** The container's own `/data`, which the documented client edits, is an anonymous volume that a `down` leaves behind (`SM:engines/sqlite/Dockerfile:25`). The named volume that the consoles read is overwritten from it at every start (`SM:megasamples/engines/sqlite/__init__.py:61-73`), and a reset writes both (`SM:megasamples/reset.py:318`).
  - **Version 1 has one set:** the documented client and the consoles open the same files, in the named volume.
  - **The service seeds a working file only when it is absent.** A person's committed edit is there after a restart of the service, a reboot of the host, and `down` then `up`.
  - **A reset of that database reseeds it; a replacement of the volume reseeds them all** (3.5).
  - How the image keeps its pristine files apart from that volume is the build's choice; these four outcomes are what T-32 holds.
- **Nothing goes over the network.** A caller's own directory of copies belongs to no server: its documents carry no volume identity, and a whole engine's reset does not touch it.

### 2.6 Which databases get a template, the dependency group, and the storage

**The default selection is `core`:** every physical database whose base dataset is of tier `core` or `core-medium`, less MySQL's exclusions (2.4). It is configured for each engine by `engines.<engine>.templates`: a selector, a list of databases, or `none`. It is baked. [D]

**On MySQL, `oracle_hr` and `oracle_oe` are a dependency group, by name.** [109-4] Neither has a template, and neither is reset singly, whichever of them is installed. [D: review 5's finding 20: round 5 made it depend on what was installed, which DL-109 does not say.]

**Version 1 does not bound storage.** [D]
- **A template is its database again.** A live copy is its database again. A PostgreSQL reset needs its database once more while it runs.
- **The build measures and prints** each template's allocated bytes, appended datasets included (F-9), and each copy's time. A deployer sizes a volume from that.
- **`max_copies`** bounds how many copies a namespace's owner can have through the CLI. It bounds no bytes.
- **When the disk fills,** version 1 promises this and no more, on each retained path. **The error an engine gives is not relied on:** PostgreSQL answered a full disk once with its disk-full code and once with an internal error [G-9]. So after any failed step the CLI reads what is there.

  | What was running | What must hold afterwards | Gate |
  |---|---|---|
  | A copy's creation, on a server | The server stays up. Every template and every working copy is whole. **The copy's state is whatever its row's phase and the observed object make it** (2.2). When `CREATE DATABASE` itself failed, PostgreSQL left nothing in its catalog [G-9], and the row is `stale`. **A later step that fails leaves the database there:** its comment, its grant. That copy is `interrupted`, and kept. MySQL leaves the partly filled schema, `interrupted`, and kept. | G-9, G-17a |
  | A PostgreSQL reset | Nothing is swapped until the new copy is whole. **A restore that fails part-way leaves its transient, partly filled:** it is kept and reported, and the working copy is as it was (section 14). | G-9 |
  | **A MySQL reset from the image, after its drop** | The server stays up. Every other schema is whole. **This one is not, and is not claimed to be:** the operation records `failed` and stays unsettled, and reconciling completes it once there is space. **`done` is never written for it** (3.5). | G-17b |
  | An operation's own record | **The design does not lean on a full disk refusing the write:** a small row write was seen to succeed with no space free. A phase is written before its step; `done` is written only after verification. If a write does fail, the row keeps the last phase that was written, and the operation is unsettled. | G-17b |
  | A SQLite copy's publication, or its sidecar | No file under a final name that is not whole. | G-19c |
  | A SQLite reset, or its operation's file | The working file is the old one or the image's, whole: the reset stages the new file beside the final name and renames it over (`SM:megasamples/reset.py:319-327`). The operation's file is written the same way. | G-19c |

## 3. The CLI for scripts

### 3.1 The commands

| Command | As | What it does |
|---|---|---|
| `megasamples copy create ENGINE:DATABASE --prefix P --label L [--lease DURATION]` | the namespace's owner | 2.2. It returns the issued name and the identity. |
| `megasamples copy show ENGINE:NAME` | the owner | The copy's state (2.2), its lease and its proof. **It changes nothing, whatever the state.** |
| `megasamples copy list ENGINE --prefix P [--label L]` | the owner | Every object and every row in the namespace, with its state. **It changes nothing.** |
| `megasamples copy renew ENGINE:NAME --identity ID --lease DURATION` | the owner | Sets the lease's end. |
| `megasamples copy release ENGINE:NAME --identity ID` | the owner | Ends the lease now. |
| `megasamples copy drop ENGINE:NAME --identity ID [--wait SECONDS]` | the owner | Dropping a copy that is already gone succeeds. |
| `megasamples copy sweep ENGINE --prefix P [--dry-run]` | the owner | What it removed, and what it kept and why. **With `--dry-run` it changes nothing,** and says what a real sweep would select. **Narrowed in build round 1:** whether the engine lets a selected copy go is learned only at the removal, so a copy with a connected session (PostgreSQL) or a held lock (MySQL) is listed as removed by the preview and kept as `busy` by the real sweep. |
| `megasamples reset …`; `megasamples up`; `megasamples down` | where the service runs | 3.5. |

- **`copy` needs a TCP path to the engine's port, and nothing else:** no container runtime, no checkout. For SQLite it needs `--templates DIR` and `--dir DIR`. [D] **Narrowed in build round 2:** for PostgreSQL the client also needs the system's libpq, which the pure Psycopg distribution loads; without it `copy` exits 3, `client-library`. A bundled libpq (`psycopg[binary]`) would need its own licence review.
- **`reset` and `up` run where the service runs,** as today (F-1). A reset asked for from elsewhere waits (section 11). [108-6]
- **`ENGINE:DATABASE`** follows the reset's own pairs (`SM:megasamples/reset.py:6`).
- **A copy owner's credential may be used from another machine, on a build whose confinement regressions pass.** The confinement itself is shown: on PostgreSQL by a prototype of the hook's second rule [G-29a to G-29d], on MySQL by the engine's own grants [G-11b]. **The claim is made for a build only when T-7 and T-9 pass the same cases through its images.** [108-5]

### 3.2 Output

- **One JSON document on standard output, on one line,** for every `copy` command, and for `reset` with `--json`, `--status` or `--reconcile`. Everything else goes to standard error. [D]
- **Its envelope:** `schema`, `interface`, `command`, `ok`, `exit`, `volume`, `result`, `error` and `warnings`.
  - **`volume` is the identity of the server's data volume** (3.5). For a SQLite copy in a caller's own directory it is null.
  - `error` holds a stable `code`, a `message`, and the `operation` or copy `identity` a caller reads the state by.
- **A copy's result:** its `name`, `identity`, `engine`, `database`, `prefix`, `label`, `state`, `revision`, `lease_until`, its `endpoint` (the host and port the caller used, or the file's path), its `owner`, the `template`'s build id and registry digest, and the engine's `version`.
- **No credential is ever in it.**

### 3.3 Exit codes

| Code | Meaning | What it promises |
|---|---|---|
| 0 | done | as asked |
| 1 | a defect in the CLI | nothing; treat it as 8 |
| 2 | wrong usage | no engine was contacted |
| 3 | the engine cannot be reached, the sign-in is refused, the connection was lost before any write, or the PostgreSQL client library cannot load (`client-library`) | nothing changed |
| 4 | not offered here: no template, `too-large`, `dependency-group`, `not-replayable` | nothing changed |
| 5 | refused by a rule: namespace, label in use, identity or state not as expected, `not-exclusive`, the limit, an unknown format, an unsettled operation, a reset still running, a state that cannot be read, an ordinary account that can write a MySQL target, a missing or wrong `--discard`, a stale image, a volume that cannot be identified, an earlier deployment | nothing changed |
| 6 | busy, or people's sessions were there | **the target's data is as it was, no person's session was ended, and the CLI confirmed it.** A reset may leave a `rolled-back` record, and its database may briefly have refused new connections (3.5). [115-6] |
| 7 | failed | **nothing is left changed, and the CLI confirmed it** |
| 8 | unsettled | **a durable record describes what is there,** or there is none: a create whose reply was lost before its reservation was written leaves no row, and `copy list --label` finding none settles it. A sweep that stopped after a removal names what it removed. [Narrowed in build round 2.] |

| Command | 6 means | 7 means | 8 is read by, and settled by |
|---|---|---|---|
| `copy create` | the namespace lock could not be had; no row was written | — | `copy list --label`. **An interrupted create is not settled by any command:** it is kept (2.2). |
| `copy drop` | **the change lock could not be had within the wait:** nothing was read or changed. **Sessions or a lock remained at the end of the wait:** the copy's data and every session are as they were. A copy that was `ready` is `ready` again, its revision advanced by the durable `dropping` and `ready` writes (2.3); one that was already `dropping` stays `dropping` at its revision. [Narrowed in build rounds 1 and 2.] | — | `copy show`; `copy drop` again |
| `copy sweep` | — | — | `copy list`; `copy drop` for each `dropping` one it names |
| `copy renew`, `release` | another change holds the name | — | — |
| `reset`, one target | another reset holds the target's lock, or sessions were found; **its data is as it was, and nobody's session was ended.** Found at the first look: no record, and `--status` says `unknown`. Found at the second: `--status` says `rolled-back`. [115-6] | it failed before anything of the target changed: `rolled-back` | `reset --status`; `reset --reconcile`. **A reset whose target changed and did not verify is 8, never 0 and never 7.** |

- **A command that cannot confirm what 6 or 7 promises returns 8.**
- **`copy create` never returns 7.** A create that fails after its reservation leaves a row and perhaps an object, and those are kept: exit 8.
- **A reset of several targets** returns 0 only if every one is `done`; otherwise the gravest of its targets' exits, in the order 8, 7, 6, 5, 4, 3. Before it changes its first target, it checks every target's admission and option; one that would be refused refuses them all. [D: review 4's finding 20.]
- **A caller that meets a code it does not know treats it as 8.**

### 3.4 Credentials

- **`copy`: one account, one password,** from `--password-file PATH` or `--password-stdin`. A file must be the caller's own and closed to others, or it is refused before it is read. Never an argument, never the environment; nothing ambient is read (`PGPASSWORD`, `PGPASSFILE`, `~/.pgpass`, `MYSQL_PWD`, client option files). [D]
- **`reset` and `up`: the checkout's `.env`, as today,** read once, as a file. [D]
  - **Every key the reset needs is resolved once, at its start, from that file only.** An exported variable of the same name is not read. Today's reader, under which an exported value wins (F-22), is replaced for `reset`.
  - **What is promised of a password, exactly:** it is in no argument, no output and no log, and it is not taken from the CLI's own environment. **It is in the environment of the container the reset starts,** as it is in each engine's at start (F-6, F-22). Version 1 does not change that, and does not claim otherwise.
  - If the server was started with an exported value that differs from the file's, the reset's sign-in is refused: exit 3.
- **The keys:**

  | Key | Account | Unset |
  |---|---|---|
  | `DEMO_PASSWORD` | `demo` | the published value |
  | `MYSQL_DEMO_PASSWORD` | `demo` on MySQL, when a deployer gives it a key of its own (4.5) | `DEMO_PASSWORD`'s |
  | `ADMIN_PASSWORD` | `admin`, on both engines: one key, with the authority of both | **5.1** |
  | `POSTGRES_PASSWORD`, `MYSQL_ROOT_PASSWORD` | the superusers | **5.1** |
  | `<NAME>_PASSWORD` | a namespace's owner; a declared reader or writer | the account is locked |

- **The whole inventory of keys is checked when the configuration is read.** [D: review 4's finding 8: a declared reader named `mysql_root` would have had `MYSQL_ROOT_PASSWORD` as its key.] The key of every namespace's owner and every declared account is derived, and the configuration is refused if two of them are the same, or if any is one of the five keys above.

### 3.5 Resets, starts, and anything that replaces a volume

**One reset of one target at a time, and one unsettled operation for each target.** [108-5] **This section says what each path does when nothing interrupts it. What happens after an interruption is section 14's table, written once and tested whole.** [114-3]

**The paths version 1 has:**

| Target | Path | Its option |
|---|---|---|
| A PostgreSQL database with a template | from the template, into a transient, with a swap | `--discard sessions` when people's sessions are there; or `--unattended`, which refuses |
| A PostgreSQL database with no template | **from the image, into a transient, with the same swap** [108-5] | the same |
| A MySQL database | from the image, in place, as today | **always `--discard sessions`** |
| A SQLite working database | the image's file, staged beside it and renamed over | **always `--discard sessions`** |
| A whole engine | its volume replaced from the image. **No phases and no reconciliation.** [114-2B] | **always a fresh `--discard engine`** |
| `megasamples up`, with an engine's image stale | the same replacement (F-32) | **always `--discard engine`** |

**The engine's deployment lock.** [D: review 5's finding 10.] One lock file for each engine of a deployment, **the same file for every operator and every checkout that drives those containers.**
- Today's is keyed by the operating-system user (`SM:megasamples/reset.py:110`), so two operators of one service hold different locks. Version 1's is keyed by the deployment.
- Every reset of a database on that engine takes it, and so does anything that replaces the engine's volume. So the two never run together.
- The records that are kept "where the service runs" are beside it, and are as shared as it is.

**An operation.** Each reset of one database is one operation, with an identity.
- **A script resets one target for each call, and gives the identity:** `--json` and `--operation ID` take exactly one target. An identity that already has a record is refused: exit 5, `operation-exists`. So a caller that lost a reply asks again under the same identity and is told what happened. [D: review 4's finding 18.]
- **A reset of several targets is for a person:** text output, each operation's identity printed as it starts, and `reset --status ENGINE` afterwards.
- **Its record is written before each step, and its terminal outcome is kept for the life of the volume.** There are two:
  - **`done`:** the target is the image's, verified, with its readers' grants in place;
  - **`rolled-back`:** the target is as it was before the reset.
- **`failed` is not terminal.** [113-3] It is recorded when a target that is changed in place did not verify.
  - The command ends with exit 8.
  - A fresh reset of that target is refused: exit 5, `unsettled`.
  - Only `reset --reconcile` of that same operation completes it, with counts, checksums and declared grants verified.
  - A whole engine's reset stays the way out (below).
  - A PostgreSQL database is never `failed`: nothing of it changes until the swap.
- **Where the record is:** for a database on a server, a row in `megasamples.operations`; for a SQLite working database, a file beside the deployment lock. **A whole engine's reset is not an operation of this kind** (below).
- **On MySQL, an operation that suspended declared writers has one more recorded step after `done`: `restored`.** [116-2] Until that is written the operation is not settled, though its data is.
- **Admission.** A reset is admitted only if the target has **no operation that is not settled:** one that is not terminal, or one `done` whose writers are not yet `restored`. Otherwise: exit 5, `unsettled`, naming it. Only `reset --reconcile` settles one, and it settles that operation only.
- **`megasamples reset --status [--operation ID]`** answers: `running`; `unsettled`, at a phase, with `failed` and its reason where that was recorded; a terminal outcome; or **`unknown`: this volume has no record of it.** It gives the volume's identity with every answer, and it changes nothing.

**Who holds what, from admission to the end.** [D: review 4's findings 2 and 3; review 5's findings 3 and 4.]

| | The coordinator | The worker |
|---|---|---|
| **What it is** | One session of the superuser inside the container, opened first and kept to the end. | A second process, for the image path only: `pg_restore` on PostgreSQL; the stream of the image's dump on MySQL. |
| **What it holds** | The engine's deployment lock, and **the target's reset lock, from before admission until after the outcome is written.** | PostgreSQL: nothing; it writes only into this operation's transient. MySQL: **a second lock, the target's worker lock,** taken by the first statement of its stream. |
| **What fences it** | The locks. | PostgreSQL: its transient exists under this operation's name alone. MySQL: **the guard,** below. |

- **The MySQL worker's guard is one statement, the stream's second, and it raises an error unless all of this is true on the session that will write:**
  - this session owns the worker lock. A lock attempt that returned "busy" is a successful statement, so the guard asks who owns the lock;
  - the server's volume identity is the one the coordinator read;
  - the operation's row is there, with the epoch the coordinator gave this worker and the phase `loading`.
- **The worker's client stops at the first error and never reconnects.** A stream whose session ended does not go on in another.
- **An operation is live while either lock is held.** Admission and reconciliation go on only after taking **both** without waiting; and reconciliation then **raises the row's epoch before it does anything else.**
  - A stream that arrives while a reconciliation holds the worker lock does not own it, and stops at the guard.
  - A stream that arrives later owns the lock and finds another epoch, and stops at the guard.
  - A worker already running keeps its lock, and nothing else touches the target until it ends. [G-26m]
- **On PostgreSQL** a worker that outlives its coordinator goes on filling its own transient and nothing else. A reconciliation then keeps that transient and reports it; a second reset uses another. [G-26p]

**A PostgreSQL reset, by either path.**

| Step | What happens | The phase |
|---|---|---|
| a | The locks. Admission. **The first look** at who is connected (the session decision, below). If it refuses, nothing has been created and nothing closed. | none yet |
| b | The operation's row, **with the working copy's own OID.** | `building`, written first |
| c | `CREATE DATABASE <database>__new_<id> OWNER admin`: from the template; or empty, and the worker restores the image's dump into it. **Its OID is recorded as soon as it exists.** Then its grants are given, in it (4.1). It holds no `CONNECT` for anyone but its owner. | `built`, written after |
| d | **The door is closed:** `ALTER DATABASE <database> ALLOW_CONNECTIONS false`, in one transaction with the phase. [G-3a] | `closed` |
| e | **The second look.** If a person connected during the build and the reset may not end their session: the door is opened again in one transaction that sets the phase back to `built`; then the transient is dropped by its recorded OID; then `rolled-back` is written; exit 6. Otherwise the sessions that may be ended are ended. [G-3c] | `closed` |
| f | **In one transaction:** the working copy is renamed to `<database>__old_<id>`; the new one is renamed to `<database>`; its `CONNECT` is granted to the working groups; the phase is set. [G-3b] | `swapped` |
| g | **The old transient is dropped only if its OID is the one recorded at step b.** | `done`, written after, and kept |

- **Steps d and f are each one transaction.** Each was shown to commit whole and to roll back whole, every member read after both outcomes. [G-3a, G-3b]
- **A restore that fails part-way leaves its transient partly filled.** It is kept and reported, and the working copy is as it was: `rolled-back`.

**A MySQL reset, from the image, in place.** Today's procedure (F-4), under the locks and the record, **with the declared writers held out from before its first change until after `done`.** [116-2]

| Step | What happens | The phase |
|---|---|---|
| a | The locks. Admission, **the writers' check among it** (below). `--discard sessions` is required. Then the operation's row, with its epoch **and the names of the declared writers it will suspend.** | `started` |
| b | **The declared writers are suspended:** each one's write privileges on this schema are revoked, **and every session of theirs is ended.** A revoke alone leaves an open session writing. [G-27a] Then it confirms that no ordinary account can write the schema. | `suspended`, written first |
| c | The other sessions that use the schema are ended (below). The worker: its lock, its guard, then the image's dump, which drops the schema and loads it. | `loading`, written first |
| d | Each table's row count **and checksum** against the image's own, read from the pristine container that is still running. | `loaded` |
| e | **The declared readers' grants are confirmed in place,** and made again where one is missing. | **`done`,** written after, for the verified data, and kept |
| f | **Only now are the declared writers' grants restored.** A grant that cannot be restored is reported, by name, and the step is reconcilable. | `restored`, written after |

- **No restored grant comes before `done`.** [116-2] From step b until `restored`, a declared writer that reconnects is refused a write to that schema. That holds across a restart of the server [G-27b], and the start leaves its grant out meanwhile (4.6).
- **A failure of step f does not undo `done`.** The data is verified and recorded. The command ends with exit 8, `reset --status` says `done` and names each writer still suspended, and `reset --reconcile` restores the grants; it neither loads nor verifies again.
- **A reset that ends `rolled-back` gives the writers' grants back before it writes that.**
- **`done` is written only after a verified load.** [111-1] Every table's row count and checksum equal the image's, and the readers' grants are in place. No other path writes it.
- **A load that fails is recorded `failed`, then and there,** with its reason. On a full disk that small write was seen to succeed while the load could not [G-17b]. If it does not, the row stays at `loading`. Either way the operation is unsettled: exit 8.
- **A MySQL reset is refused while an ordinary account can write its target.** [115-1]
  - **At admission the reset reads every account's effective write privilege on the target:** by a grant on its exact name, by a pattern, globally, or through a role.
  - **A holder that is not an administrator, or a privilege it cannot determine, is a refusal:** exit 5, `writer-present`, naming each holder. It comes **before anything is recorded, any session is ended, or any data or grant is changed.** The same check is made before a reconciliation loads.
  - **An administrator is the service's own `root` or `admin`.** Any other account is ordinary, whatever it holds.
  - **The way on:** the administrator withdraws the grant; or the whole engine is reset.
  - **A declared writer is not refused: it is suspended** (step b). [116-3] For any write privilege it holds beyond its declared grant, it counts as ordinary.
  - **Stated limit:** a grant an administrator makes after admission.
- **`oracle_hr` and `oracle_oe` are not reset singly** (2.6): exit 4, `dependency-group`. A reset of one would leave the other pointing at rows that are gone, and today's path does exactly that. They are reset with the whole engine. [109-4]

**A SQLite reset of one working database** is today's (F-4), under the engine's deployment lock and an operation's file.
- It stops the consoles that read the files, and those consoles also carry people's sessions on the other engines. **So it always needs `--discard sessions`, and names the consoles it will stop.** [109-4]
- **Its steps, each phase written before the step it announces:** `started`, with the volume's identity and the digests of the working file and of the image's file; the consoles are stopped, and the image's file is staged beside the working file; `staged`; the staged file is renamed over the working file [G-19c] and verified; the consoles are started; `done`.
- **The operation's file carries the volume's identity.** [115-2] A reconciliation first establishes that the record is of this volume, and that the working file is the one expected at its step: the recorded one before the rename, the image's after it.
- **A working file that is neither, a record of another volume, or an identity that cannot be read is preserved and reported, with its record.** Nothing is staged over it. A file that someone changed is recorded `failed`; it stays as they left it.
- **While a SQLite reset is unsettled, `megasamples up` does not start the consoles:** exit 5, `unsettled`, naming the operation and the `reset --reconcile` command. [115-2] So an interrupted SQLite reset keeps the consoles down, for every engine, until one command settles it.
- It does not change the volume's identity.

**The session decision.** [108-2] **A reset of a database preserves sessions unless it is told otherwise.**

| | What happens when people's sessions are on the target |
|---|---|
| **By default** | The reset stops: exit 6, saying how many sessions and whose. On a terminal it first warns, and asks. |
| **`--discard sessions`** | The warned choice, given as an option: the sessions are ended and the reset goes on. |
| **`--unattended`** | For automation. One PostgreSQL database. Any session that is not disposable is a refusal. It never takes `--discard`, and it never ends a person's session. |

- **Only a session positively known to be the product's own is ended without the option.** [D: review 4's finding 7.]
  - **The product's own sessions say so:** on PostgreSQL, the health probe and the CLI set a reserved application name on the connections they open. A client that sets that name itself has declared its own session disposable.
  - **Every other session is a person's, a console's included,** and is preserved.
  - **What was observed.** The reserved name told the product's session from the others, and nothing else did. [G-32a] **With nobody there, no bundled console held a session on either server** [G-32b], so the default does not refuse by itself.
  - **A console connection that a person opened stays open, idle, after they stop** (G-32b's control). So the default refuses until they close it, or until the reset is told `--discard sessions`. The refusal names the sessions.
- **What a refusal guarantees on PostgreSQL, exactly.** [D: review 5's finding 15.]
  - **The early refusal.** A person's session is there at the start: no transient is made, no row is written, the door is never closed, and no session is ended. A connection attempted at any moment succeeds. `reset --status` for that operation's identity says `unknown`.
  - **The late refusal.** A person connects during the build: no session is ended and no data changes. **The working database refuses new connections from step d until the reopening,** a moment; a connection attempted in it is refused once. `reset --status` says `rolled-back`.
  - **Both are exit 6, and that is what exit 6 promises** (3.3): the data as it was, and no person's session ended. [115-6] It is the whole of what `--unattended` promises.
- **What `--discard sessions` consents to, by engine.**

  | Engine | The sessions it ends |
  |---|---|
  | PostgreSQL | Every session connected to that database. A PostgreSQL session is on one database, so nothing else is touched. |
  | MySQL | **Every session of each declared writer, whatever schema it is on** [116-2]: a session already open is not stopped by the revoke. A transaction it had open is rolled back. And every session, of any other account but the reset's own, **that has the target as its default schema, or holds or waits for a lock on one of its tables.** Such a connection is ended whole, whatever else it was used for. A session of another account that touches nothing of the target is not ended. |
  | SQLite | Every session the stopped consoles carry, **on every engine.** The reset names the consoles first. A SQLite shell someone opened by hand is not seen. |

- **MySQL has no door,** and a session there can name any schema. So a MySQL reset of one database always needs `--discard sessions`, and `--unattended` is refused before any change: exit 4.
- **This changes today's default,** which disconnects (F-4). It enters version 1 at the freeze, with the impact note of 5.4. [108-2]

**Starting and stopping.** [114-2F] [D: review 5's findings 8 and 9.]
- **Each engine's data is on a named volume of the deployment:** PostgreSQL's and MySQL's data directories, and SQLite's working files. Today the servers' are anonymous volumes, and a `down` removes the container that held one (`SM:megasamples/job.py:160-163`, `:199-204`).
- **Version 1's volumes have names no earlier version used.** So an earlier version's volume is never taken for one of its own.
- **`megasamples down` removes containers and keeps volumes.** So does stopping the Compose project directly. Neither is a replacement, and neither needs an option.
- **An image starts only on data it seeded.** The build writes one build identity into the image and into its data. At its start the image compares them: an empty volume it seeds; its own data it starts on; **on anything else it refuses to start, and says what it found.** That holds whoever started it: `megasamples up`, Compose, or a hand.
- **What a start does for each engine is decided by its volume, never by whether a container exists:**

  | # | The engine's volume | `megasamples up` | `megasamples up --discard engine` | The current Compose file, started directly |
  |---|---|---|---|---|
  | U-1 | absent, **with no trace of an earlier deployment:** a first start | creates it, and the image seeds it | the same: there is nothing to discard | **refuses to start:** the current Compose file creates no engine's volume; only `megasamples up` does [115-U] |
  | U-2 | present, seeded by the current image | **attaches it and starts. Nothing is replaced,** whether or not a container existed. | the same, and says that nothing was stale | the same |
  | U-3 | present, seeded by another build: **stale** | **refuses that engine:** exit 5, `stale-image`. What is running is left running; nothing is recreated. | replaces it, by the rules below | **the image refuses to start on it.** Nothing is replaced. |
  | U-4 | present, and what seeded it cannot be read | **refuses that engine:** exit 5, `unidentified-volume`, naming the volume | **refuses the same.** It removes nothing it cannot identify; the README has the route by hand. | the image refuses to start on it |
  | U-5 | none of this version's, **and an earlier deployment is detectable:** an engine's container from an earlier version; or, after that version's `down`, a volume it named, or a Compose file or pages it generated in this checkout | **refuses that engine before any fresh data is served:** exit 5, `earlier-deployment`, naming what it found and the README's upgrade route [115-U] | removes an earlier container if there is one, **leaves every earlier volume in place and names those it can,** and starts on a new volume | **refuses,** as U-1: it creates no volume |

- **An upgrade never puts fresh data into service unasked.** [115-U] Wherever an earlier deployment is detectable, both starts reattach data that this version identifies as its own, or refuse before serving fresh data. Version 1 does not start on an earlier version's data (above), so there it refuses.
- **Stated limit: an install that cannot be told from a first one.** [115-U] An earlier version's `down` removes its containers and leaves its servers' data in volumes with no name; from a checkout that holds no trace of that version, nothing says they were a deployment. **The README's upgrade route covers it** (5.3): before the earlier version's `down`, identify each engine's volume and keep it; after the upgrade, verify an edit; and how to go back. T-29 rehearses those steps.
- **How the build identity is kept, how `up` reads a stopped volume's, and how the Compose file is kept from creating a volume, are the build's choice.** The table's outcomes are what T-22 holds.

**Replacing a whole engine's volume.** [108-9] [109-3] [114-2A] [114-2B]
- **It is refused before any change unless it is given `--discard engine`.** `--discard sessions` is refused for it: it is not the same decision. Every copy, every session and every account that is not the image's goes with the volume. There is no drain in version 1.
- **It is one act, with no phases and nothing to reconcile.** Under the engine's deployment lock it writes a record with the old volume's identity, replaces the volume, and completes the record with the new one's. It notes the new volume in the record as soon as it has created it.
- **Each replacement takes a fresh `--discard engine`.** No command resumes one that was interrupted.
  - `reset --reconcile` does not apply to it.
  - An `--operation` identity that already has a record is refused, so a retry cannot spend an earlier consent.
  - After an interruption, `reset --status` says what the record says and what is there now. `megasamples up` then acts by the table above. Replacing again is a new decision, with its own option.
- **It is refused while any reset on that engine is running, unsettled, or cannot be read.** [115-W] The volume and every record are kept and reported, and the refusal names the operation and the `reset --reconcile` command.
  - **Running** is the deployment lock held; either lock of a reset held in the server; **or a session on an operation's transient database,** which is how a PostgreSQL restore that outlived its coordinator shows. Exit 5, `reset-active`.
  - **Unsettled** is any operation there that is not terminal. Exit 5, `unsettled`.
  - **Cannot be read** is a server that refuses the sign-in, does not answer, **or is stopped.** Exit 5, `state-unreadable`. A server that will not start is recovered by the README's general upgrade route (5.3), a deliberate act outside the CLI, which T-29 rehearses.
- **There is one escape, and only this.** [115-W] [113-3] A whole engine's `reset`, named, with a fresh `--discard engine`, under the deployment lock, is admitted **when the volume is identified, every unsettled operation there is durably recorded `failed`, and all their locks are free.** It names each operation it discards. `megasamples up --discard engine` has no escape.
- **Where it cannot tell which volume it would remove, it removes none** (U-4), **even with fresh consent.** A volume that the replacement's own record shows it created, and that was never seeded, is not uncertain: a fresh `--discard engine` may replace it. [115-7]
- **Other callers are stopped first.** [114-2A] **Version 1 does not claim that a command or a worker started before a replacement cannot act after it.** The README says to stop the scripts that use an engine before replacing it. The checks that would catch one stay in place: a `copy` command's one connection, and the worker's guard.
- **`megasamples up` is the same act when an engine's image is stale** (F-32; U-3), under every rule above, and without the escape.

**The volume's identity** is information, and the `copy` commands' check. [G-33a] [114-2A]
- **On a server** it is in the server: MySQL's own server identifier, which the build removes from the baked data directory so that each fresh volume makes its own [111-2]; on PostgreSQL a value written at the first start.
- **For the service's SQLite working files** it is a file in their volume, written when the volume is first seeded. A replacement of the volume renews it; a reset of one database does not.
- **`volume` is an opaque string.** A caller compares it and reads nothing into it. [111-2]
- **A MySQL volume seeded from an image built before this is unqualified.** Every one of them reports the same identifier (F-34). [111-2]
- **A `copy` command reads it once, on the one connection it uses, and never reconnects.** A replaced server ends that connection, and with it the command: exit 8. Every document carries the identity, so a caller can tell that a name it kept belongs to a volume that is gone: there `copy show` says `gone`, and `copy drop` succeeds on nothing.
- **A caller's own directory of SQLite copies has none** (2.5): its documents say null.

### 3.5a `reset --status ENGINE`, as slices 1 and 2 build it

[Build rounds 2 and 3; DL-119.] Only `postgres` is accepted, and the only thing reported is DL-119's detective control. Operation status is slice 3's.

- **Output:** one JSON document with the envelope of 3.2. `command` is `reset --status`, `volume` is null, `result` is `{"engine": "postgres", "orphan_scan": "complete" | "incomplete"}`, and `warnings` lists:
  - one `orphan-directory` per data directory with no database, giving `tablespace`, `oid`, `name` (null), the inspected `path` and `kib`;
  - a last `orphan-scan-incomplete` when a listing, a measure, the catalog or the tablespace read failed. Then no directory is reported.
- **Exit:** 0, whether the scan is complete or incomplete. The scan changes nothing, and `orphan_scan` says how far it got.
- **`megasamples up`** prints the same warnings to standard error after the stack starts.

### 3.6 Limits

| Limit | Value | Past it |
|---|---|---|
| A whole name | 63 bytes | the build refuses the dataset or the prefix |
| A prefix; a label | 16 bytes; 24 bytes | exit 2 |
| A prefix, label or name that is not of its form | never valid | exit 2, before any connection |
| A namespace's live copies | `max_copies`, 32 by default | exit 5, `limit` |
| A lease | at least one minute; at most seven days; 24 hours by default | exit 2 |
| Connection timeout; `copy drop --wait` | 10 seconds; 0 | exit 3; exit 6 |

No statement timeout is set: a copy of a large database takes as long as it takes. [D]

## 4. The account model

### 4.1 PostgreSQL's roles

Decided here [D]; what exists today is F-5.

| Role | A login | Attributes | What it is for |
|---|---|---|---|
| `postgres` | yes | superuser | The image build, the start wrapper, the reset. Owns the templates and the policy. |
| `admin` | yes | `CREATEDB`, `CREATEROLE`, **as today** | Owns each working copy and everything in each sample database. |
| `demo` | yes | — | Reads the working copies. |
| **`megasamples_read`** | no | — | `SELECT` on every table of every sample database and every copy. |
| **`megasamples_write_routines`** | no | — | `EXECUTE` on the built-ins a row change needs (P-6). No right on any table. |
| **`megasamples_working_read`**, **`megasamples_working_write`** | no | — | `CONNECT` on every working copy. The write group is also granted row changes **inside each working copy.** |
| **`megasamples_copy_<prefix>_read`** | no | — | `CONNECT` on every copy of that namespace. |
| **`megasamples_copy_<prefix>_owner`** | no | — | Marks a namespace's owner, for the hook (4.3). |
| **a namespace's owner,** such as `copier` | yes | `CREATEDB` | Makes, uses and drops its namespace's copies. |
| **a declared reader; a declared writer** | yes | — | 4.6. |

**Reading is one group. Writing is granted inside each database.**
- **The template carries no write grant to any group.** It grants row changes, and `USAGE` on sequences, to `pg_database_owner` alone. In any database that is its owner. [G-23]
- **So in a copy, its owner can change rows, and no other ordinary account can.** Version 1 has no other writer of a copy.
- **In a working copy, `admin` grants row changes to `megasamples_working_write`,** at build and in each reset (3.5, step c).

**Each membership.**

| Member | Of | `INHERIT` | `SET` | `ADMIN` |
|---|---|---|---|---|
| `megasamples_working_read`, each `…_copy_<prefix>_read` | `megasamples_read` | true | false | false |
| `megasamples_working_write` | `megasamples_read`, `megasamples_write_routines` | true | false | false |
| `demo` | `megasamples_working_read` | true | false | false |
| a namespace's owner | `megasamples_read`, `megasamples_write_routines`, its own `…_owner` | true | false | false |
| a declared reader | each scope's read group that its configuration names | true | false | false |
| a declared writer | `megasamples_working_write` | true | false | false |

**`admin` is a member of none of them,** and is given no admin option on any: the service makes every membership itself, at start (4.6).

**What a copy carries from its template, each a gate of its own:** every object's owner and its grants to the groups [G-2a]; the default privileges [G-2b]; the policy's extension and its event trigger [G-2c]. **What it does not carry:** `CONNECT`, its owner, its comment [G-2d].

**Which database an account reaches is decided by `CONNECT` on it:**

| Database | `CONNECT` is granted to |
|---|---|
| a working copy | its owner `admin`; `megasamples_working_read`; `megasamples_working_write` |
| a template | nobody |
| a test copy | its owner; its namespace's read group |
| `postgres`, `megasamples` | `PUBLIC`, as today |
| any database made later | its owner, until its owner grants more |

A namespace's owner also holds, in the `megasamples` database only: its own ledger, and `EXECUTE` on the advisory-lock functions.

### 4.2 The strict read profile

**What pull request #14 does** is F-12. **What changes** [D]:

| # | Change | Reason |
|---|---|---|
| P-1 | **The allow-list is granted to `PUBLIC`,** not to `demo`. | H-1. Every role that is not an administrator then has the same floor, in every database and every copy, whoever made it. |
| P-2 | **`demo` holds nothing itself** but its membership. | 4.1. |
| P-3 | **Three built-ins join the list by name, each with its reason:** `pg_export_snapshot()`, `pg_current_snapshot()` and `pg_database_size(oid)`. | A client that reads consistently across sessions, or shows a database's size, needs them (F-17, F-18). [G-5b] |
| P-4 | **The rule for the list is stated.** A routine is admitted when it changes no stored object, no setting, no sequence and no other session's data, and assigns no transaction id. An exception is named in the list with its reason. | So that P-3 is a rule and not a hole. |
| P-5 | **An exported snapshot is the one exception that reaches past its own statement.** It leaves an identifier that another session may import for as long as the exporting transaction lives. | The rule must say so. [G-5b] |
| P-6 | **A write list beside it,** granted to `megasamples_write_routines`: the built-ins that row changes need through the datasets' own defaults and triggers. It is found by running each dataset's trigger scenarios as a writer. | A writer's statement runs a trigger's body with the writer's rights. [G-5c] |
| P-7 | **The product publishes its inventory:** every executable signature, with its reason, generated from the candidate. **It is the product's list, not a consumer's.** A consumer that keeps a list of its own reconciles the two, and records that it did (7.2). | DL-085 asks for the reconciliation, not for one list to replace the other. |

**What stays:** no `TEMPORARY` for `PUBLIC`; no large-object creation; no user routine for a reader; the two rewritten `employees` views; the closed defaults for `admin` and `postgres`; MySQL not claimed strict (F-14).

### 4.3 The hook and the event trigger

Input to **one independent review, of two things: the final compiled hook, and the `SECURITY DEFINER` event trigger** (F-26). Each finding was first read in `PR14:` at the cited lines. **Four have since been reproduced by gates,** and are marked; the others are still from reading.

| # | Finding | Where | Disposition |
|---|---|---|---|
| H-1 | **Every role but `demo` and `admin` is left unable to call a built-in routine,** an operator's function among them; and `admin` could not repair it (F-13). **Reproduced:** a fresh role's `SELECT 1 = 1` was refused. [G-5a] | `PR14:engines/postgres/init/10-read-profile.sql:14-15`, `:23-35` | P-1. |
| H-2 | **The hook's `REVOKE` does nothing, and succeeds,** when the creator is not the new owner and does not inherit the owner's rights. **Reproduced:** it ended with a warning and no error, and `PUBLIC`'s privileges remained. [G-4a] | `PR14:engines/postgres/read-policy/read_policy.c:31-38` | Rule 1, and rule 3's confirmation. |
| H-3 | **An error in the hook after the copy leaves the copied files with no database.** **Reproduced** on a prototype that raises there: one directory with no catalog row. With no error, and with no hook, nothing was left. [G-4b] | `PR14:engines/postgres/read-policy/read_policy.c:24-38` | **Resolved before the merge,** as set out under the four rules below. |
| H-4 | **The role name `admin` is compiled in.** | `PR14:engines/postgres/read-policy/read_policy.c:32-33` | The hook names no account. |
| H-5 | **The hook closes `TEMPORARY` only.** | the same | `CONNECT` too. |
| H-6, H-7 | **A role can change its own password, its own settings, and its own default privileges.** **Reproduced:** natively each is accepted. [G-6a, and G-6b's control] | — | Rule 4, which refuses all three while the role still reads. [G-6b] |
| H-8 | **`NOTIFY` is a statement, not a routine** [I]; the page says notifications "receive no `demo` grant". | `PR14:docs/strict-read-account.md:3` | Correct the page. `NOTIFY` stays allowed. |
| H-9, H-10 | **The event trigger names `admin`,** runs as its definer, and is enabled in the ordinary way [I]. | `PR14:engines/postgres/read-policy/read_policy--1.sql:3-20` | It checks that the role exists; `ENABLE ALWAYS`. The review covers its definer's rights and its search path. |
| H-12 | **A policy image started on data from before the policy** would run with the hook and without the grants. | `PR14:engines/postgres/Dockerfile:83` | The build writes the policy's version into the data directory; the start wrapper refuses one whose marker is missing or older. |
| H-15 | **A role that may create databases can create one of any name, from any template.** | PostgreSQL's own rule | Rule 2. |

**The four rules.** [D]

| # | When | What |
|---|---|---|
| 1 | Before `CREATE DATABASE` | Refuse, when the creator would not hold the new owner's rights. |
| 2 | See below | The confinement of a namespace's owner. [108-5] |
| 3 | After the catalog insert and before the file copy in `CREATE DATABASE` | Close `CONNECT` and `TEMPORARY` to `PUBLIC` through the server's catalog interface, then confirm it. If confirmation fails, mark the database as accepting no connections. |
| 4 | Before `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES` | Refuse, when the caller is neither a superuser nor a holder of `CREATEROLE`. [G-6b] |

**H-3's resolution, and what rule 3 does when it cannot confirm.** [D: required before the merge; review 5's finding 1.] The gate showed the hazard is real: an error after the copy orphans the copied files [G-4b].
- **All policy work is complete before the file copy starts.** PostgreSQL calls the object-access hook after inserting the new database's catalog row and before copying any of its files. Rule 1 checks the resolved owner there. Rule 2 checks the source and destination before PostgreSQL handles the statement. [PostgreSQL source, read 2026-11-21 02:35–02:41 UTC](https://github.com/postgres/postgres/blob/REL_18_7/src/backend/commands/dbcommands.c#L1394-L1469)
- Rule 3 changes and reads back the ACL in that same pre-copy hook. If the ACL does not confirm closure, the hook sets `datallowconn` to false and emits a warning. An error writing the catalog aborts creation before any clone files exist.
- The utility hook returns directly after PostgreSQL handles the statement. The narrower placement removes the policy's extra error window after file creation and retains PostgreSQL's own crash and commit limits.
- **The CLI does not trust the hook for its own copies:** before it records `created` it reads the new database's privileges, and a copy that is not closed as rule 3 leaves it is kept, `interrupted`, and reported.
- **What stays possible goes to the independent hook review** [113-4], which reports what can raise between the copy and the commit, and whether a clean-up in the hook would close it.
  - **Accepted in advance, as a stated limit in the README:** an error PostgreSQL itself raises for want of a resource, or a crash.
  - **Returns to the deciders:** anything an ordinary caller can cause by its input or its privileges.
- **T-7 holds it on the built hook:** with a fault planted in the close, and with one planted in the confirmation, no directory is left without a catalog row and no second session connects.

**A stated limit: range-type constructors.** [Build round 2, Fable P3-8.] The event trigger closes routines whose command's class is `pg_proc`. A copy owner's `CREATE TYPE … AS RANGE` makes constructor functions that no such command reports, so they keep `PUBLIC EXECUTE`. They are immutable built-in code and no harm was found. **Reopens with:** any rule that every routine in a copy is closed.

**The hook resolves every name itself.** [D: review 5's finding 2.] The prototype that passed G-29 read `pg_roles`, `pg_database` and several functions by unqualified names, through the caller's search path (`tests/gates/prototype/dl077_gate_hook.c:40-48` on the gates' branch).
- **A namespace's owner controls the search path of its own session, and owns a schema in each of its copies.** From there it could put a relation of its own in front of a catalog. For this boundary the credential's holder acting on purpose is the realistic route (section 13).
- **So the built hook reads the catalogs through the server's own catalog interfaces, or by fully qualified names and operators under a search path it fixes itself.** Nothing the caller can create or set is consulted.
- **T-7 runs all four confinement cases twice:** from the `megasamples` database, and from a database the owner owns, with a relation and a function of the catalog's names planted there and the search path pointing at them. **No PostgreSQL copy is issued, here or from elsewhere, before that passes.**

**Rule 2, exactly.**
- **A namespace is known to the hook by its marker role:** `megasamples_copy_<prefix>_owner`. An account is that namespace's owner if it is a member.
- **A registered template** is a database marked a template, accepting no connections, owned by a superuser, **whose comment carries the service's template tag.** Only its owner can set that comment.
- **`CREATE DATABASE` by a namespace's owner is refused unless** its source is a registered template `<database>_start` [G-29b], **and** its name is exactly `<prefix>_<database>_` followed by twelve hexadecimal digits, with that `<prefix>` one of the namespaces it owns and that `<database>` its source's [G-29a].
- **`ALTER DATABASE … RENAME` by a namespace's owner is refused.** Version 1 never renames a copy. [G-29c]
- **The rule binds a namespace's owner, and nobody else.** [D: review 4's finding 9: round 4 also kept every other creator out of a namespace, which is a rule of its own that DL-108 did not list.] A role that may create databases and owns no namespace creates as PostgreSQL lets it [G-29d]. If it puts a database under a namespace's prefix, that database is `unmanaged`: listed, reported, and removed by no command (2.2).
- **It names no account and holds no state.** It reads the catalog.

**What rule 2 is for.** DL-108 asks that the hook confine a namespace's owner, wherever it signs in from. **All four parts were shown on a prototype of the rule** [G-29a to G-29d]: the destination, the source, the rename, and that nobody else is bound. **The built hook repeats them in T-7 before any PostgreSQL copy is claimed,** here or from elsewhere. [108-5] Rule 2 does not bound bytes: an owner can still fill the disk with copies of its own.

### 4.4 MySQL's accounts

Decided here [D]. **Every schema pattern has each underscore escaped.** [G-11a]

| Account | Privileges | Change |
|---|---|---|
| `root@localhost`, `root@'%'` | everything | none |
| `admin@'%'` | everything, with the grant option | none |
| `demo@'%'` | `SELECT, SHOW VIEW` on each working sample schema, by its exact name; `SELECT` on `megasamples`' registry and service tables; and on each foreign namespace marked `demo_reads`, by its pattern | **narrowed** from `*.*` [G-11c] |
| **a namespace's owner** | on its own pattern, such as `copy\_%`: what making, filling, using and dropping a copy needs, **without the grant option.** On each template, by exact name: `SELECT`. On `megasamples`: `SELECT`, and row changes on its own ledger. | **new**; locked until its key is set [G-11b] |
| **a declared reader; a declared writer** | 4.6 | **new** [116-1] |

- **`demo` no longer reaches the `mysql` schema,** nor a template. That is the first of line 10's two items (LR: line 10).
- **`demo` reads a consumer's own schemas only where the configuration marks that foreign namespace `demo_reads`.** By default it reads none.
- **MySQL's `admin` is not narrowed.** [D: narrowing it needs partial revokes, under which a pattern's wildcards may stop working.]
- **An account that manages accounts can change the service's own.** A deployer or a consumer may add one; the product ships none. It is a consideration for whoever adds one (5.2), not a gate of the product.
- **MySQL stays not claimed strict:** named locks, and the two definer views of `employees`, are as F-14 found them.

### 4.5 An account changing its own password

The second of line 10's two items. A read account's credential is shared: by the consoles, the probe, and whoever is given it. A holder who changes it locks the others out, and can set it to a value everyone knows.

| Engine | In version 1 |
|---|---|
| **PostgreSQL** | **Refused,** by the hook's fourth rule, for every role without `CREATEROLE`. Natively such a role changed its own password [G-6a]; under a prototype of the rule it could not, and still read [G-6b]. The built hook repeats it in T-7 and T-25. |
| **MySQL** | **Not refused: the engine has no refusal that version 1 can use.** [G-16] |

**What G-16 recorded,** as `demo` on the pinned server:

| Mechanism tried | The four statements that change one's own password | `demo`'s sign-in, by the probe, a client and each console |
|---|---|---|
| none: `demo`'s grants as they are | all four changed it | accepted |
| `PASSWORD REQUIRE CURRENT` | three refused; **`SET PASSWORD … REPLACE` still changed it** | accepted |
| the account locked, or its password expired | all four refused | **refused** |
| global `read_only`, or `super_read_only` | all four refused | accepted |

- **`PASSWORD REQUIRE CURRENT` is no refusal:** whoever holds a shared credential knows its current value.
- **A locked or expired account cannot be used at all.**
- **The two global settings refuse every ordinary account's writes with it:** a namespace owner's copies, a declared writer's rows, a ledger's rows. That is the engine's documented behaviour, as the record notes (`GR:98`); the gate did not itself try those writes. Version 1 cannot run under them.
- **So MySQL has no usable refusal, and DL-106's fallback applies.** [113-1]

**The product says that MySQL cannot refuse it, and version 1 has what limits the harm:**
- **a key of its own for MySQL's `demo`,** so that it can be kept and rotated apart;
- **a declared reader for each consumer** (4.6), so that one consumer's change locks out only itself;
- **the probe,** which signs in as `demo` and so shows the engine unhealthy; and **every start,** which applies the configured passwords again (F-6).

### 4.6 Declared readers and writers

**Who may read or write is declared in the configuration.** [108-5] Version 1 has no command that enrolls anyone.

```yaml
accounts:
  readers:
    - {name: reader_a, scopes: [working]}             # the working copies
    - {name: reader_b, scopes: [working, copy]}       # and the copies of the namespace `copy`
  writers:
    - {name: editor_a, scopes: [working]}             # the working copies' rows
```

- **Each declared account is one the service makes.** Its name is checked like a prefix; it may be none of the service's own; and its key may be nobody else's (3.4). It is neither a reader and a writer at once, nor an existing account adopted.
- **It is locked until its key is set:** `<NAME>_PASSWORD`.
- **A reader's scopes** are `working`, and any defined namespaces, by reference (2.1). **A writer's scope is `working`, and only that:** in version 1 a copy's one writer is its namespace's owner.
- **A declared writer is made on both servers.** [116-1] PostgreSQL holds it out of a reset by its closed door and its one-transaction swap. **MySQL has no door, so a MySQL reset suspends it** (3.5): its grant on that schema is revoked and its sessions are ended before any change, and its grant is restored only after `done`.
- **Its grants are exactly what is declared:**

  | | PostgreSQL | MySQL |
  |---|---|---|
  | A reader of the working copies | member of `megasamples_working_read` | `SELECT, SHOW VIEW` on each working schema, by exact name |
  | A reader of a namespace | member of `megasamples_copy_<prefix>_read` | `SELECT, SHOW VIEW` on the namespace's pattern |
  | A writer | member of `megasamples_working_write` | the reader's, and `INSERT, UPDATE, DELETE` on each working schema, by exact name |

- **The start applies it,** every time: it makes each declared account that is missing; sets each keyed one's password; locks each unkeyed one; **locks every account it made before that is declared no longer;** and makes the grants exactly the declared ones. The configuration is the one authority.
- **Each reset confirms the readers' grants before its `done`,** and a MySQL reset restores its writers' grants after it (3.5).
- **The start leaves out a writer's grant on a MySQL schema whose reset has it suspended,** until that reset records `restored`. [116-2]
- **A writer writes rows, and nothing else:** no definition, no account, no registry. A reset restores what it changed.
- **Nobody is declared by default.**

### 4.7 What each account reaches, and what a credential's holder can do

**An account reaches whatever any role it inherits reaches.** A consumer whose set-up gives `admin` its own roles (F-16) gives `admin` whatever those roles are later granted.

*PostgreSQL:*

| Account | A working copy | A template | A copy of its namespace | Another namespace's copy | `megasamples` |
|---|---|---|---|---|---|
| `demo` | reads | refused | — | refused | reads |
| a declared reader | reads, if `working` is in its scopes | refused | reads, if that namespace is in its scopes | refused | reads |
| a declared writer | reads and writes rows | refused | — | refused | reads |
| a namespace's owner | refused | copies it; refused a connection | owner; reads and writes rows | refused | reads; writes its own ledger |
| `admin` | owner | copies it; refused a connection; cannot alter it | refused; **it owns the copy's tables, and connects if it inherits a role that may** | the same | reads and writes |
| `postgres` | everything | can open it | everything | everything | everything |

*MySQL:*

| Account | A working copy | A template | A copy of its namespace | Another namespace's copy | A foreign namespace's schema | `mysql` |
|---|---|---|---|---|---|---|
| `demo` | reads | no privilege | — | no privilege | reads, only where marked | no privilege |
| a declared reader | reads, if in its scopes | no privilege | reads, if in its scopes | no privilege | no privilege | no privilege |
| a declared writer | reads and writes rows | no privilege | — | no privilege | no privilege | no privilege |
| a namespace's owner | no privilege | reads | everything a schema allows, but no granting | no privilege | no privilege | no privilege |
| `admin`, `root` | everything | reads; can change the option | everything | everything | everything | everything |

**What each credential's holder can do, from any address that reaches the port** (F-20). Version 1 has no rule about where a client comes from (section 11).

| Credential | What its holder can do | What bounds it |
|---|---|---|
| `postgres`, `root`; MySQL's `admin` | everything | nothing |
| PostgreSQL's `admin` | own and change all sample data; make databases and roles | not a superuser; cannot alter a template [G-1c] |
| `demo`; a declared reader | read what it is granted. On MySQL: take any named lock; change its own password (4.5) | the read profile on PostgreSQL; its grants on MySQL |
| a declared writer | change rows of every working copy | no definition change; a reset restores. On MySQL a reset suspends it from before its first change until after `done` (3.5). |
| **a namespace's owner** | **every copy of its namespace, whoever made it:** read, write, drop. Fill the disk with copies. On MySQL, take any named lock, and so make a copy or a reset report busy. | PostgreSQL: the hook [G-29a to G-29d]. MySQL: nothing outside its pattern, and no granting [G-11b]. |

- **One credential is one trust domain.** Two runs that share a namespace owner's credential can change each other's copies, and the product reports nothing that says otherwise.
- **The product makes no claim that a copy has had one writer.** On PostgreSQL the engine itself bounds who can write a copy: its owner and the administrators. On MySQL an administrator's grant made by hand on a copy's name, perhaps before that name was issued, is not the product's to remove. The product reports each one it finds on a copy (2.2), and still makes no claim. A consumer that needs that claim establishes it on its own side (7.2).

## 5. Defaults, and what a deployer weighs

The product does not know where it runs (DL-107).

### 5.1 Version 1's defaults

| # | Default | Mark |
|---|---|---|
| 1 | **The generated Compose file publishes every port on loopback,** as today (F-28). Version 1 has no setting that widens one. | [R] |
| 2 | **No privileged account has a published password, even on loopback.** | [108-5] |
| 3 | **Nothing the product serves holds or shows privileged access.** | [108-5] |
| 4 | **`demo` keeps its published password.** | [108-5] |
| 5 | A namespace's owner, a declared reader and a declared writer are **locked until keyed.** Nobody is declared. | [D] |
| 6 | **A reset of a database preserves sessions unless told otherwise; nothing replaces an engine's volume unless told to.** | [108-2] [108-9] |
| 7 | `demo` reads no consumer's own schemas. | [D] |

**Which ways of starting it version 1 controls.** [D: review 4's finding 10; review 5's finding 7.]

| Path | Who publishes the port | What version 1 enforces there |
|---|---|---|
| `megasamples up` | the product: loopback, always | Defaults 1 to 7. T-23 checks that no configuration makes the generator publish wider. |
| **The Compose file that the current version generated, started directly** | the product: loopback, always | **A supported start.** [114-7] Defaults 1 to 7, the pages included (default 3). It may refuse to start where `megasamples up` would have asked for a decision (3.5). |
| A Compose file that an earlier version generated | — | **Not a supported start.** New code cannot make safe a file it never wrote. The README says to regenerate after an upgrade. |
| An image run by hand; a Compose file someone wrote or edited | **the deployer** | Defaults 2 and 5, which are in the image: no privileged or declared account is usable without its own private key. **Not default 1:** an image cannot know how its port is published. **`demo`'s password is published, so whoever publishes that port wider gives read access to the samples to anyone who reaches it.** |

**The last path is documented, not refused.** [110-1] DL-108 item 2 (a) is a default of the start path the product generates. An image run by hand cannot see how its port is published, so the README says that anyone who can reach that port can read the samples as `demo`.
- **On every start path, that one included, the image's start names each account still on its published password,** and keeps each privileged account locked while its key is missing or set to its published value. [110-2]
- **There is no switch that acknowledges the exposure.** [110-3] It would verify nothing, and scripts would come to depend on it.
- **Adding a refusal there later breaks hand-run scripts,** and is a decision of its own. The README claims none.

**Default 2, exactly.**
- **The privileged accounts are `admin` on both engines, `postgres`, and both of MySQL's `root`.**
- **The image holds none of them usable over the network:** each is baked with no password that signs in. Without one, each was refused on every way in that was tried, and `demo` still signed in. [G-35p, G-35m] **That the MySQL start's own maintenance works with those accounts locked is not something a gate showed.** It is T-23's to show on the candidate, and is claimed only once T-23 has passed. [115-5]
- **The start gives one a password only from its key, and tests the value:** a key that is unset, **or set to the value published today,** leaves that account locked, and the start says which.
- **`megasamples up` writes a private value for each such key that is missing,** into the checkout's `.env`, closed to others, and never prints it.
- **The reset, and everything else that signs in as a superuser, reads the same keys** (3.4). With none set it cannot run, and says so.

**Default 3, exactly.** [D: review 4's first P1: round 4 changed three consoles and left two generated pages printing `admin`'s password.]
- **No console is given a privileged password.** phpMyAdmin's second server asks for a sign-in instead of holding `admin`'s; DbGate's and CloudBeaver's `admin` connections are stored without a password, or not stored (F-31).
- **No generated page prints one.** The landing page and the Adminer help page show `demo`'s, and for `admin` say which key in `.env` holds it. Neither generator reads a privileged key at all.
- **A page that an earlier version generated is never served, on either supported start.** [114-7] An upgraded checkout still holds the old landing and Adminer pages, with `admin`'s password in them, in the directory the landing console mounts (`SM:megasamples/consoles.py:39`).
  - **The Compose file and the pages are generated in one step.** The current generator removes every page it did not write before it writes the file, and the file mounts only what that step wrote. So a current-version Compose file never exists beside an older page.
  - **`megasamples up` does the same before it starts anything,** and removes the pages when the landing console is not configured.
  - **T-23 holds it from each route's own upgraded checkout,** with a synthetic canary planted in the old pages: fetched with no sign-in, neither the landing page nor the connection page returns it. A direct Compose start that refuses to start passes too.
- **`demo` stays signed in,** as the consoles open today.

**Defaults 2 and 3 may be one bounded pull request of their own, merged before the build.** [108-5]

### 5.2 What a deployer weighs

Version 1 gives these mechanisms. Which to use is the deployer's.

| What to weigh | What version 1 gives | What stays the deployer's |
|---|---|---|
| **Who can reach the engines** | Loopback publication, on the paths the product controls. | Any forward, proxy, shared network, or image run by hand. **Version 1 has no setting for a wider listener and no rule about where a client comes from** (section 11): whoever reaches the port can try every account, and `demo`'s password is published. |
| **The transport** | PostgreSQL's passwords are not sent (`SM:ARCHITECTURE.md:166-167`). The product configures no TLS (`MR:` B-04). | A tunnel, or a network the deployer trusts. |
| **Passwords** | One key for each account. **Rotation:** set the key and start again. **Revocation:** clear a key, and the account is locked at the next start. | When, and who is told. |
| **A shared read credential** | `demo` is one account. On MySQL a holder can change its password, and the engine has no usable refusal (4.5). | A declared reader for each consumer that must not be able to lock out the others; `demo` only for the consoles. |
| **Who makes copies** | A namespace and an owner for each consumer that must be kept apart. | How many to bake, and which to leave locked. |
| **A copy owner's credential away from the service** | Claimed for a build whose confinement regressions pass (3.1). | **It can still fill the disk.** Version 1 bounds no bytes. |
| **A consumer that manages accounts** | A foreign namespace keeps the product out of the consumer's objects. | An account that manages accounts may be able to change the service's own. The product ships none and tests none; whoever adds one tests what it reaches, **before that account and a credential that has left the machine exist together.** |
| **Handing a credential over** | Nothing: **it is the deployer's own procedure,** which the README describes: one credential, alone, never the `.env`. [108-11] | The channel, and the record of it. |
| **Write access to the samples** | A declared writer, on either server (4.6). | Whether to declare one. |

### 5.3 Changing a deployment, and the runbook's split

- **A new image renews the data volumes,** and only when told to: `megasamples up --discard engine`, or a whole engine's reset (3.5). Everything made on the old ones goes. Declared accounts return at the start, from the configuration.
- **Image and data must match, and every engine's start holds it:** an image starts only on data it seeded (3.5). On PostgreSQL the policy image also refuses data without its marker (H-12).
- **After an upgrade the Compose file is generated again** before anything is started from it (5.1).
- **A MySQL volume kept from an image built before this is unqualified for the identity rule** (3.5). After going back by kept volumes, that rule is not claimed for MySQL until its volume is next replaced.
- **The runbook is split in this work.** [108-3]
  - **The product keeps a short, tested, general upgrade route, with its helpers:** replace the images, keep the old volumes until the new ones are checked, go back by the kept volumes. **Its first step comes before the earlier version's `down`: identify each engine's volume and keep it.** Then it says how to verify an edit after the upgrade, and how to go back. [115-U] **It is also the route for an engine that will not start,** which the CLI does not replace. [115-W]
  - **The live-upgrade runbook moves to DataIntent's side,** as the procedure of its rollout's plan, pinned to a sql-megasamples revision (F-29).
  - **The README's dated paragraph about one deployment, and its paragraphs that take LAN forwards for granted, leave it,** or become a profile.
  - The split is rehearsed before that rollout's approval (7.2).

### 5.4 The impact note for what version 1 changes

It enters at the freeze, with migration instructions, and every caller is changed in the same work. [108-2] [109-4] [D: review 4's finding 20.]

| What changes | Who is affected | What to do instead |
|---|---|---|
| **A reset of a database no longer ends people's sessions by itself.** | Anyone who ran `make reset` or `megasamples reset` on a database others were connected to. | Answer the question on a terminal, or pass `--discard sessions`. Automation passes `--unattended`, and is refused while anyone is there. |
| **A MySQL or SQLite reset of one database always needs `--discard sessions`.** | Every script that resets one. Automation has no unattended route for either. | Pass it knowingly. **A SQLite reset stops the consoles, and with them people's sessions on PostgreSQL and MySQL through those consoles;** the reset names the consoles first. A SQLite shell someone opened by hand is not seen, and must be closed first, as today. |
| **A whole engine's reset, and `megasamples up` on a stale image, need `--discard engine`.** | Anyone who rebuilt an image and ran `make up`; anyone who ran `make reset R=<engine>` or `R=all`. | Pass it knowingly: **every database, copy, account and edit on that engine goes.** |
| **`oracle_hr` and `oracle_oe` do not reset singly on MySQL.** [109-4] | Anyone who reset either, whichever of them is installed. | Reset the whole MySQL engine, which discards everything on it. |
| **`admin` and the superusers have no published password.** | Anyone who signed in as `admin` with the published value; every tool that did. | Read the private value `megasamples up` wrote into `.env`. |
| **No console signs in as `admin`, and no page prints its password.** | Anyone who used a console's full-access connection. | Sign in with the private value. |
| **`megasamples down` then `up` keeps each engine's data.** Today it comes back fresh. | Anyone who used `down` and `up` to get the samples back as shipped. | `megasamples reset <engine> --discard engine`. |
| **A SQLite start no longer copies the image's files over the working files,** and the documented client and the consoles open one set. | Anyone who relied on a restart to refresh what the consoles show, or to publish an edit to them. | An edit shows at once. `megasamples reset sqlite:<database> --discard sessions` puts one back. |
| **An engine does not start on data that another build seeded.** | Anyone who rebuilt an image and started it over the old data, by `up` or by Compose. | `megasamples up --discard engine`; or the upgrade route, which keeps the old volumes aside. |
| **After an upgrade, the Compose file is generated again before it is used.** | Anyone who starts the stack with the Compose file directly. | Run the generator, or `megasamples up`. A file from an earlier version is not a supported start. |

**Callers changed in the same work** (F-33): the Makefile's `reset` shim; **every validation script that calls it,** found by a search and not from a list: today `probe-reset-flags.py`, `rehearse-lts-resets.py`, `probe-approved-datasets.py`, `rehearse-lts-append-reset.py`, `rehearse-lts-persistence.py` and `validate-credential-prerequisite.py`, each of which resets with no option and expects success; the README's reset examples, the single SQLite one among them; the general upgrade route; the reset's own unit tests. T-21 fails if a call of `reset` in the repository names a target that needs an option and passes none.

## 6. The contract and its versioning

| Thing | Where it lives | Its own version |
|---|---|---|
| The JSON envelope and each result | standard output | `schema` |
| The commands and options of section 0; the exit codes and their promises; the lock protocol of 2.2 and 3.5; the names; the `.env` keys; the configuration keys of section 0 | the command line, the process, the server, two files | `interface` |
| The service's record, **with the volume's identity** | a comment or a table in the server; for the service's SQLite files, a file in their volume | the tag `megasamples-service/1` |
| A template's record | the same | `megasamples-template/1` |
| A copy's row; a copy's comment on PostgreSQL; its marker event on MySQL | a ledger; the copy | `megasamples-copy/1` |
| An operation's record, **with its identity, its epoch and its terminal outcome** | `megasamples.operations`; a file where the service runs | `megasamples-operation/1` |
| SQLite's manifest; its sidecar | files on a disk | `megasamples-manifest/1`; `megasamples-sidecar/1` |

**The rules.** [108-1]
- **Version 1 of each is fixed at the merge into `main`.**
- **Within a version, only additions,** and a reader obeys these, which are tested: a member it does not know is ignored; an exit code it does not know is treated as 8; a state it does not know is not usable; a sweep's reason it does not know means the copy was kept.
- **Any break raises the number of the thing that broke, and is recorded with what it breaks.**
- **A format held in a server is matched exactly, or refused:** exit 5, `format-unknown`, before any change.
- **A consumer's files are read one format back, for identification and reporting only.** Such a copy is kept and reported; it is removed only by an explicit `copy drop`.
- **An unknown format is refused before any change, clean-up included.**
- **Who approves a break, or a loosening of one of 5.1's defaults,** is the governance of the repository's maintainers, and is not part of the product. [108-1]

## 7. Deployment profiles

Examples of configuration. Neither is a premise of the product.

### 7.1 A laptop

The default. `megasamples up` writes the privileged keys; `demo` is published; nothing is declared; the namespace `copy` is locked. To make copies, set `COPIER_PASSWORD`.

### 7.2 DataIntent's development instance

One deployment, by the product's present maintainers. Its records are DataIntent's. **Nothing here is the product's.**

**Its configuration.**

| | This instance |
|---|---|
| **Exposure** | Published on loopback, and forwarded to a LAN by two socket units outside the product (F-30). **Version 1 gives it no rule about origins, so its administrators are reachable wherever the forward reaches.** That is recorded as such on DataIntent's side; custody of their credentials is their protection. |
| **Templates** | `core`; the selection on each engine is made at its rollout's approval, from the build's measurements. |
| **Namespaces** | One for each machine or consumer that makes copies, and spare locked ones. None begins with `di`. |
| **Foreign namespaces** | `di`, marked `demo_reads: true`: its fixture's own (F-16, F-30). So `demo` keeps the sight of `di_…` schemas on MySQL that DL-079 item 3 allowed and a DataIntent case asserts. |
| **Declared accounts** | A reader for each LAN consumer, since MySQL cannot refuse a password change (4.5). **No writer:** its first is the two deciders' decision, after the controls of `ED:` R-39. |
| **MySQL's binary log** | Its choice at its rollout's approval. The image starts and passes either way [G-18a, G-18b]. |

**Its policy,** each a choice among 5.2's mechanisms:
- **No administrator's or superuser's credential leaves the machine,** `di_admin` and its fixture and provisioning credentials included.
- **Whether to send a namespace owner's credential elsewhere is DataIntent's.** It sends none before that engine's confinement regressions pass on the candidate (T-7, T-9). Meanwhile it records DL-077 item 3's "from a separate machine" as unmet for that engine. [108-1]
- **`di_admin` and a MySQL namespace credential that has left the machine must not come to exist together untested.** **Before the first sending, or before it provisions `di_admin`, whichever would first bring the two together, DataIntent has on record that `di_admin` was refused** each change it tried to a namespace's owner and to a per-consumer reader: its password, its lock, its grants and its removal. **A test that finds it can make any of them does not meet this,** and the two are then not brought together. [D: review 4's finding 17; review 5's finding 18.]
- **It keeps the record of each sending,** an uncertain delivery included, and holds a send it cannot record. [108-1]
- **MySQL's `demo`** gets a key of its own, rotated at its rollout, which ends the value its LAN machines already hold; each of them reads with its own declared reader.
- **Its automation resets with `--unattended` only:** one PostgreSQL database at a time. It resets no MySQL database, **and no SQLite one: it has no unattended route to either in version 1.** Its SQLite cases work on copies of their own. [108-1]
- **A long run renews its lease.** `ED:` criterion 11, "never a copy in use", is recorded as **not passed** for an idle MySQL session and an open SQLite file whose lease has ended.
- **A result that needs to be the only writer** (`ED:` R-35). On PostgreSQL it holds for a namespace one run uses alone. **On MySQL it is recorded as unmet in version 1,** unless the copy's own document reports no other account's grant on its name, and DataIntent, as an administrator on its own instance, has read the same. [D: review 4's finding 16.]
- **After its deployment, loosening one of these is the owner's** (DL-106), as its own rule.

**What else version 1 means for it.**
- A copy's name is issued; its harness keeps the name and the identity, and finds a copy by its label after a lost reply.
- Its edit tests' writer of a **copy** is that namespace's owner in version 1.
- A MySQL copy holds one event that the dataset does not: the marker (2.2).
- **It has no MySQL copy of a database with triggers** (2.4): `sakila` and `adventureworks_lt` among them. A case that needs one is Not run there, by exit 4, in version 1.
- Its kept MySQL volume, from today's image, is unqualified for the identity rule (5.3).
- The provider's list of databases does not gain the templates: it leaves out every database marked as a template (F-17). A raw catalog query shows them; the registry does not list them. Each is tested apart.
- A fixture role cannot connect to a working copy. The fixture grants `EXECUTE` on its own routines, and `TEMPORARY` where a case needs it. A fixture role cannot change its own password on PostgreSQL.
- Its harness maps the exit codes (`ED:` 4.2): 3 and 4 are Not run; 2, 5 and 7 Failed; 6 a deferral; 1 and 8 Failed, and it reads the state first.

**Its one rollout** (DL-103; DL-105). The plan is DataIntent's record; this is what version 1 asks of it.

| # | Step | It must show |
|---|---|---|
| 1 | **Version 1's gates** (8.1): run. **This revision's dispositions, checked once by Astra;** a disputed one returns to the deciders. | DL-114 item 6. |
| 2 | **The credentials, consoles and pages change** (5.1), as its own pull request if it is split out. | Merged before the build. |
| 3 | **The build,** test-first, on a branch that merges pull request #14's branch first (section 9). **Astra and Fable review its code and tests to two rounds in a row with nothing to fix now.** | 8.2, section 14 whole, and 8.3's trace: every claim has its test, or is gone. |
| 4 | **DL-078's README,** on the same branch, reviewed. **The runbook's split,** rehearsed. | Section 10; 5.3. |
| 5 | **The branch's candidate,** built in an isolated store. | The dataset matrix, the image tests and every native suite Passed. **The gates that ran on a prototype or on compiled sources pass again on the candidate itself,** as T-7 and T-8; G-13 runs on it as a regression. [112-3] |
| 6 | **DL-087's acceptance is recorded.** | Nothing from step 7 on comes before it (F-26). |
| 7 | **DataIntent's comparison against that candidate,** the read account's admission among it. **And the reconciliation of the product's routine inventory with DataIntent's own (IA-01), recorded: each signature in one and not the other, with its disposition.** | Below. These are DL-085 item 3's conditions. |
| 8 | **The reviews, on the head step 7 compared:** one independent review that covers **both the compiled hook and the `SECURITY DEFINER` event trigger,** each named in its record; Fable's and Astra's blessing (DL-086). | A review that signs off one of the two does not meet it. The hook's review may start with the build's first slice [114-5], and reports what can raise between the copy and the commit [113-4]. |
| 9 | **The merge into `main`.** | Version 1 of the contract is fixed here. |
| 10 | **One build of the final `main`,** qualified: the suites again, and the comparison again. | This is the build that is deployed. |
| 11 | **The two deciders' approval** of one exact plan the coordinator directs. | A plan that changes afterwards goes back to them. |
| 12 | **The rollout,** then DataIntent's accepting run on the live instance. | Accepted only then. |

- **The comparison is all five parts** (F-24): C1, PostgreSQL's suites; C2, the MySQL provider probe, since `demo`'s grants change; C3, SQLite freshly staged, since the image is rebuilt; C4, the observed identities, since every build id changes; **C5, both controls:** an export refused with an empty stream after an elevation, and when the fresh check cannot be made, on each isolated server only. One DataIntent revision and one inventory across steps 7, 10 and 12.
- **It compares two builds of the service on the same engine versions,** and its evidence says so.
- **Before the rollout the live instance still has today's profile.** The candidate half expects `demo` admitted; the live half expects it **refused**, as a recorded baseline. Which route the rest of the live half takes is DataIntent's to name.
- **A part whose prerequisite does not exist** waits, or goes to the deciders by name. It is not left out.
- **Its verification is generated from each account's effective state,** not from whether it has a key. [D: review 4's finding 19: a privileged account keyed to the published value is locked on purpose.]
  - **An account with a private key signs in,** and a wrong password is refused as an authentication failure.
  - **`demo` with no key signs in with its published value;** MySQL's `demo` with no key of its own, with `DEMO_PASSWORD`'s. Each is checked with the credential that is in effect for it.
  - **Every other account with no key, and a privileged one keyed to the published value, is refused.**
  - The probe and each console sign in as the account they are meant to. No console and no served page offers or shows anything privileged.
- **Its rollback** is by the kept volumes (5.3). Where MySQL's `demo` was rotated, the old shared value is in force again afterwards.

## 8. Gates and tests

### 8.1 Version 1's feasibility gates, and what each showed

**All 58 have run, on a task-owned isolated stack, each with its control shown.** [108-12] The record is `GR:`.
- **The first run:** 55 Passed, 3 Failed, 0 Not run, 0 Unsupported. The three were G-13, G-17b and G-33a.
- **The deciders ruled on the three** (DL-111, DL-112), and their re-runs Passed. Each of those rows says what first happened and what was done.
- **Each gate is one assertion, with a control that would fail if it were false.** Its test is as round 5 defined it, in this file at `0896ebc`, section 8.1; its launcher is `tests/gates/<gate>` on the gates' branch.
- **A row's last column but one says what in version 1 rests on that result.**

**What they ran on** (`GR:76-83`): PostgreSQL 18.7, MySQL 9.7.4 and SQLite 3.54.1, from the retained images of `main` at `e61335f`; and its consoles, CloudBeaver 26.2.5, DbGate 7.3.6, Adminer 6.3.0 and phpMyAdmin 5.2.3.
- **E · engine-only** (52): that stack, stock clients, raw SQL and plain processes. No code of this work.
- **H · needs the hook** (6): the same, with a prototype of the changed rules preloaded. No CLI code.

**What a result here does not show.** Each is a regression's to show, on the candidate (7.2, step 5):
- **The six H gates ran on a prototype of the rules, not on the built hook** (`GR:83`). T-7 repeats them.
- **G-2c and G-5a to G-5c ran on pull request #14's exact policy sources,** compiled and applied to disposable copies of the data. Its candidate image was not reproduced (`GR:82`). T-8 repeats them on the candidate.
- **G-33a's re-run used a fixture image** built from a scratch copy of the product's recipe with the removal added (`GR:152`). T-30 holds it in the product's own build.
- **Nothing that needs the CLI, the start wrapper or the package is a gate.** Those are 8.2's. [D: review 4's finding 13.]
- **The product's full regression suite was Not run** by the gates' task (`GR:111`, `:162`).

**The stack was put back:** eight images and 95 dataset fingerprints matched before and after, and the live deployment's inventory was unchanged (`GR:114-138`, `:164-168`).

**PostgreSQL: the template and what a copy carries.**

| Gate | Kind | The one assertion | Result | What was observed, with its control | What rests on it | Serves |
|---|---|---|---|---|---|---|
| **G-1a** | E | A template that accepts no connections refuses every connection. | Passed | The closed template refused a query on the local socket and from the bridge. Control: opened, it answered. | every PostgreSQL template, copy, and reset from a template | 5, first |
| **G-1b** | E | A role with `CREATEDB` alone copies it, and two copies at the same moment both succeed. | Passed | Two sessions were inside `CREATE DATABASE` together; the twin and both copies gave one count and one checksum. Control: the same role's copy of a database that is not a template was refused, `42501`. | every PostgreSQL template, copy, and reset from a template | 5, first |
| **G-1c** | E | `admin` cannot alter, rename, drop or comment on it. | Passed | `ALTER`, rename, `COMMENT` and `DROP` as `admin`: each `42501`. Control: all four succeeded on a database `admin` owns. | **every use of a template as pristine:** PostgreSQL copies, template resets, and rule 2's registration | 5, first and fifth |
| **G-2a** | E | A copy carries each object's owner, and each object's grants to group roles and to `pg_database_owner`. | Passed | Five rows of owners and grants were equal in the twin and its copy, the grant to `pg_database_owner` among them. Control: a grant added to the twin afterwards was absent from the copy. | the read group and the owner's writing: all PostgreSQL copies and reset-made working copies | 5, first and fourth |
| **G-2b** | E | A copy carries the default privileges. | Passed | Two rows of default privileges were equal in both. Control: a later grant changed the template's alone. | the closed defaults of pull request #14 on every copy and reset-made working copy | 5, fourth |
| **G-2c** | E | A copy carries the policy's extension and its event trigger. | Passed | On pull request #14's policy: the copy held the extension, and a routine made in it had no `EXECUTE` for `PUBLIC`. Control: with the extension removed, it had. | **the strict profile on every copy and reset-made working copy** | 5, fourth |
| **G-2d** | E | A copy does not carry `CONNECT`, its owner or its comment. | Passed | The twin had the superuser as owner, a comment and a `CONNECT` grant. Its copy had its creator as owner, no comment and no grant. | 4.1's `CONNECT` table; the copy's own comment as its proof | 5, first and second |
| **G-23** | E | A grant to `pg_database_owner` is held, in each database, by that database's owner and by no other ordinary role. | Passed | The copy's owner updated rows. The namespace's reader and the working writer were each refused, `42501`. Control: the owner was refused the same in a working database. | a copy's owner writing its copy: PostgreSQL copies | 5, first and seventh |

**PostgreSQL: locks, proof, and the reset.**

| Gate | Kind | The one assertion | Result | What was observed, with its control | What rests on it | Serves |
|---|---|---|---|---|---|---|
| **G-7a** | E | A session's advisory lock is held while that session runs `CREATE DATABASE`, also after its client is gone, and ends when the session does. | Passed | With its client killed, the session's lock still refused a second session while the create ran; the copy then appeared. Control: once the backend ended, the lock was granted. | on PostgreSQL: every `copy` command that changes anything; `reset` of one database | 5, first and third |
| **G-7b** | E | The same key taken from another database does **not** conflict. | Passed | The same key, held in another database, was granted. Control: in the same database it was refused. | where the lock is taken: every command takes it in the `megasamples` database (2.2) | 5, first and third |
| **G-8a** | E | A database's comment is read by any role from any database, and set only by its owner or a superuser. | Passed | A reader read the template's comment from `megasamples`. A namespace's owner was refused setting it, `42501`. Control: it set and read its own copy's. | template records; rule 2's registered template; a copy's proof | 5, first, second and fifth |
| **G-8b** | E | A plain `DROP DATABASE` refuses while any session is connected to it. | Passed | With one session connected, the drop was refused, `55006`. Control: with none, it succeeded. | on PostgreSQL: `copy drop`, `copy sweep`, and the reconciliation's drop of a transient | 5, first and third |
| **G-24p** | E | A database dropped and made again under one name has another OID. | Passed | The reused name's OID changed from one creation to the next. Control: an untouched database kept its OID across a restart. | the proof on PostgreSQL: `copy drop`, `copy sweep`, the reset's steps c and g | 5, second |
| **G-24w** | E | **Between a proof's check and the drop, no account but the object's owner and the administrators can put another object under its name.** | Passed | Outside roles could neither drop the object nor take its name: `42501` or `42P04` on PostgreSQL; `1044` on MySQL, for the schema and for the marker. Control: the owner replaced each, and the OID or the marker then no longer matched. | `copy drop` and `copy sweep` on each server. **It tried no account with a hand-made grant on the name;** that is the `not-exclusive` check, and T-10's. | 5, second |
| **G-3a** | E | Closing a database to connections, and a row's update, commit or roll back together. | Passed | Rolled back: the phase and the admission were as before. Committed: the new phase was read, and a new connection was refused. | PostgreSQL's reset of one database | 5, third and eighth |
| **G-3b** | E | Two renames, a `CONNECT` grant and a row's update commit or roll back together. | Passed | Committed: both names with their OIDs, the phase `swapped`, and a reader saw the new data under the old name. Rolled back: both original names and OIDs, no grant, the phase `closed`, and the reader refused. | PostgreSQL's reset of one database | 5, third and eighth |
| **G-3c** | E | A closed database keeps its sessions and refuses new ones; the superuser ends a session of `demo`'s. | Passed | After the door closed, an open session still answered and a new one was refused; the superuser ended the open one, and none remained. | the door and the session decision on PostgreSQL | 5, third; 2 (b) |
| **G-26p** | E | **A restore worker that outlives its lock holder changes nothing but its own transient.** | Passed | `pg_restore` went on in the first transient while its coordinator was killed and two admissions raced it. The working database's checksum was unchanged, and the two transients had OIDs of their own. Control: a restore aimed at the working database changed its checksum. | **PostgreSQL's reset from the image** | 5, third and eighth |
| **G-9** | E | When the data volume fills during a copy, by each strategy, and during a reset before its swap: the server stays up, no part of the new database remains in the catalog, and every other database is whole. | Passed | At 2,048 KiB free every create failed: by `WAL_LOG` with an internal error, `XX000`; by `FILE_COPY` with the disk-full code, `53100`. Each time the server answered, the catalog had no row for the new database, and every database's checksum matched. Control: with space, each succeeded. A reset's build is the same statement. | on PostgreSQL: `copy create`; `reset` of one database. **Only a failure inside `CREATE DATABASE` was exercised;** a later one is T-14's and T-19's. | 5, first and eighth |
| **G-32a** | E | **A session is told to be the product's own by its application name, and by nothing else.** | Passed | Through CloudBeaver's editor a person's statements ran, and its sessions then sat idle as `demo` with no transaction. The reserved application name matched exactly one session, the product's. Control: under another name it matched none. | ending any session without `--discard sessions` | 2 (b) |
| **G-32b** | E | With the stack up and nobody using a console, no console holds a session on an engine. | Passed | Three polls with nobody there: no console held a session on PostgreSQL or MySQL. Control: opening a connection in CloudBeaver left two idle sessions. | the session decision's default: it does not refuse by itself. A connection a person opened does hold it (3.5). | 2 (b) |

**PostgreSQL: the profile and the hook.**

| Gate | Kind | The one assertion | Result | What was observed, with its control | What rests on it | Serves |
|---|---|---|---|---|---|---|
| **G-5a** | E | On pull request #14's candidate, a role other than `demo` and `admin` cannot call an operator's function. | Passed, **on the policy's source** | A fresh role's `SELECT 1 = 1` was refused, `42501`, for `int4eq`. Control: `demo`'s returned true. | P-1. H-1 is reproduced. **This is a result about pull request #14's policy as it stands;** on the candidate, with P-1, the same statement must succeed (8.3). | 5, fourth |
| **G-5b** | E | `pg_export_snapshot`, `pg_current_snapshot` and `pg_database_size` assign no transaction id and change no catalog row; a snapshot exported by one session is imported by another, both holding only the floor and the three. | Passed | Each of the three returned with no transaction id assigned and the catalog's digest unchanged. A second transaction imported the snapshot and read the earlier row. Control: each was refused before its grant. | P-3, P-5 | 5, fourth |
| **G-5c** | E | A trigger's body runs with the rights of the account whose statement fired it. | Passed | The writer's insert was refused, `42501`, for `current_setting`, and wrote nothing. Control: with that one built-in granted, it wrote. | P-6; a declared writer | 5, fourth and seventh |
| **G-6a** | E | Natively, a role without `CREATEROLE` can change its own password, and cannot change another role's. | Passed | The role set its own password to null. Control: its change of another role was refused, `42501`. | nothing by itself: it shows the hazard that rule 4 is for | 5, fourth |
| **G-6b** | H | With rule 4, that role cannot change its own password, its own settings or its own default privileges, and still reads. | Passed | On the prototype: the three statements were each refused, `42501`; the role still read; its password was unchanged. Control: `admin` altered a role it manages; with the library not loaded, all three succeeded. | rule 4, and with it PostgreSQL's refusal in 4.5. The built hook repeats it (T-7, T-25). | 5, fourth |
| **G-4a** | E | `REVOKE … FROM PUBLIC` on a new database, by a creator that is not its owner and does not inherit the owner's rights, leaves `PUBLIC`'s privileges in place and raises no error. | Passed | The non-owner's `REVOKE` ended with exit 0 and warning `01006`, and `PUBLIC`'s privileges remained. Control: the owner's revoke removed them. | rule 1, and rule 3's confirmation. H-2 is reproduced. | 5, fourth |
| **G-4b** | H | An error raised after `CREATE DATABASE` has copied its files leaves files with no catalog row. | Passed | On a prototype that raises after the copy: the catalog had no row, and the data directory held one directory with none. Control: an ordinary create left only its own; with the library not loaded the create succeeded and left nothing over. | H-3 is reproduced: its resolution is required before the merge (4.3). | 5, fourth |
| **G-29a** | H | **The destination.** A namespace's owner is refused a database whose name is not exactly its own namespace's form. | Passed | On the prototype: four malformed destinations were refused, `42501`. Control: the well-formed name was made; with the library not loaded, the first malformed one was accepted. | **PostgreSQL copies, here and from elsewhere.** The prototype resolved names through the caller's search path; the built hook does not, and repeats this from an owner's own database (4.3, T-7). | 5, fifth |
| **G-29b** | H | **The source.** A namespace's owner is refused any source that is not a registered template. | Passed | On the prototype: five unregistered sources were refused, `42501`. Control: the registered one was copied; not loaded, the first was accepted. | **PostgreSQL copies, here and from elsewhere.** As G-29a: repeated on the built hook, from two places (T-7). | 5, fifth |
| **G-29c** | H | **The rename.** A namespace's owner is refused every rename of a database. | Passed | On the prototype: a rename inside the namespace and one outside it were refused, `42501`. Control: `admin` renamed a database of its own; not loaded, the rename was accepted. | **PostgreSQL copies, here and from elsewhere.** The built hook repeats it (T-7). | 5, fifth |
| **G-29d** | H | **Nobody else is bound.** A role that may create databases and owns no namespace creates and renames as PostgreSQL lets it. | Passed | On the prototype: a role with no marker created both names and renamed its own, and the catalog query classed the one under the prefix `unmanaged`. Control: once given the marker, it was refused both. | the claim that rule 2 binds namespace owners only | 5, fifth |
| **G-35p** | E | A PostgreSQL role with no password cannot sign in over any network rule the image has, while the container's own maintenance still can. | Passed | `admin` and `postgres`, with null passwords, were refused on both TCP ways in, as authentication failures; the local socket still answered as the user meant. Control: with passwords, both signed in on both. | default 2 on PostgreSQL | 5, sixth |

**MySQL.**

| Gate | Kind | The one assertion | Result | What was observed, with its control | What rests on it | Serves |
|---|---|---|---|---|---|---|
| **G-10a** | E | `READ ONLY = 1` on a schema refuses every account's write. | Passed | `UPDATE` and `ALTER` were refused for all three accounts, `3989`. Control: with the option off, both succeeded as `admin`. | every MySQL template and copy | 5, first |
| **G-10b** | E | It is read by several `INSERT … SELECT` at once. | Passed | Two `INSERT … SELECT` sessions ran together; the source and both copies gave one checksum. Control: a write into the source was refused, `3989`. | every MySQL template and copy | 5, first |
| **G-10c** | E | Changing the option needs `ALTER` on the schema. | Passed | The owner with `SELECT` alone was refused, `1044`. Control: `admin` opened the schema and changed a row. | the claim that only an administrator can open a template | 5, first |
| **G-11a** | E | In a schema-level grant an escaped underscore is literal, and an unescaped one matches any character. | Passed | Escaped: `a_b` was read and `axb` refused, `1142`. Control: unescaped, both were read. | every grant the product makes on MySQL | 5, first, fourth, seventh |
| **G-11b** | E | A holder of 4.4's privileges on `P\_%`, with no grant option, can create, fill and drop inside it and nowhere else, and can grant nothing. | Passed | Create, fill and drop inside the pattern succeeded. Definition changes on schemas outside it were refused, `1044`, and so was a `GRANT`. | MySQL namespaces; a MySQL owner's credential used away from the service | 5, first and fifth |
| **G-11c** | E | `demo`'s grants reach what they name and nothing else, **with a foreign namespace marked readable beside one that is not.** | Passed | `demo` read the working schema and `fa_x`. It was refused `fb_x`, `fax`, `mysql.user` and the template, `1142`. | `demo`'s narrowing; declared readers and writers; `demo_reads` | 5, fourth and seventh |
| **G-13** | E | **A replayed definition belongs to the schema it was replayed into.** | **Failed,** as first defined. Its consequence is applied. Re-run Passed. | **First run:** with the log on, the owner's trigger was refused, `1419`; with it off the trigger replayed and wrote into the copy alone; every other kind passed both ways, the source changed and the copy not. **Re-run, as evidence for the deciders** [111-3]: with the log on and trust unset, a trigger `1419` and a function `1418`; with `log_bin_trust_function_creators` set, a trigger, function, procedure, view and event replayed in both modes, source and copy apart, grants unchanged, and warning `1287` at every setting of it. | **Applied:** no MySQL copy of a database that holds a trigger, or a function of a kind not shown to replay (2.4). [111-3] [112-1] [113-2] The setting stays unset; the lift is S-8. MySQL copies of every other templated database rest on the part that passed. | 5, first |
| **G-15a** | E | A named lock is held while its session runs a statement after its client is gone, and ends with the session. | Passed | With its client killed, the lock still refused a second session while the statement ran. Control: granted once the session ended. | on MySQL: every `copy` command that changes anything; `reset` of one database | 5, first and third |
| **G-15b** | E | `DROP DATABASE` waits on a transaction that has touched the schema, and gives up at the lock wait's end. | Passed | The drop gave up, `1205`, and the table's checksum was unchanged. Control: with no transaction open, it succeeded. | `copy drop` and `copy sweep` on MySQL | 5, first |
| **G-24m** | E | **A marker event made first in a schema is there exactly as long as that schema is,** and a schema made again under the same name within the same second, with the same tables, does not have it. | Passed | In both log modes the marker was there, disabled, before and after a restart. A schema made again within the same second, with the same tables, had no event. Control: the untouched schema kept its own. | the proof on MySQL: `copy drop`, `copy sweep`, and so MySQL copies at all | 5, second |
| **G-26m** | E | **From admission to the written outcome, a competing reset or reconciliation never changes a target that a live coordinator or worker holds.** | Passed | All five intervals, each with the coordinator killed, the worker killed and the server restarted: the locks and the phase kept the second admission out, and a fenced late stream stopped at its second statement with checksums equal. Control: with the fence removed, the late stream loaded. | **MySQL's reset of one database.** It did not exercise a stream that arrives after a reconciliation holds the worker lock and before it raises the epoch; 3.5's guard and T-20 do. | 5, third and eighth |
| **G-27a** | E | A grant revoked from an account, with that account's sessions ended, leaves it unable to write the schema. | Passed | After the revoke alone, the writer's open session still wrote. After that session was ended, a new one was refused, `1142`. Control: the writer wrote before the revoke. | **the suspension of declared writers through a MySQL reset** [116-2]: both the revoke and the ending of sessions are needed, and both are made (3.5, step b) | 5, third and seventh |
| **G-27b** | E | A revoked grant is still revoked after the server restarts. | Passed | After a restart the writer was still refused, `1142`. Control: it wrote before the revoke. | the suspension holding across a restart of the server, until `restored` [116-2] | 5, third and seventh |
| **G-16** | E | Whether the pinned MySQL can refuse an account's change of its own password while that account still signs in. | Passed | All four statements changed the password. `PASSWORD REQUIRE CURRENT` refused three, and `SET PASSWORD … REPLACE` still changed it. A locked or expired account could not sign in. Global `read_only` and `super_read_only` refused all four with sign-in intact, by the probe, a client and each console. The matrix is at `GR:85-98`. | 4.5's branch: MySQL has no refusal that version 1 can use | 5, fourth |
| **G-17a** | E | When the disk fills during a copy, the server stays up and every template and working schema is whole. | Passed | The `INSERT … SELECT` failed, `1114`; the server answered; the template's and the working schema's checksums were unchanged. Control: with space, every row arrived. | `copy create` on MySQL | 5, first |
| **G-17b** | E | When the disk fills during a load that has already dropped its schema: the server stays up, every other schema is whole, the row read back is the last phase successfully written, and the schema's counts and checksum differ from the image's. | Failed, by the test's own defect. **Re-run Passed.** | **First run Failed by its own test:** after the load failed, the test itself wrote `done` and then required that write to fail. **Corrected** [111-1], **re-run:** the load failed, `1114`, at 0 KiB free; a write of `failed` succeeded and was read back; the schema held no rows where the image has 32,768; the server answered and the other schemas matched. Control: after space was freed, a reload matched the image's count and checksum. | MySQL's reset of one database, and its rule that `done` follows only a verified load (3.5). T-27 holds it through the real command. | 5, third and eighth |
| **G-18a** | E | The shipped MySQL starts and passes its image tests with the binary log off. | Passed | `log_bin` read 0, and the image's whole test suite reported no failure. | the `binary_log` key, which is in version 1 [109-2] | 1 |
| **G-18b** | E | It does so with the log on, as shipped. | Passed | `log_bin` read 1, and the same suite reported no failure. | the image as it ships, with the log on | 1 |
| **G-35m** | E | **Each privileged MySQL account, by each way in, cannot sign in while locked.** | Passed | Locked, each account on each way in was refused, `3118`, after a restart too, while `demo` signed in. Control: before locking, `CURRENT_USER()` named `admin@%`, `root@%` and `root@localhost` on the ways meant. | default 2 on MySQL. **It did not show the start's own maintenance working with those locks;** T-23 does. | 5, sixth |

**Both servers, and SQLite.**

| Gate | Kind | The one assertion | Result | What was observed, with its control | What rests on it | Serves |
|---|---|---|---|---|---|---|
| **G-33a** | E | Each volume has an identity that survives a restart and is not the next volume's. | Failed, on today's image. **Re-run Passed.** | **First run Failed on MySQL:** the image bakes `auto.cnf`, and the old and the new volume reported one server UUID (F-34). **With the build's removal** [111-2], **re-run:** the image held no `auto.cnf`; two fresh volumes reported different UUIDs, and each kept its own across a restart. PostgreSQL's row and SQLite's file kept across a restart and were absent after replacement, in both runs. | `volume`, as information and as the `copy` commands' check [114-2A]. On MySQL: for volumes from an image built with the removal; older ones are unqualified (3.5). | 9 |
| **G-33b** | E | **Nothing started against one volume changes the next.** | Passed | Three paused commands lost their connections. A late restore found no transient, and a late MySQL stream failed at its epoch query, `1146`. The new volumes' catalogs and fingerprints matched the image's. Control: an unfenced stream loaded into the new volume. | **Evidence only.** The guarantee it was to carry is not claimed in version 1 [114-2A]: a replacement is refused while a reset is running or unsettled. The checks it exercised stay, as checks. | 9 |
| **G-19a** | E | On the filesystems a copy is made on, a bind mount shared by a host and a container among them: exclusive creation and a hard link each fail when the name exists, and two racing publications leave one winner. | Passed | Across the bind mount, exclusive opens and hard links refused occupied names, and each race between host and container had one winner. Control: a vacant name was published and read from both sides. | every SQLite `copy` command | 5, first |
| **G-19b** | E | **A file moved aside and compared with a retained link is this copy's exactly when they are one file;** and while the link is kept no other file has its inode. | Passed | A replaced file failed the comparison and was put back without overwriting. None of a thousand new files shared the retained inode. Control: an untouched copy compared the same. | the proof on SQLite: `copy drop`, `copy sweep` | 5, second |
| **G-19c** | E | When the destination fills while a file is staged beside its final name, or while a small record is written beside it, no final name holds a file that is not whole. | Passed | On a full filesystem all four stagings failed, `ENOSPC`, and each final name held whole content. Control: a partial staging differed by hash; with space, a complete one matched. | SQLite `copy create`; SQLite's reset of one database | 5, first and third |
| **G-20** | E | A `flock` held by one process is seen by another across the host and a container on one mount, and a lock file replaced after it was opened is detected. | Passed | A lock held on the host was seen in the container. A replaced lock file was detected as another file. Control: the vacant path could be locked. | every SQLite `copy` command that changes anything | 5, first |

**Not gates.** Round 4's G-12 withheld nothing: whether a grant outlives its schema's drop only decides whether the reset's regrant repairs or confirms, and T-5 observes it. G-21 needed the package, and is T-28. G-32m had no consumer: every MySQL reset of one database needs `--discard sessions`. What the start wrapper decides about a configured value is T-23. Whether a deployment's clients look different to its servers, and what an account that manages accounts can do, are a deployer's own to observe.

### 8.2 Regressions

Revised from what the gates showed. Every red asserts the outcome that is wanted, and fails on the commit before its change because that outcome is not yet there. Every row has a reversal that changes the very assertion it plants a fault for.

**The native entry point.** A native test runs only against **an explicitly provisioned, task-owned, disposable target,** named to it: its project, its store and its ports. It verifies that the target carries the marker its provisioning wrote, and refuses one without it. It names no machine and no path. Its own tests: a shared target is refused; a second isolated one is accepted.

**The reset slice starts with these, each written and red before its code.** [115-9] [116-4]

| The route | Its first test |
|---|---|
| **P1-1** · a whole engine replaced over a reset that is still running, recoverable, or unreadable | T-22 |
| **P1-2** · a retained MySQL write grant that changes verified data | T-27 |
| **P1-3** · an upgrade that would put fresh data into service | T-22, with T-29 |
| **P1-4** · a SQLite reconciliation that overwrites a later edit | T-19, with T-32 |
| **DL-116** · a declared writer reconnecting at each step of a MySQL reset | T-33 |
| **DL-116** · a writer's grant that cannot be restored after `done` | T-33 |
| **DL-116** · a writer's session ended in the middle of a transaction | T-33 |

| # | The outcome asserted | Its reversal | The class it covers |
|---|---|---|---|
| T-1 | **A template is closed, as its engine closes it.** PostgreSQL: every account's connection is refused. MySQL: every account's write is refused; `demo` and a declared account have no privilege on it; a namespace's owner and the administrators read it. | PostgreSQL: built with connections allowed. MySQL: the option left off. | Every templated database; every account; each engine's own expectation. |
| T-2 | **Nothing an ordinary account does changes a template.** PostgreSQL: `admin`'s alteration is refused. MySQL: a namespace's owner's is refused; `admin`'s change of the option succeeds, and is the stated limit. | The template made `admin`'s; the owner given `ALTER` on it. | Rename, owner, flags, drop, comment, grant; a row change; the option. |
| T-3 | **No defined prefix overlaps anything, and a scope that names a defined namespace is accepted.** `oracle` as a namespace or as a foreign namespace does not build; **nor does the prefix `working`;** a reader with the scope `copy` does. **A declared account whose key would be another account's does not build.** | Each check removed in turn; the reference check made to refuse `copy`; `working` allowed as a prefix. | Database names, templates, `megasamples`, engine schemas; adjacent prefixes such as `lab` and `lab2`; a scope that names nothing; the names `mysql_root`, `mysql_demo`, `demo` and `admin`; two declared names with one key; a declared writer on a stack with MySQL alone, which builds. |
| T-4 | **The reach tables of 4.7,** cell by cell. | One fault for each column. | Every account against every kind of database, for connect, read, row write, definition change, drop and grant; a right held directly and through an inherited role. |
| T-5 | **Declared grants are in force after a start and after each reset:** a declared reader reads a working table, and a declared writer changes a working row, after its database was reset, on both servers. | The reset's confirmation removed; the start's step; MySQL's restore step removed. | Both servers; every reset path; an account declared no longer, locked at the next start; **a start during an unsettled MySQL reset, which leaves the suspended writer's grant out** [116-2]. It also records whether a MySQL grant outlived the drop. |
| T-6 | **A declared writer writes rows of working copies and nothing else:** it is refused a definition change, a copy, the registry, a template. | The write grant put in the template. | Both servers; a reader of a namespace and of the working copies at once. |
| T-7 | **The hook's four rules, through the built image, from two places:** the `megasamples` database; and a database the namespace's owner owns, with a relation and a function of the catalog's names planted there and the search path pointing at them. | Each rule removed in turn; the library not loaded; one catalog name left to the caller's search path. | G-4a, G-4b, G-6b and G-29a to G-29d as regressions on the built hook. **A fault planted in rule 3's close, and one in its confirmation: every directory has a catalog row, and a second session cannot connect; by direct SQL and through `copy create`.** Every command that makes a routine, by each kind of creator; a second session that never sees a new database open. |
| T-8 | **The routine floor is the list, for every role, on the candidate.** A fresh role's `SELECT 1 = 1` succeeds, and a routine outside the list is refused it. A routine made in a copy, or in a working copy a reset made, has no `EXECUTE` for `PUBLIC`. A declared writer's insert that fires a dataset's trigger succeeds, and one that reaches a built-in outside both lists is refused. | The list granted to `demo` alone; the event trigger left out of the template; the write list emptied. | `demo`, a fresh role, a namespace's owner, a declared reader and writer; every kind of database; an exported snapshot imported by a second session. Pull request #14's own cases, kept. **8.3 maps each gate that ran on a source or a prototype to its assertion here.** |
| T-9 | **MySQL's grants reach what they name and nothing else.** | One underscore left unescaped; `demo`'s grant on `*.*` restored. | G-11b's and G-11c's cases through the built image. |
| T-10 | **A copy's access is exactly what its engine's design says.** **PostgreSQL:** the copy's database privileges are its owner's and `CONNECT` for its namespace's read group, and nothing else. **MySQL:** the product makes no grant that names the copy's schema. **A grant that was there before, made by hand, is detected and reported as not the product's; if it gives create or drop, the copy is `not-exclusive`, and its drop and its sweep are refused, exit 5, with the schema and the row kept.** | PostgreSQL: a `CONNECT` grant to `PUBLIC` planted in the create. MySQL: the exclusivity check removed, so that the drop goes ahead. | Both engines; a create that is interrupted; a hand-made grant on the exact name and one on a pattern; one that gives `SELECT` alone, which blocks nothing; the grant removed, after which the drop succeeds; `copy show` and `copy list` on a `not-exclusive` copy. |
| T-11 | **A MySQL copy is the dataset:** its own verification passes against a copy (`SM:ARCHITECTURE.md:239-249`). | The foreign keys' replay skipped; one view left pointing at the template. | Every templated database; the marker event present and reported. **The exclusions, each refused with exit 4 before any reservation:** `too-large`, `dependency-group`, and `not-replayable` for a trigger and for a function. **The build's inventory, upstream dumps included, names them, and the README's list is generated from it.** [113-2] **G-13 as a regression, on the candidate and at every engine upgrade** [112-3]: with the log on a trigger and an undeclared function are refused the owner; **each of the three declarations, `DETERMINISTIC`, `NO SQL` and `READS SQL DATA`, is tried as the owner with the log on, under the shipped settings, and either outcome passes** [113-2] [115-3]: a faithful replay, after which that kind is offered; or the engine's refusal, after which every database with that kind is listed with its reason and refused with exit 4 before any reservation, in both log modes. **What fails is an offer of a kind not shown to replay.** a replayed definition reads and writes its copy alone. It fails if the engine's answer changes either way. |
| T-12 | **The contract:** one document; each exit's promise checked on the server; each reader rule. | A second line; a changed code; an unknown member rejected. | Every command by every outcome of 3.3. `--json` with two targets: exit 2. An operation's identity given twice: exit 5. **Exit 6 from a reset, both ways** [115-6]: the early refusal, with no record and `--status` `unknown`; the late one, with `--status` `rolled-back`; in both, the data and every person's session as they were. |
| T-13 | **A reset signs in with the file's value when another is exported,** for its coordinator and for its worker. | Today's reader put back. | Each key; a canary password in no argument, output or log, nor taken from the CLI's environment. |
| T-14 | **An interrupted create is kept, and what is expected depends on where it stopped.** **Killed before the exclusive creation:** there is no object; the row is `stale`; a drop or a real sweep removes it. **Killed after it and before `ready`:** the object is there, `interrupted`, and no command removes it. **Killed after `ready` was written and before the reply: the copy is `ready`, and its caller finds it by its label.** | Recovery made to remove an `interrupted` object; `stale` made to keep its row for ever; a `ready` copy after a lost reply reported `interrupted`. | Each phase, each engine; an occupied name; **it tells PostgreSQL's two failures apart** [115-4]: inside `CREATE DATABASE`, nothing is left and the row is `stale`; in a later step, the comment or the grant with the disk full, the database is there, `interrupted`, and the object and the row are kept (2.6); a `ready` object replaced outside the CLI, kept as `inconsistent`; a MySQL schema made again within the second, without its marker. |
| T-15 | **Every command against every command,** pairs generated from section 0's commands and every reset path and scope. **Its invariants, for each operation:** a sweep removes nothing inside its lease; an owner's own drop may remove its leased copy; no working copy is lost or left closed by a completed command; nothing is present that `copy list` or `reset --status` does not show. | Each guard removed in turn. | Natively, with the first paused at each durable phase; and by gated fakes. |
| T-16 | **A reservation is atomic:** forty creates into a namespace of 32 give exactly 32. | The count taken outside the lock. | Creates that fail and keep their place, as 2.2 has it. |
| T-17 | **A sweep removes only what 2.2 allows:** a copy renewed between its look and its removal is kept. | Each condition removed in turn. | Each reason a copy is kept. **The stated limits:** an idle MySQL session and an open SQLite file, past their lease, shown unprotected. |
| T-18 | **The build reports each template's allocated bytes,** appended datasets included. | The appended tables left out of the measure. | Each templated physical database; a copy's time by each strategy. |
| T-19 | **The reset-recovery table of section 14, whole.** For every path, with the CLI killed at each kill point the table names, each command of its columns gives the answer the table gives: `reset --status`, `reset --reconcile`, a new reset of that target, a whole engine's reset, and `megasamples up`. | Admission made to ignore an unsettled row; any one cell's action changed. | Each path; G-26m's and G-26p's intervals through the CLI; the server restarted, and the host rebooted, at each kill point; the disk filled part-way into a restore and into a load; a second operating-system user running each command after the first was killed. **First in the reset slice (P1-4)** [115-2]: with a SQLite reset unsettled, `megasamples up` is refused and no console starts; a sentinel row committed to the working file after the reset installed it is still there after `--reconcile`, which records `failed` and stages nothing; a record of another volume changes nothing on this one, and a sentinel row there is kept. **The rows DL-115 added** [115-7]: a MySQL worker that survives, against a restart that frees its lock; a mismatch that persists at `loaded`; SQLite on either side of its rename; PostgreSQL killed inside its second-look refusal, and after a terminal write before the reply; a whole engine's volume created and not yet seeded. **Several targets** [115-8]: killed between two targets and during a later one, a second operator tells finished, interrupted and never-started apart by the printed identities and `--status`; a finished target keeps an edit made since; an unstarted one is untouched. Several targets, one of which would be refused: none is changed. |
| T-20 | **A worker changes nothing unless it holds its lock, on the volume, the operation, the epoch and the phase it was started for.** | Lock ownership left out of the guard; the epoch check removed; the client allowed to reconnect. | Both servers. **A MySQL stream that arrives after a reconciliation has taken the worker lock and before it raises the epoch: stopped.** A stream whose session is ended part-way: it does not go on. A PostgreSQL worker that outlives its coordinator: only its own transient. |
| T-21 | **A reset of a database preserves sessions unless told otherwise.** | The default made to disconnect; a console's idle session made disposable; the first look removed. | Each path; a person's idle session, directly and through a console; a connection with the reserved application name. **PostgreSQL, a person there at the start: refused with nothing created and the door never closed, shown by a connection attempted throughout. A person who connects during the build: refused at the second look, the door opened again, the transient removed, `rolled-back`.** `--unattended` on MySQL and SQLite, refused; a MySQL and a SQLite reset without `--discard sessions`, refused. **MySQL with it: a session using the target is ended; a reader's session on another schema, touching nothing of the target, is not; a declared writer's is, wherever it is** [116-2]. `make reset` and every validation script that calls it (F-33), as migrated; a search of the repository for a call that lacks the option its target needs. **Exit 6 early and late, each with its `--status`: `unknown`, then `rolled-back`.** [115-6] |
| T-22 | **Nothing replaces an engine's volume without a fresh `--discard engine`, a stop does not replace it, and an upgrade does not put fresh data into service unasked.** `megasamples down` then `up`, with a live copy and an edited working row: both are there afterwards. A whole engine's reset without the option, and with `--discard sessions`: refused. `megasamples up` with a stale image and a live copy: refused before anything is recreated; with `--discard engine`: replaced. | Either refusal removed; the volume made anonymous again; the escape widened to any operation whose locks are free. | Each engine. Each row of 3.5's start table, by `megasamples up` and by the generated Compose file started directly. **First in the reset slice (P1-1)** [115-W]: a whole engine's reset with `--discard engine` is **refused** over a PostgreSQL restore that outlived its coordinator; over a `closed` operation that reconciling would reopen; over a server that refuses the sign-in; and over a stopped engine. It is **admitted** over an operation durably `failed`, with its locks free and the volume identified, and it names that operation. `up --discard engine` is refused in all five. **First in the reset slice (P1-3)** [115-U]: both upgrade histories, the earlier container present and after the earlier version's `down`, each through both starts, with a committed edit: no start serves fresh data, and each refuses and names what it found. A whole engine's reset killed after the new volume is up: `--reconcile` has nothing to do for it, `--status` says what is there, and nothing is replaced again without a new `--discard engine`; from a second operating-system user as well. A volume that its own replacement created and never seeded: replaced by a fresh `--discard engine`; one of uncertain identity: kept even then [115-7]. A reused `--operation` identity: refused. A `copy` command begun before a replacement: its connection ends, exit 8. |
| T-23 | **No privileged password is published or shown, on any supported start.** **From each route's own upgraded checkout, `megasamples up` and the regenerated Compose file started directly, with a canary planted in the old pages:** the landing page and the connection page, fetched with no sign-in, do not return it. | The value's test removed; a page made to print it; a stale page left in place; the Compose file generated without removing older pages. | G-35p's and G-35m's cases through the built images, on an image run by hand as well [110-2]. **With every privileged MySQL account locked, the start still applies each configured password and each declared account, and `demo` signs in:** its maintenance runs through the server's init file and signs in as nobody (`SM:engines/mysql/entrypoint-wrapper.sh:7-30`). **This test is where that is shown; no gate showed it.** [115-5] The start naming each account still on its published password; a privileged key set to the published value, leaving its account locked; `megasamples up` writing each missing key; no console offering anything privileged; no configuration making the generator publish a port wider than loopback. |
| T-24 | **SQLite copies:** a truncated copy is not published; a replaced file is not dropped; adjacent files are left and reported. **A drop killed between setting the file aside and comparing it: the next `copy drop` finds it aside; the copy's own file is removed; a foreign file is put back or kept, and reported.** | The hash check removed; the move-aside removed; the aside path recorded after the rename. | Create, drop, sweep; a manifest that disagrees; a sidecar one format back, kept; `copy show` and `copy list` while a file is aside, which move nothing. |
| T-25 | **Passwords:** PostgreSQL refuses `demo`'s change of its own. MySQL: what G-16 established, as a case that fails if the engine's answer changes: each of the four statements changes it. | Rule 4 removed. | Each account without `CREATEROLE`; a cleared key locking its account at the next start. |
| T-26 | **`oracle_hr` and `oracle_oe` are not reset singly on MySQL.** [109-4] **First, on today's path, it shows the harm:** a row added to `oracle_oe`, then `oracle_hr` reset alone, leaves a key with no parent. Then: the reset is refused, exit 4, and after a whole engine's reset every key holds. | The refusal removed. | A MySQL with both; one with `oracle_hr` alone, which is refused the same. |
| T-27 | **A MySQL reset is `done` only after a verified load, through the real reset command.** [111-1] With the data volume filled during the load: the reset ends unsettled, exit 8, recorded `failed`, **never `done`.** After space is freed, reconciling ends `done`, with the image's counts and checksums and the readers' grants, and then `restored`. | An unconditional `done` put back. | A load that fails for each reason: a full disk, a killed stream, one table that differs afterwards. The write of `failed` itself refused, leaving `loading`. The next reset of that target refused meanwhile, exit 5 [113-3]. **First in the reset slice (P1-2)** [115-1]: an ordinary account is given a write grant on the target by hand, and is shown to write through it. The reset is then **refused at admission, exit 5, naming that account, with no record written, no session ended, and the target's data and grants intact.** The same for a grant by pattern, a global one, and one through a role; and for a privilege that cannot be determined. With the grant withdrawn, the reset succeeds. Paused between the verification and `done`, a fresh session of each account the product makes, a declared writer among them, is refused a write to that schema (T-33). A grant an administrator makes after admission is the stated limit. SQLite's reset, the same way. |
| T-29 | **The general upgrade route, rehearsed as the README gives it** [115-U]: before the earlier version's `down`, each engine's volume identified and kept; the images replaced; an edit verified; and back by the kept volumes. | A step removed from the route: its test fails. | PostgreSQL's refusal of data without the policy's marker. **An install that cannot be told from a first one:** the route's first step is what keeps its data. **An engine that will not start:** recovered by this route, which the CLI's reset refuses [115-W]. |
| T-30 | **Each volume has an identity of its own.** The MySQL image holds no `auto.cnf`, as an image test [111-2]; two fresh volumes report different identities, and each keeps its own across a restart. | The removal taken out of the build. | PostgreSQL's value and SQLite's file, the same way; `megasamples up --discard engine` and a whole engine's reset, after which the identity is another; a reset of one database, after which it is the same. |
| T-31 | **A command that only looks changes nothing.** `copy show`, `copy list`, `copy sweep --dry-run` and `reset --status`, against a copy in every state of 2.2 and a target at every kill point of section 14: every row, object, lease, file and phase is the same afterwards. | `show` made to finish a `dropping` copy; a dry run made to remove a `stale` row. | Each engine; each state; a SQLite file set aside; an unsettled and a `failed` reset. |
| T-32 | **The service's SQLite working files keep a committed edit.** A sentinel row, written through the documented client, is read back after a restart of the generated service, after a reboot's restart, and after `down` then `up`; and a console reads it. **A reset of that database removes it; a reset of another does not; a replacement given `--discard engine` removes them all.** | The start made to copy the image's files over the volume. | Each working file; a file deleted by hand, which the next start seeds again; a stale image, which `up` refuses and does not reseed. **With a reset of a working database unsettled:** `megasamples up` starts no console, and a row committed since is kept by `--reconcile` [115-2]. |
| T-33 | **A declared writer cannot change a MySQL database from its reset's first change until `done`, and has its grant back only after.** [116-2] **First in the reset slice, three cases.** **A declared writer reconnecting at each step:** after `suspended`, during the load, after `loaded`, and after `done` before `restored`, a fresh session is refused the write each time; after `restored` it writes. **A regrant failing after `done`:** the command reports the writer, exit 8; `--status` says `done` with that writer still suspended; `--reconcile` restores the grant, and neither loads nor verifies again. **A session ended mid-transaction:** a declared writer has a transaction open on the target when the reset begins; its session is ended, its transaction is rolled back, the drop does not wait on it, and none of its rows is in the verified data. | A grant restored before `done`; the writers' sessions left open after the revoke; the restore step made silent when it fails. | Each declared writer; a writer whose session is on another schema, ended too, as the consent says; the server restarted at each step, the writer still out [G-27b]; the start leaving the grant out until `restored`; a reset that ends `rolled-back`, which gives the grants back first; a declared writer that also holds a hand-made grant, which refuses the reset [115-1]. |
| T-28 | **The package installs with the two drivers alone,** on each supported Python, and `uv sync --locked` is unchanged. Psycopg's licence is reviewed first. **The PostgreSQL client also needs the system's libpq;** without it, exit 3 `client-library`. | A pipeline dependency imported by a `copy` module; the libpq guard removed. | One `copy list` from that install, with no container runtime, on the oldest supported Python. |

### 8.3 Every claim traces to a test

**The rule.** [114-4] **Before the merge, every sentence of this record and of the README that says what the product does, refuses or keeps is traced to a passing test that drives the real commands:** `megasamples …`, the generated Compose file, the image's own start, or SQL sent as a named account. A sentence with no such test is removed, or reworded to what a test shows.
- **The build keeps the trace beside the tests:** the claim, by section and sentence; the test; the command it drives.
- **Not yet claimed for the slices 1 and 2 build** [build round 2]. These have no passing test through the real commands yet, so the build does not claim them, and the merge waits for each:
  - T-11's dataset verification (`megasamples verify`) against a copy of each offered database;
  - T-15's command-against-command pairs and the kill points;
  - G-9 and T-14's full disk on the copy paths;
  - the account-by-database matrix beyond the cases in `tests/test_v1_server_copy.py`, `tests/test_v1_postgres_policy.py` and the native strict-read suite.
- **A gate's result is evidence about an engine. It is not such a test.** A gate that ran on a source or a prototype says so, and has a row below.
- **An amendment the build needs lands in this file with its code and its reason.** One that adds to section 0 returns to the deciders first.

**From a gate's result to the candidate's assertion.** [D: review 5's finding 14.]

| Gate, and what it ran on | What it showed | What the candidate must show, and its reversal | Test |
|---|---|---|---|
| **G-5a,** pull request #14's policy source | A fresh role is refused `SELECT 1 = 1`. | **The opposite:** with P-1 the statement succeeds for a fresh role, and a routine outside the list is refused. Reversal: the list granted to `demo` alone. | T-8 |
| **G-2c,** the same | A copy carries the extension and its event trigger. | A routine made in a copy, and in a working copy a reset made, has no `EXECUTE` for `PUBLIC`. Reversal: the event trigger left out of the template. | T-8 |
| **G-5b,** the same | The three built-ins change nothing, and a snapshot is imported by another session. | A fresh role exports a snapshot and a second session imports it. Reversal: one of the three taken off the list. | T-8 |
| **G-5c,** the same | A trigger's body runs with the writer's rights. | A declared writer's insert that fires a dataset's trigger succeeds; one that reaches a built-in outside both lists is refused. Reversal: the write list emptied. | T-8, T-6 |
| **G-4a, G-4b,** stock engine and a prototype | A revoke that does nothing; an orphan after a raise. | On the built hook, with a fault planted in the close and in the confirmation: no orphan, and no second session connects. Reversal: the fail-closed step removed. | T-7 |
| **G-6b,** a prototype | Rule 4 refuses the three statements. | The same on the built hook. Reversal: rule 4 removed. | T-7, T-25 |
| **G-29a to G-29d,** a prototype, from one database | Rule 2's four parts. | The same on the built hook, from the `megasamples` database and from an owner's own. Reversal: one name left to the caller's search path. | T-7 |
| **G-35m,** stock engine | Locked accounts are refused on each way in; `demo` signs in. | With those locks, the start's own maintenance still applies passwords and declared accounts. Reversal: the maintenance made to sign in as `root`. | T-23 |
| **G-33a,** a fixture image | Without `auto.cnf`, each volume has its own identifier. | The product's own image holds none. Reversal: the removal taken out. | T-30 |
| **G-13,** stock engine | An undeclared function is refused the owner with the log on. A declared one was not shown. | Each of the three declarations is tried as the owner, log on, shipped settings. A replay offers that kind; a refusal withholds it, with exit 4 before any reservation. [115-3] Reversal: a kind offered that was not shown to replay. | T-11 |
| **G-26m,** raw sessions | Five intervals. | The interval between a reconciliation's lock and its epoch. Reversal: lock ownership left out of the guard. | T-20 |
| **G-9,** stock engine | Failures inside `CREATE DATABASE`. | A failure of a later step, and of a restore part-way. Reversal: every failed create classed `stale`. | T-14, T-19 |
| **G-24w,** raw sessions | No outside account can replace a copy. | An account with a hand-made grant can, and the drop is refused. Reversal: the exclusivity check removed. | T-10 |

## 9. Pull request #14, and the order of the work

- **Pull request #14 is folded into this work's branch.** It is not rebased, and its content does not reach `main` by itself. [D]
- **How.** The branch starts from `main` and merges `fix/strict-read-account` at `2879fc4` first. It merges without conflict (F-15).
- **Each of DL-085's conditions keeps its disposition** (F-26) [D: review 4's finding 17]:

  | DL-085 asks, before it merges | Where it is met |
  |---|---|
  | C1 passed against its candidate | 7.2, step 7 |
  | The other roles settled | 4.2, P-1; 4.6 |
  | **Its allow-list reconciled with DataIntent's own routine inventory (IA-01)** | 7.2, step 7: recorded, signature by signature. The product's published inventory (P-7) is one side of it, not a substitute. |
  | **One independent review, of the compiled hook and of the `SECURITY DEFINER` event trigger** | 7.2, step 8: both named in its record. 4.3 is its input. |
  | The account model designed with the templates | section 4 |
  | Permissions kept through template creation, a copy and a reset | G-2a to G-2d; T-5 |
  | Unmerged until the first cutover is accepted | 7.2, step 6 |

- **Its tests are not loosened.** A changed expectation is a test-only change of its own, saying why. Its native guard is replaced by 8.2's entry point (F-14).
- **Its evidence is made again** for the final candidate; the earlier receipts remain in history at `2879fc4`.
- **The credentials, consoles and pages change** (5.1) may be its own pull request, merged before the build. [108-5]
- **Carried on the same branch:** the ten notes that pull request #16's review left for the next pull request, C-1 to C-10 (`DI:docs/work/megasamples-pr16-review-loop.md:17-27` at `d02f7384`). [R]

## 10. What the README must document

For DL-078's writer, before the merge. **The README describes the product.** A deployment is an example.

**What DL-078 itself asks** (F-27):
1. **It leads with the project's purpose:** one place to go for fast access to sample data across many technologies.
2. **The LTS engines and the clients,** at the versions the build pins.
3. **The datasets:** which there are, on which engines, with a matrix.
4. **The configuration and the `.env` passwords, and where to find them.**
5. **The general upgrade route** (5.3), **step by step** [115-U]: before the earlier version's `down`, how to identify each engine's volume and keep it; how to verify an edit afterwards; how to go back. **That it is also the route for an engine that will not start** [115-W].
6. **Visuals where they help.**

**What version 1 fixes:**
7. **The model, with a picture:** a template, a working copy, a test copy and a reset; and how the three engines differ, MySQL's reset from the image among the differences.
8. **Which databases have a template,** per engine, with measured sizes and times; **each MySQL database that has none, by name, with its reason** [112-2]: too large; a dependency group; or triggers, whose replay the engine refuses a copy's owner while the binary log is on, the one setting that lifts it being deprecated (warning `1287`); that version 1 bounds no storage, and what it promises when a disk fills (2.6).
9. **Namespaces:** what a prefix is, why it may not overlap, a foreign namespace.
10. **A copy's life:** issued, ready, leased, renewed, released, swept. That an interrupted create is kept, and how an administrator removes one. That the lease is the protection, and the two cases past it. **That a MySQL copy holds one marker event.**
11. **The commands,** each with one example and its JSON; the identity on `drop`, `renew` and `release`.
12. **The exit codes,** both tables, and what a script does on 8.
13. **Credentials:** the two routes for `copy`; the keys; that privileged passwords are private and where `megasamples up` writes them; what a console and a page show.
14. **The accounts,** as 4.7's tables. It replaces today's two-row tables (`SM:README.md:120-123`, `:247-255`).
15. **Declared readers and writers.**
16. **The read profile on PostgreSQL,** and its limit. It replaces the sentence that `demo` "still has `TEMPORARY`" (`SM:README.md:163-167`).
17. **5.1's table of start paths, and 5.2's table, whole.** **For an image run by hand: anyone who can reach its port can read the samples as `demo`.** [110-1] How to hand a credential over: one, alone, never the `.env`. [108-11]
18. **The impact note of 5.4, whole,** with each migration.
19. **What is not claimed:** that anything started before a volume's replacement cannot act after it, which is why other callers are stopped first; recovery of a whole engine's reset that was interrupted; a MySQL copy of a database with a trigger, or with a function of a kind not shown to replay; **that a `CREATE DATABASE` which fails for want of a resource, or a crash, leaves no file behind** [113-4]; a sweep protecting a copy past its lease; that a copy has had one writer; a copy owner's credential away from the service before its gates; any bound on storage; a wider listener, or any refusal of one on an image run by hand; MySQL as a strict read profile; MySQL refusing a password change; the volume identity of a MySQL volume from an older image; TLS.
20. **Starting and stopping:** what `up`, `down`, a restart and a reboot each do with the data they find (3.5's table); that the service's SQLite working files keep an edit; that the Compose file is generated again after an upgrade. **Resets:** that a MySQL reset suspends the declared writers and ends their sessions before it changes anything, and gives their grants back only after `done` [116-2]; that it is refused while any other ordinary account can write its target, until that grant is withdrawn or the whole engine is reset [115-1]; that an interrupted SQLite reset keeps the consoles down until it is reconciled [115-2]; each path and its option, the session decision, `--discard sessions` and `--discard engine`, operations and their identities, one target for each scripted call, `--status` and `--reconcile`.
21. **The contract and the formats.**

**What leaves the README:** the dated account of one deployment (`SM:README.md:16-20`) and the paragraphs that take LAN forwards for granted (`:258-270`). [108-3]

## 11. What waits, and in which stage

Each is new work with a brief of its own, added under section 6's rules. [108-4] [108-6] The fuller design at `e0c2f935` is the source for each.

**Every deferred finding is listed against its stage, by review and number,** so that the lines register can carry it. [D: review 4's finding 21.] "R3-14" is review 3's finding 14. **The register is DataIntent's file, not this record's:** it carries this table by a pin to this section at the commit it cites (review 5's finding 21).

| Stage | What waits in it | DL-108 | Deferred findings |
|---|---|---|---|
| **S-1 · Exposure** | `network.bind`, `administrators.allow_from`, `whoami`. The approved default that a wider listener is refused while an account keeps a published password, or until administrators' origins are set, and that a console with stored administrator access or anonymous use is refused a wider bind. The profiles of a shared server, a container platform and remote access. A map from account keys to mounted secret files. | 2 (a), 6 | **R3-1** (the wider-listener check); **R3-2** (wider publication of a console); **R3-14** (the map to mounted files); **R4-10** (what is enforced on an image run by hand); **R2-13** (origins for administrators) |
| **S-2 · Enrollment at run time** | The enrollment commands, their record, its replay and its repair. `accounts check`. A writer of a copy that is not its owner, and the per-run writer boundary a result would need. | 6 | **R3-6** (repair during a reset); **R3-10** (a per-run writer boundary); **R3-17** (one authority for run-time enrollment); **R2-7** (the grant audit); **R2-8** (admission of an existing role by its effective privileges); **R4-16** (effective write access to a copy, established by the product) |
| **S-3 · Storage admission** | Headroom reserved across an engine; a recovery reserve; inputs for an image reset, an off-host file and a retained log. | 6 | **R3-15**; **R2-12** (admission across namespaces) |
| **S-4 · A remote image worker** | A reset asked for from anywhere but where the service runs. | 6 | **R3-13** |
| **S-5 · `copy hold`** | Holding a copy past its lease; a holder's own identity; protection of active copies, holds and sessions across a replacement of a volume, with a drain; **a guarantee that nothing started against one volume acts on the next; phases and reconciliation for a whole engine's reset.** | 8, 9; DL-114 item 2 (A, B) | **R3-5** (protection and drain); **R3-11** (a drop against a hold); **R2-9** (the hold's handshake); **R5-3** (a late worker's volume); **R5-10** (recovery of a whole engine's reset) |
| **S-6 · MySQL's reset from a template** | The reset itself; a group of databases that refer to each other, reset and recovered as one; an unattended route for MySQL. | 10 | **R3-6** (the template path's exclusion); **R3-16** (a group's recovery); **R2-11** (definers restored on a reset); **R4-20** (a reset of one of a group without the whole engine); **R5-20** (`oracle_hr` installed alone) |
| **S-7 · `accounts export`** | One credential handed over with a value-free receipt; an optional custody record. | 1, 11 | — |
| **S-8 · MySQL copies of databases with triggers** | **A ready addition, not a design to be made** [112-3]: `log_bin_trust_function_creators` in the shipped configuration, or whatever replaces it, with an image test that the server starts with it and reads it back in both log modes; the withholding kept as the fallback. **Its evidence is G-13's re-run** (`GR:144-148`): with the setting, a trigger, a function and a procedure replayed in both log modes, with source and copy apart and no grant changed. | DL-111 item 3; DL-112 | **G-13** (the first run's failure) |

## 12. What the gates changed, and the reviews' findings

**Review 5 is of round 6** (`84d2c96`). Its 21 findings have their dispositions in 12.1, under the bar of section 13. Round 5 itself had no review: the gates ran on it.

### 12.1 Review 5's findings, each with its disposition

**One row for each finding, in the form DL-114 item 1 asks:** who does it, through which supported entry point, on what precondition, with what outcome that can be observed; the nearest realistic route through the same mechanism, by its row in section 13; and then one of three: **fix**, **narrow**, or **a stated limit** with what would reopen it.

| # | Finding | Actor, and supported entry point | Precondition, and observable outcome | Nearest realistic route (section 13) | Disposition | Where; reopened by |
|---|---|---|---|---|---|---|
| 1 | **P1 · A failed privilege check can leave a database open.** | Anyone who creates a database: `admin` or a consumer's role by SQL, a namespace's owner through `copy create`. | Rule 3's close leaves `PUBLIC` able to connect. Another reader enters the new database. | **RT-12,** a creator without the owner's rights: the one cause a gate showed [G-4a]. | **Fix.** The close uses the server's rights, not the creator's. A database not confirmed closed is closed to every connection. Both outcomes are asserted on a planted fault, by SQL and by the CLI. | 4.3; T-7. Reopened by: a caller's input or privileges that makes the last step raise, which returns to the deciders [113-4]. |
| 2 | **P1 · The confinement prototype trusts the caller's name resolution.** | A namespace's owner, on purpose, by SQL from a database it owns. | Its search path puts its own relation before a catalog. A copy is made outside its namespace, or from an unregistered template. | **RT-12:** this boundary exists against its credential's holder, so that is the realistic route. | **Fix.** The built hook resolves every name itself. The four confinement cases run from an owner's own database with shadowing objects planted. No PostgreSQL copy is issued before that passes. | 4.3; T-7; 8.3 |
| 3 | **P1 · G-33b does not establish the late worker's volume.** | An operator who replaces an engine while a reset of it has not ended. | An old worker meets, on the new volume, an operation of the same identity and epoch, or a transient of the same name. It writes into the new volume. | **RT-8 with RT-13:** a reset that seems hung, answered by resetting the whole engine. | **Narrow (A), as ruled** [115-W]. The guarantee is not claimed. A replacement is refused while a reset there is running, unsettled or unreadable; a restore that outlived its coordinator, and a stopped engine, are among those. One escape: every unsettled operation durably `failed`, the volume identified, the locks free, a fresh `--discard engine`. | 3.5; section 14 (EN); T-22, T-19; S-5. Reopened by: a worker seen to write after a replacement in T-22's runs; or the guarantee being wanted, which is S-5. |
| 4 | **P1 · The MySQL stream can pass its epoch check without the worker lock.** | An operator who reconciles straight after a reset was killed. | The killed reset's stream arrives after the reconciliation has the worker lock and before it raises the epoch. Two loads run into one schema. | **RT-10 with RT-13 and RT-14:** a kill followed at once by `--reconcile`, perhaps by a second operator. | **Fix.** One guard statement requires lock ownership, the volume, the operation, the epoch and the phase. The client never reconnects. That interval is exercised with a pause. | 3.5; T-20 |
| 5 | **P1 · A MySQL writer can change verified data before `done`.** | A declared writer, from a fresh session, by SQL. | Its grant is back before the terminal row. A committed write lands between verification and `done`. | **RT-12 with RT-7, and RT-18:** a consumer that writes while a reset finishes. | **Fix** [116-2] [115-1]. A declared writer is suspended before the reset's first change, by a revoke and the ending of its sessions, and its grant is restored only after `done`, as a recorded step. Any other ordinary account that can write the target, or one that cannot be determined, refuses the reset at admission. **Stated limit:** a grant an administrator makes after admission. | 4.6; 3.5; section 14 (MY); T-33, T-27. Narrowing C is reversed by the owner (DL-116). |
| 6 | **P1 · A retained MySQL grant invalidates the deletion proof.** | An account that an administrator granted create and drop on a namespace's names, by SQL; and the owner's `copy drop` or sweep. | The grant's holder replaces the schema between the marker's read and the drop. The CLI removes a schema that is not the copy. | **RT-12:** an administrator giving a second account "everything on `copy_%`" is an ordinary thing to do. | **Fix, by refusing.** Before a removal on MySQL the CLI establishes that nobody but the owner holds create or drop there by such a grant. Otherwise the copy is `not-exclusive`: kept, reported, and not removed until the grant is gone. | 2.2; T-10; 8.3. **Stated limit:** the owner itself, and an administrator, can still defeat the proof. |
| 7 | **P1 · A supported start can still serve the old administrator password.** | An upgrading operator, by `megasamples up` or by the generated Compose file. | The checkout holds pages an earlier version generated. A visitor with no sign-in reads `admin`'s password. | **RT-4 and RT-5,** exactly. | **Fix** [114-7]. The Compose file and the pages are generated in one step that removes older pages. Both routes are tested from their own upgraded checkout with a canary. **Narrow:** a Compose file from an earlier version is not a supported start. | 5.1; T-23. Reopened by: any artifact of the current version that serves an older page. |
| 8 | **P1 · A missing container is treated as a first installation.** | An operator, by `megasamples down` then `up`. | The containers are gone. A fresh volume is attached; copies and edits are no longer in the service. | **RT-2,** exactly. | **Fix (F), on every detectable history** [115-U]. Named volumes; a start is decided by the volume. Wherever an earlier deployment is detectable, both starts refuse before serving fresh data; the Compose file creates no volume. **Stated limit:** an install that cannot be told from a first one, for which the README's upgrade route keeps the data. | 3.5 (U-1 to U-5); 5.3; T-22, T-29. Reopened by: a way to tell such an install apart. |
| 9 | **P1 · SQLite's real replacement path differs from the one tested.** | A person who edits a working database; an operator who restarts. | The start copies the image's files over the working files. The edit is gone. | **RT-3,** exactly. | **Fix** [114-2]. One set of working files, seeded only when absent, kept across a restart, a reboot and `down` then `up`. A reset reseeds one; a replacement reseeds all and renews the identity. | 2.5; 3.5; T-32, T-30 |
| 10 | **P1 · Whole-engine recovery can discard a replacement twice.** | An operator, and a second operator on the same host, by a whole engine's reset and what follows its interruption. | It died after the new volume was up. A recovery replaces again; or two operators hold two locks. Edits on the new volume are lost. | **RT-8 with RT-10 and RT-14.** | **Narrow (B), and fix the lock.** No phases and no reconciliation; each replacement needs a fresh `--discard engine`. The lock is the deployment's, not the user's. | 3.5; section 14 (EN); T-22; S-5 |
| 11 | **P1 · SQLite drop can lose track of someone else's file.** | A script's `copy drop`, killed; and whatever put a file under the name. | The process dies after setting the file aside and before comparing. The next command calls the copy `gone` and removes its record. A file is left hidden. | **RT-9 with RT-10:** the same kill with the copy's own file aside, which leaks it the same way. | **Fix.** The sidecar records where the file goes before it is moved. Recovery looks there first. A foreign file is put back or kept, and reported. | 2.2; T-24, T-31 |
| 12 | **P2 · G-13 leaves an unproved class on the offered side.** | A script, by `copy create` on a MySQL database with a function. | A function that declares a characteristic was never shown to replay as the owner with the log on. The copy fails part-way and is left `interrupted`. | **RT-9,** exactly. | **Fix** [113-2] [115-3]. A database is offered only for kinds shown to replay. Each function declaration is tried on the candidate, and both outcomes are correct: offered if it replays, withheld if the engine refuses. The list comes from the build's inventory. | 2.4; T-11; 8.3; section 10 |
| 13 | **P2 · G-9's result is generalised across failure points.** | A script or an operator, with the disk full. | A step after `CREATE DATABASE` fails, or a restore fails part-way. The object is there, and the record says `stale`. | **RT-11,** exactly. | **Fix.** The state comes from the durable phase and the observed object. Both later failures are run through the real commands. Section 12.2's summary of G-9 says only what the gate saw [115-4]. | 2.2; 2.6; 3.5; 12.2; T-14, T-19 |
| 14 | **P2 · The candidate cannot repeat every policy-source gate.** | The builder and the reviewers, by T-8 and T-23. | A regression copies G-5a's expectation and fails on the corrected candidate; or leaves out G-2c, G-5c and the start's maintenance. | Not a route of the product: a defect of the test plan. | **Fix.** 8.3 maps each such gate to its candidate assertion and reversal. G-5a's row says what it is a result of. The start's maintenance with locked accounts is attributed to T-23, not to G-35m [115-5]. | 8.1; 8.3; 5.1; T-8, T-23 |
| 15 | **P2 · The session refusal promises more than the sequence delivers.** | Automation with `--unattended`; a person at a console; a writer on another schema. | The transient is made and the door closed before the refusal. On MySQL a connection is ended that was not on the target. | **RT-15 with RT-7.** | **Fix and narrow.** A first look before anything is made. Exit 6 promises the data as it was and no person's session ended; the early and the late refusal each have their `--status` [115-6]. What `--discard sessions` consents to is stated by engine. | 3.3; 3.5; T-12, T-21 |
| 16 | **P2 · The copy state table authorises mutations from read-only commands.** | A script, by `copy show`, `copy list` or a dry run after a crashed drop. | A command asked only to look finishes the deletion. | **RT-9 with RT-10.** | **Fix.** Classification is apart from recovery. Only a drop of that copy or a real sweep recovers. | 2.2; 3.1; T-31 |
| 17 | **P2 · `working` can mean two grant scopes.** | A deployer, by the configuration. | A namespace named `working`. A reader's scope `working` exposes other data than was meant. | **RT-16.** | **Fix.** The prefix is reserved. | 2.1; T-3 |
| 18 | **P2 · DataIntent's account-manager check has a time but no required result.** | DataIntent's coordinator, by sending a credential. | The check was made and found that `di_admin` can alter the owner. The credential is sent anyway. | A consumer's own procedure; not a route of the product. | **Fix,** in the profile: a recorded refusal for both kinds of account. | 7.2 |
| 19 | **P2 · Three acceptance rows reject a valid outcome.** | The builder. | A correct build fails T-10, T-14 or the sign-in check. | A defect of the test plan. | **Fix.** Each case has its own expectation. | T-10, T-14; 7.2 |
| 20 | **P2 · T-26 freezes an exception absent from DL-109.** | An operator, by `megasamples reset mysql:oracle_hr`. | Only `oracle_hr` is installed. Round 6 let it reset singly; DL-109 does not. | **RT-7.** | **Narrow, to the decision as recorded:** both are refused by name. **Stated limit:** `oracle_hr` installed alone is refused though nothing would break. | 2.6; 5.4; T-26; S-6. Reopened by: a deployment that installs one alone and asks; the deciders then record the exception. |
| 21 | **P3 · The lines register lists stages without their findings.** | A maintainer, opening a stage from DataIntent's register. | The register names the stages only. | Not this record's file. | **A stated limit of this record:** it cannot write the register. Section 11 is the stable table, and the register pins it. | Section 11. Closed by the coordinator, in the register. |

**The readings round 7 applied.** Astra accepted 2, 4, 5 and 6. The deciders ruled on 1 and 3 (DL-115), and round 7's own readings of those two are withdrawn.
1. **A replacement while a reset is unsettled: ruled.** [115-W] It is refused while anything there is running, unsettled or unreadable. The one escape is for operations durably `failed` (3.5).
2. **"Version 1 rejects declared writers on MySQL": overtaken.** The owner reversed narrowing C [116-1]. A declared writer is made on both servers (4.6).
3. **A retained MySQL write grant: ruled.** [115-1] It is not a stated limit. The reset is refused at admission while an ordinary account can write its target (3.5).
4. **An image starts only on data it seeded.** This is new: it is how a direct Compose start "refuses safely" on stale data, and it makes MySQL match what PostgreSQL's policy marker already did (3.5).
5. **One set of SQLite working files.** The review named the volume; this record also folds in the container's own `/data`, which `down` discards today (2.5).
6. **Finding 20 is narrowed to DL-109 as recorded,** which undoes round 5's answer to review 4's finding 20.

### 12.2 What the gates changed

Every conditional sentence about a gate is now a statement of what it showed, and **[G-n]** marks an observation. Beyond that:

| What was observed or decided | What changed in this record | Where |
|---|---|---|
| **G-13:** with the binary log on, the engine refuses a namespace's owner a trigger (`1419`), and a function that declares no characteristic (`1418`). DL-111 item 3; DL-112. | No MySQL copy of a database that needs either: exit 4, `not-replayable`, before any reservation or change, in both log modes. The setting that lifts it stays unset. The README names the databases and the reason. G-13 is kept as a regression. The lift is a ready addition. | 2.4; 3.3; 7.2; T-11; section 10; S-8 |
| **G-17b:** the failure was the test's own write of `done`. A small row write succeeds on a full disk. DL-111 item 1. | **`done` is written only after a verified load,** with counts, checksums and declared grants matching. A load that fails is recorded `failed`, which is not terminal: the operation stays unsettled, exit 8, and reconciling completes it. **T-27 is now that regression,** through the real reset command, as DL-111 names it; the upgrade route's rehearsal, T-27 in round 5, is T-29. | 3.5; 3.3; 2.6; T-27, T-29 |
| **G-33a:** today's MySQL image bakes `auto.cnf`. DL-111 item 2. | The build removes it after its final shutdown, with an image test. `volume` is an opaque string. A volume from an older image is unqualified for the identity rule. | 2.4; 3.5; 5.3; F-34; T-30 |
| **G-16:** MySQL has no account-local refusal of a password change; the two global settings that refuse it also refuse version 1's own writes. | Version 1 takes the branch round 5 set for "no usable refusal": it says MySQL cannot refuse it, and limits the harm. A consumer's instance declares a reader for each consumer and gives `demo` a key of its own. | 4.5; 5.2; 7.2; T-25 |
| **G-4b:** an error after the copy orphans the copied files. H-3 is reproduced. | H-3's resolution is no longer conditional. It is set out, and required before the merge. | 4.3; T-7 |
| **G-5a, G-4a, G-6a:** H-1, H-2, and H-6 with H-7 are reproduced. | Each is stated as shown, with its disposition unchanged. | 4.3 |
| **G-9:** PostgreSQL answered a full disk once with its disk-full code and once with an internal error; it left nothing of the new database in the catalog. | No engine error code is relied on. **What the gate saw is a failure inside `CREATE DATABASE`:** nothing is left, and the row is `stale`. A failure in a later step leaves the database there: `interrupted`, with the object and the row kept, as 2.6 says. A failed MySQL create leaves an `interrupted` schema. [115-4] | 2.6; T-14 |
| **G-27a:** after a revoke alone, a session already open still wrote. | Both steps of the suspension are needed, and both are made. [116-2] | 3.5 |
| **G-32a, G-32b:** only the reserved name tells the product's session; no console holds a session with nobody there; a connection a person opened stays open. | The default stands. The record says a reset refuses while such a connection is open. | 3.5 |
| **The H gates ran on a prototype; G-2c and G-5a to G-5c on compiled policy sources.** | Each is repeated on the candidate, as T-7 and T-8, before the claim it carries is made for a build. | 8.1; 3.1; 7.2, step 5 |
| **DL-109, DL-110:** the three readings; an image run by hand. | The readings are cited as decisions. An image run by hand is documented, not refused; every start names each account still on its published password; there is no acknowledgement switch. | Section 0; 5.1; T-23 |

**The deciders confirmed round 6's four readings** (DL-113):
1. **4.5's branch after G-16:** no usable refusal; DL-106's fallback applies. [113-1]
2. **The withholding covers a stored function refused with `1418`,** with the condition that a characterised function is shown before any database with a function is offered. [113-2]
3. **`failed` is not terminal.** [113-3]
4. **H-3's remaining exposure goes to the independent hook review,** with the limit accepted in advance and what returns to them. [113-4]

**Not settled here:**
- **The exact file list of the runbook's split** (5.3).
- **Every regression of 8.2.** None has run; each is the build's.

### 12.3 Review 4's findings, each answered

| # | Finding | What changed | Where |
|---|---|---|---|
| 1 | **P1 · The landing pages still disclose the administrator credential.** | Neither generated page prints a privileged password, and neither generator reads one. `megasamples up` removes pages generated before. T-23 fetches both pages with no sign-in and looks for a canary. | 5.1; F-31; T-23 |
| 2 | **P1 · G-26m starts too late.** | The coordinator holds the target's lock from before admission until after the outcome is written. The worker holds a second lock, and is fenced by an epoch that a reconciliation raises first. Admission and reconciliation need both locks. G-26m rehearses five intervals, each with the coordinator killed, the worker killed and the server restarted. G-27b adds the restart to the suspension. A failure withholds MySQL's reset of one database. **Rounds 7 and 8:** the worker's fence became one guard statement (12.1, finding 4); the suspension is DL-116's protocol, with no grant restored before `done`. | 3.5; G-26m; T-19, T-20, T-33 |
| 3 | **P1 · The PostgreSQL image worker has lost its gate.** | G-26p is back: a database with no template, the lock holder killed while `pg_restore` runs, a reconciliation and a second admission raced against it, and the working database and both transients verified. A failure withholds the reset from the image. | 3.5; G-26p |
| 4 | **P1 · G-33 never tests a command crossing the replacement.** | G-33b pauses a client between its read and its change, replaces the volume, starts a worker late, and then reads the new volume for any change. **Round 7 withdrew the claim that nothing can cross** [114-2A]: a replacement is refused while a reset is running or unsettled, other callers are stopped first, and the checks stay as checks. The service's SQLite files carry an identity file in their volume; a caller's own SQLite directory belongs to no volume, and its documents say null. | 3.5; 2.5; 3.2; G-33a, G-33b; T-22 |
| 5 | **P1 · A retained command can replace a whole engine without the discard decision.** | `megasamples up` replaces nothing when an image is stale: it refuses, exit 5, before it recreates anything, unless it is given `--discard engine`, as the deciders settled it. T-22 runs it with a stale image and a live copy. | 3.5; 5.3; 5.4; F-32; T-22 |
| 6 | **P1 · The cleanup gates do not establish identity at deletion.** | MySQL's proof by creation times is withdrawn, for a marker event made first in the schema, which a schema made again in the same second lacks (G-24m). PostgreSQL's reset records the working copy's own OID at admission and drops the old transient only by it. SQLite's drop moves the file aside before it compares, so what is compared is what is removed; adjacent files are left and reported. G-24w tests the boundary itself: who can put another object under the name between the check and the drop. | 2.2; 3.5; G-24p, G-24m, G-24w, G-19b; T-14, T-24 |
| 7 | **P1 · G-32p cannot tell a person's idle console session from the product's.** | Only a session that carries the product's reserved application name is ended without the option. Every other session, a console's included, is a person's and is preserved. G-32a tests a person idle through a console beside such a connection; G-32b tests whether consoles hold sessions with nobody there, which would return to the deciders. | 3.5; G-32a, G-32b; T-21 |
| 8 | **P1 · A declared reader's key can be a superuser's key.** | The whole inventory of derived keys is checked when the configuration is read: no two alike, and none one of the five reserved. T-3 tries `mysql_root` and `mysql_demo`. | 3.4; 4.6; T-3 |
| 9 | **P2 · The confinement gates have the wrong boundary and incomplete controls.** | G-29 is four: destination, source, rename, and that nobody else is bound; each refusal has a successful control beside it, and each isolates one cause. A failure withholds PostgreSQL copies altogether, not only their use from elsewhere. **The restriction on other creators is removed:** rule 2 binds a namespace's owner only. G-11b now creates, fills and drops inside its pattern before it is refused outside. | 4.3; G-29a to G-29d; G-11b |
| 10 | **P2 · The wider-listener default is deferred without a boundary of supported start.** | 5.1 says which start paths the product controls and what it enforces on each. On an image run by hand the publisher is the deployer; the product says so, and that `demo`'s password is published. T-23 checks every path the product controls. The exception to DL-108 item 2 (a) was returned to the deciders, who decided it: documented, not refused (DL-110). | 5.1; 5.2; T-23 |
| 11 | **P2 · Several PostgreSQL gates can pass with part of their assertion false.** | G-3a and G-3b read every member of the change after both outcomes. G-7 is two, and G-7b takes the same key from another database. G-2 is four, each withholding what inherits it, the strict profile on every copy and reset-made working copy among them. G-1c withholds every use of a template as pristine. | 8.1 |
| 12 | **P2 · G-6 cannot select the PostgreSQL password fallback.** | G-6a shows the native hazard; G-6b gates the rule itself, with a control on the same image. Only a failure to refuse the password change while the account still reads selects the fallback. G-16 records its statements, mechanisms and usability controls before a branch is chosen. | 4.5; G-6a, G-6b, G-16 |
| 13 | **P2 · The next gate run mixes engine evidence with implementation and packaging.** | Every gate is marked engine-only or needs-the-hook; none needs the CLI. G-21 is T-28. G-35p and G-35m test native authentication by account and by way in, and `CURRENT_USER()` names who signed in; the wrapper's decision is T-23. G-12 and G-32m are removed. | 8.1; 8.2 |
| 14 | **P2 · MySQL's grant and fidelity gates admit false passes.** | G-11c has a readable foreign namespace beside a denied one. G-13 changes the source only, and checks which schema each replayed definition reads and writes. G-10 is three. G-18 is two: a failure with the log off withdraws the key; a failure as shipped is the image's own defect. | 8.1 |
| 15 | **P2 · The disk-full guarantee has no gate on two retained paths.** | 2.6's table says what is promised on each retained path. G-17b fills the disk after a load has dropped its schema, and tries the record's write while full. G-19c fills the destination during a SQLite publication, a sidecar's write, a reset's staged file and an operation's file. | 2.6; G-17b, G-19c |
| 16 | **P2 · Two grant claims remain wider than their evidence.** | A scope is a reference to a defined namespace, and only definitions are checked for overlap; T-3 has the positive case. The product claims nowhere that a copy has had one writer; DataIntent records that criterion as unmet on MySQL unless it has itself read the grants. T-10 forces a repeated name with a hand-made grant. | 2.1; 4.6; 4.7; 7.2; T-3, T-10 |
| 17 | **P2 · Two acceptance conditions lost their disposition.** | Section 9 lists each of DL-085's conditions with where it is met. The inventory's reconciliation with IA-01 is recorded at step 7; the product's inventory is one side of it. The one review covers the hook and the event trigger, each named, at step 8. The check of `di_admin` comes before the first sending or before its provisioning, whichever first brings the two together. | 9; 7.2; 4.2 P-7; 4.3 |
| 18 | **P2 · A lost multi-target reply cannot be reconciled.** | The scripting contract is one target for each call: `--json` and `--operation` take exactly one. Several targets are for a person, with each identity printed as it starts, an aggregate exit, and every target checked before the first is changed. `reset --wait` is removed. | 3.5; 3.3; section 0; T-12, T-19 |
| 19 | **P2 · Section 12 closed findings with impossible expectations.** | T-10 has each engine's own expectation: PostgreSQL's copy has exactly its owner's rights and its read group's `CONNECT`. T-14 depends on the phase: before the exclusive creation there is no object. The rollout's sign-in checks follow each account's effective state. | 8.2; 7.2 |
| 20 | **P2 · The reset migration omits callers and the breadth of the discard.** | 5.4 is the impact note: each change, who it reaches, and what to do; the consoles a SQLite reset stops and whose sessions go with them; that a whole engine's discard is everything on it; that automation has no unattended MySQL or SQLite route. Every caller is named: a search found six validation scripts at seven call sites, where the review named two (F-33); T-21 searches again. The Oracle refusal follows the installed group. Several targets are checked before any is changed. | 5.4; 2.6; 3.3; F-33; T-21, T-26 |
| 21 | **P3 · The lines register lists stages without their findings.** | Section 11 lists every deferred finding against its stage, by review and number. | Section 11 |

**The deciders on round 4's three readings** (DL-109):
- **No `template` and no `interface` command:** accepted. [109-1]
- **`engines.mysql.binary_log` in version 1:** accepted, and its condition is met [G-18a, G-18b]. [109-2]
- **`--discard` takes a named value:** `sessions` for a database's reset, `engine` for a volume's replacement; a whole engine's reset refuses the first; `megasamples up` asks the second. [109-3]
- **Both narrowings accepted, each in the impact note:** a dependency group resets through the whole engine; a SQLite reset needs its discard. T-26 first shows the broken key on today's path. [109-4]

### 12.4 Review 3's findings, each mapped

As round 4 mapped them, with what rounds 5 and 6 changed. Every finding is answered first by removing or narrowing a claim, and is **closed in version 1** only where every entry point version 1 keeps avoids the hazard. [108-7]

| # | Finding | Where it goes | How |
|---|---|---|---|
| 1 | **P1 · The exposure defaults trust everyone who can reach loopback.** | **Version 1,** for privileged accounts. The wider-listener check: **S-1.** | No privileged account has a usable published password on any start path (5.1). G-35p, G-35m; T-23. |
| 2 | **P1 · An exposed console gives administrator access.** | **Version 1.** Wider publication of a console: **S-1.** | No console holds, and no page prints, a privileged password (5.1). T-23. |
| 3 | **P1 · Clean-up authorizes deletion without proof.** | **Version 1.** | An interrupted create is never removed. Each engine's proof is checked at the removal (2.2). G-24p, G-24m, G-24w, G-19b; T-14. |
| 4 | **P1 · A new reset can overtake an unsettled one.** | **Version 1.** | One unsettled operation for each target; both locks; the epoch (3.5). G-26m, G-26p; T-19, T-20. |
| 5 | **P1 · A whole engine's reset can destroy an active copy.** | **Version 1, as DL-108 item 9 has it.** Protection and drain: **S-5.** | A fresh `--discard engine`, for the reset and for `up`; a stop that keeps the volume; no replacement while a reset is running or unsettled (3.5). T-22. |
| 6 | **P1 · MySQL enrollment repair can reopen a database during reset.** | **Version 1,** on the image path. Repair: **S-2.** The template path: **S-6.** | No repair command. A declared writer is suspended before any change and restored only after `done` [116-2]. `done` needs the data verified and the readers' grants in place (3.5). T-27, T-33. |
| 7 | **P2 · The hook does not define an exact namespace boundary.** | **Version 1.** | Rule 2, exact, and binding owners only (4.3). G-29a to G-29d. |
| 8 | **P2 · A readable foreign namespace can expose protected schemas.** | **Version 1.** | Every defined prefix is checked (2.1). G-11c; T-3, T-9. |
| 9 | **P2 · Copy names can be reissued.** | **Version 1, by narrowing.** | The promise is stated exactly, and no claim about a copy's writers rests on it (2.1, 4.7). T-10, T-14. |
| 10 | **P2 · `exclusive: true` does not establish exclusive writing.** | **Removed.** A per-run boundary: **S-2.** | 4.7; 7.2. |
| 11 | **P2 · A drop cannot identify the caller's own hold.** | **S-5.** | `copy hold` is not in version 1. |
| 12 | **P2 · Reset status can give a false answer.** | **Version 1.** | Outcomes kept for the volume's life; `unknown`; one target for each scripted call (3.5). T-12, T-19. |
| 13 | **P2 · The remote reset matrix promises an image source the client lacks.** | **Removed.** **S-4.** | A reset runs where the service runs (3.1). |
| 14 | **P2 · The credential contract does not cover worker and platform inputs.** | **Version 1, by narrowing.** The map to mounted files: **S-1.** | The promise says what is true (3.4). T-13. |
| 15 | **P2 · Storage admission has no input for several operations.** | **S-3.** | Version 1 bounds no bytes; what it promises when a disk fills is gated (2.6). |
| 16 | **P2 · A coordinated MySQL reset lacks a group recovery rule.** | **Version 1, by a tested narrowing.** The group reset: **S-6.** | An installed group is not reset singly (3.5). T-26. |
| 17 | **P2 · Enrollment replay and admission have conflicting authorities.** | **Version 1.** Run-time enrollment: **S-2.** | The configuration is the one authority (4.6). T-5. |
| 18 | **P2 · Several gate fallbacks retain the failed prerequisite.** | **Version 1.** | 8.1: every gate has run, and each failure's consequence is applied (12.2). |
| 19 | **P2 · The regression matrix has impossible expectations.** | **Version 1.** | T-1, T-2, T-10 and T-14, each with its engine's or its phase's own expectation. |
| 20 | **P2 · The native-test plan assumes one machine.** | **Version 1.** | A named, task-owned, disposable target (8.2). |
| 21 | **P2 · The rollout cannot pass its account check with locked spares.** | **Version 1,** in the profile. | Verification follows each account's effective state (7.2). |

**Rounds 1 and 2** are answered in this file's history: round 1's findings at `bdd9033`, round 2's at `e0c2f935`. Section 11 lists those that wait.

## 13. The bar for a finding, and the table of ordinary routes

**The bar** (DL-040; DL-114 item 1). It governs every review from here on.
- **A finding to fix now names four things:** its actor, the supported entry point, the precondition, and the outcome that can be observed.
- **A class is judged by its nearest realistic route, checked through the same mechanism,** before anything is called constructed. Unusual is not constructed.
- **For a security boundary, deliberate misuse by the bounded credential's holder is a realistic route.** Those boundaries are the hook's confinement, the read profile, and the credential defaults.
- **Every deferral is recorded:** its witness, why it is not reachable, and what would reopen it (12.1; section 11).

**The ordinary routes.** This table is the minimum; a route that an ordinary operator, script or credential's holder takes and that is not here is added, not dismissed. Each disposition of 12.1 cites a row.

| # | Route | Who takes it | Through | Held by |
|---|---|---|---|---|
| RT-1 | A first start, and any later one | an operator | `megasamples up` | T-22, T-23 |
| RT-2 | A stop, then a start | an operator | `megasamples down`, then `up`; or the Compose project stopped and started | T-22, T-32 |
| RT-3 | A restart of a container, and a reboot of the host | an operator; the host | the container runtime's restart policy | T-22, T-32, T-19 |
| RT-4 | An upgraded checkout, started by the CLI | an operator | `megasamples up`, with or without `--discard engine` | T-22, T-23, T-29 |
| RT-5 | An upgraded checkout, started from the Compose file | an operator | the file the current version generated, started directly | T-22, T-23 |
| RT-6 | An image run by hand | a deployer | the container runtime | T-23 |
| RT-7 | A reset of one database, by each path | an operator; automation | `megasamples reset`, with `--discard sessions` or `--unattended` | T-19, T-21, T-26, T-27 |
| RT-8 | A reset of a whole engine; a stale image replaced | an operator | `megasamples reset <engine> --discard engine`; `megasamples up --discard engine` | T-22, T-19 |
| RT-9 | A script's copy lifecycle | a script, as a namespace's owner | `copy create`, `show`, `list`, `renew`, `release`, `drop`, `sweep` | T-10 to T-17, T-24, T-31 |
| RT-10 | The CLI killed at any durable phase | the host, a signal, an operator | any command above | T-14, T-19, T-24, T-31 |
| RT-11 | A full disk | the host | any command above | T-14, T-19, T-27 |
| RT-12 | SQL sent directly by a credential's holder, **on purpose where the credential is a bounded one** | `demo`; a declared reader or writer; a namespace's owner; an account an administrator made | the engine's port | T-4, T-6 to T-10, T-25 |
| RT-13 | A worker that starts late, or whose connection drops | the reset's own second process | the image path of a reset | T-20 |
| RT-14 | A second operator on the same host, after an interruption | another operating-system user | any command above | T-19, T-22 |
| RT-15 | A person at a console, or with a client open | a person | a bundled console; a client of their own | T-21 |
| RT-16 | A configuration edited, then a build and a start | a deployer | `megasamples.yaml`, `.env` | T-3, T-5, T-23 |
| RT-18 | **A declared writer at work while its MySQL database is reset** [116-2] | a declared writer | SQL, from a session open when the reset starts, or opened during it | T-33, T-27 |
| RT-17 | **A reset of several targets, or of all** [115-8] | an operator, at a terminal | `megasamples reset` with several targets, a selector, or `all` | T-19 |

## 14. The reset-recovery decision table

**Written once, and tested whole by T-19.** [114-3] The area is hot (`knowledge/governance/review-and-fix.md` in DataIntent): it is not patched finding by finding. A change to any cell is a change to this table, with its test. **DL-115 item 7 completed it; every row it added resolves to an outcome the table already had, and adds no phase and no command.**

**How to read it.** A row is where a reset stopped: a **kill point**. The CLI is killed there in T-19. The columns are the commands that can follow, **by the same operator or a second one.**
- **`--status` changes nothing, in every row, and reports what it observes:** the recorded phase, and the object as it finds it. Where two durable writes cannot be told apart from the record alone, it says both what the record says and what is there. [115-7]
- **`--reconcile` preserves whatever it cannot place.** [115-7]
- **"Refused"** is exit 5, `unsettled`, naming the operation and the `reset --reconcile` command, unless the cell says otherwise.
- **While either lock of the operation is still held** (a worker that outlived its coordinator), `--reconcile` and a new reset are refused as busy, exit 6; the cells are for both locks free.
- **A restart of the server, or a reboot of the host, ends every session and frees every lock.** The row is then the one that says so: a worker's row becomes the row below it.
- **A terminal outcome whose reply was lost,** on any path: `reset --status --operation ID` gives the outcome; the same identity given again to `reset` is refused, `operation-exists`, with that outcome. Nothing is replayed. [115-7]

**PG · A PostgreSQL database, by either path** (steps of 3.5).

| Kill point | What is there | `reset --status` | `reset --reconcile` | A new reset of it | A whole engine's reset; `up` |
|---|---|---|---|---|---|
| **PG-0** during step a, before the row | nothing of this reset | `unknown` | nothing to reconcile | admitted | as if no reset had run |
| **PG-1** after `building`, before the transient exists | the row | unsettled, `building` | **`rolled-back`.** Nothing is dropped. | refused | EN-rules below |
| **PG-2** the transient exists; its OID may not be recorded; a restore may be part-way, **still running,** or failed with the disk full | the row; a transient, empty or partly filled; perhaps a session on it | unsettled, `building`, naming the transient; **`running` while a session is on it** | busy while a session is on the transient. Otherwise **`rolled-back`,** and the transient is **kept and reported:** without a recorded OID it is not known to be this operation's. | refused | EN-rules |
| **PG-3** after `built` | the row, with the transient's OID; the transient, whole | unsettled, `built` | drops the transient if its OID is the recorded one and it has no session, else keeps and reports it. **`rolled-back`.** | refused | EN-rules |
| **PG-4** after `closed`: **the working database refuses connections** | as PG-3, and the door closed | unsettled, `closed`; says the database is closed | **opens the door again;** the transient as PG-3. **`rolled-back`.** | refused | EN-rules |
| **PG-5** after `swapped`, before the old one is dropped | the new working database, open; the old one under its transient name | unsettled, `swapped` | drops the old one, only by the OID recorded at step b. **`done`.** | refused | EN-rules |
| **PG-6** the old one dropped, `done` not yet written | the new working database | unsettled, `swapped` | finds no old transient. **`done`.** | refused | EN-rules |
| **PG-7** the second look refused, and the CLI was killed **after the reopening** [115-7] | the row, back at `built`; the door open; the transient | unsettled, `built` | as PG-3. **`rolled-back`.** | refused | EN-rules |
| **PG-8** a terminal outcome written, the reply lost [115-7] | what the outcome says | `done`, or `rolled-back` | nothing to reconcile | admitted, under a new identity | as if no reset were pending |

- **The CLI itself opens the door again when a signal interrupts it at PG-4.** A kill it cannot catch leaves the database closed until someone reconciles; `--status` says so.
- **A second look that refuses** reopens the door in one transaction that sets the phase back to `built`, then drops its transient, then writes `rolled-back` (3.5, step e). Killed before the reopening, it is PG-4; after it, PG-7; after the last write, PG-8.

**MY · A MySQL database** (steps of 3.5). Every cell that loads makes the writers' check first (3.5). [115-1] **From MY-2 to MY-9 a declared writer that reconnects is refused a write to that schema;** only `restored`, or a `rolled-back`, gives its grant back. [116-2]

| Kill point | What is there | `reset --status` | `reset --reconcile` | A new reset of it | A whole engine's reset; `up` |
|---|---|---|---|---|---|
| **MY-0** during step a, before the row; **or refused at the writers' check** | nothing of this reset | `unknown` | nothing to reconcile | admitted | as if no reset had run |
| **MY-1** after `started` | the row; nothing suspended; the schema untouched | unsettled, `started` | **`rolled-back`.** | refused | EN-rules |
| **MY-2** after `suspended`: some or all of the declared writers revoked [116-2] | the row, naming them; the schema untouched | unsettled, `suspended`, naming the writers | **gives every named writer its grant back,** then **`rolled-back`.** | refused | EN-rules |
| **MY-3** after `loading`, before the worker's guard | the row; the schema untouched; the writers suspended | unsettled, `loading` | raises the epoch; runs steps c to f again. **`done`, then `restored`;** or `failed`. | refused | EN-rules |
| **MY-4** the worker is loading, the coordinator is killed, **and the server is still up** | the row; **the worker still holds its lock** | `running` | **busy,** exit 6, until the worker ends | busy, exit 6 | **refused,** `reset-active` |
| **MY-5** the load stopped part-way: the worker killed, its session ended, the disk full, **or the server restarted during MY-4** [115-7] | the row, `loading`, with `failed` if that write was made; **a schema that is not the image's;** both locks free | unsettled, `loading`, with `failed` and its reason where recorded | raises the epoch; runs steps c to f again. **`done`, then `restored`;** or `failed` again if it still cannot load. | refused | **the escape, once `failed` is recorded.** Where that write was not made, refused: reconcile first. `up --discard engine` is refused either way. |
| **MY-6** the load finished, before `loaded` | the row, `loading`; the schema loaded, not verified | unsettled, `loading` | as MY-3: it loads again | refused | EN-rules |
| **MY-7** after `loaded`, before `done` | the row; the schema verified | unsettled, `loaded` | **verifies again, confirms the readers' grants, and does not load. `done`, then `restored`;** or, if tables differ, records `failed`: that is MY-8. | refused | EN-rules |
| **MY-8** `loaded`, with `failed`: **a reverification found tables that differ, and they still do** [115-7] | the row; a schema that is not the image's | unsettled, `loaded`, `failed`, with the tables | **as MY-5:** raises the epoch and runs steps c to f again, on the same operation. **`done`, then `restored`;** or `failed` again. | refused | the escape |
| **MY-9** **after `done`, before `restored`:** the CLI killed there, or a writer's grant could not be restored [116-2] | the row, `done`; the data verified; **one or more declared writers still without their grant** | **`done`, and each writer still suspended, by name** | **restores the grants. It does not load, and does not verify again. `restored`;** or it reports the grant that still fails, exit 8. | refused, until `restored` | EN-rules: refused, for the operation is not settled and is not `failed` |
| **MY-10** a stream of the killed reset arrives during or after a reconciliation | — | — | **the stream stops at its guard:** it does not own the lock, or the epoch is another. The reconciliation is unaffected. | — | — |

**SL · A SQLite working database** (steps of 3.5). [115-2] [115-7]

| Kill point | What is there | `reset --status` | `reset --reconcile` | A new reset of it | `megasamples up`; a whole engine's reset |
|---|---|---|---|---|---|
| **SL-0** before the operation's file | nothing of this reset | `unknown` | nothing to reconcile | admitted | `up` starts as usual |
| **SL-1** after `started`; the consoles may be stopped | the record; the working file is the recorded one | unsettled, `started`; names the stopped consoles; says the working file is the recorded one | starts the consoles. **`rolled-back`.** | refused | **`up` starts no console:** exit 5, `unsettled`, naming the operation and `reset --reconcile`. A whole engine's reset: EN-rules. |
| **SL-2** a staged file beside the working file; the phase still `started` | as SL-1, and the staged file | as SL-1 | removes the staged file it made; starts the consoles. **`rolled-back`.** | refused | as SL-1 |
| **SL-3** the phase `staged`, **the rename not made** | the working file is still the recorded one; the staged file | unsettled, `staged`; **says the working file is still the recorded one** | as SL-2. **`rolled-back`.** | refused | as SL-1 |
| **SL-4** the phase `staged`, **the rename made;** not verified, or the consoles not started | the working file is the image's | unsettled, `staged`; **says the working file is the image's** | verifies it; starts the consoles. **`done`.** | refused | as SL-1 |
| **SL-5** at any of SL-1 to SL-4, **the working file is neither the recorded one nor the image's:** someone changed it | the record; a file with someone's edit | unsettled; says the file is neither | **changes nothing in the file, and stages nothing over it.** Records `failed`, with what it found. The consoles stay stopped. | refused | as SL-1. Once `failed` is recorded, the escape applies; or the README's route by hand. |
| **SL-6** **the record is of another volume;** or the volume's identity cannot be read | a record that may not be about these files | says which volume the record is of, and this volume's identity, or that it could not be read | **changes nothing,** and keeps the record | a record of another volume does not hold this one: admitted. An identity that cannot be read: refused. | the same: `up` goes on past a record of another volume, and refuses where the identity cannot be read |

**EN · A whole engine's volume.** It has no phases, so nothing here is reconciled. [114-2B]

| Kill point | What is there | `reset --status` | `reset --reconcile` | The same command again, with a fresh `--discard engine` | `megasamples up`, with no option |
|---|---|---|---|---|---|
| **EN-0** before its record | the old volume, attached; the engine running | no record of it | does not apply: exit 2 | by the EN-rules | starts, by U-2 or U-3 |
| **EN-1** the record written; the engine stopped; nothing removed yet | the old volume, detached | interrupted; **the volume there is the old one,** by its identity | does not apply | **refused: the engine is stopped, and its state cannot be read** [115-W]. `megasamples up` first. | attaches the old volume, by U-2; or refuses, by U-3 |
| **EN-2** the old volume removed; no new one yet | no volume | interrupted; no volume | does not apply | admitted: there is nothing left to discard, and it creates | creates and seeds, by U-1 |
| **EN-3** **the new volume created, and noted in the record; not yet seeded or identified** [115-7] | a volume, empty or partly seeded | interrupted; a volume that this replacement created, not yet identified | does not apply | **admitted: the record shows this replacement made it.** It is replaced. | an empty one the image seeds; a partly seeded one it refuses to start on, and `up` refuses, by U-4 |
| **EN-4** a volume that the record does not account for, or whose identity cannot be read [115-7] | a volume of uncertain identity | interrupted; says what it can read | does not apply | **refused, even with fresh consent.** The volume and the record are kept (U-4). | refuses, by U-4 |
| **EN-5** the new volume is up; the record not completed | the new volume, perhaps with edits made since | interrupted; **the volume there is the one the record notes as new** | does not apply | by the EN-rules; admitted, **it discards the new volume: that is the decision the fresh option records** | attaches the new volume, by U-2. **Nothing is replaced.** |

- **EN-rules, for a whole engine's reset or `up --discard engine` over the resets of single databases on that engine** [115-W]: **refused** while one is running, which is a lock held or a session on its transient; while one is unsettled; and while the engine's state cannot be read, a stopped engine included. **The one escape:** a whole engine's `reset`, named, with a fresh `--discard engine`, the volume identified, every unsettled operation durably `failed`, and their locks free. It names each. `up --discard engine` has none. `megasamples up` with no option never replaces, in any row.
- **A copy command at any of these points** is unaffected by a reset of another database, and ends with exit 8 if its engine's volume is replaced under it.

**MT · A reset of several targets.** [115-8] **There is no record of the whole.** Each target is its own operation, and its identity is printed as it starts.

| Kill point | What is there | `reset --status ENGINE` | What an operator, the same or a second, then does |
|---|---|---|---|
| **MT-1** before the first target is started | nothing of this reset | `unknown` for each | gives the command again |
| **MT-2** between two targets | each finished target has its terminal record; the others have none | each finished one, with its outcome. Nothing for the others, for nothing of them was started. | resets the targets that have no record. **A finished target is not touched,** and keeps any edit made since. |
| **MT-3** during a later target | the finished ones as MT-2; the one in hand unsettled, at a kill point of its own path; the others none | as MT-2; and the one in hand as its own table says | reconciles the one in hand by its own table; then resets those with no record |

- **The same command given again is not a recovery.** It is refused if any target it names is unsettled; otherwise it resets every target it names, finished ones included. The printed identities and `--status` are how the remaining targets are chosen.

## 15. DL-115's rulings and DL-116's direction: where each rule is, and its test

**For the coordinator's mechanical check.** Round 8 holds only these. Each line number is of this file at this commit. A rule's line carries its mark, **[115-n]** or **[116-n]**, or is the table row named; a test's line is its row in 8.2.

| What was ruled or directed | The rule, by section | Its lines | Its test rows | Their lines |
|---|---|---|---|---|
| **Item 1** · P1-2: a retained MySQL write grant is refused at admission, before any change | 3.5, the writers' check; section 14, MY-0 | 486, 488, 492, 1459 | T-27 | 1163 |
| **Item 2** · P1-4: `up` starts no console while a SQLite reset is unsettled; the operation's file carries the volume's identity; a changed file, another generation or an uncertain identity is preserved | 3.5, a SQLite reset; section 14, SL-1, SL-5, SL-6 | 498, 499, 500, 1476, 1480, 1481 | T-19, T-32 | 1155, 1167 |
| **Item 3** · P2-7: T-11 accepts a correct withholding | 2.4; 8.3, G-13's row | 277, 1191 | T-11 | 1147 |
| **Item 4** · P2-8: 12.2 agrees with 2.6; a later failure is `interrupted` and preserved | 2.6; 12.2, G-9's row | 317, 1317 | T-14 | 1150 |
| **Item 5** · P3-10: the start's maintenance with locked accounts is T-23's, once it runs | 5.1, default 2 | 853 | T-23 | 1159 |
| **Item 6** · P2-9: what exit 6 promises; the early and the late refusal, each with `--status` | 3.3; 3.5, the session decision | 363, 373, 517, 518, 519 | T-12, T-21 | 1148, 1157 |
| **Item 7** · P2-5: the recovery table completed; `--status` reports what it observes, `--reconcile` preserves; a partly seeded volume this replacement made may be replaced, an uncertain one is kept | Section 14: how to read it; PG-7, PG-8; MY-5, MY-8; SL-3, SL-4; EN-3, EN-4. 3.5, replacing a volume | 1431, 1432, 1436, 1449, 1450, 1464, 1467, 1478, 1479, 1490, 1491, 562 | T-19, T-22 | 1155, 1158 |
| **Item 8** · P2-6: the route of several targets, and its kill points, with no record of the whole | Section 13, RT-17; section 14, MT-1 to MT-3 | 1424, 1497, 1501, 1502, 1503 | T-19 | 1155 |
| **Item 9** · the four P1 routes are the first tests of the reset slice | 8.2, the list before the table | 1123, 1127, 1128, 1129, 1130 | T-22, T-27, T-29, T-19, T-32 | 1158, 1163, 1164, 1155, 1167 |
| **The whole-engine escape** (taken where they differed): refused while running, unsettled or unreadable; one escape; a stopped engine refused, recovered by the README's route | 3.5, replacing a volume; section 14, EN-rules and EN-1; 5.3 | 557, 558, 560, 561, 1494, 1488, 892 | T-22, T-29 | 1158, 1164 |
| **An upgrade after an older `down`** (taken where they differed): reattach or refuse wherever an earlier deployment is detectable; a stated limit only for an indistinguishable install, with the README's steps | 3.5, the start table, U-1 and U-5, and the two rules after it; 5.3; section 10, item 5 | 540, 544, 546, 547, 892, 1226 | T-22, T-29 | 1158, 1164 |
| **DL-116, item 1** · declared writers on MySQL's working databases are in version 1; narrowing C and its stated limit are removed | Section 0; 4.4; 4.6; 4.7 | 39, 60, 716, 768, 775 | T-5, T-6 | 1141, 1142 |
| **DL-116, item 2** · a MySQL reset suspends the declared writers before any change, records `done` for the verified data, and restores their grants only after, as a recorded and reconcilable step | 3.5, a MySQL reset, steps b, e and f; 4.6; section 14, MY-2 and MY-9; section 13, RT-18 | 475, 478, 479, 481, 482, 432, 779, 1461, 1468, 1423 | T-33, T-5 | 1168, 1141 |
| **DL-116, item 3** · DL-115 item 1 stands for every other ordinary writer | 3.5, the writers' check | 491 | T-27, T-33 | 1163, 1168 |
| **DL-116, item 4** · its three ordering cases are among the first tests of the reset slice: a writer reconnecting at each step; a regrant failing after `done`; a session ended mid-transaction | 8.2, the list before the table | 1131, 1132, 1133 | T-33 | 1168 |
