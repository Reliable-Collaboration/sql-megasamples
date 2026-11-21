"""PostgreSQL gate cases using SQL and stock clients."""

from contextlib import ExitStack

from native import checked, denied, require, same

TEMPLATE = "dl077_gate_start"
TWIN = "dl077_gate_twin"
COPY = "dl077_gate_copy"
CHECKSUM = "SELECT md5(string_agg(id::text || ':' || payload, ',' ORDER BY id)) FROM gate_data"


def value(target, sql, database="postgres", user="postgres", key="postgres"):
    return checked(target.pg(sql, database, user, key))


def fixture(target, key="postgres", closed=True):
    value(target, f"CREATE DATABASE {TWIN} TEMPLATE template0", key=key)
    value(target, """
        CREATE ROLE gate_reader LOGIN;
        CREATE ROLE gate_owner LOGIN CREATEDB;
        CREATE ROLE gate_group;
        CREATE ROLE gate_writer LOGIN;
        GRANT gate_group TO gate_reader;
    """, key=key)
    value(target, """
        CREATE TABLE gate_data (id integer PRIMARY KEY, payload text);
        INSERT INTO gate_data VALUES (1, 'one'), (2, 'two');
        CREATE SEQUENCE gate_sequence;
        CREATE SCHEMA gate_schema;
        CREATE VIEW gate_view AS SELECT * FROM gate_data;
        GRANT USAGE ON SCHEMA gate_schema TO gate_group;
        GRANT SELECT ON gate_data, gate_view TO gate_group;
        GRANT UPDATE ON gate_data TO pg_database_owner;
        GRANT USAGE ON gate_sequence TO pg_database_owner;
    """, TWIN, key=key)
    connection_option = "ALLOW_CONNECTIONS false" if closed else ""
    value(target, f"CREATE DATABASE {TEMPLATE} TEMPLATE {TWIN} IS_TEMPLATE true {connection_option}", key=key)


def closed_to_every_login(target):
    fixture(target)
    accounts = value(target, "SELECT rolname FROM pg_roles WHERE rolcanlogin ORDER BY 1").splitlines()
    for user in accounts:
        denied(target.pg("SELECT current_user", TEMPLATE, user), "55000")
    remote = target.pg_network("SELECT current_user", TEMPLATE, "postgres", "network")
    require(remote.returncode and "is not currently accepting connections" in remote.stderr,
            "network client did not report a closed database")
    value(target, f"ALTER DATABASE {TEMPLATE} ALLOW_CONNECTIONS true")
    same(value(target, "SELECT current_user", TEMPLATE), "postgres")


def concurrent_copies(target):
    from clients import Client, until

    fixture(target)
    same(value(target, "SELECT rolcreatedb AND NOT (rolsuper OR rolcreaterole OR rolreplication OR rolbypassrls) FROM pg_roles WHERE rolname='gate_owner'"), "t")
    denied(target.pg(f"CREATE DATABASE {COPY} TEMPLATE {TWIN}", user="gate_owner"), "42501")
    value(target, f"ALTER DATABASE {TEMPLATE} IS_TEMPLATE false")
    value(target, f"DROP DATABASE {TEMPLATE}")
    value(target, """
        INSERT INTO gate_data
        SELECT i, repeat(md5(i::text), 15) FROM generate_series(3, 300000) AS i;
        CHECKPOINT;
    """, TWIN)
    value(target, f"CREATE DATABASE {TEMPLATE} TEMPLATE {TWIN} IS_TEMPLATE true ALLOW_CONNECTIONS false")

    with ExitStack() as stack:
        sessions = [stack.enter_context(Client(target, target.psql_args(user="gate_owner")))
                    for _ in range(2)]
        for suffix, session in zip(("a", "b"), sessions):
            session.send(f"SET application_name='dl077-g1b-{suffix}';")
            same(session.query("SELECT 1;"), "1")
        for suffix, session in zip(("a", "b"), sessions):
            session.send(f"CREATE DATABASE {COPY}_{suffix} TEMPLATE {TEMPLATE};")
        until(lambda: value(target, f"""
            SELECT count(*) FROM pg_stat_activity
            WHERE application_name LIKE 'dl077-g1b-%' AND state='active'
              AND query LIKE 'CREATE DATABASE {COPY}_%';
        """) == "2")
        for session in sessions:
            same(session.query("SELECT 1;"), "1")

    checksum = "SELECT count(*),bit_xor(hashtextextended(id::text || payload,0)) FROM gate_data"
    digest = value(target, checksum, TWIN)
    require(bool(digest), "the template twin yielded no checksum")
    for suffix in ("a", "b"):
        same(value(target, checksum, f"{COPY}_{suffix}"), digest)


def admin_cannot_change_template(target):
    fixture(target)
    value(target, "CREATE DATABASE gate_admin_owned OWNER admin")
    for statement in (
        "ALTER DATABASE {} ALLOW_CONNECTIONS false",
        "ALTER DATABASE {} RENAME TO gate_renamed",
        "COMMENT ON DATABASE {} IS 'changed'",
        "DROP DATABASE {}",
    ):
        denied(target.pg(statement.format(TEMPLATE), user="admin"), "42501")
    for statement in (
        "ALTER DATABASE gate_admin_owned ALLOW_CONNECTIONS false",
        "ALTER DATABASE gate_admin_owned RENAME TO gate_renamed",
        "COMMENT ON DATABASE gate_renamed IS 'changed'",
        "DROP DATABASE gate_renamed",
    ):
        value(target, statement, user="admin")


OBJECT_ACLS = """
    SELECT kind, name, owner, acl FROM (
      SELECT 'relation' AS kind, relname::text AS name,
             relowner::regrole::text AS owner, coalesce(relacl::text, '') AS acl
      FROM pg_class WHERE relname IN ('gate_data','gate_view','gate_sequence','gate_data_pkey')
      UNION ALL SELECT 'schema', nspname, nspowner::regrole::text, coalesce(nspacl::text, '')
      FROM pg_namespace WHERE nspname = 'gate_schema'
    ) AS objects ORDER BY 1, 2;
"""


def object_ownership_and_acls(target):
    fixture(target)
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}")
    expected = value(target, OBJECT_ACLS, TWIN)
    require(len(expected.splitlines()) == 5, "the catalog did not return all five fixture objects")
    same(value(target, OBJECT_ACLS, COPY), expected)
    value(target, "GRANT DELETE ON gate_data TO gate_group", TWIN)
    require(value(target, OBJECT_ACLS, TWIN) != value(target, OBJECT_ACLS, COPY),
            "control grant made the catalog comparison succeed")


def default_privileges(target):
    fixture(target, closed=False)
    value(target, "ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC", TEMPLATE)
    value(target, "ALTER DEFAULT PRIVILEGES FOR ROLE gate_owner GRANT SELECT ON TABLES TO gate_group", TEMPLATE)
    value(target, f"ALTER DATABASE {TEMPLATE} ALLOW_CONNECTIONS false")
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}")
    sql = """
        SELECT defaclrole::regrole, defaclnamespace, defaclobjtype, defaclacl
        FROM pg_default_acl ORDER BY 1, 2, 3;
    """
    value(target, f"ALTER DATABASE {TEMPLATE} ALLOW_CONNECTIONS true")
    original = value(target, sql, TEMPLATE)
    require(len(original.splitlines()) == 2, "expected two default-privilege catalog rows")
    same(value(target, sql, COPY), original)
    value(target, "ALTER DEFAULT PRIVILEGES FOR ROLE gate_owner GRANT DELETE ON TABLES TO gate_group", TEMPLATE)
    require(value(target, sql, TEMPLATE) != value(target, sql, COPY),
            "control grant made the default-privilege comparison succeed")


def extension_trigger(target):
    key = "postgres_pr14"
    fixture(target, key)
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}", key=key)
    installed = """
        SELECT count(*) FROM pg_extension e JOIN pg_depend d ON d.refobjid=e.oid
        JOIN pg_event_trigger t ON t.oid=d.objid
        WHERE e.extname='read_policy' AND d.classid='pg_event_trigger'::regclass
          AND d.refclassid='pg_extension'::regclass AND d.deptype='e';
    """
    same(value(target, installed, COPY, key=key), "1")
    value(target, "CREATE DATABASE gate_without_trigger TEMPLATE template0", key=key)
    value(target, "DROP EXTENSION IF EXISTS read_policy CASCADE", "gate_without_trigger", key=key)
    for db, expected in ((COPY, "0"), ("gate_without_trigger", "1")):
        value(target, "ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC", db, key=key)
        value(target, "CREATE FUNCTION gate_f() RETURNS int LANGUAGE sql AS 'SELECT 1'", db, key=key)
        same(value(target, """
            SELECT count(*) FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,
            acldefault('f', p.proowner))) a WHERE p.proname='gate_f' AND a.grantee=0
            AND a.privilege_type='EXECUTE';
        """, db, key=key), expected)


def database_metadata(target):
    fixture(target)
    value(target, f"GRANT CONNECT ON DATABASE {TEMPLATE} TO gate_group")
    value(target, f"COMMENT ON DATABASE {TEMPLATE} IS 'template comment'")
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}", user="gate_owner")
    sql = """
        SELECT datdba::regrole, coalesce(shobj_description(oid, 'pg_database'), ''),
            EXISTS (SELECT FROM aclexplode(coalesce(datacl, acldefault('d',datdba))) a
              WHERE a.grantee='gate_group'::regrole AND a.privilege_type='CONNECT')
        FROM pg_database WHERE datname='{}';
    """
    same(value(target, sql.format(TEMPLATE)), "postgres|template comment|t")
    same(value(target, sql.format(COPY)), "gate_owner||f")


def database_owner_grant(target):
    fixture(target)
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}", user="gate_owner")
    value(target, f"GRANT UPDATE ON gate_data TO gate_writer", TWIN)
    value(target, "UPDATE gate_data SET payload = 'edited'", COPY, "gate_owner")
    same(value(target, "SELECT count(*) FROM gate_data WHERE payload='edited'", COPY), "2")
    for user in ("gate_reader", "gate_writer"):
        denied(target.pg("UPDATE gate_data SET payload='denied'", COPY, user), "42501")
    denied(target.pg("UPDATE gate_data SET payload='denied'", TWIN, "gate_owner"), "42501")


def database_comment(target):
    fixture(target)
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}", user="gate_owner")
    value(target, f"COMMENT ON DATABASE {TEMPLATE} IS 'megasamples-template/1 fixture'")
    sql = f"SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='{TEMPLATE}'"
    same(value(target, sql, "megasamples", "gate_reader"), "megasamples-template/1 fixture")
    denied(target.pg(f"COMMENT ON DATABASE {TEMPLATE} IS 'changed'", user="gate_owner"), "42501")
    value(target, f"COMMENT ON DATABASE {COPY} IS 'megasamples-copy/1 fixture'", user="gate_owner")
    same(value(target, sql.replace(TEMPLATE, COPY), "megasamples", "gate_reader"), "megasamples-copy/1 fixture")


def database_oid(target):
    fixture(target, closed=False)
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}")
    sql = "SELECT oid FROM pg_database WHERE datname='{}'"
    first = value(target, sql.format(COPY))
    untouched = value(target, sql.format(TEMPLATE))
    require(first.isdecimal() and untouched.isdecimal(), "catalog returned no OID")
    value(target, f"DROP DATABASE {COPY}")
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}")
    second = value(target, sql.format(COPY))
    require(second.isdecimal() and first != second, "same-named replacement kept the old OID")
    target.restart("postgres", lambda: target.pg("SELECT 1"))
    same(value(target, sql.format(TEMPLATE)), untouched)


def closing_transaction(target):
    fixture(target)
    value(target, "CREATE TABLE gate_operations(phase text); INSERT INTO gate_operations VALUES ('built')")
    for end, phase in (("ROLLBACK", "built"), ("COMMIT", "closed")):
        value(target, f"""
            BEGIN;
            ALTER DATABASE {TWIN} ALLOW_CONNECTIONS false;
            UPDATE gate_operations SET phase='closed';
            {end};
        """)
        same(value(target, "SELECT phase FROM gate_operations"), phase)
        result = target.pg("SELECT 1", TWIN)
        if end == "ROLLBACK":
            same(checked(result), "1")
        else:
            denied(result, "55000")


def swap_transaction(target):
    fixture(target)
    value(target, f"CREATE DATABASE {COPY} TEMPLATE {TEMPLATE}")
    value(target, f"REVOKE CONNECT ON DATABASE {COPY} FROM PUBLIC")
    value(target, "CREATE TABLE gate_operations(phase text); INSERT INTO gate_operations VALUES ('closed')")
    value(target, "UPDATE gate_data SET payload='new data'", COPY)
    old_oid, new_oid = [
        value(target, f"SELECT oid FROM pg_database WHERE datname='{name}'") for name in (TWIN, COPY)
    ]
    for end in ("ROLLBACK", "COMMIT"):
        value(target, f"""
            BEGIN;
            ALTER DATABASE {TWIN} RENAME TO gate_old;
            ALTER DATABASE {COPY} RENAME TO {TWIN};
            GRANT CONNECT ON DATABASE {TWIN} TO gate_reader;
            UPDATE gate_operations SET phase='swapped';
            {end};
        """)
        catalog = value(target, f"""
            SELECT datname, oid, EXISTS (
                SELECT FROM aclexplode(coalesce(datacl, acldefault('d',datdba))) a
                WHERE a.grantee='gate_reader'::regrole AND a.privilege_type='CONNECT'
            ) FROM pg_database WHERE datname IN ('{TWIN}','{COPY}','gate_old') ORDER BY 1;
        """)
        if end == "ROLLBACK":
            same(catalog, f"{COPY}|{new_oid}|f\n{TWIN}|{old_oid}|f")
            same(value(target, "SELECT phase FROM gate_operations"), "closed")
            denied(target.pg("SELECT 1", COPY, "gate_reader"), "42501")
        else:
            same(catalog, f"{TWIN}|{new_oid}|t\ngate_old|{old_oid}|f")
            same(value(target, "SELECT phase FROM gate_operations"), "swapped")
            same(value(target, "SELECT DISTINCT payload FROM gate_data", TWIN, "gate_reader"), "new data")


def candidate_floor(target):
    key = "postgres_pr14"
    value(target, "CREATE ROLE gate_fresh LOGIN", key=key)
    denied(target.pg("SELECT 1 = 1", user="gate_fresh", key=key), "42501")
    same(value(target, "SELECT 1 = 1", user="demo", key=key), "t")


def native_role_change(target):
    from hook_cases import SEED_PASSWORD

    value(target, "CREATE ROLE gate_reader LOGIN; CREATE ROLE gate_other LOGIN")
    value(target, SEED_PASSWORD)
    exists = "SELECT rolpassword IS NOT NULL FROM pg_authid WHERE rolname='gate_reader'"
    same(value(target, exists), "t")
    denied(target.pg("ALTER ROLE gate_other PASSWORD NULL", user="gate_reader"), "42501")
    value(target, "ALTER ROLE gate_reader PASSWORD NULL", user="gate_reader")
    same(value(target, exists), "f")


def revoke_without_owner(target):
    value(target, """
        CREATE ROLE gate_other;
        CREATE ROLE gate_creator LOGIN CREATEDB;
        GRANT gate_other TO gate_creator WITH INHERIT FALSE, SET TRUE;
    """)
    value(target, "CREATE DATABASE gate_acl OWNER gate_other", user="gate_creator")
    measure = """
        SELECT privilege_type FROM pg_database d,
          LATERAL aclexplode(coalesce(datacl,acldefault('d',datdba))) AS a
        WHERE d.datname='gate_acl' AND a.grantee=0 ORDER BY 1;
    """
    original = value(target, measure)
    same(original, "CONNECT\nTEMPORARY")
    sql = "REVOKE CONNECT, TEMPORARY ON DATABASE gate_acl FROM PUBLIC"
    value(target, sql, user="gate_creator")
    same(value(target, measure), original)
    value(target, "SET ROLE gate_other; " + sql, user="gate_creator")
    same(value(target, measure), "")


CASES = {
    "G-1a": closed_to_every_login,
    "G-1b": concurrent_copies,
    "G-1c": admin_cannot_change_template,
    "G-2a": object_ownership_and_acls,
    "G-2b": default_privileges,
    "G-2c": extension_trigger,
    "G-2d": database_metadata,
    "G-23": database_owner_grant,
    "G-8a": database_comment,
    "G-24p": database_oid,
    "G-3a": closing_transaction,
    "G-3b": swap_transaction,
    "G-5a": candidate_floor,
    "G-6a": native_role_change,
    "G-4a": revoke_without_owner,
}


def locks_are_database_local(target):
    from clients import Client

    with Client(target, target.psql_args("megasamples")) as owner:
        same(owner.query("SELECT pg_try_advisory_lock(415077);"), "t")
        same(value(target, "SELECT pg_try_advisory_lock(415077)", "megasamples"), "f")
        same(value(target, "SELECT pg_try_advisory_lock(415077)", "postgres"), "t")


def create_keeps_session_lock(target):
    from clients import kill_managed_client, managed_client, until

    # A real file copy must be in progress before the client is killed.
    fixture(target, closed=False)
    value(target, """
        CREATE TABLE gate_bulk AS
        SELECT i, md5(i::text) || md5((i+1)::text) || md5((i+2)::text) AS payload
        FROM generate_series(1, 5000000) i;
        CHECKPOINT;
    """, TEMPLATE)
    value(target, f"ALTER DATABASE {TEMPLATE} ALLOW_CONNECTIONS false")
    observer = "SELECT pg_try_advisory_lock(415077)"
    same(value(target, observer), "t")
    with managed_client(target, target.psql_args()) as owner:
        same(owner.query("SELECT pg_try_advisory_lock(415077);"), "t")
        value(target, "SELECT pg_stat_clear_snapshot()")
        owner.send(f"CREATE DATABASE {COPY} WITH TEMPLATE {TEMPLATE} STRATEGY FILE_COPY;")
        until(lambda: value(target, f"""
            SELECT count(*) FROM pg_stat_activity
            WHERE query LIKE 'CREATE DATABASE {COPY} WITH TEMPLATE%'
              AND state='active';
        """) == "1")
        kill_managed_client(target, target.container("postgres"))
        same(value(target, observer), "f")
        until(lambda: value(target, observer) == "t", seconds=180)
    same(value(target, f"SELECT count(*) FROM pg_database WHERE datname='{COPY}'"), "1")


def connected_drop(target):
    from clients import Client

    value(target, "CREATE DATABASE gate_drop")
    with Client(target, target.psql_args("gate_drop")) as client:
        same(client.query("SELECT current_database();"), "gate_drop")
        denied(target.pg("DROP DATABASE gate_drop"), "55006")
    value(target, "DROP DATABASE gate_drop")


def closing_keeps_open_sessions(target):
    from clients import Client

    value(target, "CREATE DATABASE gate_door")
    with Client(target, target.psql_args("gate_door", "demo")) as client:
        backend = client.query("SELECT pg_backend_pid();")
        require(backend.isdecimal(), "failed to identify demo's live session")
        value(target, "ALTER DATABASE gate_door ALLOW_CONNECTIONS false")
        same(client.query("SELECT current_user;"), "demo")
        denied(target.pg("SELECT 1", "gate_door", "demo"), "55000")
        same(value(target, f"SELECT pg_terminate_backend({backend}, 5000)"), "t")
        same(value(target, f"SELECT count(*) FROM pg_stat_activity WHERE pid={backend}"), "0")


def snapshot_probes(target):
    from clients import Client

    key = "postgres_pr14"
    db = "gate_snapshot"
    value(target, f"CREATE DATABASE {db} TEMPLATE template0", key=key)
    value(target, """
        CREATE ROLE gate_reader LOGIN;
        CREATE TABLE gate_snapshot_data (value integer);
        INSERT INTO gate_snapshot_data VALUES (1);
        GRANT SELECT ON gate_snapshot_data TO gate_reader;
    """, db, key=key)
    value(target, r"""
        SELECT format('GRANT EXECUTE ON ROUTINE %s TO PUBLIC', p.oid::regprocedure)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname IN ('pg_catalog','information_schema')
          AND has_function_privilege('demo',p.oid,'EXECUTE') \gexec
    """, db, key=key)
    expressions = ("pg_export_snapshot()", "pg_current_snapshot()", "pg_database_size(oid)")
    for expression in expressions:
        denied(target.pg(
            f"SELECT {expression} FROM pg_database LIMIT 1", db, "gate_reader", key
        ), "42501")
    value(target, """
        GRANT EXECUTE ON FUNCTION
            pg_export_snapshot(), pg_current_snapshot(), pg_database_size(oid) TO PUBLIC;
    """, db, key=key)
    digest_sql = r"""
        SELECT format(
            'SELECT %L, md5(coalesce(string_agg(to_jsonb(t)::text, '''' ORDER BY to_jsonb(t)::text COLLATE "C"), '''')) FROM pg_catalog.%I t',
            relname, relname
        )
        FROM pg_class WHERE relnamespace='pg_catalog'::regnamespace AND relkind='r'
        ORDER BY relname \gexec
    """
    with Client(target, target.psql_args(db, "gate_reader", key)) as exporter:
        exporter.send("SET application_name='dl077-exporter'; BEGIN ISOLATION LEVEL REPEATABLE READ;")
        observe_xid = """
            SELECT coalesce(backend_xid::text, 'none') FROM pg_stat_activity
            WHERE application_name='dl077-exporter' AND datname='gate_snapshot';
        """
        snapshot = None
        for expression in expressions:
            # A round trip after BEGIN also ensures the observer can see the open client.
            same(exporter.query("SELECT 1;"), "1")
            same(value(target, observe_xid, key=key), "none")
            before = value(target, digest_sql, db, key=key)
            observed = exporter.query(f"SELECT {expression} FROM pg_database LIMIT 1;")
            require(bool(observed), f"{expression} returned no value")
            if expression == "pg_export_snapshot()":
                snapshot = observed
            same(value(target, observe_xid, key=key), "none")
            same(value(target, digest_sql, db, key=key), before)
        require(snapshot and all(c in "0123456789ABCDEF-" for c in snapshot),
                "snapshot identifier did not have the expected form")
        value(target, "UPDATE gate_snapshot_data SET value=2", db, key=key)
        same(value(target, f"""
            BEGIN ISOLATION LEVEL REPEATABLE READ;
            SET TRANSACTION SNAPSHOT '{snapshot}';
            SELECT value FROM gate_snapshot_data;
            ROLLBACK;
        """, db, "gate_reader", key), "1")


def trigger_runs_as_writer(target):
    key = "postgres_pr14"
    db = "gate_writer"
    value(target, f"CREATE DATABASE {db} TEMPLATE template0", key=key)
    value(target, """
        CREATE ROLE gate_writer LOGIN;
        CREATE TABLE gate_data (probe_value text);
        CREATE FUNCTION gate_trigger() RETURNS trigger LANGUAGE plpgsql AS $body$
        BEGIN
            NEW.probe_value := current_setting('application_name');
            RETURN NEW;
        END
        $body$;
        CREATE TRIGGER gate_insert BEFORE INSERT ON gate_data
            FOR EACH ROW EXECUTE FUNCTION gate_trigger();
        GRANT INSERT ON gate_data TO gate_writer;
        REVOKE EXECUTE ON FUNCTION current_setting(text) FROM PUBLIC;
    """, db, key=key)
    write = "SET application_name = 'declared-writer'; INSERT INTO gate_data VALUES ('before')"
    result = target.pg(write, db, "gate_writer", key)
    denied(result, "42501")
    require("current_setting" in result.stderr, "trigger failed on a different routine")
    same(value(target, "SELECT count(*) FROM gate_data", db, key=key), "0")
    value(target, "GRANT EXECUTE ON FUNCTION current_setting(text) TO gate_writer", db, key=key)
    value(target, write, db, "gate_writer", key)
    same(value(target, "SELECT probe_value FROM gate_data", db, key=key), "declared-writer")


def null_password(target):
    for user in ("admin", "postgres"):
        for route in ("network", "published"):
            same(checked(target.pg_network("SELECT current_user", "postgres", user, route)), user)
        value(target, f"ALTER ROLE {user} PASSWORD NULL")
        same(value(target, "SELECT current_user", user=user), user)
        for route in ("network", "published"):
            result = target.pg_network("SELECT current_user", "postgres", user, route)
            require(result.returncode and "password authentication failed" in result.stderr,
                    f"{user} through {route} did not report an authentication refusal")


CASES.update({
    "G-7a": create_keeps_session_lock,
    "G-7b": locks_are_database_local,
    "G-8b": connected_drop,
    "G-3c": closing_keeps_open_sessions,
    "G-5b": snapshot_probes,
    "G-5c": trigger_runs_as_writer,
    "G-35p": null_password,
})
