# Templates, copies, the scripting CLI and the account model: version 1

**Design record · 2026-11-20 · round 5, the drafter's part. Status: a design under review. Nothing here is built, and nothing here has been run.**

- **What this is.** The design of **version 1** of sql-megasamples' pristine templates, per-test copies, the commands that scripts drive them with, and the account model that goes with them. It carries the strict PostgreSQL read profile of pull request #14.
- **Version 1 only.** The two deciders staged the design (DL-108): one bounded version 1, merged and rolled out once, and later stages as new work. This record holds exactly the list of DL-108 items 5 and 8 to 11, at the placements of its items 1 to 3. Its surface is frozen (section 0).
- **The fuller design is kept in Git history,** at `e0c2f935` of this file, as the source for the later stages. Section 11 names each stage, what waits in it, and every deferred finding against it.
- **What sql-megasamples is.** A stand-alone offering: sample database servers that someone spins up, in any network setting (DL-107). Sections 2 to 6 describe that product. A deployment is configuration; DataIntent's development instance is one, in section 7.
- **Rounds.** Round 1 is `2a15387`; round 2 `bdd9033`, with `9fe0bbd`; round 3 `e0c2f935`; round 4, the cut, `e8af920`. Astra's review 4, on the cut's scope and gates, found eight P1s, twelve P2s and a P3. Section 12 answers each by number. The reviews are in the coordinator's ignored `.local/megasamples-design/` in DataIntent.
- **What comes next** (DL-108 item 12): version 1's gates run on an isolated stack; then this record is revised from what was observed and reviewed to two clean rounds. **No round counts as clean while a gate of section 8.1 is unrun.** A required capability that fails its gate returns to the deciders.
- **Method.** Reading only: no container, no database connection, no network, and no credential file. So no statement about how an engine behaves has been observed.
- **Marks.** Each claim carries one:
  - **[R]** read in the cited file and line;
  - **[G-n]** rests on a native behaviour nobody has shown: gate *n* of section 8.1. It is not asserted either way;
  - **[I]** inferred, and not load-bearing;
  - **[D]** decided here, with the reason;
  - **[108-n]** decided by the two deciders in DL-108, item *n*; **[108+]** decided by them since, on this record's three readings, as the coordinator relayed it to this task.
  - A table or list whose heading line carries a mark is marked as a whole. A file and line cited inside any row is **[R]**.
- **Citations.**
  - `SM:` is sql-megasamples at `main`, `e61335f`. `PR14:` is its branch `fix/strict-read-account` at `2879fc4`.
  - `DL:` is DataIntent's `docs/work/decision-log.md` on `origin/coordinator/journal-during-full`: DL-070 to DL-103 at `d02f7384`; DL-104 to DL-108 at `5831ef43`. `LR:` is `docs/work/lines-register.md` there.
  - `ED:` is DataIntent's `docs/work/samples-service-editing-requirements.md`, `MR:` its `docs/work/samples-service-requirements-and-architecture.md`, and `DI:` any other DataIntent file, all at `4a8aad61` (`origin/coordinator/samples-p1`).

## 0. Version 1's surface

**This is the whole of it.** [108-7] Nothing below may be added to without the deciders. Anything may be removed or narrowed.

| Kind | Version 1 has |
|---|---|
| **Commands** | `megasamples copy create`, `show`, `list`, `drop`, `renew`, `release`, `sweep`. `megasamples reset` and `megasamples up`, as today, with the options below. No other command is new. [108+: no `template` and no `interface` command.] |
| **Options** | For `copy`: `--host`, `--port`, `--user`, `--connect-timeout`; `--password-file` or `--password-stdin`; `--prefix`, `--label`, `--lease`, `--identity`, `--wait`, `--dry-run`; for SQLite `--templates` and `--dir`. For `reset`: `--json`, `--operation`, `--discard sessions`, `--discard engine`, `--unattended`, `--status`, `--reconcile`. For `up`: `--discard engine`. |
| **Configuration keys** | `engines.<engine>.templates`; `engines.mysql.binary_log` [108+]; `copies.namespaces` (each: `prefix`, `owner`, `max_copies`); `copies.foreign` (each: `prefix`, `demo_reads`); `accounts.readers` and `accounts.writers` (each: `name`, `scopes`). |
| **`.env` keys** | Today's four. `MYSQL_DEMO_PASSWORD`. One for each namespace's owner and each declared account: its name in upper case, then `_PASSWORD`. |
| **Formats** | The JSON document's `schema`. The `interface` number. Four records with a tag each: the service's, a template's, a copy's, an operation's. For SQLite, a manifest and a sidecar. |
| **Service accounts** | `postgres`, `root`, `admin` and `demo`, as today. A namespace's owner. A declared reader; a declared writer. On PostgreSQL, the groups of 4.1. |
| **Hook rules** | Four (4.3): the creator must hold the new owner's rights; a namespace's owner is confined to its namespace and to registered templates; a new database is closed to `PUBLIC`; a role without `CREATEROLE` cannot alter roles or default privileges. |

- **`--discard` is one option with a named value.** [108+] `--discard sessions` ends people's sessions on a database's reset. `--discard engine` authorises replacing a whole engine's volume. A whole engine's reset refuses `--discard sessions` and requires `--discard engine`; so does `megasamples up` before it replaces a stale engine's volume (3.5).
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
| Item 5, seventh | Reader and writer grants declared in the configuration, locked until keyed, applied at start, and applied again by each reset under its exclusion. | 4.6 |
| Item 5, eighth | A safe service-side image restore. | 3.5 |
| Item 5, ninth | The CLI's contract for the formats version 1 has; the reset's session decision; the runbook's split. | 6; 3.5; 5.3 |
| Item 9 | A whole engine's reset refuses unless told to discard, and the service's record carries an identity for each volume. | 3.5 |

**What version 1 does not contain** is section 11: seven named stages.

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
- **What is promised of a name, and no more.** A name is never issued while its record or its object exists: both are confirmed absent under the namespace's lock before a row is written. **A name may come again once both are gone,** by a collision of twelve digits. Version 1 makes no grant by a copy's name on MySQL, so nothing of its own can wait there for a later copy. **A grant an administrator made by hand on such a name is not checked, and so no claim that a copy has one writer is made where that could be** (4.7). [D]
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

An `interrupted`, `unmanaged` or `inconsistent` object is an administrator's to remove, by hand. `copy list` goes on showing it.

**Removing a copy: the proof is checked at the removal itself.** [D: review 4's finding 6.]

| Engine | The removal | What stays possible |
|---|---|---|
| PostgreSQL | Under the change lock: the OID, the comment and the owner are read; then `DROP DATABASE` by name, plain. | PostgreSQL has no drop by OID. Between the read and the drop, a database could be put under the name only by someone who can first drop the old one: its owner or a superuser. No other account can enter that window. [G-24w] |
| MySQL | Under the change lock: **the marker is read in the schema.** If it is not there, nothing is dropped and the object is `inconsistent`. Then `DROP DATABASE`. | Between the read and the drop, only the namespace's owner or an administrator could replace the schema. [G-24w] |
| SQLite | **The final name is first moved aside,** into `.megasamples/`; what was moved is then compared with the retained link. If it is the same file, both are removed, then the sidecar. If it is not, it is put back by a link that cannot overwrite, or kept aside, and reported. | Nothing: the file compared is the file removed. |

- **The proof guards against accident and against a late or repeated command. It does not guard a principal against itself:** the owner of a copy, acting outside the CLI at the same moment, can defeat it on the two servers. That is said, and [G-24w] shows that nobody else can.
- **SQLite's adjacent files are not removed.** A `-wal`, `-shm` or `-journal` beside a dropped copy carries no identity; it is left and reported. No later copy takes that name while its record exists.

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
- **What that does not protect, said plainly.** A copy whose lease has ended is the sweep's to take. On PostgreSQL a connected session still saves it. **On MySQL an idle session does not, and for SQLite an open file does not.** The product claims that a sweep never removes a copy inside its lease, and no more.
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

**A copy,** as the namespace's owner, on one connection to the `megasamples` database:
- `CREATE DATABASE <copy> TEMPLATE <database>_start STRATEGY <strategy>`. The hook confines the name and the template, and closes the new database to `PUBLIC` (4.3).
- Its OID is recorded, and its comment written: `megasamples-copy/1` and the identity.
- **Last,** `GRANT CONNECT` on it to the namespace's read group. Until then only its owner can connect.
- **Its owner is the one ordinary account that can write it** (4.1). [G-23]
- **What it carries from its template** is 4.1's, each a gate of its own. [G-2a to G-2d]

**A drop** is a plain `DROP DATABASE`, never with force [G-8b]. With `--wait` it is tried again until the wait ends. A drop that gives up has changed nothing.

### 2.4 MySQL

**The template.**
- **It is the schema `<database>_start`, set `READ ONLY = 1`.** [D] Every account's write to it is refused [G-10a]; it can be read by several copies at once [G-10b]; changing the option needs `ALTER` on it, which `admin` and `root` hold and a namespace's owner does not [G-10c].
- **MySQL has no "accepts no connections" for a schema.** What stands in its place: `demo` holds no privilege there; a namespace's owner holds `SELECT` only; `admin` and `root` can read it, and can change the option. [D]

**How the image makes it.** After the dumps are loaded (`SM:engines/mysql/Dockerfile:39-42`), for each templated database, as `root`:
1. Its definitions are recorded in `megasamples.template_ddl`: tables, then routines, views in dependency order, triggers and events, each without its definer; and the insertable columns and the `CHECKSUM TABLE … EXTENDED` of each table. [G-13]
2. The template is made from the loaded database by the copy below, with each original definer kept.
3. Each table's row count and checksum are compared with the loaded database's.
4. The template is set `READ ONLY = 1`.

**A copy,** as the namespace's owner, on one connection, all of it inside the server:
1. `CREATE DATABASE <copy>`, with the template's character set and collation. **Then the marker event** (2.2).
2. Each table's recorded definition, with foreign-key checks off for the session.
3. `INSERT INTO <copy>.<table> (…) SELECT … FROM <database>_start.<table>`, a table at a time.
4. The routines, the views, and then the triggers and events.
5. Each table's row count and checksum compared with the template's record.
6. The row is set `ready`.

- **A copy has no grant of its own.** A namespace's owner is the one ordinary account that can write its copies; a declared reader of the namespace can read them (4.6).
- **The definer of everything in a copy is the namespace's owner.** [D]
- **Whether a replayed definition belongs to the copy and not still to its source** is [G-13]. A kind that fails excludes the datasets that use it, by name.

**What gets no MySQL template.** [D]

| Database | In version 1 | Why |
|---|---|---|
| Above 512 MiB of allocated bytes, measured at build | no template, no copies: exit 4, `too-large` | A logical copy's time and undo grow with its rows. The number is fixed by the build's measurements before the freeze. |
| A database of an installed dependency group (2.6) | no template, no copies: exit 4, `dependency-group` | A copy of one would point at the other's shared working copy (F-11). |

**A MySQL working copy still resets from the image.** A reset from a template waits (section 11). Its gap against DL-077 item 1 is recorded. [108-10]

**The binary log is configurable, and the image keeps it on:** `engines: {mysql: {binary_log: false}}`. Every logical copy is written to it a second time (F-10). [G-18a, G-18b]

### 2.5 SQLite

- **The template is the image's file,** and "read-only" is its mode. There is no server and no account.
- **The build writes a manifest** beside the files it already writes: `build/sqlite/templates.json`, with the tag `megasamples-manifest/1` and each file's name, size and SHA-256 (`SM:README.md:173`). A caller elsewhere works from a copy of that directory. No command stages it. [D]
- **A copy,** in the caller's directory:
  1. the name's lock file is locked; the sidecar is made with exclusive creation: `reserved`, then `issuing`;
  2. the template is copied to its retained name in `.megasamples/`, synced, and held to the manifest's SHA-256;
  3. it is published by a hard link to its final name, which fails if that name exists. **The retained link stays.** [G-19a, G-19b]
- **A drop** is 2.2's: move aside, compare, remove.
- **Nothing goes over the network.** A caller's own directory of copies belongs to no server: its documents carry no volume identity, and a whole engine's reset does not touch it.

### 2.6 Which databases get a template, the dependency group, and the storage

**The default selection is `core`:** every physical database whose base dataset is of tier `core` or `core-medium`, less MySQL's exclusions (2.4). It is configured for each engine by `engines.<engine>.templates`: a selector, a list of databases, or `none`. It is baked. [D]

**An installed dependency group** is a set of databases, on one engine, that refer to one another: on MySQL, `oracle_hr` and `oracle_oe` **when that engine is configured with both.** An engine configured with `oracle_hr` alone has no group, and `oracle_hr` is then an ordinary database. [D: review 4's finding 20: round 4 refused both by name, whatever was installed.]

**Version 1 does not bound storage.** [D]
- **A template is its database again.** A live copy is its database again. A PostgreSQL reset needs its database once more while it runs.
- **The build measures and prints** each template's allocated bytes, appended datasets included (F-9), and each copy's time. A deployer sizes a volume from that.
- **`max_copies`** bounds how many copies a namespace's owner can have through the CLI. It bounds no bytes.
- **When the disk fills,** version 1 promises this and no more, on each retained path:

  | What was running | What must hold afterwards | Gate |
  |---|---|---|
  | A copy's creation, on a server | The server stays up. Every template and every working copy is whole. The copy is `interrupted`, and kept. | G-9, G-17a |
  | A PostgreSQL reset | The same: nothing is swapped until the new copy is whole. | G-9 |
  | **A MySQL reset from the image, after its drop** | The server stays up. Every other schema is whole. **This one is not, and is not claimed to be:** its operation is unsettled at `loading`, and reconciling completes it once there is space. | G-17b |
  | An operation's own record | The phase not written means the step it announces was not taken. An outcome not written leaves the operation unsettled, which reconciling settles. | G-17b |
  | A SQLite copy's publication, or its sidecar | No file under a final name that is not whole. | G-19c |
  | A SQLite reset, or its operation's file | The working file is the old one or the image's, whole: the reset stages the new file beside the final name and renames it over (`SM:megasamples/reset.py:319-327`). The operation's file is written the same way. | G-19c |

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
| `megasamples reset …`; `megasamples up` | where the service runs | 3.5. |

- **`copy` needs a TCP path to the engine's port, and nothing else:** no container runtime, no checkout. For SQLite it needs `--templates DIR` and `--dir DIR`. [D]
- **`reset` and `up` run where the service runs,** as today (F-1). A reset asked for from elsewhere waits (section 11). [108-6]
- **`ENGINE:DATABASE`** follows the reset's own pairs (`SM:megasamples/reset.py:6`).
- **A copy owner's credential may be used from another machine only after its engine's confinement gates have passed:** G-29a to G-29d on PostgreSQL, G-11b on MySQL. Until then the product does not claim it, and says so. [108-5]

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
| 3 | the engine cannot be reached, or the sign-in is refused | nothing changed |
| 4 | not offered here: no template, `too-large`, `dependency-group`, or a failed gate's command | nothing changed |
| 5 | refused by a rule: namespace, label in use, identity or state not as expected, the limit, an unknown format, an unsettled operation, a missing or wrong `--discard`, a stale image | nothing changed |
| 6 | busy | **nothing changed, and the CLI confirmed it** |
| 7 | failed | **nothing is left changed, and the CLI confirmed it** |
| 8 | unsettled | **a durable record describes what is there** |

| Command | 6 means | 7 means | 8 is read by, and settled by |
|---|---|---|---|
| `copy create` | the namespace lock could not be had; no row was written | — | `copy list --label`. **An interrupted create is not settled by any command:** it is kept (2.2). |
| `copy drop` | sessions remained at the end of the wait; the copy is untouched | — | `copy show`; `copy drop` again |
| `copy sweep` | — | — | `copy list`; `copy drop` for each `dropping` one it names |
| `copy renew`, `release` | another change holds the name | — | — |
| `reset`, one target | another reset holds the target's lock, or sessions were found; **the target is as it was** | it failed before anything of the target changed | `reset --status`; `reset --reconcile` |

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

### 3.5 Resets, and anything that replaces a volume

**One reset of one target at a time, and one unsettled operation for each target, on every path.** [108-5]

**The paths version 1 has:**

| Target | Path | Its option, when people's sessions are there |
|---|---|---|
| A PostgreSQL database with a template | from the template, into a transient, with a swap | `--discard sessions`; or `--unattended`, which refuses |
| A PostgreSQL database with no template | **from the image, into a transient, with the same swap** [108-5] | the same |
| A MySQL database | from the image, in place, as today | **always `--discard sessions`** |
| A SQLite database | from the image's file, as today | **always `--discard sessions`** |
| A whole engine | the volume replaced from the image, as today | **always `--discard engine`** |
| `megasamples up`, with an engine's image stale | the same replacement (F-32) | **always `--discard engine`** |

**An operation.** Each reset of each target is one operation, with an identity.
- **A script resets one target for each call, and gives the identity:** `--json` and `--operation ID` take exactly one target. An identity that already has a record is refused: exit 5, `operation-exists`. So a caller that lost a reply asks again under the same identity and is told what happened. [D: review 4's finding 18: with several targets every identity arrived in the one document a caller could lose.]
- **A reset of several targets is for a person:** text output, each operation's identity printed as it starts, and `reset --status ENGINE` afterwards.
- **Its record is written before each step, and its terminal outcome is kept for the life of the volume:** `done`, `rolled-back` or `failed`.
  - For a database on a server, it is a row in `megasamples.operations`.
  - For a SQLite database and for a whole engine, it is a file where the service runs, outside the volume.
- **Admission.** A reset is admitted only if the target has **no operation that is not terminal.** Otherwise: exit 5, `unsettled`, naming it. Only `reset --reconcile` settles one, and it settles that operation only.
- **`megasamples reset --status [--operation ID]`** answers: `running`; `unsettled`, at a phase; a terminal outcome; or **`unknown`: this volume has no record of it.** It gives the volume's identity with every answer. `unknown` on the volume the caller started against means it never started. `unknown` on another volume means only that the volume was replaced since.

**Who holds what, from admission to the end.** [D: review 4's findings 2 and 3: round 4's MySQL lock began with the worker, after the row and the suspension and before the check and the regrant; and its PostgreSQL worker had no gate.]

| | The coordinator | The worker |
|---|---|---|
| **What it is** | One session of the superuser inside the container, opened first and kept to the end. | A second process, for the image path only: `pg_restore` on PostgreSQL; the stream of the image's dump on MySQL. |
| **What it holds** | **The target's reset lock, from before admission until after the outcome is written.** | PostgreSQL: nothing; it writes only into this operation's transient. MySQL: **a second lock, the target's worker lock,** taken by the first statement of its stream. |
| **What fences it** | The lock. | PostgreSQL: its transient exists under this operation's name alone. MySQL: its stream's second statement raises an error unless the operation's row still carries the **epoch** the coordinator gave it, and its client stops at the first error. |

- **An operation is live while either lock is held.** Admission and reconciliation go on only after taking **both** without waiting; and reconciliation **raises the row's epoch first.** So a worker that starts late finds another epoch and changes nothing; a worker already running keeps its lock, and nothing else touches the target until it ends. [G-26m]
- **On PostgreSQL** a worker that outlives its coordinator goes on filling its own transient and nothing else. A reconciliation then keeps that transient and reports it; a second reset uses another. [G-26p]
- **SQLite and a whole engine:** the lock file where the service runs, one for the engine (F-3). So a whole engine's reset and a reset of one of its databases never run together there.
- **If an engine's lock or worker gate fails, that engine's reset of one database is not offered.** A whole engine's reset remains.

**A PostgreSQL reset, by either path.**

| Step | What happens | The phase |
|---|---|---|
| a | The lock. Admission. The operation's row, **with the working copy's own OID.** | `building`, written first |
| b | `CREATE DATABASE <database>__new_<id> OWNER admin`: from the template; or empty, and the worker restores the image's dump into it. **Its OID is recorded as soon as it exists.** Then its grants are given, in it (4.1). It holds no `CONNECT` for anyone but its owner. | `built`, written after |
| c | **The door is closed:** `ALTER DATABASE <database> ALLOW_CONNECTIONS false`, in one transaction with the phase. [G-3a] | `closed` |
| d | The session decision (below). | `closed` |
| e | **In one transaction:** the working copy is renamed to `<database>__old_<id>`; the new one is renamed to `<database>`; its `CONNECT` is granted to the working groups; the phase is set. [G-3b] | `swapped` |
| f | **The old transient is dropped only if its OID is the one recorded at step a.** [D: review 4's finding 6.] | `done`, written after, and kept |

**Reconciling it:**

| The row's phase, with both locks free | What reconciling does | Outcome |
|---|---|---|
| `building` | **Nothing is dropped.** A transient is kept and reported. | `rolled-back`: the working copy is as it was |
| `built` | drops the new transient, if its recorded OID matches and it has no session; otherwise keeps and reports it | `rolled-back` |
| `closed` | **opens the door again;** the transient as above | `rolled-back` |
| `swapped` | drops the old transient, by the OID recorded at step a | `done` |

- **Steps c and e are each one transaction or the swap is not built.** If [G-3a] or [G-3b] fails, PostgreSQL's reset of one database returns to the deciders.
- **A crash in step c or d leaves the working copy closed** until someone reconciles. It is kept short by doing all the copying first, and the CLI opens the door again when it is interrupted by a signal.

**A MySQL reset, from the image, in place.** Today's procedure (F-4), under the two locks and the record:

| Step | What happens | The phase |
|---|---|---|
| a | The coordinator's lock. Admission. The operation's row, with its epoch. | `started` |
| b | `--discard sessions` is required (below). **Each declared writer's grant on this schema is revoked, and that account's sessions are ended.** The suspension is written in the row. [G-27a] | `excluding` |
| c | The worker: its lock, its epoch check, then the image's dump, which drops the schema and loads it. | `loading`, written first |
| d | Each table's row count **and checksum** against the image's own, read from the pristine container that is still running. | `loaded` |
| e | **The declared grants are applied again.** | `done`, written after, and kept |

- **It cannot be undone after step c begins.** Reconciling says which it does:

  | The row's phase, with both locks free | What reconciling does | Outcome |
  |---|---|---|
  | `started`, `excluding` | applies the declared grants again | `rolled-back` |
  | `loading` | runs steps c to e again, under the same operation and a new epoch | `done` |
  | `loaded` | **checks, and applies the grants. It does not load again.** | `done`, or `failed` with the tables that differ |

- **`done` requires both:** the data checked, and the declared grants in place.
- **A start of the server during an unsettled reset does not reopen it.** A revoked grant stays revoked across a restart [G-27b]; the start applies declared grants (4.6), and leaves out any that an unsettled operation's row records as suspended.
- **A database of an installed dependency group is not reset singly** (2.6): exit 4, `dependency-group`. A reset of one would leave the other pointing at rows that are gone, and today's path does exactly that. They are reset with the whole engine. [108+: accepted, in the impact note.]
- **If [G-26m] or [G-27a] fails,** a MySQL reset of one database is not offered: where any writer is declared, for G-27a; at all, for G-26m.

**A SQLite reset** is today's (F-4), under its lock file and an operation's file. It stops the consoles that read the files, and those consoles also carry people's sessions on the other engines. **So it always needs `--discard sessions`, and says which consoles it will stop.** [108+: accepted, in the impact note.]

**The session decision.** [108-2] **A reset of a database preserves sessions unless it is told otherwise.**

| | What happens when people's sessions are on the target |
|---|---|
| **By default** | The reset stops: exit 6, saying how many sessions and whose. On a terminal it first warns, and asks. |
| **`--discard sessions`** | The warned choice, given as an option: the sessions are ended and the reset goes on. |
| **`--unattended`** | For automation. One PostgreSQL database. Any session that is not disposable is a refusal before any change. It never takes `--discard`. |

- **Only a session positively known to be the product's own is ended without the option.** [D: review 4's finding 7: a person at a bundled console has the console's address, and between statements is idle with no transaction; round 4 would have disconnected them.]
  - **The product's own sessions say so:** on PostgreSQL, the health probe and the CLI set a reserved application name on the connections they open. A client that sets that name itself has declared its own session disposable.
  - **Every other session is a person's, a console's included,** and is preserved.
  - Whether a session can be told that way, and whether a console holds a session while nobody uses it, is [G-32a, G-32b]. **If consoles hold sessions on their own, the default would refuse every reset; that returns to the deciders,** with what was observed.
- **On PostgreSQL** the door is closed first, so nobody arrives between the look and the swap. [G-3c]
- **MySQL has no door,** and a session there can name any schema. So a MySQL reset of one database always needs `--discard sessions`, and `--unattended` is refused before any change: exit 4.
- **This changes today's default,** which disconnects (F-4). It enters version 1 at the freeze, with the impact note of 5.4. [108-2]

**Replacing a whole engine's volume.** [108-9] [108+]
- **It is refused before any change unless it is given `--discard engine`.** `--discard sessions` is refused for it: it is not the same decision. Every copy, every session and every account that is not the image's goes with the volume. There is no drain in version 1.
- **`megasamples up` is the same act when an engine's image is stale** (F-32). **Without `--discard engine` it replaces nothing:** it names the stale engine and stops, exit 5, `stale-image`, before it recreates anything. With it, it does what it does today. An engine whose container does not exist yet is simply started. [D: review 4's finding 5.]
- **The service's record carries an identity for each volume.** [G-33a] Every document carries it.
  - **On a server** it is in the server: MySQL's own server identifier, which the baked data directory must not hold; on PostgreSQL a value written at the first start.
  - **For the service's SQLite files** it is a file in their volume, written when the volume is first started and never copied from the image. A SQLite reset reads it under the engine's lock file.
  - **A caller's own directory of copies has none** (2.5): its documents say null.
- **Nothing a command does can land in a volume it did not start on.** [D: review 4's finding 4.]
  - **A command never reconnects.** Each connection that changes anything is opened at the command's start, and the volume's identity is read on it. A replaced server ends that connection, and with it the command: exit 8.
  - **A worker, which opens a connection of its own, is fenced by what only the old volume holds:** PostgreSQL's worker restores into a transient that exists only there; MySQL's stream fails at its epoch check, for the operation's row exists only there. [G-33b]
  - **A reconciliation** reads its operation on the connection it changes with; on a new volume it finds none, and answers `unknown`.
  - **Where the service runs,** a reset of one database and anything that replaces its engine's volume take the same lock file (F-3).
- A name or an identity that a caller kept from the old volume finds nothing in the new one: `copy show` says `absent`, and `copy drop` succeeds on nothing.

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
- **In a working copy, `admin` grants row changes to `megasamples_working_write`,** at build and in each reset (3.5, step b).

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

Input to **one independent review, of two things: the final compiled hook, and the `SECURITY DEFINER` event trigger** (F-26). Each finding is from reading `PR14:` at the cited lines; none was run.

| # | Finding | Where | Disposition |
|---|---|---|---|
| H-1 | **Every role but `demo` and `admin` may be left unable to call any built-in routine,** an operator's function among them; and `admin` could not repair it (F-13). [G-5a] | `PR14:engines/postgres/init/10-read-profile.sql:14-15`, `:23-35` | If reproduced: P-1. |
| H-2 | **The hook's `REVOKE` may do nothing, and succeed,** when the creator is not the new owner and does not inherit the owner's rights. [G-4a] | `PR14:engines/postgres/read-policy/read_policy.c:31-38` | Rule 1, and rule 3's confirmation. |
| H-3 | **An error in the hook after the copy may leave the copied files with no database.** [G-4b] | `PR14:engines/postgres/read-policy/read_policy.c:24-38` | **If reproduced, it is resolved before the merge:** everything the hook can know is refused before any file is copied; the step after the copy may not raise for a reason of its own. If a raising path remains, or the leak shows with no hook at all, it returns to the deciders. |
| H-4 | **The role name `admin` is compiled in.** | `PR14:engines/postgres/read-policy/read_policy.c:32-33` | The hook names no account. |
| H-5 | **The hook closes `TEMPORARY` only.** | the same | `CONNECT` too. |
| H-6, H-7 | **A role may change its own password, its own settings, and its own default privileges.** [G-6a] | — | Rule 4. [G-6b] |
| H-8 | **`NOTIFY` is a statement, not a routine** [I]; the page says notifications "receive no `demo` grant". | `PR14:docs/strict-read-account.md:3` | Correct the page. `NOTIFY` stays allowed. |
| H-9, H-10 | **The event trigger names `admin`,** runs as its definer, and is enabled in the ordinary way [I]. | `PR14:engines/postgres/read-policy/read_policy--1.sql:3-20` | It checks that the role exists; `ENABLE ALWAYS`. The review covers its definer's rights and its search path. |
| H-12 | **A policy image started on data from before the policy** would run with the hook and without the grants. | `PR14:engines/postgres/Dockerfile:83` | The build writes the policy's version into the data directory; the start wrapper refuses one whose marker is missing or older. |
| H-15 | **A role that may create databases can create one of any name, from any template.** | PostgreSQL's own rule | Rule 2. |

**The four rules.** [D]

| # | When | What |
|---|---|---|
| 1 | Before `CREATE DATABASE` | Refuse, when the creator would not hold the new owner's rights. |
| 2 | See below | The confinement of a namespace's owner. [108-5] |
| 3 | After `CREATE DATABASE` | Close `CONNECT` and `TEMPORARY` on the new database to `PUBLIC`; then confirm it. |
| 4 | Before `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES` | Refuse, when the caller is neither a superuser nor a holder of `CREATEROLE`. [G-6b] |

**Rule 2, exactly.**
- **A namespace is known to the hook by its marker role:** `megasamples_copy_<prefix>_owner`. An account is that namespace's owner if it is a member.
- **A registered template** is a database marked a template, accepting no connections, owned by a superuser, **whose comment carries the service's template tag.** Only its owner can set that comment.
- **`CREATE DATABASE` by a namespace's owner is refused unless** its source is a registered template `<database>_start` [G-29b], **and** its name is exactly `<prefix>_<database>_` followed by twelve hexadecimal digits, with that `<prefix>` one of the namespaces it owns and that `<database>` its source's [G-29a].
- **`ALTER DATABASE … RENAME` by a namespace's owner is refused.** Version 1 never renames a copy. [G-29c]
- **The rule binds a namespace's owner, and nobody else.** [D: review 4's finding 9: round 4 also kept every other creator out of a namespace, which is a rule of its own that DL-108 did not list.] A role that may create databases and owns no namespace creates as PostgreSQL lets it [G-29d]. If it puts a database under a namespace's prefix, that database is `unmanaged`: listed, reported, and removed by no command (2.2).
- **It names no account and holds no state.** It reads the catalog.

**What rule 2 is for.** DL-108 asks that the hook confine a namespace's owner, wherever it signs in from. **So if any of G-29a to G-29d fails, PostgreSQL copies are not offered at all, here or from elsewhere, and it returns to the deciders.** [108-5] Rule 2 does not bound bytes: an owner can still fill the disk with copies of its own.

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
- **An account that manages accounts can change the service's own.** A deployer or a consumer may add one; the product ships none. It is a consideration for whoever adds one (5.2), not a gate of the product.
- **MySQL stays not claimed strict:** named locks, and the two definer views of `employees`, are as F-14 found them.

### 4.5 An account changing its own password

The second of line 10's two items. A read account's credential is shared: by the consoles, the probe, and whoever is given it. A holder who changes it locks the others out, and can set it to a value everyone knows.

| Engine | In version 1 |
|---|---|
| **PostgreSQL** | **Refused,** by the hook's fourth rule, for every role without `CREATEROLE`. Natively such a role can change its own password [G-6a]; with the rule it cannot, and still reads [G-6b]. |
| **MySQL** | **Not known to be possible. [G-16] establishes it first.** |

- **PostgreSQL takes MySQL's fallback only if G-6b shows the rule failing to refuse the password change while the account still reads.** No other result of G-6a or G-6b selects it. [D: review 4's finding 12.]
- **G-16 records, before any branch is chosen:** each statement it tried by which a MySQL account changes its own password; each mechanism of the pinned server it tried against that, by name; and, for each mechanism, whether `demo` still signs in from the probe, from each console and from a client.
- **If G-16 finds a refusal that keeps `demo` usable,** it is built. If that would add to section 0's surface, it returns to the deciders first.
- **If it finds none,** the product says that MySQL cannot refuse it, and version 1 has what limits the harm:
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
- **Its grants are exactly what is declared:**

  | | PostgreSQL | MySQL |
  |---|---|---|
  | A reader of the working copies | member of `megasamples_working_read` | `SELECT, SHOW VIEW` on each working schema, by exact name |
  | A reader of a namespace | member of `megasamples_copy_<prefix>_read` | `SELECT, SHOW VIEW` on the namespace's pattern |
  | A writer | member of `megasamples_working_write` | the reader's, and `INSERT, UPDATE, DELETE` on each working schema |

- **The start applies it,** every time: it makes each declared account that is missing; sets each keyed one's password; locks each unkeyed one; **locks every account it made before that is declared no longer;** and makes the grants exactly the declared ones. The configuration is the one authority.
- **Each reset applies it again, under its exclusion** (3.5).
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
| `demo`; a declared reader | read what it is granted. On MySQL: take any named lock; change its own password, unless G-16 finds a refusal | the read profile on PostgreSQL; its grants on MySQL |
| a declared writer | change rows of every working copy | no definition change; a reset restores |
| **a namespace's owner** | **every copy of its namespace, whoever made it:** read, write, drop. Fill the disk with copies. On MySQL, take any named lock, and so make a copy or a reset report busy. | PostgreSQL: the hook [G-29a to G-29d]. MySQL: nothing outside its pattern, and no granting [G-11b]. |

- **One credential is one trust domain.** Two runs that share a namespace owner's credential can change each other's copies, and the product reports nothing that says otherwise.
- **The product makes no claim that a copy has had one writer.** On PostgreSQL the engine itself bounds who can write a copy: its owner and the administrators. On MySQL an administrator's grant made by hand on a copy's name, perhaps before that name was issued, is something the owner cannot see (2.1). A consumer that needs that claim establishes it on its own side (7.2).

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

**Which ways of starting it version 1 controls.** [D: review 4's finding 10.]

| Path | Who publishes the port | What version 1 enforces there |
|---|---|---|
| `megasamples up`; the generated Compose file used directly | the product: loopback, always | Defaults 1 to 7. T-23 checks that no configuration makes the generator publish wider. |
| An image run by hand; a Compose file someone wrote or edited | **the deployer** | Defaults 2 and 5, which are in the image: no privileged or declared account is usable without its own private key. **Not default 1:** an image cannot know how its port is published. **`demo`'s password is published, so whoever publishes that port wider gives read access to the samples to anyone who reaches it.** |

DL-108 item 2 (a) approved refusing a wider listener while any account keeps a published password. **On the second path the product cannot do that from inside the image;** version 1 documents it instead. That exception is returned to the deciders (section 12).

**Default 2, exactly.**
- **The privileged accounts are `admin` on both engines, `postgres`, and both of MySQL's `root`.**
- **The image holds none of them usable over the network:** each is baked with no password that signs in. [G-35p, G-35m]
- **The start gives one a password only from its key, and tests the value:** a key that is unset, **or set to the value published today,** leaves that account locked, and the start says which.
- **`megasamples up` writes a private value for each such key that is missing,** into the checkout's `.env`, closed to others, and never prints it.
- **The reset, and everything else that signs in as a superuser, reads the same keys** (3.4). With none set it cannot run, and says so.

**Default 3, exactly.** [D: review 4's first P1: round 4 changed three consoles and left two generated pages printing `admin`'s password.]
- **No console is given a privileged password.** phpMyAdmin's second server asks for a sign-in instead of holding `admin`'s; DbGate's and CloudBeaver's `admin` connections are stored without a password, or not stored (F-31).
- **No generated page prints one.** The landing page and the Adminer help page show `demo`'s, and for `admin` say which key in `.env` holds it. Neither generator reads a privileged key at all.
- **Pages generated before this are removed.** `megasamples up` removes the generated pages before it writes them, and removes them when the landing console is not configured.
- **`demo` stays signed in,** as the consoles open today.

**Defaults 2 and 3 may be one bounded pull request of their own, merged before the build.** [108-5]

### 5.2 What a deployer weighs

Version 1 gives these mechanisms. Which to use is the deployer's.

| What to weigh | What version 1 gives | What stays the deployer's |
|---|---|---|
| **Who can reach the engines** | Loopback publication, on the paths the product controls. | Any forward, proxy, shared network, or image run by hand. **Version 1 has no setting for a wider listener and no rule about where a client comes from** (section 11): whoever reaches the port can try every account, and `demo`'s password is published. |
| **The transport** | PostgreSQL's passwords are not sent (`SM:ARCHITECTURE.md:166-167`). The product configures no TLS (`MR:` B-04). | A tunnel, or a network the deployer trusts. |
| **Passwords** | One key for each account. **Rotation:** set the key and start again. **Revocation:** clear a key, and the account is locked at the next start. | When, and who is told. |
| **A shared read credential** | `demo` is one account. On MySQL a holder may change its password, unless G-16 finds a refusal. | A declared reader for each consumer that must not be able to lock out the others; `demo` only for the consoles. |
| **Who makes copies** | A namespace and an owner for each consumer that must be kept apart. | How many to bake, and which to leave locked. |
| **A copy owner's credential away from the service** | Claimed only once that engine's confinement gates have passed (3.1). | **It can still fill the disk.** Version 1 bounds no bytes. |
| **A consumer that manages accounts** | A foreign namespace keeps the product out of the consumer's objects. | An account that manages accounts may be able to change the service's own. The product ships none and tests none; whoever adds one tests what it reaches, **before that account and a credential that has left the machine exist together.** |
| **Handing a credential over** | Nothing: **it is the deployer's own procedure,** which the README describes: one credential, alone, never the `.env`. [108-11] | The channel, and the record of it. |
| **Write access to the samples** | A declared writer (4.6). | Whether to declare one. |

### 5.3 Changing a deployment, and the runbook's split

- **A new image renews the data volumes,** and only when told to: `megasamples up --discard engine`, or a whole engine's reset (3.5). Everything made on the old ones goes. Declared accounts return at the start, from the configuration.
- **Image and data must match.** On PostgreSQL the policy image refuses data without its marker (H-12). On MySQL nothing refuses. SQLite has no such pairing.
- **The runbook is split in this work.** [108-3]
  - **The product keeps a short, tested, general upgrade route, with its helpers:** replace the images, keep the old volumes until the new ones are checked, go back by the kept volumes.
  - **The live-upgrade runbook moves to DataIntent's side,** as the procedure of its rollout's plan, pinned to a sql-megasamples revision (F-29).
  - **The README's dated paragraph about one deployment, and its paragraphs that take LAN forwards for granted, leave it,** or become a profile.
  - The split is rehearsed before that rollout's approval (7.2).

### 5.4 The impact note for what version 1 changes

It enters at the freeze, with migration instructions, and every caller is changed in the same work. [108-2] [108+] [D: review 4's finding 20.]

| What changes | Who is affected | What to do instead |
|---|---|---|
| **A reset of a database no longer ends people's sessions by itself.** | Anyone who ran `make reset` or `megasamples reset` on a database others were connected to. | Answer the question on a terminal, or pass `--discard sessions`. Automation passes `--unattended`, and is refused while anyone is there. |
| **A MySQL or SQLite reset of one database always needs `--discard sessions`.** | Every script that resets one. Automation has no unattended route for either. | Pass it knowingly. **A SQLite reset stops the consoles, and with them people's sessions on PostgreSQL and MySQL through those consoles;** the reset names the consoles first. A SQLite shell someone opened by hand is not seen, and must be closed first, as today. |
| **A whole engine's reset, and `megasamples up` on a stale image, need `--discard engine`.** | Anyone who rebuilt an image and ran `make up`; anyone who ran `make reset R=<engine>` or `R=all`. | Pass it knowingly: **every database, copy, account and edit on that engine goes.** |
| **`oracle_hr` and `oracle_oe` do not reset singly on a MySQL that has both.** | Anyone who reset either. | Reset the whole MySQL engine, which discards everything on it. An engine with only one of the two is unaffected. |
| **`admin` and the superusers have no published password.** | Anyone who signed in as `admin` with the published value; every tool that did. | Read the private value `megasamples up` wrote into `.env`. |
| **No console signs in as `admin`, and no page prints its password.** | Anyone who used a console's full-access connection. | Sign in with the private value. |

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
| **Declared accounts** | A reader for each LAN consumer, if G-16 finds no refusal. **No writer:** its first is the two deciders' decision, after the controls of `ED:` R-39. |
| **MySQL's binary log** | Its choice at its rollout's approval, after G-18a. |

**Its policy,** each a choice among 5.2's mechanisms:
- **No administrator's or superuser's credential leaves the machine,** `di_admin` and its fixture and provisioning credentials included.
- **Whether to send a namespace owner's credential elsewhere is DataIntent's.** It sends none before that engine's gates. Meanwhile it records DL-077 item 3's "from a separate machine" as unmet for that engine. [108-1]
- **`di_admin` and a MySQL namespace credential that has left the machine must not come to exist together untested.** DataIntent tests what `di_admin` can do to the service's accounts **before the first sending, or before it provisions `di_admin`, whichever would first bring the two together.** [D: review 4's finding 17: round 4's condition fired only on a later provisioning.]
- **It keeps the record of each sending,** an uncertain delivery included, and holds a send it cannot record. [108-1]
- **MySQL's `demo`, if G-16 finds no refusal,** gets a key of its own, rotated at its rollout, which ends the value its LAN machines already hold; each of them reads with its own declared reader.
- **Its automation resets with `--unattended` only:** one PostgreSQL database at a time. It resets no MySQL database, **and no SQLite one: it has no unattended route to either in version 1.** Its SQLite cases work on copies of their own. [108-1]
- **A long run renews its lease.** `ED:` criterion 11, "never a copy in use", is recorded as **not passed** for an idle MySQL session and an open SQLite file whose lease has ended.
- **A result that needs to be the only writer** (`ED:` R-35). On PostgreSQL it holds for a namespace one run uses alone. **On MySQL it is recorded as unmet in version 1,** unless DataIntent itself, as an administrator on its own instance, has read that no grant but the owner's reaches the copy's name. [D: review 4's finding 16.]
- **After its deployment, loosening one of these is the owner's** (DL-106), as its own rule.

**What else version 1 means for it.**
- A copy's name is issued; its harness keeps the name and the identity, and finds a copy by its label after a lost reply.
- Its edit tests' writer of a **copy** is that namespace's owner in version 1.
- A MySQL copy holds one event that the dataset does not: the marker (2.2).
- The provider's list of databases does not gain the templates: it leaves out every database marked as a template (F-17). A raw catalog query shows them; the registry does not list them. Each is tested apart.
- A fixture role cannot connect to a working copy. The fixture grants `EXECUTE` on its own routines, and `TEMPORARY` where a case needs it. A fixture role cannot change its own password on PostgreSQL.
- Its harness maps the exit codes (`ED:` 4.2): 3 and 4 are Not run; 2, 5 and 7 Failed; 6 a deferral; 1 and 8 Failed, and it reads the state first.

**Its one rollout** (DL-103; DL-105). The plan is DataIntent's record; this is what version 1 asks of it.

| # | Step | It must show |
|---|---|---|
| 1 | **Version 1's gates** (8.1), on an isolated stack. Then this record revised and reviewed to two clean rounds. | DL-108 item 12. |
| 2 | **The credentials, consoles and pages change** (5.1), as its own pull request if it is split out. | Merged before the build. |
| 3 | **The build,** test-first, on a branch that merges pull request #14's branch first (section 9). | 8.2. |
| 4 | **DL-078's README,** on the same branch, reviewed. **The runbook's split,** rehearsed. | Section 10; 5.3. |
| 5 | **The branch's candidate,** built in an isolated store. | The dataset matrix, the image tests and every native suite Passed. |
| 6 | **DL-087's acceptance is recorded.** | Nothing from step 7 on comes before it (F-26). |
| 7 | **DataIntent's comparison against that candidate,** the read account's admission among it. **And the reconciliation of the product's routine inventory with DataIntent's own (IA-01), recorded: each signature in one and not the other, with its disposition.** | Below. These are DL-085 item 3's conditions. |
| 8 | **The reviews, on the head step 7 compared:** one independent review that covers **both the compiled hook and the `SECURITY DEFINER` event trigger,** each named in its record; Fable's and Astra's blessing (DL-086). | A review that signs off one of the two does not meet it. |
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
  - **An account with no key, or a privileged one keyed to the published value, is refused.**
  - The probe and each console sign in as the account they are meant to. No console and no served page offers or shows anything privileged.
- **Its rollback** is by the kept volumes (5.3). Where MySQL's `demo` was rotated, the old shared value is in force again afterwards.

## 8. Gates and tests

### 8.1 Version 1's feasibility gates

**These run next, on an isolated stack.** [108-12] Each is **one assertion**; each tests the crossing or the identity it names, with a control that would fail if the assertion were false; and each names everything of version 1 it withholds. A required capability that fails returns to the deciders.

**Two kinds, marked in each row:**
- **E · engine-only.** The stack as `main` builds it today, its consoles included, or stock engines and stock clients; raw SQL and plain processes; for pull request #14's profile, its candidate as that branch builds it today. **No code of this work. These can all run now.**
- **H · needs the hook.** The same, on an image with the changed hook built as a prototype. Still no CLI code.

Anything that needs the CLI, the start wrapper or the package is not a gate: it is a regression of 8.2. [D: review 4's finding 13.]

**PostgreSQL: the template and what a copy carries.**

| Gate | Kind | The one assertion | The test, with its control | Withholds if it fails | Serves |
|---|---|---|---|---|---|
| **G-1a** | E | A template that accepts no connections refuses every connection. | Each account, the superuser over the network and inside the container: refused. Control: with connections allowed, one succeeds. | every PostgreSQL template, copy, and reset from a template | 5, first |
| **G-1b** | E | A role with `CREATEDB` alone copies it, and two copies at the same moment both succeed. | Two sessions create from it together; both exist, and their tables' checksums equal the template's twin. Control: a database that is not a template is refused to that role. | the same | 5, first |
| **G-1c** | E | `admin` cannot alter, rename, drop or comment on it. | Each statement as `admin`: refused. Control: the same on a database `admin` owns: accepted. | **every use of a template as pristine:** PostgreSQL copies, template resets, and rule 2's registration | 5, first and fifth |
| **G-2a** | E | A copy carries each object's owner, and each object's grants to group roles and to `pg_database_owner`. | The catalog's rows for both, in a template's twin and in its copy: equal. Control: a grant added to the twin afterwards is absent from the copy. | the read group and the owner's writing: all PostgreSQL copies and reset-made working copies | 5, first and fourth |
| **G-2b** | E | A copy carries the default privileges. | The same, for the default-privilege catalog. | the closed defaults of pull request #14 on every copy and reset-made working copy | 5, fourth |
| **G-2c** | E | A copy carries the policy's extension and its event trigger. | On pull request #14's candidate: a routine created in a copy has no `EXECUTE` for `PUBLIC`. Control: in a database made from a template without the extension, it has. | **the strict profile on every copy and reset-made working copy** | 5, fourth |
| **G-2d** | E | A copy does not carry `CONNECT`, its owner or its comment. | A twin with a `CONNECT` grant and a comment; its copy has neither, and its owner is the creator. | 4.1's `CONNECT` table; the copy's own comment as its proof | 5, first and second |
| **G-23** | E | A grant to `pg_database_owner` is held, in each database, by that database's owner and by no other ordinary role. | In a copy a namespace's owner made: it changes a row; a member of the namespace's read group and a member of the working write group are refused. Control: the owner is refused the same row in a working copy. | a copy's owner writing its copy: PostgreSQL copies | 5, first and seventh |

**PostgreSQL: locks, proof, and the reset.**

| Gate | Kind | The one assertion | The test, with its control | Withholds if it fails | Serves |
|---|---|---|---|---|---|
| **G-7a** | E | A session's advisory lock is held while that session runs `CREATE DATABASE`, also after its client is gone, and ends when the session does. | Kill the client during a long create; a second session's try-lock on the same key fails until the statement ends, then succeeds. | on PostgreSQL: every `copy` command that changes anything; `reset` of one database | 5, first and third |
| **G-7b** | E | The same key taken from another database does **not** conflict. | Hold it in `megasamples`; take it in `postgres`: granted. So every command must take it in one database. Control: taken twice in `megasamples`: refused. | nothing by itself: it fixes where the lock is taken. If the key did conflict across databases, the design is unchanged. | 5, first and third |
| **G-8a** | E | A database's comment is read by any role from any database, and set only by its owner or a superuser. | A reader reads a template's comment from `megasamples`. A namespace's owner sets one on a template: refused; on its own copy: accepted. | template records; rule 2's registered template; a copy's proof | 5, first, second and fifth |
| **G-8b** | E | A plain `DROP DATABASE` refuses while any session is connected to it. | An idle session connected: refused. Control: none connected: it succeeds. | on PostgreSQL: `copy drop`, `copy sweep`, and the reconciliation's drop of a transient | 5, first and third |
| **G-24p** | E | A database dropped and made again under one name has another OID. | Record, drop, create under the same name, compare: different. Control: after a restart, an untouched database's OID is the same. | the proof on PostgreSQL: `copy drop`, `copy sweep`, the reset's steps b and f | 5, second |
| **G-24w** | E | **Between a proof's check and the drop, no account but the object's owner and the administrators can put another object under its name.** | Pause after the check. On PostgreSQL: another namespace's owner, a declared account and `demo` each try to drop the copy and to create under its name: refused. On MySQL: the same accounts try to drop the schema, to drop its marker, and to create a schema under its name: refused. Control, on each: the copy's own owner can, and that is the stated limit. | `copy drop` and `copy sweep` on that engine | 5, second |
| **G-3a** | E | Closing a database to connections, and a row's update, commit or roll back together. | Roll back: the database accepts a connection **and the row is unchanged.** Commit: a new connection is refused **and the row reads the new phase.** | PostgreSQL's reset of one database | 5, third and eighth |
| **G-3b** | E | Two renames, a `CONNECT` grant and a row's update commit or roll back together. | Roll back: both names, the grant and the row are as before, each read. Commit: all four are changed, each read; a reader connects under the old name to the new database. | the same | 5, third and eighth |
| **G-3c** | E | A closed database keeps its sessions and refuses new ones; the superuser ends a session of `demo`'s. | One session open across the closing still answers; a new one is refused; the open one is ended. | the door and the session decision on PostgreSQL | 5, third; 2 (b) |
| **G-26p** | E | **A restore worker that outlives its lock holder changes nothing but its own transient.** | A database with no template. The coordinator takes the lock, writes the row, creates the transient, starts `pg_restore` into it, and is killed. While the worker runs: a reconciliation and a second admission are raced against it, as raw statements. Afterwards: the working database's checksums are unchanged; the first transient exists, with its recorded OID; the second reset made another. | **PostgreSQL's reset from the image** | 5, third and eighth |
| **G-9** | E | When the data volume fills during a copy, by each strategy, and during a reset before its swap: the server stays up, no part of the new database remains in the catalog, and every other database is whole. | A small volume; fill it; check the catalog and each database's checksums. | on PostgreSQL: `copy create`; `reset` of one database | 5, first and eighth |
| **G-32a** | E | **A session is told to be the product's own by its application name, and by nothing else.** | Through a bundled console: a person runs a statement and goes idle, with no transaction. Beside it: a connection that carries the reserved application name. The superuser's view tells the second from the first; **nothing in it tells the first from any other idle session of that console.** | ending any session without `--discard sessions` | 2 (b) |
| **G-32b** | E | With the stack up and nobody using a console, no console holds a session on an engine. | Each bundled console, started and left alone: the engines' session lists show none of theirs. | **the default itself:** if a console holds sessions by itself, every default reset would refuse. That returns to the deciders. | 2 (b) |

**PostgreSQL: the profile and the hook.**

| Gate | Kind | The one assertion | The test, with its control | Withholds if it fails | Serves |
|---|---|---|---|---|---|
| **G-5a** | E | On pull request #14's candidate, a role other than `demo` and `admin` cannot call an operator's function. | A fresh role runs `SELECT 1 = 1`: refused. Control: `demo` runs it: accepted. | P-1's reason. If the role can already, P-1 is still applied, and H-1 is recorded as not reproduced. | 5, fourth |
| **G-5b** | E | `pg_export_snapshot`, `pg_current_snapshot` and `pg_database_size` assign no transaction id and change no catalog row; a snapshot exported by one session is imported by another, both holding only the floor and the three. | The transaction id and a catalog digest before and after each; the import. | P-3, P-5 | 5, fourth |
| **G-5c** | E | A trigger's body runs with the rights of the account whose statement fired it. | A writer's insert fires a trigger that calls a built-in outside the floor: refused. With that built-in granted to the writer: accepted. | P-6; a declared writer | 5, fourth and seventh |
| **G-6a** | E | Natively, a role without `CREATEROLE` can change its own password, and cannot change another role's. | `ALTER ROLE` on itself: accepted. On another: refused. | nothing: it shows the hazard that rule 4 is for | 5, fourth |
| **G-6b** | H | With rule 4, that role cannot change its own password, its own settings or its own default privileges, and still reads. | Each of the three: refused. Control, same image: it reads a table; `admin` alters a role it made; and with the rule's library unloaded, the first three are accepted. | rule 4. **Only a failure to refuse the password change while it still reads selects 4.5's fallback.** | 5, fourth |
| **G-4a** | E | `REVOKE … FROM PUBLIC` on a new database, by a creator that is not its owner and does not inherit the owner's rights, leaves `PUBLIC`'s privileges in place and raises no error. | Such a creator creates `OWNER other`, then revokes; `PUBLIC`'s privileges are read. Control: the owner's own revoke removes them. | rule 1's reason. Whatever it shows, rule 3 confirms. | 5, fourth |
| **G-4b** | H | An error raised after `CREATE DATABASE` has copied its files leaves files with no catalog row. | A prototype hook that raises there; the data directory listed against the catalog. Control: no error, no leftover. | H-3's resolution, or the deciders | 5, fourth |
| **G-29a** | H | **The destination.** A namespace's owner is refused a database whose name is not exactly its own namespace's form. | As the owner of `lab`, with its source a registered template throughout: a name in `lab2`'s form; a name outside every namespace; the right prefix with another database's name; a token of eleven digits. Each refused. **Control: its own well-formed name: made.** | **PostgreSQL copies, here and from elsewhere.** Returns to the deciders. | 5, fifth |
| **G-29b** | H | **The source.** A namespace's owner is refused any source that is not a registered template. | With its name well-formed throughout: `template0`, `template1`, a working copy, another copy, and a closed template named `x_start` with no tag. Each refused. **Control: a registered template: made.** | the same | 5, fifth |
| **G-29c** | H | **The rename.** A namespace's owner is refused every rename of a database. | Its own copy, to a name inside and to a name outside its namespace: refused. Control: `admin` renames a database of its own. | the same | 5, fifth |
| **G-29d** | H | **Nobody else is bound.** A role that may create databases and owns no namespace creates and renames as PostgreSQL lets it. | Such a role creates a database outside every namespace, creates one under `lab`'s prefix, and renames its own: each accepted. The second is then reported as `unmanaged` by a plain catalog query of the namespace. | the claim that rule 2 binds namespace owners only | 5, fifth |
| **G-35p** | E | A PostgreSQL role with no password cannot sign in over any network rule the image has, while the container's own maintenance still can. | `admin` and `postgres`, each with a null password: from a second container on the stack's network, and through the published port: refused, by its error as an authentication failure. Inside the container, as today's wrapper connects: accepted. Control: with a password set, each signs in. | default 2 on PostgreSQL | 5, sixth |

**MySQL.**

| Gate | Kind | The one assertion | The test, with its control | Withholds if it fails | Serves |
|---|---|---|---|---|---|
| **G-10a** | E | `READ ONLY = 1` on a schema refuses every account's write. | A row change and a definition change, as a namespace's owner, `admin` and `root`: each refused. Control: with the option off, `admin`'s is accepted. | every MySQL template and copy | 5, first |
| **G-10b** | E | It is read by several `INSERT … SELECT` at once. | Two sessions copy from it together; both finish, with equal checksums. | the same | 5, first |
| **G-10c** | E | Changing the option needs `ALTER` on the schema. | `admin` changes it: accepted. A namespace's owner, with `SELECT` only: refused. | the claim that only an administrator can open a template | 5, first |
| **G-11a** | E | In a schema-level grant an escaped underscore is literal, and an unescaped one matches any character. | A grant on `a\_b`: `a_b` is read, `axb` is refused. A grant on `a_b`: both are read. | every grant the product makes on MySQL | 5, first, fourth, seventh |
| **G-11b** | E | A holder of 4.4's privileges on `P\_%`, with no grant option, can create, fill and drop inside it and nowhere else, and can grant nothing. | As the owner of `copy`: **create, fill and drop `copy_x`: each accepted.** Then a schema `copyx`, a working schema, a template, `megasamples`, another namespace's: create, alter and drop each refused. A `GRANT` on its own schema: refused. | MySQL namespaces; a MySQL owner's credential used away from the service | 5, first and fifth |
| **G-11c** | E | `demo`'s grants reach what they name and nothing else, **with a foreign namespace marked readable beside one that is not.** | With `fa` marked and `fb` not: `demo` reads each working schema and a schema `fa_x`; it is refused `fb_x`, `fax`, `mysql.user` and each template. | `demo`'s narrowing; declared readers and writers; `demo_reads` | 5, fourth and seventh |
| **G-13** | E | **A replayed definition belongs to the schema it was replayed into.** | A source with tables holding generated columns, foreign keys and full-text indexes; a view; a routine and a trigger that read and write a table; an event. Replayed into a second schema by a namespace's owner, **then a marked row is changed in the source only.** Each replayed view and routine returns the second schema's data, and a write through the second's trigger lands in the second. Run with the binary log on, and with it off. | MySQL copies of each dataset that uses a kind that fails | 5, first |
| **G-15a** | E | A named lock is held while its session runs a statement after its client is gone, and ends with the session. | Kill the client during a long statement; a second session's attempt fails, then succeeds when the statement ends. | on MySQL: every `copy` command that changes anything; `reset` of one database | 5, first and third |
| **G-15b** | E | `DROP DATABASE` waits on a transaction that has touched the schema, and gives up at the lock wait's end. | A transaction open on a table: the drop times out, and the schema's checksums are unchanged. Control: with none, it succeeds. | `copy drop` and `copy sweep` on MySQL | 5, first |
| **G-24m** | E | **A marker event made first in a schema is there exactly as long as that schema is,** and a schema made again under the same name within the same second, with the same tables, does not have it. | A namespace's owner creates the schema and the disabled event, with the scheduler off, and with the binary log on and off. Drop the schema and make it again at once with the same tables: the event is absent. Control: the untouched schema still has it after a restart. | the proof on MySQL: `copy drop`, `copy sweep`. With no proof no MySQL copy can be removed, so **MySQL copies are not offered.** | 5, second |
| **G-26m** | E | **From admission to the written outcome, a competing reset or reconciliation never changes a target that a live coordinator or worker holds.** | Raw sessions play each part: the coordinator with its lock, row and epoch; the worker's stream with its lock and its epoch check. **In each of five intervals** (after admission; after the suspension; while the worker loads; after it, before the check; before the regrant), **with the coordinator killed, with the worker killed, and with the server restarted,** a second admission and a reconciliation are attempted. **The second admission is refused every time:** by a lock while one is held, and by the unsettled row when none is. **The reconciliation is refused while either lock is held;** when it proceeds it has raised the epoch, and a worker's stream started after that stops at its second statement, with the schema's checksums unchanged. Control: with the epoch check removed from the stream, the late worker loads. | **MySQL's reset of one database** | 5, third and eighth |
| **G-27a** | E | A grant revoked from an account, with that account's sessions ended, leaves it unable to write the schema. | A writer with a session open: after the revoke alone, what the open session can still do is recorded; after its session is ended, a new session is refused the write. | MySQL's reset of one database, where a writer is declared | 5, third and seventh |
| **G-27b** | E | A revoked grant is still revoked after the server restarts. | Revoke; restart; the writer is refused. | the same | 5, third and seventh |
| **G-16** | E | Whether the pinned MySQL can refuse an account's change of its own password while that account still signs in. | Each statement that changes it, as `demo`; each mechanism that might refuse it; **and for each mechanism, `demo`'s sign-in from the probe's command, a console and a client.** All recorded by name. | nothing: it selects the branch of 4.5 | 5, fourth |
| **G-17a** | E | When the disk fills during a copy, the server stays up and every template and working schema is whole. | A small volume; fill it during the load; checksums of every other schema. | `copy create` on MySQL | 5, first |
| **G-17b** | E | When the disk fills during a load that has already dropped its schema, the server stays up, every other schema is whole, and a row that could not be written leaves the earlier phase readable. | The image's dump into a schema, the volume filled mid-load; then an update of the operation's row attempted while full. After space is freed, the load is run again and the schema's checksums are the image's. | MySQL's reset of one database | 5, third and eighth |
| **G-18a** | E | The shipped MySQL starts and passes its image tests with the binary log off. | That start. | the `binary_log` key: withdrawn, and the log stays on | 1 |
| **G-18b** | E | It does so with the log on, as shipped. | That start, on the candidate's image. | **nothing of this work:** a failure here is a defect of the image as it is, and returns to the deciders | 1 |
| **G-35m** | E | **Each privileged MySQL account, by each way in, cannot sign in while locked.** | `admin@'%'` and `root@'%'` over TCP from a second container and through the published port; `root@localhost` over the socket inside the container: each refused while locked. Control: unlocked, each signs in, **and `CURRENT_USER()` names the account that was meant.** With all three locked, the engine starts and `demo` signs in. | default 2 on MySQL | 5, sixth |

**Both servers, and SQLite.**

| Gate | Kind | The one assertion | The test, with its control | Withholds if it fails | Serves |
|---|---|---|---|---|---|
| **G-33a** | E | Each volume has an identity that survives a restart and is not the next volume's. | MySQL: with the baked directory holding no server identifier, each fresh volume's is its own, and the same after a restart. PostgreSQL: a row written on a first start is there after a restart and absent from a fresh volume. SQLite's container: a file written into its volume at a first start is there after a restart, and absent after the engine is recreated with its volumes renewed. | item 9's rule, on that engine | 9 |
| **G-33b** | E | **Nothing started against one volume changes the next.** | Pause a client between its read of the identity and its change, playing in turn a `copy` command, a reset's coordinator and a reconciliation; replace the volume; let it go on: its connection is dead and it changes nothing. Start a worker with the old operation's parameters after the replacement: PostgreSQL's `pg_restore` fails for want of its transient; MySQL's stream fails at its epoch check. **Then the new volume is read:** every schema's checksums and the catalog are as the image shipped them. Control: a stream with no epoch check loads into the new volume. | `copy` and `reset` commands on that engine, beside anything that replaces a volume. **Without it, `megasamples up --discard engine` and a whole engine's reset say that callers elsewhere must be stopped first.** | 9 |
| **G-19a** | E | On the filesystems a copy is made on, a bind mount shared by a host and a container among them: exclusive creation and a hard link each fail when the name exists, and two racing publications leave one winner. | Two processes, one on each side of the mount. | every SQLite `copy` command | 5, first |
| **G-19b** | E | **A file moved aside and compared with a retained link is this copy's exactly when they are one file;** and while the link is kept no other file has its inode. | Replace the final name with another file; move aside; compare: different, and it is put back without overwriting. Remove the final name and make a thousand files: none is the retained link's file. Control: an untouched copy compares the same. | the proof on SQLite: `copy drop`, `copy sweep` | 5, second |
| **G-19c** | E | When the destination fills while a file is staged beside its final name, or while a small record is written beside it, no final name holds a file that is not whole. | A small filesystem, filled at each step of: a copy's publication by hard link; a sidecar's write; a reset's staged file renamed over a working file; an operation's file renamed into place. Each final name is absent, or holds its earlier content whole, or the new content whole, by SHA-256. | SQLite `copy create`; SQLite's reset of one database | 5, first and third |
| **G-20** | E | A `flock` held by one process is seen by another across the host and a container on one mount, and a lock file replaced after it was opened is detected. | Two processes; a replaced lock file. | every SQLite `copy` command that changes anything | 5, first |

**Not gates.** Round 4's G-12 withheld nothing: whether a grant outlives its schema's drop only decides whether the reset's regrant repairs or confirms, and T-5 observes it. G-21 needed the package, and is T-28. G-32m had no consumer: every MySQL reset of one database needs `--discard sessions`. What the start wrapper decides about a configured value is T-23. Whether a deployment's clients look different to its servers, and what an account that manages accounts can do, are a deployer's own to observe.

### 8.2 Regressions

Revised after the gates have run. Every red asserts the outcome that is wanted, and fails on the commit before its change because that outcome is not yet there. Every row has a reversal that changes the very assertion it plants a fault for.

**The native entry point.** A native test runs only against **an explicitly provisioned, task-owned, disposable target,** named to it: its project, its store and its ports. It verifies that the target carries the marker its provisioning wrote, and refuses one without it. It names no machine and no path. Its own tests: a shared target is refused; a second isolated one is accepted.

| # | The outcome asserted | Its reversal | The class it covers |
|---|---|---|---|
| T-1 | **A template is closed, as its engine closes it.** PostgreSQL: every account's connection is refused. MySQL: every account's write is refused; `demo` and a declared account have no privilege on it; a namespace's owner and the administrators read it. | PostgreSQL: built with connections allowed. MySQL: the option left off. | Every templated database; every account; each engine's own expectation. |
| T-2 | **Nothing an ordinary account does changes a template.** PostgreSQL: `admin`'s alteration is refused. MySQL: a namespace's owner's is refused; `admin`'s change of the option succeeds, and is the stated limit. | The template made `admin`'s; the owner given `ALTER` on it. | Rename, owner, flags, drop, comment, grant; a row change; the option. |
| T-3 | **No defined prefix overlaps anything, and a scope that names a defined namespace is accepted.** `oracle` as a namespace or as a foreign namespace does not build; a reader with the scope `copy` does. **A declared account whose key would be another account's does not build.** | Each check removed in turn; the reference check made to refuse `copy`. | Database names, templates, `megasamples`, engine schemas; adjacent prefixes such as `lab` and `lab2`; a scope that names nothing; the names `mysql_root`, `mysql_demo`, `demo` and `admin`; two declared names with one key. |
| T-4 | **The reach tables of 4.7,** cell by cell. | One fault for each column. | Every account against every kind of database, for connect, read, row write, definition change, drop and grant; a right held directly and through an inherited role. |
| T-5 | **Declared grants are in force after a start and after each reset:** a declared writer changes a working row after its copy was reset. | The reset's grant step removed; the start's. | Both engines; every reset path; an account declared no longer, locked at the next start; **a server restarted during an unsettled MySQL reset, whose suspended writer stays shut out.** It also records whether a MySQL grant outlived the drop. |
| T-6 | **A declared writer writes rows of working copies and nothing else:** it is refused a definition change, a copy, the registry, a template. | The write grant put in the template. | Both engines; a reader of a namespace and of the working copies at once. |
| T-7 | **The hook's four rules,** through the built image. | Each rule removed in turn; the library not loaded. | G-4a, G-6b and G-29a to G-29d as regressions; every command that makes a routine, by each kind of creator; a second session that never sees a new database open. |
| T-8 | **The routine floor is the list, for every role.** | The list granted to `demo` alone. | `demo`, a fresh role, a namespace's owner, a declared reader and writer; every kind of database; an exported snapshot imported by a second session. Pull request #14's own cases, kept. |
| T-9 | **MySQL's grants reach what they name and nothing else.** | One underscore left unescaped; `demo`'s grant on `*.*` restored. | G-11b's and G-11c's cases through the built image. |
| T-10 | **A copy's access is exactly what its engine's design says.** **PostgreSQL:** the copy's database privileges are its owner's and `CONNECT` for its namespace's read group, and nothing else. **MySQL:** no entry in the grant tables names the copy's schema. | PostgreSQL: a `CONNECT` grant to `PUBLIC` planted in the create: the assertion reads the database's privileges, and fails. MySQL: a grant on the copy's name planted: it reads the grant tables, and fails. | Both engines; a create that is interrupted; **a name forced to repeat, with a hand-made grant left on it:** the product reports no claim about the copy's writers. |
| T-11 | **A MySQL copy is the dataset:** its own verification passes against a copy (`SM:ARCHITECTURE.md:239-249`). | The foreign keys' replay skipped; one view left pointing at the template. | Every templated database; the two exclusions; the marker event present and reported. |
| T-12 | **The contract:** one document; each exit's promise checked on the server; each reader rule. | A second line; a changed code; an unknown member rejected. | Every command by every outcome of 3.3. `--json` with two targets: exit 2. An operation's identity given twice: exit 5. |
| T-13 | **A reset signs in with the file's value when another is exported,** for its coordinator and for its worker. | Today's reader put back. | Each key; a canary password in no argument, output or log, nor taken from the CLI's environment. |
| T-14 | **An interrupted create is kept, and what is expected depends on where it stopped.** **Killed before the exclusive creation:** there is no object; the row is `stale` and is removed. **Killed after it, at each later phase:** the object is there, `copy list` reports it `interrupted`, and no command removes it. | Recovery made to remove an `interrupted` object; `stale` made to keep its row for ever. | Each phase, each engine; an occupied name; a `ready` object replaced outside the CLI, kept as `inconsistent`; a MySQL schema made again within the second, without its marker. |
| T-15 | **Every command against every command,** pairs generated from section 0's commands and every reset path and scope. **Its invariants, for each operation:** a sweep removes nothing inside its lease; an owner's own drop may remove its leased copy; no working copy is lost or left closed by a completed command; nothing is present that `copy list` or `reset --status` does not show. | Each guard removed in turn. | Natively, with the first paused at each durable phase; and by gated fakes. |
| T-16 | **A reservation is atomic:** forty creates into a namespace of 32 give exactly 32. | The count taken outside the lock. | Creates that fail and keep their place, as 2.2 has it. |
| T-17 | **A sweep removes only what 2.2 allows:** a copy renewed between its look and its removal is kept. | Each condition removed in turn. | Each reason a copy is kept. **The stated limits:** an idle MySQL session and an open SQLite file, past their lease, shown unprotected. |
| T-18 | **The build reports each template's allocated bytes,** appended datasets included. | The appended tables left out of the measure. | Each templated physical database; a copy's time by each strategy. |
| T-19 | **One unsettled operation for each target:** B is refused while A is unsettled, and A's reconciliation changes only what A made. | Admission made to ignore an unsettled row. | Each path; G-26m's and G-26p's intervals through the CLI; `--status` on the same volume and on a replaced one; several targets, one of which would be refused: none is changed. |
| T-20 | **A worker that outlives its coordinator still excludes the next reset, or touches only its own transient.** | The worker's lock removed; its epoch check removed. | Both server engines. |
| T-21 | **A reset of a database preserves sessions unless told otherwise.** | The default made to disconnect; a console's idle session made disposable. | Each path; a person's idle session, directly and through a console; a connection with the reserved application name; `--unattended` on MySQL and SQLite, refused; a MySQL and a SQLite reset without `--discard sessions`, refused; **`make reset` and every validation script that calls it (F-33), as migrated; a search of the repository for a call that lacks the option its target needs.** |
| T-22 | **Nothing replaces an engine's volume without `--discard engine`.** A whole engine's reset without it, and with `--discard sessions`: refused. **`megasamples up` with a stale image and a live copy: refused before anything is recreated;** with `--discard engine`: replaced. | Either refusal removed. | Each engine; an engine not yet started, which `up` simply starts; a `copy` command begun on the old volume, which changes nothing in the new one. |
| T-23 | **No privileged password is published or shown,** on any path that starts an engine. **The landing page and the Adminer page, fetched with no sign-in, do not hold a canary set as `admin`'s password.** | The value's test removed; a page made to print it; a stale page left in place. | G-35p's and G-35m's cases through the built images; a privileged key set to the published value, leaving its account locked; `megasamples up` writing each missing key; no console offering anything privileged; **no configuration making the generator publish a port wider than loopback.** |
| T-24 | **SQLite:** a truncated copy is not published; a replaced file is not dropped; adjacent files are left and reported. | The hash check removed; the move-aside removed. | Create, drop, sweep; a manifest that disagrees; a sidecar one format back, kept. |
| T-25 | **Passwords:** PostgreSQL refuses `demo`'s change of its own. MySQL: what G-16 established, as a case that fails if the engine's answer changes. | Rule 4 removed. | Each account without `CREATEROLE`; a cleared key locking its account at the next start. |
| T-26 | **An installed dependency group is not reset singly.** **First, on today's path, it shows the harm:** a row added to `oracle_oe`, then `oracle_hr` reset alone, leaves a key with no parent. [108+] Then: the reset is refused, and after a whole engine's reset every key holds. | The refusal removed. | A MySQL with both; one with `oracle_hr` alone, which resets singly. |
| T-27 | **The general upgrade route, rehearsed:** images replaced, the old volumes kept, and back. | A step removed from the route: its test fails. | PostgreSQL's refusal of data without the policy's marker. |
| T-28 | **The package installs with the two drivers alone,** on each supported Python, and `uv sync --locked` is unchanged. Psycopg's licence is reviewed first. | A pipeline dependency imported by a `copy` module. | One `copy list` from that install, with no container runtime. |

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
5. **The general upgrade route** (5.3).
6. **Visuals where they help.**

**What version 1 fixes:**
7. **The model, with a picture:** a template, a working copy, a test copy and a reset; and how the three engines differ, MySQL's reset from the image among the differences.
8. **Which databases have a template,** per engine, with measured sizes and times; that version 1 bounds no storage, and what it promises when a disk fills (2.6).
9. **Namespaces:** what a prefix is, why it may not overlap, a foreign namespace.
10. **A copy's life:** issued, ready, leased, renewed, released, swept. That an interrupted create is kept, and how an administrator removes one. That the lease is the protection, and the two cases past it. **That a MySQL copy holds one marker event.**
11. **The commands,** each with one example and its JSON; the identity on `drop`, `renew` and `release`.
12. **The exit codes,** both tables, and what a script does on 8.
13. **Credentials:** the two routes for `copy`; the keys; that privileged passwords are private and where `megasamples up` writes them; what a console and a page show.
14. **The accounts,** as 4.7's tables. It replaces today's two-row tables (`SM:README.md:120-123`, `:247-255`).
15. **Declared readers and writers.**
16. **The read profile on PostgreSQL,** and its limit. It replaces the sentence that `demo` "still has `TEMPORARY`" (`SM:README.md:163-167`).
17. **5.1's table of start paths, and 5.2's table, whole.** How to hand a credential over: one, alone, never the `.env`. [108-11]
18. **The impact note of 5.4, whole,** with each migration.
19. **What is not claimed:** a sweep protecting a copy past its lease; that a copy has had one writer; a copy owner's credential away from the service before its gates; any bound on storage; a wider listener, or any refusal of one on an image run by hand; MySQL as a strict read profile; MySQL refusing a password change, unless G-16 finds it does; TLS.
20. **Resets:** each path and its option, the session decision, `--discard sessions` and `--discard engine`, operations and their identities, one target for each scripted call, `--status` and `--reconcile`.
21. **The contract and the formats.**

**What leaves the README:** the dated account of one deployment (`SM:README.md:16-20`) and the paragraphs that take LAN forwards for granted (`:258-270`). [108-3]

## 11. What waits, and in which stage

Each is new work with a brief of its own, added under section 6's rules. [108-4] [108-6] The fuller design at `e0c2f935` is the source for each.

**Every deferred finding is listed against its stage, by review and number,** so that the lines register can carry it. [D: review 4's finding 21.] "R3-14" is review 3's finding 14.

| Stage | What waits in it | DL-108 | Deferred findings |
|---|---|---|---|
| **S-1 · Exposure** | `network.bind`, `administrators.allow_from`, `whoami`. The approved default that a wider listener is refused while an account keeps a published password, or until administrators' origins are set, and that a console with stored administrator access or anonymous use is refused a wider bind. The profiles of a shared server, a container platform and remote access. A map from account keys to mounted secret files. | 2 (a), 6 | **R3-1** (the wider-listener check); **R3-2** (wider publication of a console); **R3-14** (the map to mounted files); **R4-10** (what is enforced on an image run by hand); **R2-13** (origins for administrators) |
| **S-2 · Enrollment at run time** | The enrollment commands, their record, its replay and its repair. `accounts check`. A writer of a copy that is not its owner, and the per-run writer boundary a result would need. | 6 | **R3-6** (repair during a reset); **R3-10** (a per-run writer boundary); **R3-17** (one authority for run-time enrollment); **R2-7** (the grant audit); **R2-8** (admission of an existing role by its effective privileges); **R4-16** (effective write access to a copy, established by the product) |
| **S-3 · Storage admission** | Headroom reserved across an engine; a recovery reserve; inputs for an image reset, an off-host file and a retained log. | 6 | **R3-15**; **R2-12** (admission across namespaces) |
| **S-4 · A remote image worker** | A reset asked for from anywhere but where the service runs. | 6 | **R3-13** |
| **S-5 · `copy hold`** | Holding a copy past its lease; a holder's own identity; protection of active copies, holds and sessions across a replacement of a volume, with a drain. | 8, 9 | **R3-5** (protection and drain); **R3-11** (a drop against a hold); **R2-9** (the hold's handshake) |
| **S-6 · MySQL's reset from a template** | The reset itself; writers shut out through it; a group of databases that refer to each other, reset and recovered as one; an unattended route for MySQL. | 10 | **R3-6** (the template path's exclusion); **R3-16** (a group's recovery); **R2-11** (definers restored on a reset); **R4-20** (a reset of one of a group without the whole engine) |
| **S-7 · `accounts export`** | One credential handed over with a value-free receipt; an optional custody record. | 1, 11 | — |

## 12. The reviews' findings

### 12.1 Review 4's findings, each answered

| # | Finding | What changed | Where |
|---|---|---|---|
| 1 | **P1 · The landing pages still disclose the administrator credential.** | Neither generated page prints a privileged password, and neither generator reads one. `megasamples up` removes pages generated before. T-23 fetches both pages with no sign-in and looks for a canary. | 5.1; F-31; T-23 |
| 2 | **P1 · G-26m starts too late.** | The coordinator holds the target's lock from before admission until after the outcome is written. The worker holds a second lock, and is fenced by an epoch that a reconciliation raises first. Admission and reconciliation need both locks. G-26m rehearses five intervals, each with the coordinator killed, the worker killed and the server restarted. G-27b adds the restart to the suspension. A failure withholds MySQL's reset of one database. | 3.5; G-26m, G-27a, G-27b; T-5, T-19 |
| 3 | **P1 · The PostgreSQL image worker has lost its gate.** | G-26p is back: a database with no template, the lock holder killed while `pg_restore` runs, a reconciliation and a second admission raced against it, and the working database and both transients verified. A failure withholds the reset from the image. | 3.5; G-26p |
| 4 | **P1 · G-33 never tests a command crossing the replacement.** | G-33b pauses a client between its read and its change, replaces the volume, starts a worker late, and then reads the new volume for any change. The design says why nothing can cross: a command never reconnects; a worker is fenced by its transient or its epoch; a reconciliation reads its operation on the connection it changes with; where the service runs, one lock file covers both. The service's SQLite files carry an identity file in their volume; a caller's own SQLite directory belongs to no volume, and its documents say null. | 3.5; 2.5; 3.2; G-33a, G-33b; T-22 |
| 5 | **P1 · A retained command can replace a whole engine without the discard decision.** | `megasamples up` replaces nothing when an image is stale: it refuses, exit 5, before it recreates anything, unless it is given `--discard engine`, as the deciders settled it. T-22 runs it with a stale image and a live copy. | 3.5; 5.3; 5.4; F-32; T-22 |
| 6 | **P1 · The cleanup gates do not establish identity at deletion.** | MySQL's proof by creation times is withdrawn, for a marker event made first in the schema, which a schema made again in the same second lacks (G-24m). PostgreSQL's reset records the working copy's own OID at admission and drops the old transient only by it. SQLite's drop moves the file aside before it compares, so what is compared is what is removed; adjacent files are left and reported. G-24w tests the boundary itself: who can put another object under the name between the check and the drop. | 2.2; 3.5; G-24p, G-24m, G-24w, G-19b; T-14, T-24 |
| 7 | **P1 · G-32p cannot tell a person's idle console session from the product's.** | Only a session that carries the product's reserved application name is ended without the option. Every other session, a console's included, is a person's and is preserved. G-32a tests a person idle through a console beside such a connection; G-32b tests whether consoles hold sessions with nobody there, which would return to the deciders. | 3.5; G-32a, G-32b; T-21 |
| 8 | **P1 · A declared reader's key can be a superuser's key.** | The whole inventory of derived keys is checked when the configuration is read: no two alike, and none one of the five reserved. T-3 tries `mysql_root` and `mysql_demo`. | 3.4; 4.6; T-3 |
| 9 | **P2 · The confinement gates have the wrong boundary and incomplete controls.** | G-29 is four: destination, source, rename, and that nobody else is bound; each refusal has a successful control beside it, and each isolates one cause. A failure withholds PostgreSQL copies altogether, not only their use from elsewhere. **The restriction on other creators is removed:** rule 2 binds a namespace's owner only. G-11b now creates, fills and drops inside its pattern before it is refused outside. | 4.3; G-29a to G-29d; G-11b |
| 10 | **P2 · The wider-listener default is deferred without a boundary of supported start.** | 5.1 says which start paths the product controls and what it enforces on each. On an image run by hand the publisher is the deployer; the product says so, and that `demo`'s password is published. T-23 checks every path the product controls. **The exception to DL-108 item 2 (a) is returned to the deciders,** below. | 5.1; 5.2; T-23 |
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

**The deciders on this record's three readings** [108+]:
- **No `template` and no `interface` command:** accepted.
- **`engines.mysql.binary_log` in version 1:** accepted.
- **Both narrowings accepted, each in the impact note:** a dependency group resets through the whole engine; a SQLite reset needs its discard. T-26 first shows the broken key on today's path.
- **`--discard` takes a named value:** `sessions` for a database's reset, `engine` for a volume's replacement; a whole engine's reset refuses the first; `megasamples up` asks the second.

**Returned to the deciders:**
- **DL-108 item 2 (a), on an image run by hand.** The approved default refuses a wider listener while an account keeps a published password. The product cannot see how a hand-run image's port is published, and `demo`'s password is published by item 5. Version 1 documents the exposure there instead of refusing it (5.1). Whether that is the intended reading is theirs.

**Not settled here:**
- **The exact file list of the runbook's split** (5.3).
- **What the gates will show.** Each has its consequence written; none is assumed.

### 12.2 Review 3's findings, each mapped

As round 4 mapped them, with what round 5 changed. Every finding is answered first by removing or narrowing a claim, and is **closed in version 1** only where every entry point version 1 keeps avoids the hazard. [108-7]

| # | Finding | Where it goes | How |
|---|---|---|---|
| 1 | **P1 · The exposure defaults trust everyone who can reach loopback.** | **Version 1,** for privileged accounts. The wider-listener check: **S-1.** | No privileged account has a usable published password on any start path (5.1). G-35p, G-35m; T-23. |
| 2 | **P1 · An exposed console gives administrator access.** | **Version 1.** Wider publication of a console: **S-1.** | No console holds, and no page prints, a privileged password (5.1). T-23. |
| 3 | **P1 · Clean-up authorizes deletion without proof.** | **Version 1.** | An interrupted create is never removed. Each engine's proof is checked at the removal (2.2). G-24p, G-24m, G-24w, G-19b; T-14. |
| 4 | **P1 · A new reset can overtake an unsettled one.** | **Version 1.** | One unsettled operation for each target; both locks; the epoch (3.5). G-26m, G-26p; T-19, T-20. |
| 5 | **P1 · A whole engine's reset can destroy an active copy.** | **Version 1, as DL-108 item 9 has it.** Protection and drain: **S-5.** | `--discard engine`, for the reset and for `up`; the volume's identity (3.5). G-33a, G-33b; T-22. |
| 6 | **P1 · MySQL enrollment repair can reopen a database during reset.** | **Version 1,** on the image path. Repair: **S-2.** The template path: **S-6.** | No repair command. A recorded suspension that a restart keeps; `done` needs the data and the grants (3.5). G-27a, G-27b; T-5. |
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
| 18 | **P2 · Several gate fallbacks retain the failed prerequisite.** | **Version 1.** | 8.1, as round 5 has it. |
| 19 | **P2 · The regression matrix has impossible expectations.** | **Version 1.** | T-1, T-2, T-10 and T-14, each with its engine's or its phase's own expectation. |
| 20 | **P2 · The native-test plan assumes one machine.** | **Version 1.** | A named, task-owned, disposable target (8.2). |
| 21 | **P2 · The rollout cannot pass its account check with locked spares.** | **Version 1,** in the profile. | Verification follows each account's effective state (7.2). |

**Rounds 1 and 2** are answered in this file's history: round 1's findings at `bdd9033`, round 2's at `e0c2f935`. Section 11 lists those that wait.
