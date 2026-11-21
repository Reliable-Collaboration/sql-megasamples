#!/usr/bin/env python3
"""Lifecycle helpers for the throwaway MySQL build server every dataset is loaded into.

  python3 -m megasamples build-server [start | fresh | stop | status]

The build server is a plain container running the pinned image with the project's my.cnf plus the
loading options the plan requires (local_infile on, binary logging off). Datasets are loaded into it,
tested there, and dumped from it; the container is disposable.
"""
import json, os, shlex, subprocess, sys, time

from megasamples.paths import BUILD, DATASETS, ENGINES, STAGE
from megasamples.engines.mysql import base_image
from megasamples.credentials import client
IMAGE = os.environ.get("MYSQL_IMAGE", base_image.IMAGE)
NAME = os.environ.get("BUILD_SERVER", "megasamples-build-mysql")
PW = "build"


def run(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(cmd if isinstance(cmd, list) else shlex.split(cmd), **kw)


def container_state():
    p = run(["docker", "inspect", "-f", "{{.State.Status}}", NAME])
    return p.stdout.strip() if p.returncode == 0 else None


def ready(timeout=180):
    """Wait until a real statement succeeds over TCP. `mysqladmin ping` answers on access-denied
    (P-02), and the socket answers during the official image's first-start initialisation, when a
    temporary server runs with --skip-networking and is stopped before the real one starts."""
    for _ in range(int(timeout * 5)):
        with client("mysql", NAME, "root", PW) as command:
            if run([*command, "-N", "-e", "SELECT 1"]).returncode == 0:
                return True
        time.sleep(0.2)
    return False


def start(fresh=False):
    if fresh and container_state():
        stop()
    if container_state() == "running":
        running = run(["docker", "inspect", "-f", "{{.Image}}", NAME])
        expected = run(["docker", "image", "inspect", "-f", "{{.Id}}", IMAGE])
        if (running.returncode or expected.returncode or
                running.stdout.strip().removeprefix("sha256:") != expected.stdout.strip().removeprefix("sha256:")):
            sys.exit("Build server uses a different image; run `build-server fresh` to initialize "
                     "the pinned LTS image. Do not reuse an Innovation data directory.")
        return
    if container_state():
        run(["docker", "rm", "-fv", NAME])
    if IMAGE == base_image.IMAGE:
        base_image.build()
    os.makedirs(STAGE, exist_ok=True)     # mounted below; Docker would otherwise create it as root
    p = run(["docker", "run", "-d", "--name", NAME,
             # transient: `python3 -m megasamples status clean` removes everything so labelled, and
             # Docker Desktop shows them apart from the compose stack rather than mixed into it
             "--label", "megasamples.transient=true", "--label", "megasamples.role=build",
             "-e", f"MYSQL_ROOT_PASSWORD={PW}",
             "-e", "MYSQL_ROOT_HOST=127.0.0.1",
             "-v", f"{os.path.join(ENGINES, 'mysql', 'my.cnf')}:/etc/mysql/conf.d/megasamples.cnf:ro",
             "-v", f"{DATASETS}:/datasets:ro",
             # read-only: staged inputs are produced on the host. The context must NOT be the
             # secure_file_priv directory -- the entrypoint chowns that one to uid 999 at every
             # start, which takes it away from the host user (found at S-02).
             "-v", f"{STAGE}:/context:ro",
             # writable output for dumps; safe to mount rw because it is not secure_file_priv
             "-v", f"{BUILD}:/build",
             IMAGE, "mysqld",
             "--local-infile=1", "--skip-log-bin"])
    if p.returncode != 0:
        sys.exit(f"could not start the build server: {p.stderr.strip()}")
    if not ready():
        logs = run(["docker", "logs", "--tail", "30", NAME])
        sys.exit(f"build server never became ready:\n{logs.stdout}{logs.stderr}")


def stop():
    run(["docker", "rm", "-fv", NAME])


def sql(statement, database=None, table=False, check=True, raw=True):
    """Run a statement through the mysql client. `raw=False` keeps the client's batch escaping
    (\\n, \\t, \\\\, \\0 inside values), so a value holding a newline or a tab cannot break a row."""
    cmd = ["--default-character-set=utf8mb4", "--local-infile=1"]
    if not table:
        cmd += ["-N", "--batch"] + (["--raw"] if raw else [])
    else:
        cmd += ["--table"]
    if database:
        cmd += ["-D", database]
    with client("mysql", NAME, "root", PW) as command:
        p = run([*command, *cmd], input=statement)
    if check and p.returncode != 0:
        raise RuntimeError(f"SQL failed: {p.stderr.strip()}\n--- statement ---\n{statement[:400]}")
    return p.stdout


def sql_file(path, database=None):
    """Stream a .sql file into the server (files can be large; never read them into argv)."""
    # --local-infile: the client is the one that reads a LOAD DATA LOCAL INFILE path, and it runs
    # inside the container, so those paths are the container's (/context is the staged input mount)
    cmd = ["--default-character-set=utf8mb4", "--local-infile=1"]
    if database:
        cmd += ["-D", database]
    with client("mysql", NAME, "root", PW) as command, open(path, "rb") as fh:
        p = subprocess.run([*command, *cmd], stdin=fh, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"loading {path} failed: {p.stderr.strip()[:500]}")
    return p.stderr


def rows(statement, database=None):
    out = sql(statement, database=database)
    return [line.split("\t") for line in out.splitlines() if line]


BATCH_UNESCAPE = {"n": "\n", "t": "\t", "\\": "\\", "0": "\x00"}


def unescape_batch(field):
    if "\\" not in field:
        return field
    out, i = [], 0
    while i < len(field):
        c = field[i]
        if c == "\\" and i + 1 < len(field):
            out.append(BATCH_UNESCAPE.get(field[i + 1], field[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def rows_escaped(statement, database=None):
    """Rows whose values may hold newlines or tabs: the client escapes them, and they are unescaped
    here, so every row is one line and every field one cell."""
    out = sql(statement, database=database, raw=False)
    return [[unescape_batch(f) for f in line.split("\t")] for line in out.splitlines() if line]


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    action = argv[0] if argv else "start"
    if action == "start":
        start(); print(f"{NAME} ready ({IMAGE})")
    elif action == "fresh":
        start(fresh=True); print(f"{NAME} ready, fresh ({IMAGE})")
    elif action == "stop":
        stop(); print(f"{NAME} removed")
    elif action == "status":
        print(container_state() or "absent")
    else:
        sys.exit(f"unknown action {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
