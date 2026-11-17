"""The verification adapter for MySQL: every stage's questions, answered with information_schema
and the canonical digest in SQL (megasamples/canon.py)."""
import copy
from datetime import datetime, timezone

from megasamples import canon
from megasamples.engines.mysql import server as db


def group_concat_calls(text):
    """The argument text of every GROUP_CONCAT( ... ) call, found by walking to the matching
    parenthesis, so nesting depth and quoted strings do not matter."""
    out, low, i = [], text.lower(), 0
    while True:
        i = low.find("group_concat(", i)
        if i < 0:
            return out
        depth, j, quote = 0, i + len("group_concat"), None
        start = j + 1
        while j < len(text):
            ch = text[j]
            if quote:
                if ch == quote:
                    quote = None
            elif ch in ("'", '"', "`"):
                quote = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(text[start:j])
        i = j


def has_unordered_group_concat(definition):
    """True when a GROUP_CONCAT in the definition has no ORDER BY of its own: its result then depends
    on the order the engine reads rows in, which MySQL leaves unspecified."""
    return any("order by" not in args.lower() for args in group_concat_calls(definition))


def computed_columns(definition, columns):
    """For each output column of a view, what it is: None for anything computed, or the
    (table, column) it reads unchanged. Parsed with sqlglot; a definition it cannot parse (or a
    UNION) counts every column as computed, the conservative answer."""
    import sqlglot
    from sqlglot import exp
    from megasamples.port import sqltranslate
    try:
        text, _ = sqltranslate._json_table(definition, "postgres")
        tree = sqlglot.parse_one(text, read="mysql")
    except Exception:  # noqa: BLE001 - conservative on anything sqlglot rejects
        return {c: None for c in columns}
    if not isinstance(tree, exp.Select) or len(tree.expressions) != len(columns):
        return {c: None for c in columns}
    aliases = {}
    for t in tree.find_all(exp.Table):
        aliases[(t.alias or t.name).lower()] = t.name.lower()
    out = {}
    for name, e in zip(columns, tree.expressions):
        inner = e.this if isinstance(e, exp.Alias) else e
        while isinstance(inner, exp.Paren):
            inner = inner.this
        if isinstance(inner, exp.Column):
            table = aliases.get(inner.table.lower(), inner.table.lower()) if inner.table else None
            out[name] = (table, inner.name)
        else:
            out[name] = None
    return out


class MySQLAdapter:
    name = "mysql"
    exact_decimals = True

    def with_clock(self, value):
        """A verification-only adapter for view baselines made at a recorded UTC second.

        Each fingerprint uses a fresh client, so SET timestamp must share that query's session.
        The ordinary adapter and server-wide clock are never changed.
        """
        if not isinstance(value, str):
            raise ValueError("MySQL view clock must be an explicit UTC timestamp")
        try:
            instant = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("invalid MySQL view clock") from exc
        if instant.tzinfo is None or instant.utcoffset() != timezone.utc.utcoffset(instant) or instant.microsecond:
            raise ValueError("MySQL view clock must specify a whole UTC second")
        epoch = int(instant.timestamp())
        if not 1 <= epoch <= 2147483647:
            raise ValueError("MySQL view clock is outside the server timestamp range")
        frozen = copy.copy(self)
        frozen._clock_epoch = epoch
        return frozen

    def supports(self, stage):
        return True

    def tables(self, schema):
        return [r[0] for r in db.rows(
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema='{schema}' AND table_type='BASE TABLE' ORDER BY table_name")]

    def columns(self, schema, table):
        return [(r[0], r[1]) for r in db.rows(
            "SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_schema='{schema}' AND table_name='{table}' ORDER BY ordinal_position")]

    def count(self, schema, table):
        return int(db.rows(f"SELECT COUNT(*) FROM `{schema}`.`{table}`")[0][0])

    def fingerprint(self, schema, table, cols):
        sql = canon.fingerprint_sql(schema, table, cols)
        if getattr(self, "_clock_epoch", None) is not None:
            sql = f"SET timestamp={self._clock_epoch}; SET time_zone='+00:00'; " + sql
        row = db.rows(sql)[0]
        return int(row[0]), int(row[1]), int(row[2])

    def foreign_keys(self, schema):
        # kcu.referenced_table_schema, not the constraint's own schema: Oracle OE's orders and
        # customers reference oracle_hr, and joining against the wrong database finds no table
        return db.rows(
            "SELECT rc.constraint_name, rc.table_name, kcu.column_name, "
            "kcu.referenced_table_schema, rc.referenced_table_name, "
            "kcu.referenced_column_name FROM information_schema.referential_constraints rc "
            "JOIN information_schema.key_column_usage kcu ON kcu.constraint_name=rc.constraint_name "
            "AND kcu.constraint_schema=rc.constraint_schema "
            f"WHERE rc.constraint_schema='{schema}' ORDER BY 1,3")

    def orphans(self, schema, table, col, rschema, rtable, rcol):
        return int(db.rows(
            f"SELECT COUNT(*) FROM `{schema}`.`{table}` c LEFT JOIN `{rschema}`.`{rtable}` p "
            f"ON c.`{col}` = p.`{rcol}` WHERE c.`{col}` IS NOT NULL AND p.`{rcol}` IS NULL")[0][0])

    def indexes(self, schema):
        out = {}
        for table, index, nonuniq, itype, cols in db.rows(
                "SELECT table_name, index_name, MAX(non_unique), MAX(index_type), "
                "GROUP_CONCAT(column_name ORDER BY seq_in_index) "
                f"FROM information_schema.statistics WHERE table_schema='{schema}' "
                "GROUP BY table_name, index_name ORDER BY table_name, index_name"):
            out.setdefault(table, {})[index] = {
                "unique": nonuniq == "0", "type": itype, "columns": cols.split(",")}
        return out

    def carries_index(self, spec):
        return True

    def views(self, schema):
        return [r[0] for r in db.rows(
            f"SELECT table_name FROM information_schema.views WHERE table_schema='{schema}' ORDER BY table_name")]

    def view_columns(self, schema, view):
        return self.columns(schema, view)

    def views_not_ported(self, schema):
        return set()

    def view_has_unordered_aggregate(self, schema, view):
        create = db.rows_escaped(f"SHOW CREATE VIEW `{schema}`.`{view}`")[0][1]
        return has_unordered_group_concat(create)

    def view_inexact_columns(self, schema, view, _seen=None):
        """The decimal columns the view computes, and those it reads unchanged from another view
        that computes them (see computed_columns): what floating-point arithmetic cannot reproduce."""
        from megasamples.port.model import view_body
        seen = _seen if _seen is not None else set()
        if view in seen:
            return []
        seen.add(view)
        views = set(self.views(schema))
        create = db.rows_escaped(f"SHOW CREATE VIEW `{schema}`.`{view}`")[0][1]
        cols = self.columns(schema, view)
        origin = computed_columns(view_body(create), [c for c, _ in cols])
        out = []
        for c, t in cols:
            if t.lower() != "decimal":
                continue
            src = origin[c]
            if src is None:
                out.append(c)
            elif src[0] in views and src[1] in self.view_inexact_columns(schema, src[0], seen):
                out.append(c)
        return out

    # --- routines and triggers ------------------------------------------------------------------
    def routines(self, schema):
        """{name: (kind, [(mode, name, type)])}"""
        out = {}
        for name, kind in db.rows(
                "SELECT routine_name, routine_type FROM information_schema.routines "
                f"WHERE routine_schema='{schema}' ORDER BY routine_name"):
            params = [(r[0], r[1], r[2]) for r in db.rows(
                "SELECT parameter_mode, parameter_name, dtd_identifier FROM information_schema.parameters "
                f"WHERE specific_schema='{schema}' AND specific_name='{name}' AND ordinal_position > 0 "
                "ORDER BY ordinal_position")]
            out[name] = (kind, params)
        return out

    def routines_not_ported(self, schema):
        return set()

    def triggers_not_ported(self, schema):
        return set()

    def call_routine(self, schema, case):
        """The lines a call prints: a function's value; a procedure's result set, then its OUT
        parameters as one row; then the probe query's rows. All inside a rolled-back transaction."""
        from megasamples import probe
        kind, params = self.routines(schema)[case["routine"]]
        args = [str(a) for a in case.get("args", [])]
        if kind == "FUNCTION":
            statements = [f"SELECT `{case['routine']}`({', '.join(args)})"]
        else:
            outs = [f"@out{i}" for i, p in enumerate(params) if p[0] in ("OUT", "INOUT")]
            statements = [f"CALL `{case['routine']}`({', '.join(args + outs)})"]
            # probe_only: the OUT values are not compared (an auto-increment id, for one, is not
            # the same from one run to the next); the probe query is what the call is judged by
            if outs and not case.get("probe_only"):
                statements.append(f"SELECT {', '.join(outs)}")
        if case.get("probe"):
            statements.append(case["probe"])
        return self._script(schema, statements, case.get("error", False))

    def run_scenario(self, schema, case):
        return self._script(schema, list(case["statements"]) + [case["probe"]], case.get("error", False))

    def _script(self, schema, statements, expect_error):
        from megasamples import probe
        script = "START TRANSACTION;\n" + ";\n".join(statements) + ";\nROLLBACK;\n"
        try:
            out = db.sql(script, database=schema)
        except RuntimeError as exc:
            if expect_error:
                return ["ERROR"]
            raise RuntimeError(f"{exc}") from None
        if expect_error:
            raise RuntimeError(f"the call was expected to fail on MySQL and did not:\n{script}")
        return probe.lines(out)

    def explain_json(self, schema, query):
        return db.sql(f"EXPLAIN FORMAT=JSON {query}", database=schema)

    def query_text(self, schema, query):
        return db.sql(query, database=schema).strip()
