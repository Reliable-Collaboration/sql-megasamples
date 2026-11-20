# Templates, copies, the scripting CLI and the account model: design

**Design record · 2026-11-20 · round 1, the drafter's part. Status: a design under review. Nothing here is built, and nothing here has been run.**

- **What this is.** The design of sql-megasamples' pristine templates and per-test copies, the commands that scripts drive them with, and the account model of both server engines. It carries the strict PostgreSQL read profile of pull request #14.
- **Authority.** The owner's DL-076 (read or write by account), DL-077 (templates, copies and the CLI, built into sql-megasamples), DL-078 (the README) and DL-101 (a problem found in a piece of work is finished in it). The two deciders' DL-079, DL-085 and DL-087. The lines register's lines 2, 4, 10 and 16.
- **Method.** Reading only: no container, no database connection, no network, and no credential file. So every statement about how an engine behaves is an inference until the build's native tests show it. Section 10 lists them.
- **Marks.** Each claim carries one:
  - **[R]** read in the cited file and line;
  - **[I]** inferred, from general knowledge of an engine or from reading code that was not run;
  - **[D]** decided here, with the reason.
  - A table or list whose heading line carries **[D]** is decided as a whole. A file and line cited inside any row is **[R]**. The summary's rows are each decided in the section they point to.
- **Citations.**
  - `SM:` is sql-megasamples at `main`, `e61335f`.
  - `PR14:` is its branch `fix/strict-read-account` at `2879fc4`.
  - `DL:` is DataIntent's `docs/work/decision-log.md` at `d02f7384` (`origin/coordinator/journal-during-full`), and `LR:` is `docs/work/lines-register.md` there.
  - `ED:` is DataIntent's `docs/work/samples-service-editing-requirements.md`, `MR:` its `docs/work/samples-service-requirements-and-architecture.md`, and `DI:` any other DataIntent file, all at `4a8aad61` (`origin/coordinator/samples-p1`).

## 0. Summary

| Area | Decided here |
|---|---|
| **Names** | `<database>_start` is the template, `<database>` the working copy, and `<prefix>_<database>_<label>` a test copy. Lower case, digits and underscores, at most 63 bytes. |
| **PostgreSQL** | The template is a database marked as a template that accepts no connections and is owned by the superuser. A copy is `CREATE DATABASE … TEMPLATE`. A reset builds the new working copy beside the old one and swaps them in one transaction. |
| **MySQL** | The template is a schema set `READ ONLY`. A copy is logical and runs inside the server, from definitions recorded at build. Datasets over a size limit, and one with references into another database, are excluded. A reset is not atomic there, and says so. |
| **SQLite** | The template is the image's file, staged read-only with a manifest. A copy is a verified file copy. Nothing goes over the network. |
| **Templates by default** | The core tier on both server engines. At most about 2.6 GB more on PostgreSQL and 1.8 GB more on MySQL. Extended and generated datasets get one only when named. |
| **The CLI** | `megasamples template`, `copy`, `reset`, `accounts` and `interface`. One JSON document on standard output, nine stable exit codes, the password from a file or standard input only, and no container runtime needed for PostgreSQL and MySQL. |
| **Accounts** | Two group roles carry the data grants through every copy and reset. A new `copier` account makes and drops copies. PostgreSQL's built-in routine allow-list goes to `PUBLIC`, so that every role that is not an administrator gets the same floor. |
| **Password changes** | PostgreSQL refuses them through the hook, for every role without `CREATEROLE`. **MySQL cannot refuse them by grants [I]**; there the change is detected and repaired. That is open question 2. |
| **Pull request #14** | Folded into this work's pull request, not merged by itself: by itself it would leave every role but `demo` and `admin` unable to run a query. |
| **The rollout** | From a build of `main` at the merge commit, by the corrected runbook, after DL-087's acceptance, with the owner's exact approval. |

**Three findings that change pull request #14's content**, each to be shown by a failing test before it is fixed (section 4.3):
1. **Roles other than `demo` and `admin` are left with no built-in routine at all,** operators included, and `admin` cannot grant them back. That reaches DataIntent's `di_reader`, `di_analyst` and `di_login_…`. [I]
2. **The hook can leave a new database open to `PUBLIC` without failing,** when the creator is not the new database's owner. [I]
3. **DataIntent's provider calls two built-ins as a read account that the allow-list refuses:** `pg_export_snapshot()` and `pg_database_size()`. [R]

## 1. What the design rests on

| # | Fact | Where | Mark |
|---|---|---|---|
| F-1 | **Every command of the CLI today reaches an engine through `docker exec`.** The reset starts a second container of the running image, and pipes a dump from it. So none of it works without a container runtime. | `SM:megasamples/credentials.py:29-70`; `SM:megasamples/reset.py:156-197`, `:245-304` | [R] |
| F-2 | **The CLI's output is text for a person,** and a command returns 0, 1 or 2. An unknown command is 2. | `SM:megasamples/cli.py:68-82`; `SM:megasamples/reset.py:384` | [R] |
| F-3 | **Resets exclude each other by a lock file** for one user on one host. Resets from other hosts "must be coordinated separately". | `SM:megasamples/reset.py:101-116`; `SM:README.md:323-325` | [R] |
| F-4 | **PostgreSQL's reset of one database drops it with force,** as the superuser, then restores it. | `SM:megasamples/reset.py:256-260` | [R] |
| F-5 | **Accounts today.** PostgreSQL: `admin` has `CREATEDB` and `CREATEROLE` and owns each sample database and what is in it; `demo` has `SELECT` on the tables. MySQL: `admin` and `root@'%'` hold all privileges with the grant option; `demo` holds `SELECT, SHOW VIEW ON *.*`. | `SM:engines/postgres/init/00-users.sql:10-12`; `SM:engines/postgres/init/20-grants.sql:4-7`; `SM:engines/postgres/Dockerfile:43-55`; `SM:engines/mysql/init/00-users.sql:9-19` | [R] |
| F-6 | **Each health probe signs in as `demo`** with a password file written at start. Passwords are applied at each start from the environment. | `SM:megasamples/engines/postgres/__init__.py:80`; `SM:megasamples/engines/mysql/__init__.py:139`; `SM:engines/postgres/entrypoint-wrapper.sh:17-35`; `SM:engines/mysql/entrypoint-wrapper.sh:19-40` | [R] |
| F-7 | **The registry has one row per database,** with a build id that is `dev` unless `MEGASAMPLES_BUILD_ID` is set. | `SM:megasamples/registry.py:52-88`, `:111` | [R] |
| F-8 | **The maintained deployment's baked data** is 22.712 GiB on MySQL, 20.902 GiB on PostgreSQL and 17.862 GiB of SQLite files. | `SM:docs/live-upgrade-runbook.md:101-105` | [R] |
| F-9 | **The core tier is a small part of it.** PostgreSQL's data directory was 2.6 GB for the 21 core databases. MySQL's was 1,785 MB for 22, measured on 2026-09-03; its largest core database was 160.6 MB of data. | `SM:ARCHITECTURE.md:170-171`; `SM:knowledge/decisions/tier-assignments.md:65-87` | [R]; that both still hold on today's engines is [I] |
| F-10 | **MySQL's binary log grew to 10.9 GB** after the rehearsal of logical resets. The build server runs without one; the shipped server's configuration does not turn it off. | `SM:docs/live-upgrade-runbook.md:109`; `SM:megasamples/engines/mysql/server.py:74`; `SM:engines/mysql/my.cnf:1-11` | [R] |
| F-11 | **One dataset reaches into another database:** `oracle_oe` depends on `oracle_hr`. | `SM:datasets/oracle_oe/dataset.yaml:8`; `SM:README.md:212` | [R] |
| F-12 | **Pull request #14** revokes `TEMPORARY` and routine `EXECUTE` from `PUBLIC` in every database and both templates, grants `admin` what it had, and grants `demo` an allow-list. A compiled hook closes `TEMPORARY` on each new database. An event trigger closes `EXECUTE` on each new routine. | `PR14:engines/postgres/init/10-read-profile.sql:4-35`; `PR14:engines/postgres/read-policy/read_policy.c:29-40`; `PR14:engines/postgres/read-policy/read_policy--1.sql:1-20` | [R] |
| F-13 | **Its grant to `admin` carries no grant option.** | `PR14:engines/postgres/init/10-read-profile.sql:10-13` | [R] |
| F-14 | **Its evidence:** 254 native cases Passed on the isolated stack; 1,663 signatures stay executable by `demo`; MySQL is not claimed strict. | `PR14:docs/strict-read-evidence.md:16-18`, `:30` | [R] |
| F-15 | **It merges into `main` without conflict,** and shares no file with what `main` has gained since its base, `2cf1f3e`. | `git merge-tree origin/main fix/strict-read-account`; the two diffs' file lists against `2cf1f3e` | [R] |
| F-16 | **DataIntent's fixture** makes `di_reader` and `di_analyst` as `admin`, makes each `di_…` database from `di_template`, `template1` or `template0`, and closes it to `PUBLIC` itself. The superuser makes `di_template`. Leased logins are `di_login_` and 32 hexadecimal digits, members of a fixture group. | `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureServer.cs:27-32`, `:131-134`, `:224-230`, `:403-409`; `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureRoles.cs:11`, `:69-71` | [R] |
| F-17 | **DataIntent's provider, as a read account,** calls `pg_database_size(oid)` when it lists databases, and `pg_export_snapshot()` and `pg_current_snapshot()` when it takes a snapshot. | `DI:src/DataIntent.Adapters/Postgres/PostgresSourceServer.cs:238`, `:347` | [R] |
| F-18 | **Of those, only `pg_postmaster_start_time` is in the allow-list.** | a search of `PR14:engines/postgres/init/read-routine-names.sql` for each name | [R] |
| F-19 | **What DataIntent asks of this task:** twelve acceptance criteria, and a CLI contract. | `ED:` section 5; section 4 | [R] |

## 2. Templates, copies, resets and the sweep

### 2.1 Names

| Thing | Name | Rule |
|---|---|---|
| The template | `<database>_start` | `<database>` is the registry's name for the database (F-7). A dataset that appends to another's database shares its template. |
| The working copy | `<database>` | The name people use today. |
| A test copy | `<prefix>_<database>_<label>` | The prefix says whose it is. The label is the caller's, and unique to its run. |
| A reset's transient | `<database>__new_<8 hex>`, `<database>__old_<8 hex>` | PostgreSQL only (2.2). |

- **Characters:** lower-case letters, digits and underscores. A prefix matches `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` and is at most 16 bytes. A label matches `^[a-z0-9]{1,24}$`. [D: one rule for both engines; a label without an underscore keeps the last segment unambiguous.]
- **Length:** a whole name is at most 63 bytes, PostgreSQL's limit, on both engines. [D: one rule; MySQL allows one more [I].] The longest database names today are 21 bytes, so the longest prefix and label still fit. [R: `SM:datasets/` directory names]
- **Reserved:** the suffix `_start`, a double underscore, and the name `megasamples`. The image build refuses a dataset whose database name ends in `_start`, holds a double underscore, or is longer than 49 bytes. [D: so that no working copy can be taken for a template or a transient, and every transient fits.]
- **Prefixes are the service's configuration,** baked at build: `copies: {prefixes: [copy]}` in `megasamples.yaml`. A prefix that is not configured is refused. [D: on MySQL the prefix is a grant pattern, which must exist before the first copy (4.4).]
- **Nothing is found by parsing a name.** What a copy is, is in its marker (2.2, 2.3). [D]

### 2.2 PostgreSQL

**The template.**
- **It is `<database>_start`, with `datistemplate` true, `datallowconn` false, and the superuser `postgres` as its owner.** [D]
  - **It refuses every connection,** the superuser's included, as `template0` does. [I]
  - **Any account that may create databases can still copy it,** because it is marked as a template. [I]
  - **Only the superuser can alter, rename or drop it.** `admin` is not its owner, so `admin` cannot open it. That is the reason for the owner. [I]
- **What it would take to write it:** the superuser sets `ALLOW_CONNECTIONS true`. The superuser's credential never leaves the host, and no command of the CLI does it. [D]
- **It is frozen before it is closed:** `VACUUM (FREEZE, ANALYZE)` in the image build. [D: a database nobody can connect to is vacuumed only by the server's own wraparound protection [I]; freezing first leaves that nothing to do.]
- **Its record is its comment,** set by the build: `megasamples-template/1` and a JSON object with the database, its size in bytes, the copy strategy, the build id and the SHA-256 of its registry row. [D: a database's comment is in a shared catalog, readable from any database by any role [I], so one connection to the `postgres` database serves every command.]

**How the image makes it.** [D: all of it, so that the image's own working copy comes from the path a reset uses.]
1. The dataset is loaded into `<database>_start`, as `admin`, as today (`SM:engines/postgres/Dockerfile:43-53`).
2. The grants of section 4.1 and the read profile are applied there.
3. It is frozen, given to `postgres`, and closed.
4. The working copy is made from it: `CREATE DATABASE <database> OWNER admin TEMPLATE <database>_start`.
5. A dataset with no template is loaded straight into `<database>`, as today.

The build's private server loads the hook, so step 4 closes the new database as a running service would.

**A copy.**

| Step | Statement, as `copier`, connected to the `postgres` database | If it fails |
|---|---|---|
| 1 | The name, the prefix and the limit are checked. The template's flags, owner and comment are read from `pg_database`. | exit 2, 4 or 5; nothing was done |
| 2 | `CREATE DATABASE <copy> TEMPLATE <database>_start STRATEGY <strategy>` | exit 7, or 8 when the connection was lost |
| 3 | `GRANT CONNECT ON DATABASE <copy> TO <role>` for each `--read` and `--write` role (3.1) | the copy is dropped; exit 7, or 8 |
| 4 | `COMMENT ON DATABASE <copy> IS 'megasamples-copy/1 {…}'`: the database, the label, the creation time, the template's build id | the same |

- **The hook closes the copy to `PUBLIC` inside step 2** (4.3). So nobody but its owner can connect between steps 2 and 3. [I]
- **The comment is written last, and is what "ready" means.** A copy without one is `incomplete`. [D]
- **The strategy** is the template's recorded one: `WAL_LOG` up to 64 MiB, `FILE_COPY` above. The build measures both for each dataset and records the faster. [D: DL-077 item 4 names `FILE_COPY` for large ones; the threshold is a starting value until criterion 8's measurement.]
- **No session is on the template during a copy,** because none can be. Two copies of one template at once, and a copy during a reset, each only read it. [I]
- **A drop** is a plain `DROP DATABASE`, never with force. A copy that has sessions is not dropped: with `--wait`, the copy is first closed to new connections and marked `dropping`, and the drop is tried until the wait ends. [D: `copier` cannot end another account's session, and is not given the right to (4.1).]

**A reset of the working copy,** as `admin`, connected to the `postgres` database.

| Step | What happens | If it fails or is interrupted |
|---|---|---|
| a | An advisory lock for the database is tried. Transients left by an earlier reset are dropped. | exit 6 when another reset holds it |
| b | `CREATE DATABASE <database>__new_<id> OWNER admin TEMPLATE <database>_start ALLOW_CONNECTIONS false`, then its grants (4.1). | the transient is dropped; exit 7. **The working copy is untouched.** |
| c | **The door is closed:** `ALTER DATABASE <database> ALLOW_CONNECTIONS false`. No new session can arrive; those already there stay. | the transient is dropped; exit 7 |
| d | The sessions on the working copy are listed. With `--if-idle`, any session stops the reset here. Without it, they are ended. | the door is opened again and the transient dropped; exit 6, naming how many sessions and whose, or exit 7 |
| e | In one transaction: the working copy is renamed to `<database>__old_<id>`; the new one is renamed to `<database>` and opened. | it rolls back, and the door is opened again; exit 7. A lost connection is exit 8 |
| f | `DROP DATABASE <database>__old_<id>`. The lock is released. | exit 0, with the transient named under `cleanup_pending` |

- **Why a swap, and not a drop and then a copy.** DL-077's entry says "drop-and-copy". This keeps its result, and changes the order. [D]
  - **A failure before step e changes nothing.** After a drop, a failed copy would leave no working copy at all.
  - **The name `<database>` is never free.** `copier` may create databases (4.1), and PostgreSQL cannot limit which names. With a drop first, the name would be free for as long as the copy takes.
  - **People see no gap:** a client that reconnects finds a database under the name.
  - **Its cost:** one more copy of that database's storage while it runs, and it leans on a rename inside a transaction. [I]
- **The door is closed before anyone is looked for,** as `ED:` R-37 asks, so no session can arrive between the look and the swap. [D]
- **What a connected client sees:** its session is ended at step d, and its next connection reaches the pristine copy. What it had saved is gone, which is what a reset is for.
- **Permissions after it:** what is inside the database comes from the template, so it is as shipped (4.7). The database's own privileges are not copied [R: `PR14:docs/strict-read-account.md:9`], so step b gives them again from the service's record.
- **A dataset with no template** resets by today's path, from a second container of the image, on the service's machine only (F-1). [D]
- **A whole engine's reset** is unchanged: the volume is made again from the image (`SM:README.md:301-303`), so templates and working copies return, and every copy is gone.

**The sweep,** as `copier`: only databases that `copier` owns and whose name begins with the prefix.

| What it finds | What it does |
|---|---|
| a marker, older than the age, no session | plain `DROP DATABASE` |
| a marker, younger than the age | keeps it: `too-young` |
| any session connected | keeps it: `in-use`. The plain drop's own refusal is what decides, so a session that arrives late still wins. |
| marked `dropping`, no session | drops it, whatever its age |
| no marker | writes `megasamples-orphan/1` with the time it was first seen, and keeps it. A later sweep ages it from that time. |
| a database it does not own, or outside the prefix | never listed |

[D: PostgreSQL records no creation time [I], so an unmarked copy gets one from the sweep; a copy just created is therefore never old enough, which is what keeps a sweep off a copy in progress.]

### 2.3 MySQL

**The template.**
- **It is the schema `<database>_start`, set `READ ONLY = 1`.** [D] That refuses every write by every account, `root`'s included, until the option is changed. [I]
- **MySQL has no "accepts no connections" for a schema.** What stands in its place: `demo` holds no privilege there, so it neither sees nor reads it; `copier` holds `SELECT` only. `admin` and `root` can read it, and can change the option. [D: stated as a difference from DL-077's model, not hidden.]
- **What it would take to write it:** `ALTER SCHEMA … READ ONLY = 0`, which needs the `ALTER` privilege on it: `admin` or `root`. Both credentials stay on the host. [I]
- **`admin` is not shut out of it by a partial revoke.** [D: that needs the server's `partial_revokes` setting, which makes wildcards in database-level grants literal [I]; the copier's prefix grant, and the `di\_%` grant DataIntent plans for its fixture administrator (`MR:` 2.10), both need wildcards.]

**How the image makes it.** After the dumps are loaded (`SM:engines/mysql/Dockerfile:39-42`), for each templated database:
1. Its definitions are recorded in `megasamples.template_ddl`: tables, then routines, views in dependency order, triggers and events, each without its definer and with no reference to its own schema by name. The insertable columns of each table are recorded too.
2. The template is made from the loaded database by the copy below, as `root`, keeping each definer.
3. Each table's row count and `CHECKSUM TABLE … EXTENDED` are compared with the loaded database's.
4. The template is set `READ ONLY = 1`.

[D: the copy runs from recorded definitions so that `copier` needs `SELECT` on a template and nothing server-wide. Reading a routine's body otherwise needs a global privilege [I].]

**A copy,** as `copier`, all of it inside the server:
1. A row in the ledger `megasamples.copies`: the name, the database, the label, the time, `creating`. A second row of that name is refused, which is how two creates of one name exclude each other.
2. `CREATE DATABASE <copy>`, with the template's character set and collation.
3. Each table's recorded definition, with foreign-key checks off for the session.
4. `INSERT INTO <copy>.<table> (…) SELECT … FROM <database>_start.<table>`, a table at a time.
5. The routines, the views, and then the triggers and events, so that no trigger fires during the load.
6. Each table's row count compared with the template's.
7. The grants for `--read` and `--write` roles, and the ledger row set to `ready`.

- **The definer of everything in a copy is `copier`.** [D: keeping `admin` as the definer would need a privilege that lets `copier` run code as `admin` [I].] A view or routine in a copy therefore runs with `copier`'s rights, which reach that copy and no working copy.
- **The template cannot change under a copy,** so the copy needs no single snapshot. [I]
- **A failure** drops the copy and removes its row: exit 7. If that clean-up fails too, the row stays, marked `incomplete`: exit 8.
- **The sweep** goes by the ledger: rows of the prefix older than the age. A schema of the prefix with no row gets an `orphan` row with the time first seen. A drop waits five seconds for a lock and gives up, so a copy with a statement or a transaction on it is kept. **A session that is only idle there is not seen** [I]; the age is what protects it.

**Large datasets, and the stated exclusions.** [D]

| Dataset | On MySQL | Why |
|---|---|---|
| Templated, up to `copy_limit_mb` (default 512) of data and indexes, measured at build | template, copies and reset by the logical method | The largest core database is 160.6 MB (F-9), so every core dataset qualifies. |
| Templated, above the limit | template and reset; **no copies**: exit 4, `too-large` | A logical copy's time and undo grow with its rows. Raising the limit is the override, and the build then publishes the measured time. |
| `oracle_oe`, and any dataset with `depends` | **no template, no copies**; reset by today's path | Its foreign keys and views reach into `oracle_hr` (F-11). A copy would still point at the shared working copy, which people may edit. |
| Extended and generated tiers | none unless named | Hundreds of megabytes to gigabytes each (`SM:knowledge/decisions/tier-assignments.md:32-62`). |

Transportable tablespaces are not used: they need the server's files, so a container runtime on the service's machine. [D]

**Its records are tables in `megasamples`,** since MySQL has no comment on a schema [I]: `service` (the prefixes, the limits, the build id), `templates` (each template's size, whether copies are offered, and why not), `template_ddl` and the ledger `copies`. [D]

**A reset of the working copy,** as `admin`: a named lock (`GET_LOCK`), a ledger row, `DROP DATABASE`, then the copy above with each recorded definer, then the count check.
- **It is not atomic.** While it runs, the schema exists and is partly filled. An interrupted reset leaves the row `incomplete` and exits 8; running it again completes it. [D: MySQL cannot rename a schema, and cannot move a table with triggers to another schema [I].]
- **The drop waits for open transactions,** as today (`SM:README.md:307`). `--wait` bounds it: exit 6.
- **Privileges stay:** MySQL keeps them by schema name, so `demo`'s grant on `<database>` outlives the drop (`SM:README.md:308-309`).
- **A database that another refers to** (`oracle_hr`, from `oracle_oe`) is dropped and refilled with foreign-key checks off, and each referring key is then checked for orphans. [D: today's reset of it works the same way, through its dump's header [I].]

**The binary log is turned off in the shipped server.** [D: every logical copy and reset would otherwise be written to it a second time; it reached 10.9 GB in one rehearsal (F-10), and nothing replicates from this server.]

### 2.4 SQLite

- **The template is the image's file.** There is no server and no account, so "read-only" is the file's mode. [R: `PR14:docs/strict-read-account.md:13`]
- **Staging, once, on the service's machine:** `megasamples template stage sqlite --out DIR` writes each `<database>.sqlite` with mode 0444, and `templates.json`: for each file its size, its SHA-256 and the build id. Its source is `build/sqlite/` in the checkout, or the image through the container runtime (`SM:megasamples/reset.py:307-332`). [D]
- **A copy** is a file copy from a staged directory into the caller's directory: written under a temporary name, synced, held to the manifest's SHA-256, then moved into place with mode 0600. A sidecar `<copy>.copy.json` is its marker. [D]
- **A drop** removes the file, its sidecar, and any `-wal`, `-shm` or `-journal` beside it.
- **A sweep** goes by the prefix and the file's age. A file being read cannot be told from one that is not [I], so age is the only rule.
- **Nothing goes over the network.** A development container or a separate machine works from a staged directory someone copied there, manifest included, as `MR:` 2.10 already asks. [D: a file server for them would be a new listener on the LAN, which DL-075 did not grant.]
- **The service's own files** keep today's reset.

### 2.5 Which datasets get a template, and the cost

**The default is the core tier, on both server engines** (`templates: core`): the datasets of tiers `core` and `core-medium` that the engine is configured with. [D]
- It covers the five that DataIntent's suites read: `northwind`, `adventureworks`, `employees`, `pubs` and `dvdstore` (`ED:` 3.3 and question 7). Each is of tier `core` or `core-medium`. [R: `SM:datasets/*/dataset.yaml`]
- It is small beside what the maintained deployment holds (F-8, F-9).
- **It is configured per engine:** `engines: {postgres: {datasets: …, templates: core}}`, with a selector, a list, or `none`. It is baked, so a change is a rebuild. [D]

| Engine | Steady cost of the default | While a test copy lives | While a reset runs |
|---|---|---|---|
| PostgreSQL | at most 2.6 GB more, on 20.9 GiB today (F-8, F-9) [I] | that database's size again | that database's size again, until step f |
| MySQL | at most 1.8 GB more, on 22.7 GiB today [I] | the same | nothing more: it is in place |
| SQLite | none in the service | the file's size, where the caller keeps it | none |

- **Per database, little is known here.** PostgreSQL's sizes were not in what was read; MySQL's are recorded for eleven core databases, as of 2026-09-03 (F-9). The build measures each template, and each copy's and drop's time by each strategy, and publishes them (criterion 8 of `ED:` section 5). [D]
- **A limit on live copies:** 32 for a prefix, by default. The 33rd is refused: exit 5, `limit`. [D: storage is the shared resource; the count is checked before the copy, and two racing creates can pass it by one.]
- **The image and its first start grow with it.** The first start copies the data directory into a fresh volume; the budgets are twice the observed maximum (`SM:megasamples/engines/image_startup.py:9-18`), and are measured again. [D]
- **PostgreSQL 18 can clone files** where the filesystem supports it [I], which would make a template nearly free. It is measured on the service's filesystem, and not relied on. [D]

## 3. The CLI for scripts

### 3.1 The commands

The commands, their names and their options are decided here. [D: DL-077 item 3; `ED:` 4.1 sketched them.]

| Command | Account | What it does |
|---|---|---|
| `megasamples interface` | none | The interface number, the output schema, the package version and the revision. |
| `megasamples template list ENGINE` | any | For each registered database: whether it has a template, the template's flags and record, and whether copies are offered, with the reason if not. |
| `megasamples template stage sqlite --out DIR [DATABASE…]` | none | 2.4. The service's machine only. |
| `megasamples copy create ENGINE:DATABASE --prefix P --label L [--read ROLE]… [--write ROLE]…` | `copier` | 2.2, 2.3, 2.4. |
| `megasamples copy show ENGINE:NAME` | `copier` | One copy's state: `creating`, `ready`, `incomplete`, `dropping` or `absent`. |
| `megasamples copy list ENGINE [--prefix P]` | `copier` | Each copy's name, database, label, age and state. |
| `megasamples copy drop ENGINE:NAME [--wait SECONDS]` | `copier` | Dropping a copy that is already gone succeeds. |
| `megasamples copy sweep ENGINE --prefix P [--older-than AGE] [--dry-run]` | `copier` | What it removed, and what it kept and why. The age defaults to 24 hours and is at least 10 minutes. |
| `megasamples reset ENGINE:DATABASE… [--json] [--if-idle] [--wait SECONDS] [--from auto\|template\|image]` | `admin` | Today's command, which gains the template path. `auto` takes the template when there is one. |
| `megasamples accounts check [--repair]` | the service's machine | Each service account signs in with its configured password: exit 7 if one is refused. `--repair` applies the configured ones again (4.5). |

- **Common options:** `--host`, `--port`, `--user`, `--connect-timeout`, and one of `--password-file` or `--password-stdin`. For SQLite: `--templates DIR` and `--dir DIR`.
- **`ENGINE:DATABASE`** follows the reset's own pairs (`SM:megasamples/reset.py:6`). The database is the registry's name.
- **`--read ROLE` and `--write ROLE`** name who may use the copy besides its owner. [D: DataIntent reads a copy as a read account, and its admission refuses an owner (`MR:` 2.2).]
  - **On PostgreSQL** the role's group decides what it can do, so the CLI checks it: a `--read` role must be a member of `megasamples_read` and not of `megasamples_write`; a `--write` role must be a member of `megasamples_write`. Otherwise exit 5, `role-ineligible`.
  - **On MySQL** the grant is the access (4.4).
- **`reset` keeps its text output by default,** and its present behaviour of disconnecting clients (F-4). `--if-idle` is for automation that must defer to a person. Which of the two DataIntent's automation uses is its own question 6 (`ED:` section 10). [D: both mechanisms here; the policy stays where the owner was asked it.]

### 3.2 Output

- **One JSON document on standard output, on one line,** for `interface`, `template`, `copy` and `accounts`, and for `reset --json`. Everything else goes to standard error. [D: `ED:` 4.2]
- **Its envelope:** `schema`, `command`, `ok`, `exit`, `result`, `error` and `warnings`. `error` holds a stable `code`, a `message`, and `left_behind` where something is known to remain.
- **A copy's result:** its `name`, `engine`, `database`, `prefix`, `label`, `state`, `created`, its `endpoint` (the host and port the caller used, or the file's path), its `owner`, the `read` and `write` roles, the `template` with its build id and registry digest, the engine's `version`, the `strategy`, and the seconds it took.
- **`schema` is 1.** Adding a member does not change it. Removing or renaming one, or changing a meaning, does. `interface` is the number a caller compares before use (`ED:` 4.4). [D]
- **No credential is ever in it:** an account is a name.

### 3.3 Exit codes

Decided here [D], from the outcomes `ED:` 4.2 asks to be told apart.

| Code | Meaning | The state afterwards | DataIntent reports (`ED:` 4.2) |
|---|---|---|---|
| 0 | done | as asked | the case goes on |
| 1 | a defect in the CLI | **not known** | Failed; it lists before it asks again |
| 2 | wrong usage, or an invalid name | nothing was contacted | Failed: a defect in the harness |
| 3 | the engine cannot be reached, or the sign-in is refused | nothing changed | Not run |
| 4 | not offered: no template, `too-large`, or excluded | nothing changed | Not run, with the reason |
| 5 | refused by a rule: prefix, name taken, not the caller's copy, limit, role | nothing changed | Failed |
| 6 | busy: sessions connected, or another reset holds the lock | nothing changed | its question 6 |
| 7 | failed, and the CLI confirmed that nothing is left | nothing changed | Failed |
| 8 | **incomplete or not known:** the connection was lost, or a clean-up failed | read it with `copy show` or `copy list` | Failed; it lists before it asks again |

[D: 2 is what the CLI already returns for an unknown command (F-2). Codes above 125 are left to the shell. "Unsupported" is not among them: DataIntent keeps that word for its own product.]

### 3.4 Credentials

- **The password comes from a file an argument names, or from standard input.** Never from an argument, and never from an environment variable. [D: `ED:` 4.3; an environment is readable by the same user's other processes.]
  - A password file must be the caller's own and closed to others, or it is refused.
  - On the service's machine, a command run from the service's checkout with no option takes the account's password from `.env`, by the reader the reset already uses (`SM:megasamples/config.py:123-167`).
- **Nothing ambient is used.** `PGPASSWORD`, `PGPASSFILE`, a `~/.pgpass`, `MYSQL_PWD` and client option files are not read, and every connection parameter is given explicitly. [D: a run must not sign in as an account nobody named.]
- **It is in no output.** A driver's error text is passed through the redaction the pull request's helper already has (`PR14:docs/validation/strict_read_clients.py:66-71`), and a canary test holds it (T-12).
- **No SQL the remote commands send holds a password.** They never set one.
- **On the wire:** PostgreSQL's rule is SCRAM for every address (`SM:ARCHITECTURE.md:166-167`), so the password is not sent. MySQL's sign-in without verified TLS is as `MR:` 2.10 describes it. This design changes neither.

### 3.5 Where it runs

| From | PostgreSQL and MySQL | SQLite |
|---|---|---|
| The service's machine | `template`, `copy`, `reset`, `accounts` | everything |
| A development container | `template list`, `copy`, and `reset` where `admin`'s credential is | copies, from a staged directory in the checkout |
| A separate machine on the LAN | `template list` and `copy`, with `copier`'s credential (open question 1) | copies, from a staged directory copied there |

- **The remote commands need a TCP path to the engine's port, and nothing else:** no container runtime, no checkout. They speak to the server through a driver. [D: criterion 10; F-1 is why today's code cannot.]
- **Drivers:** PyMySQL, which is a dependency already, and Psycopg, which is a development dependency already, at 3.3.9 (`SM:pyproject.toml:8`, `:19`). [D: both are already locked and reviewed here.] Whether Psycopg's bundled-library wheels suit the supported Python versions is for the build's dependency step; a pure-Python driver is the fallback. [I]
- **A small install.** [D: criterion 10]
  - The new code is a subpackage that imports the standard library and the two drivers only.
  - `pyproject.toml` gains a build backend and a `megasamples` entry point. The pipeline's dependencies (`duckdb`, `lxml`, `sqlglot`, `py7zr`, `PyYAML`) move to a dependency group that `uv sync --locked` installs by default, so a maintainer's setup is unchanged.
  - A consumer installs the package at one commit and gets the two drivers. A pipeline command without its dependencies says which group to install: exit 2.
- **The interface is checked, not assumed:** `megasamples interface`, and the service's own record (4.1), which holds the build id.

### 3.6 Concurrency

Each row's behaviour is decided here [D]; that the engine gives it is [I] where marked, and T-15 shows it.

| At once | What happens | Why |
|---|---|---|
| Two `copy create` of one template | both succeed | each only reads the template [I] |
| Two `copy create` of one name | one succeeds; the other is exit 5, `exists` | the engine's unique name; the MySQL ledger's key |
| `copy create` and `copy sweep` | the new copy is kept | it is too young, or unmarked and first seen now (2.2, 2.3) |
| `copy create` and `reset` of that database | both succeed | both copy the template; a copy never touches the working copy |
| `copy drop` and `copy sweep` of one copy | one drops it; the other finds it gone, which is success | a drop of what is gone succeeds |
| `copy drop` and a session on the copy | exit 6, or it waits | no force (2.2) |
| Two `reset` of one database | one runs; the other is exit 6, `busy-lock` | a lock on the server: an advisory lock, or `GET_LOCK` |
| `reset` and `copy sweep` | independent | a sweep takes only `copier`'s copies; a reset's transients are `admin`'s |
| Any command and a whole engine's reset | exit 3 or 8 | the server goes away; the caller reads the state before it asks again |

- **The lock is on the server,** so it is seen from every machine and ends with its holder's session. The lock file stays for the image path, which is one machine's (F-3). [D: `ED:` R-36]
- **PostgreSQL's advisory locks are per database** [I], so every command takes them in the `postgres` database.
- **Copies need no lock between them:** each has a name of its own.
- **An outcome that is not known** is resolved by reading: `copy show` says `creating` while a session of the caller's account is still running the statement, and then `ready`, `incomplete` or `absent`. Nothing is retried blind.

### 3.7 Limits

Decided here [D], as starting values.

| Limit | Value | Past it |
|---|---|---|
| A whole name | 63 bytes | exit 2 |
| A prefix; a label | 16 bytes; 24 bytes | exit 2 |
| Empty, upper-case, a space, a non-ASCII character, a quote, a double underscore, the suffix `_start` | never valid | exit 2, before any connection |
| Live copies of a prefix | 32, configurable | exit 5, `limit` |
| A sweep's age | at least 10 minutes; 24 hours by default | exit 2 |
| MySQL copy size | `copy_limit_mb`, 512 by default | exit 4, `too-large` |
| Connection timeout; `--wait` | 10 seconds; 0 | exit 3; exit 6 |

No statement timeout is set by default: a copy of a large database takes as long as it takes. [D]

## 4. The account model

### 4.1 PostgreSQL's roles

The roles and what each holds are decided here [D]; what exists today is F-5.

| Role | Signs in | Attributes and memberships | What it is for |
|---|---|---|---|
| `postgres` | host only | superuser | The image build, the start wrapper, the image path of the reset. Owns the templates and the policy. |
| `admin` | host only | `CREATEDB`, `CREATEROLE`; **new:** `pg_signal_backend`, and the admin option on the two groups | Owns each working copy and everything in each sample database. Resets. Makes DataIntent's fixture roles and databases. |
| `demo` | anywhere | member of `megasamples_read` | Reads. |
| **`megasamples_read`** | no | — | `SELECT` on every table of every sample database, and on those `admin` makes later. |
| **`megasamples_write`** | no | member of `megasamples_read` | `INSERT`, `UPDATE`, `DELETE` on the same tables, and `USAGE` on their sequences. |
| **`copier`** | where tests run | `CREATEDB`; member of `megasamples_write` | Makes, uses and drops its own copies. |
| `editor` | — | member of `megasamples_write` | **Not created.** See below. |

- **The data grants go to the two groups, not to `demo`.** [D: what is inside a database is copied with it, group grants included [I]; so a copy and a reset carry them with no step of their own, which is criterion 7.]
- **A member cannot take a group up:** each membership is `WITH INHERIT TRUE, SET FALSE`, as the fixture's own are (F-16). [D: DataIntent's admission looks for roles that "can be taken up" (`MR:` IA-01).]
- **Which database an account reaches is decided by `CONNECT` on it,** which is not copied [R: `PR14:docs/strict-read-account.md:9`] and is set for each database:

  | Database | `CONNECT` |
  |---|---|
  | a working copy | its owner `admin`, and `demo` |
  | a template | nobody |
  | a test copy | its owner `copier`, and the `--read` and `--write` roles |
  | `postgres`, `megasamples` | `PUBLIC`, as today |
  | any database made later | its owner, until its owner grants more |

- **So `copier`, though it holds the write group, cannot write a working copy:** it cannot connect to one. [I]
- **The hook closes `CONNECT` as well as `TEMPORARY` on each new database.** [D: without it a database is open to every role between its creation and the next statement; the fixture already closes its own (F-16), so nothing of DataIntent's changes.]
- **`copier` holds one more thing,** in the `postgres` database only: `EXECUTE` on the function behind `pg_stat_activity`. With it `copy show` can see that a statement of its own account is still creating a copy. [D: the floor does not hold that function (a search of `PR14:engines/postgres/init/read-routine-names.sql` for `pg_stat_get_activity` finds nothing [R]), and the floor is not widened for one account's need.]
- **`copier` has no password by default.** It cannot sign in until `COPIER_PASSWORD` is set in `.env`. [D: a published default would put the right to create databases behind a password everyone knows; a script needs a credential file in any case.]
- **`copier` may create a database of any name.** PostgreSQL has no way to limit that, short of more compiled code in the hook. The CLI enforces the prefix; the engine does not. [D: stated as a limit, with a test that asserts it. The swap in 2.2 is what keeps a working copy's name from being taken.]
- **Another caller's copy.** Copies made with one `copier` credential are one owner's to the engine, and are told apart by prefix, in the CLI. `admin` can make a second account like `copier` for a consumer that must be kept apart; each then owns its own. [D]
- **`editor`: the group is shipped, the account is not.** [D: DataIntent's record forbids a read/write account on a live service until its controls have passed (`ED:` R-39), and the product does not write (`MR:` A-31). The group is enough for criterion 7's evidence, and for a fixture role that `admin` makes a member.]
- **The service's record** is the `megasamples` database's comment: `megasamples-service/1`, with the prefixes, the copy limit, the build id and which roles connect to a working copy. [D]

### 4.2 The strict read profile

**What pull request #14 does** is F-12. **What changes:**

| # | Change | Reason | Mark |
|---|---|---|---|
| P-1 | **The allow-list is granted to `PUBLIC`,** not to `demo`. | Finding 1 (4.3). Every role that is not an administrator then has the same floor, with no step per role, in every database and every copy. It is DL-085 item 7's own description: "the change reaches every non-admin role". | [D] |
| P-2 | **`demo` holds nothing itself** but its membership and `CONNECT`. | 4.1. | [D] |
| P-3 | **Three built-ins join the list by name, each with its reason:** `pg_export_snapshot()`, `pg_database_size(oid)` and `pg_current_snapshot()`. | F-17, F-18. The first two are volatile [I]. None of the three changes a stored object, a setting, a sequence or another session, and none assigns a transaction id [I]. | [D] |
| P-4 | **The rule for the list is stated as that,** not as "nonvolatile": a routine is admitted when it changes nothing outside the calling statement's own reading. Volatility stays the default test, and an exception is named, with its reason, in the list. | So that P-3 is a rule and not a hole. | [D] |
| P-5 | **A write list beside it,** granted to `megasamples_write`: the built-ins that inserting, updating and deleting rows through the datasets' own defaults and triggers need. It is found by running each dataset's trigger scenarios as a member and reading each refusal. | A writer's statement runs a trigger's body with the writer's rights [I]. | [D] |
| P-6 | **The published inventory is the one authority:** every executable signature, with its reason, generated from the candidate. | DL-085 item 4 asks for one. DataIntent's admission can take it as data; that is its own design. | [D] |

**What stays:** no `TEMPORARY` for `PUBLIC`; no large-object creation; no user routine for a reader; the two rewritten `employees` views; the closed defaults for `admin` and `postgres`; MySQL not claimed strict (F-14).

**DL-085's item on the list is settled by a run, not by this text:** DataIntent's C1 selection against the candidate names any other routine the provider needs. Each is admitted under P-4, or the provider changes. [D]

### 4.3 The hook and the event trigger: a design check

This is input to the independent review DL-085 requires. Each row is from reading `PR14:` at the cited lines; none was run.

| # | Finding | Where | Disposition |
|---|---|---|---|
| H-1 | **Every role but `demo` and `admin` is left with no built-in routine.** The revoke covers every schema, `pg_catalog` included; the operators' and casts' functions come back for `demo` alone. A role such as `di_reader` could then not evaluate `1 = 1`. `admin` cannot repair it: its own grant has no grant option (F-13). [I] The file's own comment says why the functions matter: "Operators/casts are needed by ordinary expressions". DL-085 item 3 names the reach. | `PR14:engines/postgres/init/10-read-profile.sql:14-15`, `:23-35`, `:29-30` | **Fix: P-1.** Its red: a fresh role's executable set is empty, where the profile expects the list. |
| H-2 | **The hook's `REVOKE` can do nothing, and succeed.** It runs as the creator. A creator who is not the new owner and does not inherit the owner's rights has no grant option; PostgreSQL then warns and revokes nothing [I]. That is reachable: `CREATE DATABASE x OWNER r` by a role that may only `SET ROLE r`. | `PR14:engines/postgres/read-policy/read_policy.c:31-38`; `PR14:docs/strict-read-account.md:9` | **Fix: verify, then fail.** After the statement the hook reads the new database's privileges and raises an error if `PUBLIC` still holds either. |
| H-3 | **An error in the hook leaves the copied files with no database.** `CREATE DATABASE` has copied them by then; the abort removes the catalog row. [I] With templates of hundreds of megabytes that is a leak worth a test. | `PR14:engines/postgres/read-policy/read_policy.c:24-38` | **Test it,** and report what remains. If files remain, the hook's failures are made as few as H-2 and H-4 allow, and the README says how they are found. |
| H-4 | **The role name `admin` is compiled in.** If the role is missing or renamed, every `CREATE DATABASE` on the server fails. `admin` owns what it must use, and the image build grants the rest. | `PR14:engines/postgres/read-policy/read_policy.c:32-33` | **Fix: the hook names no role.** It closes `PUBLIC`, and nothing more. |
| H-5 | **The hook closes `TEMPORARY` only.** | the same | **Extend:** `CONNECT` too (4.1). |
| H-6 | **A role can change its own password and its own settings,** which the hook does not touch. `ALTER ROLE demo SET statement_timeout = 1` would break every later `demo` session, the health probe's among them. [I] | — | **Extend:** 4.5. |
| H-7 | **A reader can still write a catalog row:** `ALTER DEFAULT PRIVILEGES` for itself, in any database it reaches. [I] | — | **Extend:** refused with H-6's rule. |
| H-8 | **`NOTIFY` is a statement, not a routine,** so revoking `pg_notify` does not stop it [I]. The page says notifications "receive no `demo` grant". | `PR14:docs/strict-read-account.md:3` | **Correct the page.** `NOTIFY` stays allowed: it stores nothing, and nothing in the service listens. [D] |
| H-9 | **The event trigger also names `admin`,** and would fail every routine's creation if the role were missing. | `PR14:engines/postgres/read-policy/read_policy--1.sql:9-11` | **Fix:** it checks that the role exists. |
| H-10 | **The event trigger is enabled in the ordinary way,** so a session in replica mode would skip it [I]. Only a superuser can enter that mode [I]. | `PR14:engines/postgres/read-policy/read_policy--1.sql:19-20` | **Set `ENABLE ALWAYS`.** |
| H-11 | **Which commands can make a routine, and who covers each.** The closed defaults cover whatever `admin` and `postgres` create, by any command. The trigger covers a later role's `CREATE FUNCTION`, `PROCEDURE` and `AGGREGATE`. Routines an extension's script or a type's definition makes are covered by the defaults only [I]. | `PR14:engines/postgres/init/10-read-profile.sql:18-20`; `PR14:docs/strict-read-evidence.md:22` | **Test the table:** every such command, by each kind of creator (T-7). |
| H-12 | **The library is named in the data directory's configuration.** An image without the library cannot then start on policy data, which is the safe way to fail. But a policy image started on data from before the policy would run with the hook and without the grants. | `PR14:engines/postgres/Dockerfile:83` | **Keep the line, and add a marker:** the build writes the policy's version into the data directory, and the start wrapper refuses a data directory whose marker is missing or older. [D] |
| H-13 | **The headers' package is taken from the network at build,** at the base image's own version. A later rebuild at the same pin needs that version to be served still. | `PR14:engines/postgres/Dockerfile:13` | **Record it** with the image's other inputs (`SM:engines/images.lock.yaml`), under the repository's pinning procedure. |
| H-14 | **What a role with no grant can still do,** for the reviewer to confirm as a class: anonymous `DO` blocks; `SET`; `LISTEN`; a held cursor; `LOCK TABLE` in a share mode on what it may read. None stores anything. [I] | — | **Document** as the profile's limit. |

**What the hook does after this design** [D]:
1. **After `CREATE DATABASE`:** revoke `CONNECT` and `TEMPORARY` on the new database from `PUBLIC`; then confirm it; fail the creation otherwise.
2. **Before `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES`:** refuse, when the caller is neither a superuser nor a holder of `CREATEROLE`.

It names no role, reads no configuration, and holds no state.

### 4.4 MySQL's accounts

Decided here [D]; what exists today is F-5.

| Account | Privileges | Change |
|---|---|---|
| `root@localhost`, `root@'%'` | everything | none |
| `admin@'%'` | everything, with the grant option | none (4.6) |
| `demo@'%'` | `SELECT, SHOW VIEW` on each sample schema by name, and `SELECT` on `megasamples`' registry tables | **narrowed** from `*.*` |
| **`copier@'%'`** | on `<prefix>\_%`, for each configured prefix: what making, filling, using and dropping a copy needs, with the grant option. On each template: `SELECT`. On `megasamples`: `SELECT`, and row changes on the ledger. | **new**; locked until `COPIER_PASSWORD` is set |

- **`demo` no longer reaches the `mysql` schema,** where account rows are (LR: line 10). It no longer sees a template, a copy it was not given, or a fixture's `di_…` database. [I]
- **That reverses what DL-079 item 3 allowed:** that `demo` and the consoles may see DataIntent's synthetic fixtures. It was a permission, not a requirement, and the lines register put the narrowing here. DataIntent's case that asserts the sight changes with it (section 11). [D]
- **A grant by name outlives a reset** (2.3). A schema `admin` makes later is not `demo`'s to read until `admin` grants it. [D: said in the README; it is the price of not reading `mysql`.]
- **On MySQL the prefix is enforced by the engine:** `copier` holds nothing outside its patterns, so it cannot create a schema elsewhere. [I]
- **`--read ROLE`** grants `SELECT, SHOW VIEW` on the copy; **`--write ROLE`** adds `INSERT, UPDATE, DELETE`. Here the grant is the access. `copier` cannot read what another account already holds, so the CLI cannot vouch that a `--read` role holds no more. [D: stated; reading other accounts' grants would need the `mysql` schema.]
- **One prefix, two owners.** MySQL has no owner of a schema. A copy and a fixture database under one prefix would be each other's to drop. A consumer therefore takes a copy prefix that its fixture never uses; `di_copy` is within F-05's `di_…`. [D: the choice is DataIntent's; the default here is `copy`.]
- **MySQL stays not claimed strict** (DL-085 item 5): named locks, and the two definer views of `employees`, are as F-14 found them.

### 4.5 An account changing its own password

| Engine | Decided | Mark |
|---|---|---|
| **PostgreSQL** | **Refused,** by the hook's second rule (4.3), for every role without `CREATEROLE`: `demo`, `copier`, a fixture role. The rule also covers a role's own settings, which would do the same harm. `admin` cannot change `demo`'s either: it holds no admin option on a role the superuser made [I]. | [D] |
| **MySQL** | **Not prevented.** Any account may change its own password with no privilege [I], and nothing in the community server refuses it [I]. **It is detected and repaired.** | [D], and open question 2 |

**On MySQL:**
- **Detected:** the health probe signs in as `demo` (F-6), so the engine shows unhealthy. `megasamples accounts check` reports each service account whose configured password is refused, and exits 7.
- **Repaired:** `megasamples accounts check --repair`, on the service's machine, applies the configured passwords again as `root`, by the private client files the reset uses (F-1). So does any restart (F-6).
- **The harm it leaves:** until someone repairs it, other holders of that password cannot sign in. No data is exposed and none is changed.
- **A test asserts today's truth:** `demo` changes its password, the check reports it, the repair restores it. If a later engine can refuse the change, that test fails and says so. [D]
- **Not chosen:** a timed job in the server that restores the password. It would be a privileged job that silently undoes an administrator's own change. [D]

### 4.6 What `admin` can do

The table follows from 2.2, 2.3, 4.1 and 4.4 [I]; what changes is decided below it.

| | PostgreSQL | MySQL |
|---|---|---|
| Sample data | owns it: reads, writes, alters, drops | all privileges |
| A working copy | owns it; resets it | drops and refills it |
| A template | **copies it; cannot connect to it, alter it or drop it** | reads it; **can change its read-only option** |
| A test copy | cannot connect to it or drop it | can do anything |
| Accounts | makes roles; changes those it made; **cannot change `demo`, `copier` or `postgres`** [I] | makes and changes any account, `root`'s included [I] |
| Sessions | **new:** ends any that is not a superuser's | ends any |
| The server | not a superuser | in effect the administrator |

- **PostgreSQL's `admin` gains one thing:** `pg_signal_backend`, because a reset must end `demo`'s sessions and `admin` is not `demo`'s member (2.2, step d). [D]
- **MySQL's `admin` is not narrowed.** [D: narrowing it needs partial revokes, which 2.3 rules out. It was the engine's administrator in all but name before this design (`MR:` B-03).] It is why DataIntent keeps its own `di_admin` there (`MR:` R-20).
- **Neither `admin`'s credential leaves the host** (`ED:` R-33). So a reset is asked for where that credential is.

### 4.7 DataIntent's fixture roles, and `di_…` databases

**What a database inherits from the one it is copied from** [I]:

| Copied with it | Not copied: set anew for each database |
|---|---|
| tables, rows, indexes, views, routines, triggers, sequences | its owner |
| each object's owner, which stays `admin` | `CONNECT`, `TEMPORARY` and `CREATE` on the database |
| each object's privileges: the two groups' grants; the routine floor | settings made for the database |
| default privileges | its comment |
| the policy's extension and event trigger | whether it is a template and whether it accepts connections |

**So for DataIntent:**

| Thing | Where it comes from | What it has | What it lacks |
|---|---|---|---|
| `di_reader`, `di_analyst`, `di_login_…`, in a fixture database | `admin` makes the role; the database is copied from `di_template`, `template1` or `template0` (F-16) | the routine floor, through `PUBLIC` (P-1); whatever the fixture grants | `TEMPORARY`, unless `admin` grants it on that database; `EXECUTE` on a routine the fixture creates, unless the fixture grants it |
| The same role, in a test copy of a sample | `copy create --read di_reader`, after `admin` made it a member of `megasamples_read` | `CONNECT`, the tables' `SELECT`, the floor | any write; `TEMPORARY` |
| The same role, in a working copy | — | nothing: it cannot connect | — |
| A `di_…` test copy | `copier` owns it; its tables stay `admin`'s | everything the template had, as the table above says | `CONNECT` for anyone not named |

- **Pull request #14's revocations reach every one of these,** because both templates carry them, and every later database is a copy of one. With P-1 the fixture roles keep the built-ins a reader needs. Without it they keep none (H-1).
- **Two things the fixture must then do itself,** which it did not need before: grant `EXECUTE` on its own routines to the roles that call them, and grant `TEMPORARY` where a case needs it. Both are `admin`'s to grant, as the owner. Which cases need them is what the C1 run shows (section 11).
- **Permissions are kept through template creation, a copy and a reset** by construction: the left column is carried, and the right column is set by the build, the hook and the commands. T-5 holds each to a fingerprint.

### 4.8 How each account reaches each kind of database

Each cell follows from the sections above [I], and is the expected value of a test.

**PostgreSQL.**

| Account | A working copy | A template | Its own test copy | Another's test copy | A fixture `di_…` database | `megasamples` |
|---|---|---|---|---|---|---|
| `demo` | reads | refused | reads, if named `--read` | refused | refused | reads |
| `copier` | refused: no `CONNECT` | copies it; refused a connection | owner; reads and writes rows | the same account, so the same; a second copier account is refused | refused | reads |
| a `--write` role | refused | refused | reads and writes rows | refused | — | reads |
| `admin` | owner | copies it; refused a connection | refused | refused | owner | reads and writes |
| `di_reader` | refused | refused | reads, if named and a member | refused | as the fixture grants | reads |
| `postgres` | everything | refused a connection; can open it | everything | everything | everything | everything |

**MySQL.**

| Account | A working copy | A template | A test copy | A fixture `di_…` schema | `mysql` |
|---|---|---|---|---|---|
| `demo` | reads | not visible | reads, if named `--read` | not visible | **refused** |
| `copier` | not visible | reads | everything, within its prefix | everything, if under its prefix (4.4) | refused |
| `admin`, `root` | everything | reads; writes are refused until the option is changed | everything | everything | everything |

Every cell is a case of T-4.

## 5. The second live rollout

**It carries, from one build of `main`:** the templates and working copies, the account model, the strict read profile, the CLI, and the build revision in each registry row and image label, which DL-079 item 5 put no later than this rollout. No third rollout is planned (DL-085 item 2).

### 5.1 What changes on the live service

Each row follows from sections 2 to 4, or is decided where it says [D].

| | Change |
|---|---|
| **Images** | All three engines' images are replaced. PostgreSQL's gains the hook's library and the policy extension. Consoles are rebuilt only if their inputs changed. |
| **Initialisation** | The start wrappers apply `COPIER_PASSWORD`, leave `copier` locked without it, and PostgreSQL's refuses a data directory without the policy marker (H-12). |
| **Accounts** | New: `copier`, and the two PostgreSQL groups. Changed: `demo` on MySQL, narrowed; on PostgreSQL every role that is not an administrator is held to the floor, and loses `CONNECT` on working copies unless named. `admin` gains `pg_signal_backend`. |
| **Passwords** | The four existing values are **not** rotated. `.env` gains one key. [D: nothing about them changed; DataIntent's credential files stay valid.] |
| **Data** | Both data volumes are renewed from the images (`MR:` B-10). Everything made there since is gone: DataIntent's roles, `di_template`, its fixture databases, any edit. |
| **SQLite** | Each dataset file must be the same bytes as today, unless its dataset changed: held by SHA-256 against a read-only capture taken before. Only the registry file changes. [D: DataIntent pins one of them (`MR:` A-13).] |
| **Configuration** | `megasamples.yaml` gains `templates` and `copies`. MySQL's binary log is off (2.3). |
| **Storage** | The steady cost of 2.5, and the rollback's inputs: cold copies of today's volumes, and both image sets. |
| **Unchanged** | Engine versions, ports, the LAN forwards (DL-075), the consoles' addresses. |

### 5.2 The order

The order is decided here [D]. It is the corrected runbook's, with this rollout's content.

| # | Step | By the runbook's | It must show |
|---|---|---|---|
| 0 | **DL-087's acceptance is recorded.** | — | Gate 6's declared run met C1. Nothing below starts before it, except the design and the build in isolation. |
| 1 | The pull request is reviewed and merged into `main` (section 7). | — | DL-086's two blessings on one head; the independent review of 4.3; a merge commit. |
| 2 | **The candidate is built from `main` at that merge commit,** in the isolated store. | "Isolation used for rehearsal" (`SM:docs/live-upgrade-runbook.md:2370`) | The full dataset matrix, the image tests and every native suite of section 6 Passed on it. Its image IDs recorded. |
| 3 | **DataIntent's C1 selection against the isolated candidate,** at one declared DataIntent revision (5.3). | — | Complete, every case Passed. |
| 4 | The owner's exact approval (5.5). | — | Recorded before any live step. |
| 5 | Preparation while the live servers run: the backup directory, the retained images and configuration, the archive gates, the rollback set rehearsed in a fresh store, the candidate's images imported. | "Prepare while the live servers are still running" (`:268`); importing leaves the running containers as they are (`:630`) | Every gate Passed. An abort here changes nothing (`:936`). |
| 6 | A quiet point: DataIntent's writers stopped, its standing permission to start the services suspended (`:181`), restart automation paused (`:1094`). | "Final backups and cutover" (`:1045`) | The coordinator's hold recorded. |
| 7 | The capture, then the stop: consoles, then SQLite, then PostgreSQL and MySQL (`:1082`). | DL-088's gate | A missing capture holds before downtime. |
| 8 | **The four checks** (`:1277`): the state table, no project container running, and the recorded identities and data verified. | the quiescence gate | PASS. A refusal or a hold blocks the copy, and has its own route. |
| 9 | Cold copies of each data mount, with their digests. The old volumes are kept (`:1166`). | — | Each digest recorded. |
| 10 | `.env` gains `COPIER_PASSWORD`, generated without printing. `megasamples.yaml` gains its two keys. | as the first cutover set its four (`:1170`) | No value in an argument, a log or a receipt. |
| 11 | The stack is started on the imported images with fresh volumes. **Nothing is rebuilt here** (`:1192`). | — | The running image IDs are the compared candidate's (`:1202`). |
| 12 | Verification before clients resume (5.3). | "Verify before resuming clients" (`:1461`) | Each check Passed. |
| 13 | Restart automation restored (`:1238`); the hold released; DataIntent's credential files refreshed, and its fixture set up again. | — | — |
| 14 | **DataIntent's accepting run on the live service** (5.3). | — | The rollout is accepted only then. The rollback's inputs are kept until it is. |

- **The runbook is revised in this work's pull request** for a rollout that replaces images without rotating passwords: it is written today for DL-074's versions and its rotation (`SM:docs/live-upgrade-runbook.md:46-56`). The gates are reused as they are. The revision is rehearsed on the isolated store, forward and back (T-22). [D: DL-086 item 1.]
- **Its order with the README:** the pull request keeps the README true (DL-086 item 1). DL-078's rewrite follows the rollout, so that it describes what is finished.

### 5.3 Verification, and DataIntent's acceptance

**Before clients resume,** on the live service, read-only except where said [D]:
- each engine's version, and each registry row with its build id;
- **every account:** its configured password signs in, and a wrong one is refused as an authentication failure;
- **every template:** on PostgreSQL its three properties (2.2); on MySQL its read-only option; and a connection or a write refused for each account;
- **the policy is in force:** the library is loaded, the extension is in every database, and `PUBLIC` holds neither `CONNECT` nor `TEMPORARY` on a working copy;
- **one round trip on each server engine,** as `copier`: a copy of `pubs`, a read of it, its drop. It writes one database of the configured prefix and removes it;
- **one reset of `pubs` by the template path, with `--if-idle`.** It replaces a pristine database with a pristine one;
- SQLite's files against the capture (5.1).

**DataIntent's acceptance,** in DL-087's form [D]:
- **Declared before it starts:** one DataIntent revision, which holds whatever section 11 needed; the C1 selection (`MR:` section 3); the binding; the image IDs.
- **Against the isolated candidate first** (step 3), then against the live service (step 14).
- **It passes only if complete:** every case Passed, none Not run, against that revision's inventory. A triaged failure is not a pass. It is one run.
- **Each failure before step 4 is triaged to the service or to DataIntent** (DL-085 item 3), and fixed where it belongs.
- **With it:** the native admission of `demo` as a read account, which DL-085 item 4 left Not run until this profile exists.

### 5.4 The rollback

The routes are the runbook's [R at each line]; choosing among them is as it says.

| When | Route | What is lost |
|---|---|---|
| Before the stop | Abort the preparation (`:936`). | nothing |
| The stop was refused, or the gate did not pass | Restart the original containers on their unchanged volumes (`:809`). | nothing |
| After the candidate started | Stop the candidates behind the same capture and gate; then restart the exact originals on the volumes that were kept (`:2215`), or restore the cold copies (`:1776`). | what was written to the candidate. Its volumes are kept. |

- **A rollback is of the whole engine.** The profile is in the image and in the data together; there is no rolling back the permissions alone. [D]
- **An old image cannot start on the new data,** and the new image refuses the old data (H-12). Both are refusals, not silent mixes. [I]
- **After a rollback** `.env` is the kept original, DataIntent's fixture is set up again, and `copier`'s credential file is removed.
- **The rollback has never restored the live service** (DL-087 item 8). Its rehearsal for this rollout is T-22, in the isolated store.

### 5.5 What needs the owner's exact approval, at the time

Decided here [D], from DataIntent's root policy on shared services and DL-085 item 7.

1. **Stopping the shared services, replacing their images and renewing their data volumes.** It removes everything DataIntent made there.
2. **The permission change,** with the pull request's final content (DL-085 item 7): it reaches every role that is not an administrator, on PostgreSQL; and `demo` on MySQL.
3. **The new account `copier`,** and where its credential may go (open question 1).
4. **A compiled hook in the PostgreSQL server,** and what it refuses (4.3).
5. **The storage** of 5.1.
6. **MySQL without a binary log.**

## 6. The test plan

**Test-first, on the isolated stack.** The plan is decided here [D]. Each behaviour below has a test that fails first for the stated reason, and a reversal: its fix reverted, or a plausible bug planted, with the test shown to catch it. The failing command and its result go into the commit message.

- **Two levels.** Unit cases run in `make check`, with no container. Native cases are opt-in, and refuse any store but the isolated one, as `PR14:tests/test_strict_read_native.py:20-30` does.
- **A native case that cannot run is Unsupported or Not run, never Passed.**
- **The base for each red** is `main` with pull request #14 merged in (section 7), unless the row says otherwise.

| # | Behaviour | Its red | Its reversal | The class it covers |
|---|---|---|---|---|
| T-1 | **A PostgreSQL template refuses every connection, and can be copied** (criterion 1). | No `_start` database exists. | Built with connections allowed: a connection succeeds. | Every templated dataset; every account, the superuser's over the network and on the loopback. |
| T-2 | **Nothing writes or changes a template** (criterion 3). | The same. | The template owned by `admin`: its `ALTER DATABASE` succeeds. | Every account, against rename, owner, the two flags, drop, comment and grant. On MySQL: every account against a row change, a definition change and the option. |
| T-3 | **A copy needs no session on its template;** two at once; one during a reset (criterion 2). | No command. | A lock planted around the copy: the two no longer overlap. | Each strategy; each pair of commands that read one template. |
| T-4 | **The reach table of 4.8,** cell by cell (criterion 4). | The accounts and groups do not exist. | `CONNECT` on a working copy left with `PUBLIC`: `copier` writes a sample. One planted per column. | Every account against every kind of database, for connect, read, row write, definition change, drop, rename and grant, on both engines. |
| T-5 | **Permissions are kept through template creation, a copy and a reset** (criterion 7). A fingerprint of each object's owner and privileges, the default privileges, the event trigger and the extension is equal across the image's working copy, a test copy and a reset one; the database's own privileges are the expected set. | No template path. | The reset's grants left out: `demo` cannot connect. | Every templated dataset, on both engines. |
| T-6 | **The routine floor is the list, for every role** (H-1, P-1 to P-5). | **On the base, a fresh role's set is empty,** and `SELECT 1 = 1` is refused. | The list granted to `demo` alone. | `demo`, a fresh role, a fixture-like role, `copier`, a write member; in every kind of database, a later one and a copy included. The pull request's own cases, kept. |
| T-7 | **The hook closes each new database, or fails** (H-2 to H-5), **and the trigger closes each new routine** (H-9 to H-11). | A creator with only `SET ROLE` to the owner leaves `PUBLIC` holding `TEMPORARY`. `CONNECT` is open on every new database. | The library not loaded. The confirmation removed. | Creator (superuser, `admin`, `copier`, the `SET`-only role) by template (`template0`, `template1`, a `_start`, a fixture-like template) by strategy. Every command that makes a routine, by each kind of creator. A second session that polls the catalog never sees the new database open. A forced failure: no database, and what files remain is reported. |
| T-8 | **A password an account can change** (4.5). | PostgreSQL accepts `demo`'s change. | The refusal removed. | Each account without `CREATEROLE`, against a password change by each statement form, its own settings, and its own default privileges. On MySQL: the change is accepted, the probe and the check report it, the repair and a restart each restore it. |
| T-9 | **MySQL's `demo` is narrowed** (4.4). | `demo` reads `mysql.user`. | The grant on `*.*` restored. | Every sample schema read, its views included, those that cross databases too; `mysql`, each template, an unnamed copy and a fixture-like schema not visible. |
| T-10 | **A MySQL copy is the dataset** (criterion 9). | No command. | The foreign keys' replay skipped; one view skipped. Each fails the dataset's own verification. | Every templated dataset: its counts, digests, foreign keys, indexes, views, routines and triggers, by the repository's own expectations (`SM:ARCHITECTURE.md:239-249`), run against a copy. The object inventory against the template's. |
| T-11 | **The stated exclusions** (2.3). | No command. | The limit ignored. | A dataset above the limit: exit 4. `oracle_oe`: no template, no copy, and today's reset. |
| T-12 | **The CLI's contract** (criterion 10). | No command. | A password echoed in an error; a second line on standard output; a changed exit code. | Every command by every outcome of 3.3: the document against its schema, and the code. A canary password in no argument, environment, output or log. The remote commands with no container runtime on the path, and in an install with the two drivers only. |
| T-13 | **The sweep** (criterion 11). | No command. | The age check removed; the session check removed; the prefix check removed. | Every row of 2.2's table, on each engine; a copy made during a sweep; a database outside the prefix; one another account owns. |
| T-14 | **A reset under connected clients** (criterion 5). | The template path does not exist. | The door left open (step c skipped): a client that reconnects in a loop makes the swap fail. Step d skipped under `--if-idle`: a connected writer is ended without a word. | A reader and a writer connected; a session that arrives during the copy; `--if-idle`; the time each takes. The CLI killed after each step of 2.2 and 2.3: the next run completes, and the working copy is whole at every point on PostgreSQL. |
| T-15 | **Every command against every command** (3.6). | No commands. | Each row's guard removed in turn. | The full matrix of `create`, `show`, `list`, `drop`, `sweep`, `reset` and a whole engine's reset: by gated fakes at each step in unit cases, and natively for each row of 3.6. Its invariants: no working copy lost, no copy dropped in use, no name with two owners, nothing left that `list` does not show. |
| T-16 | **Names** (2.1, 3.7). | No validation. | The check moved after the connection. | A table: empty; a space; upper case; a non-ASCII letter, an emoji, a right-to-left mark; a quote, a semicolon, a backtick; 63 and 64 bytes; `_start`; a double underscore; a prefix that is not configured. Each is exit 2 with no connection made. |
| T-17 | **Limits** (3.7). | None. | The count check removed. | The 32nd and 33rd copy; the age floor; the longest database name with the longest prefix and label. |
| T-18 | **Sizes and times** (criterion 8). | — | — | For each templated dataset: the template's size, and a copy's and a drop's time by each PostgreSQL strategy and by MySQL's method. The first-start budgets again. Measured and published, not a pass or a fail. |
| T-19 | **SQLite** (2.4). | No command. | The hash check removed: a damaged copy passes. | Every staged file; a copy, a drop, a sweep; a truncated template; a manifest that disagrees. |
| T-20 | **The image** as shipped. | The image test knows no template. | — | Each configured template present and each unconfigured one absent; the service's record; `copier` locked without its password, and no account passwordless (`SM:ARCHITECTURE.md:250`). |
| T-21 | **Round trips.** | — | The marker lost on restart. | Copies and their markers across a stop and a start. After a whole engine's reset: no copy, each template pristine, each account as shipped. Create, drop, and create again under one name. A list by prefix whose parts sum to the whole list. |
| T-22 | **The rollout, rehearsed** (5.2, 5.4). | The runbook has no such route. | — | On the isolated store: from `main`'s stack to the candidate by the revised runbook, the verification of 5.3, and back by each rollback route. |
| T-23 | **MySQL's reset with configured credentials** (criterion 12), and the build revision in each registry row. | The registry says `dev` (F-7). | — | Carried from the first rollout's evidence, and run again on the candidate. |

**Then DataIntent's own:** the C1 selection against the candidate (5.3). It is the proof for the fixture roles and for the list of P-3.

## 7. Pull request #14's disposition

**It is folded into this work's pull request. It is not rebased, and it is not merged by itself.** [D]

- **Why not by itself.** Merged alone, `main` would build a server on which every role but `demo` and `admin` can run no query (H-1). The owner asked, on 2026-11-20, that what follows uses "the latest … from a build of main" (this task's brief); a `main` between the two merges would be a broken one. DL-085 item 3 already holds it until the account model exists.
- **Why folded.** Its grants, its hook and its tests are the ground the templates stand on: the profile is applied before a template is frozen, the hook closes each copy, and the reach table needs both. They are one account model, reviewed once.
- **How.** The work's branch starts from `main` and merges `fix/strict-read-account` at `2879fc4` as its first commit. It merges without conflict (F-15). Its history is kept; nothing is rewritten. Pull request #14 is then closed, pointing at the new one.
- **Its tests are not loosened.** Where this design changes an expectation, that is a test-only change of its own, saying why: the grant to `PUBLIC` in place of `demo`; the three named built-ins; `demo`'s MySQL grants.
- **Its evidence is made again.** Its receipts describe a candidate that grants 1,663 signatures to `demo`. The final candidate does not. The pull request publishes the final candidate's inventory and receipts, and removes the earlier ones from the tree; they remain in history at `2879fc4`. [D: DL-086 item 1.]
- **Its conditions under DL-085 item 3,** and where each is met: C1 against the candidate (5.3); the other roles (4.2, 4.7); the list reconciled (P-3, P-6); the independent review (4.3 is its input); the account model (section 4); permissions kept (T-5).
- **Carried into the same pull request:** the ten notes that pull request #16's review left for "the next sql-megasamples PR", C-1 to C-10 (`DI:docs/work/megasamples-pr16-review-loop.md:17-27` at `d02f7384`). [R]

## 8. What the README must then document

For DL-078's writer. Each is a fact this design fixes [D]; the review checks each against the repository.

1. **The model, with a picture:** a template, a working copy, a test copy and a reset, for one dataset. One diagram, and a table of how the three engines differ.
2. **Which datasets have a template,** per engine, with each one's measured size and copy time, and how to configure it.
3. **The commands,** each with one example and its JSON: `template list`, `copy create`, `show`, `list`, `drop`, `sweep`, `reset --json`, `accounts check`, `interface`.
4. **The exit codes** of 3.3, as a table, and what a script does on 8.
5. **Credentials for scripts:** the two ways in, that nothing ambient is read, and that `copier` is locked until `COPIER_PASSWORD` is set in `.env`.
6. **Using it from a development container or another machine:** the install, the one port each engine needs, and the staged directory for SQLite.
7. **The accounts,** as a matrix by engine: what `demo`, `copier` and `admin` can do to a working copy, a template and a test copy. It replaces today's two-row tables (`SM:README.md:120-123`, `:247-255`).
8. **The read profile on PostgreSQL:** what a reader cannot do, where the list is, and its limit (H-14). It replaces the sentence that `demo` "still has `TEMPORARY`" (`SM:README.md:163-167`; `SM:.env.example:14-17`).
9. **What changed for someone who used the service before:**
   - a new database is closed until its owner grants `CONNECT`;
   - a new routine is closed until its owner grants `EXECUTE`;
   - MySQL's `demo` reads the sample schemas only;
   - an account cannot change its own password on PostgreSQL.
10. **What is not claimed:** MySQL is not a strict read profile; a MySQL reset is not atomic; MySQL cannot stop a password change; a template on MySQL can be read by administrators; SQLite has no accounts.
11. **Resets:** the template path and the image path, what each does to a connected client, and `--if-idle`. It revises "Putting the data back" (`SM:README.md:281-325`).
12. **The rollout runbook's** new route.

## 9. Open questions for the owner

Only what is hard to change later. Everything else is decided above.

1. **May `copier`'s credential be given to a separate machine on the LAN?** *Recommended: yes.* DL-077 asks that the CLI work from one "with the right credentials". With it a machine can make, use and drop copies. It cannot write a working copy, a template, the registry or an account. On PostgreSQL it can create a database of any name, and so fill the disk; on MySQL only within its prefix. Without it, copies are asked for only on the service's machine. It is asked because a credential, once sent, is sent.
2. **MySQL cannot stop an account changing its own password** [I]. *Recommended: accept detection and repair (4.5).* The brief asked that neither engine's `demo` be able to; PostgreSQL's cannot. On MySQL the harm is that other holders of that password are locked out until `accounts check --repair` or a restart; nothing is read or changed. The alternatives are a different sign-in method for `demo`, which every client would have to follow, or giving up a shared `demo` on MySQL.

**Told, not asked:**
- The permission change of 5.5 item 2 is approved at the rollout, with the final content, as DL-085 item 7 says.
- `demo` on MySQL stops seeing DataIntent's fixture databases, which DL-079 item 3 had allowed (4.4).
- A reset's default still disconnects clients. Whether DataIntent's automation defers is its own question 6.
- The names `copier`, `megasamples_read`, `megasamples_write` and `_start`, the JSON schema and the exit codes become what scripts rely on. They are free to change until the repository publishes; it has not (`SM:README.md:40`).

## 10. Inferences the build must show

None was observed. Each is marked [I] where it is used.

**PostgreSQL:**
- a template that accepts no connections can be copied, by any account that may create databases, with two copies at once (T-1, T-3);
- only its owner or a superuser can change it (T-2);
- a database's comment is readable from any database by any role (T-13);
- what is inside a database is copied with it, and its own privileges are not (T-5);
- two renames and a change of `ALLOW_CONNECTIONS` commit as one transaction (T-14);
- `admin` with `pg_signal_backend` can end `demo`'s sessions, and cannot change `demo`'s password (T-14, T-8);
- a `REVOKE` by a role without the grant option warns and revokes nothing (T-7);
- a failed `CREATE DATABASE` after the copy leaves files (T-7);
- a role without `CREATEROLE` can alter only itself, so refusing it those statements takes nothing else away (T-8);
- `pg_export_snapshot` and `pg_database_size` are volatile and change nothing stored (T-6);
- advisory locks are per database (T-15);
- cloning files, where the filesystem allows it (T-18).

**MySQL:**
- `READ ONLY = 1` refuses every account's writes, and needs `ALTER` to change (T-2);
- a grant on a schema by name outlives the schema's drop (T-5);
- a wildcard grant confines `copier` to its prefix, and partial revokes would make that wildcard literal (T-4);
- a table's definition, read in its own schema, names no schema for references inside it (T-10);
- an account changes its own password with no privilege, and nothing in the server refuses it (T-8);
- a drop waits on a transaction and not on an idle session (T-13);
- turning the binary log off needs nothing else changed (T-20).

**The CLI:** Psycopg's wheels for the supported Python versions; that the dependency group keeps `uv sync --locked` as it is (T-12).

**Sizes:** every figure in 2.5 (T-18).

## 11. What this means for DataIntent

Not decided here. Each is a consequence its own records take up, and the C1 run of 5.3 is where each shows.

- **The database list grows:** a `_start` beside each templated database, which accepts no connections (`ED:` 3.6).
- **A fixture role cannot connect to a working copy** any more. It could before, and read nothing.
- **The fixture grants `EXECUTE` on its own routines,** and `TEMPORARY` where a case needs it (4.7).
- **A fixture role cannot change its own password or settings** on PostgreSQL. `admin` still sets them (F-16).
- **MySQL's `demo` no longer sees fixture databases,** so the case that asserts it changes, and what the provider says of `demo`'s list with it (`MR:` 2.10).
- **Its copy prefix** should be one its fixture never uses on MySQL (4.4).
- **Its edit tests' writer** is a fixture role that `admin` makes a member of `megasamples_write`, named with `--write`. No `editor` exists on the service (4.1).
- **Its criteria 6 and the door** (`ED:` section 5; section 7, rule 4): on PostgreSQL the reset's step c is the door, held by the engine, for every account and not the editor's alone. On MySQL there is none, as that record already assumed.
- **Its SQLite staging** can take `template stage`'s directory and manifest in place of its own capture (`ED:` 3.5). That is its choice.
- **Its dependency review** covers the package at one commit with two drivers (`ED:` 4.4).
