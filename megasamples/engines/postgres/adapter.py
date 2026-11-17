"""The verification adapter for PostgreSQL.

Counts, foreign keys and indexes are read from the ported database itself; the canonical digest is
computed in Python from a `COPY ... TO STDOUT` of each table rendered column by column in the
canonical text form (megasamples/canon.py), because PostgreSQL text cannot hold the U+0000 NULL
sentinel the SQL form uses. The MySQL types every column had come from the port's model.json, so the
same digest rules apply to the same columns.
"""
import json, os

from megasamples import canon
from megasamples.engines.postgres import server as pg
from megasamples.paths import engine_build_dir
from megasamples.port import typemap
from megasamples.port.ddl import physical_index_name

PG_UNESCAPE = {b"\\": b"\\", b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f", b"v": b"\v"}


def canonical_expr(name, mysql_type, precision=None, scale=None):
    q = '"' + name + '"'
    t = mysql_type.lower()
    if t == "decimal" and precision is not None and scale is not None:
        # a view's computed decimal (an AVG, a SUM) carries MySQL's precision and scale; PostgreSQL's
        # numeric is unbounded, so it is rendered at the same scale
        return f"CAST({q} AS numeric({precision},{scale}))::text"
    if t in ("datetime", "timestamp"):
        return f"to_char({q}, 'YYYY-MM-DD HH24:MI:SS.US')"
    if t == "time":
        return f"to_char({q}::interval, 'HH24:MI:SS.US')"
    if t in typemap.BLOB_KINDS or t in typemap.GEOMETRY_KINDS or t == "bit":
        return f"encode({q}, 'hex')"
    if t == "char":
        return f"rtrim({q})"
    return f"{q}::text"


def unescape_field(field):
    if field == b"\\N":
        return None
    if b"\\" not in field:
        return field.decode("utf-8")
    out, i, n = bytearray(), 0, len(field)
    while i < n:
        c = field[i:i + 1]
        if c == b"\\" and i + 1 < n:
            out += PG_UNESCAPE.get(field[i + 1:i + 2], field[i + 1:i + 2])
            i += 2
        else:
            out += c
            i += 1
    return out.decode("utf-8")


class PostgresAdapter:
    name = "postgres"
    exact_decimals = True

    def __init__(self, dataset):
        from megasamples import datasets as inventory
        path = os.path.join(engine_build_dir("postgres"), inventory.load(dataset)["database"], "model.json")
        if not os.path.exists(path):
            raise SystemExit(f"{dataset}: no PostgreSQL port under build/postgres/; run: megasamples pg-port {dataset}")
        with open(path, encoding="utf-8") as fh:
            self.model = json.load(fh)
        self.types = {t["name"]: {c["name"]: c["data_type"] for c in t["columns"]} for t in self.model["tables"]}
        self.view_types = {v["name"]: [(c[0], c[1], c[2], c[3]) for c in v["columns"]] for v in self.model.get("views", [])}
        self.ported_views = set(self.model.get("ported_views", []))
        self.logical = {physical_index_name(t["name"], i["name"]): i["name"]
                        for t in self.model["tables"] for i in t["indexes"] if not i["primary"]}

        self.ported_routines = set(self.model.get("ported_routines", []))
        self.table_functions = set(self.model.get("result_sets", {}))
        self.ported_triggers = set(self.model.get("ported_triggers", []))
        self.names = None

    def supports(self, stage):
        return stage in ("counts", "digests", "fks", "indexes", "views", "routines", "triggers")

    # --- routines and triggers ------------------------------------------------------------------
    def routines_not_ported(self, schema):
        return {r["name"] for r in self.model.get("routines", [])} - self.ported_routines

    def triggers_not_ported(self, schema):
        return {t["name"] for t in self.model.get("triggers", [])} - self.ported_triggers

    def translate(self, sql):
        from megasamples.port import sqltranslate
        if self.names is None:
            self.names = sqltranslate.names_of(self.model)
        return sqltranslate.translate(sql, "postgres", self.model["name"], names=self.names,
                                      extra=[r["name"] for r in self.model.get("routines", [])])

    def call_routine(self, schema, case):
        """The same lines MySQL prints for the call (mysql/adapter.py): every argument is cast to
        the parameter's type, since PostgreSQL resolves a function by its argument types."""
        from megasamples.port import routines as routine_port
        r = next(r for r in self.model["routines"] if r["name"] == case["routine"])
        name = case["routine"]
        args = [str(a) for a in case.get("args", [])]
        ins = [p for p in r["params"] if p[0] == "IN"]
        outs = [p for p in r["params"] if p[0] in ("OUT", "INOUT")]
        cast = [f"CAST({a} AS {routine_port.pg_type(p[2])})" for a, p in zip(args, ins if r["kind"] != "FUNCTION" else r["params"])]
        if r["kind"] == "FUNCTION":
            statements = [f'SELECT "{name}"({", ".join(cast)})']
        elif name in self.table_functions:
            call = f'"{name}"({", ".join(cast)})'
            statements = [f"SELECT * FROM {call}"]
            if outs:
                # the OUT parameters a table function cannot carry (ports/notes.yaml): in this corpus
                # each one is the count of the rows returned, which is what stands in for it here;
                # a procedure whose OUT is something else would fail this comparison, by design
                statements.append("SELECT " + ", ".join(f"(SELECT count(*) FROM {call})" for _ in outs))
        elif outs and case.get("probe_only"):
            # the OUT values are not compared: a DO block receives them and prints nothing
            declare = " ".join(f"o{i} {routine_port.pg_type(p[2])};" for i, p in enumerate(outs))
            statements = [f'DO $$ DECLARE {declare} BEGIN CALL "{name}"({", ".join(cast + [f"o{i}" for i in range(len(outs))])}); END $$']
        else:
            statements = [f'CALL "{name}"({", ".join(cast + ["NULL"] * len(outs))})']
        if case.get("probe"):
            statements.append(self.translate(case["probe"]))
        return self._script(schema, statements, case.get("error", False))

    def run_scenario(self, schema, case):
        statements = [self.translate(s) for s in case["statements"]] + [self.translate(case["probe"])]
        return self._script(schema, statements, case.get("error", False))

    def _script(self, schema, statements, expect_error):
        from megasamples import probe
        script = "BEGIN;\n" + ";\n".join(statements) + ";\nROLLBACK;\n"
        try:
            out = pg.psql_script(script, schema, null="NULL")
        except RuntimeError as exc:
            if expect_error:
                return ["ERROR"]
            raise
        if expect_error:
            raise RuntimeError(f"the call was expected to fail on PostgreSQL and did not:\n{script}")
        return probe.lines(out)

    def tables(self, schema):
        return [r[0] for r in pg.rows(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' "
            "AND table_type='BASE TABLE' ORDER BY table_name", schema)]

    def columns(self, schema, table):
        types = self.types.get(table, {})
        return [(c["name"], types[c["name"]]) for t in self.model["tables"] if t["name"] == table for c in t["columns"]]

    def count(self, schema, table):
        return int(pg.rows(f'SELECT count(*) FROM "{table}"', schema)[0][0])

    def views(self, schema):
        return sorted(self.ported_views)

    def view_columns(self, schema, view):
        return [(c[0], c[1]) for c in self.view_types.get(view, [])]

    def view_has_unordered_aggregate(self, schema, view):
        from megasamples.engines.mysql.adapter import has_unordered_group_concat
        v = next((v for v in self.model.get("views", []) if v["name"] == view), None)
        return bool(v) and has_unordered_group_concat(v["definition"])

    def views_not_ported(self, schema):
        return {v["name"] for v in self.model.get("views", [])} - self.ported_views

    def fingerprint(self, schema, table, cols):
        kept = [(c, t) for c, t in cols if t.lower() not in canon.EXCLUDED]
        scales = {c[0]: (c[2], c[3]) for c in self.view_types.get(table, [])}
        exprs = ", ".join(canonical_expr(c, t, *scales.get(c, (None, None))) for c, t in kept) or "1"
        data = pg.copy_out(f'SELECT {exprs} FROM "{table}"', schema)
        digests = []
        for line in data.split(b"\n"):
            if not line:
                continue
            values = [unescape_field(f) for f in line.split(b"\t")] if kept else []
            digests.append(canon.row_digest(values))
        f = canon.fold(digests)
        return f["n"], f["x"], f["s"]

    def foreign_keys(self, schema):
        return [(r[0], r[1], r[2], schema, r[3], r[4]) for r in pg.rows(
            "SELECT con.conname, rel.relname, att.attname, frel.relname, fatt.attname "
            "FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid "
            "JOIN pg_class frel ON frel.oid = con.confrelid "
            "JOIN LATERAL unnest(con.conkey, con.confkey) AS k(a, f) ON true "
            "JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k.a "
            "JOIN pg_attribute fatt ON fatt.attrelid = con.confrelid AND fatt.attnum = k.f "
            "WHERE con.contype = 'f' AND rel.relnamespace = 'public'::regnamespace ORDER BY 1, 3", schema)]

    def orphans(self, schema, table, col, rschema, rtable, rcol):
        return int(pg.rows(
            f'SELECT count(*) FROM "{table}" c LEFT JOIN "{rtable}" p ON c."{col}" = p."{rcol}" '
            f'WHERE c."{col}" IS NOT NULL AND p."{rcol}" IS NULL', schema)[0][0])

    def indexes(self, schema):
        """Indexes by MySQL's names: the `<table>_` prefix stripped, the primary key as PRIMARY."""
        out = {}
        for table, index, unique, primary, cols in pg.rows(
                "SELECT t.relname, i.relname, ix.indisunique, ix.indisprimary, "
                "string_agg(a.attname, ',' ORDER BY k.ord) "
                "FROM pg_index ix JOIN pg_class t ON t.oid = ix.indrelid JOIN pg_class i ON i.oid = ix.indexrelid "
                "JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord) ON true "
                "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum "
                "WHERE t.relnamespace = 'public'::regnamespace AND t.relkind = 'r' "
                "GROUP BY t.relname, i.relname, ix.indisunique, ix.indisprimary ORDER BY 1, 2", schema):
            name = "PRIMARY" if primary == "t" else self.logical.get(index, index)
            out.setdefault(table, {})[name] = {"unique": unique == "t", "type": "BTREE", "columns": cols.split(",")}
        # a FULLTEXT index became a GIN index over to_tsvector('simple', coalesce("a", '') || ...):
        # an expression index, which the query above cannot name column by column
        for table, index, definition in pg.rows(
                "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' "
                "AND indexdef LIKE '%USING gin (to_tsvector(%' ORDER BY 1, 2", schema):
            import re
            cols = re.findall(r'COALESCE\(\(?"?([^",)]+)"?\)?::text, \'\'::text\)', definition) or re.findall(r'COALESCE\("?(\w+)"?', definition)
            out.setdefault(table, {})[self.logical.get(index, index)] = {"unique": False, "type": "FULLTEXT", "columns": cols}
        return out

    def carries_index(self, spec):
        return spec.get("type") in ("BTREE", "FULLTEXT")

    def indexes_not_ported(self, schema):
        return self.model.get("indexes_not_ported", {})

    def explain_json(self, schema, query):
        raise NotImplementedError

    def query_text(self, schema, query):
        raise NotImplementedError
