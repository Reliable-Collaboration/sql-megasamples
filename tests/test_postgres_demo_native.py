"""PostgreSQL's demo, natively: PostgreSQL's own read model, and the statements DataIntent sends as it.

"Read only" is what PostgreSQL itself defines: demo holds the built-in role pg_read_all_data and no
write privilege, directly, through a role or through a default privilege; otherwise the engine's
defaults stand (CONNECT, TEMPORARY, EXECUTE on built-in functions, large objects of its own). A
write reaching the samples, inherited through a role, a default privilege or pg_write_all_data, is
what the account checks refuse.

The consumer compatibility check runs each catalog, describe, snapshot and data-read statement of
DataIntent's PostgreSQL adapter (src/DataIntent.Adapters/Postgres in RCC.DataIntent) as demo. It is
kept permanently: a change to demo that breaks a consumer fails here first.

Opt in with POSTGRES_DEMO_NATIVE=HOST:PORT naming a server from this image (demo's password from
POSTGRES_DEMO_PASSWORD, default the factory `demo`). It needs psycopg and libpq.
"""
import os

import pytest

TARGET = os.environ.get("POSTGRES_DEMO_NATIVE", "")
PASSWORD = os.environ.get("POSTGRES_DEMO_PASSWORD", "demo")
CONSUMER_DATABASES = ("chinook", "northwind", "pubs")

pytestmark = pytest.mark.skipif(not TARGET, reason="set POSTGRES_DEMO_NATIVE=HOST:PORT to a server from this image")


def connect(database, user="demo"):
    import psycopg
    host, _, port = TARGET.rpartition(":")
    return psycopg.connect(host=host, port=int(port), user=user, password=PASSWORD, dbname=database,
                           autocommit=True, connect_timeout=10)


def sqlstate(connection, sql):
    """None when the statement runs, its SQLSTATE when PostgreSQL refuses it (in its own transaction)."""
    import psycopg
    try:
        with connection.transaction():
            connection.execute("SET LOCAL statement_timeout = 30000")
            cursor = connection.execute(sql)
            if cursor.description:
                cursor.fetchall()
        return None
    except psycopg.Error as error:
        return error.sqlstate


def sample_databases():
    with connect("megasamples") as connection:
        names = [row[0] for row in connection.execute(
            "SELECT DISTINCT d.datname FROM datasets r JOIN pg_database d ON d.datname = r.name "
            "WHERE d.datallowconn ORDER BY 1")]
    assert names, "the registry names no sample database on this server"
    return names


def first_table(connection):
    return connection.execute("""
        SELECT c.relname::text, array_agg(a.attname::text ORDER BY a.attnum),
               (array_agg(a.attname::text ORDER BY a.attnum)
                FILTER (WHERE format_type(a.atttypid, NULL) IN ('integer', 'bigint', 'smallint', 'numeric')))[1]
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        GROUP BY c.relname ORDER BY c.relname LIMIT 1""").fetchone()


# --- the consumer compatibility check: DataIntent's statements, as its adapter sends them ---------------

SYSTEM = "n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'"
RELS = f"""WITH rels AS (
    SELECT c.oid, n.nspname, c.relname, c.relkind
    FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'v', 'm', 'f', 'p') AND NOT c.relispartition AND {SYSTEM}
    ORDER BY n.nspname, c.relname LIMIT 10000)"""
COLUMNS = """, btree_types AS (
    SELECT oc.opcintype AS typ FROM pg_catalog.pg_opclass oc JOIN pg_catalog.pg_am am ON am.oid = oc.opcmethod
    WHERE am.amname = 'btree' AND oc.opcdefault
    UNION
    SELECT c.castsource FROM pg_catalog.pg_cast c
    JOIN pg_catalog.pg_opclass oc ON oc.opcintype = c.casttarget JOIN pg_catalog.pg_am am ON am.oid = oc.opcmethod
    WHERE c.castmethod = 'b' AND am.amname = 'btree' AND oc.opcdefault)
SELECT a.attrelid::int8, a.attname::text, a.attnum::int4, pg_catalog.format_type(a.atttypid, a.atttypmod),
       ((a.attnotnull AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_constraint nn WHERE nn.conrelid = a.attrelid AND nn.contype = 'n'
            AND nn.conkey = ARRAY[a.attnum]::int2[] AND NOT nn.convalidated)) OR (t.typtype = 'd' AND t.typnotnull)),
       bt.typname::text, pg_catalog.format_type(bt.oid, NULL), bt.typcategory::text, bt.typtype::text,
       (CASE WHEN t.typtype = 'd' AND a.atttypmod < 0 THEN t.typtypmod ELSE a.atttypmod END)::int4,
       (bt.oid IN (SELECT typ FROM btree_types)
          OR (bt.typcategory = 'A' AND bt.typelem IN (SELECT typ FROM btree_types))
          OR bt.typtype IN ('e', 'r')),
       CASE WHEN a.attgenerated = '' THEN pg_catalog.pg_get_expr(d.adbin, d.adrelid) END,
       a.attidentity <> '',
       CASE WHEN a.attgenerated <> '' THEN pg_catalog.pg_get_expr(d.adbin, d.adrelid) END,
       a.attgenerated::text,
       pg_catalog.col_description(a.attrelid, a.attnum),
       COALESCE((SELECT co.collisdeterministic FROM pg_catalog.pg_collation co WHERE co.oid = a.attcollation), true)
FROM rels r
JOIN pg_catalog.pg_attribute a ON a.attrelid = r.oid
JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
JOIN pg_catalog.pg_type bt ON bt.oid = CASE WHEN t.typtype = 'd' THEN t.typbasetype ELSE t.oid END
LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
WHERE a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attrelid, a.attnum"""
CATALOG = {
    "version and database": "SELECT current_setting('server_version'), current_database()",
    "schemas": f"SELECT n.nspname::text FROM pg_catalog.pg_namespace n WHERE {SYSTEM} ORDER BY 1",
    "relation counts": f"""SELECT count(*) FILTER (WHERE NOT c.relispartition), count(*) FILTER (WHERE c.relispartition)
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r', 'v', 'm', 'f', 'p') AND {SYSTEM}""",
    "relations": RELS + """
        SELECT r.oid::int8, r.nspname::text, r.relname::text, r.relkind::text, pg_catalog.obj_description(r.oid, 'pg_class'),
               c.reltuples::float8, pg_catalog.has_schema_privilege(c.relnamespace, 'USAGE'),
               pg_catalog.has_table_privilege(r.oid, 'SELECT'), pg_catalog.has_any_column_privilege(r.oid, 'SELECT'),
               CASE WHEN r.relkind IN ('v', 'm') THEN pg_catalog.pg_get_viewdef(r.oid) END, c.relrowsecurity
        FROM rels r JOIN pg_catalog.pg_class c ON c.oid = r.oid ORDER BY r.nspname, r.relname""",
    "columns": RELS + COLUMNS,
    "keys": RELS + """
        SELECT con.conrelid::int8, con.conname::text, con.contype::text,
               ARRAY(SELECT a.attname::text FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
                     JOIN pg_catalog.pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum ORDER BY k.ord),
               tn.nspname::text, tc.relname::text,
               ARRAY(SELECT a.attname::text FROM unnest(con.confkey) WITH ORDINALITY k(attnum, ord)
                     JOIN pg_catalog.pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.attnum ORDER BY k.ord),
               con.convalidated
        FROM pg_catalog.pg_constraint con JOIN rels r ON r.oid = con.conrelid
        LEFT JOIN pg_catalog.pg_class tc ON tc.oid = con.confrelid LEFT JOIN pg_catalog.pg_namespace tn ON tn.oid = tc.relnamespace
        WHERE con.contype IN ('p', 'u', 'f') AND con.conparentid = 0
        UNION ALL
        SELECT i.indrelid::int8, ic.relname::text, 'i',
               ARRAY(SELECT a.attname::text FROM unnest(i.indkey::int2[]) WITH ORDINALITY k(attnum, ord)
                     JOIN pg_catalog.pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
                     WHERE k.ord <= i.indnkeyatts ORDER BY k.ord),
               NULL, NULL, NULL, NULL::boolean
        FROM pg_catalog.pg_index i JOIN rels r ON r.oid = i.indrelid JOIN pg_catalog.pg_class ic ON ic.oid = i.indexrelid
        WHERE i.indisunique AND NOT i.indisprimary AND i.indisvalid AND i.indpred IS NULL AND i.indexprs IS NULL
          AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_constraint x WHERE x.conindid = i.indexrelid AND x.contype IN ('p', 'u', 'x'))
        ORDER BY 1, 2""",
    "routines, triggers and indexes": RELS + f"""
        SELECT kind, schema, name, detail FROM (
            SELECT CASE p.prokind WHEN 'p' THEN 'procedure' WHEN 'a' THEN 'aggregate' WHEN 'w' THEN 'window function' ELSE 'function' END AS kind,
                   n.nspname::text AS schema, p.proname::text AS name, pg_catalog.pg_get_function_identity_arguments(p.oid) AS detail
            FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace WHERE {SYSTEM}
            UNION ALL
            SELECT 'trigger', r.nspname::text, t.tgname::text, r.relname::text
            FROM pg_catalog.pg_trigger t JOIN rels r ON r.oid = t.tgrelid WHERE NOT t.tgisinternal
            UNION ALL
            SELECT 'index', r.nspname::text, ic.relname::text, r.relname::text
            FROM pg_catalog.pg_index i JOIN rels r ON r.oid = i.indrelid JOIN pg_catalog.pg_class ic ON ic.oid = i.indexrelid
        ) m ORDER BY kind, schema, name, detail LIMIT 10001""",
    "lookup by name": """WITH rels AS (
            SELECT c.oid, n.nspname, c.relname, c.relkind, c.relhassubclass
            FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN unnest(ARRAY['public']::text[], ARRAY['x']::text[]) AS w(s, r) ON n.nspname = w.s AND c.relname = w.r
            WHERE c.relkind IN ('r', 'v', 'm', 'f', 'p'))
        SELECT oid::int8, nspname::text, relname::text, relkind::text, relhassubclass FROM rels""",
}


def digest(value):
    """DataIntent's per-value digest (PostgresReads.Digests): 16 hex digits of a SHA-256 of length and head."""
    length = f"octet_length(convert_to(({value})::text, 'UTF8'))"
    head = f"convert_to(left(({value})::text, 64), 'UTF8')"
    return (f"CASE WHEN ({value}) IS NULL THEN '----------------' ELSE "
            f"left(encode(sha256(convert_to('Text:' || {length}::text || ':', 'UTF8') || {head}), 'hex'), 16) END")


def reads(table, columns, numeric):
    table_sql, first = f'public."{table}"', f'x."{columns[0]}"'
    listed = ", ".join(f'x."{c}"' for c in columns)
    number = f'x."{numeric}"' if numeric else "1"
    return {
        "keyset page read": f"SELECT {listed} FROM {table_sql} AS x WHERE ({first})::text COLLATE \"C\" > '' "
                            f"ORDER BY ({first})::text COLLATE \"C\", x.ctid LIMIT 51",
        "full-row page with sha256 digests": f"SELECT p.c0, {digest('p.b0')} FROM (SELECT {first} AS c0, {first} AS b0 "
                                             f"FROM {table_sql} AS x ORDER BY x.tableoid, x.ctid LIMIT 51 OFFSET 1) AS p",
        "count with ILIKE ... ESCAPE": f"SELECT count(*) FROM {table_sql} AS x WHERE ({first})::text ILIKE '%a%' ESCAPE '\\'",
        "aggregates": f"SELECT sum(({number})::numeric), min(({first})::text COLLATE \"C\"), max({number}), "
                      f"round(abs(sum(({number})::numeric)), 2), trim_scale(1.500::numeric), count(*) FROM {table_sql} AS x",
        "text functions": f"SELECT btrim(({first})::text), replace(({first})::text, 'a', 'b'), concat(({first})::text, 'x'), "
                          f"left(({first})::text, 10), substring(convert_to(({first})::text, 'UTF8') from 1 for 8), "
                          f"octet_length(convert_to(({first})::text, 'UTF8'))::int8 FROM {table_sql} AS x LIMIT 5",
        "extract and arrays": f"SELECT extract(year from now())::int8, array_agg(v ORDER BY v) "
                              f"FROM (SELECT ({first})::text AS v FROM {table_sql} AS x LIMIT 5) AS s",
        "locator read": f"SELECT {first} FROM {table_sql} AS x WHERE x.ctid = '(0,1)'::tid LIMIT 2",
        "key join by unnest": f"SELECT {first} FROM {table_sql} AS x JOIN unnest(ARRAY['1']::text[]) WITH ORDINALITY AS k(c0, ord) "
                              f"ON ({first})::text = k.c0 ORDER BY k.ord",
    }


@pytest.mark.parametrize("database", CONSUMER_DATABASES)
def test_dataintent_catalog_and_reads_run_as_demo(database):
    if database not in sample_databases():
        pytest.skip(f"{database} is not on this server")
    with connect(database) as connection:
        connection.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("ROLLBACK")
        table, columns, numeric = first_table(connection)
        refused = {label: state for label, sql in {**CATALOG, **reads(table, columns, numeric)}.items()
                   if (state := sqlstate(connection, sql))}
    assert refused == {}, refused


def test_dataintent_database_listing_runs_as_demo():
    with connect("megasamples") as connection:
        assert sqlstate(connection, """
            SELECT d.datname::text, d.datallowconn AND pg_catalog.has_database_privilege(d.oid, 'CONNECT'),
                   CASE WHEN d.datallowconn AND pg_catalog.has_database_privilege(d.oid, 'CONNECT') THEN pg_catalog.pg_database_size(d.oid) END,
                   pg_catalog.shobj_description(d.oid, 'pg_database')
            FROM pg_catalog.pg_database d WHERE NOT d.datistemplate ORDER BY 1 LIMIT 1001""") is None


def test_dataintent_snapshot_export_and_import_run_as_demo():
    database = next(d for d in CONSUMER_DATABASES + tuple(sample_databases()) if d in sample_databases())
    with connect(database) as anchor, connect(database) as reader:
        anchor.execute("SET statement_timeout = 30000; SET idle_in_transaction_session_timeout = 600000; "
                       "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        snapshot = anchor.execute("SELECT pg_catalog.pg_export_snapshot(), pg_catalog.pg_current_snapshot()::text, "
                                  "pg_catalog.pg_postmaster_start_time()::text, current_database()").fetchone()
        reader.execute(f"BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET TRANSACTION SNAPSHOT '{snapshot[0]}'; "
                       "SET LOCAL statement_timeout = 30000")
        table = first_table(reader)[0]
        reader.execute(f'SELECT count(*) FROM public."{table}"').fetchone()
        reader.execute("COMMIT")
        anchor.execute("ROLLBACK")


# --- the account: PostgreSQL's own read role, and no write ------------------------------------------------

def test_demo_holds_pg_read_all_data_and_no_role_that_writes():
    with connect("megasamples") as connection:
        assert connection.execute("SELECT pg_has_role('demo', 'pg_read_all_data', 'USAGE')").fetchone() == (True,)
        roles = [row[0] for row in connection.execute(
            "SELECT r.rolname FROM pg_roles r WHERE pg_has_role('demo', r.oid, 'USAGE') ORDER BY 1")]
        assert "pg_write_all_data" not in roles and "admin" not in roles and "postgres" not in roles, roles
        attributes = connection.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles "
                                        "WHERE rolname = 'demo'").fetchone()
        assert attributes == (False, False, False, False)


@pytest.mark.parametrize("privilege", ["INSERT", "UPDATE", "DELETE", "TRUNCATE"])
def test_no_sample_table_is_writable_by_demo_directly_or_through_a_role(privilege):
    for database in sample_databases():
        with connect(database) as connection:
            writable = [row[0] for row in connection.execute(
                "SELECT c.oid::regclass::text FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relkind IN ('r', 'p') AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
                f"AND has_table_privilege('demo', c.oid, '{privilege}')")]
            assert writable == [], (database, privilege, writable[:5])


def test_no_default_privilege_gives_demo_a_write():
    for database in sample_databases():
        with connect(database) as connection:
            granted = connection.execute("""
                SELECT d.defaclrole::regrole::text, a.privilege_type
                FROM pg_default_acl d, aclexplode(d.defaclacl) a
                WHERE a.privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
                  AND (a.grantee = 0 OR pg_has_role('demo', a.grantee, 'USAGE'))""").fetchall()
            assert granted == [], (database, granted)


def test_demo_reads_every_sample_table():
    for database in sample_databases():
        with connect(database) as connection:
            tables = [row[0] for row in connection.execute(
                "SELECT format('%I.%I', n.nspname, c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relkind IN ('r', 'p') AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
                "AND n.nspname !~ '^pg_' ORDER BY 1")]
            assert tables, database
            refused = {t: s for t in tables if (s := sqlstate(connection, f"SELECT count(*) FROM {t}"))}
            assert refused == {}, (database, refused)


def test_demo_writes_are_refused_with_their_native_sqlstate():
    for database in sample_databases():
        with connect(database) as connection:
            table, columns, _ = first_table(connection)
            target, column = f'public."{table}"', f'"{columns[0]}"'
            states = {
                "INSERT": sqlstate(connection, f"INSERT INTO {target} DEFAULT VALUES"),
                "UPDATE": sqlstate(connection, f"UPDATE {target} SET {column} = {column}"),
                "DELETE": sqlstate(connection, f"DELETE FROM {target}"),
                "TRUNCATE": sqlstate(connection, f"TRUNCATE {target}"),
                "CREATE TABLE": sqlstate(connection, "CREATE TABLE public.demo_probe (i int)"),
                "DROP": sqlstate(connection, f"DROP TABLE {target}"),
            }
            assert states == {statement: "42501" for statement in states}, (database, states)


def test_demo_may_create_its_own_large_object():
    """PostgreSQL's default: a large object demo creates is its own, and changes no sample."""
    with connect(sample_databases()[0]) as connection:
        assert sqlstate(connection, "BEGIN; SELECT lo_create(0); ROLLBACK") is None


def test_demo_keeps_the_engine_defaults_for_reading():
    """TEMPORARY and EXECUTE on built-in functions are PostgreSQL's defaults, and a reader's tools rely on them."""
    with connect(sample_databases()[0]) as connection:
        assert sqlstate(connection, "CREATE TEMP TABLE demo_scratch (i int)") is None
        assert sqlstate(connection, "SELECT sha256('x'::bytea), 'a' ILIKE 'a' ESCAPE '\\', md5('x')") is None
