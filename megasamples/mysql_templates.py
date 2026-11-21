"""Replay a captured MySQL schema using the connection that owns the copy."""

import re

DEFINER = re.compile(r"^((?:CREATE)(?:\s+ALGORITHM\s*=\s*\w+)?)\s+DEFINER\s*=\s*"
                     r"`(?:[^`]|\x60\x60)*`\s*@\s*`(?:[^`]|\x60\x60)*`", re.I)
SQL_TOKEN = re.compile(r"'(?:''|\\.|[^'\\])*'|\"(?:\"\"|\\.|[^\"\\])*\"|`(?:``|[^`])*`|"
                       r"/\*[\s\S]*?\*/|--[^\n]*|#[^\n]*|[A-Za-z0-9_]+|\s+|.")


def quote(name):
    return "`" + name.replace("`", "``") + "`"


def qualify(database, name):
    return f"{quote(database)}.{quote(name)}"


def demo_read_grants(working, foreign):
    schemas = [*working, *(prefix + "_%" for prefix, readable in foreign if readable)]
    return [
        ("SELECT", "megasamples.datasets"),
        ("SELECT", "megasamples.copy_service"),
        *(("SELECT, SHOW VIEW", quote(name.replace("_", r"\_")) + ".*") for name in schemas),
    ]


def definition(sql, source, target, remove_definer):
    if remove_definer:
        sql = DEFINER.sub(r"\1", sql, count=1)
    tokens = SQL_TOKEN.findall(sql)
    for index, token in enumerate(tokens):
        if token.casefold() not in (source.casefold(), quote(source).casefold()):
            continue
        suffix = index + 1
        while suffix < len(tokens) and tokens[suffix].isspace():
            suffix += 1
        if suffix < len(tokens) and tokens[suffix] == ".":
            tokens[index] = quote(target)
    return "".join(tokens)


def create_schema(run, name, charset, collation):
    run(f"CREATE DATABASE {quote(name)} CHARACTER SET {quote(charset)} COLLATE {quote(collation)}")


def replay(run, query, metadata, source, target, *, remove_definer):
    old_checks, old_mode = query("SELECT @@session.foreign_key_checks, @@session.sql_mode")[0]
    modes = old_mode.split(",") if old_mode else []
    if "NO_AUTO_VALUE_ON_ZERO" not in modes:
        modes.append("NO_AUTO_VALUE_ON_ZERO")
    run("SET SESSION foreign_key_checks=0")
    try:
        run(f"USE {quote(target)}")
        for table in metadata["tables"]:
            run(definition(table["ddl"], metadata["database"], target, remove_definer))
        # Only the row copy needs an explicit AUTO_INCREMENT zero kept; no definition is made under it.
        run(f"SET SESSION sql_mode='{','.join(modes)}'")
        for table in metadata["tables"]:
            columns = ", ".join(map(quote, table["columns"]))
            src = qualify(source, table["name"])
            dst = qualify(target, table["name"])
            run(f"INSERT INTO {dst} ({columns}) SELECT {columns} FROM {src}")
        run(f"SET SESSION sql_mode='{old_mode}'")
        for item in metadata["objects"]:
            # A view stores no SQL mode; a stored program is made under the one its source had.
            ddl, mode = (item["ddl"], item["sql_mode"]) if isinstance(item, dict) else (item, old_mode)
            run("SET SESSION sql_mode='" + mode.replace("'", "''") + "'")
            run(definition(ddl, metadata["database"], target, remove_definer))
        run(f"SET SESSION sql_mode='{old_mode}'")
        for table in metadata["tables"]:
            destination = qualify(target, table["name"])
            count = query(f"SELECT COUNT(*) FROM {destination}")[0][0]
            checksum = query(f"CHECKSUM TABLE {destination} EXTENDED")[0][1]
            if count != table["count"] or checksum is None or checksum != table["checksum"]:
                raise ValueError("table verification failed")
    finally:
        run(f"SET SESSION foreign_key_checks={int(old_checks)}, sql_mode='{old_mode}'")
        run("USE megasamples")
