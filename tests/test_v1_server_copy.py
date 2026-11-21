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
    assert not command("sweep", "postgres", "--prefix", "copy")["result"]["removed"]
    command("release", target, *identity)
    assert command("sweep", "postgres", "--prefix", "copy", "--dry-run")["result"]["removed"]
    assert command("show", target)["result"]["state"] == "ready"
    assert command("sweep", "postgres", "--prefix", "copy")["result"]["removed"]
    command("drop", target, *identity)

    second = command("create", "postgres:chinook", "--prefix", "copy", "--label", "second")["result"]
    target = "postgres:" + second["name"]
    identity = ("--identity", second["identity"])
    import psycopg

    with psycopg.connect(
        host=server["host"], port=server["port"], dbname=second["name"], user=server["owner"],
        password=Path(server["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
    ) as session:
        command("drop", target, *identity, status=6)
        assert session.execute("SELECT 42").fetchone() == (42,)
        assert command("show", target)["result"]["state"] == "ready"
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
    assert not command("sweep", "mysql", "--prefix", "copy")["result"]["removed"]
    with pymysql.connect(
        host=server["host"], port=server["port"], database=row["name"], user=server["owner"],
        password=Path(server["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM v2")
            assert cursor.fetchall() == ((42,),)
            cursor.execute("INSERT INTO parent VALUES (51)")
            cursor.execute("SELECT id FROM v2 ORDER BY id")
            assert cursor.fetchall() == ((42,), (51,))
            cursor.execute("SELECT id FROM sample_start.v2")
            assert cursor.fetchall() == ((42,),)
            cursor.execute("CALL read_value()")
            assert cursor.fetchall() == ((42,), (51,))
            while cursor.nextset():
                pass
            with pytest.raises(pymysql.IntegrityError):
                cursor.execute("INSERT INTO child VALUES (2,999)")
            cursor.execute("SELECT STATUS FROM information_schema.EVENTS WHERE EVENT_NAME=%s AND EVENT_SCHEMA=%s",
                           (row["proof"]["event"], row["name"]))
            assert cursor.fetchone() == ("DISABLED",)
    command("release", target, *identity)
    assert command("sweep", "mysql", "--prefix", "copy", "--dry-run")["result"]["removed"]
    assert command("sweep", "mysql", "--prefix", "copy")["result"]["removed"]
    command("drop", target, *identity)


def test_mysql_copy_replacement_grant_refuses_sweep(server):
    witness = server.get("not_exclusive")
    if server["engine"] != "mysql" or not witness:
        pytest.skip("requires a copy with an outside replacement grant")
    options = ["--host", server["host"], "--port", str(server["port"]), "--user", server["owner"],
               "--password-file", server["password_file"]]

    def execute(*args):
        result = subprocess.run([sys.executable, "-m", "megasamples", "copy", *args, *options],
                                text=True, capture_output=True, timeout=25)
        return result, json.loads(result.stdout)

    target = "mysql:" + witness["name"]
    before, shown = execute("show", target)
    assert before.returncode == 0
    assert shown["result"]["state"] == "not-exclusive"
    assert shown["warnings"]
    dropped, error = execute("drop", target, "--identity", witness["identity"])
    assert dropped.returncode == 5
    assert error["error"]["code"] == "not-exclusive"
    swept, error = execute("sweep", "mysql", "--prefix", "copy")
    assert swept.returncode == 5, swept.stdout + swept.stderr
    assert error["error"]["code"] == "not-exclusive"
    assert execute("show", target)[1]["result"] == shown["result"]
