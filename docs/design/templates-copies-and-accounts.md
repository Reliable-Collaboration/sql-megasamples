# Templates, copies, the scripting CLI and the account model: design

**Design record · 2026-11-20 · round 3, the drafter's part. Status: a design under review. Nothing here is built, and nothing here has been run.**

- **What this is.** The design of sql-megasamples' pristine templates and per-test copies, the commands that scripts drive them with, and the account model of both server engines. It carries the strict PostgreSQL read profile of pull request #14.
- **What sql-megasamples is.** A stand-alone offering: sample database servers that someone spins up, in any network setting. [R: `DL:` DL-107] **Sections 2 to 6 describe that product,** and assume nothing about where it runs or who uses it. A particular deployment is configuration; section 7 gives examples, and DataIntent's development instance is one of them.
- **Rounds.**
  - Round 1 is `2a15387`. Astra's review 1 found two P1s, fourteen P2s and a P3.
  - Round 2 is `bdd9033`, with `9fe0bbd`. Astra's review 2 found four P1s, sixteen P2s and a P3. The two deciders answered its questions in DL-106.
  - The owner then found that the design, and DL-106 with it, had mixed the product with one deployment's policy (DL-107), and returned DL-106 to the deciders to be separated.
  - Round 3 is this. Every finding of both reviews is fixed here, under DL-101; section 13 answers each by number. Section 11 proposes where each of DL-106's decisions belongs. The reviews are in the coordinator's ignored `.local/megasamples-design/` in DataIntent.
- **Authority.** The owner's DL-076, DL-077, DL-078, DL-101, DL-103, DL-104, DL-105 and DL-107. The two deciders' DL-079, DL-085, DL-087 and DL-106. The lines register's lines 2, 4, 10 and 16.
- **Method.** Reading only: no container, no database connection, no network, and no credential file. So no statement about how an engine behaves has been observed.
- **Marks.** Each claim carries one:
  - **[R]** read in the cited file and line;
  - **[G-n]** rests on a native behaviour nobody has shown. It is feasibility gate *n* of section 8.1, which the build passes before anything is built on it. It is not asserted either way; the gate names every command that depends on it and what those commands do if it fails;
  - **[I]** inferred, and not load-bearing;
  - **[D]** decided here, with the reason;
  - **[106-n]** carries item *n* of DL-106, at the level section 11 proposes for it. **The deciders confirm or change that placement** (DL-107 item 4); until they do, it is a proposal.
  - A table or list whose heading line carries a mark is marked as a whole. A file and line cited inside any row is **[R]**.
- **Citations.**
  - `SM:` is sql-megasamples at `main`, `e61335f`.
  - `PR14:` is its branch `fix/strict-read-account` at `2879fc4`.
  - `DL:` is DataIntent's `docs/work/decision-log.md` at `d02f7384` (`origin/coordinator/journal-during-full`), and `LR:` is `docs/work/lines-register.md` there. DL-104 to DL-107 and `docs/bootstrap/approvals.md`'s MEGASAMPLES-ROLLOUT-2 were read on that branch at `6ac5373c`.
  - `ED:` is DataIntent's `docs/work/samples-service-editing-requirements.md`, `MR:` its `docs/work/samples-service-requirements-and-architecture.md`, and `DI:` any other DataIntent file, all at `4a8aad61` (`origin/coordinator/samples-p1`).

## 0. Summary

**The product** (sections 2 to 6):

| Area | What the design says |
|---|---|
| **Names** | `<database>_start` is the template and `<database>` the working copy. A test copy is `<prefix>_<database>_<token>`: **the CLI issues the token, and no name is ever used twice.** |
| **Namespaces** | A prefix is a namespace with one owning account, set in the configuration and baked into the image. No namespace may overlap anything else, a consumer's own declared namespace included. |
| **Lifecycle** | Every copy has an identity, a durable record with its phase, a physical proof of what it is, and a lock held on the server for each whole change. Every command that changes a copy names the identity it expects. Nothing is removed that cannot be proved. |
| **PostgreSQL** | The template accepts no connections and is the superuser's. A copy is `CREATE DATABASE … TEMPLATE`. Both reset paths build the new working copy beside the old one and swap them in one transaction. |
| **MySQL** | The template is a schema set `READ ONLY`. A copy is logical and runs inside the server. A reset cannot be undone after its drop, shuts ordinary writers out while it runs, and is checked by checksum. |
| **SQLite** | The template is the image's file, staged read-only with a manifest. A copy is a verified, exclusive file publication, proved by its inode. |
| **The CLI** | `template`, `copy`, `reset`, `accounts`, `whoami` and `interface`. One JSON document on standard output, nine exit codes whose promise each command defines, operation identities with kept outcomes, and every password resolved once from a private file or standard input. |
| **Accounts** | Reading is one group everywhere. **Writing is granted inside each database, to that database's own scope,** so enrollments cannot combine. Enrollment is recorded, replayable, and admitted by what a role can do in effect. |
| **Safe defaults** | Every listener on loopback. A wider one is refused while any account has its published password, or while the deployer has not said from where administrators may sign in. Copy owners locked until keyed. Nobody enrolled to write. No administrator's credential exported. A reset discards nobody's session unless told to. |
| **Exposure** | What a deployer weighs, and each mechanism the product gives for it: section 5.3. |
| **The contract** | Versioned, each persisted format with its own tag, fixed at the merge: section 6. |

**The work** (sections 8 to 10): thirty-one feasibility gates before anything is built on them; pull request #14 folded into the branch; the README product-first.

**One deployment, as an example** (section 7.5): DataIntent's development instance, with its configuration, its custody of credentials, and its rollout.

**Three findings that change pull request #14's content** (section 4.3), each a gate before it is a fix:
1. **Roles other than `demo` and `admin` can call no built-in routine,** not an operator's function nor a cast's, and `admin` cannot grant them back. That reaches every role a deployer or a consumer makes. [G-5]
2. **The hook may leave a new database open to `PUBLIC` without failing,** when the creator is not the new database's owner. [G-4]
3. **The allow-list refuses built-ins that an ordinary reading client needs:** `pg_export_snapshot()`, `pg_current_snapshot()` and `pg_database_size()`. One consumer is known to call all three (F-17). [R]

## 1. What the design rests on

### 1.1 The product, as it is today

| # | Fact | Where | Mark |
|---|---|---|---|
| F-1 | **Every command of today's CLI that contacts a running engine does it through `docker exec`.** The reset starts a second container of the running image, and pipes a dump from it. So none of those works without a container runtime. | `SM:megasamples/credentials.py:29-70`; `SM:megasamples/reset.py:156-197`, `:245-304` | [R] |
| F-2 | **The CLI's output is text for a person,** and a command returns 0, 1 or 2. An unknown command is 2. | `SM:megasamples/cli.py:68-82`; `SM:megasamples/reset.py:384` | [R] |
| F-3 | **Resets exclude each other by a lock file** for one user on one host. Resets from other hosts "must be coordinated separately". | `SM:megasamples/reset.py:101-116`; `SM:README.md:323-325` | [R] |
| F-4 | **PostgreSQL's reset of one database drops it with force, and only then restores it,** with `pg_restore --create`. MySQL's pipes a dump that drops and reloads the schema in place. | `SM:megasamples/reset.py:254-262`, `:294-299` | [R] |
| F-5 | **Accounts today.** PostgreSQL: `admin` has `CREATEDB` and `CREATEROLE` and owns each sample database and what is in it; `demo` has `SELECT` on the tables. MySQL: `admin` and `root@'%'` hold all privileges with the grant option; `demo` holds `SELECT, SHOW VIEW ON *.*`. | `SM:engines/postgres/init/00-users.sql:10-12`; `SM:engines/postgres/init/20-grants.sql:4-7`; `SM:engines/postgres/Dockerfile:43-55`; `SM:engines/mysql/init/00-users.sql:9-19` | [R] |
| F-6 | **Each health probe signs in as `demo`** with a password file written at start. Passwords are applied at each start from the environment. phpMyAdmin reaches MySQL from its own container, as `demo` and as `admin`. | `SM:megasamples/engines/postgres/__init__.py:80`; `SM:megasamples/engines/mysql/__init__.py:139`; `SM:engines/postgres/entrypoint-wrapper.sh:17-35`; `SM:engines/mysql/entrypoint-wrapper.sh:19-40`; `SM:consoles/phpmyadmin/config.user.inc.php:12-19` | [R] |
| F-7 | **The registry has one row per database,** with a build id that is `dev` unless `MEGASAMPLES_BUILD_ID` is set. | `SM:megasamples/registry.py:52-88`, `:111` | [R] |
| F-8 | **A large configuration is large.** One, of 33 datasets in 30 physical databases, bakes 22.712 GiB on MySQL, 20.902 GiB on PostgreSQL and 17.862 GiB of SQLite files. | `SM:docs/live-upgrade-runbook.md:97`, `:101-105` | [R] |
| F-9 | **Sizes on record are old, and of two kinds.** PostgreSQL's data directory was 2.6 GB for the 21 core databases. MySQL's was 1,785 MB for 22 on 2026-09-03, which was 1.9 times their logical size. Neither counts a dataset that appends to a core database. | `SM:ARCHITECTURE.md:170-171`; `SM:knowledge/decisions/tier-assignments.md:65-88` | [R] |
| F-10 | **MySQL's binary log grew to 10.9 GB** after a rehearsal of logical resets. The build server runs without one; the shipped server's configuration does not turn it off. | `SM:docs/live-upgrade-runbook.md:109`; `SM:megasamples/engines/mysql/server.py:74`; `SM:engines/mysql/my.cnf:1-11` | [R] |
| F-11 | **One dataset reaches into another database:** `oracle_oe` depends on `oracle_hr`. | `SM:datasets/oracle_oe/dataset.yaml:8`; `SM:README.md:212` | [R] |
| F-12 | **Pull request #14** revokes `TEMPORARY` and routine `EXECUTE` from `PUBLIC` in every database and both templates, grants `admin` what it had, and grants `demo` an allow-list. A compiled hook closes `TEMPORARY` on each new database. An event trigger closes `EXECUTE` on each new routine. | `PR14:engines/postgres/init/10-read-profile.sql:4-35`; `PR14:engines/postgres/read-policy/read_policy.c:29-40`; `PR14:engines/postgres/read-policy/read_policy--1.sql:1-20` | [R] |
| F-13 | **Its grant to `admin` carries no grant option.** | `PR14:engines/postgres/init/10-read-profile.sql:10-13` | [R] |
| F-14 | **Its evidence:** 254 native cases Passed on an isolated stack; 1,663 signatures stay executable by `demo`; MySQL is not claimed strict, and `demo` there can take a named lock. | `PR14:docs/strict-read-evidence.md:16-18`, `:30` | [R] |
| F-15 | **It merges into `main` without conflict,** and shares no file with what `main` has gained since its base, `2cf1f3e`. | `git merge-tree origin/main fix/strict-read-account`; the two diffs' file lists against `2cf1f3e` | [R] |
| F-20 | **Each server accepts every account from every address that reaches its port.** PostgreSQL's rule is `host all all all scram-sha-256`. Every MySQL account but one of `root`'s is `@'%'`. | `SM:engines/postgres/Dockerfile:33`; `SM:engines/mysql/init/00-users.sql:9-18` | [R] |
| F-21 | **Three datasets append to a core database:** `nyc_taxi_yellow` to `nyc_taxi`, `chicago_crimes_full` to `chicago_crimes`, and `dvdstore_reviews` to `dvdstore`. | `SM:datasets/nyc_taxi_yellow/dataset.yaml`, `SM:datasets/chicago_crimes_full/dataset.yaml`, `SM:datasets/dvdstore_reviews/dataset.yaml`; `SM:knowledge/decisions/tier-assignments.md:32-62` | [R] |
| F-22 | **The reset reads its passwords in the host's own process,** by a reader under which an exported value wins over the file's and a value in the file may be expanded from the environment. | `SM:megasamples/reset.py:246`, `:290`; `SM:megasamples/config.py:155-167` | [R] |
| F-28 | **Every port binds to `127.0.0.1`,** and the file that says so is generated: an edit to it is rewritten by the next `make up`. Passwords have published defaults, "committed on purpose". | `SM:megasamples/compose.py:10-11`, `:30-31`, `:40`; `SM:megasamples/engines/postgres/__init__.py:76`; `SM:megasamples/engines/mysql/__init__.py:135`; `SM:.env.example:5-9` | [R] |
| F-29 | **The README and the runbook already hold one deployment's story:** a dated account of "the maintained deployment", its LAN forwards, and a runbook headed "coordinator only". | `SM:README.md:16-20`, `:258-270`; `SM:docs/live-upgrade-runbook.md:1-3` | [R] |

### 1.2 One consumer, DataIntent

These are facts about one consumer. The product sections cite one only where it shows a need any consumer could have. Section 7.5 is where they are used.

| # | Fact | Where | Mark |
|---|---|---|---|
| F-16 | **Its fixture** makes `di_reader` and `di_analyst` as `admin`, makes each `di_…` database from `di_template`, `template1` or `template0`, and closes it to `PUBLIC` itself. The superuser makes `di_template`. Leased logins are `di_login_` and 32 hexadecimal digits. | `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureServer.cs:27-32`, `:131-134`, `:224-230`, `:403-409`; `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureRoles.cs:11`, `:69-71` | [R] |
| F-17 | **Its provider, as a read account,** lists databases `WHERE NOT d.datistemplate`, and calls `pg_database_size(oid)` for those it may connect to. It calls `pg_export_snapshot()` and `pg_current_snapshot()` when it takes a snapshot, and imports that snapshot in another transaction. | `DI:src/DataIntent.Adapters/Postgres/PostgresSourceServer.cs:237-240`, `:347`; `DI:src/DataIntent.Adapters/Postgres/PostgresSnapshot.cs:136` | [R] |
| F-18 | **Of those built-ins, only `pg_postmaster_start_time` is in pull request #14's allow-list.** | a search of `PR14:engines/postgres/init/read-routine-names.sql` for each name | [R] |
| F-19 | **What it asks of this task:** twelve acceptance criteria, and a CLI contract. | `ED:` section 5; section 4 | [R] |
| F-23 | **Its fixture gives each of its roles to `admin`, inherited.** | `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureServer.cs:230`; `DI:tests/DataIntent.Component.Tests/Fixtures/FixtureRoles.cs:70-71` | [R] |
| F-24 | **Its comparison before an upgrade has five parts, C1 to C5,** and "from the next upgrade on, they are as designed". C5 asks that an export be refused, with nothing in its stream, after an elevation **and** when the fresh check cannot be made. The first rollout's rollback inputs are kept until its accepting run and package 3's gate have both passed. | `MR:` section 3, "The comparison as designed"; `DL:` DL-079 item 6.5 | [R] |
| F-25 | **One rollout rebuilds its instance from a build of `main`,** after the templates, pull request #14's account model and the README are merged. Each engine image copies `README.md`. | `DL:` DL-103 items 1 to 3; `SM:engines/postgres/Dockerfile:13`; `SM:engines/mysql/Dockerfile:18`; `SM:engines/sqlite/Dockerfile:21` | [R] |
| F-26 | **Pull request #14 stays unmerged until that instance's first cutover is accepted,** and C1 must pass against its candidate before it merges. The read account's native admission on the candidate comes "once the cutover is accepted". | `DL:` DL-085 items 1, 3 and 4 | [R] |
| F-27 | **DL-078 asks that the README lead with the project's purpose,** and cover the LTS engines and clients, and the datasets. | `DL:` DL-078 item 1 | [R] |
| F-30 | **Its instance is forwarded to a LAN** by two socket units outside the product, and it keeps a prefix, `di`, for its own databases and roles, for which it plans an administrator account on MySQL that manages accounts server-wide. | `DL:` DL-075; `MR:` A-02, 2.10 | [R] |

## 2. Capabilities: templates, copies, resets and the sweep

### 2.1 Names and namespaces

| Thing | Name | Rule |
|---|---|---|
| The template | `<database>_start` | `<database>` is the registry's name for the physical database (F-7). A dataset that appends to another's database is in that database's template. |
| The working copy | `<database>` | The name people use today. |
| A test copy | `<prefix>_<database>_<token>` | The prefix is its namespace. **The token is twelve hexadecimal digits that the CLI issues.** |
| A reset's transient | `<database>__new_<8 hex>`, `<database>__old_<8 hex>` | PostgreSQL only (2.3). |

- **The CLI names a copy; the caller does not.** [D: review 2's findings 2 and 3. A name the caller chose could already be in use, and could be used again, so a record under that name proved nothing about the object under it.]
  - The token is the first twelve digits of the copy's identity, which is 128 random bits.
  - **A name is never reused,** so a command that arrives late can only name the copy it meant, or nothing.
  - **The caller's label is in the record, not in the name.** It matches `^[a-z0-9]{1,24}$`, and is unique among a namespace's live copies. A caller that lost a reply finds its copy by its label.
- **Characters:** lower-case letters, digits and underscores. A prefix matches `^[a-z][a-z0-9]*(_[a-z0-9]+)*$` and is at most 16 bytes. [D]
- **Length:** a whole name is at most 63 bytes on both engines; 63 is valid and 64 is not. The image build refuses a dataset whose database name is longer than 33 bytes, so that the longest prefix and a token always fit. The longest today is 21. [D] [R: `SM:datasets/` directory names]
- **Reserved:** the suffix `_start`, a double underscore, and the name `megasamples`. [D]

**A namespace** is one prefix with one owning account. It is configuration, baked into the image (5.1):

```yaml
copies:
  namespaces:
    - {prefix: copy, owner: copier}        # the default: one namespace
  foreign: []                              # namespaces a consumer keeps for objects of its own
```

- **Any number of namespaces, each with an owner of its own.** [106-1] One owner is one trust domain (4.9); a deployer who must keep two consumers apart gives each a namespace.
- **A namespace's owner is locked until its key is set.** So a namespace can be baked ahead of need and taken into use later by setting its key and starting the service again: no rebuild, and no copy or enrollment is lost. Clearing the key locks it again. [106-17]
- **Adding a namespace that was not baked is a new image,** which renews the volumes: every copy and every enrollment goes, and the enrollments are replayed (4.6).
- **A foreign namespace** is a prefix some consumer uses for databases and accounts of its own on the same server. Declaring it lets the product keep out of it.

**No namespace may overlap anything else.** The image build refuses a configuration in which, for a prefix `P` [D]:
- any registered database, any template, `megasamples`, or an engine's own schema is named `P` or begins with `P_`;
- another prefix `Q` equals `P`, or one begins with the other followed by an underscore;
- a declared foreign namespace `F` equals `P`, or one begins with the other followed by an underscore.

So `oracle` is refused, because `oracle_hr` exists; and a prefix inside a declared foreign namespace is refused.

- **The same check runs at every build,** so a dataset added later cannot fall inside a namespace.
- **On MySQL every underscore in a grant's schema pattern is escaped,** in a prefix and in a database's own name: `copy\_%`, `oracle\_hr`, `northwind\_start`. [G-11]

### 2.2 A copy's record, its proof, and what excludes what

This section is the same on all three engines. [D: review 1's findings 3 and 4; review 2's findings 2, 3 and 9.]

**The record.** Each namespace has a ledger. A row is one copy:

| Member | What it is |
|---|---|
| `name`, `identity` | The issued name, and the 128 bits it comes from. |
| `label`, `database` | The caller's tag; the template it was copied from. |
| `phase` | `reserved`, `issuing`, `created`, `ready` or `dropping`. Written **before** the step it announces. |
| `revision` | A number raised by every change to the row. |
| `lease_until` | When the owner's stated need ends. |
| `proof` | What physically identifies the object (below). |
| `bytes` | The storage reserved for it (2.6). |

| Engine | The ledger | The physical proof |
|---|---|---|
| PostgreSQL | a table in the `megasamples` database, writable by the namespace's owner and the administrators | the database's OID, recorded once it exists, and its comment, which carries the identity. A database dropped and made again has another OID. [G-24] |
| MySQL | the same, in the `megasamples` schema | at `ready`: a fingerprint of every table's name and creation time. A schema dropped and made again has other creation times. [G-24] |
| SQLite | a sidecar `<name>.copy.json` beside each file, made with exclusive creation | the device and inode of the file the CLI wrote, recorded **before** it is published by a hard link. [G-19] |

**Locks, all ending with their holder's session.**
- **The change lock** of a name is held for the whole of any change to that copy. On PostgreSQL it is a session's advisory lock, taken in the `megasamples` database; on MySQL a named lock; on SQLite a `flock`.
- **A hold** is a row in the ledger and a lock of its own, one for each holder. So any number can hold one copy, on every engine. A holder that dies leaves a row whose lock is free; that row is stale, and whoever finds it removes it. [G-25]
- **A namespace lock** is held only while a reservation is counted and written.
- **The session that runs a change is the session that holds its lock.** If the client is lost, the lock lasts exactly as long as the server goes on with the statement. [G-7, G-15]
- **SQLite's lock files are stable.** They are files of their own in `.megasamples-locks/`, one for each name and one for each holder, never the sidecar. A process opens one, locks it, and then confirms that the path still names the file it locked. [G-20]

**Creating,** under the name's change lock, taken before the reservation:

| # | Step | The phase written before it |
|---|---|---|
| 1 | **The reservation, atomic:** under the namespace lock and the engine's storage lock (2.6), the limits are checked, an identity is issued, the name is confirmed absent, and a row is written. | `reserved` |
| 2 | The object is made (2.3, 2.4, 2.5). | `issuing` |
| 3 | The proof is recorded. On PostgreSQL the comment is written. The object is filled or granted. | `created` |
| 4 | Access is opened (4.6). The lock is released. | `ready` |

**A copy's state is read, never guessed,** from the row, the lock and the object:

| The row's phase | The change lock | The object | State | May anything remove it? |
|---|---|---|---|---|
| none | — | absent | `absent` | — |
| none | — | present, in the namespace | `unmanaged` | **no** |
| any | held | — | `changing` | no: it is being changed |
| `reserved` | free | absent | `stale` | the row only |
| `reserved` | free | present | `conflict`: the name was reserved absent, so the object is not this operation's | **no** |
| `issuing` | free | absent | `stale` | the row only |
| `issuing` | free | present | **`unproven`,** unless the engine's own proof says otherwise (below) | **no** |
| `created`, `dropping` | free | present, proof matches | `incomplete` | yes |
| `ready` | free | present, proof matches | `ready` | yes, by the rules below |
| `created`, `ready`, `dropping` | free | absent | `gone` | the row only |
| `created`, `ready`, `dropping` | free | present, **proof does not match** | `inconsistent` | **no** |

- **`issuing` is the one phase in which the object may exist without a recorded proof:** the creator died between the engine's success and the record of it. What each engine can still prove [G-24]:
  - **SQLite:** the inode was recorded before the link. The published file is that inode, and so this copy's; or it is not, and it is a `conflict`.
  - **MySQL:** a schema with no table in it. Removing it destroys nothing, so it is removed. A schema that holds any table is a `conflict`.
  - **PostgreSQL:** nothing. The database is `unproven`.
- **Nothing the design cannot prove is removed by any command.** `unmanaged`, `conflict`, `unproven` and `inconsistent` objects are kept and reported, with what was found. Removing one is an administrator's act, by hand. [D: review 2's finding 2.]
- **What the proof rests on, said plainly.** Only a namespace's owner and the administrators can make an object in a namespace [G-11, G-29]. So an object that defeats the proof was put there by one of them, under a name read from the ledger. The proof guards against accident and against a late or repeated command; it does not guard a principal against itself.

**Every command that changes a copy names the identity it expects.** `copy drop`, `renew`, `release` and `hold` take `--identity`. Under the change lock the row is read again, and the command goes on only if all of these hold [D: review 2's finding 3]:

| Command | Identity | Phase | Proof | Lease | Holds |
|---|---|---|---|---|---|
| `renew`, `release` | the one named | `ready` | — | — | — |
| `hold` | the one named | `ready` | matches | — | it adds one |
| `drop` | the one named | `ready`, or `incomplete` | matches | **any:** an owner may drop its own leased copy | no live hold but the caller's own |
| a sweep's removal | the one it selected | `ready` or `incomplete`, **at the revision it selected** | matches | ended, **read again now** | no live hold |

Otherwise: exit 5, `identity-mismatch` or `state-changed`, or exit 6, `held`; and nothing was changed. A renewal that finishes between a sweep's look and its removal raises the revision, so the sweep keeps the copy.

**What a sweep may remove.** A copy, only when every one of these holds [D]:

| # | Condition | What it guards |
|---|---|---|
| 1 | Its state is `ready` with a lease that has ended, or `incomplete`. | A lease is the owner's own statement of how long the copy is wanted. |
| 2 | Its change lock is taken without waiting. | A change in progress, however slow. |
| 3 | No hold on it is live. | A user that holds it, whatever its lease says. |
| 4 | Its identity, revision and lease, read again under the lock, are as selected, and its proof matches. | A renewal, a replacement, an impostor. |
| 5 | The engine lets it go: on PostgreSQL a plain `DROP DATABASE`, which refuses while any session is connected [G-8]; on MySQL a drop that gives up after five seconds on a lock [G-15]; on SQLite nothing more. | What the engine itself can see of use. |

Anything else is **kept and reported with its reason.**

**What "in use" covers, and what it does not.** [106-11]
- **Protected, for the whole period of use:** a copy whose user holds it or keeps its lease; and on PostgreSQL any copy with a session connected.
- **Not protected:** an idle MySQL session, and a process with a SQLite copy open, that neither holds the copy nor has a lease on it. No engine check sees them [G-15, G-20]. **The product says so, and does not claim that a sweep never removes a copy in use.** T-17 shows both cases, so that this sentence stays true.
- **So a user holds every copy it uses, for as long as it uses it.**

### 2.3 PostgreSQL

**The template.**
- **It is `<database>_start`, with `datistemplate` true, `datallowconn` false, and the superuser `postgres` as its owner.** [D]
  - It refuses every connection, the superuser's included; any account that may create databases can still copy it; only the superuser can alter, rename or drop it. [G-1]
  - `admin` is not its owner, so `admin` cannot open it. That is the reason for the owner.
- **What it would take to write it:** the superuser sets `ALLOW_CONNECTIONS true`. No command of the CLI does it. [D]
- **It is frozen before it is closed:** `VACUUM (FREEZE, ANALYZE)` in the image build. [D]
- **Its record is its comment,** set by the build: the tag `megasamples-template/1` and a JSON object with the database, its allocated bytes, the measured peaks of a copy and a reset, the copy strategy, the build id and the SHA-256 of its registry row. [D] [G-8]

**How the image makes it.** [D: so that the image's own working copy comes from the path a reset uses.]
1. The dataset is loaded into `<database>_start`, as `admin`, as today (`SM:engines/postgres/Dockerfile:43-53`).
2. The read grants of section 4.1 and the read profile are applied there. **No write grant to any group is.**
3. It is frozen, given to `postgres`, and closed.
4. The working copy is made from it, and its own write grants and `CONNECT` are given (4.1).
5. A database with no template is loaded straight into `<database>`, as today, with the same grants.

The build's private server loads the hook, so step 4 closes the new database as a running service would.

**A copy,** as the namespace's owner, connected to the `megasamples` database. It is steps 2 to 4 of 2.2's creation:
- `CREATE DATABASE <copy> TEMPLATE <database>_start STRATEGY <strategy>`. The hook confines the name and the template, and closes the new database to `PUBLIC` (4.3).
- Its OID is recorded, and its comment written: `megasamples-copy/1` and the identity.
- **In the copy itself,** the owner grants row changes on its tables to the namespace's write group (4.1).
- **Last,** `GRANT CONNECT ON DATABASE <copy>` to the namespace's two groups. Until then only its owner can connect.
- **The strategy** is the template's recorded one. The build measures `WAL_LOG` and `FILE_COPY` for each template and records the faster. [D]
- **What a copy inherits** is section 4.8. [G-2]

**A drop** is a plain `DROP DATABASE`, never with force, under 2.2's checks. With `--wait` it is tried again until the wait ends. It closes nothing first: a drop that gives up has changed nothing.

**A reset of the working copy,** as `admin`, connected to the `megasamples` database. **Both paths are the same procedure;** they differ only in how the new copy is filled. [D: review 2's finding 4. Today's image path drops the working copy and then restores it (F-4); between the two there is nothing to go back to.]

| Step | What happens | The phase, and how it is made durable |
|---|---|---|
| a | The database's reset lock is taken, without waiting. A row is written in `megasamples.operations` under the caller's operation identity. | `building`, written first |
| b | `CREATE DATABASE <database>__new_<id> OWNER admin`, from the template, or empty from `template0` for the image path. **Image path:** a worker restores the image's dump into it, with no `--create`. Then its write grants are given, in it. It holds no `CONNECT` for anyone but its owner. | `built`, written after |
| c | **The door is closed:** `ALTER DATABASE <database> ALLOW_CONNECTIONS false`, **in one transaction with the phase.** | `closed` |
| d | The sessions on the working copy are listed. Any session stops the reset here, unless the caller chose to discard them (3.6). Then they are ended. | `closed` |
| e | **In one transaction:** the working copy is renamed to `<database>__old_<id>`; the new one is renamed to `<database>`; its `CONNECT` is granted to the working groups; and the phase is set. | `swapped` |
| f | `DROP DATABASE <database>__old_<id>`. | `done`, written after, **and kept** |

- **Steps c and e are each one transaction or the swap is not built.** [G-3]
- **Why a swap, and not a drop and then a copy.** DL-077's entry says "drop-and-copy". This keeps its result, and changes the order: a failure before step e changes no data, and the working copy's name is never free. Review 2 found the change justified, conditional on G-3. [D]
- **The image path's worker** writes only into the transient, whose name is the operation's own. If the connection that holds the lock is lost while the worker runs, the CLI stops the worker. A later reconciliation finds sessions on the transient and waits: a plain drop refuses while they are there. [G-26]
- **A transient is proved** by its name, which holds the operation's identity, by its owner, and by its OID once recorded. [G-24]

**An operation's outcome is kept, under an identity the caller knows.** [D: review 2's finding 5.]
- **The caller may give the identity** (`--operation`), or reads the one the CLI prints before it changes anything.
- **The row is not removed at the end.** It ends in one of `done`, `rolled-back` or `failed`, with what was found, and is kept for seven days.
- **`megasamples reset --status --operation ID`** answers, whenever asked: still running; unsettled at a phase; its terminal outcome; or **not found, which means it never started.**
- **A reset of several targets** is one operation for each, and its document gives each target's outcome.

**Reconciling,** by `megasamples reset --reconcile --operation ID`, under the lock:

| The row's phase, with the lock free | What reconciling does | Outcome |
|---|---|---|
| `building` | drops the transient if it exists and is proved, and has no session | `rolled-back`: the working copy is as it was |
| `built` | the same | `rolled-back` |
| `closed` | **opens the door again;** drops the transient | `rolled-back` |
| `swapped` | drops the old transient if it is still there | `done`: the working copy is pristine |
| a terminal phase | nothing | as recorded |

- **A crash in step c or d leaves the working copy closed** until someone reconciles. It is kept short by doing all the copying first. The CLI opens the door again when it is interrupted by a signal. `megasamples accounts check` reports any unsettled operation. [D]
- **A whole engine's reset** is 3.6's.

### 2.4 MySQL

**The template.**
- **It is the schema `<database>_start`, set `READ ONLY = 1`.** [D] [G-10]
- **MySQL has no "accepts no connections" for a schema.** What stands in its place: `demo` holds no privilege there; a namespace's owner holds `SELECT` only; `admin` and `root` can read it, and can change the option. [D]
- **`admin` is not shut out of it by a partial revoke.** [D: that needs the server's `partial_revokes` setting, under which wildcards in schema grants may stop working [G-11].]

**How the image makes it.** After the dumps are loaded (`SM:engines/mysql/Dockerfile:39-42`), for each templated database:
1. Its definitions are recorded in `megasamples.template_ddl`: tables, then routines, views in dependency order, triggers and events. **Each row holds the definition without its definer, and the original definer and security mode beside it.** [D: review 2's finding 11.] The insertable columns of each table, and each table's `CHECKSUM TABLE … EXTENDED`, are recorded too. [G-13]
2. The template is made from the loaded database by the copy below, as `root`, with each recorded definer.
3. Each table's row count and checksum are compared with the loaded database's.
4. The template is set `READ ONLY = 1`.

**A copy,** as the namespace's owner, all of it inside the server. It is steps 2 to 4 of 2.2's creation:
1. `CREATE DATABASE <copy>`, never `IF NOT EXISTS`, with the template's character set and collation.
2. Each table's recorded definition, with foreign-key checks off for the session.
3. `INSERT INTO <copy>.<table> (…) SELECT … FROM <database>_start.<table>`, a table at a time.
4. The routines, the views, and then the triggers and events, so that no trigger fires during the load.
5. **Each table's row count and checksum** compared with the template's record. [D: review 2's finding 6: a count does not see an update.]
6. The fingerprint is recorded (2.2), and the row is set `ready`.

- **A copy has no grant of its own.** [D: review 1's second P1.] And since no name is reused, a grant someone left on an old copy's name can never meet a new copy.
- **On MySQL a namespace's owner is the only ordinary account that can write its copies.** Enrollment in a namespace is for reading only there (4.6). [D: review 2's finding 6. A pattern grant cannot be closed for one copy while it is filled.]
- **Accounts enrolled to read a namespace can see a copy while it is being filled.** A caller uses a copy only once `copy create` has returned it `ready`.
- **The definer of everything in a copy is the namespace's owner.** [D: an owner may not run code as `admin`.]
- **Whether the owner can replay every kind of definition,** with the binary log on and off, is [G-13]. A kind it cannot replay excludes the datasets that use it, by name.

**Large datasets, and the stated exclusions.** [D]

| Database | On MySQL | Why |
|---|---|---|
| Templated, up to `copy_limit_mb` of allocated bytes, measured at build | template, copies and reset by the logical method | The limit's default, 512, is a starting value. |
| Templated, above the limit | template and reset; **no copies**: exit 4, `too-large` | A logical copy's time and undo grow with its rows. |
| A database with `depends` (`oracle_oe`) | **no template, no copies**; reset by the image path | Its foreign keys and views reach into `oracle_hr` (F-11). |
| A database another refers to (`oracle_hr`) | template and copies if [G-14] passes. **Its reset, by either path, is coordinated** (below). | Rows a person added to `oracle_oe` may point at rows of `oracle_hr` that the pristine one does not have. |

**A reset of the working copy,** as `admin`. Each phase is written before its step. The session that drops and fills is the session that holds the reset lock. [D]

| Step | What happens | The phase written before it |
|---|---|---|
| a | The reset lock (`GET_LOCK`) is taken, without waiting. Unexpected grants on the schema's name are looked for (4.5): any stops the reset here. | `started` |
| b | **Ordinary writers are shut out:** each enrolled writer's grant on this schema is revoked, and its sessions are ended. [G-27] | `excluding` |
| c | `DROP DATABASE`, bounded by `--wait`. | `dropping` |
| d | The copy above, with each recorded definer. | `filling` |
| e | Each table's count and checksum against the template's record; each foreign key that points in from another schema, for orphans. | `filled` |
| f | The writers' grants are given again, from the enrollment record. | `done`, written after, and kept |

- **It cannot be undone after step c.** Reconciling an interrupted one says which of two things it does, by the phase:

  | The row's phase, with the lock free | What reconciling does | Outcome |
  |---|---|---|
  | `started` | nothing was changed | `rolled-back` |
  | `excluding` | gives the writers' grants again | `rolled-back` |
  | `dropping`, and the schema is still whole | gives the grants again | `rolled-back` |
  | `dropping` with the schema gone; `filling` | drops what is there, fills, checks, gives the grants again | `done` |
  | `filled` | **checks only.** It does not drop again. | `done`, or `failed` with the tables that differ |

- **Until it is `done` the writers stay shut out.** An interrupted reset fails closed.
- **If [G-27] shows that writers cannot be shut out,** a MySQL working copy's reset by this path is not offered where any writer is enrolled: exit 4, before any change.
- **A coordinated reset.** A database that another working database refers to is reset only together with those that refer to it: `reset mysql:oracle_hr` is refused, exit 5 and `has-dependents`, unless `--with-dependents` is given. Then `oracle_hr` and `oracle_oe` are one operation, each with its own outcome, and every key between them is checked at the end. [D: review 2's finding 11. It binds the image path too, which today resets `oracle_hr` alone.]
- **The image path** (a database with no template) has the same phases and the same lock. **Its worker takes the lock itself:** the stream the worker reads begins with a statement that takes the reset lock and fails if it cannot. So a worker that outlives the CLI still excludes the next reset. [G-26]
- **Privileges stay:** a grant on `<database>` by name outlives the drop. [G-12]

**Its records are tables in `megasamples`:** `service`, `templates`, `template_ddl`, `operations`, `enrollments`, `storage`, and one ledger for each namespace. [D]

**The binary log is configurable, and the image keeps it on.** [106-13] `engines: {mysql: {binary_log: false}}` turns it off. Every logical copy and reset is written to it a second time; it reached 10.9 GB in one rehearsal (F-10). Turning it off is a deployer's choice, with [G-18] and the storage report in hand.

### 2.5 SQLite

- **The template is the image's file.** There is no server and no account, so "read-only" is the file's mode. [R: `PR14:docs/strict-read-account.md:13`]
- **Staging, once, where the service runs:** `megasamples template stage sqlite --out DIR` writes each `<database>.sqlite` with mode 0444, and `templates.json`: its format tag, and for each file its size, its SHA-256 and the build id. [D]
- **A copy,** by 2.2's creation, in the caller's directory:
  1. the name's lock file is locked; the sidecar is made with exclusive creation, as the reservation;
  2. the template is copied to a temporary name in the same directory, synced, and held to the manifest's SHA-256; **its device and inode are written to the sidecar;**
  3. it is published by a hard link to its final name, which fails if that name exists; the temporary name is removed. Nothing is ever moved over an existing file. [G-19]
- **A drop** removes the file only if it is the recorded inode; then any `-wal`, `-shm` or `-journal` beside it; then the sidecar. The lock files stay.
- **A sidecar of the format before this one** is read for what it identifies, and the copy is kept and reported (section 6).
- **Nothing goes over the network.** Anyone who is not where the service runs works from a staged directory that was copied to them, manifest included. [D: serving files would be a new listener.]
- **The service's own files** keep today's reset.

### 2.6 Which databases get a template, and the storage

**The default selection is `core`:** every physical database whose base dataset is of tier `core` or `core-medium`. [106-18]
- **It is configured per engine:** `engines: {postgres: {datasets: …, templates: core}}`, with a selector, a list of databases, or `none`. It is baked. [D]

**No size is promised here.** A template is a physical database, appended datasets included (F-21), and the figures on record are old and of two kinds (F-9).

**The build measures, and enforces a budget.** [D]
- **Each selected physical database** is measured as that engine holds it, in allocated bytes.
- **`templates.budget_mb`** is the most the selected templates may add on one engine. A selection over it does not bake. Its default is 4096, a starting value.
- **For each template the build records two peaks,** measured: the most extra space one copy needed at any moment, and the most one reset needed, with the write-ahead log, the undo and the temporary space counted.
- **The build prints a storage report:** each template's bytes; both peaks for each; and what the configured limits allow at once. A deployer sizes a volume from it.

**Admission reserves headroom for the whole engine, not for one namespace.** [D: review 2's finding 12.]
- **`storage.headroom_mb`** is the space the deployer gives to copies and resets on one engine.
- **Every `copy create` and every `reset` reserves its template's recorded peak,** in `megasamples.storage`, under the engine's storage lock, before it changes anything. A live copy keeps its size reserved. What does not fit is refused: exit 5, `no-headroom`.
- **A reserve for recovery is never lent:** the largest single reset's peak. So an interrupted reset can always be reconciled.
- **A namespace's own limits** are inside that: at most 32 live copies, and `quota_mb`.
- **What this does not bound:** SQL sent outside the CLI by a credential's holder (5.3).

**When the disk fills anyway.** [D]

| What was running | What must hold afterwards | Gate |
|---|---|---|
| A copy, on any engine | Every template and every working copy is whole. The copy is `incomplete` or gone. | G-9, G-17, G-19 |
| A PostgreSQL reset | The same: nothing is swapped until the new copy is whole. | G-9 |
| **A MySQL reset, after its drop** | Every template and every **other** working copy is whole. **This one is not, and is not claimed to be:** it is unsettled at `filling`, and reconciling completes it once there is space. | G-17 |
| A record's own write | The command stops before the change the record would have announced. | G-9, G-17 |
| A SQLite sidecar, a journal, or the publication | No file under a final name that is not whole. | G-19 |

If a gate shows a server falling over, **copies and template resets** on that engine are not offered until the design has a guard.

## 3. The CLI for scripts

### 3.1 The commands

Decided here. [D: DL-077 item 3.]

| Command | As | What it does |
|---|---|---|
| `megasamples interface` | nobody | The interface number, the output schema, each format's tag that it reads and writes, the package version and the revision. |
| `megasamples whoami ENGINE` | any account | The account it signed in as, **and the address the server saw it come from** (5.3). |
| `megasamples template list ENGINE` | any account | For each registered database: whether it has a template, the template's record, and whether copies are offered, with the reason if not. |
| `megasamples template stage sqlite --out DIR [DATABASE…]` | nobody | 2.5. Where the service runs only. |
| `megasamples copy create ENGINE:DATABASE --prefix P --label L [--lease DURATION]` | the namespace's owner | 2.2. It returns the issued name and the identity. The lease defaults to 24 hours. |
| `megasamples copy show ENGINE:NAME` | the owner | The copy's derived state (2.2), its lease, its holds and its proof. It changes nothing. |
| `megasamples copy list ENGINE --prefix P [--label L]` | the owner | Each copy's name, identity, database, label, state and lease. |
| `megasamples copy hold ENGINE:NAME --identity ID [--hold-fd N]` | the owner | Holds the copy (below). |
| `megasamples copy renew ENGINE:NAME --identity ID --lease DURATION` | the owner | Sets the lease's end. |
| `megasamples copy release ENGINE:NAME --identity ID` | the owner | Ends the lease now. |
| `megasamples copy drop ENGINE:NAME --identity ID [--wait SECONDS]` | the owner | Dropping a copy that is already gone succeeds. |
| `megasamples copy sweep ENGINE --prefix P [--dry-run]` | the owner | What it removed, and what it kept and why (2.2). |
| `megasamples reset ENGINE:DATABASE… [--json] [--operation ID] [--discard-sessions] [--unattended] [--with-dependents] [--wait SECONDS] [--from auto\|template\|image]` | `admin` | Today's command, with the template path. `auto` takes the template when there is one. |
| `megasamples reset --status ENGINE[:DATABASE] [--operation ID]` | `admin` | Each operation: its phase, whether it is still running, its outcome, and what reconciling would do. It changes nothing. |
| `megasamples reset --reconcile ENGINE:DATABASE --operation ID` | `admin` | Settles an interrupted reset (2.3, 2.4), and says which way. |
| `megasamples accounts check [--repair]` | the administrator, where the service runs | 4.5. |
| `megasamples accounts enroll\|unenroll\|list\|restore …` | `admin`, where the service runs | 4.6. |
| `megasamples accounts reader ENGINE --name N --password-out FILE` | `admin`, where the service runs | Makes a read account for one consumer, and enrolls it (4.6). |
| `megasamples accounts export ACCOUNT --for WHOM --out FILE` | where the service runs | Writes one credential, alone, to a private file, and records the handing-over (5.3). |

- **Common options:** `--host`, `--port`, `--user`, `--connect-timeout`, and one of `--password-file`, `--password-stdin` or `--env-file` (3.4). For SQLite: `--templates DIR` and `--dir DIR`.
- **`ENGINE:DATABASE`** follows the reset's own pairs (`SM:megasamples/reset.py:6`). The database is the registry's name.

**`copy hold`, for a script.** [D: review 2's finding 9.]
1. It takes the change lock; checks the identity, the phase and the proof (2.2); writes its hold's row and takes its hold's lock; releases the change lock. A sweep cannot fall between those.
2. **Then it writes one line to standard output:** the acknowledgment, with the identity it holds and the lease. **A caller opens the copy only after it has read that line.**
3. It holds until it is told to stop, which is never by standard input: `--hold-fd N` names an inherited descriptor, and the hold ends when that reaches end of file; or it ends on a signal; or when the process that started it is gone. A password given by `--password-stdin` is one line, and closing it ends nothing.
4. On the way out it removes its row. If it dies, its lock goes with it and the row is stale.

### 3.2 Output

- **One JSON document on standard output, on one line,** for `interface`, `whoami`, `template`, `copy` and `accounts`, and for `reset` with `--json`, `--status` or `--reconcile`. `copy hold` writes its one acknowledgment line and nothing else. Everything else goes to standard error. [D]
- **Its envelope:** `schema`, `command`, `ok`, `exit`, `result`, `error` and `warnings`. `error` holds a stable `code`, a `message`, and the `operation` or copy `identity` a caller reads the state by.
- **A copy's result:** its `name`, `identity`, `engine`, `database`, `prefix`, `label`, `state`, `revision`, `reserved`, `lease_until`, its `endpoint` (the host and port the caller used, or the file's path), its `owner`, **its `writers` and whether they are `exclusive`** (4.6), the `template` with its build id and registry digest, the engine's `version`, the `strategy`, and the seconds it took.
- **A reset's result:** for each target its `operation`, `phase`, `outcome` and exit.
- **No credential is ever in it:** an account is a name.

### 3.3 Exit codes

Decided here [D].

| Code | Meaning | What it promises |
|---|---|---|
| 0 | done | as asked |
| 1 | a defect in the CLI | nothing; treat it as 8 |
| 2 | wrong usage | no engine was contacted |
| 3 | the engine cannot be reached, or the sign-in is refused | nothing changed |
| 4 | not offered here: no template, `too-large`, excluded, a failed gate's command, or an option this engine or path cannot honour safely | nothing changed |
| 5 | refused by a rule: namespace, label in use, identity or state not as expected, a limit, no headroom, an unknown format, an unexpected grant | nothing changed |
| 6 | busy | **nothing changed, and the CLI confirmed it** |
| 7 | failed | **nothing is left changed, and the CLI confirmed it** |
| 8 | unsettled | **a durable record describes what is there** |

| Command | 6 means | 7 means | 8 is read by, and settled by |
|---|---|---|---|
| `copy create` | the namespace lock could not be had in time; no row was written | the object this operation made is gone, with its proof checked, and so is its row | `copy list --label`; `copy drop`, for what 2.2 lets it remove |
| `copy drop` | sessions remained at the end of the wait, or another holds the copy; it is still `ready` and untouched | — | `copy show`; `copy drop` again |
| `copy sweep` | — | — | `copy list`; `copy drop` for each it names |
| `copy hold`, `renew`, `release` | another change holds the name | — | — |
| `reset`, PostgreSQL | another reset holds the lock; or sessions were found and **the door is open again** | no data changed; the door is open; the transient is gone; the outcome is `rolled-back` | `reset --status --operation`; `reset --reconcile` |
| `reset`, MySQL | another reset holds the lock, or the wait ended before the drop; **the writers' grants are back** | it failed before the drop; the grants are back | the same; reconciling may only be able to complete it |
| `reset --reconcile` | the operation, or its worker, is still running | — | itself |
| `accounts check` | — | something is not as expected; the document lists each | — |

- **A command that cannot confirm what 6 or 7 promises returns 8.**
- **A reset of several targets** returns 0 only if every one is `done`. Otherwise it returns the gravest of its targets' exits, in the order 8, 7, 6, 5, 4, 3, and the document gives each.
- **A caller that meets a code it does not know treats it as 8** (section 6).
- **2 is what the CLI already returns for an unknown command** (F-2). Codes above 125 are left to the shell.

### 3.4 Credentials

- **A password comes from a private file or from standard input.** Never from an argument, and never from the environment. [D]

  | Route | What is read |
  |---|---|
  | `--password-file PATH` | the file's one line |
  | `--password-stdin` | one line of standard input |
  | `--env-file PATH` | the keys of a `.env`-style file that this command needs |

- **Every file route requires a file that is the caller's own and closed to others.** Otherwise it is refused before it is read. [D: review 2's finding 10.]
- **The keys:**

  | Key | Account |
  |---|---|
  | `DEMO_PASSWORD` | `demo`, on PostgreSQL; and on MySQL unless the next key is set |
  | `MYSQL_DEMO_PASSWORD` | `demo` on MySQL, when a deployer gives it a key of its own (4.5) |
  | `ADMIN_PASSWORD` | `admin`, on both engines: **one key, with the authority of both** (4.9) [106-14] |
  | `POSTGRES_PASSWORD`, `MYSQL_ROOT_PASSWORD` | the superusers |
  | `<OWNER>_PASSWORD`, such as `COPIER_PASSWORD` | a namespace's owner, on both engines. Unset, the account is locked. |

- **The `--env-file` grammar.** A line is `KEY=value`, or a comment. A value is bare, single-quoted or double-quoted, with the quotes' own escapes and nothing else. **A value that asks for expansion is refused:** exit 2, `env-file-expansion`. It is not expanded, and its text is not printed.
- **Every key a command needs is resolved once, at its start, from the one route named, and handed to everything it starts.** [D: review 2's finding 10.]
  - That is so for the reset's image path too. Today its host process reads its passwords by a reader that takes an exported value over the file's (F-22). That reader is replaced, for `reset` and for `accounts`, by this one. The container the reset starts, and each client inside a container, is given the resolved values by the private file the reset already writes for it (`SM:megasamples/reset.py:172-183`).
  - So a network connection and a worker can never sign in with two different inputs.
  - **An exported variable of the same name is never read.** A warning names the key, never a value.
  - **If the server was started with an exported value** that differs from the file's, every sign-in is refused: exit 3. The README already tells an operator to unset such exports (`SM:README.md:130-131`).
- **`reset` and `accounts`, where the service runs, default to `--env-file` at the checkout's `.env`.** No other command has a default. [D: `reset` works today with no option (`SM:README.md:318`).]
- **Nothing else ambient is used.** `PGPASSWORD`, `PGPASSFILE`, a `~/.pgpass`, `MYSQL_PWD` and client option files are not read, and every connection parameter is given explicitly. [D]
- **It is in no output.** A driver's error text is passed through the redaction the pull request's helper has (`PR14:docs/validation/strict_read_clients.py:66-71`).

### 3.5 Where it runs

| From | PostgreSQL and MySQL | SQLite |
|---|---|---|
| Where the service runs | everything | everything |
| Anywhere else that reaches an engine's port | `whoami`, `template list`, and whatever the credential in hand allows: `copy` with a namespace owner's; `reset` with `admin`'s | copies, from a staged directory that was copied there |

- **The remote commands need a TCP path to the engine's port, and nothing else:** no container runtime, no checkout. [D]
- **Two capabilities are claimed only once their gates pass:**
  - **A MySQL namespace owner's credential used away from the service:** after [G-11] and [G-28].
  - **A PostgreSQL namespace owner's credential used away from the service:** after [G-29]. Until then DL-077 item 3's "from a separate machine" is not met for PostgreSQL copies, and the README says so. [106-4]
- **Drivers:** PyMySQL, which is a dependency already, and Psycopg, which is a development dependency already, at 3.3.9 (`SM:pyproject.toml:8`, `:19`). **Psycopg's licence is reviewed first,** under the repository's dependency procedure [106-19]; a pure-Python driver is the fallback. [G-21]
- **A small install.** [D]
  - The new code is a subpackage that imports the standard library and the two drivers only.
  - `pyproject.toml` gains a build backend and a `megasamples` entry point. The pipeline's dependencies move to a dependency group that `uv sync --locked` installs by default. [G-21]

### 3.6 What excludes what, and resets under people

Each row's behaviour is decided here [D]. T-15 generates every pair from the command inventory.

| At once | What happens | By |
|---|---|---|
| Two `copy create` of one template | both succeed, under names of their own | each only reads the template [G-1, G-10] |
| Two `copy create` with one label | one succeeds; the other is exit 5, `label-in-use` | the reservation |
| Many `copy create` at a namespace's last place, or the engine's last headroom | exactly as many succeed as fit | the reservation under the namespace and storage locks |
| `copy sweep` and a `copy renew` of the same copy | the copy is kept | the revision, read again under the lock |
| `copy drop` that arrives after its copy is gone and another exists | it finds its own name gone: success. The other is untouched. | names are not reused; the identity |
| `copy hold` and `copy sweep` or another's `copy drop` | the sweep keeps it: `held`; the drop is exit 6 | the hold |
| `copy create` and `reset` of that database | both succeed | both copy the template |
| Two `reset` of one database, **by either path** | one runs; the other is exit 6 | the reset lock |
| A reset's worker that outlives its CLI, and another reset | the second is exit 6 | PostgreSQL: the transient is the first's own. MySQL: the worker holds the lock. [G-26] |
| A whole engine's reset and anything else | below | the maintenance record |

**One exclusion for both reset paths.** The image path takes the same lock and writes the same operation row (2.3, 2.4). The lock file stays as a second guard for one machine (F-3).

**A whole engine's reset** replaces the server that held every lock and every record. So its own exclusion and outcome live outside the volume. [D: review 2's finding 4.]
1. **A maintenance record where the service runs,** a file that the volume's replacement does not touch, is written first, under a file lock: an operation identity and the phase `started`.
2. On the old server it takes, without waiting, every database's reset lock. Any held: exit 6, and the record ends `rolled-back`.
3. The volume is replaced. **The new server starts closed to the CLI:** the start wrapper is given the operation's identity and writes a maintenance marker into the service's record before the server listens. Every command of the CLI that finds the marker does nothing: exit 6, `maintenance`. [G-30]
4. The whole engine's reset checks the new server, clears the marker, and ends its record `done`. **The record is kept,** so `reset --status` there answers for it afterwards.
- A marker left by a reset that died is cleared by `reset --reconcile` where the service runs, which finishes step 4.

**Resets under people.** [106-12] **A reset discards nobody's work unless it is told to.**

| | What happens when sessions are on the working copy |
|---|---|
| **By default** | The reset stops: exit 6, saying how many sessions and whose. On a terminal it first warns, and asks whether to discard them. |
| **`--discard-sessions`** | The warned human choice, given as an option: the sessions are ended and the reset goes on. |
| **`--unattended`** | For automation. One database only. The door is closed, the sessions are looked for, and any session is a refusal before any change. It never takes `--discard-sessions`. |

| Engine and path | What an idle check can be |
|---|---|
| PostgreSQL, either path | 2.3: the door is closed, then sessions are looked for. |
| MySQL, either path | **There is no door.** A session can name any schema, and an idle one cannot be seen [G-15]. **`--unattended` is refused before any change:** exit 4. A person's reset there always needs `--discard-sessions`, since nothing else would be true. |
| SQLite | `--unattended` is refused: exit 4. Its reset stops the consoles and cannot see another reader (`SM:README.md:312-314`). |

- **This changes today's default,** which disconnects (F-4). `make reset` from a terminal asks; from a script it needs the option.
- **Who can take these locks.** On PostgreSQL only the accounts given the lock functions in the `megasamples` database: the namespaces' owners and `admin`. On MySQL any account can take any named lock (F-14), so any credential's holder can make a copy or a reset report busy (5.3).

### 3.7 Limits

Decided here [D], as starting values.

| Limit | Value | Past it |
|---|---|---|
| A whole name | 63 bytes; 63 is valid | the build refuses the dataset or the prefix |
| A prefix; a label | 16 bytes; 24 bytes | exit 2 |
| A prefix or label that is empty, or holds upper case, a space, a non-ASCII character, a quote or a double underscore | never valid | exit 2, before any connection |
| A name given to a command that is not a copy's issued form | never valid | exit 2 |
| A namespace's live copies; their total size | 32; `quota_mb` | exit 5, `limit` |
| The engine's headroom | `storage.headroom_mb`, less the recovery reserve | exit 5, `no-headroom` |
| A lease | at least one minute; at most seven days; 24 hours by default | exit 2 |
| MySQL copy size | `copy_limit_mb` | exit 4, `too-large` |
| Connection timeout; `--wait` | 10 seconds; 0 | exit 3; exit 6 |

No statement timeout is set by default: a copy of a large database takes as long as it takes. [D]

## 4. The account model

### 4.1 PostgreSQL's roles

Decided here [D]; what exists today is F-5.

| Role | A login | Attributes | What it is for |
|---|---|---|---|
| `postgres` | yes | superuser | The image build, the start wrapper, the image path's worker. Owns the templates and the policy. |
| `admin` | yes | `CREATEDB`, `CREATEROLE`; **new:** `pg_signal_backend` | Owns each working copy and everything in each sample database. Resets. Enrolls. Makes whatever roles and databases a consumer needs of its own. |
| `demo` | yes | — | Reads the working copies. **It is promised read-only, and can never be enrolled to write.** |
| **`megasamples_read`** | no | — | `SELECT` on every table of every sample database and every copy. |
| **`megasamples_write_routines`** | no | — | `EXECUTE` on the built-ins a row change needs (P-6). It holds no right on any table. |
| **`megasamples_working_read`**, **`megasamples_working_write`** | no | — | `CONNECT` on every working copy. The write group is also granted row changes **inside each working copy.** |
| **`megasamples_copy_<prefix>_read`**, **`…_write`** | no | — | `CONNECT` on every copy of that namespace. The write group is also granted row changes **inside each of that namespace's copies.** |
| **`megasamples_copy_<prefix>_owner`** | no | — | Marks a namespace's owner, for the hook (4.3). |
| **`copier`**, and each namespace's owner | yes | `CREATEDB` | Makes, uses and drops its namespace's copies. |

**Reading is one group. Writing is granted inside each database, to that database's own scope.** [D: review 2's first P1.]
- **Round 2's fault.** It gave one write group the row changes on every table of every database, and let `CONNECT` decide the rest. A role enrolled to read the working copies and to write one namespace then held both halves of writing a working copy.
- **Now the template carries no write grant to any group.** It grants row changes, and `USAGE` on sequences, to `pg_database_owner` alone, with the grant option. In any database that is its owner. [G-23]
- **Each database's owner then grants, in that database, to its own scope's write group:** `admin` to `megasamples_working_write` in a working copy; a namespace's owner to its `…_write` group in each of its copies.
- **So a write group's rights exist only in its own scope's databases.** Enrolled to write a namespace and to read the working copies, a role finds in a working copy no write grant that names any role it holds.
- **Reading cannot combine into more than reading,** so one read group serves every scope.

**Each membership, and its options.** [D: review 2's finding 8.]

| Member | Of | `INHERIT` | `SET` | `ADMIN` | Made by |
|---|---|---|---|---|---|
| `megasamples_working_read`, each `…_copy_<prefix>_read` | `megasamples_read` | true | false | false | the build |
| `megasamples_working_write`, each `…_copy_<prefix>_write` | `megasamples_read`, `megasamples_write_routines` | true | false | false | the build |
| `demo` | `megasamples_working_read` | true | false | false | the build |
| a namespace's owner | `megasamples_read`, `megasamples_write_routines`, its own `…_owner` | true | false | false | the build |
| **`admin`** | every group above | **false** | **false** | **true** | the build |
| an enrolled role | one scope's read or write group | true | false | false | `admin`, by enrollment (4.6) |

So `admin`, as shipped, administers every group and inherits none of them.

**Which database an account reaches is decided by `CONNECT` on it,** which is not copied [R: `PR14:docs/strict-read-account.md:9`]:

| Database | `CONNECT` is granted to |
|---|---|
| a working copy | its owner `admin`; `megasamples_working_read`; `megasamples_working_write` |
| a template | nobody |
| a test copy | its owner; its namespace's two groups |
| `postgres`, `megasamples` | `PUBLIC`, as today |
| any database made later | its owner, until its owner grants more |

- **These grants name groups and never a person's account,** so what a reset gives a new working copy is always the same, and who is enrolled is a membership, which a reset does not touch (4.6).
- **The hook closes `CONNECT` as well as `TEMPORARY` on each new database.** [D]
- **A namespace's owner also holds,** in the `megasamples` database only: its own ledger, its rows of the storage table, and `EXECUTE` on the advisory-lock functions. [D]

### 4.2 The strict read profile

**What pull request #14 does** is F-12. **What changes:**

| # | Change | Reason | Mark |
|---|---|---|---|
| P-1 | **The allow-list is granted to `PUBLIC`,** not to `demo`. | Finding H-1. Every role that is not an administrator then has the same floor, in every database and every copy, whoever made it. | [D] |
| P-2 | **`demo` holds nothing itself** but its membership. | 4.1. | [D] |
| P-3 | **Three built-ins join the list by name, each with its reason:** `pg_export_snapshot()`, `pg_current_snapshot()` and `pg_database_size(oid)`. | A client that reads consistently across sessions, or shows a database's size, needs them. One consumer does both (F-17, F-18). What each does to the server is [G-5]. | [D] |
| P-4 | **The rule for the list is stated.** A routine is admitted when it changes no stored object, no setting, no sequence and no other session's data, and assigns no transaction id. Volatility is the default test; an exception is named in the list with its reason. | So that P-3 is a rule and not a hole. | [D] |
| P-5 | **An exported snapshot is admitted explicitly, as the one exception that reaches past its own statement.** It leaves an identifier that another session may import for as long as the exporting transaction lives. | The rule must say so. | [D] [G-5] |
| P-6 | **A write list beside it,** granted to `megasamples_write_routines`: the built-ins that inserting, updating and deleting rows through the datasets' own defaults and triggers need. It is found by running each dataset's trigger scenarios as a writer and reading each refusal. Holding it changes no row: that needs a table's grant, which is scoped (4.1). | A writer's statement runs a trigger's body with the writer's rights [G-5]. | [D] |
| P-7 | **The published inventory is the one authority:** every executable signature, with its reason, generated from the candidate. A consumer that checks an account's privileges can take it as data. | So that there is one list, not one in each consumer. | [D] |

**What stays:** no `TEMPORARY` for `PUBLIC`; no large-object creation; no user routine for a reader; the two rewritten `employees` views; the closed defaults for `admin` and `postgres`; MySQL not claimed strict (F-14).

**A routine a consumer finds it needs** is admitted under P-4, or the consumer changes. [D]

### 4.3 The hook and the event trigger: a design check

This is input to an independent review of **the final hook** [106-15]. Each row is from reading `PR14:` at the cited lines; none was run. A finding that rests on engine behaviour is a gate first.

| # | Finding | Where | Disposition |
|---|---|---|---|
| H-1 | **Every role but `demo` and `admin` may be left unable to call any built-in routine.** The revoke covers every schema, `pg_catalog` included; the operators' and casts' functions come back for `demo` alone. A statement that uses an operator, a cast function or an aggregate would then be refused for any role a deployer or consumer makes. `admin` could not repair it: its own grant has no grant option (F-13). The file's own comment says why the functions matter: "Operators/casts are needed by ordinary expressions". [G-5] | `PR14:engines/postgres/init/10-read-profile.sql:14-15`, `:23-35`, `:29-30` | **If reproduced: P-1.** |
| H-2 | **The hook's `REVOKE` may do nothing, and succeed,** when the creator is not the new owner and does not inherit the owner's rights. [G-4] | `PR14:engines/postgres/read-policy/read_policy.c:31-38` | The hook refuses such a creation before it starts, and afterwards confirms that `PUBLIC` holds neither privilege. |
| H-3 | **An error in the hook after the copy may leave the copied files with no database.** [G-4] | `PR14:engines/postgres/read-policy/read_policy.c:24-38` | **If reproduced, it is resolved before the merge** (below). |
| H-4 | **The role name `admin` is compiled in.** If the role is missing or renamed, every `CREATE DATABASE` fails, after its copy. | `PR14:engines/postgres/read-policy/read_policy.c:32-33` | **The hook names no account.** |
| H-5 | **The hook closes `TEMPORARY` only.** | the same | **Extend:** `CONNECT` too (4.1). |
| H-6 | **A role may change its own password and its own settings.** `ALTER ROLE demo SET statement_timeout = 1` would break every later `demo` session. [G-6] | — | **Extend:** 4.5. |
| H-7 | **A reader may still write a catalog row:** `ALTER DEFAULT PRIVILEGES` for itself. [G-6] | — | **Extend:** refused with H-6's rule. |
| H-8 | **`NOTIFY` is a statement, not a routine** [I]. The page says notifications "receive no `demo` grant". | `PR14:docs/strict-read-account.md:3` | **Correct the page.** `NOTIFY` stays allowed: it stores nothing. [D] |
| H-9 | **The event trigger also names `admin`.** | `PR14:engines/postgres/read-policy/read_policy--1.sql:9-11` | **Fix:** it checks that the role exists. |
| H-10 | **The event trigger is enabled in the ordinary way,** so a session in replica mode may skip it [I]. | `PR14:engines/postgres/read-policy/read_policy--1.sql:19-20` | **Set `ENABLE ALWAYS`.** |
| H-11 | **Which commands can make a routine, and who covers each.** [I] | `PR14:engines/postgres/init/10-read-profile.sql:18-20`; `PR14:docs/strict-read-evidence.md:22` | **Test the table** (T-7). |
| H-12 | **The library is named in the PostgreSQL data directory's configuration.** A policy image started on data from before the policy would run with the hook and without the grants. | `PR14:engines/postgres/Dockerfile:83` | **Keep the line, and add a marker** that PostgreSQL's start wrapper checks. [D] |
| H-13 | **The headers' package is taken from the network at build.** | `PR14:engines/postgres/Dockerfile:13` | **Record it** with the image's other inputs. |
| H-14 | **What a role with no grant can still do:** anonymous `DO` blocks; `SET`; `LISTEN`; a held cursor; a share lock on what it may read. [I] | — | **Document** as the profile's limit, once the reviewer has confirmed that none stores anything. |
| H-15 | **A role that may create databases can create one of any name, from any template,** and rename its own to any name. So a namespace's owner could make a database outside its namespace, copy `template0`, or take a name another namespace is about to be issued. | PostgreSQL's own rule; nothing in the pull request | **The hook confines it** (below). [106-4] |

**H-3's resolution, if the gate reproduces the leak.** [D]
1. **Everything the hook can know beforehand is refused beforehand,** before any file is copied.
2. **The step after the copy may not raise for a reason of its own.**
3. **T-7 forces each failure that was reachable** and shows it is now refused before the copy, with no file left.
4. **If any raising path after the copy remains,** or the leak shows without the hook at all, the work goes back to the two deciders with what was found.

**What the hook does after this design.** [D]

| # | When | What |
|---|---|---|
| 1 | Before `CREATE DATABASE` | Refuse, when the creator would not hold the new owner's rights. |
| 2 | Before `CREATE DATABASE`, and before `ALTER DATABASE … RENAME`, **by a role that may create databases and is neither a superuser nor a holder of `CREATEROLE`** | **The name must begin with the prefix of a namespace the role owns,** read from its membership in `megasamples_copy_<prefix>_owner`. **The template must be a closed service template:** marked a template, accepting no connections, a superuser's, named `…_start`. Otherwise refuse. A role of that kind that owns no namespace can create nothing. [G-29] |
| 3 | After `CREATE DATABASE` | Close `CONNECT` and `TEMPORARY` on the new database to `PUBLIC`; then confirm it. |
| 4 | Before `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES` | Refuse, when the caller is neither a superuser nor a holder of `CREATEROLE`. [G-6] |

- **It names no account and holds no state.** It reads the catalog, and nothing else.
- **Rule 2 is what makes a PostgreSQL namespace owner's credential safe to use away from the service** (3.5). It is built in this work. Until [G-29] shows it refusing direct SQL, that use is not claimed, and `accounts check` reports any database a namespace's owner holds outside its namespace.
- **Rule 2 does not bound bytes.** A namespace's owner can still fill the disk with copies of its own, outside the CLI's reservations.

### 4.4 MySQL's accounts

Decided here [D]. **Every schema pattern has each underscore escaped** (2.1).

| Account | Privileges | Change |
|---|---|---|
| `root@localhost`, `root@'%'` | everything | none |
| `admin@'%'` | everything, with the grant option | none (4.7) |
| `demo@'%'` | `SELECT, SHOW VIEW` on each working sample schema, by its exact name; `SELECT` on `megasamples`' registry and service tables; **and on each foreign namespace that the configuration marks as readable by `demo`,** by its pattern | **narrowed** from `*.*` |
| **a namespace's owner,** such as `copier@'%'` | on its own pattern, such as `copy\_%`: what making, filling, using and dropping a copy needs, **without the grant option.** On each template, by exact name: `SELECT`. On `megasamples`: `SELECT`, and row changes on its own ledger and its rows of the storage table. | **new**; locked until its key is set |

- **`demo` no longer reaches the `mysql` schema,** where account rows are, nor a template. [G-11]
- **`demo` reads a consumer's own schemas only where the configuration says so:** `foreign: [{prefix: P, demo_reads: true}]` grants `SELECT, SHOW VIEW` on that namespace's pattern, and nothing wider. The default is that it reads none. [106-9]
- **The owner holds no grant option.** [D: review 1's findings 2 and 13.]
- **A grant by exact name outlives a reset** [G-12]. A schema `admin` makes later is not `demo`'s to read until `admin` grants it. [D]
- **The namespace is enforced by the engine:** its owner holds nothing outside its pattern. [G-11]
- **An account that manages accounts can change the service's own.** A deployer or a consumer may add one. Whether it can alter, lock or drop a namespace's owner, a consumer's reader or `demo`, and what protects them, is [G-28]. Until that gate passes, the use of a MySQL namespace owner's credential away from the service is not claimed (3.5). [106-5]
- **MySQL stays not claimed strict:** named locks, and the two definer views of `employees`, are as F-14 found them.

### 4.5 Passwords, and the accounts' check

**An account changing its own password.** A read account's credential is usually shared: by the consoles, the probe, and every consumer given it. A holder who changes it locks the others out, and can set it to a value everyone knows.

| Engine | What the product does | Mark |
|---|---|---|
| **PostgreSQL** | **Refuses it,** by the hook's fourth rule (4.3), for every role without `CREATEROLE`. | [D] [G-6] |
| **MySQL** | **Not known to be possible. Gate G-16 establishes it first.** It tries every statement by which an account can change its own password, and each mechanism of the pinned server that might refuse it, and reports each by name with what else it breaks. | [G-16] |

- **If G-16 finds a refusal that keeps `demo` usable** by the consoles, the probe and a consumer: it is built.
- **If it finds none** (and likewise on PostgreSQL if G-6 fails), the product says so and gives three mechanisms [106-6]:
  - **a key of its own for MySQL's `demo`,** `MYSQL_DEMO_PASSWORD`, so that it can be kept and rotated apart from PostgreSQL's;
  - **a reader for each consumer** (`accounts reader`), so that one consumer's change of its password locks out only itself;
  - **detection and repair** (below).
  How a deployer uses them is a consideration of section 5.3, not a rule of the product.

**`megasamples accounts check`** compares what is there with what is expected, as the engine's administrator, where the service runs. **What is expected is written down** [D: review 2's finding 7]: the image's own grants and memberships, and the enrollment record (4.6). It reports, and exits 7 if anything is found:

| What it finds | Which is |
|---|---|
| A grant or membership that reaches a working copy, a template, a namespace or the registry, and is neither the image's nor in the enrollment record | **unexpected:** stale, made by hand, or overlapping |
| An enrollment in the record with no grant or membership behind it | **missing** |
| A grant, exact or by pattern or through a role, on a schema that does not exist | **dangling** |
| A database or schema in a namespace with no row in its ledger; a database a namespace's owner holds outside its namespace | **unmanaged**; **drift** |
| A service account whose configured password is refused | **changed** |
| An operation, or a maintenance marker, that is not settled | **unsettled** |
| On PostgreSQL: the policy's library not loaded, or its marker not current | **policy** |
| A listener wider than loopback with a published password still in force (5.2) | **exposed** |

- **`--repair`** applies the configured passwords again, locks an account whose key is unset, and gives again what is **missing**. **It revokes nothing.** What is unexpected is an administrator's to remove, knowingly.
- **A legitimate enrollment is expected,** so an audit after one finds nothing. T-9 holds that.
- **`reset` looks for unexpected grants on a working schema's name before it makes that schema again,** and refuses if it finds any (2.4, step a). Copies need no such check: no copy's name is used twice.

### 4.6 Enrollment: who may use working copies and a namespace's copies

Reading or writing the samples is by the account used (DL-076). **Enrollment is at the scope of the working copies or of one namespace.** [106-10]

```
megasamples accounts enroll   ENGINE --role ROLE --access read|write (--working | --prefix P)
megasamples accounts unenroll ENGINE --role ROLE (--working | --prefix P)
megasamples accounts list     ENGINE
megasamples accounts restore  ENGINE
```

| | PostgreSQL | MySQL |
|---|---|---|
| **What enrolling does** | makes the role a member of one scope's read or write group (4.1) | grants, by escaped name or pattern, `SELECT, SHOW VIEW`; for `write` on working copies, `INSERT, UPDATE, DELETE` as well |
| **`write` in a namespace** | yes | **not offered:** exit 4. Its owner is the only ordinary writer (2.4). |
| **A reset of one database** | keeps it: a membership is not in the database | keeps it: the grant is by name [G-12]; a reset suspends a writer's while it runs (2.4) |
| **A whole engine's reset, or a new image** | removes it. **`accounts restore` replays the record.** | the same |

**The enrollment record.** [D: review 2's finding 7.] [106-17]
- **Each enrollment is written down before it is granted,** in two places: the server's `megasamples.enrollments`, and an enrollment file where the service runs, which holds no secret and which a new volume does not touch.
- **`accounts restore`** replays the file into a new server, for each role that exists there, and names each that does not. Its rehearsal is part of T-22.
- **Every path that grants validates the namespace and the principal first:** the prefix is a configured one; a copy's creator is that namespace's owner; an enrolled role passes admission.

**Admission is by what a role can do in effect.** [D: review 2's finding 8.] A role is enrolled for `write` only if, itself or through any role it inherits or can take up, all of these hold:

| It must not | Read from |
|---|---|
| be a superuser, or hold `CREATEDB`, `CREATEROLE`, `REPLICATION` or `BYPASSRLS`; on MySQL, hold any global privilege or grant option | the role catalog; `SHOW GRANTS … USING` |
| own any object in any sample database, template or copy | PostgreSQL's shared dependency catalog, from one connection [G-23] |
| hold any privilege there that is not the scope's own: a schema's `CREATE`, a table's grant, a routine's | the same; on MySQL the grant tables |
| own a namespace, or be a member of an administrator | the memberships |
| be a reserved service identity | the list below |

- **Reserved identities.** `demo` is promised read-only: it is never enrolled for `write`, on either engine. `postgres`, `root`, `admin`, the groups and a namespace's owner are not enrolled at all.
- **Changing a role's access in one scope** replaces it: from `read` to `write` the read membership or grant is removed as the write one is given, and the reverse. A role is never in both of one scope.
- **One role in several scopes** is allowed, at different levels. On PostgreSQL that is safe because write grants are scoped (4.1) [G-23]; on MySQL because each grant names its schemas.
- **Unenrolling takes effect for new sessions.** Whether it reaches a session already open, on each engine, is [G-27].
- **Nobody is enrolled for `write` as shipped.** [106-16] The service ships no `editor` account: an editor is whatever role `admin` makes and enrolls.

**Who can write a copy.** [106-10]
- **A copy's ordinary writers** are its namespace's owner, and on PostgreSQL every role enrolled to write that namespace. `copy create` returns them as `writers`, and `exclusive` is true only when the owner is the one.
- **While a copy is being made** nobody but its owner can reach it on PostgreSQL, and nobody but its owner can write it on MySQL.
- **Afterwards,** two roles enrolled to write one PostgreSQL namespace can change each other's copies. **A caller that needs to be the only writer uses a namespace whose one writer is its owner,** and reads `exclusive` to know. Even then the administrators can write.

### 4.7 What `admin` can do

| | PostgreSQL | MySQL |
|---|---|---|
| Sample data | owns it: reads, writes, alters, drops | all privileges |
| A working copy | owns it; resets it | drops and refills it |
| A template | copies it; cannot connect to it, alter it or drop it [G-1] | reads it; can change its read-only option [G-10] |
| A test copy | **owns its tables. It can connect whenever it holds, or inherits, a role enrolled in that namespace, and it can enroll itself.** It cannot drop the database. | everything |
| Accounts | makes roles; changes those it made; cannot change `demo`, a namespace's owner or `postgres` [G-6] | makes and changes any account |
| Sessions | **new:** ends any that is not a superuser's | ends any |
| The server | not a superuser | in effect the administrator |

- **PostgreSQL's `admin` gains one thing:** `pg_signal_backend`, because a reset must end `demo`'s sessions. [D] [G-3]
- **MySQL's `admin` is not narrowed.** [D: narrowing it needs partial revokes, which 2.4 rules out.]
- **One key, `ADMIN_PASSWORD`, is `admin` on both engines:** whoever holds it is PostgreSQL's owner of all sample data and MySQL's administrator at once. [106-14]

### 4.8 A consumer's own roles and databases, and what a copy inherits

**What a database inherits from the one it is copied from** [G-2]:

| Copied with it | Not copied: set anew for each database |
|---|---|
| tables, rows, indexes, views, routines, triggers, sequences | its owner |
| each object's owner, which stays `admin` | `CONNECT`, `TEMPORARY` and `CREATE` on the database |
| each object's privileges: the read group's; the owner-relative write grant; the routine floor | settings made for the database |
| default privileges | its comment |
| the policy's extension and event trigger | whether it is a template and whether it accepts connections |

And one thing is **given in each database after it is made:** its scope's write grant (4.1).

**A consumer may have `admin` make roles and databases of its own** on the server: test fixtures, for one. Every database is a copy of some template, so the profile reaches them too:

| Thing | What it has | What it lacks |
|---|---|---|
| A role `admin` makes, in a database copied from `template0`, `template1` or a template of the consumer's own | the routine floor, through `PUBLIC` (P-1); whatever its maker grants | `TEMPORARY`, unless its database's owner grants it; `EXECUTE` on a routine made there, unless its owner grants it |
| The same role, in a test copy of a sample | once enrolled in the copy's namespace: `CONNECT`, the tables' `SELECT`, the floor | any write, unless enrolled for it; `TEMPORARY` |
| The same role, in a working copy | nothing, unless enrolled: it cannot connect | — |

- **Pull request #14's revocations reach every one of these,** because both of PostgreSQL's own templates carry them. With P-1 such a role keeps the built-ins a reader needs.
- **Permissions are kept through template creation, a copy and a reset:** T-5 holds each to a fingerprint.

### 4.9 Effective access, and each credential's authority

**An account reaches whatever any role it inherits reaches.**
- **The rule.** On PostgreSQL an account holds a privilege if it, a role it inherits directly or through other roles, or `PUBLIC` holds it. `SET FALSE` stops it from becoming that role; it does not stop the inheritance.
- **So when `admin` inherits a role that is enrolled in a namespace,** which a consumer's set-up may arrange (F-23 is one that does), `admin` inherits `CONNECT` on that namespace's copies, and it already owns their tables.

**What each account reaches, by the grants it holds itself.** Each cell is the expected value of a test (T-4), tested held directly, inherited through one role, inherited through two, and held as a role that can only be taken up.

*PostgreSQL:*

| Account | A working copy | A template | A copy in a namespace it owns or is enrolled in | A copy in another namespace | A consumer's own database | `megasamples` |
|---|---|---|---|---|---|---|
| `demo` | reads | refused | reads, if enrolled | refused | refused, unless granted | reads |
| a namespace's owner | refused; **reads, and only reads, if enrolled to read** | copies it; refused a connection | owner; reads and writes rows | refused | refused | reads; writes its own ledger |
| a role enrolled to write one namespace | **reads only, if also enrolled to read there; otherwise refused** | refused | reads and writes rows | refused | as granted | reads |
| a role enrolled to write working copies | reads and writes rows | refused | **reads only, if also enrolled to read there; otherwise refused** | refused | as granted | reads |
| `admin`, as shipped | owner | copies it; refused a connection | refused, until it enrolls itself | the same | owner, if it made it | reads and writes |
| `admin`, inheriting a role enrolled in that namespace | owner | the same | connects; owns the tables | refused | owner | reads and writes |
| `postgres` | everything | can open it | everything | everything | everything | everything |

*MySQL:*

| Account | A working copy | A template | A copy in its namespace | A copy in another namespace | A declared foreign namespace's schema | `mysql` |
|---|---|---|---|---|---|---|
| `demo` | reads | no privilege | reads, if enrolled | no privilege | **reads, only where marked `demo_reads`** | no privilege |
| a namespace's owner | no privilege; reads if enrolled to read | reads | everything a schema allows, but no granting | no privilege | no privilege | no privilege |
| a role enrolled to read a namespace | as enrolled | no privilege | reads | no privilege | as granted | no privilege |
| a role enrolled to write working copies | reads and writes rows | no privilege | reads only if enrolled there | no privilege | as granted | no privilege |
| `admin`, `root` | everything | reads; can change the option | everything | everything | everything | everything |

**What each credential's holder can do, from any address that reaches the port.** The servers accept every account from every address (F-20). Where a credential's file is kept is a deployer's rule, **not something the server enforces,** unless the deployer has set from where administrators may sign in (5.3).

| Credential | What its holder can do | What bounds it |
|---|---|---|
| `postgres`, `root`; MySQL's `admin` | everything | nothing |
| PostgreSQL's `admin` | own and change all sample data; reset; make databases and roles; enroll any role, itself included, anywhere; end sessions | not a superuser; cannot alter a template, `demo`, a namespace's owner or `postgres` [G-1, G-6] |
| `demo` | read every working copy, and what it is enrolled or marked for. On MySQL: take any named lock; change its own password, unless G-16 finds a refusal | the read profile on PostgreSQL; its grants on MySQL |
| a consumer's reader | read what it is enrolled for; change its own password on MySQL | its enrollment |
| **a namespace's owner, MySQL** | every copy of its namespace, whoever made it. Take any named lock. Fill the disk within its pattern. | nothing outside its pattern; no granting [G-11] |
| **a namespace's owner, PostgreSQL** | every copy of its namespace. Take the locks. Fill the disk with copies of service templates under its own prefix. | the hook: no name outside its namespace, no other template [G-29]; it cannot connect to a working copy or a template, nor alter a role |
| a role enrolled to write working copies | change rows of every working copy | no definition change; a reset restores |

- **One credential is one trust domain.** Every holder of a namespace owner's credential controls every copy there.
- **Reserving a name is not owning it.** A namespace's owner owns the copies it has made. It does not own the names the CLI will issue next. On PostgreSQL the hook keeps every other creator out of its prefix [G-29]; on MySQL the patterns do [G-11].

## 5. Configuration, defaults and exposure

The product does not know where it runs: a laptop, a lab, a container platform, behind remote access. [R: `DL:` DL-107 item 1] **So its defaults must be safe when nothing is known, and everything else is configuration that a deployer chooses on purpose.**

### 5.1 The configuration

Decided here [D]. `megasamples.yaml` is the one file (`SM:megasamples/config.py:1-15`); `.env` holds the passwords (3.4).

| Key | What it sets | Default | Baked? |
|---|---|---|---|
| `engines.<engine>.datasets` | which datasets an engine has | today's | yes |
| `engines.<engine>.templates` | which databases get a template: a selector, a list, or `none` | `core` | yes |
| `engines.mysql.binary_log` | MySQL's binary log | `true`, as the image is today | no: at start |
| `engines.mysql.copy_limit_mb` | the largest database a logical copy is offered for | 512 | yes |
| `templates.budget_mb` | the most the selected templates may add on one engine | 4096 | checked at build |
| `storage.headroom_mb` | the space given to copies and resets on one engine | none: **copies are not offered until it is set** | no |
| `copies.namespaces` | each prefix, its owner, and its limits | one: `copy`, owned by `copier` | yes |
| `copies.foreign` | prefixes a consumer keeps for objects of its own; each may be marked `demo_reads` | none | yes |
| `network.bind` | the address each engine and console listens on | `127.0.0.1` for every one | no |
| `administrators.allow_from` | from which addresses `postgres`, `root` and `admin` may sign in: a list, or the word `any` | unset | no |

- **`network.bind` is new.** Today every port binds to loopback and the only way to widen it is to edit a generated file that the next start rewrites (F-28). A setting is the honest form of "a deliberate edit". [D]
- **`administrators.allow_from` is new.** On PostgreSQL it becomes host rules for those roles, ahead of the general one; on MySQL it becomes those accounts' host patterns. Whether it can mean anything depends on what address the server sees a client come from, which depends on the deployment (5.3). [G-22]

### 5.2 Defaults safe for an unknown network

Decided here [D]. Each is what the product does when the deployer has said nothing.

| # | Default | Why it is safe where nothing is known |
|---|---|---|
| 1 | **Every engine and every console listens on loopback only.** | Nothing is reachable from another machine. It is today's rule (F-28). |
| 2 | **A wider listener is refused while any account still has its published password.** `megasamples up` stops, naming each key that is unset. | The published passwords are for a database nobody else can reach (`SM:.env.example:5-9`). They must not meet a network by one edit. |
| 3 | **A wider listener is refused until `administrators.allow_from` is set,** to a list or to the word `any`. | Whether administrators can be reached from the network is the deployer's decision to make, not an accident of the topology. |
| 4 | **A namespace's owner is locked until its key is set.** | The right to create databases is behind no published password. |
| 5 | **Nobody is enrolled to write.** `demo` can never be. | A working copy changes only by an administrator, until someone is enrolled on purpose. |
| 6 | **`accounts export` does not export an administrator's or a superuser's credential.** | The tool that hands credentials out cannot hand out the ones that can do everything. A deployer who wants them elsewhere moves them knowingly, by other means. |
| 7 | **`demo` reads no consumer's own schemas.** | A foreign namespace is another party's until the configuration says otherwise. |
| 8 | **Copies are not offered until the deployer has given them headroom.** | The product does not guess what a disk can bear. |
| 9 | **A reset discards nobody's session unless told to; a sweep removes nothing it cannot prove; a password is read from nowhere ambient.** | 3.6; 2.2; 3.4. |

- **What a default does not cover.** A forward, a proxy, or an orchestrator's service that exposes a loopback listener is outside the product, and the product cannot see it. `megasamples whoami`, run from where a consumer is, shows that the path exists.

### 5.3 What a deployer weighs when exposing it

The product gives mechanisms. Which to use is the deployer's, and none is a premise of the product. [R: `DL:` DL-107 item 2]

| What to weigh | What the product gives | What stays the deployer's |
|---|---|---|
| **Who can reach the ports** | `network.bind`; defaults 1 to 3 | Any forward or proxy outside the product. |
| **The transport** | PostgreSQL's passwords are not sent: the rule is SCRAM for every address (`SM:ARCHITECTURE.md:166-167`). **The product configures no TLS on either engine** (`MR:` B-04, from its search of `SM:engines/`). | A tunnel, or a network the deployer trusts, for anything beyond the machine. |
| **Passwords** | One key for each account (3.4). **Rotation:** set the key and start again, or `accounts check --repair`. **Revocation:** clear a key, and the account is locked. | When to rotate, and who is told. |
| **Administrators' reach** | `administrators.allow_from`, where the server sees a different address for a client that should be refused. **`megasamples whoami` shows the address the server sees,** so a deployer can find out from each place. | If every client looks the same to the server, **no rule can tell them apart,** and the administrators are reachable wherever the port is. Then only custody of their credentials protects them. |
| **A shared read credential** | `demo` is one account. Any holder reads the samples. On MySQL a holder may also change the password, unless G-16 finds a refusal (4.5). | Give `demo` only to the machine's own consoles, and **a reader of its own to each consumer** (`accounts reader`), where one consumer must not be able to lock out the others. |
| **Who makes copies** | **A namespace and an owner for each consumer that must be kept apart** (2.1). Its authority is 4.9's table. | How many namespaces to bake, and which to leave locked. |
| **A copy owner's credential away from the service** | On PostgreSQL the hook confines it to its namespace and to service templates [G-29]. On MySQL its grants do [G-11]. | **It can still fill the disk,** and on MySQL make commands report busy. The CLI's limits bind the CLI. A volume's own limit is the deployer's. |
| **A consumer that manages accounts** | A declared foreign namespace keeps the product out of the consumer's objects. | An account that manages accounts may be able to change the service's own [G-28]. Give such an account only to a consumer that is trusted with that. |
| **Handing a credential over** | **`accounts export`: one credential, alone, to one private file,** never the `.env`; and a line in a custody record where the service runs, with the account, whom it is for and when, **and no value.** [106-2] | The channel it travels by. |
| **Write access to the samples** | Enrollment (4.6): scoped, recorded, admitted by effective privilege. A reset restores the data. | Who is enrolled, and whether that role's credential is handed over. |
| **Storage** | The build's report; the budget; the headroom and its reserve (2.6). | The volume's size. |

### 5.4 Changing a deployment

- **A new image renews the data volumes.** Everything made on the old ones goes: copies, a consumer's own roles and databases, edits, enrollments. Enrollments are replayed from their record (4.6).
- **Image and data must match.** On PostgreSQL an image without the policy's library is meant not to start on policy data, and the policy image refuses data without its marker (H-12). On MySQL nothing refuses: everything this design adds there is in the data. SQLite has no such pairing.
- **The procedure for one such change, with its gates and its rollback, is the repository's runbook.** It is written today for one deployment (F-29). The route this work adds to it, an image replaced with no rotation of every password, is general, and T-22 rehearses it.

## 6. The contract and its versioning

What a consumer pins, and what stays on a disk or in a server. [106-7]

| Thing | Where it lives | Its own version |
|---|---|---|
| The JSON envelope and each result | standard output | `schema` |
| The commands and options; the exit codes and their promises; the lock protocol of 2.2 and 3.6; the names (`_start`, the groups, a copy's issued form) | the command line, the process, the server | `interface` |
| The `.env` key names and the `--env-file` grammar (3.4) | a private file | `interface` |
| `megasamples.yaml`'s keys (5.1) | the service's configuration | `interface` |
| The service's record | a comment or a table in the server | the tag `megasamples-service/1` |
| A template's record | the same | `megasamples-template/1` |
| A copy's row, and its holds; a copy's comment on PostgreSQL | a ledger | `megasamples-copy/1` |
| An operation's row, **with its identity and its terminal outcome** | `megasamples.operations`; the maintenance record | `megasamples-operation/1` |
| An enrollment | `megasamples.enrollments`; the enrollment file | `megasamples-enrollment/1` |
| A storage reservation | `megasamples.storage` | `megasamples-storage/1` |
| A custody record's line | a file where the service runs | `megasamples-custody/1` |
| SQLite's manifest; its sidecar | files on the consumer's disk | `megasamples-manifest/1`; `megasamples-sidecar/1` |

**The rules.**
- **Version 1 of each is fixed at the merge into `main`.**
- **Within a version, only additions,** and a reader obeys these, which are tested:
  - a member it does not know is ignored;
  - an exit code it does not know is treated as 8;
  - a state it does not know is not usable: the copy is not used and not removed;
  - a sweep's reason it does not know means the copy was kept.
- **Any break raises a number: the one of the thing that broke.** A changed sidecar gets a new sidecar tag, not a new `interface`. [D: review 2's finding 15.]
- **A format held in a server is matched exactly, or refused.** A CLI whose tags are not the server's changes nothing there: exit 5, `format-unknown`. A new image renews the volumes, so a server's records are always its own build's and are never migrated.
- **A consumer's files are read one format back, for identification and reporting only.** Such a copy is kept and reported. It is not renewed, held or swept. It is removed only by an explicit `copy drop`. Staging again replaces a manifest; it does not touch a copy's sidecar.
- **An unknown format is refused before any change, clean-up included.**
- **Every break is recorded where it is made,** with a note of what it breaks and for whom. Who must approve one is the governance of whoever maintains the repository; for its present maintainers that is in 7.5.2.

## 7. Deployment profiles

**Examples of configuration.** None is a premise of the product, and a deployer's own will differ. Each shows which of 5.3's mechanisms it uses.

### 7.1 A laptop

The default. Nothing is set.

- **Listeners:** loopback. **Passwords:** the published ones. **Namespaces:** `copy`, locked.
- To make copies: set `COPIER_PASSWORD` and `storage.headroom_mb`.
- **What it relies on:** that only the person at the laptop reaches loopback.

### 7.2 A server shared on a network

A lab, a team, an office.

```yaml
network: {bind: {postgres: 10.0.0.5, mysql: 10.0.0.5}}      # consoles stay on loopback
administrators: {allow_from: [127.0.0.1/32, 10.89.0.0/24]}  # or `any`, said on purpose
copies:
  namespaces:
    - {prefix: copy_a, owner: copier_a}
    - {prefix: copy_b, owner: copier_b}
    - {prefix: copy_c, owner: copier_c}                     # baked, left locked
storage: {headroom_mb: 20000}
```

- **Every password is set** before the first start; default 2 refuses otherwise.
- **`whoami`, run from a consumer's machine and from the server,** tells whether `allow_from` can mean anything here.
- **Each consumer gets a namespace's owner and a reader of its own,** each exported alone. `demo` stays with the consoles.
- **What it relies on:** whatever the deployer decides about the network. The product claims no TLS (5.3).

### 7.3 A container platform

A job's services: the engines beside the job, gone when it ends.

- **Listeners:** the platform's service address, so every password is set, from the platform's secrets, each mounted as a private file and named with `--password-file`.
- **`administrators.allow_from: any`,** said on purpose: every client is a container the job started.
- **One namespace for the job.** A whole engine's reset is starting the service again.
- **Nothing here needs a container runtime inside the job:** the remote commands use the port (3.5).

### 7.4 Remote access

A server reached through a tunnel or a VPN.

- **Listeners stay on loopback,** and the tunnel ends there. The product sees every remote client as a local one: `whoami` shows it. **So `allow_from` cannot tell an administrator at the far end from one at the server.**
- **Custody is then the only protection of the administrators' credentials,** and the tunnel is the only protection of the transport.

### 7.5 DataIntent's development instance

One deployment, by the product's present maintainers. Its records are DataIntent's; this section points at them. **Nothing here is the product's.** [R: `DL:` DL-107 item 3]

#### 7.5.1 Its configuration

| | This instance | Where it is recorded |
|---|---|---|
| **Exposure** | Loopback in the product's own configuration, forwarded to a LAN by two socket units outside the product (F-30). **So the product's defaults 2 and 3 do not see it:** every password was nonetheless rotated at the first rollout, and where administrators may sign in from must be decided explicitly (7.5.2). | `DL:` DL-075; DL-079 item 6 |
| **Datasets** | 33 on MySQL, in 30 databases (F-8). | `SM:docs/live-upgrade-runbook.md:97` |
| **Templates** | `core` to begin with; **the selection on each engine is made at the rollout's approval, from the storage report.** [106-18] | 7.5.9 |
| **Namespaces** | One for each machine or consumer that makes copies, **and spare locked ones for the machines known today.** [106-1] None begins with `di`. | 7.5.2 |
| **Foreign namespaces** | `di`, marked `demo_reads: true`. | below |
| **MySQL's binary log** | May be turned off at the rollout's approval, after G-18 and the storage report. [106-13] | 7.5.9 |

- **`di` is DataIntent's own.** Its fixture makes `di_…` databases and roles (F-16), and plans a `di_admin` on MySQL (F-30). Declaring `di` foreign keeps every copy out of it: a copy cannot be named `di_…` here, and F-05's wording and the fixture's name guard do not cover a copy. Its approvals name the copy namespace separately.
- **`demo` keeps its sight of the `di_…` schemas on MySQL.** DL-079 item 3 allowed that sight and a DataIntent case asserts it. The deciders kept it, through a grant confined to those schemas (DL-106). **In the product that is `demo_reads: true` on a declared foreign namespace** (4.4), and nothing more. [106-9]

#### 7.5.2 Its policy

Each is this deployment's choice among 5.3's mechanisms. Section 11 says which of DL-106's decisions these are.

| Policy | What it uses |
|---|---|
| **No administrator's or superuser's credential leaves the machine:** `postgres`, `root`, `admin` on either engine, `di_admin`, its provisioning and fixture credentials. [106-2] | Custody; the product's default 6 for the first three. |
| **Where administrators may sign in from.** [106-3] The first thing is an observation of this instance, through its real forward (`whoami` from the machine and from the LAN). If the servers see different addresses: `administrators.allow_from` is set, and shown before the rollout by three cases: a LAN reader signs in; a LAN administrator is refused; the fixture still reaches `postgres` through the published port from the machine. If they see the same: no boundary is claimed, and the administrators are recorded as reachable from the LAN, in DataIntent's lines register. A change to a listener, a forward or a firewall is a host permission that stays reserved, put to the owner once with that observation. | `administrators.allow_from`; `whoami` |
| **A PostgreSQL namespace owner's credential stays on the machine until G-29 has passed.** [106-4] A MySQL one, until G-11 and G-28 have, **the latter against `di_admin` as planned.** [106-5] | 3.5's two conditions |
| **Each credential is sent alone, and each sending is recorded** by namespace and machine. [106-2] | `accounts export` |
| **MySQL's `demo`, if G-16 finds no refusal:** it stays on the machine with a key of its own, **rotated at this rollout,** which ends the value every LAN machine already holds; each LAN consumer gets a reader. The owner is told that this narrows DL-075 item 5 for MySQL. [106-6] | `MYSQL_DEMO_PASSWORD`; `accounts reader` |
| **The first write enrollment on this instance is the two deciders' decision,** after the controls of `ED:` R-39. So is the leaving of that role's credential, which is DL-076's LAN editor. [106-16] | Enrollment |
| **Its automation resets one database at a time, unattended, and no MySQL working copy** until MySQL has a door. That answers the editing record's question 6. [106-12] | `reset --unattended` |
| **Its harness holds every copy it uses.** `ED:` criterion 11, "never a copy in use", **is recorded as not passed** for an idle MySQL session and an open SQLite file (2.2). [106-11] | `copy hold` |
| **A result that needs exclusive writing counts only in a namespace whose one writer is its owner** (`ED:` R-35), read from `exclusive`. [106-10] | 4.6 |
| **After the merge, every break of the contract is a recorded decision of the two deciders,** with the pull request's impact note as its brief. An addition needs none. [106-8] | Section 6's last rule |

#### 7.5.3 What else this means for DataIntent

Not decided here. Each is a consequence its own records take up.

- **A copy's name is issued.** The harness keeps the name and the identity it was given, and finds a copy by its label after a lost reply.
- **Access to a copy is by enrollment in its namespace** (4.6), where the service runs, replayed after a whole engine's reset.
- **`admin` reaches a copy once a fixture role is enrolled,** because the fixture gives its roles to `admin` (F-23; 4.9).
- **The provider's list of databases does not gain the templates:** it leaves out every database marked as a template (F-17), and each `_start` is one. A raw catalog query shows them; the registry does not list them. Each of the three is tested apart. [D: review 2's P3.]
- **A fixture role cannot connect to a working copy** unless enrolled. It could before, and read nothing.
- **The fixture grants `EXECUTE` on its own routines,** and `TEMPORARY` where a case needs it (4.8).
- **A fixture role cannot change its own password or settings** on PostgreSQL. `admin` still sets them.
- **MySQL's `demo` no longer reads `mysql`.** What the provider then says of its list is checked in C2 (7.5.6).
- **An unknown outcome of a reset** is read with `reset --status --operation`.
- **Its harness maps the exit codes to its own results** (`ED:` 4.2): 3 and 4 are Not run, with the reason; 2, 5 and 7 are Failed; 6 is a deferral; 1 and 8 are Failed, and it reads the state before it asks again. "Unsupported" is not among them: DataIntent keeps that word for its own product.
- **Its SQLite staging** can take `template stage`'s directory and manifest in place of its own capture (`ED:` 3.5).
- **Its dependency review** covers the package at one commit with two drivers (`ED:` 4.4).

#### 7.5.4 Its one rollout: what changes on the instance

It is this instance's second live rollout and the only one planned (DL-085 item 2; DL-103 item 2). It carries, from one build of the final `main`, everything in sections 2 to 6, the finished README, and the build revision in each registry row, which DL-079 item 5 put no later than this rollout.

| | Change |
|---|---|
| **Images** | All three engines' images are replaced. Each holds the finished README (F-25). |
| **Accounts** | As sections 4.1 and 4.4: new namespace owners, spares locked; the PostgreSQL groups; `demo` on MySQL narrowed, with `di` readable. Nobody is enrolled for `write`. |
| **Passwords** | `.env` gains one key for each namespace taken into use. MySQL's `demo` gets a key of its own and is rotated, if G-16 found no refusal. The other existing values are not rotated. |
| **Data** | Both data volumes are renewed (`MR:` B-10): DataIntent's roles, `di_template`, its fixture databases, any edit and any enrollment go. Enrollments are replayed. |
| **SQLite** | Each dataset file must be the same bytes as today, unless its dataset changed: held by SHA-256 against a read-only capture taken before. [D: DataIntent pins one of them (`MR:` A-13).] |
| **Unchanged** | **The engines' versions.** Ports, the LAN forwards, the consoles' addresses. |

#### 7.5.5 Its order

Decided here [D], from DL-085 items 1, 3 and 4 and DL-103.

| # | Step | It must show |
|---|---|---|
| 1 | **Psycopg's licence review, then the feasibility gates** of 8.1, on the isolated stack, on a branch that merges pull request #14's branch first (section 9). | Each gate Passed, or its stated consequence taken. |
| 2 | **The build,** test-first, on that branch. | Section 8.2, each with its red and its reversal. The README kept true as it goes (DL-086 item 1). |
| 3 | **DL-078's README,** written by Astra on the same branch, against finished functionality; reviewed by Astra and Fable. | Its review's own two clean rounds. Section 10 is its list. |
| 4 | **The branch's candidate,** built from its head in the isolated store. | The full dataset matrix, the image tests and every native suite Passed. The storage report. |
| 5 | **DL-087's acceptance is recorded.** | Gate 6's declared run met C1. Steps 1 to 4 may come before it. **Nothing from step 6 on does.** |
| 6 | **DataIntent's comparison against that candidate** (7.5.6), the read account's admission among it. | Every part that applies, Passed and complete. This is DL-085 item 3's condition, at item 4's time. |
| 7 | **The reviews:** the independent review of the final hook and the event trigger (4.3); Fable's and Astra's blessing on one head (DL-086). | Both, on the head that step 6 compared. A change after step 6 runs steps 4 and 6 again. |
| 8 | **The merge into `main`,** by a merge commit. | `main`'s tree is the blessed head's tree. **Version 1 of the contract and of each format is fixed here** (section 6). |
| 9 | **One build of the final `main`,** at the merge commit, in the isolated store. | Its image IDs recorded. **This is the build that is deployed.** |
| 10 | **That build is qualified:** the dataset matrix, the image tests and the native suites again, and DataIntent's comparison again, on it. | Complete, every case Passed. It differs from step 4's candidate only by the revision in its registry rows and labels; whether that could excuse any of this is the two deciders', and is not assumed here. |
| 11 | **The two deciders' approval** of one exact plan and revision (7.5.9). | Recorded before any live step. A plan that changes afterwards goes back to them. |
| 12 | **The rollout** (7.5.7), and then **DataIntent's accepting run on the live instance** (7.5.6). | The rollout is accepted only then. The deployment's checkout moves to that `main` (DL-103 item 2). |

#### 7.5.6 DataIntent's comparison, in full

Its record defines five parts and says that from the next upgrade they are as designed (F-24). This is that upgrade.

| Part | What it runs (`MR:` section 3) | Why this rollout needs it | Needs, in DataIntent |
|---|---|---|---|
| **C1** · PostgreSQL's suites | `sample02` (shared, fixture, pure), `results-postgresql`, the `cli` jobs | The profile reaches every role the fixture makes. It is also where the routine list is settled (4.2). | packages 1, 2 |
| **C2** · The MySQL provider probe | sign-in, the listing and each describe, as `demo`, on both servers | **`demo`'s MySQL grants change:** the `mysql` schema leaves its list, and the `di_…` schemas stay. | packages 1, 2, 3 |
| **C3** · SQLite, freshly staged | the provider's reads and the offline example, on files captured from each stack | The SQLite image is rebuilt. Its dataset files must be the same bytes. | packages 1, 2, 4 |
| **C4** · Observed identities | each engine's version and the registry digests | Every registry row's build id changes, from `dev` to a revision (F-7). | package 2 |
| **C5** · The two controls that change an account | **(i)** the read account is elevated before an export: the export is refused, and its stream is empty. **(ii)** the fresh privilege check cannot be made: the export is refused, and its stream is empty. | The read account's privileges are what this rollout changes. | packages 1, 2, 3 |
| **The read account's native admission** | `demo` admitted on the candidate, with no relaxed list; an administrator's alias refused | DL-085 item 4 left it Not run until this profile exists. | package 1 |

- **C5's target and its authority.** Both controls run on each isolated server only, PostgreSQL and MySQL, each authorized for fixture writes by its marker (`MR:` 2.8). The account they change is a `di_…` one the fixture makes, never a service account. [D: review 2's finding 17.]
- **This compares two builds of the service, not two versions of an engine.** The engines' versions do not change. The evidence says "the same engine versions, two service builds". DataIntent's record names this rollout as comparison mode's first use on two versions; **that is not what this rollout gives,** and its evidence does not claim it. [D]
- **One DataIntent revision and one inventory** are declared before the first run and are the same for the comparison against the candidate (step 6), against the final build (step 10) and the accepting run (step 12). A case present in one and missing in another returns to the deciders.
- **Pass means complete:** every case of each part Passed, none Not run, on each target. A triaged failure is not a pass.
- **Before the rollout, the live instance still has today's profile.** [D: review 2's finding 16.]
  - **The candidate half is held to the full gate:** `demo` is admitted there, natively.
  - **The live half, before the rollout, expects the opposite and says so:** the admission's own case asserts that today's `demo` is **refused**, by the read-only capability queries DL-085 item 4 describes. That refusal is the expected result there, recorded as a baseline.
  - **The rest of the live half** runs by the route DL-087's accepted run used. Which route that is, is DataIntent's to name in the declaration; this design does not relax either half to make them match.
  - **After the rollout,** the accepting run expects admission on the live instance too.
- **A part whose prerequisite does not exist is not left out quietly.** The step waits, or the two deciders rule on that part by name, in writing, before the step. What is given up is recorded as lost, not passed.
- **Each failure before the merge is triaged to the service or to DataIntent** (DL-085 item 3).

#### 7.5.7 The rollout, and its verification

The order is the repository's runbook's [R at each line of `SM:docs/live-upgrade-runbook.md`].

| # | Step | The runbook's place |
|---|---|---|
| a | Preparation while the live servers run: the backup directory, the retained images and configuration, the archive gates, the rollback set rehearsed in a fresh store, the final build's images imported. | `:268`; importing leaves the running containers as they are (`:630`); an abort here changes nothing (`:936`) |
| b | A quiet point, as the coordinator's direction sets it: DataIntent's writers stopped, its standing permission to start the services suspended (`:181`), restart automation paused (`:1094`). | `:1045` |
| c | The capture, then the stop: consoles, then SQLite, then PostgreSQL and MySQL (`:1082`). | DL-088's gate: a missing capture holds before downtime |
| d | **The four checks** (`:1277`). | A refusal or a hold blocks the copy, and has its own route |
| e | Cold copies of each data mount, with their digests. The old volumes are kept (`:1166`). | — |
| f | `.env` gains each new key, generated without printing. `megasamples.yaml` gains its keys. | as the first cutover set its four (`:1170`) |
| g | The stack is started on the imported images with fresh volumes. **Nothing is rebuilt here** (`:1192`). The running image IDs are step 9's (`:1202`). | — |
| h | Verification before clients resume, below. | `:1461` |
| i | Restart automation restored (`:1238`); the hold released; DataIntent's credential files refreshed, its fixture set up again, and **the enrollments replayed.** | — |

**Before clients resume,** read-only except where said [D]:
- each engine's version, and each registry row with its build id;
- **every account:** its configured password signs in, and a wrong one is refused as an authentication failure. **Where MySQL's `demo` was rotated, its old value is shown refused, and each console and the probe are shown signed in;**
- **every template:** its properties, and a connection or a write refused for each account;
- **`megasamples accounts check` finds nothing** (4.5);
- **the three cases of `administrators.allow_from`,** if it was set (7.5.2);
- **one round trip on each server engine,** as a namespace's owner: a copy of `pubs`, a hold, a read, its drop;
- **one reset of `pubs` by the template path, unattended,** on PostgreSQL;
- SQLite's files against the capture.

#### 7.5.8 The rollback

The routes are the runbook's [R at each line]; choosing among them is as it says.

| When | Route | What is lost |
|---|---|---|
| Before the stop | Abort the preparation (`:936`). | nothing |
| The stop was refused, or the gate did not pass | Restart the original containers on their unchanged volumes (`:809`). | nothing |
| After the candidate started | Stop the candidates behind the same capture and gate; then restart the exact originals on the volumes that were kept (`:2215`), or restore the cold copies (`:1776`). | what was written to the candidate. Its volumes are kept. |

- **A rollback is of the whole engine,** and image and data must match (5.4).
- **After a rollback** `.env` is the kept original, DataIntent's fixture is set up again, and each credential that was exported is recalled by its custody record. **Where MySQL's `demo` was rotated, the old shared value is in force again,** and each consumer goes back to it.
- **The rollback has never restored the live instance** (DL-087 item 8). Its rehearsal is T-22.
- **How long the rollback's inputs are kept.** The first rollout's stay under their own rule: until its accepting run and DataIntent's package 3's gate have both passed (F-24). This rollout's are kept until its accepting run has passed **and** package 3's gate has passed on the instance as it then is.

#### 7.5.9 What is approved, and by whom

**The two deciders give the specific approval for this rollout, on one exact plan the coordinator directs.** [R: `DL:` DL-105; `DI:docs/bootstrap/approvals.md`, MEGASAMPLES-ROLLOUT-2, at `6ac5373c`] **The plan is DataIntent's record, not this one.**

- **The coordinator's direction sets:** when it runs; which agents and runs are paused for it; the quiet window; the runbook, with its quiescence gate; and the acceptance and rollback evidence.
- **It is one exact plan and one revision.** A plan that changes after approval goes back to the two deciders.
- **What it does not grant:** host installation, changes to the Docker daemon, credentials outside the service's own `.env`, and destructive clean-up beyond the plan.

**What that plan would state,** from this design [D]:

| # | What | Where |
|---|---|---|
| 1 | **Stopping the shared services, replacing their images and renewing their data volumes,** at one revision of `main` and its image IDs. | 7.5.4; 7.5.5 step 9; 7.5.7 |
| 2 | **The permission change,** with the final content: it reaches every role that is not an administrator, on PostgreSQL; and `demo` on MySQL (DL-085 item 7). | 4.1 to 4.4 |
| 3 | **The final hook,** what it refuses, and its independent review. | 4.3 |
| 4 | **The selection of templates on each engine,** and **whether MySQL's binary log is off,** each chosen from the storage report. The headroom and the recovery reserve. | 2.6; 2.4; 7.5.1 |
| 5 | **The namespaces taken into use,** each credential that leaves and the machine it is for, and the gates each rested on. | 7.5.2 |
| 6 | **The observation of origins,** and with it either `allow_from`'s evidence or the record that the administrators are reachable from the LAN. | 7.5.2 |
| 7 | **G-16's result,** and with it either the refusal that was built or MySQL `demo`'s rotation and the consumers' readers. | 4.5; 7.5.2 |
| 8 | **The acceptance evidence:** the final build's qualification and DataIntent's comparison on it, and the accepting run that follows. | 7.5.5 steps 10 and 12; 7.5.6 |
| 9 | **The rollback evidence:** the routes, their rehearsal, the enrollments' replay, and how long each rollout's inputs are kept. | 7.5.8; T-22 |

## 8. The test plan

**Test-first, on an isolated stack.** The plan is decided here [D].

- **Two kinds, in this order.** Feasibility gates (8.1) test an engine's own behaviour, with no CLI code, and run first. Regressions (8.2) test what is built.
- **A regression's red asserts the outcome that is wanted,** and fails on the commit before its change because that outcome is not yet there. It is never an assertion of what was wrong. [D: review 2's finding 20.]
- **Every regression has a reversal:** a fault planted in what was built, which that test is shown to catch.
- **Two levels.** Unit cases run in `make check`, with no container. Native cases are opt-in, and refuse any store but the isolated one, as `PR14:tests/test_strict_read_native.py:20-30` does.
- **A native case that cannot run is Unsupported or Not run, never Passed.**

### 8.1 Feasibility gates

Each is one independent assertion about an engine. **"Depends on it" names every command that does. "If it fails" is what those commands do, and none of them goes on using what failed.** [D: review 2's finding 19.] "Not offered" is exit 4, before anything is changed.

| Gate | What is shown, natively, and by what test | Depends on it | If it fails |
|---|---|---|---|
| **G-1** | A PostgreSQL template that accepts no connections and is the superuser's: refuses every account; is copied by a role that only may create databases; twice at once; cannot be altered, renamed or dropped by `admin`. | every PostgreSQL template, copy and template-path reset | The template model returns to the design. Copies and the template path are not offered. |
| **G-2** | What a copy carries and what it does not: each row of 4.8's first table. | the read group; 4.8 | Read grants are given in each database after it is made, as write grants are. |
| **G-3** | The door and its phase commit as one transaction. Two renames, a `CONNECT` grant and a phase commit as one. A rename needs no session. A closed database keeps its sessions and refuses new ones. `admin` with `pg_signal_backend` ends `demo`'s sessions. | PostgreSQL's reset, both paths | The swap is withdrawn. PostgreSQL's reset is not offered by either new path; today's stays, said to be unrecoverable after its drop, until the design returns. |
| **G-4** | The hook's cases: a creator without the owner's rights; an error forced after the copy, and what files remain; the same with no hook loaded. | every `CREATE DATABASE` on the service | H-3's resolution, step 4. |
| **G-5** | Routine admission: what a fresh role can run on pull request #14's candidate, and with the list on `PUBLIC`. What the three named built-ins change; that a snapshot exported under the floor is imported by another session under it. Whose rights a trigger's body runs with. | 4.2 | P-1 and P-3 are revised from what is found. |
| **G-6** | A role without `CREATEROLE`: what `ALTER ROLE`, `ALTER ROLE … SET` and `ALTER DEFAULT PRIVILEGES` let it change, and whether anything but itself. Whether `admin` can change `demo`, a namespace's owner or `postgres`. | the hook's fourth rule; 4.5 | PostgreSQL is treated as MySQL is when G-16 finds no refusal (4.5). |
| **G-7** | A session's advisory lock: per database; held while its session runs `CREATE DATABASE`, also after the client is gone; ended with the session. | on PostgreSQL: `copy create`, `drop`, `hold`, `renew`, `release`, `sweep`; `reset`, `reset --reconcile` | **All of them are not offered on PostgreSQL** until another exclusion with those three properties is shown by its own gate. |
| **G-8** | A database's comment is read by any role from any database. A plain `DROP DATABASE` refuses while any session is connected. | template records; the service's record; the sweep's and the reconciliation's engine check | The records move to tables in `megasamples`. Without the drop's refusal, `copy sweep` and `reset --reconcile` are not offered on PostgreSQL. |
| **G-9** | PostgreSQL when the data volume fills during a copy by each strategy, a reset, and a record's write: 2.6's table. | `copy create`, `reset` on PostgreSQL | Both are not offered until the design has a guard. |
| **G-10** | MySQL's `READ ONLY = 1`: every account's write refused, `root`'s too; what changing it needs; read by many `INSERT … SELECT` at once. | every MySQL template, copy and template-path reset | The MySQL template returns to the design; none of them is offered. |
| **G-11** | MySQL's grant patterns: an escaped underscore is literal and an unescaped one is not; a holder of `P\_%` can do nothing outside it; an exact, escaped name reaches that schema alone; what `partial_revokes` does to each. Proved against every kind of schema in T-9's list. | every MySQL namespace; `demo`'s grants; enrollment on MySQL | Namespaces on MySQL return to the design. No MySQL copy is offered. |
| **G-12** | A grant on a schema, by name and by pattern, after that schema is dropped and made again. | MySQL's reset; enrollment on working copies | The reset gives the working grants again from the image's list and the enrollment record, which do not depend on the grants surviving. |
| **G-13** | Definitions recorded from one schema and replayed into another, **by the namespace's owner and by `admin`, with the binary log on and off:** tables with generated columns, foreign keys and full-text indexes; views; routines; triggers; events; each recorded definer restored by `admin`. Held to each dataset's own verification. | MySQL's copy and template-path reset | Each kind that fails excludes the datasets that use it, by name: no template for them. |
| **G-14** | A schema that another's foreign keys point into is dropped and refilled; with a row added to the child that points at a row the pristine parent lacks. | `reset` of `oracle_hr`, by either path | It is offered only with its dependents (2.4), which is already the rule; if even that leaves a broken key, `oracle_hr`'s reset is refused and only the whole engine's remains. |
| **G-15** | MySQL's locks and drops: a named lock is held while its session runs a statement after the client is gone, and ends with the session; a drop waits on a transaction and gives up on a timeout; whether an idle session on a schema is visible to anyone. | on MySQL: `copy create`, `drop`, `hold`, `renew`, `release`, `sweep`; `reset`, `reset --reconcile` | **All of them are not offered on MySQL.** |
| **G-16** | A MySQL account changing its own password: every statement that does it, and each mechanism of the pinned server that might refuse it, **each named in the report with its result.** Repair by `root`. | 4.5 | The product says it cannot refuse it, and gives the three mechanisms of 4.5. |
| **G-17** | MySQL when the disk fills during a copy, a reset after its drop, and a record's write: 2.6's table. | `copy create`, template-path `reset` on MySQL | Both are not offered until the design has a guard. |
| **G-18** | The shipped MySQL starts and passes its image tests with the binary log off, and with it on. | the `binary_log` setting | The setting is withdrawn; the log stays on, and the storage report counts it. |
| **G-19** | On the filesystems a copy is made on, a bind mount shared by a host and a container among them: exclusive creation and a hard link each fail when the name exists; two racing publications leave one winner; the published file is the recorded inode; each step's failure for want of space leaves no file under a final name. | every SQLite `copy` command | **SQLite copies are not offered through the CLI.** A caller copies the staged file itself. |
| **G-20** | `flock` held by one process is seen by another, across the host and a container on one mount; a lock file opened and locked is confirmed against its path. A file removed while a reader has it open: what that reader sees. | SQLite's `copy create`, `drop`, `hold`, `sweep` | As G-19. |
| **G-21** | **An install test:** the package installs with the two drivers alone on each supported Python; `uv sync --locked` is unchanged. Psycopg's licence has been reviewed first. | the remote commands | The pure-Python driver; the dependency layout is revised. |
| **G-22** | **`administrators.allow_from` works where the server sees different addresses:** with two clients at two addresses, a reader signs in from both, an administrator from the allowed one only, on each engine. `whoami` reports each address truly. **Whether a given deployment's clients look different is not a gate:** it is that deployer's observation, with `whoami`. | `administrators.allow_from` | The setting is withdrawn, and 5.2's third default asks only for the word `any`. |
| **G-23** | **Composed enrollment.** A grant to `pg_database_owner` with the grant option is held by each database's own owner and nobody else. A role enrolled to read working copies and write one namespace cannot change a working row; the mirror; each also through an inherited role. The shared dependency catalog shows what a role owns and holds in every database. | every PostgreSQL write grant; `accounts enroll` | Write enrollment is not offered on PostgreSQL. Copies stay their owners' to write. |
| **G-24** | **Physical identity.** PostgreSQL: a database dropped and made again under one name has another OID. MySQL: its tables have other creation times; a schema made and not yet filled holds no table. An interrupted create, on each side of the creating statement, on each engine. | `copy drop`, `copy sweep`, `reset --reconcile` | A proof that fails is not used: every object it would have proved is kept and reported, and removal is by hand. |
| **G-25** | **Concurrent holders.** Two holds on one copy; the first released, the second still protects; a holder killed, its row found stale and removed; an acknowledgment that is never written before the hold is real. | `copy hold`; the sweep's third condition | One holder at a time, said so; or `copy hold` not offered, and the product's statement of what a sweep protects is narrowed to match. |
| **G-26** | **The image path's worker.** PostgreSQL: with the lock's connection cut while the worker runs, a reconciliation waits and removes nothing. MySQL: the worker's own session holds the reset lock, and a second reset is refused while it lives. | the image path of `reset` | The image path is offered only where the service runs, under the file lock alone, and says that nothing excludes a reset from elsewhere. |
| **G-27** | **Revocation and live sessions.** On each engine: whether an unenrollment or a suspended grant reaches a session already open; that ending the session does. | MySQL's reset where a writer is enrolled; `accounts unenroll` | The reset is not offered where a writer is enrolled; `unenroll` says that open sessions keep what they had. |
| **G-28** | **An account that manages accounts.** One with that privilege server-wide on MySQL: whether it can alter, lock or drop a namespace's owner, a consumer's reader or `demo`, and what protects them. | the claim of 3.5 for MySQL | The claim is not made, and 5.3 says that such an account can change the service's own. |
| **G-29** | **The hook confines a creator.** By direct SQL, as a namespace's owner: a name outside its prefix; another namespace's prefix; `template0`, `template1`, a working copy and another copy as the source; a rename out of its prefix. Each refused, and its own copies still made. | the claim of 3.5 for PostgreSQL | The claim is not made. |
| **G-30** | **Admission as a replaced server starts.** A server started with a maintenance marker shows it to the first connection; a command sent in that moment does nothing. | a whole engine's reset beside any other command | A whole engine's reset says that it excludes nothing reached from elsewhere, and that callers elsewhere must be stopped first. |
| **G-31** | **The exposure defaults.** With a listener wider than loopback: a start with any published password is refused; a start with `allow_from` unset is refused; with both given it starts. | 5.2's defaults 2 and 3 | The defaults are withdrawn only together with `network.bind`: the listener stays loopback-only, as today. |

### 8.2 Regressions

| # | Behaviour, and the outcome its red asserts | Why that fails on the commit before | Its reversal | The class it covers |
|---|---|---|---|---|
| T-1 | **The image ships each configured template** as 2.3 and 2.4 say: a connection to it is refused. | There is no `<database>_start`. | Built with connections allowed. | Every templated database on both engines; every account, the superuser's over the network and on the loopback. |
| T-2 | **Nothing writes or changes a template:** `admin`'s `ALTER DATABASE` on it is refused. | The template is `admin`'s. | The same, planted. | Every account, against rename, owner, the two flags, drop, comment and grant. On MySQL: a row change, a definition change and the option. |
| T-3 | **Namespaces do not overlap:** a configuration with the prefix `oracle` does not build. | It builds. | The foreign-namespace check removed. | A table of prefixes against database names, templates, `megasamples`, engine schemas, other prefixes and foreign namespaces; generated pairs, one differing only by an underscore. |
| T-4 | **The reach tables of 4.9,** cell by cell. Its first red: `admin`, inheriting an enrolled role, **connects** to that namespace's copy. | The reach is computed from an account's own grants only. | `CONNECT` on a working copy left with `PUBLIC`. One planted per column. | Every account against every kind of database, for connect, read, row write, definition change, drop, rename and grant; each right held directly, through one role, through two, and takable. |
| T-5 | **Permissions and enrollment are kept through template creation, a copy and a reset:** an enrolled writer changes a row of a working copy after its reset. | The reset gives the new copy no write grant. | That step removed; a per-account grant in place of the group's. | Every templated database, both engines, both reset paths. The fingerprint of owners, privileges, default privileges, the trigger and the extension, equal across them; **on MySQL a copy's definers compared as its owner's.** |
| T-6 | **Enrollments do not combine:** a role enrolled to read working copies and to write one namespace is **refused** a row change in a working copy. | One write group holds every table. | The write grant put back in the template. | Mixed scopes both ways; through an inherited role; read to write and back in one scope; overlapping enrollments; a session open across an unenrollment; `demo`, a table's owner, a holder of a schema's `CREATE`, and a role that can take up a privileged one, each refused for `write`. |
| T-7 | **The hook confines, closes or refuses:** a namespace's owner is refused a database outside its prefix. | The hook has no such rule. | The library not loaded; each rule removed in turn. | Every case of G-4 and G-29, as regressions. Creator by template by strategy. Every command that makes a routine, by each kind of creator. A second session that never sees a new database open. |
| T-8 | **The routine floor is the list, for every role.** | A fresh role's executable set is not the list. | The list granted to `demo` alone. | `demo`, a fresh role, a namespace's owner, a writer; in every kind of database, one a consumer made among them; an exported snapshot imported by a second session. The pull request's own cases, kept. |
| T-9 | **MySQL's grants reach what they name and nothing else,** and an audit after a legitimate enrollment finds nothing. | `demo` reads `mysql.user`; the audit reports the enrollment. | The grant on `*.*` restored; one underscore left unescaped; the enrollment record ignored. | Every working copy, template, `megasamples`, engine schema, other namespace, and a foreign namespace with a principal of its own. Exact, pattern, role-held and hand-made grants. `demo` reads a foreign schema only where marked, and never `mysql`. |
| T-10 | **No access to a copy outlives it:** a role enrolled when one copy was dropped, and unenrolled since, cannot read the next. | With a grant per copy it can. | A grant per copy planted back. | Create, drop and create again, with different readers and writers each time, both engines; a creation that fails; a dangling grant found by the check; a reset refused over an unexpected grant. |
| T-11 | **A MySQL copy is the dataset:** the dataset's own verification passes against a copy. | No foreign key is replayed. | One view skipped; a definer not restored on reset. | Every templated database: counts, digests, foreign keys, indexes, views, routines, triggers (`SM:ARCHITECTURE.md:239-249`). The stated exclusions. A coordinated reset of `oracle_hr` with an edited `oracle_oe`. |
| T-12 | **The CLI's contract:** one document on standard output. | A second line is written. | A password echoed; a changed exit code; an unknown member rejected by a reader; an unknown format changed anyway. | Every command by every outcome of 3.3's two tables: the document, the code, and the promised state checked on the server. The reader rules of section 6, each. The remote commands with no container runtime, in an install with the two drivers only. |
| T-13 | **Every password is resolved once, from the file:** with a conflicting value exported, the image path's reset signs in with the file's, for its lock and for its worker. | The host process takes the exported value. | That reader planted back; expansion allowed; a group-readable file accepted. | Each route; **through the real image reset and `accounts check --repair`;** a value that asks for expansion; a canary password in no argument, environment, output or log. |
| T-14 | **Nothing unproved is removed:** a create killed before its creating statement, with an object already under that name, leaves the object there. | Recovery removes whatever is under the name. | The proof check removed, for each engine. | An interruption on each side of the creating statement and of the publication, on each engine; an occupied name; a ready MySQL schema replaced outside the CLI; an `unproven` PostgreSQL database: each kept and reported. |
| T-15 | **Every command against every command.** | A pair with its guard missing. | Each guard removed in turn. | **Pairs are generated from the command inventory, so none can be left out:** every `copy`, `reset`, `accounts` and `template` command, `unenroll`, `accounts check --repair`, `template stage` and `reset --status` among them, by every reset scope and path, on each engine that has both; natively, with the first paused at each durable phase by a test-only pause point; and by gated fakes. **Its invariants are stated for each operation:** a sweep removes nothing leased or held; **an owner's own drop may remove its leased copy;** no working copy is lost or left closed by a completed command; nothing is present that `list` or `--status` does not show. |
| T-16 | **A reservation is atomic:** forty creates into a namespace of 32 give exactly 32. | More succeed. | The count taken outside the lock. | The count, the quota and the engine's headroom, two namespaces at once with a reset; creates that fail and give their place back. |
| T-17 | **A sweep removes only what 2.2 allows:** a copy renewed between the sweep's look and its removal is kept. | It is removed. | Each of the five conditions removed in turn. | Every reason a sweep keeps a copy; a creator paused past its lease; a held copy; a session on PostgreSQL; a transaction on MySQL. **The two cases 2.2 says are not protected:** shown unprotected. |
| T-18 | **The build refuses a selection over its budget.** | It bakes. | The check removed. | For each templated physical database, with its appended datasets: allocated bytes; both peaks; a copy's and a drop's time by each strategy. The first-start budgets again (`SM:megasamples/engines/image_startup.py:9-18`). |
| T-19 | **A reset's outcome can always be read:** after a reset whose reply was lost, `--status --operation` says `done`. | The row was removed at the end. | The outcome not kept; a phase written after its step; `--reconcile` made to drop again at `filled`. | The CLI killed after each phase, and its connection cut during each step, both engines, both paths: the status, the reconciliation's outcome, nothing reset twice. An edit made after a MySQL fill survives a reconciliation. Several targets, one failing: each reported. |
| T-20 | **One exclusion for both reset paths, and for a worker that outlives its CLI.** | Two resets of one database, by the two paths, both run. | The image path's lock removed; the worker's own lock removed. | Each pair of paths on each engine; the lock's connection cut while a worker runs; a whole engine's reset against each, and a command sent as the replaced server starts. |
| T-21 | **Names:** a copy's name is issued, and a second create with one label is refused. | The caller's name is taken. | The label's uniqueness removed; a token reused. | A prefix and a label: empty; a space; upper case; a non-ASCII letter, an emoji, a right-to-left mark; a quote, a semicolon, a backtick; one byte too long: exit 2, no connection. A database name of 33 bytes builds, with a 63-byte copy; 34 does not. A prefix that is not configured: exit 5. Each lease bound. |
| T-22 | **An image replaced, and each rollback route, rehearsed, with the enrollments replayed.** | The runbook has no such route: its fence test fails. | A step of the route removed from the runbook: the fence test fails; `accounts restore` skipping a role without naming it. | From `main`'s stack to the candidate, the verification, and back by each route. PostgreSQL's two refusals of unmatched image and data. One account's rotation and its undoing. |
| T-23 | **SQLite:** a truncated copy is not published. | It is. | The hash check removed; the link replaced by a move; the inode check removed; a lock taken on the sidecar. | Every staged file; create, drop, hold, sweep; a manifest that disagrees; a sidecar one format back, kept; an unknown one, refused. |
| T-24 | **Records survive a restart:** a copy's row, its holds and its lease are as they were after a stop and a start. | — | The ledger put on a store that the restart clears. | After a whole engine's reset: no copy, each template pristine, nobody enrolled until the replay. A list by prefix whose parts sum to the whole list. No name issued twice in a million. |
| T-25 | **Passwords:** PostgreSQL refuses `demo`'s change of its own. | It accepts it. | The hook's fourth rule removed. | Each account without `CREATEROLE`, each statement form, its settings and its default privileges. MySQL: whatever G-16 established, as a case that fails if the engine's answer changes; the check and `--repair`; a consumer's reader that can lock out only itself; a cleared key locking its account. |
| T-26 | **The image as shipped:** each registry row carries the build's revision. | It says `dev` (F-7). | The revision left out of the build. | The service's record; each namespace's owner locked without its key; no account passwordless (`SM:ARCHITECTURE.md:250`); MySQL's reset with configured credentials. |
| T-27 | **When the disk fills:** 2.6's table, row by row. | Whatever G-9, G-17 and G-19 showed unguarded. | Each guard removed. | Data, the log or undo, a record's write and a clean-up, each failing for want of space, on each engine. |
| T-28 | **A late or repeated command touches only what it names:** a drop that names an identity that is gone succeeds and changes nothing else. | The command takes a name alone. | The identity check removed. | `drop`, `renew`, `release` and `hold`, each sent late, twice, and with another copy's identity. |
| T-29 | **`copy hold` is real before it says so:** a sweep run the moment after the acknowledgment keeps the copy. | The acknowledgment is written first. | The order swapped; the hold ended by standard input closing. | The acknowledgment's identity; `--hold-fd`; a signal; the starter's death; two holders; the last one's release. |
| T-30 | **A MySQL reset reports only what is true:** with an enrolled writer, a row changed during the fill makes the reset `failed`, or cannot be made at all. | It is made, and the counts still match. | The writers not shut out; the checksum replaced by a count. | An update that keeps every count; two runs with different labels in one namespace, each reporting whether it is `exclusive`. |
| T-31 | **A credential is handed over alone, and recorded:** `accounts export` writes one value to one private file, and one line with no value. | It does not exist. | The whole `.env` written; the record holding a value; an administrator's exported. | Each kind of credential; an administrator's and a superuser's refused. |
| T-32 | **The defaults of 5.2,** each: with nothing configured, nothing listens beyond loopback; a wider listener is refused with a published password, and with `allow_from` unset. | `megasamples up` starts it. | Each refusal removed. | Every key unset in turn; every engine and console; `accounts check` reporting `exposed`; `whoami` from two addresses. |

## 9. Pull request #14's disposition

**It is folded into this work's branch. It is not rebased, and its content does not reach `main` by itself.** [D]

- **Why not by itself.** If H-1 is as read, `main` alone with it would build a server on which no role but `demo` and `admin` can call a built-in routine.
- **Why folded.** Its grants, its hook and its tests are the ground the templates stand on.
- **How.** The work's branch starts from `main` and merges `fix/strict-read-account` at `2879fc4` as its first commit. It merges without conflict (F-15). Its history is kept.
- **When its content reaches `main`:** with the branch. Its maintainers have set conditions on that merge (F-26); they are in 7.5.5. Pull request #14 is closed then, pointing at the merged one.
- **Its tests are not loosened.** Where this design changes an expectation, that is a test-only change of its own, saying why.
- **Its evidence is made again,** for the final candidate. The earlier receipts leave the tree and remain in history at `2879fc4`. [D]
- **Carried on the same branch:** the ten notes that pull request #16's review left for "the next sql-megasamples PR", C-1 to C-10 (`DI:docs/work/megasamples-pr16-review-loop.md:17-27` at `d02f7384`). [R]

## 10. What the README must document

For DL-078's writer, on the same branch, before the merge. **The README describes the product:** its capabilities, its configuration, its safe defaults, and what a deployer weighs. A deployment is an example. [R: `DL:` DL-107 item 1]

**What DL-078 itself asks** [R: F-27] [D: review 2's P3]:

1. **It leads with the project's purpose:** one place to go for fast access to sample data across many technologies.
2. **The LTS engines and the clients,** at the versions the build pins.
3. **The datasets:** which there are, on which engines, with a matrix.
4. **The configuration and the `.env` passwords, and where to find them.**
5. **The procedure for changing a deployment** (5.4).
6. **Visuals where they help,** in a form that renders and does not go stale.

**What this design fixes** [D]:

7. **The model, with a picture:** a template, a working copy, a test copy and a reset, for one dataset; and how the three engines differ.
8. **Which databases have a template,** per engine, with measured sizes and times, the budget, the headroom, and how to configure them.
9. **Namespaces:** what a prefix is, why it may not overlap, a foreign namespace, and how a baked one is taken into use.
10. **A copy's life:** issued, ready, leased, held, released, swept. What nothing will remove. **The two cases a sweep does not protect.**
11. **The commands,** each with one example and its JSON; that `drop`, `renew`, `release` and `hold` need the identity; how a script waits for a hold.
12. **The exit codes,** both tables of 3.3, and what a script does on 8.
13. **Credentials for scripts:** the three routes, the keys, that nothing in the environment is read.
14. **The accounts,** as 4.9's tables: what each can reach, that an account reaches what it inherits, and what a credential's holder can do from any address. It replaces today's two-row tables (`SM:README.md:120-123`, `:247-255`).
15. **Enrollment:** how an account is given the working copies or a namespace, that writing is scoped, what a reset keeps, and how the record is replayed.
16. **The read profile on PostgreSQL,** and its limit (H-14). It replaces the sentence that `demo` "still has `TEMPORARY`" (`SM:README.md:163-167`; `SM:.env.example:14-17`).
17. **The defaults, and why each is safe when nothing is known** (5.2).
18. **Exposing it:** 5.3's table, whole. **Then profiles as examples** (7.1 to 7.4), each marked as one configuration among many.
19. **What changed for someone who used it before:** a new database is closed until its owner grants `CONNECT`; a new routine until its owner grants `EXECUTE`; MySQL's `demo` no longer reads `mysql`; an account cannot change its own password on PostgreSQL; **a reset no longer disconnects without being told to.**
20. **What is not claimed:** MySQL is not a strict read profile; a MySQL reset cannot be undone and has no door; whatever G-16 established; a template on MySQL can be read by administrators; SQLite has no accounts; no TLS is configured; the limits bind the CLI, not a credential's holder.
21. **Resets:** the two paths, the default and its two options, `--status` and `--reconcile`, operation identities, coordinated resets.
22. **The contract and the formats,** and their rules (section 6).

**What leaves the README, or becomes an example** [D: DL-107 item 2]: the dated account of "the maintained deployment" and its acceptance (`SM:README.md:16-20`), and the paragraphs that take LAN forwards for granted (`:258-270`) (F-29). One deployment's status is that deployment's record.

## 11. Where each of DL-106's decisions belongs: a proposal

The owner returned DL-106 to the deciders to be separated (DL-107 item 4). **This table proposes the split. The deciders confirm or change it;** until they do, every `[106-n]` in this record is a proposal.

The levels: **a mechanism** the product has; **a default** the product ships; **the contract**; or **DataIntent's deployment policy** (7.5).

| # | DL-106 decided | Proposed level | Restated at that level | Where |
|---|---|---|---|---|
| 1 | A namespace and an owner for each machine or consumer; spare locked ones for the machines known today; revoking one needs no rebuild. | **Mechanism**, and **deployment policy** | *Product:* any number of namespaces, each with its own owner; an owner locked until keyed, so a baked namespace can wait; clearing a key revokes. *DataIntent:* one for each of its machines, with spares. | 2.1; 7.5.1 |
| 2 | No administrator's or superuser's credential leaves the service's machine; each credential sent alone, each sending recorded. | **Mechanism**, **default**, and **deployment policy** | *Product:* `accounts export` hands over one credential alone and records it with no value; by default it exports no administrator's or superuser's. *DataIntent:* none of its administrators' leaves, `di_admin` and its fixture and provisioning credentials included. | 5.2 item 6; 5.3; 7.5.2 |
| 3 | A local-only rule for administrators if G-22 shows an engine can tell origins apart, as a precondition of the rollout; otherwise recorded as LAN-reachable. | **Mechanism**, **default**, and **deployment policy** | *Product:* `administrators.allow_from`, and `whoami` to observe origins; a wider listener is refused until the deployer has set it, to a list or to `any`. *DataIntent:* the observation on its instance, and the two branches as its rollout's precondition or its record. **Changed level:** G-22 is now a test that the mechanism works, and the question "can this deployment tell them apart" is each deployer's observation. | 5.1; 5.2 item 3; 5.3; 7.5.2; G-22 |
| 4 | A PostgreSQL namespace owner's credential stays on the machine until the hook refuses out-of-namespace names and unapproved template sources through direct SQL. | **Mechanism**, and a **claim the product withholds**; then **deployment policy** | *Product:* the hook's second rule; the product does not claim the use of that credential away from the service until G-29 passes, and says so. *DataIntent:* does not send one before then. | 4.3; 3.5; 7.5.2; G-29 |
| 5 | A MySQL owner's credential may leave after G-11; before any leaves, a gate shows `di_admin` cannot alter a namespace's owner or a reader. | **Claim the product withholds**, and **deployment policy** | *Product:* the same claim for MySQL waits for G-11 and for G-28, which is about any account that manages accounts. *DataIntent:* G-28 run against `di_admin` as it plans it. **Changed level:** the product's gate no longer names `di_admin`. | 3.5; 4.4; 7.5.2; G-28 |
| 6 | If G-16 finds no refusal: MySQL `demo` stays on the machine with its own key, rotated at this rollout; each LAN consumer gets a reader; the owner is told DL-075 item 5 is narrowed. | **Mechanism**, and **deployment policy** | *Product:* a separate key for MySQL's `demo`; a reader per consumer; detection and repair; and the consideration, in 5.3, that a shared read credential can be changed by any holder. *DataIntent:* keeps `demo` on its machine, rotates it at its rollout, gives each LAN machine a reader. **Changed level:** "stays on the machine" and "rotated at this rollout" are not rules of the product. | 4.5; 5.3; 7.5.2 |
| 7 | The CLI and the records are versioned: additions only, the four reader rules, a tag for each format, version 1 fixed at the merge, server formats matched exactly, consumer files read one back, unknown formats refused; the contract gains the `.env` keys, `megasamples.yaml`'s keys and the lock protocol. | **The contract** | As decided. | Section 6 |
| 8 | After the merge, every break is a recorded decision of the two deciders. | **The contract**, and **governance** | *Product:* every break raises its own number and is recorded with what it breaks. *Its present maintainers:* the two deciders approve each. **Changed level:** who approves is not part of the product. | Section 6; 7.5.2 |
| 9 | MySQL `demo` keeps its sight of DataIntent's fixtures, through a grant confined to the fixture schemas. | **Mechanism**, **default**, and **deployment policy** | *Product:* a declared foreign namespace may be marked `demo_reads`; by default `demo` reads none. *DataIntent:* marks `di`. **Changed level:** the product knows no `di` and no fixture. | 4.4; 5.2 item 7; 7.5.1 |
| 10 | Enrollment at namespace scope, with disjoint prefixes; a result needing exclusive writing counts only when its binding excludes other ordinary writers. | **Mechanism**, and **deployment policy** | *Product:* enrollment by scope; `copy create` reports a copy's writers and whether they are exclusive. *DataIntent:* what its results may rest on. | 4.6; 7.5.2 |
| 11 | Active copies protected for the whole period of use; criterion 11 recorded as not passed for an idle MySQL session and an open SQLite file. | **Mechanism**, a **stated limit**, and **deployment policy** | *Product:* the lease and the hold; the two cases it does not protect, said plainly. *DataIntent:* its criterion 11 recorded as not passed for them; its harness holds. | 2.2; 7.5.2 |
| 12 | Unattended resets: one dataset, a closed door, an idle check, refusal before any change, a warned human choice to discard; on MySQL automation resets no working copy until a door exists. | **Default**, and **deployment policy** | *Product:* a reset discards no session unless told to; `--unattended` is one database and refuses, and is refused on MySQL. *DataIntent:* its automation uses it; that answers its question 6. | 3.6; 7.5.2 |
| 13 | MySQL's binary log configurable; the image default kept; the live deployment may turn it off at the rollout's approval. | **Mechanism**, **default**, and **deployment policy** | *Product:* the setting, default on. *DataIntent:* its choice at its approval. | 2.4; 5.1; 7.5.1 |
| 14 | One host-held `admin` key for both engines, its combined authority documented. | **The contract**, and **deployment policy** | *Product:* `ADMIN_PASSWORD` is `admin` on both engines, and the README says what that holder can do. *DataIntent:* where it keeps it. | 3.4; 4.7; 7.5.2 |
| 15 | The hook's `ALTER ROLE` rule, subject to G-6 and the independent review of the final hook. | **Mechanism** | As decided. | 4.3 |
| 16 | The first live write enrollment goes to the deciders, after R-39's controls. | **Default**, and **deployment policy** | *Product:* nobody is enrolled to write as shipped. *DataIntent:* who decides its first. | 4.6; 5.2 item 5; 7.5.2 |
| 17 | Baked namespaces, with spare locked ones and a rehearsed, replayable restoration of enrollments. | **Mechanism** | *Product:* namespaces are baked; an enrollment record that `accounts restore` replays, rehearsed in T-22. Spares are item 1's. | 2.1; 4.6 |
| 18 | `core` is the template default; the live selection per engine at the rollout's approval. | **Default**, and **deployment policy** | *Product:* `core`, within a budget the build enforces. *DataIntent:* its selection, at its approval. | 2.6; 7.5.1 |
| 19 | Psycopg's licence reviewed before G-21. | **The repository's own procedure** | A step of the build, under the repository's dependency rules. | 3.5; 7.5.5 step 1 |

**Two things DL-106 rested on that the product cannot.**
- **"The LAN is trusted."** It appears in no product section. Where a mechanism leaves something unbounded (a copy owner can fill the disk; on MySQL any account can make commands report busy), 5.3 says so, and what a deployer does about it is the deployer's.
- **"The service's machine" as a boundary.** The product has listeners and credentials. Which machine a credential is on is custody, and custody is a deployment's.

## 12. What is still only inferred

Every load-bearing behaviour is a gate (8.1). These remain marked [I], and nothing is built on them:
- that MySQL has no comment on a schema, and cannot rename one;
- that only the server itself can vacuum a database nobody can connect to;
- H-8, H-10, H-11 and H-14's readings of the engine, which the independent review confirms or corrects.

**Sizes:** none is asserted. T-18 measures each.

## 13. The reviews' findings, and what changed

Every finding of both reviews was to fix now (DL-101). None is declined.

### 13.1 Round 3: review 2's findings

| # | Finding | What changed | Where |
|---|---|---|---|
| 1 | **P1 · PostgreSQL enrollment gives write access across scopes.** | **The class is closed by where write grants live.** No group holds row changes in every database any more. The template grants them to the database's own owner alone; each owner grants them, in that database, to its own scope's write group. So no combination of enrollments gives a write that neither gave. Gate G-23 shows it natively, mixed scopes and inherited roles included; if it fails, write enrollment is not offered. | 4.1; 4.6; 2.3; G-23; T-6 |
| 2 | **P1 · Clean-up can delete an object the failed create never owned.** | **A name is issued by the CLI and never reused,** so a record cannot meet an object that was already there. Each copy has a physical proof (an OID, a creation fingerprint, an inode), and each creation writes its phase before its step. Whatever cannot be proved is `conflict`, `unproven` or `inconsistent`: kept, reported, and removed by no command. What the proof does not guard against is said. | 2.1; 2.2; 2.5; G-24, G-19; T-14 |
| 3 | **P1 · A delayed command can act on a replacement copy.** | No name is used twice, so there is no replacement to hit. And `drop`, `renew`, `release` and `hold` take the identity they expect; under the change lock the identity, the phase, the proof, the lease and the holds are read again. A sweep also requires the revision it selected, so a renewal in between keeps the copy. | 2.2; 3.1; T-17, T-28 |
| 4 | **P1 · The image reset can lose both the working database and its exclusion.** | PostgreSQL's image path no longer drops first: it restores into a transient and swaps, as the template path does, with the same phases. Its worker writes only into the operation's own transient, and a reconciliation waits while it runs. MySQL's worker takes the reset lock in its own session. A whole engine's reset keeps its exclusion and its outcome in a record outside the volume, and the replaced server starts closed to the CLI. | 2.3; 2.4; 3.6; G-26, G-30; T-20 |
| 5 | **P2 · Reset reconciliation loses the answer to a successful operation.** | Each operation has an identity the caller knows, and its row ends in a kept outcome. `--status --operation` tells done from never started. The door and its phase are one transaction. MySQL's reconciliation is by phase and never drops again at `filled`. Several targets report each its own. | 2.3; 2.4; 3.2; 3.3; T-19 |
| 6 | **P2 · MySQL can report a successful reset of data that already differs.** | A MySQL reset shuts ordinary writers out while it runs and checks by checksum; without that it is not offered where a writer is enrolled. On MySQL a namespace's owner is the only ordinary writer of its copies. `copy create` returns its `writers` and whether they are `exclusive`. The claim about R-35 is corrected. | 2.4; 4.6; 7.5.2; G-27; T-30 |
| 7 | **P2 · The grant audit cannot distinguish authorized enrollment from stale access.** | What is expected is written down: the image's grants and an enrollment record. The check reports what is unexpected, missing or dangling against it, and finds nothing after a legitimate enrollment. Every granting path validates the namespace and the principal. A reset refuses over an unexpected grant; copies cannot reuse a name. | 4.5; 4.6; T-9, T-10 |
| 8 | **P2 · Enrollment checks too few privileges to certify an editor.** | Admission is by effective privileges: attributes, ownership and any other privilege in any sample database, through every inherited or takable role. `demo` is reserved read-only. Each membership's options are in a table, with `admin`'s the one that does not inherit. T-6 covers changes of level and overlaps. | 4.1; 4.6; G-23; T-4, T-6 |
| 9 | **P2 · `copy hold` has no reliable acquisition handshake.** | It takes the hold under the change lock, then writes an acknowledgment bound to the identity; a caller opens the copy only after reading it. Its lifetime is a descriptor, a signal or its starter, never standard input. Holds are rows with a lock each, so any number can hold. SQLite's locks are stable files, never the sidecar. The two cases a sweep cannot protect are stated as not protected. | 3.1; 2.2; G-25, G-20; T-29 |
| 10 | **P2 · The file-only rule stops short of the image reset's reader.** | Every key a command needs is resolved once in its own process, from the one route, and handed to its workers. The reset's present reader is replaced for `reset` and `accounts`. The keys are listed, the superusers' among them. Every file route requires a private file. T-13 runs the conflicting export through the real image reset and the repair. | 3.4; F-22; T-13 |
| 11 | **P2 · MySQL replay and its fallback lack necessary inputs.** | The original definer and security mode are recorded beside each stripped definition. Replay is a gate under each account and each binary-log setting. A database that another refers to is reset only with its dependents, by either path, and every key between them is checked. | 2.4; G-13, G-14; T-11 |
| 12 | **P2 · The storage budget does not support the disk-full guarantee.** | The guarantee is restated: a MySQL reset interrupted after its drop is unsettled, not whole. Admission reserves each operation's measured peak against the engine's headroom, across namespaces, with a reserve for recovery never lent. SQLite's failures are in the table and the gate. A failed gate withholds resets as well as copies. | 2.6; G-9, G-17, G-19; T-16, T-27 |
| 13 | **P2 · Question 1 overstates the isolation bought by a namespace per machine.** | The consequences are in the product now: the hook confines a PostgreSQL owner's names and templates, and the use of its credential away from the service is not claimed before that is shown; an account that manages accounts is a gate before the same claim on MySQL; a baked namespace can wait locked because adding one renews the volumes; reserving a name is told apart from owning a database; an editor's credential is a different one from a copy owner's. | 4.3; 4.9; 2.1; 3.5; 5.3; G-28, G-29 |
| 14 | **P2 · Question 2(c) leaves the distributed shared password usable.** | A reader per consumer does not end a shared value already handed out: only rotating it does. The product gives MySQL's `demo` a key of its own for that; DataIntent's instance rotates it at its rollout, shows the old value refused and the consoles and probe signed in. phpMyAdmin's route is stated: custody is not an address. The rollback's consequence is stated. G-16 reports each mechanism it tried by name. | 4.5; 5.3; 7.5.2; 7.5.7; 7.5.8; G-16 |
| 15 | **P2 · Question 3 does not define how a consumer recognizes a changed format.** | Each persisted format has a tag of its own, and a break raises that tag. Reader rules are stated and tested. A copy whose sidecar is one format back is kept and reported, and removed only by an explicit drop. Operation identities and terminal outcomes are in the contract. | Section 6; 2.5 |
| 16 | **P2 · Candidate admission is scheduled before its authorization point.** | DL-087's acceptance is step 5, and the comparison with the admission is step 6. The live half before the rollout expects today's `demo` refused, as a recorded baseline; the candidate half is held to the full gate. | 7.5.5; 7.5.6 |
| 17 | **P2 · The comparison can omit a C5 case and overstate version coverage.** | Both C5 controls are listed, each with its empty stream, its targets and their authority. The evidence says two builds on the same engine versions, and does not claim comparison mode's first use on two versions. One revision and one inventory are pinned across all three runs. | 7.5.6; 7.5.4 |
| 18 | **P2 · The design reverses a fixture acceptance case without a decision.** | `demo` reads a consumer's own schemas where the configuration marks them. DataIntent's instance marks `di`, so its case stays. | 4.4; 7.5.1; section 11 item 9 |
| 19 | **P2 · Several gate fallbacks leave the failed prerequisite in use.** | Each gate now names every command that depends on it, and its failure withholds all of them, before any change. G-12's fallback rests on the record, not the grants. Nine gates are added: composed enrollment, physical identity, concurrent holders, the image worker, live-session revocation, an account that manages accounts, the hook's confinement, admission at a replaced server's start, and the exposure defaults. G-21 is an install test; G-22 tests a mechanism, and the topology is each deployer's observation. | 8.1 |
| 20 | **P2 · The regression matrix still permits false closure.** | Each red asserts the wanted outcome; T-4's is that `admin` connects. T-15's pairs are generated from the command inventory, and its invariants are stated per operation: an owner's own drop of a leased copy is allowed. Every row has a reversal. | 8; 8.2 |
| 21 | **P3 · The README checklist and the provider-listing claim.** | The checklist begins with what DL-078 itself asks: the purpose, the LTS engines and clients, the datasets. The record no longer predicts templates in the provider's list: the provider leaves out templates, and the catalog and the registry are tested apart. | Section 10; 7.5.3; F-17, F-27 |

### 13.2 Round 3: the owner's DL-107

| What drifted | What changed | Where |
|---|---|---|
| **Namespaces baked for "the machines known today".** | The product has namespaces, any number, each lockable until keyed. Which machines get one is DataIntent's configuration. | 2.1; 7.5.1 |
| **A "trusted LAN" as a premise.** | It is in no product section. The defaults assume nothing is known about the network, and refuse a wider listener until passwords and administrators' origins are settled. What stays unbounded is said in 5.3. | 5.2; 5.3; section 11 |
| **`di` and DL-079's fixture case in the product.** | The product has foreign namespaces, and a mark that lets `demo` read one. `di` is DataIntent's declaration. | 2.1; 4.4; 7.5.1 |
| **Credential rules framed around one host and one LAN machine.** | The product says what each credential's holder can do from any address, and gives mechanisms: export of one credential, a namespace and a reader per consumer, rotation, revocation, origins for administrators. Custody is a deployment's. | 4.9; 5.3; 7.5.2 |
| **The rollout woven through the design.** | It is one profile's, in 7.5, pointing at DataIntent's records. The plan itself is DL-105's, on DataIntent's side. | 7.5.4 to 7.5.9 |
| **DL-106 treated as final.** | Section 11 proposes a level for each of its nineteen decisions, restating those that move, for the deciders to confirm or change. | Section 11 |

**Not settled here, and said so:**
- **Section 11's split** is a proposal until the deciders rule on it.
- **Where the repository's runbook belongs.** It is one deployment's procedure, in the product's repository (F-29). Section 5.4 keeps it there and adds a general route. Moving it to DataIntent's side, or rewriting it as the product's, is beyond this work's files and is the coordinator's and the deciders'.
- **Which route the live half of DataIntent's comparison takes before the rollout** is DataIntent's to name (7.5.6).
- **What G-16, G-22, G-28 and G-29 will show.** Each has both branches written; none is assumed.

### 13.3 Round 2: review 1's findings

As round 2 left them. Where round 3 has since changed the answer, 13.1 says how.

| # | Finding | What changed in round 2 |
|---|---|---|
| 1 | **P1 · MySQL prefixes can grant access to working copies, templates and a consumer's fixtures.** | A prefix became a namespace that may overlap nothing; every underscore in every pattern is escaped; an audit reports any later grant that reaches in. |
| 2 | **P1 · MySQL copy grants survive deletion and leak into a replacement.** | No copy has a grant of its own. Access is the namespace's, by enrollment. The owner lost the grant option. |
| 3 | **P2 · Name uniqueness does not serialize a copy's lifecycle.** | An identity, a durable record, and a change lock for each whole change; an atomic reservation. Round 3 added the issued name and the proof. |
| 4 | **P2 · Age is not evidence that a copy is unused.** | The rule by age was withdrawn, for a lease, a hold and the engine's consent. |
| 5 | **P2 · Reset recovery cannot satisfy the stated outcome contract.** | Durable phases, `--status` and `--reconcile`, and an exit's promise per command. Round 3 added kept outcomes. |
| 6 | **P2 · Reset paths do not share their exclusion and idle guarantees.** | One lock for both paths. Round 3 made the image path the same procedure. |
| 7 | **P2 · The working-copy editor has no durable access path.** | Enrollment, which a reset keeps. Round 3 scoped the write grants. |
| 8 | **P2 · PostgreSQL's reach table ignores inherited connection rights.** | Effective access through memberships. |
| 9 | **P2 · The local credential fallback contradicts the no-environment contract.** | A file-only reader for `--env-file`. Round 3 carried it through the image path. |
| 10 | **P2 · The merge and rollout order violates DL-085 and DL-103.** | The comparison before the merge; the README before the rollout; one build of the final `main`. |
| 11 | **P2 · The second rollout silently reduces DataIntent's comparison scope.** | All five parts mapped; the retention condition named. |
| 12 | **P2 · Historical core sizes are not upper bounds.** | Both totals withdrawn; measurement per physical database; a budget. |
| 13 | **P2 · Owner question 1 understates the credential's authority.** | Each credential's effective authority from any origin. |
| 14 | **P2 · Owner question 2 presents detection-and-repair too narrowly.** | A gate first, and the consequences stated. |
| 15 | **P2 · Persisted formats and public contracts are excluded from owner review.** | A contract table and a policy. |
| 16 | **P2 · Several planned tests cannot prove the stated behaviour.** | Gates apart from regressions; H-3 given a resolution. |
| 17 | **P3 · Narrow several factual and compatibility claims.** | F-1, H-1, the snapshot exception and the image-and-data refusal, each scoped to its evidence. |
