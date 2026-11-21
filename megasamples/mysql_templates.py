"""Replay a captured MySQL schema using the connection that owns the copy."""

import re

DEFINER = re.compile(r"^((?:CREATE)(?:\s+ALGORITHM\s*=\s*\w+)?)\s+DEFINER\s*=\s*"
                     r"`(?:[^`]|\x60\x60)*`\s*@\s*`(?:[^`]|\x60\x60)*`", re.I)
# MySQL's lexical rules (Sol round 8, P3-8): `--` opens a comment only before whitespace, a control
# character or the end; `/*!` opens an executable comment, whose content is code, so only its opener is
# one token; an unquoted identifier holds ASCII letters, digits, `_`, `$` and U+0080 to U+FFFF.
# ANSI_QUOTES and NO_BACKSLASH_ESCAPES programs are withheld before replay (design 2.4).
SQL_TOKEN = re.compile(r"'(?:''|\\.|[^'\\])*'|\"(?:\"\"|\\.|[^\"\\])*\"|`(?:``|[^`])*`|"
                       r"/\*![0-9]*|/\*[\s\S]*?\*/|--(?=[\s\x00-\x1f\x7f]|$)[^\n]*|#[^\n]*|"
                       r"[A-Za-z0-9_$\u0080-\uffff]+|\s+|.")


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


def objects_are_current(objects):
    """Every object recorded with the settings this version replays: a view, or a program with its mode."""
    kinds = {"view": ("ddl",), "procedure": ("ddl", "sql_mode"), "event": ("ddl", "sql_mode", "time_zone")}
    return all(isinstance(item, dict) and item.get("kind") in kinds and all(
        isinstance(item.get(key), str) for key in kinds[item["kind"]]) for item in objects)


def replay(run, query, metadata, source, target, *, remove_definer):
    old_checks, old_mode, old_zone = query(
        "SELECT @@session.foreign_key_checks, @@session.sql_mode, @@session.time_zone")[0]
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
            # A view stores no settings; a stored program is made under the mode its source had, and an
            # event under its time zone too.
            mode, zone = item.get("sql_mode", old_mode), item.get("time_zone", old_zone)
            run("SET SESSION sql_mode='" + mode.replace("'", "''") + "', time_zone='" + zone.replace("'", "''") + "'")
            run(definition(item["ddl"], metadata["database"], target, remove_definer))
        run(f"SET SESSION sql_mode='{old_mode}', time_zone='{old_zone}'")
        for table in metadata["tables"]:
            destination = qualify(target, table["name"])
            count = query(f"SELECT COUNT(*) FROM {destination}")[0][0]
            checksum = query(f"CHECKSUM TABLE {destination} EXTENDED")[0][1]
            if count != table["count"] or checksum is None or checksum != table["checksum"]:
                raise ValueError("table verification failed")
    finally:
        run(f"SET SESSION foreign_key_checks={int(old_checks)}, sql_mode='{old_mode}', time_zone='{old_zone}'")
        run("USE megasamples")
