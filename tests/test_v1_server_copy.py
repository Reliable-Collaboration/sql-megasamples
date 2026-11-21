"""TCP copy contract against a disposable server provisioned by the native suite."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def server():
    target = os.environ.get("DL077_TCP_COPY_TARGET")
    if not target:
        pytest.skip("requires an explicitly provisioned isolated TCP target")
    path = Path(target)
    assert path.stat().st_uid == os.getuid() and not path.stat().st_mode & 0o077
    config = json.loads(path.read_text())
    assert config["host"] == "127.0.0.1"
    assert config["marker"].startswith("dl077-v1-tcp-")
    if config["engine"] == "postgres":
        import psycopg

        with psycopg.connect(
            host=config["host"], port=config["port"], dbname="megasamples", user=config["owner"],
            password=Path(config["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
        ) as connection:
            observed = connection.execute("SHOW cluster_name").fetchone()[0]
        assert observed == config["marker"]
    elif config["engine"] == "mysql":
        import pymysql

        with pymysql.connect(
            host=config["host"], port=config["port"], database="megasamples", user=config["owner"],
            password=Path(config["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT marker FROM test_fixture_marker")
                assert cursor.fetchone() == (config["marker"],)
    return config


def removed_names(reply):
    return [item["name"] for item in reply["result"]["removed"]]


def copy_command(server, *args, status=0, stdin=False, fault=None):
    password = Path(server["password_file"]).read_text() if stdin else None
    password_args = ["--password-stdin"] if stdin else ["--password-file", server["password_file"]]
    cli = ["-m", "megasamples", "copy"]
    if fault:
        cli = [str(Path(__file__).parent / "gates" / "dl077_copy_fault.py"), server["engine"], *fault]
    result = subprocess.run(
        [sys.executable, *cli, *args, "--host", server["host"],
         "--port", str(server["port"]), "--user", server["owner"], *password_args],
        input=password, text=True, capture_output=True, timeout=45,
    )
    canary = Path(server["password_file"]).read_text().strip()
    assert canary not in result.stdout + result.stderr
    assert result.returncode == status, result.stdout + result.stderr
    assert len(result.stdout.splitlines()) == 1
    reply = json.loads(result.stdout)
    assert reply["volume"] == server["volume"] and reply["exit"] == status
    return reply


def native(server, sql, *, user=None, database="megasamples", parameters=()):
    auth = {"host": server["host"], "port": server["port"], "user": user or server["owner"],
            "password": Path(server["password_file"]).read_text().strip(), "connect_timeout": 5,
            "autocommit": True}
    if server["engine"] == "postgres":
        import psycopg
        with psycopg.connect(dbname=database, **auth) as connection:
            cursor = connection.execute(sql, parameters or None)
            return cursor.fetchall() if cursor.description else None
    import pymysql
    with pymysql.connect(database=database, **auth) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, parameters or None)
            return list(cursor.fetchall()) if cursor.description else None


def change_lock(server, name):
    """A second session holding the CLI's change lock for one copy name."""
    import hashlib
    if server["engine"] == "postgres":
        key = int.from_bytes(hashlib.sha256(("megasamples/copy/" + name).encode()).digest()[:8],
                             "big", signed=True)
        # The owner may only try the lock, as the CLI does; nothing else holds it here.
        return ("SELECT pg_catalog.pg_try_advisory_lock(%s::bigint)",
                "SELECT pg_catalog.pg_advisory_unlock(%s::bigint)", key)
    key = "megasamples:" + hashlib.sha256(name.encode()).hexdigest()[:48]
    return "SELECT GET_LOCK(%s, 10)", "SELECT RELEASE_LOCK(%s)", key


def session(server, database):
    password = Path(server["password_file"]).read_text().strip()
    if server["engine"] == "postgres":
        import psycopg
        return psycopg.connect(host=server["host"], port=server["port"], dbname=database,
                               user=server["owner"], password=password, connect_timeout=5, autocommit=True)
    import pymysql
    return pymysql.connect(host=server["host"], port=server["port"], database=database,
                           user=server["owner"], password=password, connect_timeout=5, autocommit=True)


def run_sql(connection, sql, parameters=()):
    if hasattr(connection, "execute"):
        cursor = connection.execute(sql, parameters or None)
        return cursor.fetchall() if cursor.description else None
    with connection.cursor() as cursor:
        cursor.execute(sql, parameters or None)
        return cursor.fetchall() if cursor.description else None


def hold_busy(server, name):
    """Keep a copy busy for its engine: a connected session, or an open metadata lock."""
    connection = session(server, name)
    if server["engine"] == "mysql":
        run_sql(connection, "BEGIN")
        run_sql(connection, "SELECT * FROM artist LIMIT 1")
    return connection


def test_drop_wait_is_one_deadline_across_the_lock_and_the_removal(server):
    import threading
    import time
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "deadline")["result"]
    target, proof = engine + ":" + row["name"], ("--identity", row["identity"])
    take, give, key = change_lock(server, row["name"])
    holder, busy = session(server, "megasamples"), hold_busy(server, row["name"])
    try:
        assert run_sql(holder, take, (key,))[0][0] in (1, True)
        threading.Timer(2, run_sql, (holder, give, (key,))).start()
        started = time.monotonic()
        reply = copy_command(server, "drop", target, *proof, "--wait", "4", status=6)
        elapsed = time.monotonic() - started
        assert reply["error"]["code"] == "busy"
        assert 3.5 <= elapsed < 5.5, elapsed
        assert copy_command(server, "show", target)["result"]["state"] == "ready"
    finally:
        busy.close()
        holder.close()
    assert copy_command(server, "drop", target, *proof)["result"]["state"] == "gone"


def test_mysql_drop_honours_an_explicit_wait_beyond_five_seconds(server):
    import threading
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    row = copy_command(server, "create", "mysql:chinook", "--prefix", "copy", "--label", "longwait")["result"]
    target, proof = "mysql:" + row["name"], ("--identity", row["identity"])
    busy = hold_busy(server, row["name"])
    try:
        threading.Timer(7, busy.close).start()
        assert copy_command(server, "drop", target, *proof, "--wait", "15")["result"]["state"] == "gone"
    finally:
        copy_command(server, "drop", target, *proof)


def test_drop_refuses_a_copy_whose_proof_changed(server):
    engine = server["engine"]
    admin = {"user": "dl077_fixture_admin"}
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "proof")["result"]
    name, proof = row["name"], ("--identity", row["identity"])
    target = engine + ":" + name
    if engine == "postgres":
        comment = 'COMMENT ON DATABASE "{}" IS \'megasamples-copy/1 {}\''
        native(server, comment.format(name, "0" * 32), **admin)
        restore = comment.format(name, row["identity"])
        exists = ("SELECT count(*) FROM pg_database WHERE datname=%s", "postgres")
    else:
        native(server, f"DROP EVENT `{name}`.`megasamples_copy_{row['identity']}`", **admin)
        restore = (f"CREATE EVENT `{name}`.`megasamples_copy_{row['identity']}` ON SCHEDULE AT "
                   "CURRENT_TIMESTAMP + INTERVAL 1 YEAR ON COMPLETION PRESERVE DISABLE DO SELECT 1")
        exists = ("SELECT count(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", "megasamples")
    try:
        assert copy_command(server, "show", target)["result"]["state"] == "inconsistent"
        assert copy_command(server, "drop", target, *proof, status=5)["error"]["code"] == "inconsistent"
        copy_command(server, "release", target, *proof, status=5)
        swept = copy_command(server, "sweep", engine, "--prefix", "copy")["result"]
        assert not any(item["name"] == name for item in swept["removed"])
        assert native(server, exists[0], user=admin["user"], database=exists[1], parameters=(name,))[0][0] == 1
    finally:
        native(server, restore, **admin)
    assert copy_command(server, "drop", target, *proof)["result"]["state"] == "gone"


def test_mysql_declared_reader_is_not_an_outside_grant(server):
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    readers = native(server, "SELECT User FROM mysql.db WHERE User='reader_b'", user="dl077_fixture_admin",
                     database="mysql")
    if not readers:
        pytest.skip("requires an image built with the declared copy reader reader_b")
    reply = copy_command(server, "create", "mysql:chinook", "--prefix", "copy", "--label", "declared")
    target = "mysql:" + reply["result"]["name"]
    proof = ("--identity", reply["result"]["identity"])
    try:
        assert reply["result"]["state"] == "ready" and reply["warnings"] == []
        shown = copy_command(server, "show", target)
        assert shown["result"]["state"] == "ready" and shown["warnings"] == []
    finally:
        copy_command(server, "drop", target, *proof)


def test_server_inventory_reports_unmanaged_names(server):
    engine = server["engine"]
    admin = {"user": "dl077_fixture_admin"}
    native(server, "CREATE DATABASE copy_scratch", **admin)
    try:
        listed = copy_command(server, "list", engine, "--prefix", "copy", stdin=True)["result"]["copies"]
        assert ("copy_scratch", "unmanaged") in [(row["name"], row["state"]) for row in listed]
        swept = copy_command(server, "sweep", engine, "--prefix", "copy", "--dry-run")["result"]
        assert any(item["copy"]["name"] == "copy_scratch" and item["reason"] == "unmanaged"
                   for item in swept["kept"])
    finally:
        native(server, "DROP DATABASE copy_scratch", **admin)


def test_server_sweep_recovers_expired_dropping_copy(server):
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy",
                       "--label", "dropping")["result"]
    name = row["name"]
    target = engine + ":" + name
    identity = ("--identity", row["identity"])
    copy_command(server, "release", target, *identity)
    if engine == "postgres":
        change = "jsonb_set(record, '{phase}', '\"dropping\"')"
    else:
        change = """JSON_SET(record, '$.phase', 'dropping')"""
    native(server, f"UPDATE copy_ledger_copy SET record={change} WHERE name=%s", parameters=(name,))
    try:
        assert copy_command(server, "show", target)["result"]["state"] == "dropping"
        preview = copy_command(server, "sweep", engine, "--prefix", "copy", "--dry-run")["result"]
        assert any(item["name"] == name for item in preview["removed"])
        assert copy_command(server, "show", target)["result"]["state"] == "dropping"
        swept = copy_command(server, "sweep", engine, "--prefix", "copy")["result"]
        assert any(item["name"] == name for item in swept["removed"])
        assert copy_command(server, "show", target)["result"]["state"] == "gone"
    finally:
        copy_command(server, "drop", target, *identity)


@pytest.mark.parametrize("when", ["before", "after"])
def test_lost_reservation_reply_retains_the_issued_identity(server, when):
    engine = server["engine"]
    label = "lost" + when
    reply = copy_command(server, "create", engine + ":chinook", "--prefix", "copy",
                         "--label", label, status=8, fault=("insert", when))
    error = reply["error"]
    assert error["code"] == "create-unsettled" and len(error["identity"]) == 32
    rows = copy_command(server, "list", engine, "--prefix", "copy", "--label", label)["result"]["copies"]
    if when == "before":
        assert rows == []
    else:
        assert [(row["identity"], row["state"]) for row in rows] == [(error["identity"], "stale")]
        copy_command(server, "drop", engine + ":" + rows[0]["name"], "--identity", error["identity"])


@pytest.mark.parametrize("when", ["before", "after"])
def test_lost_lease_reply_retains_the_supplied_identity(server, when):
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy",
                       "--label", "renew" + when)["result"]
    target = engine + ":" + row["name"]
    identity = ("--identity", row["identity"])
    try:
        reply = copy_command(server, "renew", target, *identity, "--lease", "7d", status=8,
                             fault=("change", when))
        assert reply["error"]["identity"] == row["identity"]
        latest = copy_command(server, "show", target)["result"]
        assert latest["revision"] == row["revision"] + (when == "after")
    finally:
        copy_command(server, "drop", target, *identity)


def test_postgres_copy_lifecycle_on_tcp(server):
    if server["engine"] != "postgres":
        pytest.skip("requires the PostgreSQL fixture")

    def command(*args, status=0):
        result = subprocess.run(
            [sys.executable, "-m", "megasamples", "copy", *args, "--host", server["host"],
             "--port", str(server["port"]), "--user", server["owner"],
             "--password-file", server["password_file"]],
            text=True, capture_output=True, timeout=45,
        )
        assert result.returncode == status, result.stdout + result.stderr
        assert len(result.stdout.splitlines()) == 1
        document = json.loads(result.stdout)
        assert document["volume"] == server["volume"]
        assert document["exit"] == status
        return document

    created = command("create", "postgres:chinook", "--prefix", "copy", "--label", "first")["result"]
    target = "postgres:" + created["name"]
    identity = ("--identity", created["identity"])
    assert created["state"] == "ready"
    assert command("show", target)["result"]["proof"]["oid"] > 0
    assert command("list", "postgres", "--prefix", "copy", "--label", "first")["result"]["copies"] == [created]
    command("renew", target, *identity, "--lease", "7d")
    assert created["name"] not in removed_names(command("sweep", "postgres", "--prefix", "copy"))
    command("release", target, *identity)
    assert created["name"] in removed_names(command("sweep", "postgres", "--prefix", "copy", "--dry-run"))
    assert command("show", target)["result"]["state"] == "ready"
    assert created["name"] in removed_names(command("sweep", "postgres", "--prefix", "copy"))
    command("drop", target, *identity)

    second = command("create", "postgres:chinook", "--prefix", "copy", "--label", "second")["result"]
    target = "postgres:" + second["name"]
    identity = ("--identity", second["identity"])
    import psycopg

    with psycopg.connect(
        host=server["host"], port=server["port"], dbname=second["name"], user=server["owner"],
        password=Path(server["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
    ) as session:
        session.execute("CREATE TABLE busy_probe (i int)")
        session.execute("INSERT INTO busy_probe VALUES (42)")
        session.commit()
        command("drop", target, *identity, status=6)
        assert session.execute("SELECT i FROM busy_probe").fetchone() == (42,)
        restored = command("show", target)["result"]
        assert restored["state"] == "ready" and restored["revision"] == second["revision"] + 2
        command("release", target, *identity)
        for flags in [("--dry-run",), ()]:
            sweep = command("sweep", "postgres", "--prefix", "copy", *flags)["result"]
            assert second["name"] not in [item["name"] for item in sweep["removed"]]
            assert any(item["copy"]["name"] == second["name"] and item["reason"] == "busy"
                       for item in sweep["kept"])
        assert session.execute("SELECT i FROM busy_probe").fetchone() == (42,)
    assert command("drop", target, *identity)["result"]["state"] == "gone"


def test_mysql_copy_withholding_precedes_a_reservation(server):
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    connection = ["--host", server["host"], "--port", str(server["port"]), "--user", server["owner"],
                  "--password-file", server["password_file"]]
    for database, code in (("replay_trigger", "not-replayable"), ("replay_func", "not-replayable"),
                           ("oracle_hr", "dependency-group"), ("unknown_database", "no-template")):
        result = subprocess.run(
            [sys.executable, "-m", "megasamples", "copy", "create", "mysql:" + database,
             "--prefix", "copy", "--label", "withheld", *connection],
            text=True, capture_output=True, timeout=20,
        )
        assert result.returncode == 4, result.stdout + result.stderr
        document = json.loads(result.stdout)
        assert document["error"]["code"] == code
        assert document["error"]["identity"] is None
    listed = subprocess.run(
        [sys.executable, "-m", "megasamples", "copy", "list", "mysql", "--prefix", "copy", *connection],
        text=True, capture_output=True, timeout=20,
    )
    assert listed.returncode == 0, listed.stdout + listed.stderr
    assert not json.loads(listed.stdout)["result"]["copies"]


def test_mysql_copy_lifecycle_and_schema_replay(server):
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    import pymysql

    def command(*args, status=0):
        result = subprocess.run(
            [sys.executable, "-m", "megasamples", "copy", *args, "--host", server["host"],
             "--port", str(server["port"]), "--user", server["owner"],
             "--password-file", server["password_file"]],
            text=True, capture_output=True, timeout=45,
        )
        assert result.returncode == status, result.stdout + result.stderr
        assert len(result.stdout.splitlines()) == 1
        document = json.loads(result.stdout)
        assert document["volume"]
        return document

    row = command("create", "mysql:sample", "--prefix", "copy", "--label", "fixture")["result"]
    assert row["state"] == "ready"
    target = "mysql:" + row["name"]
    identity = ("--identity", row["identity"])
    command("show", target)
    command("list", "mysql", "--prefix", "copy", "--label", "fixture")
    command("renew", target, *identity, "--lease", "7d")
    assert row["name"] not in removed_names(command("sweep", "mysql", "--prefix", "copy"))
    with pymysql.connect(
        host=server["host"], port=server["port"], database=row["name"], user=server["owner"],
        password=Path(server["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM v2")
            assert cursor.fetchall() == ((0,), (42,))
            cursor.execute("INSERT INTO parent VALUES (51)")
            cursor.execute("SELECT id FROM v2 ORDER BY id")
            assert cursor.fetchall() == ((0,), (42,), (51,))
            cursor.execute("SELECT id FROM sample_start.v2")
            assert cursor.fetchall() == ((0,), (42,))
            cursor.execute("CALL read_value()")
            assert cursor.fetchall() == ((0,), (42,), (51,))
            while cursor.nextset():
                pass
            with pytest.raises(pymysql.IntegrityError):
                cursor.execute("INSERT INTO child VALUES (2,999)")
            cursor.execute("SELECT STATUS FROM information_schema.EVENTS WHERE EVENT_NAME=%s AND EVENT_SCHEMA=%s",
                           (row["proof"]["event"], row["name"]))
            assert cursor.fetchone() == ("DISABLED",)
            cursor.execute("SELECT amount FROM child")
            assert cursor.fetchone() == (84,)
            cursor.execute("SELECT DEFINER, STATUS, EVENT_DEFINITION FROM information_schema.EVENTS "
                           "WHERE EVENT_NAME='read_event' AND EVENT_SCHEMA=%s", (row["name"],))
            definer, event_status, definition = cursor.fetchone()
            assert definer == server["owner"] + "@%" and event_status == "DISABLED"
            assert row["name"] in definition and "sample_start" not in definition
    command("release", target, *identity)
    assert row["name"] in removed_names(command("sweep", "mysql", "--prefix", "copy", "--dry-run"))
    assert row["name"] in removed_names(command("sweep", "mysql", "--prefix", "copy"))
    command("drop", target, *identity)


def test_mysql_copy_replacement_grant_refuses_sweep(server):
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    admin = {"user": "dl077_fixture_admin"}
    native(server, "CREATE USER 'outside_reader'@'%' ACCOUNT LOCK", **admin)
    native(server, r"GRANT DROP ON `copy\_%`.* TO 'outside_reader'@'%'", **admin)
    reply = copy_command(server, "create", "mysql:chinook", "--prefix", "copy", "--label", "outside")
    row = reply["result"]
    target = "mysql:" + row["name"]
    proof = ("--identity", row["identity"])
    try:
        assert row["state"] == "not-exclusive" and reply["warnings"]
        shown = copy_command(server, "show", target)
        assert shown["result"] == row and shown["warnings"] == reply["warnings"]
        listed = copy_command(server, "list", "mysql", "--prefix", "copy", "--label", "outside")
        assert listed["result"]["copies"] == [row] and listed["warnings"] == reply["warnings"]
        assert copy_command(server, "drop", target, *proof, status=5)["error"]["code"] == "not-exclusive"
        assert copy_command(server, "sweep", "mysql", "--prefix", "copy", status=5)["error"]["code"] == "not-exclusive"
        native(server, r"REVOKE DROP ON `copy\_%`.* FROM 'outside_reader'@'%'", **admin)
        native(server, f"GRANT SELECT ON `{row['name']}`.`artist` TO 'outside_reader'@'%'", **admin)
        shown = copy_command(server, "show", target)
        assert shown["result"]["state"] == "ready"
        assert any(warning["account"] == "outside_reader@%" for warning in shown["warnings"])
        assert copy_command(server, "drop", target, *proof)["result"]["state"] == "gone"
    finally:
        native(server, "DROP USER 'outside_reader'@'%'", **admin)
        copy_command(server, "drop", target, *proof)


def test_mysql_template_size_uses_allocated_tablespace_bytes(server):
    if server["engine"] != "mysql" or "chinook_allocated_bytes" not in server:
        pytest.skip("requires the MySQL fixture with a file-allocation witness")
    rows = native(server, "SELECT JSON_EXTRACT(metadata,'$.bytes') FROM template_ddl WHERE name='chinook'")
    # Copying a sparse data directory into an image can change its block allocation.
    assert abs(int(rows[0][0]) - server["chinook_allocated_bytes"]) <= server["chinook_tablespaces"] * 4096
