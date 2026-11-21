"""Inventory and build MySQL templates from the image's loaded registry."""

import hashlib
import json
from pathlib import Path
import sys

from mysqlsh import globals as mysqlsh
from mysql_templates import create_schema, demo_read_grants, qualify, quote, replay


def run(sql, parameters=()):
    return mysqlsh.session.run_sql(sql, list(parameters))


def query(sql, parameters=()):
    return run(sql, parameters).fetch_all()


def available_objects(database):
    schema = " WHERE TABLE_SCHEMA=?"
    tables = query("SELECT TABLE_NAME FROM information_schema.TABLES" + schema +
                   " AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME", (database,))
    definitions = []
    for (table,) in tables:
        name = qualify(database, table)
        columns = [
            row[0] for row in query(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=? AND TABLE_NAME=? "
                "AND EXTRA NOT LIKE '%VIRTUAL GENERATED%' AND EXTRA NOT LIKE '%STORED GENERATED%' "
                "ORDER BY ORDINAL_POSITION", (database, table),
            )
        ]
        definition = query(f"SHOW CREATE TABLE {name}")[0][1]
        count = query(f"SELECT COUNT(*) FROM {name}")[0][0]
        checksum = query(f"CHECKSUM TABLE {name} EXTENDED")[0][1]
        if checksum is None:
            raise RuntimeError(f"could not checksum {name}")
        definitions.append({"name": table, "ddl": definition, "columns": columns,
                            "count": count, "checksum": checksum})

    routines = query("SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                     "WHERE ROUTINE_SCHEMA=? AND ROUTINE_TYPE='PROCEDURE' ORDER BY ROUTINE_NAME", (database,))
    views = {row[0] for row in query("SELECT TABLE_NAME FROM information_schema.VIEWS" + schema, (database,))}
    dependencies = {view: set() for view in views}
    for view, referenced in query(
        "SELECT VIEW_NAME, TABLE_NAME FROM information_schema.VIEW_TABLE_USAGE "
        "WHERE VIEW_SCHEMA=? AND TABLE_SCHEMA=?", (database, database),
    ):
        if view in views and referenced in views:
            dependencies[view].add(referenced)
    events = query("SELECT EVENT_NAME FROM information_schema.EVENTS WHERE EVENT_SCHEMA=? ORDER BY EVENT_NAME",
                   (database,))
    objects = [query(f"SHOW CREATE PROCEDURE {qualify(database, name)}")[0][2] for (name,) in routines]
    while dependencies:
        ready = sorted(view for view, inputs in dependencies.items() if not inputs)
        if not ready:
            raise RuntimeError("cyclic view dependencies")
        for view in ready:
            objects.append(query(f"SHOW CREATE VIEW {qualify(database, view)}")[0][1])
            dependencies.pop(view)
        for inputs in dependencies.values():
            inputs.difference_update(ready)
    objects.extend(query(f"SHOW CREATE EVENT {qualify(database, name)}")[0][3] for (name,) in events)
    return definitions, objects


def exclusion(database, selected, size, triggers, functions):
    if database in ("oracle_hr", "oracle_oe"):
        return "dependency-group", "bound to the Oracle HR/OE dependency group"
    if triggers or functions:
        reasons = ["trigger " + row[0] for row in triggers] + ["function " + row[0] for row in functions]
        return "not-replayable", ", ".join(reasons)
    if database not in selected:
        return "no-template", "not selected for templates"
    if size > 512 * 1024 * 1024:
        return "too-large", "allocated bytes exceed the template limit"
    return None, None


def allocated_bytes(database):
    innodb = query("""
        SELECT COALESCE(SUM(s.ALLOCATED_SIZE),0)
        FROM information_schema.INNODB_TABLESPACES s
        WHERE s.SPACE IN (
            SELECT t.SPACE FROM information_schema.INNODB_TABLES t
            WHERE SUBSTRING_INDEX(t.NAME,'/',1)=?
        )
    """, (database,))[0][0]
    other_engines = query("SELECT 1 FROM information_schema.TABLES "
                          "WHERE TABLE_SCHEMA=? AND TABLE_TYPE='BASE TABLE' AND ENGINE<>'InnoDB' LIMIT 1",
                          (database,))
    if not other_engines:
        return int(innodb)
    datadir = Path(query("SELECT @@datadir")[0][0]) / database
    other_files = sum(path.stat().st_blocks * 512 for path in datadir.iterdir()
                      if path.is_file() and path.suffix != ".ibd")
    return int(innodb) + other_files


def build_offers(settings):
    run("CREATE TABLE megasamples.template_ddl (name varchar(64) PRIMARY KEY, "
        "reason varchar(32), detail text, metadata json)")
    for name, build in query("SELECT name, build_id FROM megasamples.datasets ORDER BY name"):
        args = (name,)
        size = int(query("SELECT COALESCE(SUM(data_length + index_length),0) "
                         "FROM information_schema.TABLES WHERE TABLE_SCHEMA=?", args)[0][0])
        triggers = query("SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
                         "WHERE TRIGGER_SCHEMA=? ORDER BY TRIGGER_NAME", args)
        functions = query("SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                          "WHERE ROUTINE_SCHEMA=? AND ROUTINE_TYPE='FUNCTION' ORDER BY ROUTINE_NAME", args)
        reason, detail = exclusion(name, settings["templates"], size, triggers, functions)
        metadata = None
        if reason is None:
            charset, collation = query(
                "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
                "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=?", args,
            )[0]
            table_ddl, objects = available_objects(name)
            registry_row = list(query("SELECT * FROM megasamples.datasets WHERE name=?", args)[0])
            digest = hashlib.sha256(json.dumps(registry_row).encode()).hexdigest()
            template = name + "_start"
            metadata = {"tag": "megasamples-template/1", "database": name, "charset": charset,
                        "collation": collation, "tables": table_ddl, "objects": objects,
                        "build": build, "digest": digest, "bytes": int(size)}
            create_schema(run, template, charset, collation)
            replay(run, query, metadata, name, template, remove_definer=False)
            run(f"ALTER DATABASE {quote(template)} READ ONLY=1")
            print(f"template {name}: {size} allocated bytes")
        else:
            definitions = ["trigger " + row[0] for row in triggers] + ["function " + row[0] for row in functions]
            suffix = " (" + ", ".join(definitions) + ")" if definitions and reason != "not-replayable" else ""
            print(f"withheld {name}: {reason}: {detail}{suffix}")
        run("INSERT INTO megasamples.template_ddl VALUES (?,?,?,?)",
            (name, reason, detail, json.dumps(metadata) if metadata is not None else None))


def escaped_pattern(name):
    return name.replace("_", "\\_")


def account(name):
    return f"'{name}'@'%'"


def outside_grants(prefix, owner, readers):
    namespace = f"LEFT(s.SCHEMA_NAME,{len(prefix) + 1}) = '{prefix}_'"
    outside = (f"NOT ((g.User IN ('{owner}','admin') AND g.Host='%') "
               "OR (g.User='root' AND g.Host IN ('%','localhost')))")
    readers = [name for name, scopes in readers.items() if prefix in scopes]
    intended = "TRUE"
    if readers:
        names = ", ".join(f"'{name}'" for name in readers)
        pattern = escaped_pattern(prefix) + "\\_%"
        privileges = [column for (column,) in query(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA='mysql' AND TABLE_NAME='db' AND RIGHT(COLUMN_NAME,5)='_priv'"
        ) if column.lower() not in ("select_priv", "show_view_priv")]
        no_other_privileges = " AND ".join(f"g.{quote(column)}='N'" for column in privileges)
        intended = (f"NOT (g.Host='%' AND g.User IN ({names}) AND g.Db='{pattern}' "
                    f"AND g.Select_priv='Y' AND g.Show_view_priv='Y' AND {no_other_privileges})")
    schema = f"""
        SELECT s.SCHEMA_NAME AS copy_name, g.User, g.Host, g.Db, g.Create_priv, g.Drop_priv
        FROM information_schema.SCHEMATA s JOIN mysql.db g ON s.SCHEMA_NAME LIKE g.Db
        WHERE {namespace} AND {outside} AND {intended}
    """
    narrower = [
        f"""
        SELECT s.SCHEMA_NAME, g.User, g.Host, g.Db, 'N', 'N'
        FROM information_schema.SCHEMATA s JOIN mysql.{table} g ON s.SCHEMA_NAME=g.Db
        WHERE {namespace} AND {outside}
        """
        for table in ("tables_priv", "columns_priv", "procs_priv")
    ]
    return " UNION ".join([schema, *narrower])


def grant_rights(settings):
    run("CREATE TABLE megasamples.copy_service (tag varchar(40) PRIMARY KEY)")
    run("INSERT INTO megasamples.copy_service VALUES ('megasamples-service/1')")
    run("CREATE TABLE megasamples.copy_namespaces "
        "(prefix varchar(16) PRIMARY KEY, owner varchar(16) NOT NULL, max_copies integer NOT NULL)")
    working = [row[0] for row in query("SELECT name FROM megasamples.datasets")]
    templates = [row[0] + "_start" for row in query("SELECT name FROM megasamples.template_ddl WHERE reason IS NULL")]

    def grant(privileges, schemas, grantee):
        for schema in schemas:
            run(f"GRANT {privileges} ON {quote(schema)}.* TO {grantee}")

    for privileges, scope in demo_read_grants(working, settings["foreign"]):
        run(f"GRANT {privileges} ON {scope} TO 'demo'@'%'")

    for prefix, owner, limit in settings["namespaces"]:
        principal = account(owner)
        run(f"CREATE USER {principal} ACCOUNT LOCK")
        run("INSERT INTO megasamples.copy_namespaces VALUES (?,?,?)", (prefix, owner, limit))
        ledger = qualify("megasamples", "copy_ledger_" + prefix)
        run(f"CREATE TABLE {ledger} (name varchar(63) PRIMARY KEY, record json NOT NULL)")
        run(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {ledger} TO {principal}")
        for table in ("copy_namespaces", "copy_service", "template_ddl", "datasets"):
            run(f"GRANT SELECT ON {qualify('megasamples', table)} TO {principal}")
        grant("SELECT", map(escaped_pattern, templates), principal)
        grant("ALL PRIVILEGES", [escaped_pattern(prefix) + "\\_%"], principal)
        lookup = qualify("megasamples", "copy_grants_" + prefix)
        run(f"CREATE SQL SECURITY DEFINER VIEW {lookup} AS " + outside_grants(prefix, owner, settings["readers"]))
        run(f"GRANT SELECT ON {lookup} TO {principal}")

    for mode in ("readers", "writers"):
        for name, scopes in settings[mode].items():
            principal = account(name)
            run(f"CREATE USER {principal} ACCOUNT LOCK")
            read = "SELECT, SHOW VIEW"
            if "working" in scopes:
                privileges = read if mode == "readers" else read + ", INSERT, UPDATE, DELETE"
                grant(privileges, map(escaped_pattern, working), principal)
            grant(read, (escaped_pattern(scope) + "\\_%" for scope in scopes if scope != "working"), principal)


def main(settings):
    build_offers(settings)
    grant_rights(settings)


if __name__ == "__main__":
    main(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
