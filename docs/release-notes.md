# Release notes

## Release 2.0.0

### What's new

- **Copies to test on.** `megasamples copy` makes a private, writable copy of a sample database
  on PostgreSQL, MySQL or SQLite, and lists, shows, renews, releases, drops and sweeps copies. Each
  copy has a label, an identity and a lease, and every command prints one JSON document with a
  stable exit code. PostgreSQL copies are made from a template database baked into the image, in
  seconds; MySQL copies are rebuilt from a pristine schema; SQLite copies are files in a directory
  of your own. A `copier` account owns the `copy_` namespace (up to 32 copies by default).
- **Declared readers and writers.** `accounts.readers` and `accounts.writers` in
  `megasamples.yaml` create extra accounts in the image: readers read the sample databases or a copy
  namespace, writers can also change rows in the sample databases.
- **Reset clears server copies too.** `make reset` still puts a whole engine, or single databases,
  back as the image ships them; a whole-engine reset now also removes every MySQL and PostgreSQL
  copy. `reset --status postgres` reports leftover PostgreSQL data directories, and `make up` warns
  about them.
- **A stricter read-only `demo` on PostgreSQL.** `demo` has no `TEMPORARY` privilege, cannot create
  large objects and can run only allowlisted routines; a small server extension, `read_policy`,
  backs this up, and the image will not start without it.
- **`make down` says what it discards** before it does it.

### What changed for existing users

- **Rebuild and start fresh.** The new images start from their own data. `make up` after
  rebuilding recreates each changed engine, discarding its working data; save anything you made
  first. The new PostgreSQL image refuses a data directory made by an earlier image.
- **MySQL `demo` reads less.** It reads the sample databases, explicitly enabled foreign
  namespaces and the registry tables, instead of every database on the server (`*.*`, system
  schemas included).
- **`make down` and `make clean-all` now remove each engine's data volume** with its container, so
  nothing is left behind; the next `make up` starts from the images. The SQLite console volume stays.
- **Set the `copier` password** (and any declared account's) before using copies; the README shows
  how. It is needed again whenever the engine is recreated from its image.
- **The SQLite start copy removes stale journals.** A `-journal`, `-wal` or `-shm` file left beside
  a shared SQLite file is removed before the fresh copy replaces it, so it cannot be applied to the
  fresh sample.

### Known limits

- `make down`, and `make up` after a rebuild, discard each engine's working data and every MySQL
  and PostgreSQL copy. SQLite copies stay in your directory.
- SQLite samples are copied into the shared volume again at every start; the consoles read them
  read-only.
- MySQL copies assume the image's default character set (`utf8mb4`).
- On MySQL, databases with triggers or stored functions, the Oracle HR/OE pair and databases over
  512 MB have no template.
- On PostgreSQL, the sample tables in a copy stay owned by `admin`: `copier` changes rows and adds its own objects, but cannot
  `ALTER`, `TRUNCATE` or index the sample tables.
- Interrupted commands and full disks are not certified: an interrupted `copy create` can leave a
  copy that `drop` and `sweep` keep, which a whole-engine reset clears on MySQL and PostgreSQL and
  you delete by hand on SQLite; a PostgreSQL crash or cancel during a copy can leave a data
  directory with no database, which `make up` and `reset --status` report.
- PostgreSQL's read-only `demo` is a convenience for a samples server, not a security boundary.
