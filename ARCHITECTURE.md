# Architecture

How sql-megasamples is built and run. Sections are numbered because code and knowledge records
cite them. `README.md` says what the project is for; this says how it works.

## 1. Shape

Three things are chosen independently, and one file names the choice:

* **engines** — the database products the datasets are built for: MySQL, the hub every dataset is
  converted into first, and PostgreSQL and SQLite, ports of that verified corpus (section 3).
* **datasets** — 38 sample and public databases, each converted from its authoritative upstream
  source by a converter committed beside it, each verified against pinned expectations.
* **consoles** — web UIs that come up beside the engines, already connected.

`megasamples.yaml` (section 6) holds the choice. `make configure` writes it interactively; every
command reads it. The Python package `megasamples/` is the whole pipeline; `make` targets are
one-line shims over `python3 -m megasamples <command>` (section 7).

## 2. Repository layout, downloads and build outputs

```
.
├── README.md  ARCHITECTURE.md  PLAN.md  CATALOGUE.md  LICENSES.md  NOTICE.md  LICENSE
├── Makefile                    shims over the package; `make help`
├── manifest.yaml               every downloadable artifact: url, mirrors, sha256, size, licence
├── megasamples.example.yaml    the stack configuration, documented; copy to megasamples.yaml
├── pyproject.toml  uv.lock     the pinned Python stack (`uv sync`)
├── megasamples/                the package
│   ├── cli.py  paths.py  config.py  datasets.py  consoles.py  compose.py  job.py  matrix.py
│   ├── fetch.py  stage.py  canon.py  verify.py  registry.py  catalogue.py  console_page.py
│   ├── provenance.py  prepub.py  audit.py  workspace.py  okf_check.py  okf_fix_quotes.py
│   ├── engines/                one subpackage per engine: mysql/, postgres/, sqlite/ (server, load or port, adapter, image_test)
│   ├── port/                   the MySQL corpus -> engine-neutral model -> other engines (model, typemap, ddl, tsv, record)
│   └── sources/                upstream-format translators and exporters (T-SQL, PL/SQL, .bak, CSV, XML)
├── engines/<engine>/           committed engine assets: Dockerfile, server configuration, init SQL
├── consoles/<console>/         console configuration; consoles/landing/ holds the generated index page
├── datasets/<name>/            dataset.yaml  convert.py  tests/  ports/  LICENSE  PROVENANCE.md  [name_map.yaml]
├── knowledge/                  the OKF v0.2 evidence bundle behind every decision
├── downloads/                  git-ignored: verified upstream artifacts, <id>.ok and <id>.meta.json
└── build/                      git-ignored: stage/<name>/ (converted SQL), <engine>/ (dumps or port files, image context)
```

**Downloads happen once.** `megasamples fetch` reads `manifest.yaml`, tries `url` then each of
`mirrors` with `curl --fail --location --retry 5 -C -`, verifies the sha256 (and the size when the
manifest records one) and writes `downloads/<id>.ok`. A file with a matching `.ok` marker is never
fetched again, on this run or the next, and `.meta.json` records where it came from and when. A
connect or transfer failure is retried over IPv4, and the fallback is recorded, because the hosts
this build touches include several whose IPv6 path hangs on some machines
(`knowledge/runbooks/ipv6-and-privileges.md`). An artifact whose manifest has no sha256 is refused
unless `MEGASAMPLES_TRUST_FIRST_FETCH=1`, which pins the observed digest into the manifest. One
artifact is maintainer-supplied (`manual: true`, Lahman): fetch names the URL and the path and
verifies what is put there.

**Sizes.** The 21 core datasets are 1.4 GB of downloads; the quick subset is 196 MB; the extended
tier adds up to 5.1 GB. `megasamples list` prints every dataset with its download size.

## 3. Datasets, and MySQL as the hub

A dataset directory holds its contract, its converter, its expectations and its generated licence
files. The contract, `dataset.yaml`:

| key | meaning |
|---|---|
| `name`, `database` | the dataset, and the database it loads into (`append: true` datasets add tables to another dataset's database) |
| `tier` | `core` / `core-medium` (in the image), `extended` (opt-in), `generated`, `user-fetched`, `not-shipped` |
| `quick` | in the 15-dataset subset that builds in minutes with no large download |
| `record`, `licenses` | the knowledge record behind it, and its licence record ids |
| `artifacts` | the manifest ids it downloads |
| `stage` | how the converter runs: `extract` members of an archive; `input: artifact` / `dir` / `export` / `none`, with `converter`, `source`, `args`, `scale_factor` (`megasamples/stage.py`) |
| `load` | the staged SQL files, in load order |
| `depends`, `build_license`, `blurb` | cross-database prerequisites; a licence accepted at build time only; a catalogue one-liner |

**Every converter emits MySQL SQL.** `convert.py` reads the upstream artifact — a T-SQL or PL/SQL
install script, a SQL Server export, CSV or Parquet, an XML dump, a generator's output — and writes
one SQL file to `build/stage/<name>/`. The translators it leans on live in `megasamples/sources/`:
`tsql.py` and `tsqlbody.py` (SQL Server scripts and routine bodies), `plsql.py` and
`oracle_convert.py` (Oracle), `wwi.py` with `wwi_export.py` and `mssql.py` (the WideWorldImporters
backup, exported once from a SQL Server container), `csvtable.py`, `bulkinsert.py`,
`hierarchyid.py`. Conversion rules are recorded per dataset in `knowledge/decisions/*-conversion-path.md`
and summarised in each `PROVENANCE.md`.

**MySQL is the hub.** The staged SQL is loaded into a throwaway MySQL build server, verified there
(section 5), and dumped with MySQL Shell. That verified corpus is the input to every other engine.
Naming a dataset for any engine therefore builds it in the MySQL build server first, whether or not
it is in the MySQL image; `make restore` reloads the build server from the dumps in about a minute
when it has been removed. The rationale is in `knowledge/decisions/engine-hub.md`.

**The port is one deterministic program**, `megasamples/port/`, and nothing is written by hand:

| module | does |
|---|---|
| `model.py` | reads a database back from `information_schema` as tables, columns (type, nullability, default, generated expression), indexes, foreign keys and checks, plus the names of its views, routines and triggers |
| `typemap.py` | the one mapping table: a MySQL column to its PostgreSQL and SQLite declarations; a type it does not know stops the build |
| `ddl.py` | one emitter, two dialects: `CREATE TABLE` with keys, defaults, generated columns and enum checks; secondary indexes; foreign keys and checks (inline for SQLite, which cannot add them later); every object a dialect cannot carry is returned by name with the reason |
| `tsv.py` | reads the MySQL Shell dump's chunks (`knowledge/tools/mysql-shell-dump-format.md`) and re-encodes rows for `COPY` |
| `record.py` | writes `datasets/<name>/ports/{postgres,sqlite}.sql` and `not_ported.yaml` |

Rules the emitter follows, each fixed by a verification failure and covered by a unit test: unsigned
integers widen to the next signed type and `tinyint(1)` is never a boolean; enum becomes text with a
membership check and set becomes text; an identity column keeps an integer type; names over 63
bytes are shortened by one function the adapters share; stored generated columns are recomputed by
the target from the translated expression; geometry is standard WKB with longitude first; foreign
keys into another database are dropped and named. Not ported anywhere: views, routines, triggers,
FULLTEXT and SPATIAL indexes, `ON UPDATE CURRENT_TIMESTAMP`, and on SQLite a CHECK using
`regexp_like`. `megasamples ports-check` (part of `make check`) regenerates every committed port
record and fails on a byte of difference, which is what makes the ports reproducible by construction.

Conventions every dataset follows: one database per dataset, lower snake_case names, multi-schema
sources flattened to `<schema>_<table>` (`knowledge/decisions/database-naming-convention.md`,
`schema-to-database-mapping.md`); tables with primary keys first, data, then secondary indexes,
then foreign keys and checks (`indexing-strategy.md`); `utf8mb4` throughout.

## 4. Engines

`megasamples/engines/base.py` is the interface: build a dataset, verify it, bake an image, test the
image, describe the compose service, configure each console, read the registry. `megasamples/engines/__init__.py`
is the registry the configuration names.

### 4.1 MySQL (`engines/mysql/`, `megasamples/engines/mysql/`)

* **Build server.** `mysql:9.7.2` started as a plain container, `megasamples-build-mysql`, with the
  project's `my.cnf`, `--local-infile=1 --skip-log-bin`, `build/stage/` mounted read-only at
  `/context` and `build/` at `/build`. It is reused across a build session and removed by
  `make image` when the image is done (`build.keep_build_server: true` keeps it), or by `make clean`.
* **Load.** Each staged file is streamed into the server in order; a non-append dataset drops and
  recreates its database first, dropping foreign keys that point into it from other databases and
  saying which datasets to reload.
* **Dump.** `util.dumpSchemas` into `build/mysql/dumps/<name>/` (zstd-compressed TSV chunks plus
  DDL), content-addressed by `build/mysql/dumps/<name>.json`.
* **Image.** `engines/mysql/Dockerfile`, a two-stage build: the builder initialises a data directory,
  loads each dump with `util.loadDump` (`deferTableIndexes: all`, so secondary indexes are built
  after the data), loads the time-zone tables, creates the accounts and the provenance registry,
  shuts down; the final stage is `mysql:9.7.2` plus that data directory, `my.cnf` and a wrapper
  entrypoint that applies password overrides at startup. The context is `build/mysql/image/`, which
  `megasamples image` fills with hardlinks to exactly the dumps being baked and the registry SQL for
  them, so the image contains what the configuration names and nothing else. The data directory is
  shipped initialised rather than loaded at first start (`knowledge/decisions/bake-data-vs-initdb.md`):
  first start answers a real query in under two seconds. Tag: `sql-megasamples-mysql:dev`.
* **Accounts.** `root` (password `root`), `admin` (`ALL PRIVILEGES WITH GRANT OPTION`), `demo`
  (`SELECT, SHOW VIEW` only). `MYSQL_ROOT_PASSWORD`, `ADMIN_PASSWORD` and `DEMO_PASSWORD` override
  the passwords at container start.
* **Registry.** The `megasamples.datasets` table inside the image: one row per dataset with tier,
  knowledge record, licence ids, source artifacts with digests, pinned row counts and the build id.
  The catalogue, the landing page and the image tests all read it, so none can drift from what was
  actually baked.
* **Loader image.** `engines/mysql/loader.Dockerfile` builds the generators the generated tier needs
  (SSB's dbgen, sysbench for TPC-C); nothing from it reaches any published image.

### 4.2 PostgreSQL (`engines/postgres/`, `megasamples/engines/postgres/`)

* **Port** (`megasamples pg-port`, or `make build ENGINE=postgres`): the model and the dump become
  `build/postgres/<database>/` — `schema.sql`, `data/<table>.tsv` in `COPY` text format with the
  insertable columns listed, `indexes.sql` (btree, and a GIN index over `to_tsvector('simple', …)`
  for every FULLTEXT index), `constraints.sql` (foreign keys, checks, and `setval` for every
  identity sequence), `routines.sql` (PL/pgSQL), `views.sql`, `triggers.sql` (PL/pgSQL trigger
  functions, including one per `ON UPDATE CURRENT_TIMESTAMP` column), `model.json`, `dropped.txt` —
  and are loaded in that order into a throwaway `postgres:18.6-bookworm` build server,
  `megasamples-build-postgres`, with `\copy`. A procedure that returns rows becomes a function
  `RETURNS TABLE(...)`; its columns are measured once with psql's `\gdesc` on the ported schema and
  recorded in `datasets/<name>/ports/result_sets.yaml`, so the next render needs no server. A
  `complete` marker is written last, and the image builder takes only directories that have it;
  the SQLite port likewise builds its file under a temporary name and moves it into place when done.
  Both are keyed by database, so an `append: true` dataset extends its base's port rather than
  making a second one.
* **Image.** `engines/postgres/Dockerfile`: a builder stage runs `initdb` at the image's own
  `PGDATA`, appends the `host all all all scram-sha-256` rule the official entrypoint would have
  written, starts a private server with bulk-load settings, creates the accounts and the registry,
  replays every port's files, and stops; the final stage is the official image plus that cluster.
  First start answers a real query in under a second; the data directory is 2.6 GB for the 21 core
  databases and the image is 4.1 GB. Details: `knowledge/decisions/postgres-image-shape.md`.
* **Accounts.** `postgres` (superuser, `root`), `admin` (create, alter, drop; `ALL` on every table),
  `demo` (`SELECT` everywhere). `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `DEMO_PASSWORD` override them
  at start through the wrapper entrypoint. Tag: `sql-megasamples-postgres:dev`.
* **Registry.** Database `megasamples`, table `datasets`: MySQL's columns plus `engine` and
  `not_ported`.
* **Verification.** The adapter (`adapter.py`) computes the canonical digest in Python from a
  `COPY ... TO STDOUT` of each table rendered column by column, because PostgreSQL text cannot hold
  the U+0000 sentinel; counts, foreign keys and indexes come from the catalog, with index names
  mapped back to MySQL's.

### 4.3 SQLite (`engines/sqlite/`, `megasamples/engines/sqlite/`)

* **Port** (`megasamples sqlite-port`, or `make build ENGINE=sqlite`): the stdlib `sqlite3` driver
  writes `build/sqlite/<database>/<database>.sqlite` — MySQL-like declared types for their affinity,
  keys, foreign keys and checks inline (a `REGEXP` check becomes a `GLOB` when its pattern is an
  anchored run of character classes), secondary indexes after the data, then an FTS5
  external-content table with three sync triggers for every FULLTEXT index, the views, and the
  triggers; `VACUUM`ed, rollback journal, `application_id` `MSMP`. There is no build server: the
  file is the database. Details: `knowledge/decisions/sqlite-file-conventions.md`.
* **Image.** `engines/sqlite/Dockerfile`: Alpine 3.22 (digest-pinned) with the `sqlite` package
  (SQLite 3.49.2), the files under `/data` and `/data/megasamples.sqlite` as the registry; its default
  command sleeps so the container holds the files for `docker exec` and for the consoles. The 21 core
  databases are 899 MB of files and a 1.3 GB image. The same files stay under
  `build/sqlite/<database>/` for readers that want a database without a server.
* **Stack.** The `sqlite` service copies the image's files into the named volume `megasamples-sqlite`
  at every start, and the consoles that can open SQLite mount that volume read-only, so a rebuilt
  image replaces what they see.
* **Verification.** The adapter opens the file with the stdlib driver and renders each value in the
  canonical text form in Python (decimals at the declared scale, date-times with six fractional
  digits); foreign keys are checked by the orphan query with the model's names; indexes come from
  the pragmas.

### 4.4 The port toolkit (`megasamples/port/`)

One program produces every port, and nothing in it is written by hand per dataset:

* `model.py` reads a database from the MySQL build server's `information_schema` (tables, columns,
  keys, indexes, checks, views with their column types, routines with their parameters, triggers);
  `typemap.py` is the one type-mapping table; `ddl.py` emits the schema, indexes and constraints
  in two dialects; `tsv.py` reads the MySQL Shell dump chunks; `record.py` writes what was decided
  beside the dataset.
* `sqltranslate.py` translates one MySQL statement or expression at a time with sqlglot, then
  applies the rules the corpus needed and MySQL's semantics require (listed in its header): the
  target's function allowlist, so an unknown function stops the port with its name; unquoted
  identifiers resolved to the schema's spelling, because PostgreSQL folds them; a FLOAT operand
  cast to double precision on PostgreSQL, as MySQL computes it; a comparison in a select list cast
  to an integer, since MySQL has no boolean; a compact date literal against a date-time column
  written out in ISO form; `GROUP_CONCAT`, `JSON_TABLE`, `EXTRACTVALUE`, `TO_DAYS`, `ROLLUP` and
  the other constructs each engine spells differently.
* `views.py` renders the views in dependency order; `triggers.py` renders each trigger as a
  PL/pgSQL function and trigger, or as a SQLite trigger that updates the row afterwards where
  MySQL assigns `NEW` (a SQLite trigger cannot modify the row being inserted); `routines.py`
  translates the stored routines to PL/pgSQL over a closed census of constructs (`DECLARE`, `SET`,
  `SELECT INTO`, `IF`/`ELSEIF`, `CASE`, `RETURN`, DML, `CALL`, temporary tables, the two handler
  forms, `LEAVE`, transaction statements, user variables), and anything outside it drops the
  routine by name.
* Anything an engine cannot carry is dropped **with its reason**, by name, into
  `datasets/<name>/ports/not_ported.yaml`; what a routine body had to change is in
  `ports/notes.yaml`. `megasamples ports-check` (part of `make check`) re-renders every port's DDL,
  routines, views and triggers from the build server and fails on any byte of difference from what
  is committed, so a port is reproducible by construction and reviewed as a diff.

## 5. Verification

Every stage where a defect can be introduced has a check, and the expectations are engine-neutral
files under `datasets/<name>/tests/`, so a port is verified against exactly what MySQL was.

| stage | proves | where |
|---|---|---|
| S1 fetch | every artifact's sha256 equals the manifest | `megasamples fetch` |
| S3 counts | `SELECT COUNT(*)` per table equals `tests/expected_counts.yaml` | `megasamples verify <dataset> counts` |
| S4 digests | per table, `(COUNT, BIT_XOR, SUM mod 2^64)` over the canonical row digest equals `tests/checksums.yaml` | `verify … digests` |
| S5 integrity | every foreign key has zero orphans, including cross-database keys | `verify … fks` |
| S6 indexes | every index in `tests/indexes.yaml` exists with the same columns, uniqueness and type; smoke queries do not full-scan the tables `tests/explain.yaml` names | `verify … indexes explain` |
| S7 semantics | canonical queries return `tests/smoke.expected.yaml` | `verify … smoke` |
| S4v views | every view's row count and canonical digest equal `tests/views.yaml`, pinned from MySQL; a view with an unordered `GROUP_CONCAT` is held to its row count, and on an engine without decimal arithmetic a view's computed decimals are left out of the digest (`x_exact`, `s_exact`) | `verify … views` |
| S8r routines | every call in `tests/routines.yaml` (arguments as MySQL literals, inside a rolled-back transaction) prints what MySQL printed, normalised line by line by `megasamples/probe.py` (booleans, decimal scale, CHAR padding, row order) | `verify … routines` |
| S9 triggers | every scenario in `tests/triggers.yaml` (MySQL-dialect DML, translated for the port by the same translator that ported the triggers, then a probe query, then rollback) prints what MySQL printed | `verify … triggers` |
| S8 image | per engine: the image answers a real query within 30 s, holds exactly the registered datasets with their pinned counts, `demo` cannot write and `admin` can, no account is passwordless, password overrides apply (over the network for PostgreSQL); MySQL adds `CHECK TABLE` and time-zone conversion, SQLite adds `integrity_check`, `foreign_key_check` and the journal mode | `megasamples test-image --engine …` |
| S10 console | every console answers HTTP 200, the landing page names every registered database of every engine, CloudBeaver is out of its wizard and opens each engine's connections, `demo` reads and cannot write and `admin` writes on each server engine | `megasamples test-console` |

The canonical row digest (`megasamples/canon.py`, `knowledge/decisions/test-checksum-method.md`) is
one definition computable in SQL and in Python: columns in DDL order joined by U+001F, NULL as
U+0000, dates and times in fixed formats, binary and geometry as lowercase hex of standard WKB;
float, double and JSON columns are excluded and compared by aggregates instead. Because it is
defined as text, the same digest is computed on every engine — in SQL on MySQL, in Python from
`COPY` output on PostgreSQL, in Python from the driver on SQLite — which is what makes a port
provably equal to the MySQL corpus. `verify --engine postgres` runs counts, digests, foreign keys,
indexes (a FULLTEXT index counts as carried by its GIN or FTS5 form), views, routines and triggers;
`--engine sqlite` the same minus routines, which it has none of; explain and smoke stay MySQL-only,
since their queries are written in its dialect. `--pin` writes observed values instead of comparing
them, which is how a native-SQL dataset with no converter-side baseline gets its first
expectations; a `# authority:` header on a counts file marks it as generated from the source and
refuses pinning. The routine calls and trigger scenarios are the one hand-written part: the
arguments and the DML are chosen per dataset, while their outcomes are always pinned from MySQL.

## 6. The stack

**`megasamples.yaml`** (documented in full in `megasamples.example.yaml`):

```yaml
engines:
  mysql: {datasets: core}          # core | quick | all | a tier | [names]
  postgres: {datasets: core}
  sqlite: {datasets: core}
consoles: [landing, cloudbeaver, dbgate, adminer, phpmyadmin]
ports: {mysql: 3306, postgres: 5432, landing: 8080, phpmyadmin: 8081, adminer: 8082, dbgate: 8083, cloudbeaver: 8084}
build: {threads: 4, keep_build_server: false, scale_factor: 1}
downloads: {concurrency: 3}
```

Without the file, the built-in default is that example. `make configure` writes it from an
interactive engine × dataset matrix and a console list; `megasamples.config` validates it (unknown
engines, consoles that need an engine not selected, port clashes) before any command uses it.

**`compose.yaml` is generated** from the configuration by `megasamples compose` (which `make up`
runs first), so the stack is exactly what was chosen. Rules the generated file follows:

* One Compose project, `sql-megasamples`; container names `megasamples-<engine>` and
  `megasamples-<console>`. It comes up and goes down together; `docker compose up -d mysql` is the
  database alone.
* Every service has a `mem_limit`: a container with no limit can see the whole VM, so one process
  going wide takes the machine down rather than failing on its own. MySQL is given 1 GB with a 256 MB
  buffer pool named explicitly, because MySQL sizes its pool from the host's memory, not the container's.
* Every port binds to `127.0.0.1`. Publishing a console more widely is a deliberate edit.
* Images are pinned by digest. `megasamples pull-image` fetches an image over IPv4 for daemons that
  cannot reach the registry, and the digest is what makes the two paths name the same bytes.
* A console is started only when an engine it can browse is selected, and is configured for every
  engine present, read-only account first. `megasamples/consoles.py` is the registry: which engines
  each console supports, its image, its memory, how it is pointed at a database. phpMyAdmin browses
  MySQL; Adminer MySQL and PostgreSQL; DbGate and CloudBeaver all three, with one connection per
  SQLite file. `megasamples console-config` (run by `make up`) generates CloudBeaver's connections
  and its server configuration with the three drivers enabled — CloudBeaver disables file-based
  drivers such as SQLite by default (`knowledge/runbooks/cloudbeaver-unattended-startup.md`).
* Passwords come from `.env` (`.env.example` is the template): compose passes each value to the
  server, which applies it at startup, and to every console, so the two cannot drift apart.

**The landing page** (`consoles/landing/index.html`) is generated by `megasamples console-page` from
the registry inside the running image: every database with tables, rows, size, licence and a
one-line description taken from its knowledge record, links into the consoles that accept a
database in their URL, the connection details and both accounts.

**Transient containers** — the build server, the SQL Server behind `wwi-export`, the Oracle behind
`verify-oracle`, the loader, the servers the tests start, the pristine copy a reset restores from —
carry the label
`megasamples.transient=true`. `make status` lists them beside the stack; `make clean` removes them;
`make clean-all` takes the stack down too.

## 7. Commands and gates

`python3 -m megasamples --help` lists every command; each has its own `--help`. The ones a build
runs, in order: `fetch` → `stage` → `load` → `verify` → `dump` for MySQL, then `pg-port` or
`sqlite-port` → `verify --engine …` for a port, then `image` → `test-image` per engine; wrapped as
`build` (through verify, for the configured datasets of an engine), `image`, and `run` (build and
image for every configured engine, `--up` to start the stack afterwards). `make <dataset>` is
`build --engine mysql <dataset>`; `make restore` reloads the MySQL build server from its dumps.
`reset` (`megasamples/reset.py`) puts the running stack back as its images ship it: `all`, an engine,
or `engine:dataset` pairs, or `--engines`/`--datasets` with `configure`'s selectors. A whole engine
is recreated with a fresh data directory (`up --force-recreate --renew-anon-volumes`, then the
replaced anonymous volume removed by name); a single database is dumped from a transient container
pinned to the running container’s immutable image ID and loaded over the running copy
(SQLite: both `/data` and the shared volume), then checked against the pristine copy. Reset
selectors omit build prerequisites in other databases. Disposable containers use `--rm`, with
`rm -fv` cleanup on failures as well. Both SQLite paths stop running SQLite consoles before
replacement and restart them in a `finally` block; manually opened shells must be closed first.

| gate | command | cost | when |
|---|---|---|---|
| bundle and generated files | `make check` | seconds, no Docker | before every commit |
| the quick subset end to end | `make build D="$(make -s list-quick)"` or a config with `datasets: quick` | 15 datasets, minutes | before a push that touches the pipeline |
| the image and S8 | `make image` then `make test-image` | one bake | with the above |
| everything | a config with `datasets: core`, then `make run` and `make test-image` | 21 datasets, a 3.5 GB image | before publishing an image |
| the console | `make up` then `make test-console` | seconds | when the stack or a console changes |

`make check` runs the knowledge-bundle checker (`okf_check.py`: frontmatter, sections, trust rules,
links, indexes, log order), the frontmatter-quoting check, the drift checks for every generated file
(`LICENSE`, `PROVENANCE.md`, `NOTICE.md`, `LICENSES.md`, `CATALOGUE.md`, the README's database
table), the port-record reproducibility check for every dataset loaded in the MySQL build server,
and the unit tests.

## 8. Licensing and publishing

**Every dataset keeps its own upstream licence**; the project's code is Apache-2.0 and covers none
of the data. `megasamples provenance` generates, from the knowledge bundle and never by hand:
`datasets/<name>/LICENSE` (the upstream terms in full), `datasets/<name>/PROVENANCE.md` (upstream
URL, every source artifact with its sha256, what was and was not ported, measured shape),
`LICENSES.md` and `NOTICE.md`. The image carries them under `/usr/share/doc/megasamples`, because an
image is a redistribution and several licences require the notice inside one.

Four converted databases are share-alike and are offered under the same licence: `employees` and
`lahman` (CC BY-SA 3.0), the Stack Exchange datasets and `wikipedia_simple` (CC BY-SA 4.0). Two
datasets are never redistributed in any form: Citi Bike and Divvy, whose licences prohibit it; the
project ships loaders that fetch to the user's machine. The TPC family is generated on the user's
machine and nothing TPC-authored is committed or shipped.

**The pre-publication checklist**, `megasamples prepub-check`, is ten items and is meant to be re-run
on the day of publication: (1) generated licence and provenance files are current; (2) every
dataset has `LICENSE` and `PROVENANCE.md` pinning what it downloads; (3) the README states the
share-alike terms; (4) no Citi Bike, Divvy or TPC data in the repository or the image
(`megasamples audit-assets`); (5) TPC licences carry the EULA legend and no TPC metric names are
used; (6) no non-redistributable binaries — `.bak`, `.mwb`, `.pbix` — anywhere the project publishes;
(7) Enron provenance documents the personal-data handling and removal procedure; (8) Stack Exchange
provenance records the 2024-04-02 snapshot and the unaccepted click-through; (9) the Chicago,
hbiostat and Iris notices are verbatim in `README.md` and `NOTICE.md`; (10) the open licensing
questions are listed in the README with their status.

**There are no release assets.** The repository is what is published; every byte of data comes
from its upstream to the user's machine, verified against the digests `manifest.yaml` pins, and
what a script cannot fetch the README tells the user how to obtain (`lahman`, behind a share link)
or how to accept when the upstream has moved (`chicago_crimes`, with `MEGASAMPLES_ACCEPT_DRIFT=1`
re-pinning the manifest and `verify --pin` the expectations). **Nothing in this repository
publishes.** Pushing an image or making anything public is the maintainer's decision and action,
never the build's; `knowledge/decisions/no-release-assets.md` records why nothing is mirrored.

## 9. The knowledge bundle, and how to extend the project

`knowledge/` is an OKF v0.2 bundle: datasets, licences, tools, decisions, sources, runbooks and open
questions, with the conventions in `knowledge/runbooks/knowledge-bundle-conventions.md` and the
checker in `megasamples/okf_check.py`. A claim is `verified` only when it was read in a source
listed on the record or produced by a command whose output is recorded; estimates stay `inferred`.

**To add a dataset:** research it into `knowledge/datasets/<name>.md` and the licence into
`knowledge/licenses/`; add its artifacts to `manifest.yaml`; create `datasets/<name>/dataset.yaml`
and `convert.py`; `make <name>` with `megasamples verify <name> --pin` for the first expectations;
`make provenance` and `make catalogue`; `make check`.

**To add an engine:** implement `megasamples/engines/<name>/` against `base.Engine` — a port that
reads the model and the dump through `megasamples/port/`, a `Dialect` in `ddl.py` and a column in
`typemap.py`, a verification adapter, an image and its test — register it in
`megasamples/engines/__init__.py`, put its Dockerfile and configuration under `engines/<name>/`,
declare which consoles can browse it in `megasamples/consoles.py`, and add its section here.
