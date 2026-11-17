#!/usr/bin/env python3
"""Port one dataset from the MySQL corpus to PostgreSQL: write its files, then load them.

  python3 -m megasamples pg-port <dataset> [--files-only]

Reads the model from the MySQL build server (information_schema) and the data from the MySQL Shell
dump under build/mysql/dumps/<database>/, and writes build/postgres/<database>/ (an `append: true`
dataset extends its base's database, and the port is always of the whole database):

    model.json         the engine-neutral model the DDL was generated from (the adapter reads it)
    schema.sql         CREATE TABLE with primary keys, defaults, generated columns, enum checks
    data/<table>.tsv   COPY text format, one file per table; data/tables.tsv lists them in load order
    indexes.sql        secondary indexes
    constraints.sql    foreign keys, checks, identity sequences advanced past the loaded keys
    routines.sql       the stored functions and procedures, in PL/pgSQL
    views.sql          the views, in the order their dependencies allow
    triggers.sql       the triggers, as PL/pgSQL trigger functions
    dropped.txt        what PostgreSQL does not carry, one line each, with the reason
    complete           written last; the image builder takes only directories that have it

then loads them into the PostgreSQL build server: CREATE DATABASE, schema, \\copy per table,
indexes, constraints, ANALYZE. The image builder replays the same files (engines/postgres/Dockerfile).
Geometry columns are stored as WKB: the dump carries MySQL's internal form, a 4-byte SRID before
the WKB, and those four bytes are dropped so the stored value is what ST_AsBinary returns.
"""
import argparse, dataclasses, json, os, shutil, sys, time

from megasamples import datasets as inventory
from megasamples.engines.postgres import server as pg
from megasamples.engines.mysql import dump as dumper, server as mysql
from megasamples.paths import engine_build_dir, rel
from megasamples.port import ddl, model, record, tsv, typemap, views as view_port


def out_dir(dataset):
    # keyed by database: an `append: true` dataset extends its base's database, and the port is of
    # the whole database whichever dataset asked for it
    return os.path.join(engine_build_dir("postgres"), inventory.load(dataset)["database"])


def dump_dir(dataset, database, tables):
    """The MySQL Shell dump of the database, taken now unless a complete one holding every table exists."""
    dumps = os.path.join(engine_build_dir("mysql"), "dumps", database)
    if not dumper.complete(database, tables):
        dumper.dump(dataset)
    return dumps


def setval_statements(database, dialect):
    """Advance every identity sequence past the largest key that was loaded."""
    out = []
    for t in database.tables:
        for c in t.columns:
            if c.auto_increment:
                out.append(f"SELECT setval(pg_get_serial_sequence('{dialect.quote(t.name)}', '{c.name}'), "
                           f"COALESCE(MAX({dialect.quote(c.name)}), 0) + 1, false) FROM {dialect.quote(t.name)};")
    return out


class ResultProbe:
    """Measures the result columns of a procedure that returns rows: the ported schema and the
    database's functions are created in a scratch database on the build server, and psql's \\gdesc
    describes the procedure's SELECT (with its variables as typed NULLs) without running it."""

    def __init__(self, schema, database):
        self.schema, self.database, self.name, self.functions_done = schema, database, f"_probe_{schema}", False

    def open(self):
        pg.start()
        pg.psql(f'DROP DATABASE IF EXISTS "{self.name}"')
        pg.psql(f'CREATE DATABASE "{self.name}" TEMPLATE template0 ENCODING \'UTF8\'')
        from megasamples.port import routines as routine_port
        rendered = ddl.render(self.database, "postgres", {}, probe=lambda tr: [])   # no result sets needed here
        pg.psql_script("\n".join(rendered["schema"]), self.name)
        # what a procedure's SELECT may use: the functions, then the views; one at a time, because a
        # failure here is reported by the port itself when it loads the same statement
        for st in [s for s in rendered["routines"] if s.startswith("CREATE FUNCTION")
                   and "RETURNS TABLE" not in s.split("\n", 1)[0]] + rendered["views"]:
            try:
                pg.psql_script(st, self.name)
            except RuntimeError:
                pass
        self.functions_done = True

    def probe(self, tr):
        if not self.functions_done:
            self.open()
        script = "BEGIN;\n" + "\n".join(tr.temp_tables) + "\n" + tr.probe_select() + " \\gdesc\nROLLBACK;\n"
        out = pg.psql_script(script, self.name)
        cols = [tuple(line.split("\t")) for line in out.splitlines() if line]
        if not cols:
            raise RuntimeError(f"{tr.r.name}: \\gdesc described no columns for its result set")
        return cols

    def close(self):
        if self.functions_done:
            pg.psql(f'DROP DATABASE IF EXISTS "{self.name}"')


def write_files(dataset):
    cfg = inventory.load(dataset)
    schema = cfg["database"]
    mysql.start()
    database = model.extract(schema)
    if not database.tables:
        sys.exit(f"{dataset}: `{schema}` has no tables in the MySQL build server; run: make {dataset}")
    dumps = dump_dir(dataset, schema, [t.name for t in database.tables])
    target = out_dir(dataset)
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(os.path.join(target, "data"))
    dialect = ddl.DIALECTS["postgres"]
    result_columns = {}
    prober = ResultProbe(schema, database)
    try:
        rendered = ddl.render(database, "postgres", result_columns, prober.probe,
                              index_omissions=cfg.get("postgres_fulltext_limits"))
    except ddl.UnportableColumn as exc:
        prober.close()
        sys.exit(f"{dataset}: {exc}")
    prober.close()
    rendered["result_columns"] = result_columns

    with open(os.path.join(target, "routines.sql"), "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(rendered["routines"]) + ("\n" if rendered["routines"] else ""))
    view_sql = rendered["views"]
    ported_views = [s.split('"')[1] for s in view_sql]
    with open(os.path.join(target, "views.sql"), "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(view_sql) + ("\n" if view_sql else ""))
    with open(os.path.join(target, "triggers.sql"), "w", encoding="utf-8") as fh:
        fh.write("\n\n".join(rendered["triggers"]) + ("\n" if rendered["triggers"] else ""))
    with open(os.path.join(target, "model.json"), "w", encoding="utf-8") as fh:
        doc = dataclasses.asdict(database)
        doc["ported_views"] = ported_views
        doc["ported_routines"] = [s.split('"')[1] for s in rendered["routines"]]
        doc["result_sets"] = {k: [list(c) for c in v] for k, v in result_columns.items()}
        doc["ported_triggers"] = [s.split('"')[1] for s in rendered["triggers"] if s.startswith("CREATE TRIGGER")]
        doc["indexes_not_ported"] = rendered["indexes_not_ported"]
        json.dump(doc, fh, indent=1)
    with open(os.path.join(target, "schema.sql"), "w", encoding="utf-8") as fh:
        fh.write("-- generated by megasamples pg-port from the MySQL corpus; do not edit\n\n")
        fh.write("\n\n".join(rendered["schema"]) + "\n")
    with open(os.path.join(target, "indexes.sql"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rendered["indexes"]) + "\n")
    with open(os.path.join(target, "constraints.sql"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rendered["constraints"] + setval_statements(database, dialect)) + "\n")
    with open(os.path.join(target, "dropped.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(rendered["dropped"]) + ("\n" if rendered["dropped"] else ""))
    record.write(dataset, "postgres", rendered)

    started = time.time()
    total = 0
    with open(os.path.join(target, "data", "tables.tsv"), "w", encoding="utf-8") as listing:
        for table in model.load_order(database):
            dump = tsv.TableDump(dumps, schema, table.name)
            # a stored generated column is not in the dump (it cannot be inserted); the engine
            # computes it from its own expression, and the digest check proves the values agree
            loaded = [c for c in table.columns if not c.generated]
            if dump.columns != [c.name for c in loaded]:
                sys.exit(f"{dataset}.{table.name}: dump column order {dump.columns} differs from the model's "
                         f"insertable columns {[c.name for c in loaded]}")
            geometry = {i for i, c in enumerate(loaded) if c.data_type in typemap.GEOMETRY_KINDS}
            n = tsv.write_postgres(dump, os.path.join(target, "data", f"{table.name}.tsv"), strip_srid=geometry)
            total += n
            cols = ",".join(dialect.quote(c.name) for c in loaded)
            listing.write(f"{table.name}\t{table.name}.tsv\t{cols}\n")
    with open(os.path.join(target, "complete"), "w", encoding="utf-8") as fh:
        fh.write(f"{dataset} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")   # written last: the image builder's gate
    print(f"  . {dataset}: {len(database.tables)} tables, {total:,} rows written to {rel(target)} "
          f"in {time.time() - started:.1f}s; {len(rendered['dropped'])} object(s) not ported (dropped.txt)")
    return database


def load(dataset):
    cfg = inventory.load(dataset)
    schema = cfg["database"]
    target = out_dir(dataset)
    inside = f"/build/postgres/{schema}"
    pg.start()
    started = time.time()
    pg.psql(f'DROP DATABASE IF EXISTS "{schema}"')
    pg.psql(f'CREATE DATABASE "{schema}" TEMPLATE template0 ENCODING \'UTF8\'')
    pg.psql_file(f"{inside}/schema.sql", schema)
    n_tables = 0
    with open(os.path.join(target, "data", "tables.tsv"), encoding="utf-8") as listing:
        for line in listing:
            table, file, cols = line.rstrip("\n").split("\t")
            pg.psql(f'\\copy "{table}" ({cols}) FROM \'{inside}/data/{file}\' WITH (FORMAT text)', schema)
            n_tables += 1
    pg.psql_file(f"{inside}/indexes.sql", schema)
    pg.psql_file(f"{inside}/constraints.sql", schema)
    pg.psql_file(f"{inside}/routines.sql", schema)
    pg.psql_file(f"{inside}/views.sql", schema)
    pg.psql_file(f"{inside}/triggers.sql", schema)
    pg.psql("ANALYZE", schema)
    size = pg.rows(f"SELECT pg_size_pretty(pg_database_size('{schema}'))")[0][0]
    print(f"  . {dataset} loaded into PostgreSQL in {time.time() - started:.1f}s: {n_tables} tables, {size}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("datasets", nargs="+")
    ap.add_argument("--files-only", action="store_true", help="write the port files without loading")
    a = ap.parse_args(argv)
    for d in a.datasets:
        write_files(d)
        if not a.files_only:
            load(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
