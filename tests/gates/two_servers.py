"""Gates whose assertion spans products or uses an isolated volume replacement."""

from mysql import access_refused, grant_namespace, value as mysql_value
from native import checked, denied, require, same
from postgres import value as pg_value


def proof_window(target):
    pg_value(target, """
        CREATE ROLE gate_owner LOGIN CREATEDB;
        CREATE ROLE gate_other_owner LOGIN CREATEDB;
        CREATE ROLE gate_declared LOGIN;
        CREATE DATABASE lab_gate_123456789abc OWNER gate_owner;
        COMMENT ON DATABASE lab_gate_123456789abc IS 'megasamples-copy/1 fixture';
    """)
    oid_query = """
        SELECT oid FROM pg_database WHERE datname='lab_gate_123456789abc'
            AND shobj_description(oid,'pg_database')='megasamples-copy/1 fixture';
    """
    first_oid = pg_value(target, oid_query)
    require(first_oid.isdecimal(), "proof read did not find the original PostgreSQL OID")
    for user in ("gate_other_owner", "gate_declared", "demo"):
        denied(target.pg("DROP DATABASE lab_gate_123456789abc", user=user), "42501")
        denied(target.pg("CREATE DATABASE lab_gate_123456789abc", user=user),
               "42P04" if user == "gate_other_owner" else "42501")
        same(pg_value(target, oid_query), first_oid)
    pg_value(target, "DROP DATABASE lab_gate_123456789abc; CREATE DATABASE lab_gate_123456789abc",
             user="gate_owner")
    same(pg_value(target, oid_query), "")

    grant_namespace(target, "gate_owner", "lab")
    grant_namespace(target, "gate_other_owner", "other")
    mysql_value(target, "CREATE USER 'gate_declared'@'localhost'")
    mysql_value(target, "SET GLOBAL event_scheduler=OFF")
    mysql_value(target, """
        CREATE DATABASE lab_gate_123456789abc;
        CREATE EVENT lab_gate_123456789abc.megasamples_copy_abc ON SCHEDULE EVERY 1 DAY DISABLE DO SELECT 1;
    """, user="gate_owner")
    marker = """
        SELECT count(*) FROM information_schema.events
        WHERE event_schema='lab_gate_123456789abc' AND event_name='megasamples_copy_abc';
    """
    same(mysql_value(target, marker), "1")
    for user in ("gate_other_owner", "gate_declared", "demo"):
        for statement in (
            "DROP DATABASE lab_gate_123456789abc",
            "DROP EVENT lab_gate_123456789abc.megasamples_copy_abc",
            "CREATE DATABASE IF NOT EXISTS lab_gate_123456789abc",
        ):
            access_refused(target.mysql(statement, user=user))
        same(mysql_value(target, marker), "1")
    mysql_value(target, """
        DROP EVENT lab_gate_123456789abc.megasamples_copy_abc;
        DROP DATABASE lab_gate_123456789abc;
        CREATE DATABASE lab_gate_123456789abc;
    """, user="gate_owner")
    same(mysql_value(target, marker), "0")


CASES = {"G-24w": proof_window}


def replace(target, old, fresh, probe):
    from clients import until
    from native import capacity

    require(target.image(old) == target.image(fresh), "replacement uses a different baked image")
    old_id, new_id = target.container(old), target.container(fresh)
    require(old_id != new_id, "replacement refers to the same container")
    mount_names = {
        "postgres": "/var/lib/postgresql", "mysql": "/var/lib/mysql", "sqlite": "/shared",
    }
    mount = mount_names[old]
    old_mount, new_mount = target.mounts(old).get(mount), target.mounts(fresh).get(mount)
    require(old_mount and new_mount and old_mount != new_mount,
            "replacement requires a separate engine data mount")
    capacity()
    checked(target.podman("stop", old_id, timeout=180))
    checked(target.podman("start", new_id, timeout=180))
    until(lambda: probe().returncode == 0, seconds=180)


def volume_identities(target):
    import re
    import uuid

    reference = uuid.uuid4().hex
    pg_value(target, f"""
        CREATE TABLE megasamples_identity(value text);
        INSERT INTO megasamples_identity VALUES ('{reference}');
    """, "megasamples")
    target.restart("postgres", lambda: target.pg("SELECT 1"))
    same(pg_value(target, "SELECT value FROM megasamples_identity", "megasamples"), reference)
    replace(target, "postgres", "postgres_replacement",
            lambda: target.pg("SELECT 1", key="postgres_replacement"))
    same(pg_value(target, "SELECT to_regclass('megasamples_identity') IS NULL",
                  "megasamples", key="postgres_replacement"), "t")

    image = target.image("mysql")
    checked(target.podman(
        "run", "--rm", "--pull=never", "--network=none", "--memory=2g",
        "--label", "org.sql-megasamples.gates.owner=" + target.owner,
        "--entrypoint", "sh", image, "-ec", "test ! -e /var/lib/mysql/auto.cnf",
        timeout=180,
    ))
    query = "SELECT @@server_uuid"
    first = mysql_value(target, query)
    require(re.fullmatch(r"[0-9a-f-]{36}", first), "missing initial MySQL server UUID")
    target.restart("mysql", lambda: target.mysql("SELECT 1"))
    same(mysql_value(target, query), first)
    replace(target, "mysql", "mysql_replacement",
            lambda: target.mysql("SELECT 1", key="mysql_replacement"))
    second = mysql_value(target, query, key="mysql_replacement")
    require(re.fullmatch(r"[0-9a-f-]{36}", second) and first != second, "fresh MySQL UUID did not change")

    old_sqlite = target.container("sqlite")
    sqlite = lambda key, command: target.podman("exec", target.container(key), "sh", "-ec", command)
    checked(sqlite("sqlite", f"printf %s {reference} > /shared/.dl077-volume"))
    target.restart("sqlite", lambda: sqlite("sqlite", "test -f /shared/.complete"))
    same(checked(sqlite("sqlite", "cat /shared/.dl077-volume")), reference)
    same(checked(target.podman("inspect", "--type", "container", "--format", "{{.Id}}",
                              old_sqlite)), old_sqlite)
    replace(target, "sqlite", "sqlite_replacement",
            lambda: sqlite("sqlite_replacement", "test -f /shared/.complete"))
    checked(sqlite("sqlite_replacement", "test ! -e /shared/.dl077-volume"))


def after_volume_replacement(target):
    from contextlib import ExitStack

    from clients import Client
    from space import mysql_fingerprint, pg_fingerprint

    old_pg, new_pg, ref_pg = ("postgres", "postgres_replacement", "postgres_reference")
    old_my, new_my, ref_my = ("mysql", "mysql_replacement", "mysql_reference")
    require(target.image(new_pg) == target.image(ref_pg), "reference PostgreSQL image differs")
    require(target.image(new_my) == target.image(ref_my), "reference MySQL image differs")
    expected_pg = pg_fingerprint(target, ref_pg)
    expected_my = mysql_fingerprint(target, ref_my)
    old_ports = (target.published_port(old_pg, "5432"), target.published_port(old_my, "3306"))
    pg_value(target, "CREATE DATABASE gate__new_1")
    archive = target.pg_restore_archive("gate__new_1")
    pg_value(target, "CREATE TABLE dl077_old_volume(id int); INSERT INTO dl077_old_volume VALUES (1)",
             "megasamples")
    mysql_value(target, """
        CREATE TABLE megasamples.gate_operations(id int PRIMARY KEY, epoch int);
        INSERT INTO megasamples.gate_operations VALUES (1,1);
    """)
    with ExitStack() as stack:
        sessions = []
        for role in ("copy", "coordinator", "reconciliation"):
            psql = stack.enter_context(Client(target, target.pg_network_args(
                "megasamples", "postgres", "published")))
            mysql = stack.enter_context(Client(target, target.mysql_network_args("root", "published")))
            same(psql.query("SELECT id FROM dl077_old_volume;"), "1")
            same(mysql.query("SELECT epoch FROM megasamples.gate_operations WHERE id=1;"), "1")
            print(f"{role}: both clients read the old volume")
            sessions.append((psql, mysql))
        replace(target, old_pg, new_pg, lambda: target.pg("SELECT 1", key=new_pg))
        replace(target, old_my, new_my, lambda: target.mysql("SELECT 1", key=new_my))
        require((target.published_port(new_pg, "5432"), target.published_port(new_my, "3306")) == old_ports,
                "replacement did not publish on the old ports")
        for number, (psql, mysql) in enumerate(sessions):
            for client, statement in (
                (psql, f"CREATE TABLE dl077_late_{number}(id int);"),
                (mysql, f"CREATE TABLE megasamples.dl077_late_{number}(id int);"),
            ):
                try:
                    client.send(statement)
                except BrokenPipeError:
                    print("old client reported a broken pipe after replacement")
    restore = target.podman(
        "exec", "-i", target.container(new_pg), "pg_restore", "-U", "postgres",
        "--dbname=gate__new_1", "--exit-on-error", stdin=archive,
        show_input=False,
    )
    require(restore.returncode and "gate__new_1" in restore.stderr
            and "does not exist" in restore.stderr, "late worker did not fail for the absent transient")
    stream = """
        SELECT GET_LOCK('dl077-worker', 0);
        SELECT IF(EXISTS(SELECT 1 FROM megasamples.gate_operations WHERE id=1 AND epoch=1),
                  1, JSON_EXTRACT('invalid json', '$'));
        CREATE TABLE megasamples.dl077_late_worker(id int);
    """
    denied(target.mysql(stream, key=new_my), "1146")
    same(pg_fingerprint(target, new_pg), expected_pg)
    same(mysql_fingerprint(target, new_my), expected_my)
    mysql_value(target, """
        SELECT GET_LOCK('dl077-worker', 0);
        CREATE TABLE megasamples.dl077_late_worker(id int);
        INSERT INTO megasamples.dl077_late_worker VALUES (42);
    """, key=new_my)
    require(mysql_fingerprint(target, new_my) != expected_my, "unfenced stream did not change a new volume")


CASES.update({"G-33a": volume_identities, "G-33b": after_volume_replacement})
