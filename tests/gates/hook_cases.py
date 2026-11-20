"""Native tests for the six prototype-only gate assertions."""

from native import checked, denied, require, same

KEY = "postgres_hook"
CATALOG = "SELECT datname FROM pg_database WHERE datname='{}'"
POLICY_PASSWORD = "ALTER ROLE gate_reader PASSWORD NULL"
POLICY_SETTINGS = "ALTER ROLE gate_reader SET work_mem TO '8MB'"
POLICY_DEFAULTS = "ALTER DEFAULT PRIVILEGES GRANT SELECT ON TABLES TO PUBLIC"
SEED_PASSWORD = """
    DO $test$
    DECLARE synthetic_verifier text;
    BEGIN
        SELECT rolpassword INTO STRICT synthetic_verifier FROM pg_authid WHERE rolname='demo';
        IF synthetic_verifier IS NULL THEN
            RAISE EXCEPTION 'scratch demo is missing its canary';
        END IF;
        EXECUTE format('ALTER ROLE gate_reader PASSWORD %L', synthetic_verifier);
    END $test$;
"""


def sql(target, text, user="postgres", key=KEY, database="postgres"):
    return target.pg(text, database=database, user=user, key=key)


def role_changes(target):
    seed = """
        CREATE ROLE gate_reader LOGIN;
        CREATE ROLE gate_admin CREATEROLE LOGIN;
        CREATE TABLE gate_data (value integer);
        INSERT INTO gate_data VALUES (42);
        GRANT SELECT ON gate_data TO gate_reader;
    """
    checked(sql(target, seed))
    checked(sql(target, SEED_PASSWORD))
    statements = (POLICY_PASSWORD, POLICY_SETTINGS, POLICY_DEFAULTS)
    same(checked(sql(target, "SELECT value FROM gate_data", "gate_reader")), "42")
    checked(sql(target, "CREATE ROLE gate_managed; ALTER ROLE gate_managed PASSWORD NULL", "gate_admin"))
    for statement in statements:
        result = sql(target, statement, "gate_reader")
        denied(result, "42501")
        require("gate prototype: role change" in result.stderr, "refusal came from a different rule")
    password_is_set = "SELECT rolpassword IS NOT NULL FROM pg_authid WHERE rolname='gate_reader'"
    same(checked(sql(target, password_is_set)), "t")
    # Run the same image with the prototype omitted from preload.
    control = "postgres_hook_unloaded"
    if target.image(KEY) != target.image(control):
        raise AssertionError("hook-on and hook-off controls use different images")
    checked(sql(target, seed, key=control))
    checked(sql(target, SEED_PASSWORD, key=control))
    for statement in statements:
        checked(sql(target, statement, "gate_reader", control))
    same(checked(sql(target, password_is_set, key=control)), "f")


def after_copy_error(target):
    before = target.pg_database_dirs(KEY)
    name = "gate_after_copy_error"
    result = sql(target, f"CREATE DATABASE {name} TEMPLATE template0")
    denied(result, "P0001")
    require("gate prototype: injected after CREATE DATABASE" in result.stderr,
            "the error was not injected after CREATE DATABASE")
    same(checked(sql(target, CATALOG.format(name))), "")
    after = target.pg_database_dirs(KEY)
    leaked = after - before
    require(len(leaked) == 1, f"expected one orphaned directory, observed {len(leaked)}")
    registered = checked(sql(target, "SELECT oid FROM pg_database ORDER BY 1")).splitlines()
    require(leaked.isdisjoint(registered), "new directory has a catalog row")
    checked(sql(target, "CREATE DATABASE gate_after_copy_control TEMPLATE template0"))
    oid = checked(sql(target, "SELECT oid FROM pg_database WHERE datname='gate_after_copy_control'"))
    same(target.pg_database_dirs(KEY) - after, {oid})


def namespace(target):
    checked(sql(target, """
        CREATE ROLE megasamples_copy_lab_owner;
        CREATE ROLE gate_lab LOGIN CREATEDB;
        CREATE ROLE gate_other LOGIN CREATEDB;
        GRANT megasamples_copy_lab_owner TO gate_lab WITH SET FALSE;
        CREATE DATABASE gate_start TEMPLATE template0 IS_TEMPLATE true ALLOW_CONNECTIONS false;
        COMMENT ON DATABASE gate_start IS 'megasamples-template/1 {"database":"gate"}';
    """))


def guarded(target, statement, reason):
    result = sql(target, statement, "gate_lab")
    denied(result, "42501")
    require(f"gate prototype: {reason}" in result.stderr, "refusal came from a different rule")


def destination(target):
    namespace(target)
    for name in ("lab2_gate_123456789abc", "outside_gate_123456789abc",
                 "lab_other_123456789abc", "lab_gate_123456789ab"):
        guarded(target, f"CREATE DATABASE {name} TEMPLATE gate_start", "destination")
    checked(sql(target, "CREATE DATABASE lab_gate_123456789abc TEMPLATE gate_start", "gate_lab"))


def source(target):
    namespace(target)
    checked(sql(target, """
        CREATE DATABASE gate_working;
        CREATE DATABASE lab_gate_000000000000;
        CREATE DATABASE x_start TEMPLATE template0 IS_TEMPLATE true ALLOW_CONNECTIONS false;
    """))
    for source_name in ("template0", "template1", "gate_working", "lab_gate_000000000000", "x_start"):
        guarded(target, f"CREATE DATABASE lab_gate_123456789abc TEMPLATE {source_name}", "source")
    checked(sql(target, "CREATE DATABASE lab_gate_123456789abc TEMPLATE gate_start", "gate_lab"))


def rename(target):
    namespace(target)
    checked(sql(target, "CREATE DATABASE lab_gate_123456789abc TEMPLATE gate_start", "gate_lab"))
    for name in ("lab_gate_000000000001", "outside_namespace"):
        guarded(target, f"ALTER DATABASE lab_gate_123456789abc RENAME TO {name}", "rename")
    checked(sql(target, "CREATE DATABASE gate_admin_owns", "admin"))
    checked(sql(target, "ALTER DATABASE gate_admin_owns RENAME TO gate_admin_renamed", "admin"))


def unaffected_creator(target):
    namespace(target)
    checked(sql(target, """
        CREATE DATABASE outside_namespace;
        CREATE DATABASE lab_gate_123456789abc;
        ALTER DATABASE outside_namespace RENAME TO gate_renamed;
    """, "gate_other"))
    same(checked(sql(target, """
        SELECT CASE WHEN shobj_description(oid, 'pg_database') IS NULL
                    THEN 'unmanaged' ELSE 'managed' END
        FROM pg_database WHERE datname='lab_gate_123456789abc';
    """)), "unmanaged")
    checked(sql(target, "GRANT megasamples_copy_lab_owner TO gate_other"))
    denied(sql(target, "CREATE DATABASE outside_control", "gate_other"), "42501")
    denied(sql(target, "ALTER DATABASE gate_renamed RENAME TO gate_rename_control",
               "gate_other"), "42501")


CASES = {
    "G-6b": role_changes,
    "G-4b": after_copy_error,
    "G-29a": destination,
    "G-29b": source,
    "G-29c": rename,
    "G-29d": unaffected_creator,
}
