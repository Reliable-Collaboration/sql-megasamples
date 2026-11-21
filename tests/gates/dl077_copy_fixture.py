"""Provision opt-in copy regressions on a new, isolated image container."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from uuid import uuid4

from native import capacity

ROOT = Path(__file__).resolve().parents[2]
# The isolated store is named by the caller, never by this file: an env script that sets the
# container variables, and the graph root that `podman info` must then report.
ENV = os.environ.get("DL077_ISOLATED_ENV", "")
GRAPH = os.environ.get("DL077_ISOLATED_GRAPH", "")


def podman(*args, stdin=None, check=True):
    if not (ENV and GRAPH):
        raise RuntimeError("set DL077_ISOLATED_ENV and DL077_ISOLATED_GRAPH to the isolated store")
    command = ["bash", "-c", 'source "$1" || exit; shift; exec podman "$@"', "dl077", ENV, *args]
    result = subprocess.run(command, input=stdin, text=True, capture_output=True, timeout=90)
    if check and result.returncode:
        raise RuntimeError(f"isolated podman {args[0]} failed with exit {result.returncode}")
    return result


def private(path, content):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(content)


def mysql_exec(container, command, sql, *, check=True):
    # Socket client reads its bootstrap credential from an owner-only file.
    return podman("exec", "-i", container, "sh", "-ec", command, stdin=sql, check=check)


def postgres(container, database, sql, *, check=True):
    return podman("exec", "-i", container, "psql", "-XqAt", "-v", "ON_ERROR_STOP=1",
                  "-U", "postgres", "-d", database, stdin=sql, check=check)


def mysql(container, sql, *, check=True):
    return mysql_exec(container, 'mysql --defaults-extra-file=/tmp/dl077-client.cnf -N -B',
                      sql, check=check)


def wait_for(query):
    for _ in range(150):
        if not query().returncode:
            return
        time.sleep(0.2)
    raise RuntimeError("fixture database did not become ready")


def seed_postgres(container, marker, password):
    wait_for(lambda: postgres(container, "postgres", "SELECT 1", check=False))
    postgres(container, "megasamples", f"""
        ALTER ROLE copier LOGIN PASSWORD '{password}';
        CREATE ROLE dl077_fixture_admin LOGIN SUPERUSER PASSWORD '{password}';
    """)
    # The copy service row is the image's own: the fixture reads it and never writes it, so the suite
    # runs against what a shipped image provides.
    return postgres(container, "megasamples", "SELECT volume FROM copy_service WHERE singleton").stdout.strip()


def seed_mysql(container, marker, password):
    podman("exec", "-i", container, "sh", "-ec", "umask 077; cat > /tmp/dl077-client.cnf",
           stdin="[client]\nuser=root\npassword=root\n")
    wait_for(lambda: mysql(container, "SELECT 1", check=False))
    for schema in ("sample",):
        mysql(container, f"""
        CREATE DATABASE {schema};
        SET SESSION sql_mode=CONCAT_WS(',',NULLIF(@@session.sql_mode,''),'NO_AUTO_VALUE_ON_ZERO');
        CREATE TABLE {schema}.parent (id int PRIMARY KEY AUTO_INCREMENT);
        INSERT INTO {schema}.parent VALUES (0),(42);
        CREATE TABLE {schema}.child (
            id int PRIMARY KEY, parent_id int,
            amount int GENERATED ALWAYS AS (parent_id * 2) STORED,
            FOREIGN KEY (parent_id) REFERENCES {schema}.parent(id)
        );
        INSERT INTO {schema}.child (id, parent_id) VALUES (1,42);
        CREATE VIEW {schema}.v1 AS SELECT id FROM {schema}.parent;
        CREATE VIEW {schema}.v2 AS SELECT id FROM {schema}.v1;
        SET SESSION sql_mode='ONLY_FULL_GROUP_BY,STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';
        CREATE PROCEDURE {schema}.read_value() SELECT id FROM {schema}.parent ORDER BY id;
        SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE', time_zone='+05:30';
        CREATE EVENT {schema}.read_event ON SCHEDULE AT CURRENT_TIMESTAMP + INTERVAL 1 YEAR
            ON COMPLETION PRESERVE DISABLE DO SELECT id FROM {schema}.parent;
        """)
    # Round 9 (Opus 1, Sol 1): a program whose qualifier MySQL reads past `1--1` and a comment before the
    # dot. The client keeps comments, so the server stores the body as written.
    mysql_exec(container, 'mysql --defaults-extra-file=/tmp/dl077-client.cnf --comments -N -B',
               "CREATE PROCEDURE sample.read_lexed() SELECT 1--1 AS n, id FROM sample /* gap */ .parent ORDER BY id;\n")
    # A program created under ANSI_QUOTES: its double-quoted names are not rewritten, so it is withheld.
    mysql(container, """
        CREATE DATABASE replay_ansi;
        CREATE TABLE replay_ansi.t (id int PRIMARY KEY);
        SET SESSION sql_mode='ANSI_QUOTES';
        CREATE PROCEDURE replay_ansi.read_t() SELECT id FROM "replay_ansi"."t";
        CREATE DATABASE replay_nobackslash;
        CREATE TABLE replay_nobackslash.t (id int PRIMARY KEY, label varchar(8));
        SET SESSION sql_mode='NO_BACKSLASH_ESCAPES';
        CREATE PROCEDURE replay_nobackslash.read_t() SELECT 'ends\\', id FROM replay_nobackslash.t;
        """)
    mysql(container, f"""
        ALTER USER 'copier'@'%' IDENTIFIED BY '{password}' ACCOUNT UNLOCK;
        CREATE USER 'dl077_fixture_admin'@'%' IDENTIFIED BY '{password}';
        GRANT ALL PRIVILEGES ON *.* TO 'dl077_fixture_admin'@'%' WITH GRANT OPTION;
        CREATE TABLE megasamples.test_fixture_marker (marker varchar(100));
        INSERT INTO megasamples.test_fixture_marker VALUES ('{marker}');
        GRANT SELECT ON megasamples.test_fixture_marker TO 'copier'@'%';
        GRANT SELECT ON `sample\\_start`.* TO 'copier'@'%';
        INSERT INTO megasamples.template_ddl (name,reason,detail) VALUES
            ('replay_trigger','not-replayable','fixture trigger'),
            ('replay_func','not-replayable','fixture function'),
            ('oracle_hr','dependency-group','fixture group')
        ON DUPLICATE KEY UPDATE reason=VALUES(reason),detail=VALUES(detail);
    """)
    for name in ("mysql_templates.py", "mysql_template_build.py"):
        podman("cp", str(ROOT / "megasamples" / name), f"{container}:/tmp/{name}")
    # The template is made by the image build's own per-database step, as a shipped database's is.
    mysql(container, "INSERT INTO megasamples.datasets (name, tier, record, build_id) VALUES "
                     "('sample', 'fixture', 'fixture', 'fixture'), ('replay_ansi', 'fixture', 'fixture', 'fixture'), "
                     "('replay_nobackslash', 'fixture', 'fixture', 'fixture')")
    script = """
from mysql_template_build import offer
offer("sample", "fixture", ["sample", "replay_ansi", "replay_nobackslash"])
offer("replay_ansi", "fixture", ["sample", "replay_ansi", "replay_nobackslash"])
offer("replay_nobackslash", "fixture", ["sample", "replay_ansi", "replay_nobackslash"])
"""
    podman("exec", "-i", container, "sh", "-ec", "cat >/tmp/dl077-inventory.py", stdin=script)
    socket = mysql(container, "SELECT @@socket").stdout.strip()
    podman("exec", "-i", container, "mysqlsh", "--no-defaults", "-uroot", "-S",
           socket, "--passwords-from-stdin", "--py", "--file", "/tmp/dl077-inventory.py",
           stdin="root\n")
    return mysql(container, "SELECT @@server_uuid").stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=("postgres", "mysql"))
    parser.add_argument("image")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if podman("info", "--format", "{{.Store.GraphRoot}}").stdout.strip() != GRAPH:
        raise RuntimeError("the isolated image store is required")
    capacity()
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    name = f"dl077-v1-tcp-{uuid4().hex}"
    marker = name
    password = secrets.token_hex(24)
    port = "5432" if args.engine == "postgres" else "3306"
    server_args = ["postgres", "-c", f"cluster_name={marker}"] if args.engine == "postgres" else []
    podman("run", "-d", "--name", name, "--label", "org.sql-megasamples.gates.owner=" + name,
           "--memory", "2g", "--pull", "never", "-p", f"127.0.0.1::{port}",
           args.image, *server_args)
    try:
        seed = seed_postgres if args.engine == "postgres" else seed_mysql
        volume = seed(name, marker, password)
        endpoint = podman("port", name, port + "/tcp").stdout.strip()
        host, _, forwarded_port = endpoint.rpartition(":")
        if host != "127.0.0.1":
            raise RuntimeError("the test port must only bind to loopback")
        private(args.output / "password", password + "\n")
        config = {
            "container": name, "engine": args.engine, "host": host, "port": int(forwarded_port),
            "marker": marker, "volume": volume, "owner": "copier",
            "password_file": str((args.output / "password").resolve()),
        }
        if args.engine == "mysql":
            sizes = podman("exec", name, "sh", "-ec",
                           "stat -c '%b %B' /var/lib/mysql/chinook/*.ibd").stdout.splitlines()
            config["chinook_allocated_bytes"] = sum(int(blocks) * int(size)
                                                     for blocks, size in map(str.split, sizes))
            config["chinook_tablespaces"] = len(sizes)
        private(args.output / "target.json", json.dumps(config))
    except BaseException:
        podman("rm", "-fv", name, check=False)
        raise
    print(name)


if __name__ == "__main__":
    main()
