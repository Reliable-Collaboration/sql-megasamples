# Templates, copies, the scripting CLI and the account model: version 1

**Design record · 2026-11-20 · round 4, the drafter's part. Status: a design under review. Nothing here is built, and nothing here has been run.**

- **What this is.** The design of **version 1** of sql-megasamples' pristine templates, per-test copies, the commands that scripts drive them with, and the account model that goes with them. It carries the strict PostgreSQL read profile of pull request #14.
- **Round 4 is a cut.** The two deciders staged the design (DL-108): one bounded version 1, merged and rolled out once, and later stages as new work. **This record holds version 1 only,** exactly the list of DL-108 items 5 and 8 to 11, at the placements of its items 1 to 3. Its surface is frozen (section 0).
- **The fuller design is kept in Git history,** at `e0c2f935` of this file, as the source for the later stages. It was not moved to a second file: this task writes one file. Section 11 names each stage and what waits in it.
- **What sql-megasamples is.** A stand-alone offering: sample database servers that someone spins up, in any network setting (DL-107). Sections 2 to 6 describe that product. A deployment is configuration; DataIntent's development instance is one, in section 7.
- **Rounds.** Round 1 is `2a15387`; round 2 `bdd9033`, with `9fe0bbd`; round 3 `e0c2f935`. Astra's review 3 found six P1s and fifteen P2s. Section 12 maps each to version 1, closed and how, or to its waiting stage. The reviews are in the coordinator's ignored `.local/megasamples-design/` in DataIntent.
- **What comes next** (DL-108 item 12): one review of this cut, on its scope and its gates' definitions; then version 1's gates run on an isolated stack, engine behaviour only; then this record is revised from what was observed and reviewed to two clean rounds. **No round counts as clean while a gate of section 8.1 is unrun.** A required capability that fails its gate returns to the deciders.
- **Method.** Reading only: no container, no database connection, no network, and no credential file. So no statement about how an engine behaves has been observed.
- **Marks.** Each claim carries one:
  - **[R]** read in the cited file and line;
  - **[G-n]** rests on a native behaviour nobody has shown: gate *n* of section 8.1. It is not asserted either way;
  - **[I]** inferred, and not load-bearing;
  - **[D]** decided here, with the reason;
  - **[108-n]** decided by the two deciders in DL-108, item *n*.
  - A table or list whose heading line carries a mark is marked as a whole. A file and line cited inside any row is **[R]**.
- **Citations.**
  - `SM:` is sql-megasamples at `main`, `e61335f`. `PR14:` is its branch `fix/strict-read-account` at `2879fc4`.
  - `DL:` is DataIntent's `docs/work/decision-log.md` on `origin/coordinator/journal-during-full`: DL-070 to DL-103 at `d02f7384`; DL-104 to DL-108 at `5831ef43`. `LR:` is `docs/work/lines-register.md` there.
  - `ED:` is DataIntent's `docs/work/samples-service-editing-requirements.md`, `MR:` its `docs/work/samples-service-requirements-and-architecture.md`, and `DI:` any other DataIntent file, all at `4a8aad61` (`origin/coordinator/samples-p1`).

## 0. Version 1's surface

**This is the whole of it.** [108-7] Nothing below may be added to without the deciders. Anything may be removed or narrowed.

| Kind | Version 1 has |
|---|---|
| **Commands** | `megasamples copy create`, `show`, `list`, `drop`, `renew`, `release`, `sweep`. `megasamples reset`, as today, with the options below. No other command is new. |
| **Options** | For `copy`: `--host`, `--port`, `--user`, `--connect-timeout`; `--password-file` or `--password-stdin`; `--prefix`, `--label`, `--lease`, `--identity`, `--wait`, `--dry-run`; for SQLite `--templates` and `--dir`. For `reset`: `--json`, `--operation`, `--discard`, `--unattended`, `--status`, `--reconcile`, `--wait`. |
| **Configuration keys** | `engines.<engine>.templates`; `engines.mysql.binary_log`; `copies.namespaces` (each: `prefix`, `owner`, `max_copies`); `copies.foreign` (each: `prefix`, `demo_reads`); `accounts.readers` and `accounts.writers` (each: `name`, `scopes`). |
| **`.env` keys** | Today's four. `MYSQL_DEMO_PASSWORD`. One for each namespace's owner and each declared account: its name in upper case, then `_PASSWORD`. |
| **Formats** | The JSON document's `schema`. The `interface` number. Four records with a tag each: the service's, a template's, a copy's, an operation's. For SQLite, a manifest and a sidecar. |
| **Service accounts** | `postgres`, `root`, `admin` and `demo`, as today. A namespace's owner. A declared reader; a declared writer. On PostgreSQL, the groups of 4.1. |
| **Hook rules** | Four (4.3): the creator must hold the new owner's rights; a namespace's owner is confined to its namespace and to registered templates; a new database is closed to `PUBLIC`; a role without `CREATEROLE` cannot alter roles or default privileges. |

**What version 1 contains, by DL-108's list:**

| DL-108 | In version 1 | Where |
|---|---|---|
| Item 5, first | Templates, copies and the scripting CLI on all three engines: create, show, list, drop, renew, release and sweep, with the lease as the protection. | 2; 3 |
| Item 5, second | Nothing ambiguous is ever removed: an interrupted create is kept and reported. | 2.2 |
| Item 5, third | One unsettled operation for each target, on every reset path. | 3.5 |
| Item 5, fourth | Pull request #14's corrected read profile, under every condition of DL-085, with the lines register's two items of line 10. | 4.2; 4.4; 4.5 |
| Item 5, fifth | The hook's confinement of namespace owners. | 4.3 |
| Item 5, sixth | Privileged credentials private by default, even on loopback; bundled consoles that require sign-in before privileged access; `demo` still published. | 5.1 |
| Item 5, seventh | Reader and writer grants declared in the configuration, locked until keyed, applied at start, and applied again by each reset under its exclusion. | 4.6 |
| Item 5, eighth | A safe service-side image restore. | 3.5 |
| Item 5, ninth | The CLI's contract for the formats version 1 has; the reset's session decision; the runbook's split. | 6; 3.5; 5.3 |
| Item 9 | A whole engine's reset refuses unless told to discard, and the service's record carries an identity for each volume. | 3.5 |

**What version 1 does not contain** is section 11: seven named stages. A claim that rested on any of them has been removed from this record, not left standing.

## 1. What the design rests on

### 1.1 The product, as it is today

| # | Fact | Where | Mark |
|---|---|---|---|
| F-1 | **Every command of today's CLI that contacts a running engine does it through `docker exec`.** The reset starts a second container of the running image, and pipes a dump from it. | `SM:megasamples/credentials.py:29-70`; `SM:megasamples/reset.py:156-197`, `:245-304` | [R] |
| F-2 | **The CLI's output is text for a person,** and a command returns 0, 1 or 2. An unknown command is 2. | `SM:megasamples/cli.py:68-82`; `SM:megasamples/reset.py:384` | [R] |
| F-3 | **Resets exclude each other by a lock file** for one user on one host. | `SM:megasamples/reset.py:101-116`; `SM:README.md:323-325` | [R] |
| F-4 | **PostgreSQL's reset of one database drops it with force, and only then restores it.** MySQL's pipes a dump that drops and reloads the schema in place, then compares row counts with the image's. SQLite's stops the consoles that read its files. | `SM:megasamples/reset.py:254-262`, `:294-302`, `:336-354` | [R] |
| F-5 | **Accounts today.** PostgreSQL: `admin` has `CREATEDB` and `CREATEROLE` and owns each sample database and what is in it; `demo` has `SELECT` on the tables. MySQL: `admin` and `root@'%'` hold all privileges with the grant option; `demo` holds `SELECT, SHOW VIEW ON *.*`. | `SM:engines/postgres/init/00-users.sql:10-12`; `SM:engines/postgres/init/20-grants.sql:4-7`; `SM:engines/mysql/init/00-users.sql:9-19` | [R] |
| F-6 | **Each health probe signs in as `demo`.** Passwords are applied at each start from the container's environment. | `SM:megasamples/engines/postgres/__init__.py:80`; `SM:megasamples/engines/mysql/__init__.py:139`; `SM:engines/postgres/entrypoint-wrapper.sh:17-35`; `SM:engines/mysql/entrypoint-wrapper.sh:19-40` | [R] |
| F-7 | **The registry has one row per database,** with a build id that is `dev` unless `MEGASAMPLES_BUILD_ID` is set. | `SM:megasamples/registry.py:52-88`, `:111` | [R] |
| F-8 | **A large configuration is large:** one bakes 22.712 GiB on MySQL, 20.902 GiB on PostgreSQL and 17.862 GiB of SQLite files. | `SM:docs/live-upgrade-runbook.md:97`, `:101-105` | [R] |
| F-9 | **Sizes on record are old, and of two kinds,** and none counts a dataset that appends to a core database. Three do: `nyc_taxi_yellow`, `chicago_crimes_full`, `dvdstore_reviews`. | `SM:ARCHITECTURE.md:170-171`; `SM:knowledge/decisions/tier-assignments.md:32-88` | [R] |
| F-10 | **MySQL's binary log grew to 10.9 GB** after a rehearsal of logical resets. The shipped server's configuration does not turn it off. | `SM:docs/live-upgrade-runbook.md:109`; `SM:engines/mysql/my.cnf:1-11` | [R] |
| F-11 | **One dataset reaches into another database:** `oracle_oe` depends on `oracle_hr`. | `SM:datasets/oracle_oe/dataset.yaml:8`; `SM:README.md:212` | [R] |
| F-12 | **Pull request #14** revokes `TEMPORARY` and routine `EXECUTE` from `PUBLIC` in every database and both templates, grants `admin` what it had, and grants `demo` an allow-list. A compiled hook closes `TEMPORARY` on each new database. An event trigger closes `EXECUTE` on each new routine. | `PR14:engines/postgres/init/10-read-profile.sql:4-35`; `PR14:engines/postgres/read-policy/read_policy.c:29-40`; `PR14:engines/postgres/read-policy/read_policy--1.sql:1-20` | [R] |
| F-13 | **Its grant to `admin` carries no grant option.** | `PR14:engines/postgres/init/10-read-profile.sql:10-13` | [R] |
| F-14 | **Its evidence:** 254 native cases Passed on an isolated stack; MySQL is not claimed strict, and `demo` there can take a named lock. **Its native guard names one machine's project and paths.** | `PR14:docs/strict-read-evidence.md:16-18`, `:30`; `PR14:tests/test_strict_read_native.py:20-30` | [R] |
| F-15 | **It merges into `main` without conflict.** | `git merge-tree origin/main fix/strict-read-account` | [R] |
| F-20 | **Each server accepts every account from every address that reaches its port.** | `SM:engines/postgres/Dockerfile:33`; `SM:engines/mysql/init/00-users.sql:9-18` | [R] |
| F-22 | **The reset reads its passwords in the host's own process,** by a reader under which an exported value wins over the file's. It hands them to the container it starts as that container's environment. | `SM:megasamples/reset.py:172-183`, `:246`, `:290`; `SM:megasamples/config.py:155-167` | [R] |
| F-28 | **Every published port binds to `127.0.0.1`,** and the file that says so is generated. That says who reaches the published port; it says nothing of who reaches the engine inside the stack's own network. **Every password has a published default,** `admin`'s and the superusers' among them. | `SM:megasamples/compose.py:10-11`, `:30-31`, `:40`; `SM:megasamples/engines/postgres/__init__.py:76`; `SM:.env.example:5-9`, `:25-31` | [R] |
| F-29 | **The README and the runbook hold one deployment's story:** a dated account of "the maintained deployment", its LAN forwards, and a runbook headed "coordinator only". | `SM:README.md:16-20`, `:258-270`; `SM:docs/live-upgrade-runbook.md:1-3` | [R] |
| F-31 | **The bundled consoles hold administrator access.** phpMyAdmin signs a browser in with no form, and offers `admin` beside `demo`. DbGate and CloudBeaver are given `admin`'s password as a stored connection. | `SM:consoles/phpmyadmin/config.user.inc.php:15-27`; `SM:megasamples/engines/postgres/__init__.py:91-100`; `SM:megasamples/engines/mysql/__init__.py:146-162` | [R] |

### 1.2 One consumer, DataIntent

Facts about one consumer. Section 7.2 is where they are used.

| # | Fact | Where | Mark |
|---|---|---|---|
| F-16 | **Its fixture** makes `di_reader` and `di_analyst` as `admin`, and each `di_…` database from `di_template`, `template1` or `template0`. It gives each of its roles to `admin`, inherited. | `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureServer.cs:27-32`, `:131-134`, `:224-230`, `:403-409` | [R] |
| F-17 | **Its provider, as a read account,** lists databases `WHERE NOT d.datistemplate`, and calls `pg_database_size(oid)`, `pg_export_snapshot()` and `pg_current_snapshot()`. It imports the snapshot in another transaction. | `DI:src/DataIntent.Adapters/Postgres/PostgresSourceServer.cs:237-240`, `:347`; `DI:src/DataIntent.Adapters/Postgres/PostgresSnapshot.cs:136` | [R] |
| F-18 | **Of those built-ins, none of the three is in pull request #14's allow-list.** | a search of `PR14:engines/postgres/init/read-routine-names.sql` | [R] |
| F-24 | **Its comparison before an upgrade has five parts, C1 to C5.** C5 asks that an export be refused, with nothing in its stream, after an elevation **and** when the fresh check cannot be made. | `MR:` section 3, "The comparison as designed" | [R] |
| F-25 | **One rollout rebuilds its instance from a build of `main`.** Each engine image copies `README.md`. | `DL:` DL-103; `SM:engines/postgres/Dockerfile:13` | [R] |
| F-26 | **Pull request #14 stays unmerged until that instance's first cutover is accepted,** and C1 must pass against its candidate before it merges. The read account's native admission on the candidate comes "once the cutover is accepted". | `DL:` DL-085 items 1, 3 and 4 | [R] |
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
- **What is promised of a name, and no more.** [D: review 3's finding 9.] A name is never issued while its record or its object exists: both are confirmed absent under the namespace's lock before a row is written. **A name may come again once both are gone,** by a collision of twelve digits. Version 1 makes no grant on a copy's name, so nothing of its own can wait there for a later copy; a grant an administrator made by hand on such a name is that administrator's, and is not checked.
- **Characters and length.** A prefix matches `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` and is at most 16 bytes. A label matches `^[a-z0-9]{1,24}$`. A whole name is at most 63 bytes on both engines; the build refuses a database name longer than 33. [D]
- **Reserved:** the suffix `_start`, a double underscore, and the name `megasamples`. [D]

**A namespace** is one prefix with one owning account, baked into the image:

```yaml
copies:
  namespaces:
    - {prefix: copy, owner: copier, max_copies: 32}   # the default
  foreign:
    - {prefix: P, demo_reads: false}                   # a prefix a consumer keeps for objects of its own
```

- **Any number of namespaces, each with an owner of its own.** An owner is locked until its key is set, so a namespace can be baked ahead of need.
- **Every prefix that produces a grant is checked against everything it must not reach.** [D: review 3's finding 8: round 3 checked copy prefixes only.] The build refuses a configuration in which a namespace's prefix, **a foreign namespace's prefix, or a declared account's scope** `P`:
  - equals, or is followed by an underscore at the start of, the name of any registered database, any template, `megasamples`, or an engine's own schema;
  - equals another such prefix, or one begins with the other followed by an underscore.
- **On MySQL every underscore in a grant's schema pattern is escaped,** in a prefix and in a database's own name. [G-11a]

### 2.2 A copy's record, its proof, and what is ever removed

The same on all three engines. [D]

**The record.** Each namespace has a ledger: on the servers a table in `megasamples` that the namespace's owner and the administrators can write; for SQLite a sidecar beside each file. A row holds the copy's `name` and `identity`, its `label` and `database`, its `phase`, a `revision` raised by every change, `lease_until`, and its `proof`.

**The phase is written before the step it announces:** `reserved`, then `issuing`, then `created`, then `ready`; and `dropping`.

**The proof is a retained identity, tied to the exclusive creation of the object.** [D: review 3's finding 3.]

| Engine | Exclusive creation | What is retained, and recorded at `created` |
|---|---|---|
| PostgreSQL | `CREATE DATABASE`, which fails on an existing name | the database's OID, and a comment on it that carries the identity [G-24p] |
| MySQL | `CREATE DATABASE`, never `IF NOT EXISTS` | at `ready`, a fingerprint of every table's name and creation time [G-24m] |
| SQLite | a hard link to the final name, which fails if it exists | **a second link to the same file, kept for the copy's whole life** in `.megasamples/` under the identity. While it is kept, the inode cannot be given to another file, and the final name is this copy exactly when the two are one file. [G-19b] |

**Locks.**
- **The change lock** of a name is held for the whole of any change to that copy: a session's advisory lock on PostgreSQL, taken in the `megasamples` database; a named lock on MySQL; a `flock` on SQLite, on a lock file of its own that is never the sidecar and never removed while its copy's record exists.
- **The session that runs a change is the session that holds its lock.** [G-7, G-15a]
- **A namespace lock** is held only while a reservation is counted and written.

**Creating,** under the name's change lock:
1. **The reservation, atomic:** under the namespace lock, the live copies are counted against `max_copies`, an identity is issued, the name and its row are confirmed absent, and a row is written: `reserved`.
2. `issuing` is written. The object is made (2.3, 2.4, 2.5).
3. The proof is recorded: `created`. The object is filled or granted.
4. `ready` is written. The lock is released.

**Nothing ambiguous is ever removed.** [108-5] **An interrupted create is kept and reported, by every command, on every engine.**

| The row's phase | The change lock | The object | State | What any command does with it |
|---|---|---|---|---|
| none | — | present, in the namespace | `unmanaged` | keeps it; reports it |
| any | held | — | `changing` | leaves it |
| `reserved`, `issuing` | free | absent | `stale` | removes the row only |
| `reserved`, `issuing`, `created` | free | present | **`interrupted`** | **keeps it; reports it.** No command removes it. |
| `ready` | free | present, proof matches | `ready` | the rules below |
| `ready`, `dropping` | free | absent | `gone` | removes the row only |
| `dropping` | free | present, proof matches | `dropping` | finishes the drop |
| `ready`, `dropping` | free | present, **proof does not match** | `inconsistent` | keeps it; reports it |

- Round 3 removed an interrupted MySQL create when its schema held no table, and trusted a PostgreSQL transient by its name. Both are withdrawn: **only a copy that reached `ready`, with its proof, is ever removed.**
- An `interrupted`, `unmanaged` or `inconsistent` object is an administrator's to remove, by hand. `copy list` goes on showing it.

**Every command that changes a copy names the identity it expects.** `copy drop`, `renew` and `release` take `--identity`. Under the change lock the row is read again:

| Command | Requires |
|---|---|
| `renew`, `release` | the identity named; `ready` |
| `drop` | the identity named; `ready` or `dropping`; the proof. **Any lease:** an owner may drop its own leased copy. |
| a sweep's removal | the identity **and the revision** it selected; `ready`; the proof; **a lease that has ended, read again now** |

Otherwise exit 5, and nothing was changed.

**The lease is the protection.** [108-5] [108-8]
- A copy is created with a lease, 24 hours by default. A run that lasts longer renews it.
- **A sweep removes a copy only when:** its state is `ready`; its lease has ended, read again under the lock; its change lock is taken without waiting; its identity and revision are as selected and its proof matches; and the engine lets it go. On PostgreSQL that last is a plain `DROP DATABASE`, which refuses while any session is connected [G-8b]; on MySQL a drop that gives up after five seconds on a lock [G-15b].
- **What that does not protect, said plainly.** A copy whose lease has ended is the sweep's to take. On PostgreSQL a connected session still saves it. **On MySQL an idle session does not, and for SQLite an open file does not.** The product does not claim that a sweep never removes a copy in use; it claims that a sweep never removes a copy inside its lease.
- **`copy hold` waits** for a later stage (section 11).

### 2.3 PostgreSQL

**The template.**
- **It is `<database>_start`, with `datistemplate` true, `datallowconn` false, and the superuser `postgres` as its owner.** [D] It refuses every connection [G-1a]; a role that may create databases can copy it, two at once [G-1b]; only the superuser can alter, rename or drop it [G-1c].
- **It is registered by its comment,** which only its owner can set: the tag `megasamples-template/1` and a JSON object with the database, its allocated bytes, the copy strategy, the build id and the SHA-256 of its registry row. [G-8a]
- **It is frozen before it is closed:** `VACUUM (FREEZE, ANALYZE)` in the image build. [D]

**How the image makes it.** [D]
1. The dataset is loaded into `<database>_start`, as `admin`, as today (`SM:engines/postgres/Dockerfile:43-53`).
2. The read grants of 4.1 and the read profile are applied there. **No write grant to any group is.**
3. It is frozen, given to `postgres`, registered and closed.
4. The working copy is made from it, and given its own grants (4.1).
5. A database with no template is loaded straight into `<database>`, as today, with the same grants.

**A copy,** as the namespace's owner, connected to the `megasamples` database:
- `CREATE DATABASE <copy> TEMPLATE <database>_start STRATEGY <strategy>`. The hook confines the name and the template, and closes the new database to `PUBLIC` (4.3).
- Its OID is recorded, and its comment written: `megasamples-copy/1` and the identity.
- **Last,** `GRANT CONNECT` on it to the namespace's read group. Until then only its owner can connect.
- **The strategy** is the template's recorded one, measured at build. [D]
- **Its owner is the one ordinary account that can write it** (4.1). [G-23]

**A drop** is a plain `DROP DATABASE`, never with force [G-8b]. With `--wait` it is tried again until the wait ends. A drop that gives up has changed nothing.

### 2.4 MySQL

**The template.**
- **It is the schema `<database>_start`, set `READ ONLY = 1`.** [D] [G-10]
- **MySQL has no "accepts no connections" for a schema.** What stands in its place: `demo` holds no privilege there; a namespace's owner holds `SELECT` only; `admin` and `root` can read it, and can change the option. [D]

**How the image makes it.** After the dumps are loaded (`SM:engines/mysql/Dockerfile:39-42`), for each templated database, as `root`:
1. Its definitions are recorded in `megasamples.template_ddl`: tables, then routines, views in dependency order, triggers and events, each without its definer; and the insertable columns and the `CHECKSUM TABLE … EXTENDED` of each table. [G-13]
2. The template is made from the loaded database by the copy below, with each original definer kept.
3. Each table's row count and checksum are compared with the loaded database's.
4. The template is set `READ ONLY = 1`.

**A copy,** as the namespace's owner, all of it inside the server:
1. `CREATE DATABASE <copy>`, with the template's character set and collation.
2. Each table's recorded definition, with foreign-key checks off for the session.
3. `INSERT INTO <copy>.<table> (…) SELECT … FROM <database>_start.<table>`, a table at a time.
4. The routines, the views, and then the triggers and events.
5. Each table's row count and checksum compared with the template's record.
6. The fingerprint is recorded, and the row is set `ready`.

- **A copy has no grant of its own.** A namespace's owner is the one ordinary account that can write its copies; a declared reader of the namespace can read them (4.6).
- **The definer of everything in a copy is the namespace's owner.** [D]
- **Whether the owner can replay every kind of definition,** with the binary log on and off, is [G-13]. A kind it cannot replay excludes the datasets that use it, by name.

**What gets no MySQL template.** [D]

| Database | In version 1 | Why |
|---|---|---|
| Above 512 MiB of allocated bytes, measured at build | no template, no copies: exit 4, `too-large` | A logical copy's time and undo grow with its rows. The number is fixed by the build's measurements before the freeze. |
| `oracle_oe` and `oracle_hr`: a database that refers to another, or is referred to | no template, no copies: exit 4, `dependency-group` | A copy of one would point at the other's shared working copy (F-11). |

**A MySQL working copy still resets from the image.** A reset from a template waits (section 11). Its gap against DL-077 item 1 is recorded. [108-10]

**The binary log is configurable, and the image keeps it on:** `engines: {mysql: {binary_log: false}}`. Every logical copy is written to it a second time (F-10). [G-18]

### 2.5 SQLite

- **The template is the image's file,** and "read-only" is its mode. There is no server and no account.
- **The build writes a manifest** beside the files it already writes: `build/sqlite/templates.json`, with the tag `megasamples-manifest/1` and each file's name, size and SHA-256 (`SM:README.md:173`). A caller elsewhere works from a copy of that directory. No command stages it. [D]
- **A copy,** in the caller's directory:
  1. the name's lock file is locked; the sidecar is made with exclusive creation: `reserved`, then `issuing`;
  2. the template is copied to its retained name in `.megasamples/`, synced, and held to the manifest's SHA-256;
  3. it is published by a hard link to its final name, which fails if that name exists. **The retained link stays.** [G-19a, G-19b]
- **A drop** removes the final name only if it is the same file as the retained link; then any `-wal`, `-shm` or `-journal` beside it; then the retained link; then the sidecar.
- **Nothing goes over the network.**

### 2.6 Which databases get a template, and the storage

**The default selection is `core`:** every physical database whose base dataset is of tier `core` or `core-medium`, less MySQL's exclusions (2.4). It is configured for each engine by `engines.<engine>.templates`: a selector, a list of databases, or `none`. It is baked. [D]

**Version 1 does not bound storage.** [D: review 3's finding 15. Round 3's admission by reserved headroom had no input for an image reset, an off-host file or a retained log. It waits (section 11), and version 1 claims none of it.]
- **A template is its database again.** A live copy is its database again. A PostgreSQL reset needs its database once more while it runs.
- **The build measures and prints** each template's allocated bytes, appended datasets included (F-9), and each copy's time. A deployer sizes a volume from that.
- **`max_copies`** bounds how many copies a namespace's owner can have through the CLI. It bounds no bytes.
- **When the disk fills,** every template and every working copy that was not itself being changed must stay whole, and the command must say which exit it is. [G-9, G-17]

## 3. The CLI for scripts

### 3.1 The commands

| Command | As | What it does |
|---|---|---|
| `megasamples copy create ENGINE:DATABASE --prefix P --label L [--lease DURATION]` | the namespace's owner | 2.2. It returns the issued name and the identity. |
| `megasamples copy show ENGINE:NAME` | the owner | The copy's state (2.2), its lease and its proof. It changes nothing. |
| `megasamples copy list ENGINE --prefix P [--label L]` | the owner | Every object and every row in the namespace, with its state. |
| `megasamples copy renew ENGINE:NAME --identity ID --lease DURATION` | the owner | Sets the lease's end. |
| `megasamples copy release ENGINE:NAME --identity ID` | the owner | Ends the lease now. |
| `megasamples copy drop ENGINE:NAME --identity ID [--wait SECONDS]` | the owner | Dropping a copy that is already gone succeeds. |
| `megasamples copy sweep ENGINE --prefix P [--dry-run]` | the owner | What it removed, and what it kept and why. |
| `megasamples reset …` | where the service runs | 3.5. |

- **`copy` needs a TCP path to the engine's port, and nothing else:** no container runtime, no checkout. For SQLite it needs `--templates DIR` and `--dir DIR`. [D]
- **`reset` runs where the service runs,** as today (F-1). A reset asked for from elsewhere waits (section 11). [108-6]
- **`ENGINE:DATABASE`** follows the reset's own pairs (`SM:megasamples/reset.py:6`).
- **A copy owner's credential may be used from another machine only after its engine's confinement gate has passed:** [G-29] on PostgreSQL, [G-11b] on MySQL. Until then the product does not claim it, and says so. [108-5]

### 3.2 Output

- **One JSON document on standard output, on one line,** for every `copy` command, and for `reset` with `--json`, `--status` or `--reconcile`. Everything else goes to standard error. [D]
- **Its envelope:** `schema`, `interface`, `command`, `ok`, `exit`, `volume`, `result`, `error` and `warnings`.
  - **`volume` is the identity of the server's data volume** (3.5).
  - `error` holds a stable `code`, a `message`, and the `operation` or copy `identity` a caller reads the state by.
- **A copy's result:** its `name`, `identity`, `engine`, `database`, `prefix`, `label`, `state`, `revision`, `lease_until`, its `endpoint` (the host and port the caller used, or the file's path), its `owner`, the `template`'s build id and registry digest, and the engine's `version`.
- **No credential is ever in it.**

### 3.3 Exit codes

| Code | Meaning | What it promises |
|---|---|---|
| 0 | done | as asked |
| 1 | a defect in the CLI | nothing; treat it as 8 |
| 2 | wrong usage | no engine was contacted |
| 3 | the engine cannot be reached, or the sign-in is refused | nothing changed |
| 4 | not offered here: no template, `too-large`, `dependency-group`, or a failed gate's command | nothing changed |
| 5 | refused by a rule: namespace, label in use, identity or state not as expected, the limit, an unknown format, an unsettled operation, a missing `--discard` | nothing changed |
| 6 | busy | **nothing changed, and the CLI confirmed it** |
| 7 | failed | **nothing is left changed, and the CLI confirmed it** |
| 8 | unsettled | **a durable record describes what is there** |

| Command | 6 means | 7 means | 8 is read by, and settled by |
|---|---|---|---|
| `copy create` | the namespace lock could not be had; no row was written | — | `copy list --label`. **An interrupted create is not settled by any command:** it is kept (2.2). |
| `copy drop` | sessions remained at the end of the wait; the copy is untouched | — | `copy show`; `copy drop` again |
| `copy sweep` | — | — | `copy list`; `copy drop` for each `dropping` one it names |
| `copy renew`, `release` | another change holds the name | — | — |
| `reset` | another reset holds the target's lock, or sessions were found; **the target is as it was** | it failed before anything of the target changed | `reset --status`; `reset --reconcile` |

- **A command that cannot confirm what 6 or 7 promises returns 8.**
- **`copy create` never returns 7.** A create that fails after its reservation leaves a row and perhaps an object, and those are kept: exit 8.
- **A caller that meets a code it does not know treats it as 8.**

### 3.4 Credentials

- **`copy`: one account, one password,** from `--password-file PATH` or `--password-stdin`. A file must be the caller's own and closed to others, or it is refused before it is read. Never an argument, never the environment; nothing ambient is read (`PGPASSWORD`, `PGPASSFILE`, `~/.pgpass`, `MYSQL_PWD`, client option files). [D]
- **`reset`: the checkout's `.env`, as today,** read once, as a file. [D: review 2's finding 10; review 3's finding 14.]
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

### 3.5 Resets

**One reset of one target at a time, and one unsettled operation for each target, on every path.** [108-5] [D: review 3's finding 4.]

**The paths version 1 has:**

| Target | Path |
|---|---|
| A PostgreSQL database with a template | from the template, into a transient, with a swap |
| A PostgreSQL database with no template | **from the image, into a transient, with the same swap** [108-5] |
| A MySQL database | from the image, in place, as today |
| A SQLite database | from the image's file, as today |
| A whole engine | the volume replaced from the image, as today |

**An operation.** Each reset of each target is one operation, with an identity.
- **The caller may give it:** `--operation ID`, with one target. An identity that already has a record is refused: exit 5, `operation-exists`. So a caller that lost a reply asks again under the same identity and is told what happened. With several targets, or without the option, the CLI issues one for each and returns them in its document.
- **Its record is written before each step, and its terminal outcome is kept for the life of the volume:** `done`, `rolled-back` or `failed`.
  - For a database on a server, it is a row in `megasamples.operations`.
  - For a SQLite database and for a whole engine, it is a file where the service runs, outside the volume.
- **Admission.** A reset is admitted only if the target has **no operation that is not terminal.** Otherwise: exit 5, `unsettled`, naming it. Only `reset --reconcile` settles one, and it settles that operation only.
- **`megasamples reset --status [--operation ID]`** answers: `running`; `unsettled`, at a phase; a terminal outcome; or **`unknown`: this volume has no record of it.** It gives the volume's identity with every answer. [D: review 3's finding 12: round 3 said "not found means it never started".] `unknown` on the volume the caller started against means it never started. `unknown` on another volume means only that the volume was replaced since.

**The lock is on the server, and the session that changes is the session that holds it.**
- **PostgreSQL:** the reset runs as one session of the superuser inside the container, which takes the target's advisory lock first and keeps it to the end. [G-7] The image path's restore worker writes only into that operation's transient.
- **MySQL:** the stream the restore worker reads begins with a statement that takes the target's named lock and fails if it cannot. So the session that drops and loads holds the lock, and a worker that outlives the CLI still excludes the next reset. [G-26m]
- **SQLite and a whole engine:** the lock file where the service runs, as today (F-3). Both are possible only there.
- **If an engine's lock gate fails, that engine's reset of one database is not offered.** A whole engine's reset remains.

**A PostgreSQL reset, by either path.**

| Step | What happens | The phase |
|---|---|---|
| a | The lock. The operation's row. | `building`, written first |
| b | `CREATE DATABASE <database>__new_<id> OWNER admin`: from the template; or empty, and the worker restores the image's dump into it. **Its OID is recorded as soon as it exists.** Then its grants are given, in it (4.1). It holds no `CONNECT` for anyone but its owner. | `built`, written after |
| c | **The door is closed:** `ALTER DATABASE <database> ALLOW_CONNECTIONS false`, in one transaction with the phase. [G-3a] | `closed` |
| d | The session decision (below). | `closed` |
| e | **In one transaction:** the working copy is renamed to `<database>__old_<id>`; the new one is renamed to `<database>`; its `CONNECT` is granted to the working groups; the phase is set. [G-3b] | `swapped` |
| f | `DROP DATABASE <database>__old_<id>`. | `done`, written after, and kept |

**Reconciling it:**

| The row's phase, with the lock free | What reconciling does | Outcome |
|---|---|---|
| `building` | **Nothing is dropped.** A transient whose OID was never recorded is kept and reported. | `rolled-back`: the working copy is as it was |
| `built` | drops the transient, if its recorded OID matches and it has no session; otherwise keeps and reports it | `rolled-back` |
| `closed` | **opens the door again;** the transient as above | `rolled-back` |
| `swapped` | drops the old transient, by its OID | `done` |

- **Steps c and e are each one transaction or the swap is not built.** If [G-3a] or [G-3b] fails, PostgreSQL's reset of one database returns to the deciders.
- **A crash in step c or d leaves the working copy closed** until someone reconciles. It is kept short by doing all the copying first, and the CLI opens the door again when it is interrupted by a signal.

**A MySQL reset, from the image, in place.** Today's procedure (F-4), under the lock and the record, and corrected in three ways:

| Step | What happens | The phase |
|---|---|---|
| a | The operation's row. | `started` |
| b | The session decision (below). **Each declared writer's grant on this schema is revoked, and that account's sessions are ended.** The suspension is written in the row. [G-27] | `excluding` |
| c | The worker: the lock, then the image's dump, which drops the schema and loads it. | `loading`, written first |
| d | Each table's row count **and checksum** against the image's own, read from the pristine container that is still running. | `loaded` |
| e | **The declared grants are applied again.** | `done`, written after, and kept |

- **It cannot be undone after step c begins.** Reconciling says which it does:

  | The row's phase, with the lock free | What reconciling does | Outcome |
  |---|---|---|
  | `started`, `excluding` | applies the declared grants again | `rolled-back` |
  | `loading` | runs steps c to e again, under the same operation | `done` |
  | `loaded` | **checks, and applies the grants. It does not load again.** | `done`, or `failed` with the tables that differ |

- **`done` requires both:** the data checked, and the declared grants in place. [D: review 3's finding 6.]
- **A start of the server during an unsettled reset does not reopen it.** The start applies declared grants (4.6); it leaves out any that an unsettled operation's row records as suspended.
- **A database of a dependency group is not reset singly:** `oracle_hr` or `oracle_oe` alone is exit 4, `dependency-group`. A reset of one would leave the other pointing at rows that are gone (F-11), and today's path does exactly that. They are reset with the whole engine. [D: review 3's finding 16: narrowed, on the path that is kept.]
- **If [G-27] fails,** a MySQL reset of one database is not offered where a writer is declared.

**A SQLite reset** is today's (F-4), under its lock file and an operation's file. It stops the consoles that read the files, **so it always needs `--discard`.**

**The session decision.** [108-2] **A reset preserves sessions unless it is told otherwise.**

| | What happens when people's sessions are on the target |
|---|---|
| **By default** | The reset stops: exit 6, saying how many sessions and whose. On a terminal it first warns, and asks. |
| **`--discard`** | The warned choice, given as an option: the sessions are ended and the reset goes on. |
| **`--unattended`** | For automation. One database. Any session is a refusal before any change. It never takes `--discard`. |

- **The product's own idle console sessions do not count.** [108-2] A session from one of the stack's console containers, with no statement running and no transaction open, is ended without `--discard`: nothing of anyone's is lost by it. One with a statement or a transaction counts as a person's. Whether the engines show that is [G-32p, G-32m].
- **On PostgreSQL** the door is closed first, so nobody arrives between the look and the swap.
- **MySQL has no door.** A session can name any schema, and an idle one that is not a console's cannot be told from a person at work. **So on MySQL `--unattended` is refused before any change:** exit 4. A person's reset there needs `--discard`.
- **This changes today's default,** which disconnects (F-4). It enters version 1 at the freeze, with an impact note and migration instructions, and every caller changed in the same work: `make reset`, the upgrade route and the README. [108-2]

**A whole engine's reset.** [108-9]
- **It refuses before any change unless it is given `--discard`.** It replaces the volume: every copy, every session and every account that is not the image's goes with it. There is no drain in version 1.
- **The service's record carries an identity for each volume,** made when a volume is first started. Every document carries it (3.2). **A `copy` command reads it when it connects and again before each step that changes anything; if it differs, the command changes nothing more and returns exit 8, naming both identities.** So a command that straddles a replacement acts on nothing in the new volume. [G-33]
- A name or an identity that a caller kept from the old volume finds nothing in the new one: `copy show` says `absent`, and `copy drop` succeeds on nothing.

### 3.6 Limits

| Limit | Value | Past it |
|---|---|---|
| A whole name | 63 bytes | the build refuses the dataset or the prefix |
| A prefix; a label | 16 bytes; 24 bytes | exit 2 |
| A prefix, label or name that is not of its form | never valid | exit 2, before any connection |
| A namespace's live copies | `max_copies`, 32 by default | exit 5, `limit` |
| A lease | at least one minute; at most seven days; 24 hours by default | exit 2 |
| Connection timeout; `--wait` | 10 seconds; 0 | exit 3; exit 6 |

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

**Reading is one group. Writing is granted inside each database.** [D: review 2's first P1, which review 3 found closed at design level.]
- **The template carries no write grant to any group.** It grants row changes, and `USAGE` on sequences, to `pg_database_owner` alone. In any database that is its owner. [G-23]
- **So in a copy, its owner can change rows, and no other ordinary account can.** Version 1 has no other writer of a copy.
- **In a working copy, `admin` grants row changes to `megasamples_working_write`,** at build and in each reset (3.5, step b).
- **So no account holds a write grant in a database of another scope,** and nothing combines.

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
| P-7 | **The published inventory is the one authority:** every executable signature, with its reason, generated from the candidate. | So that there is one list. |

**What stays:** no `TEMPORARY` for `PUBLIC`; no large-object creation; no user routine for a reader; the two rewritten `employees` views; the closed defaults for `admin` and `postgres`; MySQL not claimed strict (F-14).

### 4.3 The hook and the event trigger

Input to an independent review of **the final hook.** Each finding is from reading `PR14:` at the cited lines; none was run.

| # | Finding | Where | Disposition |
|---|---|---|---|
| H-1 | **Every role but `demo` and `admin` may be left unable to call any built-in routine,** an operator's function among them; and `admin` could not repair it (F-13). [G-5a] | `PR14:engines/postgres/init/10-read-profile.sql:14-15`, `:23-35` | If reproduced: P-1. |
| H-2 | **The hook's `REVOKE` may do nothing, and succeed,** when the creator is not the new owner and does not inherit the owner's rights. [G-4a] | `PR14:engines/postgres/read-policy/read_policy.c:31-38` | Rule 1, and rule 3's confirmation. |
| H-3 | **An error in the hook after the copy may leave the copied files with no database.** [G-4b] | `PR14:engines/postgres/read-policy/read_policy.c:24-38` | **If reproduced, it is resolved before the merge:** everything the hook can know is refused before any file is copied; the step after the copy may not raise for a reason of its own. If a raising path remains, or the leak shows with no hook at all, it returns to the deciders. |
| H-4 | **The role name `admin` is compiled in.** | `PR14:engines/postgres/read-policy/read_policy.c:32-33` | The hook names no account. |
| H-5 | **The hook closes `TEMPORARY` only.** | the same | `CONNECT` too. |
| H-6, H-7 | **A role may change its own password, its own settings, and its own default privileges.** [G-6] | — | Rule 4. |
| H-8 | **`NOTIFY` is a statement, not a routine** [I]; the page says notifications "receive no `demo` grant". | `PR14:docs/strict-read-account.md:3` | Correct the page. `NOTIFY` stays allowed. |
| H-9, H-10 | **The event trigger names `admin`,** and is enabled in the ordinary way [I]. | `PR14:engines/postgres/read-policy/read_policy--1.sql:9-11`, `:19-20` | It checks that the role exists; `ENABLE ALWAYS`. |
| H-12 | **A policy image started on data from before the policy** would run with the hook and without the grants. | `PR14:engines/postgres/Dockerfile:83` | The build writes the policy's version into the data directory; the start wrapper refuses one whose marker is missing or older. |
| H-15 | **A role that may create databases can create one of any name, from any template.** | PostgreSQL's own rule | Rule 2. |

**The four rules.** [D]

| # | When | What |
|---|---|---|
| 1 | Before `CREATE DATABASE` | Refuse, when the creator would not hold the new owner's rights. |
| 2 | See below | The confinement. [108-5] |
| 3 | After `CREATE DATABASE` | Close `CONNECT` and `TEMPORARY` on the new database to `PUBLIC`; then confirm it. |
| 4 | Before `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES` | Refuse, when the caller is neither a superuser nor a holder of `CREATEROLE`. [G-6] |

**Rule 2, exactly.** [D: review 3's finding 7: round 3's "begins with the prefix" let `lab` reach into `lab2`, and its template test checked a name's ending.]
- **A namespace is known to the hook by its marker role:** `megasamples_copy_<prefix>_owner`. An account is that namespace's owner if it is a member.
- **A registered template** is a database marked a template, accepting no connections, owned by a superuser, **whose comment carries the service's template tag.** Only its owner can set that comment.
- **`CREATE DATABASE` by a namespace's owner is refused unless** its source is a registered template `<database>_start`, **and** its name is exactly `<prefix>_<database>_` followed by twelve hexadecimal digits, with that `<prefix>` one of the namespaces it owns and that `<database>` its source's.
- **`ALTER DATABASE … RENAME` by a namespace's owner is refused.** Version 1 never renames a copy.
- **`CREATE DATABASE` or a rename, by any other role that is neither a superuser nor a holder of `CREATEROLE`,** is refused when the new name falls in a namespace: it equals, or begins with, a namespace's prefix followed by an underscore. **Outside every namespace such a role creates as PostgreSQL lets it.** So a consumer's own role that may create databases keeps that right, and cannot take a name in someone's namespace.
- **It names no account and holds no state.** It reads the catalog.

**What rule 2 is for.** A PostgreSQL namespace owner's credential can be used away from the service only once [G-29] shows the rule refusing direct SQL. **A failed G-29 returns to the deciders.** [108-5] Rule 2 does not bound bytes: an owner can still fill the disk with copies of its own.

### 4.4 MySQL's accounts

Decided here [D]. **Every schema pattern has each underscore escaped.** [G-11a]

| Account | Privileges | Change |
|---|---|---|
| `root@localhost`, `root@'%'` | everything | none |
| `admin@'%'` | everything, with the grant option | none |
| `demo@'%'` | `SELECT, SHOW VIEW` on each working sample schema, by its exact name; `SELECT` on `megasamples`' registry and service tables; and on each foreign namespace marked `demo_reads`, by its pattern | **narrowed** from `*.*` [G-11c] |
| **a namespace's owner** | on its own pattern, such as `copy\_%`: what making, filling, using and dropping a copy needs, **without the grant option.** On each template, by exact name: `SELECT`. On `megasamples`: `SELECT`, and row changes on its own ledger. | **new**; locked until its key is set [G-11b] |
| **a declared reader; a declared writer** | 4.6 | **new** |

- **`demo` no longer reaches the `mysql` schema,** nor a template. That is the first of line 10's two items (LR: line 10).
- **`demo` reads a consumer's own schemas only where the configuration marks that foreign namespace `demo_reads`.** By default it reads none.
- **MySQL's `admin` is not narrowed.** [D: narrowing it needs partial revokes, under which a pattern's wildcards may stop working.]
- **An account that manages accounts can change the service's own.** A deployer or a consumer may add one; the product ships none. It is a consideration for whoever adds one (5.2), not a gate of the product. [D: review 3's finding 18.]
- **MySQL stays not claimed strict:** named locks, and the two definer views of `employees`, are as F-14 found them.

### 4.5 An account changing its own password

The second of line 10's two items. A read account's credential is shared: by the consoles, the probe, and whoever is given it. A holder who changes it locks the others out, and can set it to a value everyone knows.

| Engine | In version 1 |
|---|---|
| **PostgreSQL** | **Refused,** by the hook's fourth rule, for every role without `CREATEROLE`. [G-6] |
| **MySQL** | **Not known to be possible. [G-16] establishes it first:** it tries every statement by which an account can change its own password, and each mechanism of the pinned server that might refuse it, and reports each by name. |

- **If G-16 finds a refusal that keeps `demo` usable,** it is built. If that would add to section 0's surface, it returns to the deciders first.
- **If it finds none,** the product says that MySQL cannot refuse it, and version 1 has what limits the harm:
  - **a key of its own for MySQL's `demo`,** so that it can be kept and rotated apart;
  - **a declared reader for each consumer** (4.6), so that one consumer's change locks out only itself;
  - **the probe,** which signs in as `demo` and so shows the engine unhealthy; and **every start,** which applies the configured passwords again (F-6).
- **A command that checks and repairs accounts waits** (section 11).

### 4.6 Declared readers and writers

**Who may read or write is declared in the configuration.** [108-5] Version 1 has no command that enrolls anyone.

```yaml
accounts:
  readers:
    - {name: reader_a, scopes: [working]}             # the working copies
    - {name: reader_b, scopes: [working, copy]}       # and the copies of namespace `copy`
  writers:
    - {name: editor_a, scopes: [working]}             # the working copies' rows
```

- **Each declared account is one the service makes.** Its name is checked like a prefix, and may be none of the service's own. It is neither a reader and a writer at once, nor an existing account adopted.
- **It is locked until its key is set:** `<NAME>_PASSWORD`.
- **A reader's scopes** are the working copies, and any namespaces. **A writer's scope is the working copies, and only that:** in version 1 a copy's one writer is its namespace's owner.
- **Its grants are exactly what is declared:**

  | | PostgreSQL | MySQL |
  |---|---|---|
  | A reader of the working copies | member of `megasamples_working_read` | `SELECT, SHOW VIEW` on each working schema, by exact name |
  | A reader of a namespace | member of `megasamples_copy_<prefix>_read` | `SELECT, SHOW VIEW` on the namespace's pattern |
  | A writer | member of `megasamples_working_write` | the reader's, and `INSERT, UPDATE, DELETE` on each working schema |

- **The start applies it,** every time: it makes each declared account that is missing; sets each keyed one's password; locks each unkeyed one; **locks every account it made before that is declared no longer;** and makes the grants exactly the declared ones. The configuration is the one authority; nothing else is replayed or repaired. [D: review 3's finding 17.]
- **Each reset applies it again, under its exclusion** (3.5): a new PostgreSQL working copy is granted to the same groups; a MySQL schema's grants are given again before `done`.
- **A writer writes rows, and nothing else:** no definition, no account, no registry. A reset restores what it changed.
- **Nobody is declared by default.** The capability is built and tested; whom a deployer declares is the deployer's.

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
| `demo`; a declared reader | read what it is granted. On MySQL: take any named lock; change its own password, unless G-16 finds a refusal | the read profile on PostgreSQL; its grants on MySQL |
| a declared writer | change rows of every working copy | no definition change; a reset restores |
| **a namespace's owner** | **every copy of its namespace, whoever made it:** read, write, drop. Fill the disk with copies. On MySQL, take any named lock, and so make a copy or a reset report busy. | PostgreSQL: the hook [G-29]. MySQL: nothing outside its pattern, and no granting [G-11b]. |

- **One credential is one trust domain.** Two runs that share a namespace owner's credential can change each other's copies, and the product reports nothing that says otherwise. [D: review 3's finding 10: `exclusive` is withdrawn.] A deployer who must keep two apart gives each a namespace.

## 5. Defaults, and what a deployer weighs

The product does not know where it runs (DL-107).

### 5.1 Version 1's defaults

| # | Default | Mark |
|---|---|---|
| 1 | **Every published port binds to loopback,** as today (F-28). Version 1 has no setting that widens one. | [R] |
| 2 | **No privileged account has a published password, even on loopback.** | [108-5] |
| 3 | **A bundled console holds no privileged access.** | [108-5] |
| 4 | **`demo` keeps its published password.** | [108-5] |
| 5 | A namespace's owner, a declared reader and a declared writer are **locked until keyed.** Nobody is declared. | [D] |
| 6 | **A reset preserves sessions unless told otherwise.** | [108-2] |
| 7 | `demo` reads no consumer's own schemas. | [D] |

**Default 2, exactly.** [D: review 3's first P1. Round 3 trusted everyone who could reach loopback: a second user of the machine, a container on the stack's network, a client at the far end of a tunnel. And it looked for an unset key, which a key set to the published value passes.]
- **The privileged accounts are `admin` on both engines, `postgres`, and both of MySQL's `root`.**
- **The image holds none of them usable over the network:** each is baked with no password that signs in.
- **The start gives one a password only from its key, and tests the value:** a key that is unset, **or set to the value published today,** leaves that account locked, and the start says which.
- **`megasamples up` writes a private value for each such key that is missing,** into the checkout's `.env`, closed to others, and never prints it. So the quick start still works, and its `admin` password is in a file the deployer owns.
- **That holds on every path that starts an engine:** `megasamples up`, the generated Compose file used directly, and the image run by hand. Each of the last two, given no key, has no usable privileged account. [G-35p, G-35m]
- **The reset, and everything else that signs in as a superuser, reads the same keys** (3.4). With none set it cannot run, and says so.

**Default 3, exactly.** [D: review 3's second P1.]
- **No console is given a privileged password.** phpMyAdmin's second server asks for a sign-in instead of holding `admin`'s; DbGate's and CloudBeaver's `admin` connections are stored without a password, or not stored (F-31).
- **`demo` stays signed in,** as the consoles open today.
- **So a browser that reaches a console gets `demo`,** and privileged access only by typing a password it must already have.

**Defaults 2 and 3 may be one bounded pull request of their own, merged before the build.** [108-5]

### 5.2 What a deployer weighs

Version 1 gives these mechanisms. Which to use is the deployer's.

| What to weigh | What version 1 gives | What stays the deployer's |
|---|---|---|
| **Who can reach the engines** | Loopback publication. | Any forward, proxy or shared network. **Version 1 has no setting for a wider listener and no rule about where a client comes from** (section 11): whoever reaches the port can try every account. |
| **The transport** | PostgreSQL's passwords are not sent (`SM:ARCHITECTURE.md:166-167`). The product configures no TLS (`MR:` B-04). | A tunnel, or a network the deployer trusts. |
| **Passwords** | One key for each account. **Rotation:** set the key and start again. **Revocation:** clear a key, and the account is locked at the next start. | When, and who is told. |
| **A shared read credential** | `demo` is one account. On MySQL a holder may change its password, unless G-16 finds a refusal. | A declared reader for each consumer that must not be able to lock out the others; `demo` only for the consoles. |
| **Who makes copies** | A namespace and an owner for each consumer that must be kept apart. | How many to bake, and which to leave locked. |
| **A copy owner's credential away from the service** | Claimed only once that engine's confinement gate has passed (3.1). | **It can still fill the disk.** Version 1 bounds no bytes. |
| **A consumer that manages accounts** | A foreign namespace keeps the product out of the consumer's objects. | An account that manages accounts may be able to change the service's own. The product ships none and tests none; whoever adds one tests what it reaches. |
| **Handing a credential over** | Nothing: **it is the deployer's own procedure,** which the README describes: one credential, alone, never the `.env`. [108-11] | The channel, and the record of it. |
| **Write access to the samples** | A declared writer (4.6). | Whether to declare one. |

### 5.3 Changing a deployment, and the runbook's split

- **A new image renews the data volumes.** Everything made on the old ones goes. Declared accounts return at the start, from the configuration.
- **Image and data must match.** On PostgreSQL the policy image refuses data without its marker (H-12). On MySQL nothing refuses. SQLite has no such pairing.
- **The runbook is split in this work.** [108-3]
  - **The product keeps a short, tested, general upgrade route, with its helpers:** replace the images, keep the old volumes until the new ones are checked, go back by the kept volumes. The quiescence gate and the state checks are helpers of that route, and their tests stay with them.
  - **The live-upgrade runbook moves to DataIntent's side,** as the procedure of its rollout's plan, pinned to a sql-megasamples revision (F-29).
  - **The README's dated paragraph about one deployment, and its paragraphs that take LAN forwards for granted, leave it,** or become a profile.
  - The split is rehearsed before that rollout's approval (7.2).

## 6. The contract and its versioning

| Thing | Where it lives | Its own version |
|---|---|---|
| The JSON envelope and each result | standard output | `schema` |
| The commands and options of section 0; the exit codes and their promises; the lock protocol of 2.2 and 3.5; the names; the `.env` keys; the configuration keys of section 0 | the command line, the process, the server, two files | `interface` |
| The service's record, **with the volume's identity** | a comment or a table in the server | the tag `megasamples-service/1` |
| A template's record | the same | `megasamples-template/1` |
| A copy's row; a copy's comment on PostgreSQL | a ledger | `megasamples-copy/1` |
| An operation's record, **with its identity and its terminal outcome** | `megasamples.operations`; a file where the service runs | `megasamples-operation/1` |
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

Examples of configuration. Neither is a premise of the product. Round 3's three others (a shared server, a container platform, remote access) each needed a setting that waits, and are not in version 1.

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
| **Declared accounts** | A reader for each LAN consumer, if G-16 finds no refusal. **No writer:** its first is the two deciders' decision, after the controls of `ED:` R-39. |
| **MySQL's binary log** | Its choice at its rollout's approval, after G-18. |

**Its policy,** each a choice among 5.2's mechanisms:
- **No administrator's or superuser's credential leaves the machine,** `di_admin` and its fixture and provisioning credentials included.
- **Whether to send a namespace owner's credential elsewhere is DataIntent's.** It sends none before that engine's gate: G-29 on PostgreSQL, G-11b on MySQL. Meanwhile it records DL-077 item 3's "from a separate machine" as unmet for that engine. Before it provisions `di_admin` on MySQL beside a credential that has left, it tests what `di_admin` can do to the service's accounts. [108-1]
- **It keeps the record of each sending,** an uncertain delivery included, and holds a send it cannot record. [108-1]
- **MySQL's `demo`, if G-16 finds no refusal,** gets a key of its own, rotated at its rollout, which ends the value its LAN machines already hold; each of them reads with its own declared reader.
- **Its automation resets with `--unattended` only,** so one database at a time and no MySQL working copy. [108-1]
- **A long run renews its lease.** `ED:` criterion 11, "never a copy in use", is recorded as **not passed** for an idle MySQL session and an open SQLite file whose lease has ended.
- **A result that needs to be the only writer** (`ED:` R-35) is recorded as **unmet** wherever two runs share a namespace owner's credential. It holds only for a namespace one run uses alone.
- **After its deployment, loosening one of these is the owner's** (DL-106), as its own rule.

**What else version 1 means for it.**
- A copy's name is issued; its harness keeps the name and the identity, and finds a copy by its label after a lost reply.
- Its edit tests' writer of a **copy** is that namespace's owner in version 1. A writer of a copy that is not its owner waits (section 11).
- The provider's list of databases does not gain the templates: it leaves out every database marked as a template (F-17). A raw catalog query shows them; the registry does not list them. Each is tested apart.
- A fixture role cannot connect to a working copy. The fixture grants `EXECUTE` on its own routines, and `TEMPORARY` where a case needs it. A fixture role cannot change its own password on PostgreSQL.
- Its harness maps the exit codes (`ED:` 4.2): 3 and 4 are Not run; 2, 5 and 7 Failed; 6 a deferral; 1 and 8 Failed, and it reads the state first.

**Its one rollout** (DL-103; DL-105). The plan is DataIntent's record; this is what version 1 asks of it.

| # | Step | It must show |
|---|---|---|
| 1 | This cut reviewed, on scope and gates. Then **version 1's gates** (8.1), on an isolated stack. Then this record revised and reviewed to two clean rounds. | DL-108 item 12. |
| 2 | **The credentials and consoles change** (5.1), as its own pull request if it is split out. | Merged before the build. |
| 3 | **The build,** test-first, on a branch that merges pull request #14's branch first (section 9). | 8.2. |
| 4 | **DL-078's README,** on the same branch, reviewed. **The runbook's split,** rehearsed. | Section 10; 5.3. |
| 5 | **The branch's candidate,** built in an isolated store. | The dataset matrix, the image tests and every native suite Passed. |
| 6 | **DL-087's acceptance is recorded.** | Nothing from step 7 on comes before it (F-26). |
| 7 | **DataIntent's comparison against that candidate,** the read account's admission among it. | Below. This is DL-085 item 3's condition. |
| 8 | **The reviews:** the independent review of the final hook; Fable's and Astra's blessing on one head (DL-086). | On the head step 7 compared. |
| 9 | **The merge into `main`.** | Version 1 of the contract is fixed here. |
| 10 | **One build of the final `main`,** qualified: the suites again, and the comparison again. | This is the build that is deployed. |
| 11 | **The two deciders' approval** of one exact plan the coordinator directs. | A plan that changes afterwards goes back to them. |
| 12 | **The rollout,** then DataIntent's accepting run on the live instance. | Accepted only then. |

- **The comparison is all five parts** (F-24): C1, PostgreSQL's suites; C2, the MySQL provider probe, since `demo`'s grants change; C3, SQLite freshly staged, since the image is rebuilt; C4, the observed identities, since every build id changes; **C5, both controls:** an export refused with an empty stream after an elevation, and when the fresh check cannot be made, on each isolated server only. One DataIntent revision and one inventory across steps 7, 10 and 12.
- **It compares two builds of the service on the same engine versions,** and its evidence says so.
- **Before the rollout the live instance still has today's profile.** The candidate half expects `demo` admitted; the live half expects it **refused**, as a recorded baseline. Which route the rest of the live half takes is DataIntent's to name.
- **A part whose prerequisite does not exist** waits, or goes to the deciders by name. It is not left out.
- **Its verification is generated from the approved account state.** [D: review 3's finding 21: round 3 asked every account to sign in, and a locked spare cannot.] An account that is keyed signs in, and a wrong password is refused as an authentication failure; **an account that is locked is refused;** the probe and each console sign in as the account they are meant to, and a console offers nothing privileged.
- **Its rollback** is by the kept volumes (5.3). Where MySQL's `demo` was rotated, the old shared value is in force again afterwards.

## 8. Gates and tests

### 8.1 Version 1's feasibility gates

**These run next, on an isolated stack, before this record is reviewed to closure.** [108-12] Each is one assertion about an engine's own behaviour, with no CLI code. **"Withholds" is everything of version 1 that depends on it;** none of it goes on using what failed, and a required capability that fails returns to the deciders. [D: review 3's finding 18: round 3's gates were compound, and some fallbacks kept what had failed.]

**PostgreSQL.**

| Gate | Definition | A test that tells | Withholds if it fails | Serves |
|---|---|---|---|---|
| **G-1a** | A database marked a template, accepting no connections and owned by a superuser refuses every connection. | Each account, the superuser over the network and in the container, connects: all refused. Control: with connections allowed, one succeeds. | every PostgreSQL template, copy, and reset from a template | item 5, first |
| **G-1b** | A role with `CREATEDB` alone copies it; two copies at once, and one during another, succeed. | Two sessions create from it at the same moment; both databases exist and match. | the same | item 5, first |
| **G-1c** | `admin` cannot alter, rename, drop or comment on it. | Each statement as `admin`: refused. Control: as `admin`'s own database, each succeeds. | the template's registration; rule 2 | item 5, first and fifth |
| **G-2** | A copy carries each object's owner and grants to group roles, the default privileges, the extension and the event trigger; it does not carry `CONNECT`, the owner or the comment. | A fingerprint of each, in a template's twin and in its copy. | the read group; 4.1's `CONNECT` table | item 5, first and fourth |
| **G-3a** | `ALTER DATABASE … ALLOW_CONNECTIONS false` and a row's update commit or roll back together; a closed database keeps its sessions and refuses new ones. | Roll the transaction back: the database is open and the row unchanged. Commit: a new connection is refused, an old one still answers. | PostgreSQL's reset of one database | item 5, third and eighth |
| **G-3b** | Two renames, a `CONNECT` grant and a row's update commit or roll back together; a rename needs no session on either database. | Roll back: both names are as before. Commit: a reader connects to the new one under the old name. | the same | item 5, third and eighth |
| **G-4a** | `REVOKE … FROM PUBLIC` on a new database, by a creator that is not its owner and does not inherit the owner's rights: what it does. | Such a creator creates `OWNER other`; `PUBLIC`'s privileges are read afterwards. | rule 1's form | item 5, fourth |
| **G-4b** | An error raised after `CREATE DATABASE` has copied its files: what files remain. Also with no hook loaded. | Force the error; list the data directory against the catalog. | H-3's resolution, or the deciders | item 5, fourth |
| **G-5a** | On pull request #14's candidate, a role other than `demo` and `admin` cannot call an operator's function. | A fresh role runs `SELECT 1 = 1`. Then with the list on `PUBLIC`: it succeeds. | P-1 | item 5, fourth |
| **G-5b** | `pg_export_snapshot`, `pg_current_snapshot` and `pg_database_size` change no stored object and assign no transaction id; a snapshot exported under the floor is imported by a second session under it. | The transaction id and the catalog before and after; the import. | P-3, P-5 | item 5, fourth |
| **G-5c** | A trigger's body runs with the rights of the account whose statement fired it. | A writer's insert fires a trigger that calls a built-in outside the floor: refused; with the write list: accepted. | P-6; a declared writer | item 5, fourth and seventh |
| **G-6** | A role without `CREATEROLE` can alter, by `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES`, itself and nothing else. | Each statement, on itself and on another role. | rule 4. PostgreSQL is then treated as MySQL is under G-16. | item 5, fourth |
| **G-7** | A session's advisory lock is per database; is held while that session runs `CREATE DATABASE`, also after its client is gone; and ends with the session. | Kill the client during a long create; a second session's try-lock fails until the statement ends, then succeeds. | on PostgreSQL: every `copy` command that changes anything, and `reset` of one database | item 5, first and third |
| **G-8a** | A database's comment is read by any role from any database, and set only by its owner or a superuser. | A reader reads a template's comment from `megasamples`; a namespace's owner tries to set one on a template: refused. | template records; rule 2's registered template; a copy's proof | item 5, first, second and fifth |
| **G-8b** | A plain `DROP DATABASE` refuses while any session is connected to it. | An idle session connected; the drop is refused. Control: with none, it succeeds. | on PostgreSQL: `copy drop`, `copy sweep`, and the reconciliation's drop of a transient | item 5, first and third |
| **G-9** | When the data volume fills during a copy, by each strategy, and during a reset before its swap: the server stays up, no part of the new database remains, and every other database is whole. | A small volume; fill it; check each. | on PostgreSQL: `copy create`; `reset` of one database | item 5, first and eighth |
| **G-23** | A grant to `pg_database_owner` is held, in each database, by that database's owner and by no other ordinary role. | In a copy owned by a namespace's owner: it changes a row; a reader of the namespace and a declared writer of working copies cannot. | a copy's owner writing its copy | item 5, first and seventh |
| **G-24p** | A database dropped and made again under one name has another OID. | Drop and create; compare. | the proof on PostgreSQL: `copy drop`, `copy sweep`, the reconciliation | item 5, second |
| **G-29** | **The hook's rule 2, through direct SQL.** As the owner of `lab`: a database in `lab2`'s form; one outside every namespace; `template0`, `template1`, a working copy, another copy and an unregistered `x_start` as the source; a name of the right prefix and the wrong database; a rename. Each refused. Its own well-formed copy: made. As a consumer's role with `CREATEDB` and no namespace: a database outside every namespace is made; one inside `lab` is refused. | Each statement, by `psql`, with no CLI. | a PostgreSQL namespace owner's credential used away from the service. **A failure returns to the deciders.** | item 5, fifth |
| **G-32p** | The superuser sees each session's client address, its state and whether it has a transaction open. | A console's idle session, a console's session in a transaction, and a person's idle session, each told apart. | the session decision on PostgreSQL | item 2 (b) |
| **G-33** | A value written into a volume when it is first started is the same after a restart and different after the volume is replaced, and any account can read it. | Start, read, restart, read, replace, read. | item 9's straddling rule, on each server engine | item 9 |
| **G-35p** | A PostgreSQL role with no password cannot sign in over the network, by any rule the image has; the container's own maintenance still works. A key set to today's published value leaves the account locked. | `admin` and `postgres`, with no key, with the published value, and with a private one; from a second container on the stack's network, and through the published port. | default 2 on PostgreSQL | item 5, sixth |

**MySQL.**

| Gate | Definition | A test that tells | Withholds if it fails | Serves |
|---|---|---|---|---|
| **G-10** | `READ ONLY = 1` on a schema refuses every account's write, `root`'s too; it can be read by several `INSERT … SELECT` at once; changing it needs `ALTER` on it. | A write as each account; two copies at once; the option changed by `admin`, and refused to a namespace's owner. | every MySQL template and copy | item 5, first |
| **G-11a** | In a schema-level grant an escaped underscore is literal, and an unescaped one matches any character. | A grant on `a\_b`: `a_b` reached, `axb` not. A grant on `a_b`: both. | every grant the product makes on MySQL | item 5, first, fourth and seventh |
| **G-11b** | A holder of the privileges of 4.4 on `P\_%`, with no grant option, can create, alter and drop only inside it, and can grant nothing. | As the owner of `copy`: a schema `copyx`, a working schema, a template, `megasamples`, another namespace: each refused. A `GRANT`: refused. | MySQL namespaces; a MySQL owner's credential used away from the service | item 5, first and fifth |
| **G-11c** | A grant on a schema by its exact, escaped name reaches that schema alone; a grant on a foreign namespace's pattern reaches no working schema, template or engine schema. | `demo` with its narrowed grants: `mysql.user`, each template: refused; each working schema: read. | `demo`'s narrowing; declared readers and writers; `demo_reads` | item 5, fourth and seventh |
| **G-12** | A grant on a schema by exact name is still in force after that schema is dropped and made again. | Grant, drop, create, read. | nothing: the reset applies declared grants again either way. It decides whether that step is a repair or a no-op. | item 5, seventh |
| **G-13** | Definitions recorded from one schema, replayed into another by a namespace's owner, with the binary log on and with it off, give the same objects: tables with generated columns, foreign keys and full-text indexes; views; routines; triggers; events. | Each dataset's own verification, against a replayed schema. | MySQL copies of each dataset that uses a kind that fails | item 5, first |
| **G-15a** | A named lock is held while its session runs a statement after its client is gone, and ends with the session. | Kill the client during a long statement; a second session's lock attempt fails, then succeeds. | on MySQL: every `copy` command that changes anything; `reset` of one database | item 5, first and third |
| **G-15b** | `DROP DATABASE` waits on a transaction that has touched the schema, and gives up at the lock wait's end. | A transaction open; the drop times out; the schema is whole. | `copy drop` and `copy sweep` on MySQL | item 5, first |
| **G-16** | Every statement by which a MySQL account changes its own password; each mechanism of the pinned server that might refuse it, named, with its result and what else it breaks. | Each tried as `demo`. | nothing: it decides which branch of 4.5 is built | item 5, fourth |
| **G-17** | When the disk fills during a copy: the server stays up, and every template and working schema is whole. | A small volume; fill it; check each. | `copy create` on MySQL | item 5, first |
| **G-18** | The shipped MySQL starts and passes its image tests with the binary log off, and with it on. | Both starts. | the `binary_log` key | item 1 |
| **G-24m** | A schema dropped and made again has tables with other creation times; the creation time of an untouched table does not change. | Record, drop, make again, compare; and compare an untouched one after a restart. | the proof on MySQL: `copy drop`, `copy sweep` | item 5, second |
| **G-26m** | A stream that begins by taking a named lock, and fails if it cannot, holds that lock in the session that then runs the rest; a second such stream is refused while the first lives. | Two workers on one target. | MySQL's reset of one database | item 5, third and eighth |
| **G-27** | A grant revoked from an account, and that account's sessions ended, leave it unable to write the schema until the grant is given again. Without ending the sessions: what an open one can still do. | A writer with a session open, before and after. | MySQL's reset of one database, where a writer is declared | item 5, third and seventh |
| **G-32m** | An administrator sees each session's client address, whether it is idle, and whether it has a transaction open. | As G-32p. | the session decision on MySQL | item 2 (b) |
| **G-35m** | A locked MySQL account cannot sign in; a key set to today's published value leaves it locked; with no privileged key set, the engine still starts and `demo` still signs in. | `admin` and both `root` accounts, as G-35p. | default 2 on MySQL | item 5, sixth |

**SQLite, and the CLI.**

| Gate | Definition | A test that tells | Withholds if it fails | Serves |
|---|---|---|---|---|
| **G-19a** | On the filesystems a copy is made on, a bind mount shared by a host and a container among them: exclusive creation and a hard link each fail when the name exists, and two racing publications leave one winner. | Two processes, one on each side of the mount. | every SQLite `copy` command | item 5, first |
| **G-19b** | While a second link to a file is kept, no other file is given its inode; and a file that replaced the final name is not the same file as the retained link. | Replace the final name; compare. Remove the final name, make new files; none is the retained link's file. | the proof on SQLite: `copy drop`, `copy sweep` | item 5, second |
| **G-20** | A `flock` held by one process is seen by another across the host and a container on one mount; a lock file that was replaced after it was opened is detected. | Two processes; a replaced lock file. | every SQLite `copy` command that changes anything | item 5, first |
| **G-21** | **An install test:** the package installs with the two drivers alone on each supported Python, and `uv sync --locked` is unchanged. Psycopg's licence is reviewed first. | The install, and one `copy list`. | `copy` on the servers | item 5, first |

**Not gates of the product.** Whether a deployment's clients look different to its servers is that deployer's observation, and version 1 has no rule that uses it. What an account that manages accounts can do to the service's own is tested by whoever provisions one (4.4).

### 8.2 Regressions

Revised after the gates have run. Every red asserts the outcome that is wanted, and fails on the commit before its change because that outcome is not yet there. Every row has a reversal that changes the very assertion it plants a fault for. [D: review 3's finding 19.]

**The native entry point.** [D: review 3's finding 20.] A native test runs only against **an explicitly provisioned, task-owned, disposable target,** named to it: its project, its store and its ports. It verifies that the target carries the marker its provisioning wrote, and refuses one without it. It names no machine and no path. Its own tests: a shared target is refused; a second isolated one is accepted.

| # | The outcome asserted | Its reversal | The class it covers |
|---|---|---|---|
| T-1 | **A template is closed, as its engine closes it.** PostgreSQL: every account's connection is refused. MySQL: every account's write is refused; `demo` and a declared account have no privilege on it; **a namespace's owner and the administrators read it.** | PostgreSQL: built with connections allowed. MySQL: the option left off. | Every templated database; every account; each engine's own expectation. |
| T-2 | **Nothing an ordinary account does changes a template.** PostgreSQL: `admin`'s alteration is refused. MySQL: a namespace's owner's is refused; **`admin`'s change of the option succeeds, and is the stated limit.** | The template made `admin`'s; the owner given `ALTER` on it. | Rename, owner, flags, drop, comment, grant; a row change; the option. |
| T-3 | **No grant-producing prefix overlaps anything:** `oracle` as a namespace, **as a foreign namespace,** or as a declared scope does not build. | Each of the three checks removed. | Database names, templates, `megasamples`, engine schemas, other prefixes; adjacent prefixes such as `lab` and `lab2`. |
| T-4 | **The reach tables of 4.7,** cell by cell. | One fault for each column. | Every account against every kind of database, for connect, read, row write, definition change, drop and grant; a right held directly and through an inherited role. |
| T-5 | **Declared grants are in force after a start and after each reset:** a declared writer changes a working row after its copy was reset. | The reset's grant step removed; the start's. | Both engines; every reset path; an account declared no longer, locked at the next start; an unsettled MySQL reset, whose suspended grant a start leaves out. |
| T-6 | **A declared writer writes rows of working copies and nothing else:** it is refused a definition change, a copy, the registry, a template. | The write grant put in the template. | Both engines; a reader of a namespace and of the working copies at once. |
| T-7 | **The hook's four rules,** each: G-4a, G-29 and G-6 as regressions through the built image. | Each rule removed in turn; the library not loaded. | Creator by template by strategy; every command that makes a routine, by each kind of creator; a second session that never sees a new database open. |
| T-8 | **The routine floor is the list, for every role.** | The list granted to `demo` alone. | `demo`, a fresh role, a namespace's owner, a declared reader and writer; every kind of database; an exported snapshot imported by a second session. Pull request #14's own cases, kept. |
| T-9 | **MySQL's grants reach what they name and nothing else.** | One underscore left unescaped; `demo`'s grant on `*.*` restored. | Every working schema, template, `megasamples`, engine schema, other namespace and foreign namespace. |
| T-10 | **A copy carries no grant of its own:** after a create, the engine's grant tables hold no entry that names the copy. | A grant on the copy's name planted in the create: **the assertion reads the grant tables, and fails.** | Both engines; a create that is interrupted. |
| T-11 | **A MySQL copy is the dataset:** its own verification passes against a copy (`SM:ARCHITECTURE.md:239-249`). | The foreign keys' replay skipped; one view skipped. | Every templated database; the two exclusions. |
| T-12 | **The contract:** one document; each exit's promise checked on the server; each reader rule. | A second line; a changed code; an unknown member rejected. | Every command by every outcome of 3.3. `copy` with no container runtime, installed with the two drivers alone. |
| T-13 | **A reset signs in with the file's value when another is exported,** for its lock and for its worker. | Today's reader put back. | Each key; a canary password in no argument, output or log, nor taken from the CLI's environment. |
| T-14 | **An interrupted create is kept:** killed at each phase, on each engine, the object is there afterwards and `copy list` reports it; no command removes it. | Recovery made to remove an `interrupted` object. | Before and after the creating statement and the publication; an occupied name; a `ready` object replaced outside the CLI, kept as `inconsistent`; **a token forced to repeat.** |
| T-15 | **Every command against every command,** pairs generated from section 0's commands and every reset path and scope. **Its invariants, for each operation:** a sweep removes nothing inside its lease; an owner's own drop may remove its leased copy; no working copy is lost or left closed by a completed command; nothing is present that `copy list` or `reset --status` does not show. | Each guard removed in turn. | Natively, with the first paused at each durable phase; and by gated fakes. |
| T-16 | **A reservation is atomic:** forty creates into a namespace of 32 give exactly 32. | The count taken outside the lock. | Creates that fail and keep their place, as 2.2 has it. |
| T-17 | **A sweep removes only what 2.2 allows:** a copy renewed between its look and its removal is kept. | Each condition removed in turn. | Each reason a copy is kept. **The stated limits:** an idle MySQL session and an open SQLite file, past their lease, shown unprotected. |
| T-18 | **The build reports each template's allocated bytes,** appended datasets included. | The appended tables left out of the measure. | Each templated physical database; a copy's time by each strategy. |
| T-19 | **One unsettled operation for each target:** B is refused while A is unsettled, and A's reconciliation changes only what A made. | Admission made to ignore an unsettled row. | Each path; the CLI killed after each phase; `--status` on the same volume and on a replaced one; an operation's identity given twice; several targets, one failing. |
| T-20 | **A worker that outlives its CLI still excludes the next reset.** | The worker's own lock removed. | Both server engines. |
| T-21 | **A reset preserves sessions unless told otherwise.** | The default made to disconnect; a console's idle session made to count. | Each path and scope; a person's idle session; a console's idle session and one in a transaction; `--unattended` on MySQL and SQLite, refused; `make reset`. |
| T-22 | **A whole engine's reset refuses without `--discard`,** and a `copy` command that straddles one changes nothing in the new volume. | The check of the volume's identity removed. | A create, a drop and a sweep, each begun on the old volume. |
| T-23 | **No privileged account signs in with a published password,** on any path that starts an engine. | The value's test removed. | G-35p's and G-35m's cases through the built images; `megasamples up` writing each missing key; a console that offers nothing privileged without a sign-in. |
| T-24 | **SQLite:** a truncated copy is not published; a replaced file is not dropped. | The hash check removed; the retained link removed. | Create, drop, sweep; a manifest that disagrees; a sidecar one format back, kept. |
| T-25 | **Passwords:** PostgreSQL refuses `demo`'s change of its own. MySQL: what G-16 established, as a case that fails if the engine's answer changes. | Rule 4 removed. | Each account without `CREATEROLE`; a cleared key locking its account at the next start. |
| T-26 | **A dependency group is not reset singly.** | The refusal removed: `oracle_oe` then holds a key with no parent. | `oracle_hr`, `oracle_oe`; the whole engine's reset, after which every key holds. |
| T-27 | **The general upgrade route, rehearsed:** images replaced, the old volumes kept, and back. | A step removed from the route: its test fails. | PostgreSQL's refusal of data without the policy's marker. |

## 9. Pull request #14, and the order of the work

- **Pull request #14 is folded into this work's branch.** It is not rebased, and its content does not reach `main` by itself: if H-1 is as read, `main` alone with it would build a server on which no role but `demo` and `admin` can call a built-in routine. [D]
- **How.** The branch starts from `main` and merges `fix/strict-read-account` at `2879fc4` first. It merges without conflict (F-15).
- **Its conditions under DL-085** are its maintainers', and are in 7.2's steps 6 to 8. [108-5]
- **Its tests are not loosened.** A changed expectation is a test-only change of its own, saying why. **Its native guard is replaced** by 8.2's entry point (F-14).
- **Its evidence is made again** for the final candidate; the earlier receipts remain in history at `2879fc4`.
- **The credentials and consoles change** (5.1) may be its own pull request, merged before the build. [108-5]
- **Carried on the same branch:** the ten notes that pull request #16's review left for the next pull request, C-1 to C-10 (`DI:docs/work/megasamples-pr16-review-loop.md:17-27` at `d02f7384`). [R]

## 10. What the README must document

For DL-078's writer, before the merge. **The README describes the product.** A deployment is an example.

**What DL-078 itself asks** (F-27):
1. **It leads with the project's purpose:** one place to go for fast access to sample data across many technologies.
2. **The LTS engines and the clients,** at the versions the build pins.
3. **The datasets:** which there are, on which engines, with a matrix.
4. **The configuration and the `.env` passwords, and where to find them.**
5. **The general upgrade route** (5.3).
6. **Visuals where they help.**

**What version 1 fixes:**
7. **The model, with a picture:** a template, a working copy, a test copy and a reset; and how the three engines differ, **MySQL's reset from the image among the differences.**
8. **Which databases have a template,** per engine, with measured sizes and times; that version 1 bounds no storage.
9. **Namespaces:** what a prefix is, why it may not overlap, a foreign namespace.
10. **A copy's life:** issued, ready, leased, renewed, released, swept. **That an interrupted create is kept, and how an administrator removes one. That the lease is the protection, and the two cases past it.**
11. **The commands,** each with one example and its JSON; the identity on `drop`, `renew` and `release`.
12. **The exit codes,** both tables, and what a script does on 8.
13. **Credentials:** the two routes for `copy`; the keys; **that privileged passwords are private and where `megasamples up` writes them;** what a console offers.
14. **The accounts,** as 4.7's tables. It replaces today's two-row tables (`SM:README.md:120-123`, `:247-255`).
15. **Declared readers and writers.**
16. **The read profile on PostgreSQL,** and its limit. It replaces the sentence that `demo` "still has `TEMPORARY`" (`SM:README.md:163-167`).
17. **5.2's table, whole:** what a deployer weighs. **How to hand a credential over:** one, alone, never the `.env`. [108-11]
18. **What changed, with how to migrate:** a reset no longer disconnects without being told to; `admin` and the superusers have no published password; a console no longer signs in as `admin`; a new database is closed until its owner grants `CONNECT`; MySQL's `demo` no longer reads `mysql`; `oracle_hr` and `oracle_oe` reset only with the whole engine. [108-2]
19. **What is not claimed:** a sweep protecting a copy past its lease; a copy owner's credential away from the service before its gate; any bound on storage; a wider listener; MySQL as a strict read profile; MySQL refusing a password change, unless G-16 finds it does; TLS.
20. **Resets:** each path, the session decision, operations and their identities, `--status` and `--reconcile`.
21. **The contract and the formats.**

**What leaves the README:** the dated account of one deployment (`SM:README.md:16-20`) and the paragraphs that take LAN forwards for granted (`:258-270`). [108-3]

## 11. What waits, and in which stage

Each is new work with a brief of its own, added under section 6's rules. [108-4] [108-6] The fuller design at `e0c2f935` is the source for each.

| Stage | What waits in it | DL-108 |
|---|---|---|
| **S-1 · Exposure** | `network.bind`, `administrators.allow_from`, `whoami`. The approved default that a wider listener is refused while an account keeps a published password, or until administrators' origins are set, and that a console with stored administrator access or anonymous use is refused a wider bind. The profiles of a shared server, a container platform and remote access; a map from account keys to mounted secret files. | items 2 (a), 6 |
| **S-2 · Enrollment at run time** | The enrollment commands, their record, its replay and its repair. `accounts check`. A writer of a copy that is not its owner, and the per-run writer boundary a result would need. | item 6 |
| **S-3 · Storage admission** | Headroom reserved across an engine; a recovery reserve; inputs for an image reset, an off-host file and a retained log. | item 6 |
| **S-4 · A remote image worker** | A reset asked for from anywhere but where the service runs. | item 6 |
| **S-5 · `copy hold`** | Holding a copy past its lease; a holder's own identity; protection of active copies, holds and sessions across a whole engine's reset, with a drain. | items 8, 9 |
| **S-6 · MySQL's reset from a template** | The reset itself; writers shut out through it; a group of databases that refer to each other, reset and recovered as one. | item 10 |
| **S-7 · `accounts export`** | One credential handed over with a value-free receipt; an optional custody record. | items 1, 11 |

## 12. Review 3's findings, each mapped

Every finding is answered first by removing or narrowing a claim. It is **closed in version 1** only where every entry point version 1 keeps, the legacy reset paths included, avoids the hazard. [108-7]

| # | Finding | Where it goes | How |
|---|---|---|---|
| 1 | **P1 · The exposure defaults trust everyone who can reach loopback.** | **Version 1, closed,** for privileged accounts. The wider-listener check: **S-1.** | No privileged account has a usable published password on any start path, tested by value; `megasamples up` writes private ones (5.1). G-35p and G-35m, T-23, from a second container and through the published port. Version 1 has no setting that widens a listener, so the check on one has nothing to guard yet. |
| 2 | **P1 · An exposed console gives administrator access after every password is rotated.** | **Version 1, closed.** Wider publication of a console: **S-1.** | No console holds a privileged password; privileged access needs a sign-in (5.1). T-23. |
| 3 | **P1 · Clean-up still authorizes deletion without proof of ownership.** | **Version 1, closed.** | An interrupted create is never removed, on any engine, by any command: the empty-schema exception and the trust in a transient's name are withdrawn. SQLite keeps a second link for the copy's life. A PostgreSQL transient is dropped only by its recorded OID (2.2, 3.5). G-19b, G-24p, G-24m; T-14. |
| 4 | **P1 · A new reset can overtake an unsettled reset.** | **Version 1, closed.** | A target with an operation that is not terminal admits no reset; reconciliation settles that operation only; each worker is fenced, by its own transient or its own lock; a failed lock gate withholds the path (3.5). G-7, G-26m; T-19, T-20. |
| 5 | **P1 · A whole engine's reset can destroy an active copy or disconnect a user.** | **Version 1, closed as DL-108 item 9 has it.** Protection and drain: **S-5.** | It refuses unless given `--discard`; a volume identity stops a straddling command; SQLite's reset, which stops the consoles, always needs `--discard`; the session decision applies to every scope (3.5). G-33; T-21, T-22. |
| 6 | **P1 · MySQL enrollment repair can reopen a database during reset.** | **Version 1, closed,** on the image path that is kept. Repair and run-time enrollment: **S-2.** MySQL's template reset: **S-6.** | No repair command exists. A suspension is recorded in the operation; a start leaves a suspended grant out; `done` needs both the data checked and the grants in place (3.5). G-27; T-5, T-19. |
| 7 | **P2 · The hook does not define an exact namespace boundary.** | **Version 1, closed.** | Rule 2 is exact: a name of one form, a registered template by its tag, create and rename ruled apart, and a consumer's own creator left its right outside every namespace (4.3). G-29, with `lab` and `lab2`. |
| 8 | **P2 · A readable foreign namespace can expose protected schemas.** | **Version 1, closed.** | Every grant-producing prefix is checked: a namespace's, a foreign one's, a declared scope's (2.1). G-11c; T-3, T-9. |
| 9 | **P2 · Copy names can be reissued.** | **Version 1, closed by narrowing.** | The promise is stated exactly: never while a record or object exists; possibly again after. Version 1 makes no grant on a copy's name, and does not check a hand-made one (2.1). T-14 forces a repeated token. |
| 10 | **P2 · `exclusive: true` does not establish exclusive writing.** | **Version 1: removed.** A per-run boundary: **S-2.** | The flag is gone. The product says that holders of one credential share its copies (4.7). DataIntent records its criterion as unmet where a credential is shared (7.2). |
| 11 | **P2 · A drop cannot identify the caller's own hold.** | **S-5.** | `copy hold` is not in version 1, so a drop has no hold to respect. |
| 12 | **P2 · Reset status can give a false answer.** | **Version 1, closed.** | Outcomes are kept for the life of the volume. `unknown` is told apart from never started, by the volume's identity. A repeated operation identity is refused. Several targets get one each, in the one document (3.5). T-19. |
| 13 | **P2 · The remote reset matrix promises an image source the client lacks.** | **Version 1: removed.** **S-4.** | A reset runs where the service runs (3.1). |
| 14 | **P2 · The credential contract does not cover worker and platform inputs.** | **Version 1, closed by narrowing.** The map to mounted files: **S-1.** | The promise says what is true: no argument, no output, no log, not from the CLI's environment; and in the started container's environment, as today (3.4). The container-platform profile is not in version 1. T-13. |
| 15 | **P2 · Storage admission has no input for several operations.** | **S-3.** | Version 1 claims no admission and no bound on bytes (2.6). |
| 16 | **P2 · A coordinated MySQL reset lacks a group recovery rule.** | **Version 1, closed by a narrowing that is tested.** The group reset: **S-6.** | A database of a dependency group is not reset singly, on the path that is kept; today it is, and leaves a broken key (3.5). T-26. |
| 17 | **P2 · Enrollment replay and admission have conflicting authorities.** | **Version 1, closed.** Run-time enrollment: **S-2.** | The configuration is the one authority, applied at each start. The reach tables no longer offer enrollment to a namespace's owner or to `admin` (4.6, 4.7). T-5. |
| 18 | **P2 · Several gate fallbacks retain the failed prerequisite.** | **Version 1, closed.** | The gates are split, each one assertion; each names everything it withholds, `copy drop` among G-8b's; round 3's gate on MySQL's grant patterns is now three (G-11a, G-11b, G-11c); G-23 withholds the owner's writing; an account that manages accounts is no gate of the product (8.1). |
| 19 | **P2 · The regression matrix has impossible expectations and an ineffective reversal.** | **Version 1, closed.** | T-1 and T-2 give each engine and account its own expected result. T-10's assertion reads the grant tables, so its planted fault fails it (8.2). |
| 20 | **P2 · The native-test plan assumes one machine.** | **Version 1, closed.** | A task-owned, disposable target, named to the test and verified by its marker; a shared one refused, a second isolated one accepted (8.2). |
| 21 | **P2 · The rollout cannot pass its account check with locked spares.** | **Version 1, closed,** in the profile. | Verification is generated from the approved account state: a keyed account signs in, a locked one is refused (7.2). |

**Rounds 1 and 2** are answered in this file's history: round 1's findings at `bdd9033`, round 2's at `e0c2f935`. Where version 1 keeps a capability they bore on, this record carries the answer; where it does not, the answer waits with that capability's stage.

**Three readings of DL-108 that this record makes, for the deciders to correct if wrong:**
- **No `template` or `interface` command.** A template's presence is told by `copy create`'s exit 4; the interface and schema numbers are in every document; SQLite's manifest is written by the build. That is narrower than round 3, and adds nothing.
- **`engines.mysql.binary_log` is in version 1,** as DL-108 item 1 confirmed its placement and item 6 does not list it as waiting.
- **`--discard` is one option for both scopes:** a database's sessions, and everything on an engine.
