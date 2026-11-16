#!/usr/bin/env python3
"""Restore datasets into the MySQL build server from their dumps, without converting or reloading.

  python3 -m megasamples restore [dataset ...]        default: every dataset that has a dump

A dump under build/mysql/dumps/<dataset>/ is the verified corpus as MySQL Shell wrote it; loading it
back with `util.loadDump` takes seconds to minutes where the conversion took hours. This is how a
build server is repopulated after `make image` removed it -- to port datasets to another engine, or
to work on one dataset without rebuilding the rest. Each database is dropped and recreated;
prerequisites (a cross-database foreign key's target) are restored first.
"""
import argparse, os, sys, time

from megasamples import datasets as inventory
from megasamples.engines.mysql import server as db
from megasamples.paths import engine_build_dir, rel
from megasamples import container_engine

DUMPS = os.path.join(engine_build_dir("mysql"), "dumps")


def restorable():
    """The datasets whose database has a complete dump (an `append: true` dataset rides on its base's)."""
    return [d for d in inventory.names() if not inventory.load(d).get("append")
            and os.path.exists(os.path.join(DUMPS, inventory.load(d)["database"], "@.done.json"))]


def restore(dataset, threads=4):
    cfg = inventory.load(dataset)
    schema = cfg["database"]
    src = os.path.join(DUMPS, schema)
    if not os.path.exists(os.path.join(src, "@.done.json")):
        sys.exit(f"{dataset}: no complete dump under {rel(src)}")
    started = time.time()
    # a foreign key from another database blocks DROP DATABASE; drop those keys first (load.py does
    # the same) and say which datasets need restoring again afterwards
    inbound = db.rows(
        "SELECT DISTINCT rc.constraint_schema, rc.table_name, rc.constraint_name "
        "FROM information_schema.referential_constraints rc "
        "JOIN information_schema.key_column_usage kcu USING (constraint_schema, constraint_name) "
        f"WHERE kcu.referenced_table_schema = '{schema}' AND rc.constraint_schema <> '{schema}'")
    for other, table, constraint in inbound:
        db.sql(f"ALTER TABLE `{other}`.`{table}` DROP FOREIGN KEY `{constraint}`")
    if inbound:
        print(f"  ! dropped {len(inbound)} foreign key(s) into {schema} from "
              f"{', '.join(sorted({r[0] for r in inbound}))}; restore those datasets again")
    db.sql(f"DROP DATABASE IF EXISTS `{schema}`")
    script = (f"util.load_dump('/build/mysql/dumps/{schema}', {{'deferTableIndexes': 'all', "
              f"'threads': {threads}, 'showProgress': False, 'resetProgress': True, 'skipBinlog': True}})")
    out = db.run(["docker", "exec", "-u", container_engine.host_user(), "-e", "HOME=/build", db.NAME,
                  "mysqlsh", "--no-defaults", f"root:{db.PW}@127.0.0.1:3306", "--py", "-e", script])
    if out.returncode != 0:
        sys.exit(f"restore of {dataset} failed:\n{out.stdout}\n{out.stderr}")
    tables = db.rows("SELECT COUNT(*) FROM information_schema.tables "
                     f"WHERE table_schema='{schema}' AND table_type='BASE TABLE'")[0][0]
    print(f"  . {dataset}: restored {tables} tables in {time.time() - started:.1f}s")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("datasets", nargs="*")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args(argv)
    names = inventory.build_order(a.datasets or restorable())
    if not names:
        print(f"nothing to restore: no dumps under {rel(DUMPS)}")
        return 1
    db.start()
    print(f"restoring {len(names)} dataset(s) into {db.NAME} from {rel(DUMPS)}")
    for name in names:
        restore(name, a.threads)
    return 0


if __name__ == "__main__":
    sys.exit(main())
