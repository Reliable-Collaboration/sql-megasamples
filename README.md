# sql-megasamples

Sample database servers for **MySQL, PostgreSQL and SQLite**, ready to query: 38 well-known sample
and public datasets, each converted from its upstream source by a scripted, rerunnable pipeline and
checked against pinned expectations. They ship as engine images and files, with web consoles that
come up beside them already connected. You choose the engines, the databases and the consoles; one
file holds the choice and one command builds it.

There is no sensitive data here. The servers are for looking at data, trying queries, and testing
on a copy you can throw away.

| engine | what ships |
|---|---|
| **MySQL 9.7.4** | `sql-megasamples-mysql`: an image with the databases baked into its data directory |
| **PostgreSQL 18.7** | `sql-megasamples-postgres`: an image with the databases in its cluster, ported from the verified MySQL corpus |
| **SQLite 3.54.1** | `sql-megasamples-sqlite`: one `.sqlite` file per database with the `sqlite3` shell beside them; the files are also under `build/sqlite/` to copy anywhere |

PostgreSQL and SQLite are **ports of the MySQL corpus**: the same rows, proved by the same
per-table content digests, foreign-key checks and index parity that MySQL is checked against, and
produced by one deterministic program, never by hand. BTS and WideWorldImporters OLTP are not
offered on PostgreSQL and SQLite.

Every dataset keeps its own upstream licence; this project never places a single licence over the
data. [`CATALOGUE.md`](CATALOGUE.md) lists all 38 datasets with what each licence asks of you, and
[Licensing](#licensing) is worth reading before you publish anything built from this.

<p align="center">
  <a href="docs/screenshots/landing.png"><img src="docs/screenshots/landing.png" alt="The console index: how to connect your own tool to MySQL, PostgreSQL and SQLite, the four consoles, and the 21 databases with their tables, rows and sizes on each engine" width="100%"></a>
</p>
<p align="center">
  <a href="docs/screenshots/cloudbeaver.png"><img src="docs/screenshots/cloudbeaver.png" alt="CloudBeaver, opened as a guest: the MySQL read-only connection expanded to its 21 databases, and Sakila's film table on the Data tab" width="49%"></a>
  <a href="docs/screenshots/dbgate.png"><img src="docs/screenshots/dbgate.png" alt="DbGate with every connection preconfigured: Sakila's tables with their row counts, the film table's columns and references, and its rows" width="49%"></a>
</p>
<p align="center"><sub>The console index at <code>http://127.0.0.1:8080/</code>, then CloudBeaver and DbGate on Sakila's <code>film</code> table — all three engines, every database, one <code>make up</code>. Retake them with <code>make screenshots</code>.</sub></p>

**Status: not published as images.** There is no image to `docker pull`; you build them locally.
What changed in this version is in the [release notes](docs/release-notes.md).
[`ARCHITECTURE.md`](ARCHITECTURE.md) describes how the pieces fit, and
[`knowledge/`](knowledge/index.md) is the evidence behind the data.

## Quick start

```sh
uv sync --locked   # exact Python client/converter versions and hashes from uv.lock
make configure     # choose engines x databases and consoles; writes megasamples.yaml
make run           # fetch (once), convert, load, verify, bake the images
make up            # start the stack, then open http://127.0.0.1:8080/
```

`make configure` is a full-screen chooser: the engines, then a matrix of every dataset against
every engine, with each dataset's tier, download size and whether that download is already
verified on this machine, then the consoles. It writes `megasamples.yaml`, which every other
command reads. You can also copy [`megasamples.example.yaml`](megasamples.example.yaml) and edit
it, or run with no file at all: the built-in default is MySQL with the 21 core databases and the
four consoles.

You need **Docker** (Desktop or Engine), **Python 3.14+** with [`uv`](https://docs.astral.sh/uv/),
and room: the core tier is 1.4 GB of downloads, two build servers holding a copy of the data, and
up to 8.7 GB of images for the three engines. A full core build converts and loads nine million rows
and is not a five-minute job; the 15-dataset **quick** subset (196 MB of downloads) builds in
minutes, and the PostgreSQL and SQLite ports of an already-built MySQL corpus take minutes too.

`make up` starts the engines and the consoles; `make down` stops them and throws away what you
changed (see [Stopping, and what is kept](#stopping-and-what-is-kept)).

## The databases

Each one is converted from its authoritative upstream source; the description is the one its own
research record carries. These 21 are the **core** tier, the ones an image holds by default; full
detail (every tier, licence and obligation) is in [`CATALOGUE.md`](CATALOGUE.md), and `make list`
prints every dataset with its tier, download size and shape.

<!-- databases:start -->
| database | what it is | tables | rows |
|---|---|---:|---:|
| `adventureworks` | Microsoft's flagship 68-table, 5-schema OLTP sample (bicycle manufacturer) | 69 | 759,240 |
| `adventureworks_lt` | The lightweight 12-table AdventureWorks (SalesLT schema) | 12 | 4,277 |
| `chicago_crimes` | The City of Chicago's 8.6 M-row reported-crime extract plus the 434-row IUCR code lookup — a live feed: a build takes the current extract, and this count is the snapshot's floor | 2 | 260,041 |
| `chinook` | Luis Rocha's digital media store sample (v1.4.5, 2024-02-12) | 11 | 15,607 |
| `contoso` | SQLBI's synthetic Contoso retail star schema V2 | 8 | 753,467 |
| `dvdstore` | Dell/VMware's open-source OLTP benchmark schema (DVD e-commerce with reviews and memberships) | 9 | 174,716 |
| `employees` | The MySQL "Employees Sample Database" - 300,024 fabricated employees with 2.8 M salary rows | 6 | 3,919,015 |
| `enron` | About 517k real corporate emails from 150 Enron custodians, distributed by CMU as a maildir-style tree of RFC 822 files | 3 | 48,778 |
| `jaffle_shop` | dbt Labs' fictional jaffle (toasted sandwich) shop | 3 | 312 |
| `lahman` | Sean Lahman's historical MLB statistics 1871-2025, now published by SABR as 27 CSV tables (plus Access and SQL Server forms) under CC BY-SA 3.0 | 27 | 706,466 |
| `northwind` | Microsoft's classic 13-table trading-company sample (SQL Server 2000 era) shipped as a single 1 MB T-SQL script with all data inline | 13 | 3,308 |
| `nyc_taxi` | New York City yellow and green taxi trip records in Parquet, plus the 265-row taxi zone lookup | 2 | 48,591 |
| `oracle_co` | Oracle's "modern" e-commerce sample (7 tables, 8,783 rows) with identity columns, a JSON check constraint on a BLOB | 7 | 8,783 |
| `oracle_hr` | The 7-table, 216-row teaching schema from Oracle's db-sample-schemas v23.3, converted from its plain INSERT scripts | 7 | 216 |
| `oracle_oe` | The object-relational Order Entry schema | 9 | 11,518 |
| `oracle_sh` | Oracle's star-schema data-warehouse sample | 9 | 1,063,396 |
| `pubs` | Microsoft's tiny 11-table publishers/authors sample (SQL Server 2000 era) shipped as a 126 KB T-SQL script with inline data | 11 | 255 |
| `sakila` | Oracle's DVD-rental sample database for MySQL (Version 1.5), 16 tables / 7 views / 3 procedures / 3 functions / 6 triggers, 46,268 rows | 16 | 47,268 |
| `smallsets` | Three classic teaching datasets in one database — the Titanic passenger list, Fisher's Iris measurements and the Palmer Penguins | 4 | 2,147 |
| `stackexchange_beer` | CC BY-SA XML dump of a Stack Exchange Q&A site (Posts, Users, Comments, Votes, Badges, Tags, PostLinks, PostHistory) converted to MySQL with FULLTEXT | 11 | 62,523 |
| `wikipedia_simple` | Current-revision article text plus MediaWiki link tables of the Simple English Wikipedia | 9 | 1,167,112 |
<!-- databases:end -->

Beyond these, the extended, generated and user-fetched datasets are in
[Beyond the core](#beyond-the-core).

## The engines

**MySQL is the hub.** Every dataset is converted into MySQL first, loaded into a throwaway build
server, verified there (row counts, a canonical content digest of every table, foreign-key
integrity, the index set, every view's digest, the output of every stored routine and trigger,
query plans, canonical query results) and dumped. The other engines are ports of that verified
corpus, checked against the same expectations.

### MySQL

`sql-megasamples-mysql:dev` is `mysql:9.7.4` (`utf8mb4`, InnoDB) with the chosen databases already
in its data directory. First start copies that directory into a fresh volume, then starts the
server. Two accounts are offered from every console, and both work from any client:

| account | factory password (without overrides) | privileges |
|---|---|---|
| `demo` | `demo` | `SELECT` and `SHOW VIEW` on working schemas and explicitly enabled foreign namespaces. `SELECT` on the `megasamples.datasets` and `megasamples.copy_service` registry tables. Holds no write privilege. |
| `admin` | `admin` | `ALL PRIVILEGES WITH GRANT OPTION` |

The working schemas are the sample databases themselves (`sakila`, `chinook`, …). Each console
opens on `demo`, so the read-only account is the one you get without choosing.

```sh
mysql -h 127.0.0.1 -P 3306 -u demo -p sakila
docker compose up -d mysql        # the database alone, no consoles
```

A `megasamples` database inside the image holds the provenance registry: one row per database (an
`append: true` dataset joins its base's row) with its tier, knowledge record, licences, source artifacts and digests, and row counts (pinned, or for live datasets such as Chicago Crimes the snapshot verified on that
build). The landing page and the image tests read it, so neither can drift from what was baked.
The catalogue `make catalogue` is generated from the repository's dataset definitions and pinned counts, not from
a running image, so it lists every dataset whatever an image carries.

### PostgreSQL

`sql-megasamples-postgres:dev` is `postgres:18.7-trixie` with each dataset's database already in its
cluster (an `append: true` dataset shares its base's), the same `demo` and `admin` accounts, the
superuser `postgres` with factory password `root`, and a `megasamples` database holding the
registry. Tables, data, keys, indexes, foreign keys, check constraints, stored generated columns,
views, stored routines (as PL/pgSQL; a procedure that returns rows is a function you
`SELECT * FROM`), triggers, `ON UPDATE CURRENT_TIMESTAMP` columns and full-text indexes (GIN over
`to_tsvector`) are all ported. Of the corpus's 69 views two are not carried (they reach into
another database), and the one spatial index is not; each database's registry row and
[`CATALOGUE.md`](CATALOGUE.md) say exactly which. The identical table set is kept, so a query
written for one engine names the same tables on the other.

```sh
psql -W -h 127.0.0.1 -p 5432 -U demo sakila
```

**How `demo` is kept read-only on PostgreSQL.** `demo` reads sample tables, including
tables `admin` later creates in a sample database's `public` schema. It has no write privilege on them,
no `TEMPORARY` privilege, cannot create large objects, and can execute only allowlisted routines.
A small server extension, `read_policy`, loaded into every PostgreSQL server the image starts,
backs this up by refusing the few ways a read-only role could otherwise create or change things.
The image refuses to start if that extension would not be loaded, or on a data directory made
before it existed. This keeps a samples server tidy for people who should only look; it is not a
security product, and the `postgres` superuser can change it.

**The PostgreSQL `copy` client needs libpq.** The package installs the pure Psycopg distribution,
which loads the system's libpq (for example Debian's `libpq5`). Without it,
`megasamples copy … postgres` exits 3 with the code `client-library` and contacts no server.

### SQLite

`sql-megasamples-sqlite:dev` carries one file per database under `/data` plus
`/data/megasamples.sqlite`, the registry, and the `sqlite3` shell. The same files sit under
`build/sqlite/<database>/` on the machine that built them, for readers that want a database
without a server, and are what [DoltLite](https://github.com/dolthub/doltlite) opens directly. Types are declared in
MySQL's terms (`DECIMAL(10,2)`, `DATETIME`, `VARCHAR(45)`) so readers see the intent; foreign keys are
declared and verified, and enforced by the reader's `PRAGMA foreign_keys=ON`, as with any SQLite file.
Views, triggers, `ON UPDATE` columns and full-text indexes (an FTS5 table beside each indexed
table, kept in step by triggers) are ported; SQLite has no stored routines, so the 42 routines are
not, nor are the views that call them, the three views that read XML, and a handful of others the
catalogue names, every one with its reason in `datasets/<name>/ports/not_ported.yaml`.

```sh
docker exec -it megasamples-sqlite sqlite3 /data/sakila.sqlite
docker run --rm -it sql-megasamples-sqlite:dev sqlite3 /data/chinook.sqlite
```

The consoles read the SQLite files from a shared volume, `megasamples-sqlite`. Every time the SQLite
container starts, it copies the image's files into that volume again, so changes made there through
a console last only until the next start.

### How the ports are made, and why you can trust them

One program, `megasamples/port/`, reads each database's schema, views, routines and triggers from
the MySQL build server's `information_schema` and its rows from the MySQL Shell dump, applies one
type-mapping table and one DDL emitter with two dialects, translates every view, routine body and
trigger by rule, and loads the result with the engine's own tools (`psql \copy`, the `sqlite3`
driver). Nothing is written by hand and nothing is guessed: a type with no mapping or a function the
target lacks stops that object with its name. The DDL, the translated objects and the not-ported
list of every dataset are committed under `datasets/<name>/ports/`, so a rule change shows up as a
diff, and `make check` regenerates them and fails on any byte of difference. The port is then
verified against the same `datasets/<name>/tests/` files as MySQL.

### What the ports do not carry, and why

Everything an engine cannot carry is refused by name, with its reason, in three places:
`datasets/<name>/ports/not_ported.yaml`, the `not_ported` column of that database's registry row
inside the image, and the tooltip behind "n not ported" on the landing page. Every one is an
engine's limitation rather than a translation left undone
([the record](knowledge/decisions/programmable-object-parity.md) has the evidence):

| what | engines | why |
|---|---|---|
| 2 views and 3 foreign keys of `oracle_oe` that reach into `oracle_hr` | both | a PostgreSQL database or a SQLite file cannot reference another database |
| the 42 stored routines, and the 2 `employees` views that call them | SQLite | SQLite has no stored routines |
| 3 AdventureWorks views that read XML with `EXTRACTVALUE` | SQLite | SQLite has no XML functions (PostgreSQL carries them through `xpath()`) |
| `sakila.actor_info` | SQLite | `group_concat` cannot combine DISTINCT with a separator or an ORDER BY |
| the `oracle_oe` trigger that assigns `line_item_id` before an insert | SQLite | a SQLite trigger cannot modify the row being inserted, and the key must be there first |
| 4 AdventureWorks `AUTO_INCREMENT` columns inside composite keys | SQLite | SQLite auto-assigns only a single-column INTEGER PRIMARY KEY; an insert must supply the value |
| the spatial index on `sakila.address` | both | core PostgreSQL indexes geometry only with PostGIS; SQLite has no geometry type. The column itself is ported as standard WKB |

Two comparisons are weaker than a digest and say so in the verification output: a view whose
`GROUP_CONCAT` has no ORDER BY is held to its row count, and on SQLite, which does decimal
arithmetic in floating point, a view's computed decimal columns are left out of the digest.

## The accounts

| account | engines | what it can do |
|---|---|---|
| `demo` | MySQL, PostgreSQL | read the sample databases and the registry; no writes (details above) |
| `admin` | MySQL, PostgreSQL | change anything in the sample databases; on PostgreSQL it owns them but is not a superuser |
| `root` / `postgres` | MySQL / PostgreSQL | the engine's superuser |
| `copier` | MySQL, PostgreSQL | make, change and remove copies under the prefix `copy_` (see [Copies](#copies-a-database-to-test-on-then-throw-away)) |
| readers and writers you declare | MySQL, PostgreSQL | readers read the sample databases or a copy namespace; writers can also insert, update and delete rows in the sample databases |

**Passwords.** `demo`, `admin`, `root` and `postgres` take their passwords from the private `.env`
file: `DEMO_PASSWORD`, `ADMIN_PASSWORD`, `MYSQL_ROOT_PASSWORD` and `POSTGRES_PASSWORD`. For a new
setup, `umask 077; cp .env.example .env; chmod 600 .env`, edit it, then `make up`. The factory
values above apply only where `.env` does not change them. Never commit `.env`.

`copier` and the readers and writers you declare are created **without a usable password**: set one
before first use, as the copy walkthrough shows. They lose it again whenever the engine is
recreated from its image (`make down`, a whole-engine reset, or `make up` after a rebuild).

**Declaring readers and writers.** In `megasamples.yaml`, before building the image:

```yaml
accounts:
  readers: [{name: analyst, scopes: [working]}]      # working = the sample databases; or a copy prefix such as copy
  writers: [{name: loader, scopes: [working]}]       # writers: rows in the sample databases only
```

## Copies: a database to test on, then throw away

A copy is a private, writable database made from a pristine snapshot of a sample database (its
**template**, baked into the image). Make one, run your tests against it, change anything, and
throw it away; the sample databases and other copies are untouched. Copies are made with the
`megasamples copy` command, which prints one JSON document and exits with a code a script can act
on.

**The words used:**
- **target:** `ENGINE:DATABASE` to create, `ENGINE:COPYNAME` to look at or change one copy, and
  just `ENGINE` to list or sweep;
- **prefix:** the namespace copies are made in. The image sets up one, `copy`, owned by the
  `copier` account, holding at most 32 copies;
- **label:** your short name for the copy (lower-case letters and digits, up to 24); one label per
  copy at a time;
- **name and identity:** `create` answers with the copy's database name, such as
  `copy_chinook_5cbcc8902b8a`, and its 32-character **identity**. Commands that change or remove a
  copy need both, so you cannot remove someone else's copy by mistake;
- **lease:** how long the copy is wanted, from `1m` to `7d` (default `24h`). Nothing removes a copy
  when its lease ends; `sweep` removes copies whose lease has ended.

**The commands:**

| command | what it does |
|---|---|
| `create ENGINE:DATABASE --prefix copy --label L [--lease 24h]` | makes a new copy of the database and answers with its name and identity |
| `list ENGINE --prefix copy [--label L]` | lists the copies in the namespace, with their state and lease |
| `show ENGINE:COPYNAME` | one copy's state, lease and details |
| `renew ENGINE:COPYNAME --identity ID --lease 2h` | sets the copy's lease to end that long from now |
| `release ENGINE:COPYNAME --identity ID` | ends the lease now, so the next `sweep` removes the copy |
| `drop ENGINE:COPYNAME --identity ID [--wait SECONDS]` | removes the copy now; `--wait` waits that long for its sessions to end |
| `sweep ENGINE --prefix copy [--dry-run]` | removes every copy in the namespace whose lease has ended, and lists what it kept and why; `--dry-run` only reports |

**Exit codes:** `0` done; `2` the command line or password source was wrong; `3` the server could
not be reached and nothing changed; `4` that database has no template; `5` refused and nothing
changed (the JSON's `error.code` says why, for example `label-in-use` or `limit`); `6` busy, try
again; `8` something may have changed and did not finish: the reply carries the copy's identity,
so run `show` and then `drop` or `sweep`.

### PostgreSQL, step by step

Copies are made from the database's template, `<database>_start`, with PostgreSQL's own
`CREATE DATABASE … TEMPLATE`, so a copy of a large database takes seconds. PostgreSQL offers a
template for each sample database in the image's core selection.

```sh
# once, and again whenever the engine is recreated: give copier a password (you type it twice)
docker exec -it megasamples-postgres psql -U postgres -c '\password copier'
umask 077; printf '%s\n' 'the-same-password' > ~/.copier-pg; chmod 600 ~/.copier-pg

C="--host 127.0.0.1 --user copier --password-file $HOME/.copier-pg"
python3 -m megasamples copy create postgres:chinook --prefix copy --label mytest $C
python3 -m megasamples copy list   postgres --prefix copy $C
psql -h 127.0.0.1 -U copier copy_chinook_5cbcc8902b8a              # use the name create printed
python3 -m megasamples copy drop   postgres:copy_chinook_5cbcc8902b8a --identity <identity> $C
```

The password file must belong to you and be readable by nobody else; `--password-stdin` reads it
from standard input instead.

### MySQL, step by step

MySQL has no database templates, so `create` rebuilds the copy from `<database>_start`: the
tables, views and data, inside the namespace that `copier` controls. On MySQL a database with
triggers or stored functions cannot be copied this way, and neither can `oracle_hr` or `oracle_oe`
(they depend on each other) or a database over 512 MB: `create` exits 4 and names the reason.
`chinook` is a good one to start with.

```sh
# once, and again whenever the engine is recreated: unlock copier and give it a password, as root
docker exec -it megasamples-mysql mysql -uroot -p
#   mysql> ALTER USER 'copier'@'%' IDENTIFIED BY 'a-password' ACCOUNT UNLOCK;
umask 077; printf '%s\n' 'a-password' > ~/.copier-my; chmod 600 ~/.copier-my

C="--host 127.0.0.1 --user copier --password-file $HOME/.copier-my"
python3 -m megasamples copy create  mysql:chinook --prefix copy --label mytest --lease 1h $C
python3 -m megasamples copy renew   mysql:copy_chinook_5cbcc8902b8a --identity <identity> --lease 2h $C
python3 -m megasamples copy release mysql:copy_chinook_5cbcc8902b8a --identity <identity> $C
python3 -m megasamples copy sweep   mysql --prefix copy $C          # removes it: its lease has ended
```

### SQLite, step by step

A SQLite copy is a file. The templates are in the image under `/templates`; take them out once,
then make copies into a directory of your own:

```sh
docker cp megasamples-sqlite:/templates ./sqlite-templates
mkdir -m 700 copies
T="--templates ./sqlite-templates --dir ./copies"
python3 -m megasamples copy create sqlite:sakila --prefix copy --label mytest $T
sqlite3 copies/copy_sakila_5cbcc8902b8a.sqlite                    # use the name create printed
python3 -m megasamples copy drop sqlite:copy_sakila_5cbcc8902b8a --identity <identity> $T
```

SQLite copies need no account or password. The command keeps its records in `copies/.megasamples`,
which must stay private to you.

## Putting the data back

MySQL `admin` has `ALL PRIVILEGES WITH GRANT OPTION` on every database (`*.*`).

PostgreSQL `admin` has `CREATEDB` and `CREATEROLE`, owns the sample databases,
and has registry-table privileges without grant option; it is not a superuser.

So anything `admin` or a writer changes can be undone. Nothing a client writes reaches the images,
so the shipped state is always one command away. `make reset` returns what you name to exactly
what the images ship; nothing is reset without naming it:

```sh
make reset R=all                                 # every engine in the stack
make reset R=postgres                            # one engine, every database it has
make reset R="postgres:northwind mysql:sakila"   # single databases; the rest are not touched
make reset ENGINE=postgres D=quick               # configure's selectors: core | quick | all | a tier | a list
python3 -m megasamples reset --help              # the same, without make
```

* **A whole engine** is recreated with a fresh copy of its image's data directory, in seconds.
  Everything made since goes: rows, tables, databases, **copies**, accounts, roles, privileges and
  the passwords you set for `copier` and declared accounts.
* **A single database** is restored from a disposable container running the same image: MySQL and
  PostgreSQL dump it there and load it over the running one, then check each table's row count
  against the image; SQLite restores both `/data` and the shared console copy from the pristine
  file and checks their SHA-256 hashes. Copies, accounts and privileges stay as they are.

Datasets sharing a database reset together. Both SQLite reset paths briefly stop and restart the
running SQLite consoles, closing their connections. Close any SQLite shell you opened by hand first.
Resets use the private `.env` passwords. Two resets of the same engine at once are refused; retry
after the first finishes.

`python3 -m megasamples reset --status postgres` prints, as JSON, any PostgreSQL data directory left
without a database (see [Limits](#limits)); `make up` warns about them too.

## Stopping, and what is kept

`make up` brings the engines and the consoles up as one stack, and `make down` takes it away again.
`make down` and `make clean-all` remove each engine's working data with its container: the
volume holding its data directory goes too, so **every change and every copy is lost**, and the
next `make up` starts every engine from its image again. `make down` prints a line saying so before
it starts. For SQLite, the named `megasamples-sqlite` volume stays, and the next start
replaces the files the image carries and leaves any other file in the volume (a database from an earlier
selection stays until removed).

`make up` after you rebuild an image recreates that engine from the new image, which also
discards its working data and copies. Save anything you want to keep first, with `mysqldump`,
`pg_dump` or by copying a SQLite file out.

## Upgrading from an earlier build

1. Save anything you made that you want to keep (see above). The new images start from their own data.
2. Update the checkout, then `uv sync --locked`.
3. Rebuild: `make run` (or `make image ENGINE=...` for one engine).
4. `make up`. Each engine whose image changed is recreated from the new image. Your `.env`
   passwords are reapplied; set the `copier` passwords again before making copies.

The new PostgreSQL image will not start on a data directory made by an earlier image: it stops with
a message instead of serving it. `make up` gives it a fresh one. If you start it by hand on an old
volume, start it on a new volume instead, and move your own work across with `pg_dump` from the old
image and a load into the new one.

## Limits

- `make down`, and `make up` after a rebuild, discard each engine's working data and every copy.
- SQLite samples are copied into the console volume again at every start, so console edits to them
  do not survive a restart.
- MySQL copies are rebuilt with the image's default character set (`utf8mb4`); a database whose
  objects were made under another character set may not copy exactly.
- On MySQL, databases with triggers or stored functions, the Oracle HR/OE pair and databases over
  512 MB have no template.
- Interrupted commands and full disks are not certified. A `copy create` cut off part way can leave
  a copy that `drop` and `sweep` keep (state `interrupted`); a whole-engine reset clears it. On
  PostgreSQL, a crash or cancel at the wrong moment of a copy can leave a data directory with no
  database: it only takes disk, `make up` and `reset --status` report it, and the next whole-engine
  reset or `make down` removes it.
- PostgreSQL's read-only `demo` is a convenience for a samples server, not a security boundary.
- The console ports and the database ports listen on `127.0.0.1` only; publishing them wider is a
  deliberate edit of your own.

## Connect with your own tool

Every server engine listens on `127.0.0.1` of the machine running the stack. DBeaver, DataGrip,
TablePlus, VS Code's database extensions, a language driver or the engine's own client take these
details as they are; the console index page repeats them with the ports you configured. The
passwords below are the **factory** ones; use yours where `.env` changed them.

| | MySQL | PostgreSQL | SQLite |
|---|---|---|---|
| address | `127.0.0.1` port `3306` | `127.0.0.1` port `5432` | files, no server |
| read only | `demo` / `demo` | `demo` / `demo` | — |
| full access | `admin` / `admin` (all privileges) | `admin` / `admin` (owns every sample table) | — |
| superuser | `root` / `root` | `postgres` / `root` | — |
| database | any of the 21, e.g. `sakila` | one per database (an append dataset shares its base's); connect to it, or to `megasamples` for the registry | one file per database |
| client | `mysql -h 127.0.0.1 -P 3306 -u demo -p sakila` | `psql -W -h 127.0.0.1 -p 5432 -U demo sakila` | `sqlite3 sakila.sqlite` |
| URL | `mysql://demo:demo@127.0.0.1:3306/sakila` | `postgresql://demo:demo@127.0.0.1:5432/sakila` | the file's path |
| JDBC | `jdbc:mysql://127.0.0.1:3306/sakila` | `jdbc:postgresql://127.0.0.1:5432/sakila` | `jdbc:sqlite:/path/to/sakila.sqlite` |

MySQL 9 authenticates with `caching_sha2_password` only, so use a client or driver from the MySQL 8
era or newer. `docker cp megasamples-sqlite:/data/sakila.sqlite .` takes a SQLite file out, and DB
Browser for SQLite, DBeaver, DataGrip or Python's `sqlite3` open it as it is. Run
`PRAGMA foreign_keys=ON` to enforce the foreign keys the file declares; a full-text index is an
FTS5 table named `<table>_<index>_fts`.

## The consoles

Every port binds to `127.0.0.1`: an unauthenticated database UI should not appear on the network
because someone opened a laptop in a café. Only CloudBeaver and DbGate browse all three engines.

| | address | browses | notes |
|---|---|---|---|
| **console index** | **<http://127.0.0.1:8080/>** | every engine | **start here**: how to connect your own tool, then every database on every engine with its size, licence and what a port left out |
| CloudBeaver | <http://127.0.0.1:8084/> | MySQL, PostgreSQL, SQLite | opens as a guest; both accounts on each server engine and one connection per SQLite file |
| DbGate | <http://127.0.0.1:8083/> | MySQL, PostgreSQL, SQLite | every connection preconfigured, one per SQLite file |
| Adminer | <http://127.0.0.1:8082/> | MySQL, PostgreSQL | the index page's Adminer card says what to type for each engine and opens Adminer filled in |
| phpMyAdmin | <http://127.0.0.1:8081/> | MySQL only | signed in already; the server menu switches account |

Inside the stack an engine is reached by its service name (Adminer's "Server" field takes `mysql`
or `postgres`), and from your machine by `127.0.0.1` and the port above. `compose.yaml` is
generated from `megasamples.yaml` by `make up` (or `make compose`); every service carries a memory
limit and every image is pinned by digest.

## The configuration file

```yaml
engines:
  mysql: {datasets: core}          # core | quick | all | a tier name | [sakila, chinook, ...]
  postgres: {datasets: core, templates: core}   # templates: core (default) | none | [chinook, ...]
  sqlite: {datasets: quick}
consoles: [landing, phpmyadmin, adminer, dbgate, cloudbeaver]
ports: {mysql: 3306, landing: 8080, phpmyadmin: 8081, adminer: 8082, dbgate: 8083, cloudbeaver: 8084}
build: {threads: 4, keep_build_server: false, scale_factor: 1}
downloads: {concurrency: 3}
copies:
  namespaces: [{prefix: copy, owner: copier, max_copies: 32}]   # the default
accounts: {readers: [], writers: []}                            # see "The accounts"
```

`make run` reads it and, for every engine named, fetches the datasets' artifacts, converts and
loads them, verifies them and bakes the image; `make up` starts what was built. Naming a dataset
for any engine also builds it in the MySQL build server, because that is where every port comes
from. `templates` chooses which databases get a copy template. Copy namespaces and declared
accounts are baked into the image, so change them before `make image`.
[`megasamples.example.yaml`](megasamples.example.yaml) documents the other keys.

## Downloads: once, verified, watched

`make fetch` (which `make run` and `make <dataset>` call first) downloads each artifact in
`manifest.yaml`, verifies its SHA-256 against the recorded value, and writes a marker beside it.
**A verified file is never fetched again**, so an interrupted build resumes where it stopped. A
transfer that makes no progress for two minutes is retried over IPv4.

There are no release assets: the repository is what is published, and every byte of data comes from
its upstream to your machine. Two core datasets need a hand from you:

* **`lahman`** (baseball, 27 tables) is published behind a SABR share link that no script can
  fetch. Download it in a browser from the URL the fetch prints
  (<https://sabr.box.com/s/y1prhc795jk8zvmelfd3jq7tl389y6cd>), put it at
  `downloads/lahman/lahman_1871-2025_csv.zip`, and the next `make run` verifies its checksum like
  every other artifact.
* **`chicago_crimes`** is a live feed: the portal amends past years, so its 2024 extract changes
  from time to time. A build takes whatever the portal serves that day and records what it got; the
  dataset's tests hold a build to floors and structure rather than to exact bytes, so your row
  counts may exceed the documented ones. `MEGASAMPLES_REFRESH_LIVE=1 make fetch` takes the feed
  again. For any other artifact whose upstream has moved, and for a file you placed under
  `downloads/` yourself, `MEGASAMPLES_ACCEPT_DRIFT=1` accepts the bytes and re-pins the manifest.

A dataset whose download is not in place is left out of every engine's build and image and named
at the end of `make run`, which then exits 1.

## Building piece by piece

Every command is a `make` target, and every target is a one-line shim over
`python3 -m megasamples <command>`: `make -n <target>` shows exactly what will run, and
`python3 -m megasamples --help` lists every command.

```sh
make sakila                        # fetch, convert, load and verify one dataset on MySQL
make build D="sakila chinook"      # the same for several
make build ENGINE=postgres D=sakila   # port a dataset from the MySQL corpus and verify it there
make build ENGINE=sqlite           # port every configured dataset to SQLite files
make image ENGINE=postgres         # bake the configured datasets into an engine's image
make image FROM_DUMPS=1            # re-bake MySQL from the dumps already built, without the build server
make restore                       # reload the MySQL build server from its dumps, in a minute, to port from
make test-image ENGINE=sqlite      # assert an image: counts, integrity, accounts, overrides
make test-console                  # assert the consoles are up and the accounts behave on every engine
make reset R=sqlite:sakila         # put one database back as the image ships it
make status                        # the stack, and any transient container
make clean                         # remove the transient containers; the stack keeps running
```

The build servers are reused across a session, because reconverting everything takes hours;
`make image` removes them when an image is done, and `KEEP_BUILD_RESOURCES=1` (or
`build.keep_build_server: true`) keeps them.

## Licensing

**Every dataset keeps its own upstream licence.** This repository does not place a single licence
over the data, and several of the licences have obligations that travel with the data — attribution,
and in a few cases share-alike. Before you redistribute anything built from this, read:

* [`LICENSES.md`](LICENSES.md) — every licence in play, and which datasets it covers
* [`NOTICE.md`](NOTICE.md) — the attribution notices that must travel with the data
* `datasets/<name>/LICENSE` and `datasets/<name>/PROVENANCE.md` — per dataset, generated from
  [`knowledge/licenses/`](knowledge/licenses/index.md), never hand-written

Project **code** is **Apache-2.0** — [`LICENSE`](LICENSE) — and that covers the package, converters,
tests, Dockerfiles, knowledge bundle and generated documentation. It covers **none of the data**, and
is not a relicensing of anything upstream: the share-alike datasets stay CC BY-SA and are offered as
such. Where the two could appear to conflict, the dataset's licence governs the dataset and
Apache-2.0 governs the code that processed it. The console index page shows each database's licence
beside it, so the answer to "what am I allowed to do with this table" is one click from the data.

### Share-alike: four datasets must stay under their own licence

`employees`, `lahman`, the Stack Exchange datasets and `wikipedia_simple` are CC BY-SA. A converted
database is an adaptation, so **this project offers those four converted databases under the same
licence** — CC BY-SA 3.0 for `employees` and `lahman`, CC BY-SA 4.0 for Stack Exchange and
`wikipedia_simple` — and so must anyone who redistributes a modified version, in any engine.
[`CATALOGUE.md`](CATALOGUE.md) marks every dataset with what its licence asks of a redistributor.

### Notices that must travel with the data

Chicago's terms require this paragraph **verbatim** wherever the data appears, and reserve the City's
right to require distribution to stop:

> This site provides applications using data that has been modified for use from its original source, www.cityofchicago.org, the official website of the City of Chicago. The City of Chicago makes no claims as to the content, accuracy, timeliness, or completeness of any of the data provided at this site. The data provided at this site is subject to change at any time. It is understood that the data provided at this site is being used at one's own risk.

Two more are required by the terms they were obtained under:

> Data obtained from http://hbiostat.org/data courtesy of the Vanderbilt University Department of Biostatistics.

> Iris data set: Fisher, R. A. (1936), The use of multiple measurements in taxonomic problems, Annals of Eugenics 7(2):179–188. Distributed via the UCI Machine Learning Repository, https://doi.org/10.24432/C56C76, under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Two values corrected per Fisher's paper, as in R and scikit-learn (BSD-3-Clause).

[`NOTICE.md`](NOTICE.md) carries these and every other attribution in full.

### Licensing notes: what is still unresolved

Five licensing questions are genuinely open. None of them blocks using the data; each is recorded
with what was actually read, so you can form your own view rather than inherit an assumption:

| question | status |
|---|---|
| **NYC TLC terms.** The Open Data FAQ says there are no restrictions; the NYC.gov Terms of Use it incorporates reserve all rights | unresolved on the City's own pages; treated as reusable with attribution ([record](knowledge/questions/nyc-open-data-reuse-terms.md)) |
| **Titanic.** hbiostat grants blanket permission with an acknowledgement request, but names no licence | permission relied on, acknowledgement shipped ([record](knowledge/questions/titanic-hbiostat-license-status.md)) |
| **Enron.** No licence text exists; FERC public-record material redistributed by CMU with a privacy request | status inferred, not stated by anyone; CMU's deletion list is applied ([record](knowledge/licenses/enron-public-record.md)) |
| **DVD Store data.** The kit is GPL-2.0-or-later, but the CSVs are generator *output*, which GPL §0 covers only if it is a work based on the Program | treated as redistributable program output ([record](knowledge/questions/dvdstore-generated-data-license.md)) |
| **Jaffle Shop.** The newer dbt-labs/jaffle-shop seeds and the 6-year S3 set carry no licence at all | **not vendored**; only the Apache-2.0 classic seeds are used ([record](knowledge/questions/jaffle-shop-new-repo-license.md)) |

Iris was a sixth: UCI labels it CC BY 4.0 rather than public domain, which is the stricter reading,
so that is the one the project follows ([record](knowledge/questions/iris-uci-cc-by-vs-public-domain.md)).

### Two datasets are never redistributed

Citi Bike and Divvy licences forbid publishing their data as a stand-alone dataset. The loaders ship;
the data does not. They download to *your* machine, which is where the licence attaches, and refuse
to run until you accept it:

```sh
MEGASAMPLES_ACCEPT_BIKESHARE_LICENSE=1 make load-citibike
```

TPC-H, TPC-DS, SSB and TPC-C are **generated on your machine** for the same reason: nothing
TPC-authored is shipped or committed.

### One dataset needs proprietary software to *rebuild* — not to use

WideWorldImporters is published by Microsoft only as a SQL Server backup: its transactional rows are
generated by randomised T-SQL, so no script or CSV form of the released data exists. Re-deriving it
means running **SQL Server 2022 Developer Edition** in a container and accepting
[Microsoft's Developer EULA](https://go.microsoft.com/fwlink/?linkid=857698):

> BY USING THE SOFTWARE, YOU ACCEPT THESE TERMS. IF YOU DO NOT ACCEPT THEM, DO NOT USE THE SOFTWARE.
> … to design, develop, test and demonstrate your programs. You may not use the software on a device
> or server in a production environment.

**Using the images does not involve that licence.** No SQL Server code, tool or layer is in any of
them; the container is deleted when the export finishes — including if it fails — and the data it
produced is MIT, like AdventureWorks and Northwind. Building any other dataset does not involve it
either. You accept it only if you re-run the export yourself, and the target refuses to start until
you do:

```sh
MEGASAMPLES_ACCEPT_MSSQL_EULA=1 make wwi-export   # prints the terms first
```

The acceptance is recorded with the image digest and engine build in
`downloads/wideworldimporters/export/server.json`.

## Beyond the core

The core tier is what an image holds by default. The others are opt-in, because they are large,
licence-gated, or generated — name them in `megasamples.yaml`, or build one directly:

| tier | what | how |
|---|---|---|
| extended | AdventureWorks DW, BTS on-time, WideWorldImporters (+DW), and bigger versions of core datasets (8.2 M Chicago crimes, 3.5 M yellow-cab trips, 1 M- and 10 M-row Contoso, full Enron, full Simple Wikipedia, dba.stackexchange.com, DVD Store reviews) | `make adventureworks_dw`, `make chicago_crimes_full`, `make nyc_taxi_yellow`, … |
| generated | TPC-H, TPC-DS, SSB, TPC-C at a scale factor you choose | `make tpch SF=1`, `make tpcds`, `make ssb`, `make load-tpcc W=1` |
| user-fetched | Citi Bike, Divvy | `make load-citibike`, `make load-divvy` (licence gate above) |

`make help` lists every target; `make list` every dataset.

## Built on this

[`dolt-megasamples`](https://github.com/Reliable-Collaboration/dolt-megasamples) loads these same
databases into [Dolt](https://github.com/dolthub/dolt) — a SQL database with Git-like versioning —
and measures what the same data costs in each engine, in disk, time and memory. It reads the MySQL
image as its input and does not modify it.

It is worth a look if you are choosing between the two, or if you want a worked example of what this
corpus is useful for: twenty-one databases of varied shape and size, all licensed for
redistribution, are a better basis for a storage comparison than any one dataset.

## How the repository is laid out

| Path | What it holds |
|---|---|
| `ARCHITECTURE.md` | how it works: layout, the dataset contract, the MySQL hub, engines, verification, the stack, gates, licensing and publishing |
| `PLAN.md` | what is being built next |
| `CATALOGUE.md` | every dataset: tier, shape, licence, and what that licence asks of a redistributor (generated) |
| `megasamples/` | the package: the pipeline, one subpackage per engine, the upstream-format translators |
| `engines/<engine>/` | each engine's Dockerfile, server configuration and init SQL |
| `consoles/<console>/` | each console's configuration; the generated index page |
| `datasets/<name>/` | per-dataset contract, converter, pinned expectations, licence and provenance, and `ports/`: the generated PostgreSQL and SQLite DDL with what each port leaves out |
| `knowledge/` | OKF v0.2 evidence bundle: datasets, licences, tools, decisions, sources, runbooks, open questions |
| `manifest.yaml` | every downloadable artifact with checksum, size and licence |
| `megasamples.example.yaml` | the stack configuration, documented |
| `downloads/`, `build/` | gitignored: verified upstream artifacts; everything a build produces |

Every factual claim in `ARCHITECTURE.md` and `PLAN.md` traces to a record in `knowledge/`, and
`make check` enforces that the bundle stays internally consistent. If you want to know *why* a
dataset was converted the way it was, that is where the answer is.

## Development

```sh
make check                       # the local gate: bundle, generated files, port records reproducible, unit tests
uv run --locked pytest -q        # the unit tests alone: inventory, configuration, staging, the port toolkit
make build D="$(make -s list-quick)"   # the quick subset end to end, before a push that touches the pipeline
make screenshots                 # retake the README's pictures from the running stack (docs/screenshots/capture.py)
```

If a `docker pull` or a download hangs with no error, suspect IPv6 first — see
[`knowledge/runbooks/ipv6-and-privileges.md`](knowledge/runbooks/ipv6-and-privileges.md), which also
covers the `make pull-image` workaround this project uses to fetch images over IPv4.

The reviewed client inputs and vendor-source read times are in `clients.lock.yaml`.
`make up` builds CloudBeaver, DbGate, Adminer and phpMyAdmin extensions from pinned vendor images,
with the selected JDBC jars, native SQLite module, PostgreSQL library and PHP/Node runtimes. The loader
uses Oracle's matching MySQL command-line clients and C API, with sysbench built against that library.
The complete [LTS audit](docs/history/lts-upgrade-evidence.md) records policies, source read times and compatible targets. `make oracle-client-image` builds the optional current SQL*Plus and
SQL*Loader binaries; `make verify-oracle` retains its explicit database license gate.

For a deliberate Python refresh, update the exact requirements in `pyproject.toml`,
run `uv lock --upgrade`, then `uv sync --locked` and the repository gate. The client
upgrade evidence and the live procedure are in `docs/history/client-upgrade-evidence.md` and
`docs/history/live-upgrade-runbook.md`. The upgrade rehearsal installs and runs tooling only
inside its isolated containers.

The published-endpoint probe uses Psycopg with a current system libpq. The container-only
setup recipe is `docs/validation/install-probe-libpq.py`; the validated rehearsal tools
archive already includes that pinned library. No host installation is required for the rehearsal.
