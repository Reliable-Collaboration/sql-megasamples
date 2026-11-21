# Ideas for later

The owner's ideas for this project. Nothing here is scheduled or promised. `ARCHITECTURE.md`
describes what exists, and an idea leaves this file once it is built.

## Where things stand

The three engines are built: every core dataset is verified on MySQL, and ported and verified on
PostgreSQL and SQLite by one deterministic program whose output is committed and reproducibility-
checked (`ARCHITECTURE.md` sections 3 and 4): tables and rows, and also the views, stored routines,
triggers and full-text indexes, verified by executing them against outputs pinned from MySQL
(section 5). One configuration names any combination of engines, datasets and consoles, and
`make run` then `make up` builds and starts it. The extended-tier datasets are ported too.

Release 2.0.0 adds **copies**: `megasamples copy` makes a private, writable copy of a sample
database on any of the three engines, from a template baked into the image, and lists, renews,
releases, drops and sweeps them. **`make reset`** puts a whole engine, or single databases, back as
the image ships them.

## Idea: the Dolt comparison

`dolt-megasamples` reads the MySQL image and compares Dolt with MySQL on disk, time and memory. It
could add Dolt's siblings:

* **DoltgreSQL** (PostgreSQL wire protocol): loaded from the PostgreSQL port through `pg_dump` and
  `psql`, one Dolt database per sample database, the same disk, time and memory measurements as Dolt.
* **DoltLite** (a SQLite fork that reads stock SQLite files): opened directly on the files under
  `build/sqlite/<database>/`, then committed, so the measurement is what the file costs once it is
  history rather than what a load costs.

Both would go into `dolt-megasamples`, not here.

## Idea: a PostgreSQL browser

pgAdmin or pgweb could join the console registry, after an evaluation is recorded; Adminer, DbGate
and CloudBeaver already browse PostgreSQL.

## Publishing

The repository is the release; no data or file asset is published beside it. No image is published
yet: `make prepub-check` is the checklist for the day one is, and pushing it is the maintainer's
step.
