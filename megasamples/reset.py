#!/usr/bin/env python3
"""Put the running stack's databases back as the images ship them: everything, or chosen engine/dataset pairs.

  python3 -m megasamples reset all                                    # every engine the stack runs
  python3 -m megasamples reset postgres                               # one engine, every database it has
  python3 -m megasamples reset postgres:northwind mysql:sakila        # single databases
  python3 -m megasamples reset --engines postgres --datasets quick    # configure's flags and selectors

`make up` starts what megasamples.yaml names, as its images hold it; `reset` returns what it is told to
that state, discarding the changes made since. The choice reads like `configure`'s -- engines and datasets, by name or selector
(core | quick | all | a tier | a list) -- so whatever a configuration installs, a reset can restore.
Nothing is reset without naming it: `all`, an engine, a pair, or the flags.

* A whole engine is recreated with a fresh copy of its data directory from the image, the same
  `up --force-recreate --renew-anon-volumes` that `make up` uses for a rebuilt image; the data volume it
  replaced is then removed by name (never a prune). It takes seconds and discards everything: rows,
  tables, databases, accounts, roles and privileges.
* Single datasets are restored without touching the rest. PostgreSQL and MySQL start a transient
  container of the same image (labelled like the image tests, so `make clean` removes one left
  behind), dump each database from it and replace the running server's copy; each restored table's
  row count is then checked against that pristine copy. SQLite copies the image's file over the one the
  consoles read and checks the two are byte for byte the same. A dataset that shares its database with
  another (`append: true`) resets that whole database. PostgreSQL disconnects the clients of a database
  it restores; MySQL waits for their open transactions.
  What lives outside the database stays as it is: accounts and roles (server-wide on both), and on
  MySQL the privileges, which it keeps in its account tables. Reset the engine whole for those.
"""
import argparse, json, os, re, subprocess, sys, time

from megasamples import compose, config as stack, datasets as inventory, engines as engine_registry
from megasamples.engines import unique_databases
from megasamples.paths import COMPOSE, ROOT

TRANSIENT = ["--label", "megasamples.transient=true", "--label", "megasamples.role=reset"]
READY_SECONDS = 120


def sh(*args, input=None):
    return subprocess.run(list(args), capture_output=True, text=True, input=input)


# --- what to reset ---------------------------------------------------------------------------------
def plan(cfg, targets, engines=None, datasets=None):
    """{engine: None (the whole engine) | [databases]} from the arguments, or SystemExit naming the problem.

    `targets` are `all`, engine names and `engine:dataset` pairs; `engines` and `datasets` are configure's
    comma-separated flags (`datasets` a selector or names, applied to every engine named)."""
    running = list(cfg.engines)
    chosen = {}

    def whole(engine):
        chosen[engine] = None

    def some(engine, names):
        if chosen.get(engine, []) is None:
            return                                   # already reset whole
        configured = cfg.datasets(engine)
        for name in names:
            if name not in configured:
                sys.exit(f"{engine} does not ship `{name}` (megasamples.yaml gives it: {', '.join(configured) or 'nothing'})")
        databases = chosen.setdefault(engine, [])
        for database in unique_databases(names):
            if database not in databases:
                databases.append(database)

    def select(spec):
        try:
            return inventory.select(spec.split(","))
        except KeyError as unknown:
            sys.exit(unknown.args[0])

    def known(engine):
        if engine not in running:
            sys.exit(f"`{engine}` is not in the stack (megasamples.yaml runs: {', '.join(running)})")
        return engine

    for target in targets:
        if target == "all":
            for engine in running:
                whole(engine)
        elif ":" in target:
            engine, _, dataset = target.partition(":")
            some(known(engine), select(dataset))
        else:
            whole(known(target))
    if engines or datasets:
        names = [known(e) for e in (engines.split(",") if engines else running)]
        for engine in names:
            if datasets:
                some(engine, select(datasets))
            else:
                whole(engine)
    if not chosen:
        sys.exit("name what to reset: `all`, an engine, engine:dataset pairs, or --engines/--datasets (see --help)")
    return chosen


# --- whole engines ---------------------------------------------------------------------------------
def data_volumes(container):
    """The anonymous volumes a container's data lives in (the images declare one for their data directory). An
    anonymous volume is named by a 64-digit hex id; a named one (the SQLite files the consoles share) is never
    one of them."""
    mounts = sh("docker", "inspect", "-f", "{{json .Mounts}}", container)
    if mounts.returncode != 0:
        return []
    return [m["Name"] for m in json.loads(mounts.stdout or "[]")
            if m.get("Type") == "volume" and re.fullmatch(r"[0-9a-f]{64}", m.get("Name") or "")]


def reset_engines(names):
    services = [engine_registry.get(n) for n in names]
    replaced = {e.container: data_volumes(e.container) for e in services}
    print(f"  . recreating {', '.join(names)} from the image (fresh data directory)")
    if subprocess.run(["docker", "compose", "-f", COMPOSE, "up", "-d", "--force-recreate", "--renew-anon-volumes",
                       "--no-deps", "--wait", *names], cwd=ROOT).returncode != 0:
        return 1
    for container, volumes in replaced.items():
        for volume in volumes:
            if volume in data_volumes(container):
                continue
            removed = sh("docker", "volume", "rm", volume)
            print(f"  . removed the replaced data volume {volume[:12]}" if removed.returncode == 0
                  else f"  ! could not remove the replaced data volume {volume}: {removed.stderr.strip()[:200]}")
    return 0


# --- single databases ------------------------------------------------------------------------------
class Pristine:
    """A transient container of an engine's image: its data directory exactly as shipped."""

    def __init__(self, engine, ready, env=()):
        self.name = f"megasamples-reset-{engine.name}"
        self.engine = engine
        self.ready = ready
        self.env = list(env)

    def __enter__(self):
        sh("docker", "rm", "-f", self.name)
        run = sh("docker", "run", "-d", "--name", self.name, *TRANSIENT, "--memory", "2g", *self.env, self.engine.image)
        if run.returncode != 0:
            sys.exit(f"could not start a pristine {self.engine.image}: {run.stderr.strip()[:300]}")
        started = time.time()
        while time.time() - started < READY_SECONDS:
            if self.ready(self.name):
                return self
            time.sleep(0.5)
        sh("docker", "rm", "-f", self.name)
        sys.exit(f"the pristine {self.engine.image} did not answer within {READY_SECONDS}s")

    def __exit__(self, *_):
        sh("docker", "rm", "-f", self.name)


def pipe(source, target):
    """source | target, both argument lists; the first failure's message, or None."""
    producer = subprocess.Popen(source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    consumer = subprocess.run(target, stdin=producer.stdout, capture_output=True)
    producer.stdout.close()
    produced = producer.wait()
    if produced != 0:
        return producer.stderr.read().decode(errors="replace").strip()[:300]
    if consumer.returncode != 0:
        return consumer.stderr.decode(errors="replace").strip()[:300]
    return None


def pg(container, sql, database="postgres"):
    # The official image trusts its own loopback: the superuser runs maintenance without its password.
    return sh("docker", "exec", container, "psql", "-h", "127.0.0.1", "-U", "postgres", "-d", database,
              "-v", "ON_ERROR_STOP=1", "-tAc", sql)


def pg_counts(container, database):
    tables = pg(container, "SELECT format('%I.%I', schemaname, tablename) FROM pg_tables "
                           "WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1", database)
    out = {}
    for table in tables.stdout.split():
        out[table] = pg(container, f"SELECT count(*) FROM {table}", database).stdout.strip()
    return out


def reset_postgres(engine, databases):
    with Pristine(engine, lambda c: pg(c, "SELECT 1").returncode == 0) as pristine:
        for database in databases:
            print(f"  . postgres:{database}: restoring from the image")
            dropped = pg(engine.container, f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
            if dropped.returncode != 0:
                sys.exit(f"postgres:{database}: {dropped.stderr.strip()[:300]}")
            # --create carries the database's own settings and the grants on it.
            failed = pipe(["docker", "exec", pristine.name, "pg_dump", "-h", "127.0.0.1", "-U", "postgres", "-Fc", "--create", database],
                          ["docker", "exec", "-i", engine.container, "pg_restore", "-h", "127.0.0.1", "-U", "postgres",
                           "-d", "postgres", "--create", "--exit-on-error"])
            if failed:
                sys.exit(f"postgres:{database}: {failed}")
            expected, restored = pg_counts(pristine.name, database), pg_counts(engine.container, database)
            if expected != restored or not expected:
                sys.exit(f"postgres:{database}: the restored tables differ from the image's: {sorted(set(expected.items()) ^ set(restored.items()))[:5]}")
            print(f"      {len(restored)} tables, row counts as shipped")
    return 0


def my(container, sql, database=None):
    return sh("docker", "exec", container, "mysql", "-uroot", "-proot", "-N", "--batch",
              *([database] if database else []), "-e", sql)


def my_counts(container, database):
    tables = my(container, "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() "
                           "AND table_type = 'BASE TABLE' ORDER BY 1", database)
    return {t: my(container, f"SELECT COUNT(*) FROM `{t}`", database).stdout.strip() for t in tables.stdout.split()}


def reset_mysql(engine, databases):
    with Pristine(engine, lambda c: my(c, "SELECT 1").returncode == 0, ["-e", "MYSQL_ROOT_PASSWORD=root"]) as pristine:
        for database in databases:
            print(f"  . mysql:{database}: restoring from the image")
            failed = pipe(["docker", "exec", pristine.name, "mysqldump", "-uroot", "-proot", "--databases", database,
                           "--add-drop-database", "--routines", "--triggers", "--events", "--single-transaction", "--set-gtid-purged=OFF"],
                          ["docker", "exec", "-i", engine.container, "mysql", "-uroot", "-proot"])
            if failed:
                sys.exit(f"mysql:{database}: {failed}")
            expected, restored = my_counts(pristine.name, database), my_counts(engine.container, database)
            if expected != restored or not expected:
                sys.exit(f"mysql:{database}: the restored tables differ from the image's: {sorted(set(expected.items()) ^ set(restored.items()))[:5]}")
            print(f"      {len(restored)} tables, row counts as shipped")
    return 0


def reset_sqlite(engine, databases):
    # The container holds the image's files under /data and copies them into the shared volume at start.
    for database in databases:
        print(f"  . sqlite:{database}: copying the image's file")
        copied = sh("docker", "exec", engine.container, "sh", "-c",
                    f'cp -f /data/{database}.sqlite /shared/.{database}.sqlite.part && mv -f /shared/.{database}.sqlite.part /shared/{database}.sqlite')
        if copied.returncode != 0:
            sys.exit(f"sqlite:{database}: {copied.stderr.strip()[:300]}")
        sums = sh("docker", "exec", engine.container, "sha256sum", f"/data/{database}.sqlite", f"/shared/{database}.sqlite").stdout.split()
        if len(sums) != 4 or sums[0] != sums[2]:
            sys.exit(f"sqlite:{database}: the copy differs from the image's file")
        print("      the file is the image's, byte for byte")
    return 0


RESET_DATABASES = {"postgres": reset_postgres, "mysql": reset_mysql, "sqlite": reset_sqlite}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="\n".join(__doc__.strip().splitlines()[1:6]))
    ap.add_argument("targets", nargs="*", help="all | an engine | engine:dataset (dataset: a name or a selector)")
    ap.add_argument("--engines", help="comma-separated, as configure takes them (default with --datasets: every engine)")
    ap.add_argument("--datasets", help="selector or comma-separated names, applied to every engine named")
    a = ap.parse_args(argv)
    cfg = stack.load()
    chosen = plan(cfg, a.targets, a.engines, a.datasets)
    if not os.path.exists(COMPOSE):
        compose.main([])
    whole = [e for e, databases in chosen.items() if databases is None]
    if whole and reset_engines(whole):
        return 1
    for engine, databases in chosen.items():
        if databases:
            RESET_DATABASES[engine](engine_registry.get(engine), databases)
    print("  . reset: " + ", ".join(f"{e} (whole)" if d is None else f"{e}: {', '.join(d)}" for e, d in chosen.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
