# Templates, copies, the scripting CLI and the account model: design

**Design record · 2026-11-20 · round 2, the drafter's part. Status: a design under review. Nothing here is built, and nothing here has been run.**

- **What this is.** The design of sql-megasamples' pristine templates and per-test copies, the commands that scripts drive them with, and the account model of both server engines. It carries the strict PostgreSQL read profile of pull request #14.
- **Rounds.** Round 1 is `2a15387`. Astra's review 1 of it found two P1s, fourteen P2s and a P3 (the coordinator's ignored `.local/megasamples-design/astra-r1.md` in DataIntent). All are fixed in this round, under DL-101. Section 12 answers each by number.
- **Who decides what this leaves open.** The two deciders, by the owner's directions of 2026-11-20: DL-104 for the design's questions (section 9), and DL-105 with the approval MEGASAMPLES-ROLLOUT-2 for the rollout itself (5.6).
- **Authority.** The owner's DL-076 (read or write by account), DL-077 (templates, copies and the CLI, built into sql-megasamples), DL-078 (the README), DL-101 (a problem found in a piece of work is finished in it) and DL-103 (one rollout, from a build of `main`). The two deciders' DL-079, DL-085 and DL-087. The lines register's lines 2, 4, 10 and 16.
- **Method.** Reading only: no container, no database connection, no network, and no credential file. So no statement about how an engine behaves has been observed.
- **Marks.** Each claim carries one:
  - **[R]** read in the cited file and line;
  - **[G-n]** rests on a native behaviour nobody has shown. It is feasibility gate *n* of section 6.1, which the build passes before anything is built on it. It is not asserted either way; the gate says what happens if it fails;
  - **[I]** inferred, and not load-bearing;
  - **[D]** decided here, with the reason.
  - A table or list whose heading line carries **[D]** is decided as a whole. A file and line cited inside any row is **[R]**.
- **Citations.**
  - `SM:` is sql-megasamples at `main`, `e61335f`.
  - `PR14:` is its branch `fix/strict-read-account` at `2879fc4`.
  - `DL:` is DataIntent's `docs/work/decision-log.md` at `d02f7384` (`origin/coordinator/journal-during-full`), and `LR:` is `docs/work/lines-register.md` there. DL-104, DL-105 and `docs/bootstrap/approvals.md`'s MEGASAMPLES-ROLLOUT-2 were read on that branch at `3ada3517`.
  - `ED:` is DataIntent's `docs/work/samples-service-editing-requirements.md`, `MR:` its `docs/work/samples-service-requirements-and-architecture.md`, and `DI:` any other DataIntent file, all at `4a8aad61` (`origin/coordinator/samples-p1`).

## 0. Summary

| Area | Decided here |
|---|---|
| **Names** | `<database>_start` is the template, `<database>` the working copy, and `<prefix>_<database>_<label>` a test copy. Lower case, digits and underscores, at most 63 bytes. |
| **Namespaces** | A prefix is a namespace with one owning account. No namespace may overlap a database, a template, another namespace, or a namespace another principal holds. On MySQL every wildcard character is escaped. |
| **Lifecycle** | Every copy has an identity, a durable record, and a lock held on the server for each whole change. A sweep removes only a copy whose lease has ended, that nobody holds, and that the engine will let go. Anything else it keeps and reports. |
| **PostgreSQL** | The template accepts no connections and is the superuser's. A copy is `CREATE DATABASE … TEMPLATE`. A reset builds the new working copy beside the old one and swaps them in one transaction, with a durable record of each phase. |
| **MySQL** | The template is a schema set `READ ONLY`. A copy is logical and runs inside the server. A reset is not atomic there, and can only be completed, not undone. |
| **SQLite** | The template is the image's file, staged read-only with a manifest. A copy is a verified, exclusive file publication. Nothing goes over the network. |
| **Templates by default** | The databases whose base dataset is in the core tier, within a storage budget the build measures and enforces. No size is promised here. |
| **The CLI** | `template`, `copy`, `reset`, `accounts` and `interface`. One JSON document on standard output, nine exit codes whose state each command defines, and a password from a file or standard input only. |
| **Accounts** | Group roles carry the data grants through every copy and reset. Access to working copies and to a namespace's copies is by enrollment, which a reset keeps. No copy has a grant of its own on MySQL. |
| **Password changes** | PostgreSQL refuses them through the hook. On MySQL nothing is assumed: a gate establishes what the engine can refuse, and the deciders are asked only with its result. |
| **Pull request #14** | Folded into this work's branch. Its content reaches `main` only after DataIntent's comparison has passed against the branch's candidate. |
| **The rollout** | One, after DL-087's acceptance: the README finished first, then the merge, then one build of the final `main`, qualified and deployed. |

**Three findings that change pull request #14's content** (section 4.3), each a gate before it is a fix:
1. **Roles other than `demo` and `admin` can call no built-in routine,** not an operator's function nor a cast's, and `admin` cannot grant them back. That reaches DataIntent's `di_reader`, `di_analyst` and `di_login_…`. [G-5]
2. **The hook may leave a new database open to `PUBLIC` without failing,** when the creator is not the new database's owner. [G-4]
3. **DataIntent's provider calls built-ins as a read account that the allow-list refuses:** `pg_export_snapshot()`, `pg_current_snapshot()` and `pg_database_size()`. [R]

## 1. What the design rests on

| # | Fact | Where | Mark |
|---|---|---|---|
| F-1 | **Every command of today's CLI that contacts a running engine does it through `docker exec`.** The reset starts a second container of the running image, and pipes a dump from it. So none of those works without a container runtime. | `SM:megasamples/credentials.py:29-70`; `SM:megasamples/reset.py:156-197`, `:245-304` | [R] |
| F-2 | **The CLI's output is text for a person,** and a command returns 0, 1 or 2. An unknown command is 2. | `SM:megasamples/cli.py:68-82`; `SM:megasamples/reset.py:384` | [R] |
| F-3 | **Resets exclude each other by a lock file** for one user on one host. Resets from other hosts "must be coordinated separately". | `SM:megasamples/reset.py:101-116`; `SM:README.md:323-325` | [R] |
| F-4 | **PostgreSQL's reset of one database drops it with force,** as the superuser, then restores it. | `SM:megasamples/reset.py:256-260` | [R] |
| F-5 | **Accounts today.** PostgreSQL: `admin` has `CREATEDB` and `CREATEROLE` and owns each sample database and what is in it; `demo` has `SELECT` on the tables. MySQL: `admin` and `root@'%'` hold all privileges with the grant option; `demo` holds `SELECT, SHOW VIEW ON *.*`. | `SM:engines/postgres/init/00-users.sql:10-12`; `SM:engines/postgres/init/20-grants.sql:4-7`; `SM:engines/postgres/Dockerfile:43-55`; `SM:engines/mysql/init/00-users.sql:9-19` | [R] |
| F-6 | **Each health probe signs in as `demo`** with a password file written at start. Passwords are applied at each start from the environment. | `SM:megasamples/engines/postgres/__init__.py:80`; `SM:megasamples/engines/mysql/__init__.py:139`; `SM:engines/postgres/entrypoint-wrapper.sh:17-35`; `SM:engines/mysql/entrypoint-wrapper.sh:19-40` | [R] |
| F-7 | **The registry has one row per database,** with a build id that is `dev` unless `MEGASAMPLES_BUILD_ID` is set. | `SM:megasamples/registry.py:52-88`, `:111` | [R] |
| F-8 | **The maintained deployment's baked data** is 22.712 GiB on MySQL, 20.902 GiB on PostgreSQL and 17.862 GiB of SQLite files. Its MySQL holds 33 datasets in 30 physical databases. | `SM:docs/live-upgrade-runbook.md:97`, `:101-105` | [R] |
| F-9 | **Sizes on record are old, and of two kinds.** PostgreSQL's data directory was 2.6 GB for the 21 core databases. MySQL's was 1,785 MB for 22 on 2026-09-03, which was 1.9 times their logical size. Neither counts a dataset that appends to a core database. | `SM:ARCHITECTURE.md:170-171`; `SM:knowledge/decisions/tier-assignments.md:65-88` | [R] |
| F-10 | **MySQL's binary log grew to 10.9 GB** after the rehearsal of logical resets. The build server runs without one; the shipped server's configuration does not turn it off. | `SM:docs/live-upgrade-runbook.md:109`; `SM:megasamples/engines/mysql/server.py:74`; `SM:engines/mysql/my.cnf:1-11` | [R] |
| F-11 | **One dataset reaches into another database:** `oracle_oe` depends on `oracle_hr`. | `SM:datasets/oracle_oe/dataset.yaml:8`; `SM:README.md:212` | [R] |
| F-12 | **Pull request #14** revokes `TEMPORARY` and routine `EXECUTE` from `PUBLIC` in every database and both templates, grants `admin` what it had, and grants `demo` an allow-list. A compiled hook closes `TEMPORARY` on each new database. An event trigger closes `EXECUTE` on each new routine. | `PR14:engines/postgres/init/10-read-profile.sql:4-35`; `PR14:engines/postgres/read-policy/read_policy.c:29-40`; `PR14:engines/postgres/read-policy/read_policy--1.sql:1-20` | [R] |
| F-13 | **Its grant to `admin` carries no grant option.** | `PR14:engines/postgres/init/10-read-profile.sql:10-13` | [R] |
| F-14 | **Its evidence:** 254 native cases Passed on the isolated stack; 1,663 signatures stay executable by `demo`; MySQL is not claimed strict, and `demo` there can take a named lock. | `PR14:docs/strict-read-evidence.md:16-18`, `:30` | [R] |
| F-15 | **It merges into `main` without conflict,** and shares no file with what `main` has gained since its base, `2cf1f3e`. | `git merge-tree origin/main fix/strict-read-account`; the two diffs' file lists against `2cf1f3e` | [R] |
| F-16 | **DataIntent's fixture** makes `di_reader` and `di_analyst` as `admin`, makes each `di_…` database from `di_template`, `template1` or `template0`, and closes it to `PUBLIC` itself. The superuser makes `di_template`. Leased logins are `di_login_` and 32 hexadecimal digits, members of a fixture group. | `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureServer.cs:27-32`, `:131-134`, `:224-230`, `:403-409`; `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureRoles.cs:11`, `:69-71` | [R] |
| F-17 | **DataIntent's provider, as a read account,** calls `pg_database_size(oid)` when it lists databases. It calls `pg_export_snapshot()` and `pg_current_snapshot()` when it takes a snapshot, and imports that snapshot in another transaction with `SET TRANSACTION SNAPSHOT`. | `DI:src/DataIntent.Adapters/Postgres/PostgresSourceServer.cs:238`, `:347`; `DI:src/DataIntent.Adapters/Postgres/PostgresSnapshot.cs:136` | [R] |
| F-18 | **Of those, only `pg_postmaster_start_time` is in the allow-list.** | a search of `PR14:engines/postgres/init/read-routine-names.sql` for each name | [R] |
| F-19 | **What DataIntent asks of this task:** twelve acceptance criteria, and a CLI contract. | `ED:` section 5; section 4 | [R] |
| F-20 | **Each server accepts every account from every address that reaches its port.** PostgreSQL's rule is `host all all all scram-sha-256`. Every MySQL account but one of `root`'s is `@'%'`. | `SM:engines/postgres/Dockerfile:33`; `SM:engines/mysql/init/00-users.sql:9-18` | [R] |
| F-21 | **Three datasets append to a core database:** `nyc_taxi_yellow` to `nyc_taxi`, `chicago_crimes_full` to `chicago_crimes`, and `dvdstore_reviews` to `dvdstore`. The record estimates 500 to 700 MB for the first and 300 to 400 MB for `dvdstore` with its reviews. | `SM:datasets/nyc_taxi_yellow/dataset.yaml`, `SM:datasets/chicago_crimes_full/dataset.yaml`, `SM:datasets/dvdstore_reviews/dataset.yaml`; `SM:knowledge/decisions/tier-assignments.md:32-62` | [R] |
| F-22 | **The reset's password reader reads the environment:** an exported value wins over the file's, and a value in the file may be expanded from the environment. | `SM:megasamples/config.py:155-167` | [R] |
| F-23 | **The fixture gives each of its roles to `admin`, inherited:** `GRANT {role} TO CURRENT_USER WITH INHERIT TRUE, SET FALSE`. | `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureServer.cs:230`; `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureRoles.cs:70-71` | [R] |
| F-24 | **DataIntent's comparison has five parts, C1 to C5,** and "from the next upgrade on, they are as designed". Comparison mode's first use on two versions is named as this rollout. The first rollout's rollback inputs are kept until its accepting run and package 3's gate have both passed. | `MR:` section 3, "The comparison as designed" and "What option A gives up"; `DL:` DL-079 item 6.5 | [R] |
| F-25 | **One rollout rebuilds the live services from a build of `main`,** after the templates, pull request #14's account model and the README are merged. Each engine image copies `README.md`. | `DL:` DL-103 items 1 to 3; `SM:engines/postgres/Dockerfile:13`; `SM:engines/mysql/Dockerfile:18`; `SM:engines/sqlite/Dockerfile:21` | [R] |
| F-26 | **Pull request #14 stays unmerged until the first cutover is accepted,** and C1 must pass against its candidate before it merges. | `DL:` DL-085 items 1 and 3 | [R] |

## 2. Templates, copies, resets and the sweep

### 2.1 Names and namespaces

| Thing | Name | Rule |
|---|---|---|
| The template | `<database>_start` | `<database>` is the registry's name for the physical database (F-7). A dataset that appends to another's database is in that database's template. |
| The working copy | `<database>` | The name people use today. |
| A test copy | `<prefix>_<database>_<label>` | The prefix is its namespace. The label is the caller's. |
| A reset's transient | `<database>__new_<8 hex>`, `<database>__old_<8 hex>` | PostgreSQL only (2.3). |

- **Characters:** lower-case letters, digits and underscores. A prefix matches `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` and is at most 16 bytes. A label matches `^[a-z0-9]{1,24}$`. [D: one rule for both engines.]
- **Length:** a whole name is at most 63 bytes on both engines. A name of exactly 63 bytes is valid; 64 is not. [D: PostgreSQL's limit, taken as the one rule.] The longest database names today are 21 bytes, so the longest prefix and label still fit. [R: `SM:datasets/` directory names]
- **Reserved:** the suffix `_start`, a double underscore, and the name `megasamples`. The image build refuses a dataset whose database name ends in `_start`, holds a double underscore, or is longer than 49 bytes. [D]
- **Nothing is found by parsing a name.** What a copy is, is in its record (2.2). [D]

**A namespace** is one prefix with one owning account. It is the service's configuration, baked at build [D]:

```yaml
copies:
  namespaces:
    - {prefix: copy, owner: copier}       # the default
  foreign: []                             # namespaces other principals hold, such as `di`
```

**No namespace may overlap anything else.** The image build refuses a configuration in which, for a prefix `P` [D: this is review 1's first P1]:
- any registered database, any template, `megasamples`, or an engine's own schema is named `P` or begins with `P_`;
- another prefix `Q` equals `P`, or one begins with the other followed by an underscore;
- a declared foreign namespace `F` equals `P`, or one begins with the other followed by an underscore.

So `oracle` is refused, because `oracle_hr` exists. `di_copy` is refused on a service that declares `di` as foreign, because DataIntent plans a `di\_%` grant for its fixture administrator (`MR:` 2.10): a copy named `di_copy_…` would be that administrator's to drop.

- **The same check runs at every build,** so a dataset added later cannot fall inside a namespace.
- **On MySQL every underscore in a grant's schema pattern is escaped,** in a prefix and in a database's own name: `copy\_%`, `oracle\_hr`, `northwind\_start`. An unescaped underscore matches any character. [G-11]
- **An audit holds what the build cannot see.** `megasamples accounts check`, as the engine's administrator on the service's machine, reads every grant and reports any account outside the service's own whose pattern reaches a namespace, a template or a working copy (4.5). [D: `admin` can make such a grant at any time; no build check can stop it.]
- **For DataIntent this means a copy cannot be named `di_…`** on a server where `di\_%` is another principal's. DL-077 gave `di_` as an example; its fixture's guard and F-05's wording do not cover a copy namespace. That goes back to its own design (section 11).

### 2.2 A copy's record, its identity, and what excludes what

Round 1 let a name alone stand for a copy. Review 1 showed three ways that fails: a sweep that deletes a replacement, a creation with unguarded gaps, and a count that many callers pass at once. This section is the answer, and is the same on all three engines. [D]

**The record.** Each namespace has a ledger. A row is one copy: its name, a random 128-bit identity, the database, the label, its state, its size, when it was reserved, and when its lease ends.

| Engine | The ledger | The identity is bound to the copy by |
|---|---|---|
| PostgreSQL | a table in the `megasamples` database that only the namespace's owner and the administrators can write | the copy's comment, which carries the same identity [G-8] |
| MySQL | the same, in the `megasamples` schema | the lock protocol below. MySQL has no comment on a schema [I], and a marker table inside the copy would change what the copy is. |
| SQLite | a sidecar `<copy>.copy.json` beside each file, made with exclusive creation | the sidecar, which names the file and the template's SHA-256 |

**Two locks, both on the server.**
- **The change lock** of a name is held for the whole of any change to that copy: create, drop, and a sweep's removal. On PostgreSQL it is a session's advisory lock, taken in the `megasamples` database; on MySQL a named lock; on SQLite an exclusive `flock` on the sidecar.
- **The use lock** of a name is held by whoever is using the copy, through `megasamples copy hold` (3.1). It is a second lock of the same kind.
- **Both end with their holder's session.** A holder that dies leaves nothing behind. A creator that is paused, however long, still holds its lock. [G-7, G-15, G-20]
- **The session that runs the change is the session that holds the lock.** On PostgreSQL the connection that issues `CREATE DATABASE` took the lock first. If the client is lost, the lock lasts exactly as long as the server goes on with the statement. [G-7]
- **A namespace lock** is held only while a reservation is counted and written (below).

**A copy's state is read, never guessed.** `copy show` derives it under no assumption about time:

| The row | The change lock | The object | State |
|---|---|---|---|
| none | — | absent | `absent` |
| none | — | present, in the namespace | `unmanaged` |
| `creating` | held | either | `creating` |
| `creating` | free | either | `incomplete`: its creator is gone |
| `ready` | — | present, identity matches | `ready` |
| `ready` | — | absent, or another identity | `inconsistent` |
| `dropping` | held | either | `dropping` |
| `dropping` | free | either | `incomplete` |

**Creating.**
1. The name's change lock is taken, without waiting. Held by another: exit 6.
2. **The reservation, atomic:** under the namespace lock, the live rows are counted and their sizes summed; if the limits allow, a row is written with a new identity, `creating`, the template's size and the lease's end; the namespace lock is released. So no two callers can both take the last place. [D]
3. The object is made (2.3, 2.4, 2.5). **Only an object this operation made is ever cleaned up by it.** If the engine says the name already exists, the row is removed and nothing else is touched: exit 5, `exists-unmanaged`. [D: review 1's finding 3.]
4. The identity is bound, access is given (4.6), and the row is set `ready`. The lock is released.

**Dropping, and a sweep's removal, are one procedure:** take the change lock without waiting; read the row again and require the identity that was selected; set it `dropping`; remove the object; remove the row. A sweep that finds another identity under the name does nothing to it. [D]

**What a sweep may remove.** It removes a copy only when every one of these holds [D: review 1's finding 4]:

| # | Condition | What it guards |
|---|---|---|
| 1 | Its state is `ready` and its lease has ended, or its state is `incomplete`. | A lease is the owner's own statement of how long the copy is wanted. It is renewed with `copy renew`. |
| 2 | Its change lock is taken without waiting. | A creation or a drop in progress, however slow. |
| 3 | Its use lock is taken without waiting. | A user that holds it, whatever its lease says. |
| 4 | Its identity, read again under the locks, is the one selected. | A replacement under the same name. |
| 5 | The engine lets it go: on PostgreSQL a plain `DROP DATABASE`, which refuses while any session is connected [G-8]; on MySQL a drop that gives up after five seconds on a lock [G-15]; on SQLite the exclusive `flock`. | What the engine itself can see of use. |

Anything else is **kept and reported with its reason:** `leased`, `held`, `busy`, `in-use`, `unmanaged`, `inconsistent`. A sweep never removes an `unmanaged` or `inconsistent` object: it cannot establish whose it is.

- **Age alone removes nothing.** Round 1's rule by age is withdrawn.
- **What this does not see, said plainly.** A MySQL session that is idle on a copy, and a process that has a SQLite copy open, are invisible to the engine check [G-15, G-20]. They are protected by the lease and by the use lock, and by nothing else. A caller that lets its lease end and holds no use lock has, by this protocol, let the copy go. "Never a copy in use" (`ED:` criterion 11) is therefore met as **"never a copy that is leased, held, being changed, or visibly in use"**. That narrower meaning goes back to DataIntent's design (section 11).
- **If gate G-7, G-15 or G-20 fails for an engine,** sweeping is not offered on that engine: exit 4. Copies there are removed only by `copy drop`. [D]

### 2.3 PostgreSQL

**The template.**
- **It is `<database>_start`, with `datistemplate` true, `datallowconn` false, and the superuser `postgres` as its owner.** [D]
  - It refuses every connection, the superuser's included; any account that may create databases can still copy it; only the superuser can alter, rename or drop it. [G-1]
  - `admin` is not its owner, so `admin` cannot open it. That is the reason for the owner.
- **What it would take to write it:** the superuser sets `ALLOW_CONNECTIONS true`. No command of the CLI does it. [D]
- **It is frozen before it is closed:** `VACUUM (FREEZE, ANALYZE)` in the image build. [D: nobody can vacuum it afterwards but the server itself [I].]
- **Its record is its comment,** set by the build: `megasamples-template/1` and a JSON object with the database, its size in bytes, the copy strategy, the build id and the SHA-256 of its registry row. [D] [G-8]

**How the image makes it.** [D: so that the image's own working copy comes from the path a reset uses.]
1. The dataset is loaded into `<database>_start`, as `admin`, as today (`SM:engines/postgres/Dockerfile:43-53`).
2. The grants of section 4.1 and the read profile are applied there.
3. It is frozen, given to `postgres`, and closed.
4. The working copy is made from it: `CREATE DATABASE <database> OWNER admin TEMPLATE <database>_start`.
5. A database with no template is loaded straight into `<database>`, as today.

The build's private server loads the hook, so step 4 closes the new database as a running service would.

**A copy,** as the namespace's owner, connected to the `megasamples` database. It is step 3 of 2.2's creation:
- `CREATE DATABASE <copy> TEMPLATE <database>_start STRATEGY <strategy>`. The hook closes it to `PUBLIC` inside that statement (4.3).
- `COMMENT ON DATABASE <copy>`: `megasamples-copy/1` and the identity.
- `GRANT CONNECT ON DATABASE <copy>` to the namespace's two access groups (4.6).
- **The strategy** is the template's recorded one. The build measures `WAL_LOG` and `FILE_COPY` for each template and records the faster. [D: DL-077 item 4 names `FILE_COPY` for large ones; the threshold is found, not assumed.]
- **No session is on the template during a copy,** because none can be; two copies at once, and a copy during a reset, each only read it. [G-1]
- **What a copy inherits** is section 4.8. [G-2]

**A drop** is a plain `DROP DATABASE`, never with force, under 2.2's procedure. With `--wait` it is tried again until the wait ends. It closes nothing first: a drop that gives up has changed nothing. [D: round 1 closed the copy before waiting, and so could leave it closed after an exit that promised no change.]

**A reset of the working copy,** as `admin`, connected to the `megasamples` database. Each phase is written to `megasamples.operations` before the step that follows it. [D]

| Step | What happens | The durable phase after it |
|---|---|---|
| a | The database's reset lock is taken, without waiting. An earlier operation's row, if any, is reconciled first (below). A row is written with a new operation identity. | `building` |
| b | `CREATE DATABASE <database>__new_<id> OWNER admin TEMPLATE <database>_start ALLOW_CONNECTIONS false`, then its grants (4.6). | `built` |
| c | **The door is closed:** `ALTER DATABASE <database> ALLOW_CONNECTIONS false`. No new session can arrive; those already there stay. | `closed` |
| d | The sessions on the working copy are listed. With `--if-idle`, any session stops the reset here. Without it, they are ended. | `closed` |
| e | **In one transaction:** the working copy is renamed to `<database>__old_<id>`; the new one is renamed to `<database>` and opened; and the row's phase is set. | `swapped` |
| f | `DROP DATABASE <database>__old_<id>`. The row is removed. The lock is released. | none |

- **Step e is one transaction or it is not built.** Two renames, the opening and the row's update must commit or roll back together. [G-3] If the gate shows they cannot, the swap is withdrawn and the reset returns to the design: nothing weaker is put in its place here.
- **Why a swap, and not a drop and then a copy.** DL-077's entry says "drop-and-copy". This keeps its result, and changes the order. [D]
  - **A failure before step e changes no data.** After a drop, a failed copy would leave no working copy at all.
  - **The name `<database>` is never free.** A namespace's owner may create databases (4.1), and PostgreSQL cannot limit which names.
  - **Its cost:** one more copy of that database's storage while it runs.
- **The door is closed before anyone is looked for,** as `ED:` R-37 asks, so no session can arrive between the look and the swap.

**Reconciling an interrupted reset.** The row says where it stopped; the lock says whether it is still running. `megasamples reset --status` reads both and changes nothing. `megasamples reset --reconcile` settles it, under the lock [D: review 1's finding 5]:

| The row's phase, with the lock free | What reconciling does | The working copy afterwards |
|---|---|---|
| `building`, `built` | drops the transient if it exists; removes the row | as it was; **the reset did not happen** |
| `closed` | **opens the door again;** drops the transient; removes the row | as it was; the reset did not happen |
| `swapped` | drops the old transient; removes the row | pristine; **the reset happened** |

- **Nothing is reset twice by a retry.** After a lost connection the caller reads the status or reconciles, and learns which of the two happened. A plain `reset` reconciles first too, and then resets, because that is what it was asked.
- **A crash in step c or d leaves the working copy closed** until someone reconciles. That is the one outage this design can cause. It is kept short by doing all the copying before the door closes. The CLI opens the door again when it is interrupted by a signal. `megasamples accounts check` reports any unreconciled operation. [D]
- **A database with no template** resets by today's path, from a second container of the image, on the service's machine only (F-1). It takes the same lock and writes the same row (3.6).
- **A whole engine's reset** is unchanged in what it does (`SM:README.md:301-303`): templates and working copies return, and every copy is gone.

### 2.4 MySQL

**The template.**
- **It is the schema `<database>_start`, set `READ ONLY = 1`.** [D] Whether that refuses every account's writes, `root`'s included, and what it takes to change, is [G-10].
- **MySQL has no "accepts no connections" for a schema.** What stands in its place: `demo` holds no privilege there; a namespace's owner holds `SELECT` only; `admin` and `root` can read it, and can change the option. [D: stated as a difference from DL-077's model, not hidden.]
- **`admin` is not shut out of it by a partial revoke.** [D: that needs the server's `partial_revokes` setting, under which wildcards in schema grants may stop working [G-11]; the namespaces' grants need them.]

**How the image makes it.** After the dumps are loaded (`SM:engines/mysql/Dockerfile:39-42`), for each templated database:
1. Its definitions are recorded in `megasamples.template_ddl`: tables, then routines, views in dependency order, triggers and events, each without its definer and with no reference to its own schema by name. The insertable columns of each table are recorded too. [G-13]
2. The template is made from the loaded database by the copy below, as `root`, keeping each definer.
3. Each table's row count and `CHECKSUM TABLE … EXTENDED` are compared with the loaded database's.
4. The template is set `READ ONLY = 1`.

[D: the copy runs from recorded definitions so that a namespace's owner needs `SELECT` on a template and nothing server-wide.]

**A copy,** as the namespace's owner, all of it inside the server. It is step 3 of 2.2's creation:
1. `CREATE DATABASE <copy>`, never `IF NOT EXISTS`, with the template's character set and collation. A name that exists is refused and left alone (2.2).
2. Each table's recorded definition, with foreign-key checks off for the session.
3. `INSERT INTO <copy>.<table> (…) SELECT … FROM <database>_start.<table>`, a table at a time.
4. The routines, the views, and then the triggers and events, so that no trigger fires during the load.
5. Each table's row count compared with the template's.

- **A copy has no grant of its own.** Who may use it is decided by the namespace, once, when an account is enrolled (4.6). [D: review 1's second P1. A grant on a schema by name outlives the schema [G-12], so a grant made for one copy would reach the next copy of that name. With no such grant there is nothing to outlive it.]
- **Accounts enrolled in a namespace can see a copy while it is being filled.** They are one trust domain with its owner (4.9). A caller uses a copy only once `copy create` has returned it `ready`.
- **The definer of everything in a copy is the namespace's owner.** [D: keeping `admin` as the definer would need a privilege that lets the owner run code as `admin` [I].]
- **The template cannot change under a copy,** so the copy needs no single snapshot. [G-10]
- **A failure** drops the schema this operation made and removes its row: exit 7. If that clean-up fails too, the row stays: exit 8, and `copy show` reads it as `incomplete`.

**Large datasets, and the stated exclusions.** [D]

| Database | On MySQL | Why |
|---|---|---|
| Templated, up to `copy_limit_mb` of allocated bytes, measured at build | template, copies and reset by the logical method | The limit's default, 512, is a starting value; the build's measurements set it (T-18). |
| Templated, above the limit | template and reset; **no copies**: exit 4, `too-large` | A logical copy's time and undo grow with its rows. |
| `oracle_oe`, and any dataset with `depends` | **no template, no copies**; reset by today's path | Its foreign keys and views reach into `oracle_hr` (F-11). A copy would still point at the shared working copy. |
| A database another refers to (`oracle_hr`) | template, copies and reset, **if [G-14] passes**; otherwise as the row above | Its reset drops and refills a schema that `oracle_oe`'s foreign keys point into. |

Transportable tablespaces are not used: they need the server's files, so a container runtime on the service's machine. [D]

**A reset of the working copy,** as `admin`. Its row in `megasamples.operations` is written before anything is dropped: [D]

| Step | What happens | The durable phase after it |
|---|---|---|
| a | The database's reset lock (`GET_LOCK`) is taken, without waiting. An earlier row is reconciled first. A row is written. | `started` |
| b | `DROP DATABASE`, bounded by `--wait`. | `dropped` |
| c | The copy above, with each recorded definer. | `filled` |
| d | The counts are checked. The row is removed. | none |

- **It is not atomic, and cannot be undone.** After step b the old rows are gone. Reconciling an interrupted one can only complete it: drop what is there, fill it, check it. `reset --status` says so before anyone chooses. [D: MySQL cannot rename a schema [I].]
- **A process that is killed writes nothing.** That is why the row is written first, and why "interrupted" is read from the row together with a free lock, not from a mark the dead process would have had to leave.
- **A wait that ends at step b changes nothing:** exit 6, and the row is removed.
- **Privileges stay:** `demo`'s grant on `<database>` is by name and outlives the drop. [G-12]

**Its records are tables in `megasamples`:** `service`, `templates`, `template_ddl`, `operations`, and one ledger for each namespace. [D]

**The binary log is turned off in the shipped server.** [D: every logical copy and reset would otherwise be written a second time; it reached 10.9 GB in one rehearsal (F-10), and nothing replicates from this server.] [G-18]

### 2.5 SQLite

- **The template is the image's file.** There is no server and no account, so "read-only" is the file's mode. [R: `PR14:docs/strict-read-account.md:13`]
- **Staging, once, on the service's machine:** `megasamples template stage sqlite --out DIR` writes each `<database>.sqlite` with mode 0444, and `templates.json`: a format number, and for each file its size, its SHA-256 and the build id. Its source is `build/sqlite/` in the checkout, or the image through the container runtime (`SM:megasamples/reset.py:307-332`). [D]
- **A copy,** by 2.2's creation:
  1. the sidecar is made with exclusive creation, which is both the reservation and the change lock's file;
  2. the template is copied to a temporary name in the same directory, synced, and held to the manifest's SHA-256;
  3. **it is published by a hard link to its final name,** which fails if that name exists, and the temporary name is removed. Nothing is ever moved over an existing file. [G-19]
- **A namespace's limits** are counted under an exclusive lock on the directory's lock file.
- **A drop** removes the file, any `-wal`, `-shm` or `-journal` beside it, and then the sidecar.
- **Nothing goes over the network.** A development container or a separate machine works from a staged directory someone copied there, manifest included, as `MR:` 2.10 already asks. [D: a file server for them would be a new listener, which DL-075 did not grant.]
- **The service's own files** keep today's reset.

### 2.6 Which databases get a template, and the storage

**The default selection** (`templates: core`) is every physical database whose base dataset is of tier `core` or `core-medium`. [D]
- It covers the five that DataIntent's suites read: `northwind`, `adventureworks`, `employees`, `pubs` and `dvdstore` (`ED:` 3.3 and question 7). [R: `SM:datasets/*/dataset.yaml`]
- **It is configured per engine:** `engines: {postgres: {datasets: …, templates: core}}`, with a selector, a list of databases, or `none`. It is baked, so a change is a rebuild. [D]

**No size is promised here.** Round 1 gave two totals as upper bounds. They are not [D: review 1's finding 12]:
- **A template is a physical database.** Where a configuration appends `nyc_taxi_yellow`, `chicago_crimes_full` or `dvdstore_reviews`, the template of that core database holds the appended tables too (F-21). The maintained deployment's MySQL has three more datasets than databases (F-8).
- **The figures on record** are old, leave those datasets out, and mix logical sizes with allocated ones (F-9).

**So the cost is measured, and the build enforces a budget:**
- **The build measures each selected physical database** as that engine holds it: its allocated bytes, not its logical size.
- **`templates.budget_mb` is the most the selected templates may add** on one engine. The image build refuses to bake a selection that exceeds it, and prints each database's share. Its default is 4096. [D: a starting value. The point is that an over-large selection stops a build and is chosen on purpose.]
- **The storage report** is part of what is approved before a rollout (5.6). For each engine it gives:
  - each template's allocated bytes, and their total;
  - **the peak during one copy** by each strategy, with the write-ahead log, the undo and the temporary space it used;
  - **the peak during one reset:** on PostgreSQL the working copy, the template and the new copy at once;
  - the most a namespace's limits allow at once.

| What uses space | PostgreSQL | MySQL | SQLite |
|---|---|---|---|
| A template | its database again | its schema again | none in the service |
| A live copy | its database again | its schema again | the file, where the caller keeps it |
| A reset | its database again, until step f | nothing more: it is in place | none |

**A namespace's limits,** both reserved atomically (2.2): at most 32 live copies, and at most `quota_mb` of templates' sizes in total. [D: starting values, set from the report.]

**What the limits do not bound.** They bind the CLI. A holder of a namespace owner's credential who writes its own SQL can make databases the ledger never sees (4.9).

**When the disk fills.** A copy or a reset that runs out of space must leave every working copy and every template whole, and say which exit it is. Whether each engine does that, and whether the server itself stays up, is [G-9] and [G-17]. If a gate shows a server falling over, copies on that engine are not offered until the design has a guard. [D]

**The image and its first start grow with it.** The first-start budgets are twice the observed maximum (`SM:megasamples/engines/image_startup.py:9-18`), and are measured again. [D]

## 3. The CLI for scripts

### 3.1 The commands

The commands, their names and their options are decided here. [D: DL-077 item 3; `ED:` 4.1 sketched them.]

| Command | As | What it does |
|---|---|---|
| `megasamples interface` | nobody | The interface number, the output schema, the formats it reads and writes, the package version and the revision. |
| `megasamples template list ENGINE` | any account | For each registered database: whether it has a template, the template's record, and whether copies are offered, with the reason if not. |
| `megasamples template stage sqlite --out DIR [DATABASE…]` | nobody | 2.5. The service's machine only. |
| `megasamples copy create ENGINE:DATABASE --prefix P --label L [--lease DURATION]` | the namespace's owner | 2.2. The lease defaults to 24 hours. |
| `megasamples copy show ENGINE:NAME` | the owner | The copy's derived state (2.2), its lease, and whether it is held. It changes nothing. |
| `megasamples copy list ENGINE --prefix P` | the owner | Each copy's name, database, label, state and lease. |
| `megasamples copy hold ENGINE:NAME` | the owner | Holds the copy's use lock until its standard input closes or it is killed. |
| `megasamples copy renew ENGINE:NAME --lease DURATION` | the owner | Sets the lease's end. |
| `megasamples copy release ENGINE:NAME` | the owner | Ends the lease now, so that a sweep may take the copy once nothing holds it. |
| `megasamples copy drop ENGINE:NAME [--wait SECONDS]` | the owner | Dropping a copy that is already gone succeeds. It settles an `incomplete` one. |
| `megasamples copy sweep ENGINE --prefix P [--dry-run]` | the owner | What it removed, and what it kept and why (2.2). |
| `megasamples reset ENGINE:DATABASE… [--json] [--if-idle] [--wait SECONDS] [--from auto\|template\|image]` | `admin` | Today's command, which gains the template path. `auto` takes the template when there is one. |
| `megasamples reset --status ENGINE[:DATABASE]` | `admin` | Each unsettled operation: its phase, whether it is still running, and what reconciling would do. It changes nothing. |
| `megasamples reset --reconcile ENGINE:DATABASE` | `admin` | Settles an interrupted reset (2.3, 2.4), and says which way. |
| `megasamples accounts check [--repair]` | the administrator, on the service's machine | 4.5. |
| `megasamples accounts enroll\|unenroll\|list …` | `admin`, on the service's machine | 4.6. |

- **Common options:** `--host`, `--port`, `--user`, `--connect-timeout`, and one of `--password-file`, `--password-stdin` or `--env-file` (3.4). For SQLite: `--templates DIR` and `--dir DIR`.
- **`ENGINE:DATABASE`** follows the reset's own pairs (`SM:megasamples/reset.py:6`). The database is the registry's name.
- **`copy create` takes no reader and no writer.** Round 1's `--read` and `--write` are withdrawn: access is the namespace's (4.6).
- **`reset` keeps its text output by default,** and its present behaviour of disconnecting clients (F-4). Which of that and `--if-idle` DataIntent's automation uses is its own question 6 (`ED:` section 10). [D]

### 3.2 Output

- **One JSON document on standard output, on one line,** for `interface`, `template`, `copy` and `accounts`, and for `reset` with `--json`, `--status` or `--reconcile`. Everything else goes to standard error. [D: `ED:` 4.2]
- **Its envelope:** `schema`, `command`, `ok`, `exit`, `result`, `error` and `warnings`. `error` holds a stable `code`, a `message`, and the `operation` or copy `identity` a caller reads the state by.
- **A copy's result:** its `name`, `identity`, `engine`, `database`, `prefix`, `label`, `state`, `reserved`, `lease_until`, its `endpoint` (the host and port the caller used, or the file's path), its `owner`, its namespace's access (4.6), the `template` with its build id and registry digest, the engine's `version`, the `strategy`, and the seconds it took.
- **No credential is ever in it:** an account is a name.
- **Its compatibility** is section 3.8.

### 3.3 Exit codes

Decided here [D], from the outcomes `ED:` 4.2 asks to be told apart. Each code promises a state, and 3.3's second table says what that state is for each command.

| Code | Meaning | What it promises | DataIntent reports (`ED:` 4.2) |
|---|---|---|---|
| 0 | done | as asked | the case goes on |
| 1 | a defect in the CLI | nothing; treat it as 8 | Failed; it reads the state before it asks again |
| 2 | wrong usage, or an invalid name | no engine was contacted | Failed: a defect in the harness |
| 3 | the engine cannot be reached, or the sign-in is refused | nothing changed | Not run |
| 4 | not offered here: no template, `too-large`, excluded, or an option this engine or path cannot honour safely | nothing changed | Not run, with the reason |
| 5 | refused by a rule: namespace, name taken, not the caller's, a limit, an unknown format | nothing changed | Failed |
| 6 | busy | **nothing changed, and the CLI confirmed it** | its question 6 |
| 7 | failed | **nothing is left changed, and the CLI confirmed it** | Failed |
| 8 | unsettled | **a durable record describes what is there.** It is read and settled by the command the second table names. | Failed; it reads before it asks again |

| Command | 6 means | 7 means | 8 is read by, and settled by |
|---|---|---|---|
| `copy create` | another change holds the name; no row was written | the object this operation made is gone, and so is its row | `copy show`; `copy drop` |
| `copy drop` | sessions remained at the end of the wait, or the copy is held; it is still `ready` and untouched | — | `copy show`; `copy drop` again |
| `copy sweep` | — | — | `copy list`; `copy drop` for each it names |
| `copy renew`, `release` | another change holds the name | — | — |
| `reset`, PostgreSQL | another reset holds the lock; or, with `--if-idle`, sessions were found and **the door is open again** | no data changed; the door is open; the transient and the row are gone | `reset --status`; `reset --reconcile` |
| `reset`, MySQL | another reset holds the lock, or the wait ended before the drop | it failed before the drop | `reset --status`; `reset --reconcile`, which completes it |
| `reset --reconcile` | the operation is still running | — | itself |
| `accounts check` | — | something is not as configured; the document lists each | — |

- **A command that cannot confirm what 6 or 7 promises returns 8.** [D: review 1's finding 5: an exit must not promise "nothing changed" over a database left closed.]
- **2 is what the CLI already returns for an unknown command** (F-2). Codes above 125 are left to the shell. "Unsupported" is not among them: DataIntent keeps that word for its own product.

### 3.4 Credentials

- **The password comes from a file an argument names, or from standard input.** Never from an argument, and never from the environment. [D: `ED:` 4.3]
- **Three routes, and one must be named:**

  | Route | What is read |
  |---|---|
  | `--password-file PATH` | the file's one line. It must be the caller's own and closed to others, or it is refused. |
  | `--password-stdin` | one line of standard input. |
  | `--env-file PATH` | one key of a `.env`-style file: `DEMO_PASSWORD`, `ADMIN_PASSWORD`, or the namespace owner's, such as `COPIER_PASSWORD`. |

- **The `--env-file` route is a reader of its own, and reads the file only.** [D: review 1's finding 9. The reset's present reader takes an exported value over the file's and expands a value from the environment (F-22); reusing it would not be "never from the environment".]
  - **A value is literal:** bare, single-quoted or double-quoted, with the quotes' own escapes and nothing else.
  - **A value that asks for expansion is refused:** exit 2, `env-file-expansion`. It is not expanded, and its text is not printed.
  - **An exported variable of the same name is not read.** A warning names the key, never a value.
  - **If the server was started with an exported value** that differs from the file's, the sign-in is refused: exit 3. That is the safe failure, and the README already tells an operator to unset such exports (`SM:README.md:130-131`).
- **`reset` and `accounts`, on the service's machine, default to `--env-file` at the checkout's `.env`.** No other command has a default. [D: `reset` works today with no option (`SM:README.md:318`).]
- **The image path's clients inside the container keep today's reader.** They run where Compose's own precedence was applied. Every connection the CLI makes over the network uses the routes above. [D]
- **Nothing else ambient is used.** `PGPASSWORD`, `PGPASSFILE`, a `~/.pgpass`, `MYSQL_PWD` and client option files are not read, and every connection parameter is given explicitly. [D]
- **It is in no output.** A driver's error text is passed through the redaction the pull request's helper has (`PR14:docs/validation/strict_read_clients.py:66-71`).
- **No SQL the remote commands send holds a password.**
- **On the wire:** PostgreSQL's rule is SCRAM for every address (`SM:ARCHITECTURE.md:166-167`). MySQL's sign-in without verified TLS is as `MR:` 2.10 describes it. This design changes neither.

### 3.5 Where it runs

| From | PostgreSQL and MySQL | SQLite |
|---|---|---|
| The service's machine | everything | everything |
| A development container | `template list`, `copy`, and `reset` where `admin`'s credential is | copies, from a staged directory in the checkout |
| A separate machine on the LAN | `template list`, and `copy` with a namespace owner's credential (question 1 of section 9) | copies, from a staged directory copied there |

- **The remote commands need a TCP path to the engine's port, and nothing else:** no container runtime, no checkout. [D: criterion 10; F-1 is why today's code cannot.]
- **Drivers:** PyMySQL, which is a dependency already, and Psycopg, which is a development dependency already, at 3.3.9 (`SM:pyproject.toml:8`, `:19`). [D] Whether Psycopg's bundled-library wheels suit the supported Python versions, with a pure-Python driver as the fallback, is [G-21].
- **A small install.** [D: criterion 10]
  - The new code is a subpackage that imports the standard library and the two drivers only.
  - `pyproject.toml` gains a build backend and a `megasamples` entry point. The pipeline's dependencies move to a dependency group that `uv sync --locked` installs by default. [G-21]
  - A pipeline command without its dependencies says which group to install: exit 2.

### 3.6 What excludes what

Each row's behaviour is decided here [D]. T-15 holds every pair, not only these.

| At once | What happens | By |
|---|---|---|
| Two `copy create` of one template | both succeed | each only reads the template [G-1, G-10] |
| Two `copy create` of one name | one runs; the other is exit 6 while it runs, and exit 5 afterwards | the change lock; then the ledger's key |
| Many `copy create` at a namespace's last place | exactly one takes it; the rest are exit 5, `limit` | the reservation under the namespace lock |
| `copy create` and `copy sweep` | the sweep keeps it: `busy` | the change lock |
| `copy sweep`, and a drop and re-create of that name between its look and its removal | the sweep finds another identity and does nothing | the identity, read again |
| `copy drop` and `copy sweep` of one copy | one removes it; the other finds it gone | the change lock; a drop of what is gone succeeds |
| `copy hold` and `copy sweep` or `copy drop` | the sweep keeps it: `held`; the drop is exit 6 | the use lock |
| `copy create` and `reset` of that database | both succeed | both copy the template; a copy never touches the working copy |
| Two `reset` of one database, **by either path** | one runs; the other is exit 6 | the database's reset lock, on the server |
| `reset` and `reset --reconcile` of one database | the second is exit 6 | the same lock |
| A whole engine's reset and any reset of one database | whichever takes the locks first runs; the other is exit 6 | below |
| A whole engine's reset and anything else | exit 3 or 8 for the other | the server goes away; the caller reads the state |

- **One exclusion for both reset paths.** [D: review 1's finding 6.] The image path also opens a connection to the server, as `admin`, and holds the same reset lock and writes the same operation row for as long as it runs. The lock file stays as a second guard for one machine (F-3).
- **A whole engine's reset** first takes, without waiting, the reset lock of every database it will replace. If any is held it does nothing: exit 6.
- **PostgreSQL's advisory locks are per database** [G-7], so every command takes them in the `megasamples` database.
- **`--if-idle`, for each engine and path:**

  | Engine and path | `--if-idle` |
  |---|---|
  | PostgreSQL, template | 2.3: the door is closed, then sessions are looked for. |
  | PostgreSQL, image | **The same door,** before the drop: `ALLOW_CONNECTIONS false`, then the look. Sessions found: the door is opened and nothing was dropped. |
  | MySQL, either path | **Refused before any change:** exit 4, `if-idle-unsupported`. MySQL has no door for a schema, a session can name any schema, and an idle one cannot be seen [G-15]. So "idle" cannot be established. |
  | SQLite | **Refused before any change:** exit 4. Its reset stops the consoles and cannot see another reader (`SM:README.md:312-314`). |

  [D: an option that cannot be honoured safely is refused, not approximated.]
- **Who can take these locks.** On PostgreSQL only the accounts given the lock functions in the `megasamples` database: the namespaces' owners and `admin`. On MySQL any account can take any named lock (F-14). So on MySQL any credential's holder can make a copy or a reset report busy. It is a limit on availability, and is in 4.9's table.

### 3.7 Limits

Decided here [D], as starting values.

| Limit | Value | Past it |
|---|---|---|
| A whole name | 63 bytes; 63 is valid | exit 2 |
| A prefix; a label | 16 bytes; 24 bytes | exit 2 |
| Empty, upper-case, a space, a non-ASCII character, a quote, a double underscore, the suffix `_start` | never valid | exit 2, before any connection |
| A namespace's live copies; their templates' total size | 32; `quota_mb` | exit 5, `limit` |
| A lease | at least one minute; at most seven days; 24 hours by default | exit 2 |
| MySQL copy size | `copy_limit_mb` | exit 4, `too-large` |
| Connection timeout; `--wait` | 10 seconds; 0 | exit 3; exit 6 |

No statement timeout is set by default: a copy of a large database takes as long as it takes. [D]

### 3.8 The public contract and the persisted formats

These are what a consumer pins and what stays on a disk or in a server. They are question 3 of section 9, with this policy as its recommended answer. [D: review 1's finding 15.]

| Thing | Where it lives | Its version |
|---|---|---|
| The JSON envelope and each result | standard output | `schema`, now 1 |
| The exit codes and their promises (3.3) | the process | `interface`, now 1 |
| The commands and options (3.1) | the command line | `interface` |
| A template's record; the service's record | a database comment on PostgreSQL; rows in `megasamples` on MySQL | a format tag: `megasamples-template/1`, `megasamples-service/1` |
| A copy's record; an operation's record | the ledgers and `megasamples.operations`; a copy's comment on PostgreSQL | `megasamples-copy/1`; a format column |
| SQLite's manifest and sidecar | files on the consumer's disk | a `format` member, now 1 |
| The names: `_start`, the group roles, the namespace's roles | the server | `interface` |

**The policy:**
- **Within a version, only additions.** A new member, a new error code under an existing exit, a new command or option.
- **A removal, a rename or a change of meaning raises the number.** For the JSON that is `schema`; for anything else, `interface`.
- **A consumer checks before it relies:** `megasamples interface` names the interface, the schema and each format it reads and writes; the service's record names the formats the server holds. A CLI that meets a format it does not know **changes nothing there:** exit 5, `format-unknown`.
- **Migration.**
  - **What is in a server is never migrated in place.** A new image renews the data volumes (`MR:` B-10), so its records are always its own build's, and every copy is gone with the old volume.
  - **What is on a consumer's disk** is read one format back. An older sidecar or manifest is reported and left alone; staging again replaces it.
- **Before the repository's first published release** (`SM:README.md:40`) the numbers may rise freely, each time with a line saying what changed. From that release, the previous interface is kept working for one release.

## 4. The account model

### 4.1 PostgreSQL's roles

The roles and what each holds are decided here [D]; what exists today is F-5.

| Role | A login | Attributes and memberships | What it is for |
|---|---|---|---|
| `postgres` | yes | superuser | The image build, the start wrapper, the image path of the reset. Owns the templates and the policy. |
| `admin` | yes | `CREATEDB`, `CREATEROLE`; **new:** `pg_signal_backend`, and the admin option, with no inheritance, on every group below | Owns each working copy and everything in each sample database. Resets. Enrolls. Makes DataIntent's fixture roles and databases. |
| `demo` | yes | member of `megasamples_working_read` | Reads the working copies. |
| **`megasamples_read`** | no | — | `SELECT` on every table of every sample database, and on those `admin` makes later. |
| **`megasamples_write`** | no | member of `megasamples_read` | `INSERT`, `UPDATE`, `DELETE` on the same tables, and `USAGE` on their sequences. |
| **`megasamples_working_read`** | no | member of `megasamples_read` | `CONNECT` on every working copy. |
| **`megasamples_working_write`** | no | member of `megasamples_write` | `CONNECT` on every working copy. **It has no member as shipped** (4.6). |
| **`megasamples_copy_<prefix>_read`**, **`…_write`** | no | members of `megasamples_read` and `megasamples_write` | `CONNECT` on every copy of that namespace. |
| **`copier`**, and each namespace's owner | yes | `CREATEDB`; member of `megasamples_write` | Makes, uses and drops its namespace's copies. |

- **The data grants go to the two data groups, not to `demo`.** [D: what is inside a database is copied with it [G-2]; so a copy and a reset carry them with no step of their own, which is criterion 7.]
- **Every membership the service makes is `WITH INHERIT TRUE, SET FALSE`.** [D: DataIntent's admission looks for roles that "can be taken up" (`MR:` IA-01).]
- **Which database an account reaches is decided by `CONNECT` on it,** which is not copied [R: `PR14:docs/strict-read-account.md:9`] and is set for each database:

  | Database | `CONNECT` is granted to |
  |---|---|
  | a working copy | its owner `admin`; `megasamples_working_read`; `megasamples_working_write` |
  | a template | nobody |
  | a test copy | its owner; its namespace's two groups |
  | `postgres`, `megasamples` | `PUBLIC`, as today |
  | any database made later | its owner, until its owner grants more |

- **These grants name groups and never a person's account.** So what a reset must give a new working copy is always the same three lines, and who is enrolled is a membership, which is not in the database and so is not touched by a reset (4.6). [D]
- **A namespace's owner, though it holds the write group, cannot write a working copy:** it holds no `CONNECT` on one. [G-2]
- **The hook closes `CONNECT` as well as `TEMPORARY` on each new database.** [D: without it a database is open to every role between its creation and the next statement; the fixture already closes its own (F-16).]
- **A namespace's owner also holds,** in the `megasamples` database only: its own ledger, and `EXECUTE` on the advisory-lock functions. [D: the floor of 4.2 does not hold them.]
- **A namespace's owner has no password by default.** It cannot sign in until its key, such as `COPIER_PASSWORD`, is set in `.env`. [D: a published default would put the right to create databases behind a password everyone knows.]
- **A namespace's owner may create a database of any name, from any template.** PostgreSQL cannot limit that, short of more compiled code in the hook. The CLI enforces the namespace; the engine does not. [D: stated as a limit, in 4.9, with a test that asserts it.]

### 4.2 The strict read profile

**What pull request #14 does** is F-12. **What changes:**

| # | Change | Reason | Mark |
|---|---|---|---|
| P-1 | **The allow-list is granted to `PUBLIC`,** not to `demo`. | Finding H-1. Every role that is not an administrator then has the same floor, with no step per role, in every database and every copy. It is DL-085 item 7's own description: "the change reaches every non-admin role". | [D] |
| P-2 | **`demo` holds nothing itself** but its membership. | 4.1. | [D] |
| P-3 | **Three built-ins join the list by name, each with its reason:** `pg_export_snapshot()`, `pg_current_snapshot()` and `pg_database_size(oid)`. | F-17, F-18. What each does to the server is [G-5]. | [D] |
| P-4 | **The rule for the list is stated.** A routine is admitted when it changes no stored object, no setting, no sequence and no other session's data, and assigns no transaction id. Volatility is the default test; an exception is named in the list with its reason. | So that P-3 is a rule and not a hole. | [D] |
| P-5 | **An exported snapshot is admitted explicitly, as the one exception that reaches past its own statement.** It leaves an identifier that another session may import for as long as the exporting transaction lives, and DataIntent does exactly that (F-17). It stores nothing and ends with that transaction. | Review 1's P3: the rule must say so, not leave it to be inferred. | [D] [G-5] |
| P-6 | **A write list beside it,** granted to `megasamples_write`: the built-ins that inserting, updating and deleting rows through the datasets' own defaults and triggers need. It is found by running each dataset's trigger scenarios as a member and reading each refusal. | A writer's statement runs a trigger's body with the writer's rights [G-5]. | [D] |
| P-7 | **The published inventory is the one authority:** every executable signature, with its reason, generated from the candidate. | DL-085 item 4 asks for one. DataIntent's admission can take it as data; that is its own design. | [D] |

**What stays:** no `TEMPORARY` for `PUBLIC`; no large-object creation; no user routine for a reader; the two rewritten `employees` views; the closed defaults for `admin` and `postgres`; MySQL not claimed strict (F-14).

**DL-085's item on the list is settled by a run, not by this text:** DataIntent's comparison against the candidate names any other routine the provider needs. Each is admitted under P-4, or the provider changes. [D]

### 4.3 The hook and the event trigger: a design check

This is input to the independent review DL-085 requires. Each row is from reading `PR14:` at the cited lines; none was run. **A finding that rests on engine behaviour is a gate first:** the build reproduces it, or shows it false, before it changes anything for it.

| # | Finding | Where | Disposition |
|---|---|---|---|
| H-1 | **Every role but `demo` and `admin` may be left unable to call any built-in routine.** The revoke covers every schema, `pg_catalog` included; the operators' and casts' functions come back for `demo` alone. A statement that uses an operator, a cast function or an aggregate would then be refused for a role such as `di_reader`; one that only names columns might not be. `admin` could not repair it: its own grant has no grant option (F-13). The file's own comment says why the functions matter: "Operators/casts are needed by ordinary expressions". DL-085 item 3 names the reach. [G-5] | `PR14:engines/postgres/init/10-read-profile.sql:14-15`, `:23-35`, `:29-30` | **If reproduced: P-1.** |
| H-2 | **The hook's `REVOKE` may do nothing, and succeed.** It runs as the creator. A creator who is not the new owner and does not inherit the owner's rights may be only warned. That would be reachable: `CREATE DATABASE x OWNER r` by a role that may only `SET ROLE r`. [G-4] | `PR14:engines/postgres/read-policy/read_policy.c:31-38`; `PR14:docs/strict-read-account.md:9` | **Two parts, whatever the gate shows:** the hook refuses such a creation before it starts (H-3), and afterwards confirms that `PUBLIC` holds neither privilege, failing otherwise. |
| H-3 | **An error in the hook after the copy may leave the copied files with no database.** [G-4] | `PR14:engines/postgres/read-policy/read_policy.c:24-38` | **If reproduced, it is resolved before the merge, not documented** (DL-101). See below the table. |
| H-4 | **The role name `admin` is compiled in.** If the role is missing or renamed, every `CREATE DATABASE` on the server fails, after its copy. | `PR14:engines/postgres/read-policy/read_policy.c:32-33` | **Fix: the hook names no role.** It closes `PUBLIC`, and nothing more. `admin` owns what it must use, and the build grants the rest. |
| H-5 | **The hook closes `TEMPORARY` only.** | the same | **Extend:** `CONNECT` too (4.1). |
| H-6 | **A role may change its own password and its own settings,** which the hook does not touch. `ALTER ROLE demo SET statement_timeout = 1` would break every later `demo` session, the health probe's among them. [G-6] | — | **Extend:** 4.5. |
| H-7 | **A reader may still write a catalog row:** `ALTER DEFAULT PRIVILEGES` for itself, in any database it reaches. [G-6] | — | **Extend:** refused with H-6's rule. |
| H-8 | **`NOTIFY` is a statement, not a routine,** so revoking `pg_notify` may not stop it [I]. The page says notifications "receive no `demo` grant". | `PR14:docs/strict-read-account.md:3` | **Correct the page.** `NOTIFY` stays allowed: it stores nothing, and nothing in the service listens. [D] |
| H-9 | **The event trigger also names `admin`,** and would fail every routine's creation if the role were missing. | `PR14:engines/postgres/read-policy/read_policy--1.sql:9-11` | **Fix:** it checks that the role exists. |
| H-10 | **The event trigger is enabled in the ordinary way,** so a session in replica mode may skip it [I]. | `PR14:engines/postgres/read-policy/read_policy--1.sql:19-20` | **Set `ENABLE ALWAYS`.** |
| H-11 | **Which commands can make a routine, and who covers each.** The closed defaults cover whatever `admin` and `postgres` create. The trigger covers a later role's `CREATE FUNCTION`, `PROCEDURE` and `AGGREGATE`. Routines an extension's script or a type's definition makes may be covered by the defaults only [I]. | `PR14:engines/postgres/init/10-read-profile.sql:18-20`; `PR14:docs/strict-read-evidence.md:22` | **Test the table:** every such command, by each kind of creator (T-7). |
| H-12 | **The library is named in the PostgreSQL data directory's configuration.** A PostgreSQL image without the library could then not start on policy data. But a policy image started on data from before the policy would run with the hook and without the grants. | `PR14:engines/postgres/Dockerfile:83` | **Keep the line, and add a marker:** the build writes the policy's version into the data directory, and PostgreSQL's start wrapper refuses a data directory whose marker is missing or older. [D] |
| H-13 | **The headers' package is taken from the network at build,** at the base image's own version. | `PR14:engines/postgres/Dockerfile:13` | **Record it** with the image's other inputs (`SM:engines/images.lock.yaml`), under the repository's pinning procedure. |
| H-14 | **What a role with no grant can still do,** for the reviewer to confirm as a class: anonymous `DO` blocks; `SET`; `LISTEN`; a held cursor; `LOCK TABLE` in a share mode on what it may read. [I] | — | **Document** as the profile's limit, once the reviewer has confirmed that none stores anything. |

**H-3's resolution, if the gate reproduces the leak.** [D: review 1's finding 16. Fewer failures and a note in the README do not close it.]
1. **Everything the hook can know beforehand is refused beforehand,** before any file is copied: that the creator has the new owner's rights, so that the closing cannot be refused (H-2).
2. **The step after the copy may not raise for a reason of its own.** It names no role (H-4), reads no configuration, and closes `PUBLIC` in a way that cannot be denied to it.
3. **T-7 forces each failure that was reachable** and shows it is now refused before the copy, with no file left.
4. **If any raising path after the copy remains,** or the leak shows without the hook at all, the work goes back to the two deciders with what was found. It is not merged with a known leak and a note.

**What the hook does after this design** [D]:
1. **Before `CREATE DATABASE`:** refuse, when the creator would not hold the new owner's rights.
2. **After `CREATE DATABASE`:** close `CONNECT` and `TEMPORARY` on the new database to `PUBLIC`; then confirm it.
3. **Before `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES`:** refuse, when the caller is neither a superuser nor a holder of `CREATEROLE`.

It names no role, reads no configuration, and holds no state.

### 4.4 MySQL's accounts

Decided here [D]; what exists today is F-5. **Every schema pattern below has each underscore escaped** (2.1).

| Account | Privileges | Change |
|---|---|---|
| `root@localhost`, `root@'%'` | everything | none |
| `admin@'%'` | everything, with the grant option | none (4.7) |
| `demo@'%'` | `SELECT, SHOW VIEW` on each working sample schema, by its exact name; `SELECT` on `megasamples`' registry and service tables | **narrowed** from `*.*` |
| **a namespace's owner,** such as `copier@'%'` | on its own pattern, such as `copy\_%`: what making, filling, using and dropping a copy needs, **without the grant option.** On each template, by exact name: `SELECT`. On `megasamples`: `SELECT`, and row changes on its own ledger. | **new**; locked until its password key is set |

- **The owner holds no grant option.** [D: review 1's findings 2 and 13. Round 1 gave it one, to grant a copy to a reader. It could then hand its whole namespace to any account. Enrollment (4.6) is done by `admin` instead.]
- **`demo` no longer reaches the `mysql` schema,** where account rows are (LR: line 10), nor a template, nor a fixture's `di_…` schema. It reaches a namespace's copies only if `admin` enrolls it. [G-11]
- **That reverses what DL-079 item 3 allowed:** that `demo` and the consoles may see DataIntent's synthetic fixtures. It was a permission, not a requirement, and the lines register put the narrowing here. [D]
- **A grant by exact name outlives a reset** [G-12]. A schema `admin` makes later is not `demo`'s to read until `admin` grants it. [D]
- **The namespace is enforced by the engine:** its owner holds nothing outside its pattern. [G-11]
- **What the patterns are proved against** (T-9): every working copy, every template, `megasamples`, the engine's own schemas, another namespace, and a fixture-like principal that holds `di\_%` with schemas of its own. For each, the namespace's owner holds nothing there, and that principal holds nothing in the namespace.
- **MySQL stays not claimed strict** (DL-085 item 5): named locks, and the two definer views of `employees`, are as F-14 found them.

### 4.5 An account changing its own password, and the accounts' check

| Engine | Decided | Mark |
|---|---|---|
| **PostgreSQL** | **Refused,** by the hook's third rule (4.3), for every role without `CREATEROLE`: `demo`, a namespace's owner, a fixture role. The rule also covers a role's own settings, which would do the same harm. That such a role can alter only itself, and that `admin` cannot change `demo`'s, is the gate. | [D] [G-6] |
| **MySQL** | **Required, and not yet known to be possible.** The brief asks that `demo` cannot change its own password. Round 1 said MySQL cannot refuse it; that was an assertion nobody had tested. **Gate G-16 establishes it first.** | [G-16] |

**What G-16 does, before anything is designed around its answer:**
- it tries every statement by which an account with no account-management privilege can change its own password;
- it tries each candidate way of refusing that: an authentication method whose secret the account cannot set; a proxied sign-in; a password policy; anything else the engine's documentation of the pinned version offers;
- it records, for each, whether the change is refused, and what else it breaks.

**Then:**
- **If a way is found** that refuses the change and keeps `demo` usable by the consoles, the probe and a LAN client: it is built, and nothing is asked.
- **If none is found:** that is the engine's limit, established. The deciders are asked what to accept (question 2 of section 9), with these consequences stated as they are:
  - any holder of `demo`'s password can replace it, **as often as it likes;**
  - it can replace it **with a value everyone knows,** which undoes the first rollout's rotation for that account until someone repairs it;
  - while it is changed, the probe reports the engine unhealthy and the consoles cannot sign in (F-6);
  - it gains no privilege by it: `demo` reads what `demo` read.

**`megasamples accounts check`** exists either way. As the engine's administrator, on the service's machine, it reports, and exits 7 if anything is found:
- each service account whose configured password is refused;
- each grant that reaches a namespace, a template or a working copy and is not the service's own (2.1);
- each grant on a schema that does not exist, within a namespace;
- each reset operation that is not settled (2.3, 2.4);
- on PostgreSQL, whether the policy's library is loaded and its marker current (H-12).

`--repair` applies the configured passwords again, by the private client files the reset uses (F-1). **It repairs; it does not prevent.** A restart does the same (F-6).

### 4.6 Enrollment: who may use working copies and a namespace's copies

DL-076 asks for reading or writing the samples by the account used. Round 1 shipped a write group that could not connect to a working copy, and whose manual grant a reset would have removed. [D: review 1's finding 7.]

**Enrollment is a command, as `admin`, on the service's machine:**

```
megasamples accounts enroll   ENGINE --role ROLE --access read|write (--working | --prefix P)
megasamples accounts unenroll ENGINE --role ROLE (--working | --prefix P)
megasamples accounts list     ENGINE
```

| | PostgreSQL | MySQL |
|---|---|---|
| **What enrolling does** | makes the role a member of one group: `megasamples_working_read` or `_write`, or the namespace's `megasamples_copy_<prefix>_read` or `_write` | grants, by escaped pattern: on each working schema's exact name, or on the namespace's pattern, `SELECT, SHOW VIEW`; for `write`, `INSERT, UPDATE, DELETE` as well |
| **Where it is kept** | in the server's role memberships | in the server's grant tables |
| **A reset of one database** | keeps it: a membership is not in the database, and the new working copy is granted to the same groups (4.1) | keeps it: the grant is by name [G-12] |
| **A whole engine's reset, or a new image** | removes it, with every role that is not the image's. It is enrolled again. | the same |

- **What it refuses.** A role that is a superuser, may create databases or roles, or owns a namespace is not enrolled for `write`: the editor is never an alias of a privileged account (`ED:` R-38). On MySQL, where one account's privileges are not readable by another, `admin` reads them and refuses the same.
- **Nobody is enrolled for `write` on working copies as shipped, and the rollout enrolls nobody.** [D: DataIntent's record forbids a read/write account on a live service until its controls have passed (`ED:` R-39), and the product does not write (`MR:` A-31).]
- **The capability is built and tested now, on the isolated stack** (T-5, T-6): an enrolled role writes a row of a working copy; is refused a definition change; is still enrolled after a reset; is not after an unenrollment; and is refused everything on a template.
- **The service ships no `editor` account.** An editor is whatever role `admin` makes and enrolls.
- **The same command gives a namespace's copies their readers and writers.** There is no access per copy on either engine (2.4).
- **Unenrolling takes effect for new sessions.** Whether it reaches a session already open, on each engine, is `ED:` criteria 6 and 9, and T-6 records it.

### 4.7 What `admin` can do

The table follows from the sections above; what changes is decided below it.

| | PostgreSQL | MySQL |
|---|---|---|
| Sample data | owns it: reads, writes, alters, drops | all privileges |
| A working copy | owns it; resets it | drops and refills it |
| A template | copies it; cannot connect to it, alter it or drop it [G-1] | reads it; can change its read-only option [G-10] |
| A test copy | **owns its tables. It can connect whenever it holds, or inherits, a role enrolled in that namespace, and it can enroll itself.** It cannot drop the database. | everything |
| Accounts | makes roles; changes those it made; cannot change `demo`, a namespace's owner or `postgres` [G-6] | makes and changes any account |
| Sessions | **new:** ends any that is not a superuser's | ends any |
| The server | not a superuser | in effect the administrator |

- **PostgreSQL's `admin` gains one thing:** `pg_signal_backend`, because a reset must end `demo`'s sessions (2.3, step d). [D] [G-3]
- **MySQL's `admin` is not narrowed.** [D: narrowing it needs partial revokes, which 2.4 rules out. It was the engine's administrator in all but name before this design (`MR:` B-03).] It is why DataIntent keeps its own `di_admin` there (`MR:` R-20).

### 4.8 DataIntent's fixture roles, `di_…` databases, and what a copy inherits

**What a database inherits from the one it is copied from** [G-2]:

| Copied with it | Not copied: set anew for each database |
|---|---|
| tables, rows, indexes, views, routines, triggers, sequences | its owner |
| each object's owner, which stays `admin` | `CONNECT`, `TEMPORARY` and `CREATE` on the database |
| each object's privileges: the data groups' grants; the routine floor | settings made for the database |
| default privileges | its comment |
| the policy's extension and event trigger | whether it is a template and whether it accepts connections |

**So for DataIntent:**

| Thing | Where it comes from | What it has | What it lacks |
|---|---|---|---|
| `di_reader`, `di_analyst`, `di_login_…`, in a fixture database | `admin` makes the role; the database is copied from `di_template`, `template1` or `template0` (F-16) | the routine floor, through `PUBLIC` (P-1); whatever the fixture grants | `TEMPORARY`, unless `admin` grants it on that database; `EXECUTE` on a routine the fixture creates, unless the fixture grants it |
| The same role, in a test copy of a sample | `admin` enrolls it in the copy's namespace (4.6) | `CONNECT`, the tables' `SELECT`, the floor | any write, unless enrolled for it; `TEMPORARY` |
| The same role, in a working copy | not enrolled | nothing: it cannot connect | — |
| A test copy | its namespace's owner owns it; its tables stay `admin`'s | everything the template had | `CONNECT` for anyone outside the namespace's groups |

- **Pull request #14's revocations reach every one of these,** because both templates carry them, and every later database is a copy of one. With P-1 the fixture roles keep the built-ins a reader needs. Whether without it they keep none is H-1's gate.
- **Two things the fixture must then do itself:** grant `EXECUTE` on its own routines to the roles that call them, and grant `TEMPORARY` where a case needs it.
- **Permissions are kept through template creation, a copy and a reset** by construction: the left column is carried, and the right column is set by the build, the hook and the commands. T-5 holds each to a fingerprint.

### 4.9 Effective access, and each credential's authority

**An account reaches whatever any role it inherits reaches.** Round 1's table gave each account's own grants and called the rest "refused". That was wrong for the fixture as it is built. [D: review 1's finding 8.]

- **The rule.** On PostgreSQL an account holds a privilege if it, a role it inherits directly or through other roles, or `PUBLIC` holds it. `SET FALSE` stops it from becoming that role; it does not stop the inheritance. A membership held `WITH SET TRUE` and no inheritance is one the account can take up.
- **The fixture's real topology** (F-23): `admin` inherits `di_reader`, `di_analyst` and every `di_login_…`. So once any of them is enrolled in a namespace, **`admin` inherits `CONNECT` on that namespace's copies,** and it already owns their tables.
- **So a copy's contents are not beyond `admin`'s reach,** and DataIntent's rule that a result counts only if nobody else could have written its source (`ED:` R-35) holds against every account but the administrators. That is so today for every fixture database, which `admin` owns.

**What each account reaches, by the grants it holds itself.** Each cell is the expected value of a test (T-4), and each is tested held directly, inherited through one role, inherited through two, and held as a role that can only be taken up.

*PostgreSQL:*

| Account | A working copy | A template | A copy in a namespace it is enrolled in or owns | A copy in another namespace | A fixture `di_…` database | `megasamples` |
|---|---|---|---|---|---|---|
| `demo` | reads | refused | reads, if enrolled | refused | refused | reads |
| a namespace's owner | refused | copies it; refused a connection | owner; reads and writes rows | refused | refused | reads; writes its own ledger |
| a role enrolled for `write` | reads and writes rows, if enrolled on working copies | refused | reads and writes rows | refused | as granted | reads |
| `admin`, as shipped | owner | copies it; refused a connection | refused, until it enrolls itself | the same | owner | reads and writes |
| `admin`, after the fixture has run and a fixture role is enrolled | owner | the same | **connects; owns the tables** | refused | owner | reads and writes |
| `di_reader` | refused | refused | reads, if enrolled | refused | as the fixture grants | reads |
| `postgres` | everything | can open it | everything | everything | everything | everything |

*MySQL:*

| Account | A working copy | A template | A copy in its namespace | A copy in another namespace | A fixture `di_…` schema | `mysql` |
|---|---|---|---|---|---|---|
| `demo` | reads | no privilege | reads, if enrolled | no privilege | no privilege | no privilege |
| a namespace's owner | no privilege | reads | everything a schema allows, but no granting | no privilege | no privilege | no privilege |
| a role enrolled for `write` | reads and writes rows, if enrolled on working copies | no privilege | reads and writes rows | no privilege | as granted | no privilege |
| `admin`, `root` | everything | reads; can change the option | everything | everything | everything | everything |

**Each credential's authority, from each origin.** The servers accept every account from every address that reaches the port (F-20). "Kept on the service's machine" is a rule about where a credential's file is, **not something the server enforces.** Whether a server can tell a local client from a LAN one behind the published port and the socket units is not known [G-22]; until it is, each row holds for a holder at any address.

| Credential | Kept, by policy | What its holder can do, from anywhere it reaches the port | What bounds it |
|---|---|---|---|
| `postgres`, `root` | the service's machine | everything | nothing |
| `admin`, PostgreSQL | the service's machine | own and change all sample data; reset; create databases and roles; enroll any role, itself included, anywhere; end sessions; reach any copy by enrolling itself | not a superuser; cannot alter a template, `demo`, a namespace's owner or `postgres` [G-1, G-6] |
| `admin`, MySQL | the service's machine | everything | nothing |
| `demo` | any machine (DL-075 item 5) | read every working copy, and a namespace's copies if enrolled. On MySQL: take any named lock, and so make a copy or a reset report busy; change its own password, unless G-16 finds a way to refuse it | the read profile on PostgreSQL; its grants on MySQL |
| **a namespace's owner** | **question 1 of section 9** | **every copy of its namespace: read, write, drop, re-create, renew or release, whoever made it.** Take the locks, and so make any namespace's commands report busy. **Use storage without limit:** the limits are the CLI's (2.6). On PostgreSQL also: create a database of any name from any template, outside its namespace. | PostgreSQL: it cannot connect to a working copy or a template, nor alter a role. MySQL: nothing outside its pattern, and it cannot grant. |
| a role enrolled for `write` on working copies | wherever DataIntent's record puts it | change rows of every working copy, from any address | no definition change; a reset restores |

- **One credential is one trust domain.** Every holder of a namespace owner's credential controls every copy in that namespace. The CLI's prefix check tells callers apart only if they do not share a credential.
- **Where callers must be kept apart, each gets a namespace and an owner of its own.** Then the engine keeps them apart: by ownership on PostgreSQL, by non-overlapping patterns on MySQL. They still share the disk. [D: `copies.namespaces` takes any number.]

## 5. The one rollout

**It carries, from one build of the final `main`:** the templates and working copies, the account model, the strict read profile, the CLI, the finished README, and the build revision in each registry row and image label, which DL-079 item 5 put no later than this rollout. It is the second live rollout and the only one planned (DL-085 item 2; DL-103 item 2).

### 5.1 What changes on the live service

Each row follows from sections 2 to 4, or is decided where it says [D].

| | Change |
|---|---|
| **Images** | All three engines' images are replaced. PostgreSQL's gains the hook's library and the policy extension. Each holds the finished README (F-25). Consoles are rebuilt only if their inputs changed. |
| **Initialisation** | The start wrappers apply each namespace owner's password key and leave that account locked without it. PostgreSQL's refuses a data directory without the policy marker (H-12). |
| **Accounts** | New: each namespace's owner, and the PostgreSQL groups. Changed: `demo` on MySQL, narrowed; on PostgreSQL every role that is not an administrator is held to the floor, and reaches a working copy only by enrollment. `admin` gains `pg_signal_backend`. Nobody is enrolled for `write`. |
| **Passwords** | The four existing values are **not** rotated. `.env` gains one key for each namespace. [D: nothing about them changed.] |
| **Data** | Both data volumes are renewed from the images (`MR:` B-10). Everything made there since is gone: DataIntent's roles, `di_template`, its fixture databases, any edit, any enrollment. |
| **SQLite** | Each dataset file must be the same bytes as today, unless its dataset changed: held by SHA-256 against a read-only capture taken before. Only the registry file changes. [D: DataIntent pins one of them (`MR:` A-13).] |
| **Configuration** | `megasamples.yaml` gains `templates` and `copies`. MySQL's binary log is off (2.4). |
| **Storage** | What the storage report measured (2.6), and the rollback's inputs: cold copies of today's volumes, and both image sets. |
| **Unchanged** | Engine versions, ports, the LAN forwards (DL-075), the consoles' addresses. |

### 5.2 The order

Decided here [D: review 1's finding 10. Round 1 merged before the candidate was validated and compared, and put the README after the deployment. DL-085 item 3 requires the comparison before pull request #14's content merges; DL-103 puts the README before the one rollout; and the images hold the README, so the deployed build must be the final `main`'s.]

| # | Step | It must show |
|---|---|---|
| 1 | **The feasibility gates** of 6.1, on the isolated stack, on a branch that merges pull request #14's branch first (section 7). | Each gate Passed, or its stated consequence taken. Nothing is built on a gate that has not been run. |
| 2 | **The build,** test-first, on that branch. | Section 6.2, each with its red and its reversal. The README kept true as it goes (DL-086 item 1). |
| 3 | **DL-078's README,** written by Astra on the same branch, against finished functionality; reviewed by Astra and Fable. | Its review's own two clean rounds. Section 8 is its list. |
| 4 | **The branch's candidate,** built from its head in the isolated store. | The full dataset matrix, the image tests and every native suite Passed. The storage report (2.6). |
| 5 | **DataIntent's comparison against that candidate** (5.3), before anything merges. | Every part that applies, Passed and complete. This is DL-085 item 3's condition. |
| 6 | **The reviews:** the independent review of the hook and the event trigger (4.3); Fable's and Astra's blessing on one head (DL-086). | Both, on the head that step 5 compared. A change after step 5 runs steps 4 and 5 again. |
| 7 | **DL-087's acceptance is recorded.** | Gate 6's declared run met C1. Pull request #14's content does not merge before it (F-26). Steps 1 to 6 may all come before. |
| 8 | **The merge into `main`,** by a merge commit. | `main`'s tree is the blessed head's tree. |
| 9 | **One build of the final `main`,** at the merge commit, in the isolated store. | Its image IDs recorded. **This is the build that is deployed;** nothing is built again after it. |
| 10 | **That build is qualified:** the dataset matrix, the image tests and the native suites again, and DataIntent's comparison again, on it. | Complete, every case Passed. It differs from step 4's candidate only by the revision in its registry rows and labels; whether that difference could excuse any of this is the two deciders', and is not assumed here. |
| 11 | **The two deciders' approval** of one exact plan and revision (5.6). | Recorded before any live step. A plan that changes afterwards goes back to them. |
| 12 | **The rollout** (5.4), and then **DataIntent's accepting run on the live service** (5.3). | The rollout is accepted only then. The deployment's checkout moves to that `main` (DL-103 item 2). |

### 5.3 DataIntent's comparison, in full

DataIntent's record defines five parts and says that from the next upgrade they are as designed (F-24). This is that upgrade. Round 1 named C1 alone. [D: review 1's finding 11.]

| Part | What it runs (`MR:` section 3) | Why this rollout needs it | Needs, in DataIntent |
|---|---|---|---|
| **C1** · PostgreSQL's suites | `sample02` (shared, fixture, pure), `results-postgresql`, the `cli` jobs: the live service in ordinary mode, the isolated candidate in comparison mode | The profile reaches every role the fixture makes (4.8), and the database list changes. It is also where the routine list is settled (4.2). | packages 1, 2 |
| **C2** · The MySQL provider probe | sign-in, the listing and each describe, as `demo`, on both servers | **`demo`'s MySQL grants change:** its list of schemas is no longer whole, and the `mysql` schema is gone from it (4.4). | packages 1, 2, 3 |
| **C3** · SQLite, freshly staged | the provider's reads and the offline example, on files captured from each stack | The SQLite image is rebuilt. Its dataset files must be the same bytes (5.1), and C3 is the consumer's own check of that. | packages 1, 2, 4 |
| **C4** · Observed identities | each engine's version and the registry digests | Every registry row's build id changes, from `dev` to a revision (F-7). The observed ones must be the ones the candidate is meant to have. | package 2 |
| **C5** · The controls that change an account | the read account's elevation before an export, on each isolated server | The read account's privileges are what this rollout changes. It runs on the isolated candidate only. | packages 1, 2, 3 |
| **The read account's native admission** | `demo` admitted, and an administrator's alias refused | DL-085 item 4 left it Not run until this profile exists. | package 1 |
| **Comparison mode on two versions** | the relocation of C1 to the isolated servers | The record names this rollout as its first use on two versions (F-24). | packages 1, 2 |

- **Each part runs twice:** against the branch's candidate (step 5) and against the final build (step 10). C1 to C4 then run once more on the live service, as the accepting run (step 12).
- **Pass means complete,** by that record's own rules: every case of each part Passed, none Not run, on each target. A triaged failure is not a pass.
- **Declared before each run:** one DataIntent revision, which holds whatever section 11 needed; the parts; the bindings; the image IDs.
- **A part whose prerequisite does not exist is not left out quietly.** If a DataIntent package a part needs is not there when its step comes, the step waits, or the two deciders rule on that part by name, in writing, before the step, as DL-079 did for the first rollout. What is given up is then recorded as lost, not passed.
- **Each failure before the merge is triaged to the service or to DataIntent** (DL-085 item 3), and fixed where it belongs.

### 5.4 The rollout, and its verification

The order is the corrected runbook's [R at each line of `SM:docs/live-upgrade-runbook.md`]; its content is this rollout's.

| # | Step | The runbook's place |
|---|---|---|
| a | Preparation while the live servers run: the backup directory, the retained images and configuration, the archive gates, the rollback set rehearsed in a fresh store, the final build's images imported. | "Prepare while the live servers are still running" (`:268`); importing leaves the running containers as they are (`:630`); an abort here changes nothing (`:936`) |
| b | A quiet point: DataIntent's writers stopped, its standing permission to start the services suspended (`:181`), restart automation paused (`:1094`). | "Final backups and cutover" (`:1045`) |
| c | The capture, then the stop: consoles, then SQLite, then PostgreSQL and MySQL (`:1082`). | DL-088's gate: a missing capture holds before downtime |
| d | **The four checks** (`:1277`): the state table, no project container running, and the recorded identities and data verified. | A refusal or a hold blocks the copy, and has its own route |
| e | Cold copies of each data mount, with their digests. The old volumes are kept (`:1166`). | — |
| f | `.env` gains each namespace owner's key, generated without printing. `megasamples.yaml` gains its two keys. | as the first cutover set its four (`:1170`) |
| g | The stack is started on the imported images with fresh volumes. **Nothing is rebuilt here** (`:1192`). The running image IDs are step 9's (`:1202`). | — |
| h | Verification before clients resume, below. | "Verify before resuming clients" (`:1461`) |
| i | Restart automation restored (`:1238`); the hold released; DataIntent's credential files refreshed, its fixture set up again, and its roles enrolled again. | — |

- **The runbook is revised on the same branch** for a rollout that replaces images without rotating passwords: it is written today for DL-074's versions and its rotation (`SM:docs/live-upgrade-runbook.md:46-56`). The gates are reused as they are. The revision is rehearsed on the isolated store, forward and back (T-22). [D: DL-086 item 1.]

**Before clients resume,** on the live service, read-only except where said [D]:
- each engine's version, and each registry row with its build id;
- **every account:** its configured password signs in, and a wrong one is refused as an authentication failure;
- **every template:** on PostgreSQL its three properties (2.3); on MySQL its read-only option; and a connection or a write refused for each account;
- **the policy is in force:** `megasamples accounts check` finds nothing (4.5);
- **one round trip on each server engine,** as the namespace's owner: a copy of `pubs`, a read of it, its drop. It writes one database of the configured namespace and removes it;
- **one reset of `pubs` by the template path, with `--if-idle`,** on PostgreSQL. It replaces a pristine database with a pristine one;
- SQLite's files against the capture (5.1).

### 5.5 The rollback

The routes are the runbook's [R at each line]; choosing among them is as it says.

| When | Route | What is lost |
|---|---|---|
| Before the stop | Abort the preparation (`:936`). | nothing |
| The stop was refused, or the gate did not pass | Restart the original containers on their unchanged volumes (`:809`). | nothing |
| After the candidate started | Stop the candidates behind the same capture and gate; then restart the exact originals on the volumes that were kept (`:2215`), or restore the cold copies (`:1776`). | what was written to the candidate. Its volumes are kept. |

- **A rollback is of the whole engine.** The profile is in the image and in the data together. [D]
- **Image and data that do not match, by engine.** [D: review 1's P3: round 1 said this of all three engines.]
  - **PostgreSQL:** an image without the library is meant not to start on policy data, and the policy image refuses data without its marker (H-12). Both are for T-22 to show.
  - **MySQL:** nothing refuses. The old image is the same server version; everything this design adds there is in the data. The runbook's own check of image IDs is what holds it (`:1202`).
  - **SQLite:** there is no server and no such pairing.
- **After a rollback** `.env` is the kept original, DataIntent's fixture is set up again, and each namespace owner's credential file is removed.
- **The rollback has never restored the live service** (DL-087 item 8). Its rehearsal for this rollout is T-22, in the isolated store.

**How long the rollback's inputs are kept.** [D: review 1's finding 11: round 1 left out the standing condition.]
- **The first rollout's inputs** stay under their own rule: until its accepting run and DataIntent's package 3's gate have both passed (F-24). This rollout does not release them. If they are still held when it starts, they are kept beside its own.
- **This rollout's inputs** are kept until its accepting run (step 12) has passed, **and** package 3's gate has passed on the service as it then is.

### 5.6 What is approved before the rollout, and by whom

**The two deciders give the specific approval for this rollout, on one exact plan the coordinator directs.** [R: `DL:` DL-105; `DI:docs/bootstrap/approvals.md`, MEGASAMPLES-ROLLOUT-2, at `3ada3517`] That replaces the owner's approval at the time, which DL-103 item 2 and DL-085 item 7 had asked for.

- **The coordinator's direction sets:** when it runs; which agents and runs are paused for it; the quiet window; the runbook, with its quiescence gate; and the acceptance and rollback evidence.
- **It is one exact plan and one revision,** not a standing permission. **A plan that changes after approval goes back to the two deciders.**
- **It comes after** DL-087's acceptance, and after the design, the build, the README and the reviews are merged (5.2).
- **What it does not grant:** host installation, changes to the Docker daemon, credentials outside the service's own `.env`, and destructive clean-up beyond the plan. Each stays reserved as it was.

**What the plan the deciders approve must state,** from this design [D]:

| # | What | Where |
|---|---|---|
| 1 | **Stopping the shared services, replacing their images and renewing their data volumes,** at one revision of `main` and its image IDs. It removes everything DataIntent made there. | 5.1; 5.2 step 9; 5.4 |
| 2 | **The permission change,** with the final content: it reaches every role that is not an administrator, on PostgreSQL; and `demo` on MySQL. DL-085 item 7 asked that the approval say so. | 4.1 to 4.4 |
| 3 | **A compiled hook in the PostgreSQL server,** and what it refuses, with its independent review. | 4.3 |
| 4 | **Which credentials leave the machine,** as the deciders answered question 1. | section 9; 4.9 |
| 5 | **What is accepted of MySQL passwords,** if gate G-16 made it a question, as they answered question 2. | section 9; 4.5 |
| 6 | **The public contract and the persisted formats** at version 1, as they answered question 3. | section 9; 3.8 |
| 7 | **The storage report,** measured on the final build, with the budget and limits chosen from it. **MySQL without a binary log.** | 2.6; 2.4 |
| 8 | **The acceptance evidence:** the final build's qualification and DataIntent's comparison on it, and the accepting run that follows the rollout. | 5.2 steps 10 and 12; 5.3 |
| 9 | **The rollback evidence:** the routes, their rehearsal on the isolated store, and how long each rollout's inputs are kept. | 5.5; T-22 |

## 6. The test plan

**Test-first, on the isolated stack.** The plan is decided here [D].

- **Two kinds, in this order.** [D: review 1's finding 16.]
  - **Feasibility gates** (6.1) test an engine's own behaviour, with no CLI code. They run first. A design choice that rests on one is not built until it has passed.
  - **Regressions** (6.2) test what is built. Each has a red that fails for its own stated reason, and a reversal.
- **A behaviour's red is run against the commit before that behaviour's change.** "The command does not exist" is the red of a command's first case only. Every later behaviour's red must fail for the reason its row gives, on an implementation that lacks only that behaviour.
- **Two levels.** Unit cases run in `make check`, with no container. Native cases are opt-in, and refuse any store but the isolated one, as `PR14:tests/test_strict_read_native.py:20-30` does.
- **A native case that cannot run is Unsupported or Not run, never Passed.**
- **The failing command and its result** go into the commit message.

### 6.1 Feasibility gates

Each is an engine's own behaviour that this design leans on and nobody has shown. "If it fails" is what the design does then; none is assumed to pass.

| Gate | What is shown, natively | What rests on it | If it fails |
|---|---|---|---|
| **G-1** | A PostgreSQL database that is a template, accepts no connections and is the superuser's: refuses every account's connection; is copied by an account that only may create databases; is copied twice at once, and during another copy; cannot be altered, renamed or dropped by `admin`. | 2.3 | The template model returns to the design. |
| **G-2** | What a copy carries and what it does not: each row of 4.8's first table, grants to group roles among them. A role in a data group with no `CONNECT` cannot reach the tables. | 4.1, 4.6, 4.8 | The grants are given by a step after each copy; 4.1 is revised. |
| **G-3** | Two renames, an opening and a row's update commit or roll back as one transaction. A rename needs no session on either database. A closed database keeps its sessions and refuses new ones. `admin` with `pg_signal_backend` ends `demo`'s sessions. | 2.3's reset | The swap is withdrawn; the reset returns to the design. |
| **G-4** | The hook's cases: a creator without the owner's rights (H-2); an error forced after the copy, and what files remain (H-3); the same error with no hook loaded at all. | 4.3 | H-3's resolution, step 4. |
| **G-5** | Routine admission: on pull request #14's candidate, what a fresh role can and cannot run (H-1); with the list on `PUBLIC`, the same. What `pg_export_snapshot`, `pg_current_snapshot` and `pg_database_size` change; that a snapshot exported under the floor is imported by another session under the floor. Whose rights a trigger's body runs with. | 4.2 | P-1 and P-3 are revised from what is found; the provider's needs go back to DataIntent. |
| **G-6** | A role without `CREATEROLE`: what `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES` let it change, and whether anything but itself. Whether `admin` can change `demo`, a namespace's owner or `postgres`. | 4.5, the hook's third rule | The rule is narrowed to what was shown, or the question goes to the deciders as MySQL's does. |
| **G-7** | A session's advisory lock: it is per database; it is held while that session runs `CREATE DATABASE`, also after the client is gone and until the server ends the statement; it ends with the session. | 2.2 | Another server-side exclusion with the same three properties is found, or sweeping is not offered on PostgreSQL. |
| **G-8** | A database's comment is read by any role from any database. A plain `DROP DATABASE` refuses while any session is connected. | 2.2, 2.3 | The identity is bound another way; the engine check is replaced or sweeping is not offered. |
| **G-9** | PostgreSQL when the data volume fills during a copy by each strategy, a reset, and a ledger write: the server stays up; no part of a database remains; every working copy and template is whole. | 2.6 | Copies on PostgreSQL are not offered until the design has a guard. |
| **G-10** | MySQL's `READ ONLY = 1`: every account's write is refused, `root`'s too; what changing it needs; it can be read, by many `INSERT … SELECT` at once. | 2.4 | The MySQL template returns to the design. |
| **G-11** | MySQL's grant patterns: an escaped underscore is literal and an unescaped one is not; a holder of `P\_%` can do nothing outside it; a grant by an exact, escaped name reaches that schema alone; what the server's `partial_revokes` setting does to each. Proved against every kind of schema in 4.4's list. | 2.1, 4.4 | Namespaces on MySQL return to the design. It is a P1's ground. |
| **G-12** | A grant on a schema, by name and by pattern, after that schema is dropped and made again. | 2.4, 4.4, 4.6 | Whichever way it falls is built on: the working copies' grants are re-applied by the reset if they do not survive. |
| **G-13** | Definitions recorded from one schema and replayed into another give the same objects: tables with generated columns, foreign keys and full-text indexes; views; routines; triggers; events. Held to each dataset's own verification. | 2.4 | Each kind that fails excludes the datasets that use it, by name. |
| **G-14** | A schema that another's foreign keys point into is dropped and refilled with checks off, and every such key is whole afterwards. | 2.4, `oracle_hr` | `oracle_hr` is excluded as `oracle_oe` is. |
| **G-15** | MySQL's locks and drops: a named lock is held while its session runs a statement after the client is gone, and ends with the session; whether it can be shared; a drop waits on a transaction and gives up on a timeout; whether an idle session on a schema is visible to anyone. | 2.2, 3.6 | Sweeping is not offered on MySQL. |
| **G-16** | A MySQL account changing its own password: every way to do it, and every candidate way to refuse it (4.5). Repair by `root`. | 4.5 | Question 2 of section 9. |
| **G-17** | MySQL when the disk fills during a copy, a reset and a ledger write: as G-9. | 2.6 | As G-9, for MySQL. |
| **G-18** | The shipped MySQL starts and passes its image tests with the binary log off. | 2.4 | It stays on, and the storage report counts it. |
| **G-19** | On the filesystems a copy is made on, a bind mount shared by a host and a container among them: exclusive creation and a hard link each fail when the name exists, and two racing publications leave exactly one winner. | 2.5 | Another exclusive publication is found, or SQLite copies are single-caller and say so. |
| **G-20** | `flock` held by one process is seen by another, across the host and a container on one mount. A file removed while a reader has it open: what that reader sees. | 2.2, 2.5 | Sweeping is not offered for SQLite. |
| **G-21** | Psycopg's wheels on the supported Python versions; the dependency group keeps `uv sync --locked` as it is. | 3.5 | The pure-Python driver; the dependency layout is revised. |
| **G-22** | Whether each server sees a client on the machine and one on the LAN as different origins. | 4.9 | Nothing changes: 4.9 already assumes it cannot. If it can, an origin rule for the administrators' accounts becomes possible, and is proposed. |

### 6.2 Regressions

| # | Behaviour | Its red, on the commit before it | Its reversal | The class it covers |
|---|---|---|---|---|
| T-1 | **The image ships each configured template** as 2.3 and 2.4 say. | The image test finds no `<database>_start`. | Built with connections allowed: a connection is accepted. | Every templated database on both engines; every account, the superuser's over the network and on the loopback. |
| T-2 | **Nothing writes or changes a template** (criterion 3). | With the template owned by `admin`, its `ALTER DATABASE` succeeds. | The same, planted. | Every account, against rename, owner, the two flags, drop, comment and grant. On MySQL: every account against a row change, a definition change and the option. |
| T-3 | **Namespaces do not overlap** (2.1). | A configuration with the prefix `oracle` builds. | The check for a foreign namespace removed: `di_copy` builds beside `di`. | A table of prefixes against database names, templates, `megasamples`, engine schemas, other prefixes and foreign namespaces; and generated pairs, including one that differs only by an underscore. |
| T-4 | **The reach tables of 4.9,** cell by cell (criterion 4). | A fixture-like role enrolled in a namespace: the expectation that `admin`, inheriting it, is refused, fails. That is round 1's table, shown wrong. | `CONNECT` on a working copy left with `PUBLIC`: a namespace's owner writes a sample. One planted per column. | Every account against every kind of database, for connect, read, row write, definition change, drop, rename and grant; each right held directly, through one role, through two, and as a role that can only be taken up; on the fixture's real topology (F-23). |
| T-5 | **Permissions and enrollment are kept through template creation, a copy and a reset** (criterion 7). A fingerprint of each object's owner and privileges, the default privileges, the event trigger and the extension is equal across the image's working copy, a test copy and a reset one. **On MySQL a copy's definers are its namespace's owner, by design, and are compared as that;** everything else is equal. | A reset that omits the three `CONNECT` grants: an enrolled writer cannot connect afterwards. | The same omission, planted; and a per-account grant in place of the group's, which the next reset loses. | Every templated database, on both engines; a role enrolled before a reset and checked after it. |
| T-6 | **Enrollment** (4.6). | An enrolled writer is refused a working copy: there is no group that holds `CONNECT`. | The privilege check removed: `admin`'s own alias is enrolled for `write`. | Enroll, unenroll and list, for working copies and for a namespace, `read` and `write`, on both engines; a session open across an unenrollment, with what it can then do recorded; a privileged role refused. |
| T-7 | **The hook closes each new database or refuses it, and the trigger closes each new routine** (H-2 to H-5, H-9 to H-11). | A creator with only `SET ROLE` to the owner is not refused before the copy. | The library not loaded. The confirmation removed. The check before the copy removed: the forced failure leaves files. | Creator (superuser, `admin`, a namespace's owner, the `SET`-only role) by template (`template0`, `template1`, a `_start`, a fixture-like template) by strategy. Every command that makes a routine, by each kind of creator. A second session that polls the catalog never sees the new database open. Every failure G-4 found reachable: refused before any file is copied. |
| T-8 | **The routine floor is the list, for every role** (H-1, P-1 to P-6). | A fresh role's executable set is not the list. | The list granted to `demo` alone. | `demo`, a fresh role, a fixture-like role, a namespace's owner, a write member; in every kind of database, a later one and a copy included; an exported snapshot imported by a second session. The pull request's own cases, kept. |
| T-9 | **MySQL's grants reach what they name and nothing else** (4.4). | `demo` reads `mysql.user`. With an unescaped pattern, the owner of `copy` reaches a schema named `copyxnorthwind`. | The grant on `*.*` restored; one underscore left unescaped. | 4.4's list of what the patterns are proved against; every sample schema read by `demo`, its views included, those that cross databases too. |
| T-10 | **No access to a copy outlives it** (2.4). | With round 1's grant per copy: a writer of a dropped copy writes its replacement under the same name. | A grant per copy planted back. | Create, drop and re-create one name, with a different reader and a different writer enrolled each time, on both engines; a creation that fails; a drop of a copy already gone; a dangling grant found by `accounts check`. |
| T-11 | **A MySQL copy is the dataset** (criterion 9). | A copy made without the foreign keys' replay fails the dataset's foreign-key check. | The same; and one view skipped. | Every templated database: its counts, digests, foreign keys, indexes, views, routines and triggers, by the repository's own expectations (`SM:ARCHITECTURE.md:239-249`), run against a copy. The object inventory against the template's. The stated exclusions: exit 4, and no template for `oracle_oe`. |
| T-12 | **The CLI's contract** (criterion 10; 3.2, 3.3, 3.8). | A second line on standard output fails the one-document check. | A password echoed in an error; a changed exit code; an unknown format changed anyway. | Every command by every outcome of 3.3's two tables: the document against its schema, the code, and the promised state checked on the server. The remote commands with no container runtime on the path, and in an install with the two drivers only. |
| T-13 | **Credentials** (3.4). | With the reset's reader reused: an exported `DEMO_PASSWORD` is used in place of the file's. | That reader planted back; expansion allowed. | Each of the three routes; an exported value that conflicts with the file's; a value that asks for expansion; a file open to others; a canary password in no argument, environment, output or log, for each. |
| T-14 | **A change is one locked procedure, and a removal checks identity** (2.2). | A sweep paused after its look, a drop and a re-create of that name, the sweep resumed: it deletes the replacement. | The second read of the identity removed. The change lock released before the record is `ready`. | Each pause point of create, drop and sweep against each other command; a MySQL create whose name already exists: the existing schema untouched; a SQLite publication onto an existing name. |
| T-15 | **Every command against every command.** | A pair from 3.6 with its guard missing, each in turn. | Each guard removed in turn. | **Every ordered pair** of `create`, `show`, `list`, `hold`, `renew`, `release`, `drop`, `sweep`, `reset` by the template path, `reset` by the image path, `reset --reconcile`, a whole engine's reset and `enroll`, on each engine that has both: natively, with the first paused at each of its durable phases by a test-only pause point; and by gated fakes at each step in unit cases. Its invariants: no working copy lost or left closed; no copy removed while leased, held or being changed; no name with two identities; nothing present that `list` or `reset --status` does not show. |
| T-16 | **A reservation is atomic** (2.2, 2.6). | Forty creates at once in a namespace of 32: more than 32 succeed. | The count taken outside the namespace lock. | The count and the size quota; on each engine; with creates that fail and must give their place back. |
| T-17 | **A sweep removes only what 2.2 allows.** | A copy whose lease has ended and that is held by `copy hold` is removed. | Each of the five conditions removed in turn. | Every reason a sweep keeps a copy, on each engine; a creator paused past its lease; an `unmanaged` and an `inconsistent` object: reported, never removed; a session connected on PostgreSQL; a transaction open on MySQL. **The stated blind spots too:** an idle MySQL session and an open SQLite reader, each with no lease and no hold, are shown to be unprotected, so that the README's sentence is true. |
| T-18 | **Sizes and times** (criterion 8), and the storage report (2.6). | The build bakes a selection over its budget. | The budget check removed. | For each templated physical database, with its appended datasets: allocated bytes; a copy's and a drop's time by each strategy; the peak during a copy and a reset. The first-start budgets again. |
| T-19 | **A reset is durable and can be reconciled** (2.3, 2.4; criterion 5). | The CLI killed after the door is closed: the working copy stays closed and nothing reports it. | The phase written after its step, not before. `--reconcile` made to reset again after `swapped`. | The CLI killed after each phase, and its connection cut during each step, on both engines and both paths: `--status` names the phase; `--reconcile` gives the row's outcome; nothing is reset twice. A reader and a writer connected; a client reconnecting in a loop; `--if-idle` for each engine and path of 3.6. |
| T-20 | **One exclusion for both reset paths** (3.6). | A reset by the image path and one by the template path, of one database, both run. | The image path's lock removed. | Each pair of paths on each engine; a whole engine's reset against each. |
| T-21 | **Names and limits** (2.1, 3.7). | A name of 64 bytes reaches the server. | The check moved after the connection. | **Refused, exit 2, with no connection:** empty; a space; upper case; a non-ASCII letter, an emoji, a right-to-left mark; a quote, a semicolon, a backtick; 64 bytes; the suffix `_start`; a double underscore. **Accepted:** exactly 63 bytes; the longest database name with the longest prefix and label; a one-character label. **Exit 5:** a prefix that is not configured. Each lease bound. |
| T-22 | **The rollout and each rollback route, rehearsed** (5.4, 5.5). | The runbook has no route without rotation: its fence test fails. | — | On the isolated store: from `main`'s stack to the candidate, 5.4's verification, and back by each route. PostgreSQL's two refusals of unmatched image and data. |
| T-23 | **SQLite** (2.5). | A truncated copy is published. | The hash check removed; the hard link replaced by a move over the name. | Every staged file; create, drop, hold, sweep; a manifest that disagrees; an older sidecar format left alone. |
| T-24 | **Round trips.** | A record is lost across a restart. | — | Copies, records and leases across a stop and a start. After a whole engine's reset: no copy, each template pristine, each account as shipped, nobody enrolled. Create, drop, and create again under one name: a new identity each time. A list by prefix whose parts sum to the whole list. |
| T-25 | **Passwords** (4.5). | PostgreSQL accepts `demo`'s change of its own password. | The hook's third rule removed. | PostgreSQL: each account without `CREATEROLE`, against each statement form, its own settings and its own default privileges. MySQL: whatever G-16 established, as a case that fails if the engine's answer ever changes; `accounts check` and `--repair`. |
| T-26 | **The image as shipped, and the build revision.** | The registry says `dev` (F-7). | — | The service's record; each namespace's owner locked without its key, and no account passwordless (`SM:ARCHITECTURE.md:250`); MySQL's reset with configured credentials (criterion 12), again. |
| T-27 | **When the disk fills** (2.6). | Whatever G-9 and G-17 showed unguarded. | Each guard removed. | Data, the write-ahead log or undo, a record's write, and a clean-up, each failing for want of space: the exit, and that every working copy and template is whole. |

**Then DataIntent's own:** its comparison against the candidate and against the final build (5.3).

## 7. Pull request #14's disposition

**It is folded into this work's branch. It is not rebased, and its content does not reach `main` by itself.** [D]

- **Why not by itself.** If H-1 is as read, `main` alone with it would build a server on which no role but `demo` and `admin` can call a built-in routine. The owner asked that what follows uses a build of `main` (DL-103); a `main` between two merges would be a broken one. DL-085 item 3 already holds it until the account model exists.
- **Why folded.** Its grants, its hook and its tests are the ground the templates stand on. They are one account model, reviewed once.
- **How.** The work's branch starts from `main` and merges `fix/strict-read-account` at `2879fc4` as its first commit. It merges without conflict (F-15). Its history is kept; nothing is rewritten.
- **When its content reaches `main`:** with the branch, at step 8 of 5.2. That is after DataIntent's comparison has passed against the branch's candidate (DL-085 item 3) and after DL-087's acceptance (DL-085 item 1). Pull request #14 is closed then, pointing at the merged one. [D: review 1's finding 10.]
- **Its tests are not loosened.** Where this design changes an expectation, that is a test-only change of its own, saying why: the grant to `PUBLIC` in place of `demo`; the named built-ins; `demo`'s MySQL grants.
- **Its evidence is made again.** Its receipts describe a candidate that grants 1,663 signatures to `demo`. The final candidate does not. The branch publishes the final candidate's inventory and receipts, and removes the earlier ones from the tree; they remain in history at `2879fc4`. [D: DL-086 item 1.]
- **Its conditions under DL-085 item 3,** and where each is met: the comparison against the candidate (5.2 step 5; 5.3); the other roles (4.2, 4.8); the list reconciled (P-3, P-7); the independent review (4.3 is its input); the account model (section 4); permissions kept (T-5).
- **Carried on the same branch:** the ten notes that pull request #16's review left for "the next sql-megasamples PR", C-1 to C-10 (`DI:docs/work/megasamples-pr16-review-loop.md:17-27` at `d02f7384`). [R]

## 8. What the README must document

For DL-078's writer, on the same branch, before the merge (5.2 step 3). Each is a fact this design fixes [D]; the review checks each against the repository.

1. **The model, with a picture:** a template, a working copy, a test copy and a reset, for one dataset. One diagram, and a table of how the three engines differ.
2. **Which databases have a template,** per engine, with each one's measured size and copy time, the budget, and how to configure it.
3. **Namespaces:** what a prefix is, why it may not overlap, and how to add one with its own owner.
4. **A copy's life:** reserved, ready, leased, held, released, swept. What a sweep will not remove, and the two cases it cannot see (2.2).
5. **The commands,** each with one example and its JSON.
6. **The exit codes,** both tables of 3.3, and what a script does on 8.
7. **Credentials for scripts:** the three routes, that nothing in the environment is read, and that a namespace's owner is locked until its key is set.
8. **Using it from a development container or another machine:** the install, the one port each engine needs, and the staged directory for SQLite.
9. **The accounts,** as 4.9's tables: what each can reach, that an account reaches what it inherits, and what each credential's holder can do from any address. It replaces today's two-row tables (`SM:README.md:120-123`, `:247-255`).
10. **Enrollment:** how an account is given the working copies or a namespace, and that a reset of one database keeps it.
11. **The read profile on PostgreSQL:** what a reader cannot do, where the list is, and its limit (H-14). It replaces the sentence that `demo` "still has `TEMPORARY`" (`SM:README.md:163-167`; `SM:.env.example:14-17`).
12. **What changed for someone who used the service before:** a new database is closed until its owner grants `CONNECT`; a new routine until its owner grants `EXECUTE`; MySQL's `demo` reads the sample schemas only; an account cannot change its own password on PostgreSQL.
13. **What is not claimed:** MySQL is not a strict read profile; a MySQL reset is not atomic and cannot be undone; whatever G-16 established about MySQL passwords; a template on MySQL can be read by administrators; SQLite has no accounts; the limits bind the CLI, not a credential's holder.
14. **Resets:** the two paths, what each does to a connected client, `--if-idle` and where it is refused, `--status` and `--reconcile`. It revises "Putting the data back" (`SM:README.md:281-325`).
15. **The contract and the formats,** and their compatibility policy (3.8).
16. **The rollout runbook's** new route.

## 9. Questions for the deciders

By the owner's direction of 2026-11-20 (DL-104) these go to the two deciders, Astra and a Fable decider who is not this drafter. They are only what is hard to change later: security posture, persisted formats and public contracts. One question for each decision. Everything else is decided above.

### Question 1 · Which credentials may leave the service's machine, and shared or separate?

**What is at stake.**
- A credential, once sent, is sent: taking it back means changing the password everywhere it is used.
- The servers accept every account from every address that reaches them (F-20). Keeping a credential on one machine is a rule about its file, not a limit a server enforces, unless G-22 shows a server can tell the origins apart.

**Each credential's effective authority, from any address that reaches the port** (4.9 has the full table):

| Credential | What its holder can do | What it cannot |
|---|---|---|
| `postgres`, `root`; MySQL's `admin` | everything | — |
| PostgreSQL's `admin` | own and change all sample data; reset; make databases and roles; enroll any role, itself included; end sessions | alter a template, `demo`, a namespace's owner or the superuser [G-1, G-6] |
| `demo` | read every working copy. On MySQL also take any named lock, and change its own password unless G-16 finds a refusal | write anything |
| **a namespace's owner** | **every copy in its namespace, whoever made it: read, write, drop, replace.** Make any namespace's commands report busy. **Use storage without limit:** the limits are the CLI's. On PostgreSQL also create a database of any name. | write a working copy, a template or an account; on MySQL anything outside its pattern, and it cannot grant |

**The options.**

| | What it is | What it makes hard to change later |
|---|---|---|
| **(a) None leaves.** | Copies are asked for only on the service's machine. `demo` alone is sent, as DL-075 item 5 already allows. | Little: a credential can be sent later. But DL-077's "from a separate machine" is not met meanwhile, and DataIntent's harness is built for one machine. |
| **(b) One shared namespace and owner,** its credential on each machine that makes copies. | Every holder controls every copy there. That is shared trust. | Splitting it later: the prefix is in every consumer's configuration and in every script, namespaces are baked into the image, and the one password must be changed on every machine at once. |
| **(c) A namespace and an owner for each machine or consumer** that must be kept apart. | The engine keeps their copies apart: by ownership on PostgreSQL, by patterns that cannot overlap on MySQL. They still share the disk and the locks. | Each new consumer is a configuration change and a rebuild. Merging two later is easy; nothing else is fixed by it. |

**Recommended: (c) wherever a credential leaves the machine, and never an administrator's or a superuser's.**
- **Why:** it is the only option under which one holder cannot drop or replace another's copies, and a leaked credential is one namespace's to rotate. Its cost is one configured namespace each.
- **What it does not buy:** a bound on storage, or on busy locks. Those rest on the LAN being the trusted one of DL-075, under every option.

### Question 2 · If MySQL cannot refuse an account's change of its own password, what is accepted?

**It is asked only if gate G-16 finds no way to refuse it.** If one works, it is built, and this is not a question.

**What is at stake.**
- **The requirement stands:** neither engine's `demo` should be able to. PostgreSQL's is refused by the hook, subject to G-6.
- **If MySQL cannot,** then any holder of `demo`'s password, from any address, can replace it: repeatedly, and with a value everyone knows. Each time, the probe fails and the consoles cannot sign in until someone repairs it. It gains no privilege: `demo` reads what `demo` read.

**The options.**

| | What it is | What it makes hard to change later |
|---|---|---|
| **(a) Detection and manual repair** (4.5). | The probe and `accounts check` report it; `--repair` or a restart restores it. Nothing stops a repeat. | Nothing in the service. But every LAN machine goes on sharing one read credential, and DataIntent's setup is written for that. |
| **(b) Repair on a timer** as well. | It bounds each outage and undoes a known value. It is a privileged job in or beside the server, and it also undoes an administrator's own change made in SQL. | A second place where passwords are set, which every later change to accounts must respect. |
| **(c) No shared read account beyond the machine, on MySQL.** | `demo` stays for the consoles and the probe, which are on loopback. Each LAN machine gets a read account of its own, made and enrolled by `admin`. A holder can then lock out only itself. | The account a LAN client signs in with: it is in DataIntent's developer configuration and its credential export (DL-075 item 5). Going back to a shared `demo` later is easy; moving to (c) later means changing every such machine. |

**Recommended, if the gate makes it a question: (c).**
- **Why:** it is the only one that removes the shared harm; (a) and (b) only shorten it. It uses enrollment, which is built anyway (4.6).
- **Its cost:** one account for each LAN machine, enrolled again after a whole engine's reset. And PostgreSQL would keep a shared `demo`, so the two engines' LAN accounts would differ.

### Question 3 · The public contract and the persisted formats, at version 1

**What is being fixed** is 3.8's table: the JSON envelope and results; the exit codes and what each promises; the commands and options; the records in the servers (comments, ledgers, operations); SQLite's manifest and sidecar; and the names `_start`, the group roles and the namespaces' roles. DataIntent will pin a revision of the CLI and consume all of them.

**The options.**

| | Compatibility | Migration | What it makes hard to change later |
|---|---|---|---|
| **(a) Version 1, with 3.8's policy.** | Within a version, only additions. A removal, a rename or a change of meaning raises `schema` or `interface`. A CLI that meets an unknown format changes nothing there. Until the repository's first published release the numbers may rise freely, each time with a line saying what changed; from then, the previous interface works for one release. | A server's records are never migrated in place: a new image renews the volumes. A consumer's SQLite files are read one format back, and anything older is left alone. | After the first release: an exit code's meaning, a member's name, a record's format. Each then costs a release of overlap. |
| **(b) Nothing promised until the first release.** | Consumers pin a commit and nothing else. No numbers. | None. | Little now. But a consumer cannot tell a compatible change from a breaking one, and DataIntent's check of the interface before use (`ED:` 4.4) has nothing to check. |
| **(c) Frozen now.** | Version 1 with the overlap rule from today. | As (a). | Everything listed, from the first use. The build has not yet shown what the gates will change. |

**Recommended: (a).**
- **Why:** it gives DataIntent a number to check from the first use, and keeps the freedom to correct version 1 while the gates and the build can still show it wrong.
- **What stays hard under any option:** the exit codes. A harness maps them to its own results the day it is written.

**Decided here, and told, not asked:**
- `demo` on MySQL stops seeing DataIntent's fixture databases, which DL-079 item 3 had allowed (4.4).
- A copy's namespace cannot be `di_…` where `di\_%` is another principal's (2.1).
- A namespace's owner on PostgreSQL can create a database outside its namespace; the engine is not made to refuse it, because that would be more compiled code in the server (4.1). An image can add it later.
- A reset's default still disconnects clients. Whether DataIntent's automation defers is its own question 6.

## 10. What is still only inferred

Every load-bearing behaviour is a gate (6.1). These remain marked [I], and nothing is built on them:
- that MySQL has no comment on a schema, and cannot rename one;
- that keeping `admin` as a definer in a copy would need a privilege to run code as `admin`;
- that only the server itself can vacuum a database nobody can connect to;
- H-8, H-10, H-11 and H-14's readings of the engine, which the independent review confirms or corrects;
- that MySQL allows a name one byte longer than PostgreSQL.

**Sizes:** none is asserted. T-18 measures each.

## 11. What this means for DataIntent

Not decided here. Each is a consequence its own records take up, and the comparison of 5.3 is where each shows.

- **A copy's namespace is not `di_…`** on MySQL, and by the one rule not on PostgreSQL either (2.1). Its fixture's name guard and F-05's wording do not cover it; its approvals name the namespace.
- **"Never a copy in use" is met in a narrower sense** (2.2): leased, held, being changed, or visibly in use. Its harness renews a lease or runs `copy hold` for as long as it uses a copy. Without either, an idle MySQL session or an open SQLite file is not protected.
- **Access to a copy is by enrollment, not per copy** (4.6). Its setup enrolls `di_reader`, or a writer of its own, in its namespace, on the service's machine, and again after a whole engine's reset.
- **Its edit tests' writer on working copies** is a role `admin` makes and enrolls. None is enrolled on the live service by this rollout.
- **`admin` reaches a copy once a fixture role is enrolled** (4.9), so R-35 holds against every account but the administrators.
- **The database list grows:** a `_start` beside each templated database (`ED:` 3.6).
- **A fixture role cannot connect to a working copy** unless enrolled. It could before, and read nothing.
- **The fixture grants `EXECUTE` on its own routines,** and `TEMPORARY` where a case needs it (4.8).
- **A fixture role cannot change its own password or settings** on PostgreSQL. `admin` still sets them (F-16).
- **MySQL's `demo` no longer sees fixture databases,** so the case that asserts it changes, and what the provider says of `demo`'s list with it (`MR:` 2.10).
- **Its criteria 6 and the door** (`ED:` section 5; section 7, rule 4): on PostgreSQL the reset's step c is the door, for every account. On MySQL there is none, and `--if-idle` is refused there.
- **An unknown outcome of a reset** is read with `reset --status`, not `copy list` (3.3).
- **Its comparison's five parts all apply** to this rollout (5.3), with the packages each needs.
- **Its SQLite staging** can take `template stage`'s directory and manifest in place of its own capture (`ED:` 3.5). That is its choice.
- **Its dependency review** covers the package at one commit with two drivers (`ED:` 4.4).

## 12. Round 2: review 1's findings, and what changed

Every finding was to fix now (DL-101). None is declined.

| # | Finding | What changed | Where |
|---|---|---|---|
| 1 | **P1 · MySQL prefixes can grant access to working copies, templates and F-05's fixtures.** | A prefix is a namespace that may overlap nothing: not a database, a template, the registry, an engine schema, another namespace, nor a declared foreign namespace such as `di`. The build refuses it. Every underscore in every schema pattern is escaped, in database names too. An audit reports any later grant that reaches in. `di_copy` is refused beside `di`, and DataIntent is told. The patterns' behaviour is gate G-11, and T-3 and T-9 prove the grants against each kind of schema. | 2.1; 4.4; 4.5; G-11; T-3, T-9; section 11 |
| 2 | **P1 · MySQL copy grants survive deletion and leak into a replacement.** | No copy has a grant of its own, on either engine. `--read` and `--write` are withdrawn. Access is the namespace's, given once by enrollment, by `admin`. The namespace's owner loses the grant option. So nothing made for one copy can reach the next; a failed creation and a drop of an absent copy have no grant to clean. T-10 re-creates a name under different readers and writers. `accounts check` finds a dangling grant made by hand. | 2.4; 4.4; 4.6; T-10 |
| 3 | **P2 · Name uniqueness does not serialize a copy's lifecycle.** | Each copy has an identity and a durable record. A change lock on the server covers each whole change, and is held by the session that runs it. A removal reads the identity again. A place is reserved atomically, by count and by size. A creation cleans up only what it made: a MySQL schema that already existed is never touched. SQLite publishes by exclusive creation and a hard link. | 2.2; 2.4; 2.5; 3.6; T-14, T-16 |
| 4 | **P2 · Age is not evidence that a copy is unused.** | The rule by age is withdrawn. A sweep needs five conditions: a lease that has ended, the change lock, the use lock, the same identity, and the engine's own consent. A creator that is paused holds its lock for as long as it lives. `copy hold`, `renew` and `release` are the protocol. What stays invisible (an idle MySQL session, an open SQLite reader) is stated, tested as a limit, and returned to DataIntent as a narrower meaning of criterion 11. Where a gate fails, sweeping is not offered. | 2.2; 3.1; G-7, G-15, G-20; T-17; section 11 |
| 5 | **P2 · Reset recovery cannot satisfy the stated outcome contract.** | Each reset writes its phase before each step. `reset --status` reads it; `reset --reconcile` settles it, and its table says which way for each phase: a closed door is opened, a committed swap is finished, and nothing is reset twice. MySQL's row is written before the drop, and "interrupted" is read from the row and a free lock. A drop no longer closes a copy before waiting. Each exit's promise is defined per command, and a command that cannot confirm it returns 8. The swap rests on gate G-3 and is withdrawn if it fails. | 2.3; 2.4; 3.1; 3.3; G-3; T-19 |
| 6 | **P2 · Reset paths do not share their exclusion and idle guarantees.** | Both paths take one lock on the server and write one operation row. A whole engine's reset takes every database's lock first. `--if-idle` is defined for each engine and path: PostgreSQL's image path gets the same door; MySQL and SQLite refuse it before any change, exit 4. | 3.6; 2.3; T-19, T-20 |
| 7 | **P2 · The working-copy editor has no durable access path.** | Enrollment: two working-copy groups hold `CONNECT` on every working copy, a reset always grants the same three lines, and who is enrolled is a membership or a named grant that a reset keeps. It is a command, built and tested now on the isolated stack. Nobody is enrolled for `write` on the live service. | 4.1; 4.6; T-5, T-6 |
| 8 | **P2 · PostgreSQL's reach table ignores inherited connection rights.** | The rule of effective access is stated. The table says what each account holds itself, with a row for `admin` under the fixture's real topology, where it inherits an enrolled role's `CONNECT`. T-4's red is round 1's own wrong cell, and each right is tested direct, inherited once, inherited twice, and takable. | 4.7; 4.9; F-23; T-4 |
| 9 | **P2 · The local credential fallback contradicts the no-environment contract.** | The `--env-file` route has a reader of its own that reads the file only: literal values, expansion refused, an exported value never read. Its failure when the server holds an exported value is a refused sign-in. T-13 tests a conflicting export and an expansion. The image path's in-container clients keep today's reader, and that boundary is stated. | 3.4; F-22; T-13 |
| 10 | **P2 · The merge and rollout order violates DL-085 and DL-103.** | The order is rewritten: gates, the build, the README on the same branch, the branch's candidate, DataIntent's comparison, the reviews, DL-087's acceptance, the merge, one build of the final `main`, its qualification, the two deciders' approval of the exact plan, the rollout. Nothing merges before the comparison. The deployed build is the final `main`'s, README included. | 5.2; section 7; section 8; F-25, F-26 |
| 11 | **P2 · The second rollout silently reduces DataIntent's comparison scope.** | All five parts, the read account's admission and comparison mode are mapped to this rollout, each with why it is needed and what it needs. A part whose prerequisite is missing waits or goes to the two deciders by name; it is not left out. The rollback inputs' retention names package 3's gate, for both rollouts' inputs. | 5.3; 5.5; F-24 |
| 12 | **P2 · Historical core sizes are not upper bounds.** | Both totals are withdrawn as bounds. Cost is measured per selected physical database, appended datasets included, as allocated bytes. The build enforces a template budget. A storage report gives the peak during a copy and a reset, and is part of what is approved before the rollout. Disk exhaustion is two gates and a regression. | 2.6; F-8, F-9, F-21; G-9, G-17; T-18, T-27 |
| 13 | **P2 · Owner question 1 understates the credential's authority.** | 4.9 gives each credential's effective authority from any origin, says that "kept on the machine" is policy and not enforcement, and names shared trust against separate principals. Any number of namespaces, each with its own owner, can be configured. The question is rewritten on that table, with three choices, and now goes to the two deciders. The namespace owner's grant option is gone. | 4.9; 2.1; section 9, question 1; G-22 |
| 14 | **P2 · Owner question 2 presents detection-and-repair too narrowly.** | Nothing is asserted about MySQL. Gate G-16 establishes what the engine can refuse. The requirement stands until it does. The consequences are stated as they are: repeated change, a publicly known value, each outage; and repair is told apart from prevention. The question is asked only with the gate's result, with a third choice that removes the shared harm. It goes to the two deciders. | 4.5; G-16; section 9, question 2 |
| 15 | **P2 · Persisted formats and public contracts are excluded from owner review.** | 3.8 lists each contract and format with its version, and a compatibility and migration policy. They are a question of their own for the two deciders. | 3.8; section 9, question 3 |
| 16 | **P2 · Several planned tests cannot prove the stated behaviour.** | Feasibility gates are apart from regressions and run first; each says what happens if it fails. Each regression's red is its own, against the commit before it. A 63-byte name is accepted and 64 refused. MySQL's definers are compared as the owner's. T-15 is every ordered pair, natively, at each durable phase. **H-3 has a resolution** if the leak is reproduced, and returns to the deciders if it cannot be closed. | 6.1; 6.2; 4.3 |
| 17 | **P3 · Narrow several factual and compatibility claims.** | F-1 is scoped to commands that contact a running engine. H-1 says which statements would be refused, and is a gate. P-5 admits an exported snapshot explicitly, as the one exception that reaches past its statement. The refusal of unmatched image and data is stated for PostgreSQL only, with what holds for the other two. | F-1; 4.3 H-1; 4.2 P-5; 5.5 |

**Changed by the owner's directions of 2026-11-20** (DL-104, DL-105): what would have been asked of the owner is asked of the two deciders. Section 9 is written for them: one question for each decision, each with its options, the authority or the policy at stake, a recommendation with its reason, and what each option makes hard to change later. The specific approval for the rollout is the two deciders' too, on one exact plan the coordinator directs (5.6).

**Also changed, because the findings made it wrong:** the ledger is the same on all three engines, where round 1 used a comment alone on PostgreSQL; `copier` no longer holds the function behind `pg_stat_activity`, since a lock now says what that was for; and section 10 keeps only what nothing is built on.
