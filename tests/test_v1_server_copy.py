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
