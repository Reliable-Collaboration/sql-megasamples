#!/usr/bin/env python3
"""WideWorldImporters -> MySQL: the shared half of the two converters.

Input is what `megasamples/sources/wwi_export.py` wrote: `meta.json` (the SQL Server catalogue), `baseline.json`
(row counts and three per-column aggregates) and one `.dat` per table. Nothing here talks to SQL
Server, so a build that starts from a published export never needs it.

Three things in this schema have no MySQL equivalent and are handled rather than ignored:

* **Temporal tables.** 18 tables are `SYSTEM_VERSIONED` with a `_Archive` history partner. MySQL has
  no system versioning, so both sides become ordinary tables and `ValidFrom`/`ValidTo` become plain
  `DATETIME(6)` columns. A `FOR SYSTEM_TIME` query becomes a `UNION ALL` over the pair by hand.
* **Sequences.** 26 sequence objects supply key defaults, one of them (`TransactionID`) shared by
  three tables. Each target column becomes `AUTO_INCREMENT` seeded past its maximum, which is the
  closest MySQL has; the guarantee that the three transaction tables never reuse a value between
  them does not survive, and `unported` says so.
* **Computed columns.** Eight, translated explicitly rather than by a general expression
  translator -- and two of them need `COALESCE` that the T-SQL does not, because SQL Server's
  `concat()` treats NULL as an empty string while MySQL's `CONCAT` returns NULL. That difference is
  invisible in the DDL and shows up only as a changed non-null count, which is one of the three
  numbers `verify_baseline()` checks.
"""
import json, os, re, sys

from megasamples.sources import tsql            # the project's identifier rule: lower case, spaces to underscores,
                       # and a hashed truncation for anything over MySQL's 64-character limit

SEP, ROW, NUL, VAL = b"\x1f", b"\x1e\n", "\x00", "\x01"

# SQL Server type -> MySQL type. `max_length` is bytes (-1 for MAX), halved for the n-types.
SIMPLE = {"int": "INT", "bigint": "BIGINT", "smallint": "SMALLINT",
          "tinyint": "TINYINT UNSIGNED",          # SQL Server's tinyint is 0..255, MySQL's is signed
          "bit": "TINYINT(1)", "date": "DATE", "float": "DOUBLE", "real": "DOUBLE",
          "uniqueidentifier": "CHAR(36)", "xml": "LONGTEXT"}


def mysql_type(col, json_columns, spatial):
    t, ml, p, s = col["type"], col["max_length"], col["precision"], col["scale"]
    key = (col["schema"], col["table"], col["name"])
    if key in json_columns:
        return "JSON"
    if t in SIMPLE:
        return SIMPLE[t]
    if t in ("decimal", "numeric"):
        return f"DECIMAL({p},{s})"
    if t == "money":
        return "DECIMAL(19,4)"
    if t == "smallmoney":
        return "DECIMAL(10,4)"
    if t == "datetime2":
        return f"DATETIME({min(s, 6)})"            # 100 ns -> 1 us; see truncation note below
    if t == "datetime":
        return "DATETIME(3)"
    if t == "smalldatetime":
        return "DATETIME"
    if t == "time":
        return f"TIME({min(s, 6)})"
    if t == "datetimeoffset":
        return "VARCHAR(34)"
    if t == "sysname":
        return "VARCHAR(128)"
    if t in ("nvarchar", "nchar", "varchar", "char"):
        if ml == -1:
            return "LONGTEXT"
        chars = ml // 2 if t.startswith("n") else ml
        # `t.endswith("char")` is true for "nvarchar" as well, which quietly turned every string
        # column in both databases into a space-padded fixed-width CHAR
        return f"{'CHAR' if t in ('nchar', 'char') else 'VARCHAR'}({chars})"
    if t in ("varbinary", "binary", "image"):
        return "LONGBLOB" if ml == -1 else f"{'VARBINARY' if t == 'varbinary' else 'BINARY'}({ml})"
    if t in ("text", "ntext"):
        return "LONGTEXT"
    if t in ("geography", "geometry"):
        return f"{spatial.get(key, 'GEOMETRY')} SRID 4326"
    sys.exit(f"no MySQL type for {t} ({'.'.join(key)})")


def table_name(schema, table, prefix=True):
    """`<schema>_<table>`, lower-cased, spaces removed (knowledge/decisions/schema-to-database-mapping.md)."""
    name = re.sub(r"\s+", "", table).lower()
    return tsql.ident(f"{schema.lower()}_{name}" if prefix else name)


def column_name(name):
    """Lower-cased, spaces to underscores -- the rule the mapping decision sets for columns."""
    return tsql.ident(name)


def escape(text):
    return (text.replace("\\", "\\\\").replace("\t", "\\t")
            .replace("\n", "\\n").replace("\r", "\\r"))


def read_rows(path, ncols, name):
    """Yield one list of field strings (or None) per exported row, streaming."""
    buf, pending = b"", 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 22)
            if not chunk:
                break
            buf += chunk
            start = 0
            while True:
                i = buf.find(ROW, start)
                if i < 0:
                    break
                yield split_row(buf[start:i], ncols, name)
                start = i + len(ROW)
                pending += 1
            # Keep only the unfinished record, once per chunk. Slicing the suffix after
            # every row copied terabytes while reading the WWI temperature-history table.
            buf = buf[start:]
    if buf:
        yield split_row(buf, ncols, name)


def split_row(raw, ncols, name):
    fields = raw.split(SEP)
    if len(fields) != ncols:
        sys.exit(f"{name}: a row split into {len(fields)} fields, not {ncols} -- a value contains "
                 f"the field separator, which the export assumed impossible")
    out = []
    for f in fields:
        text = f.decode("utf-8")
        if text == NUL:
            out.append(None)
        elif text.startswith(VAL):
            out.append(text[1:])
        else:
            sys.exit(f"{name}: a field carries neither the NULL nor the value tag "
                     f"({text[:40]!r}); the export and this reader disagree")
    return out


def verify_baseline(observed, expected, name, columns):
    """Compare what we parsed with what SQL Server counted, per column."""
    problems = []
    if observed["n"] != expected["n"]:
        problems.append(f"{observed['n']} rows parsed, SQL Server counted {expected['n']}")
    for i, col in enumerate(columns):
        want = expected["columns"][col["name"]]
        for field, label in (("non_null", "non-null values"), ("units", "UTF-16 code units"),
                             ("non_ascii", "rows with non-ASCII text")):
            if observed[field][i] != want[field]:
                problems.append(f"{col['name']}: {observed[field][i]} {label}, "
                                f"SQL Server counted {want[field]}")
    if problems:
        sys.exit(f"{name}: the export does not match the source:\n    "
                 + "\n    ".join(problems[:12]))


# 'YYYY-MM-DD HH:MM:SS.ffffff' -- MySQL DATETIME(6) holds no more
DATETIME_CHARS = 26


def write_tsv(dat, out, columns, expected, name, json_at=(), trunc_at=()):
    """Write contract TSV and re-derive the three baseline numbers while doing it.

    `json_at` names the column positions the converter declares to be JSON. Every non-null value in
    them is parsed here, so declaring a column JSON is a claim the data has to support: MySQL would
    otherwise reject the whole load with one unhelpful message about one row.

    `trunc_at` names the datetime2(7) columns. MySQL DATETIME(6) is a digit short, and it *rounds*:
    the `9999-12-31 23:59:59.9999999` that system versioning writes into every current row's ValidTo
    rounds up to year 10000, overflows, and lands as a zero date. Truncating here makes the loss
    explicit -- and counted, so the record can say how many values it touched rather than guess.
    The export itself keeps all seven digits; this is a MySQL-side decision, not a lossy export.
    """
    n = len(columns)
    obs = {"n": 0, "non_null": [0] * n, "units": [0] * n, "non_ascii": [0] * n}
    truncated = 0
    with open(out, "w", encoding="utf-8", newline="") as fh:
        for values in read_rows(dat, n, name):
            obs["n"] += 1
            for i, v in enumerate(values):
                if v is None:
                    continue
                obs["non_null"][i] += 1
                obs["units"][i] += len(v.encode("utf-16-le")) // 2
                if any(c < " " or c > "~" for c in v):
                    obs["non_ascii"][i] += 1
                if i in json_at:
                    try:
                        json.loads(v)
                    except ValueError as exc:
                        sys.exit(f"{name}: {columns[i]['name']} is declared JSON but row "
                                 f"{obs['n']} does not parse: {exc}")
            for i in trunc_at:
                if values[i] is not None and len(values[i]) > DATETIME_CHARS:
                    values[i] = values[i][:DATETIME_CHARS]
                    truncated += 1
            fh.write("\t".join("\\N" if v is None else escape(v) for v in values) + "\n")
    verify_baseline(obs, expected, name, columns)
    return obs["n"], truncated


def group(meta):
    by_table, indexes = {}, {}
    for c in meta["columns"]:
        by_table.setdefault((c["schema"], c["table"]), []).append(c)
    for key in by_table:
        by_table[key].sort(key=lambda c: c["column_id"])
    for i in meta["indexes"]:
        indexes.setdefault((i["schema"], i["table"]), {}).setdefault(i["index"], []).append(i)
    return by_table, indexes


def primary_key(indexes, schema, table):
    for name, parts in (indexes.get((schema, table)) or {}).items():
        if parts[0].get("is_primary_key"):
            return [p["column"] for p in sorted(parts, key=lambda p: p["key_ordinal"])
                    if not p.get("is_included_column")]
    return []


def translate_check(definition):
    """`([StockItemID] IS NOT NULL ...)` -> MySQL. Identifier rewrite only; anything else is left
    alone and MySQL is allowed to reject it, which the caller reports rather than hides."""
    text = re.sub(r"\[([^\]]+)\]", lambda m: f"`{column_name(m.group(1))}`", definition)
    return re.sub(r"\bN'", "'", text)


# ---------------------------------------------------------------------------------------------
# the driver: one function both datasets call with their own declarations

def quote(text, limit):
    return "'" + text.replace("\\", "\\\\").replace("'", "''")[:limit] + "'"


def detect_spatial(by_table, export_dir):
    """POINT where every value in the column is a point, GEOMETRY where the shapes vary.

    Declaring POINT is worth the scan: it is what a reader expects of a `Location`, and it is the
    only form MySQL will accept a spatial index on.
    """
    kinds = {}
    for (schema, table), columns in sorted(by_table.items()):
        geo = [i for i, c in enumerate(columns) if c["type"] in ("geography", "geometry")]
        if not geo:
            continue
        path = os.path.join(export_dir, "data", f"{schema}.{table}.dat")
        seen = {i: set() for i in geo}
        for values in read_rows(path, len(columns), f"{schema}.{table}"):
            for i in geo:
                if values[i] is not None:
                    seen[i].add(values[i].split("(", 1)[0].strip().upper())
        for i in geo:
            shapes = seen[i]
            kinds[(schema, table, columns[i]["name"])] = (
                shapes.pop() if len(shapes) == 1 and shapes != {""} else "GEOMETRY")
    return kinds


def convert(cfg, export_dir, out_sql, name_map_path):
    context_dir = os.path.dirname(os.path.abspath(out_sql))
    meta = json.load(open(os.path.join(export_dir, "meta.json"), encoding="utf-8"))
    baseline = json.load(open(os.path.join(export_dir, "baseline.json"), encoding="utf-8"))
    by_table, indexes = group(meta)
    drop = set(cfg.get("drop_tables", ()))
    tables = [k for k in sorted(by_table) if k not in drop]
    unknown = drop - set(by_table)
    if unknown:
        sys.exit(f"dataset.yaml drops tables that do not exist: {sorted(unknown)}")

    spatial = detect_spatial({k: by_table[k] for k in tables}, export_dir)
    json_columns = set(cfg.get("json_columns", ()))
    computed = dict(cfg.get("computed", {}))
    declared = {(c["schema"], c["table"], c["name"]) for c in meta["columns"] if c.get("computed")}
    missing = {k for k in declared if k[:2] not in drop} - set(computed)
    if missing:
        sys.exit(f"computed columns with no MySQL translation: {sorted(missing)}\n"
                 f"add them to the converter rather than letting them vanish")

    # sequence-backed key columns become AUTO_INCREMENT, seeded past the sequence's current value
    seq_value = {(s["schema"], s["name"]): s["current_value"] + s["increment"]
                 for s in meta["sequences"]}
    autoinc, seeds, unported = {}, {}, list(cfg.get("unported", []))
    for c in meta["columns"]:
        key = (c["schema"], c["table"], c["name"])
        if key[:2] in drop:
            continue
        seq = re.match(r"\(NEXT VALUE FOR \[([^\]]+)\]\.\[([^\]]+)\]\)", c.get("default") or "")
        if not (c.get("is_identity") or seq):
            continue
        pk = primary_key(indexes, c["schema"], c["table"])
        if pk[:1] != [c["name"]]:
            unported.append(f"{'.'.join(key)}: {'identity' if c.get('is_identity') else 'sequence'}"
                            f" default, but the column does not lead the primary key, so it is a "
                            f"plain column here")
            continue
        autoinc[key] = True
        if seq:
            seeds[table_name(c["schema"], c["table"], cfg["prefix"])] = seq_value[seq.groups()]

    name_map, ddl, loads, later, fks = {}, [], [], [], []
    stats = {"truncated": 0}
    for schema, table in tables:
        cols = by_table[(schema, table)]
        name = table_name(schema, table, cfg["prefix"])
        for c in cols:
            name_map[f"{schema}.{table}.{c['name']}"] = f"{name}.{column_name(c['name'])}"
        name_map[f"{schema}.{table}"] = name
        ddl.append(create_table(cfg, schema, table, name, cols, indexes, json_columns, spatial,
                                computed, autoinc, meta, unported))
        loads.append(load_data(cfg, schema, table, name, cols, json_columns, computed, spatial,
                               baseline, export_dir, context_dir, stats))
        later += secondary_indexes(schema, table, name, cols, indexes, json_columns, spatial,
                                   computed, unported)
    for fk in foreign_keys(meta, drop, cfg, by_table):
        fks.append(fk)

    kinds = {}
    for r in meta["routines"]:
        kinds.setdefault(r["type_desc"].lower().replace("sql_", "").replace("_", " "), []).append(
            f"{r['schema']}.{r['name']}")
    for kind, names in sorted(kinds.items()):
        unported.append(f"{len(names)} {kind}(s), listed in the dataset record (task V-02): "
                        + ", ".join(sorted(names)[:4]) + (", ..." if len(names) > 4 else ""))

    sql = [f"""-- {cfg['title']}, converted by datasets/{cfg['dataset']}/convert.py from the export
-- megasamples/sources/wwi_export.py takes out of Microsoft's .bak. Upstream: microsoft/sql-server-samples (MIT).
-- See datasets/{cfg['dataset']}/PROVENANCE.md for how the export was produced.
SET NAMES utf8mb4;
SET SESSION foreign_key_checks = 0;
-- Both databases use dimension/reference key 0 for the "Unknown" member. Without this, MySQL
-- treats a 0 loaded into an AUTO_INCREMENT column as "generate one", which renumbers that row on
-- top of key 1 -- and LOAD DATA LOCAL implies IGNORE, so the real key-1 row is dropped without a
-- word. That cost `dimension_customer` a row before the counts were pinned from SQL Server.
SET SESSION sql_mode = CONCAT(@@sql_mode, ',NO_AUTO_VALUE_ON_ZERO');
DROP DATABASE IF EXISTS `{cfg['database']}`;
CREATE DATABASE `{cfg['database']}` DEFAULT CHARACTER SET utf8mb4;
USE `{cfg['database']}`;
"""]
    sql += ddl
    sql.append(f"\n-- {'-' * 70}\n-- data\n")
    sql += loads
    sql.append(f"\n-- {'-' * 70}\n-- secondary indexes\n")
    sql += later
    sql.append(f"\n-- {'-' * 70}\n-- foreign keys\n")
    sql += fks
    if seeds:
        sql.append(f"\n-- {'-' * 70}\n-- sequence positions carried over from SQL Server\n")
        sql += [f"ALTER TABLE `{t}` AUTO_INCREMENT = {v};" for t, v in sorted(seeds.items())]
    sql.append("\nSET SESSION foreign_key_checks = 1;\n")
    open(out_sql, "w", encoding="utf-8").write("\n".join(sql))

    counts = os.path.join(os.path.dirname(name_map_path), "tests", "expected_counts.yaml")
    os.makedirs(os.path.dirname(counts), exist_ok=True)
    with open(counts, "w", encoding="utf-8") as fh:
        fh.write("# authority: SQL Server. These are the counts sys.partitions reported inside the\n"
                 "# restored .bak, carried through the export -- not counts read back from MySQL. A\n"
                 "# row lost on the way in therefore fails the check instead of being pinned as\n"
                 "# correct, which is how a silently dropped row was found. Regenerate with\n"
                 "#   python3 -m megasamples stage %s\n" % cfg["dataset"])
        for schema, table in tables:
            fh.write(f"{table_name(schema, table, cfg['prefix'])}: "
                     f"{baseline[f'{schema}.{table}']['n']}\n")

    with open(name_map_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Generated by datasets/{cfg['dataset']}/convert.py: "
                 f"source schema.table[.column] -> MySQL name.\n")
        for old, new in sorted(name_map.items()):
            fh.write(f"{old}: {new}\n")

    rows = sum(baseline[f"{s}.{t}"]["n"] for s, t in tables)
    print(f"  . {len(tables)} tables, {rows:,} rows, {len(later)} secondary indexes, "
          f"{len(fks)} foreign keys, {len(autoinc)} AUTO_INCREMENT columns")
    print(f"  . {stats['truncated']:,} datetime2(7) values truncated to DATETIME(6)")
    for u in unported:
        print(f"  . unported {u}")
    return len(tables), rows


def comment_of(text):
    return f" COMMENT {quote(text, 1024)}" if text else ""


def create_table(cfg, schema, table, name, cols, indexes, json_columns, spatial, computed,
                 autoinc, meta, unported):
    body = []
    for c in cols:
        key = (schema, table, c["name"])
        col, note = column_name(c["name"]), comment_of(c.get("description"))
        if key in computed:
            expr = computed[key]
            body.append(f"  `{col}` {mysql_type(c, json_columns, spatial)} "
                        f"GENERATED ALWAYS AS ({expr}) VIRTUAL{note}")
            continue
        default = ""
        if (c.get("default") or "").lower() == "(sysdatetime())":
            default = " DEFAULT CURRENT_TIMESTAMP(6)"
        body.append(f"  `{col}` {mysql_type(c, json_columns, spatial)}"
                    f"{'' if c['is_nullable'] else ' NOT NULL'}{default}"
                    f"{' AUTO_INCREMENT' if key in autoinc else ''}{note}")
    pk = primary_key(indexes, schema, table)
    if pk:
        body.append("  PRIMARY KEY (" + ", ".join(f"`{column_name(c)}`" for c in pk) + ")")
    for chk in meta["checks"]:
        if (chk["schema"], chk["table"]) != (schema, table):
            continue
        if "isjson" in chk["definition"].lower():
            unported.append(f"check {chk['name']}: the column is a MySQL JSON column, which "
                            f"enforces the same thing")
            continue
        body.append(f"  CONSTRAINT `{tsql.ident(chk['name'])}` "
                    f"CHECK {translate_check(chk['definition'])}")
    table_note = next((t.get("description") for t in meta["tables"]
                       if (t["schema"], t["name"]) == (schema, table)), None)
    return (f"DROP TABLE IF EXISTS `{name}`;\nCREATE TABLE `{name}` (\n" + ",\n".join(body)
            + f"\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            + (f" COMMENT={quote(table_note, 2048)}" if table_note else "") + ";")


def load_data(cfg, schema, table, name, cols, json_columns, computed, spatial, baseline,
              export_dir, context_dir, stats):
    dat = os.path.join(export_dir, "data", f"{schema}.{table}.dat")
    tsv = os.path.join(context_dir, f"{name}.tsv")
    json_at = {i for i, c in enumerate(cols) if (schema, table, c["name"]) in json_columns}
    trunc_at = {i for i, c in enumerate(cols) if c["type"] == "datetime2" and c["scale"] > 6}
    _, truncated = write_tsv(dat, tsv, cols, baseline[f"{schema}.{table}"], f"{schema}.{table}",
                             json_at, trunc_at)
    stats["truncated"] += truncated
    targets, sets = [], []
    for c in cols:
        key, col = (schema, table, c["name"]), column_name(c["name"])
        if key in computed:
            targets.append(f"@generated_{col}")            # MySQL computes it; the file still has it
        elif c["type"] in ("varbinary", "binary", "image"):
            targets.append(f"@{col}")
            sets.append(f"`{col}` = UNHEX(@{col})")
        elif c["type"] in ("geography", "geometry"):
            # SQL Server's STAsText() writes longitude first; MySQL reads SRID 4326 as latitude
            # first unless told otherwise, which would silently put every point in the wrong place
            targets.append(f"@{col}")
            sets.append(f"`{col}` = ST_GeomFromText(@{col}, 4326, 'axis-order=long-lat')")
        else:
            targets.append(f"`{col}`")
    stmt = (f"LOAD DATA LOCAL INFILE '{cfg['context']}/{name}.tsv' INTO TABLE `{name}`\n"
            f"  CHARACTER SET utf8mb4 ({', '.join(targets)})")
    return stmt + (("\n  SET " + ",\n      ".join(sets)) if sets else "") + ";"


NEEDS_PREFIX = ("LONGTEXT", "LONGBLOB", "TEXT", "BLOB")
# InnoDB caps a key part at 3072 bytes and utf8mb4 spends 4 per character, so a key part is
# prefixed once it would exceed this. 190 characters is the same budget MySQL's own utf8mb4 index
# advice uses, and it leaves room for several parts in one key.
MAX_KEY_CHARS = 190


def index_part(c, col, json_columns, spatial, unported, index):
    """One key part, with a prefix length where MySQL demands one and None where it refuses."""
    t = mysql_type(c, json_columns, spatial)
    if t == "JSON":
        unported.append(f"index {index}: MySQL cannot index a JSON column ({col}) directly")
        return None, 0
    if t.startswith(NEEDS_PREFIX):
        return f"`{col}`(100)", 400               # a prefix is mandatory for a TEXT/BLOB key part
    if t.endswith("SRID 4326"):
        unported.append(f"index {index}: spatial key part {col} needs a NOT NULL column")
        return None, 0
    size = re.match(r"(?:VAR)?CHAR\((\d+)\)", t)
    if size and int(size.group(1)) > MAX_KEY_CHARS:
        return f"`{col}`({MAX_KEY_CHARS})", MAX_KEY_CHARS * 4
    return f"`{col}`", (int(size.group(1)) * 4 if size else 8)


def secondary_indexes(schema, table, name, cols, indexes, json_columns, spatial, computed,
                      unported):
    """Every non-primary index, as one ALTER per table so InnoDB rebuilds the table once."""
    by_name = {c["name"]: c for c in cols}
    clauses = []
    for index, parts in sorted((indexes.get((schema, table)) or {}).items()):
        if parts[0].get("is_primary_key"):
            continue
        keys = sorted([p for p in parts if not p.get("is_included_column")],
                      key=lambda p: p["key_ordinal"])
        # MySQL has no INCLUDE; appending the included columns as trailing key parts reproduces
        # the covering behaviour, and none of them is a LOB here
        keys += sorted([p for p in parts if p.get("is_included_column")],
                       key=lambda p: p["index_column_id"])
        rendered = [index_part(by_name[p["column"]], column_name(p["column"]), json_columns,
                               spatial, unported, index) for p in keys]
        if any(r is None for r, _ in rendered):
            continue
        if sum(n for _, n in rendered) > 3000:
            unported.append(f"index {index}: the key parts total "
                            f"{sum(n for _, n in rendered)} bytes, over InnoDB's 3072")
            continue
        unique = "UNIQUE " if parts[0].get("is_unique") else ""
        clauses.append(f"ADD {unique}KEY `{tsql.ident(index)}` "
                       f"({', '.join(r for r, _ in rendered)})")
    return [f"ALTER TABLE `{name}` " + ",\n  ".join(clauses) + ";"] if clauses else []


def foreign_keys(meta, drop, cfg, by_table):
    grouped = {}
    for f in meta["fks"]:
        grouped.setdefault(f["name"], []).append(f)
    out = []
    for fname, parts in sorted(grouped.items()):
        parts.sort(key=lambda p: p["constraint_column_id"])
        p = parts[0]
        if (p["schema"], p["table"]) in drop or (p["ref_schema"], p["ref_table"]) in drop:
            continue
        child = table_name(p["schema"], p["table"], cfg["prefix"])
        parent = table_name(p["ref_schema"], p["ref_table"], cfg["prefix"])
        cols = ", ".join(f"`{column_name(q['column'])}`" for q in parts)
        refs = ", ".join(f"`{column_name(q['ref_column'])}`" for q in parts)
        out.append(f"ALTER TABLE `{child}` ADD CONSTRAINT `{tsql.ident(fname)}`\n"
                   f"  FOREIGN KEY ({cols}) REFERENCES `{parent}` ({refs});")
    return out
