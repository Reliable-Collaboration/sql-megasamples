#!/usr/bin/env python3
"""Lifecycle helpers for the throwaway PostgreSQL build server every port is loaded into.

  python3 -m megasamples pg-server [start | fresh | stop | status]

The build server runs the pinned official image as a plain container with build/ mounted at /build,
so the port files a dataset produces can be loaded with psql's \\copy from inside the container.
Databases are loaded into it, verified there, and the image builder loads the same files again in
its own builder stage; the container is disposable.
"""
import os, shlex, subprocess, sys, time

from megasamples.paths import BUILD

IMAGE = os.environ.get("POSTGRES_IMAGE", 'docker.io/library/postgres:18.7-trixie@sha256:2ea8630df176ad090ec92136dee850397c5af8781e4bcf2e4162593691c61bbc')
NAME = os.environ.get("POSTGRES_BUILD_SERVER", "megasamples-build-postgres")
PW = "build"


def run(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(cmd if isinstance(cmd, list) else shlex.split(cmd), **kw)


def container_state():
    p = run(["docker", "inspect", "-f", "{{.State.Status}}", NAME])
    return p.stdout.strip() if p.returncode == 0 else None


def ready(timeout=120):
    """Wait until the server answers over TCP. On its first start the official image runs a
    temporary server on the Unix socket alone (listen_addresses='') while it initialises, then
    stops it and starts the real one; a socket check answers during that window and the next
    statement finds no server (measured: a 109 ms gap between the two on 2026-09-10)."""
    for _ in range(int(timeout * 5)):
        if run(["docker", "exec", "-e", f"PGPASSWORD={PW}", NAME, "psql", "-h", "127.0.0.1", "-U", "postgres",
                "-tAc", "SELECT 1"]).returncode == 0:
            return True
        time.sleep(0.2)
    return False


def start(fresh=False):
    if fresh and container_state():
        stop()
    if container_state() == "running":
        return
    if container_state():
        run(["docker", "rm", "-f", NAME])
    os.makedirs(BUILD, exist_ok=True)
    p = run(["docker", "run", "-d", "--name", NAME,
             "--label", "megasamples.transient=true", "--label", "megasamples.role=build",
             "-e", f"POSTGRES_PASSWORD={PW}",
             "-v", f"{BUILD}:/build",
             IMAGE, "postgres",
             # bulk-load settings for a throwaway server; nothing here reaches the image
             "-c", "fsync=off", "-c", "synchronous_commit=off", "-c", "full_page_writes=off",
             "-c", "maintenance_work_mem=512MB", "-c", "max_wal_size=4GB",
             "-c", "wal_level=minimal", "-c", "max_wal_senders=0"])
    if p.returncode != 0:
        sys.exit(f"could not start the PostgreSQL build server: {p.stderr.strip()}")
    if not ready():
        logs = run(["docker", "logs", "--tail", "30", NAME])
        sys.exit(f"PostgreSQL build server never became ready:\n{logs.stdout}{logs.stderr}")


def stop():
    run(["docker", "rm", "-f", NAME])


def psql(sql, database="postgres", check=True):
    """Run one statement through psql; rows come back tab-separated, no header, NULL as \\N."""
    cmd = ["docker", "exec", "-i", NAME, "psql", "-U", "postgres", "-d", database,
           "-v", "ON_ERROR_STOP=1", "-qAt", "-F", "\t", "-P", "null=\\N", "-c", sql]
    p = run(cmd)
    if check and p.returncode != 0:
        raise RuntimeError(f"psql failed: {p.stderr.strip()[:500]}\n--- statement ---\n{sql[:400]}")
    return p.stdout


def psql_script(text, database="postgres", null="\\N"):
    """Run a script through psql's standard input: statements go one at a time, every result is
    printed tab-separated without headers, and the first error stops it."""
    p = run(["docker", "exec", "-i", NAME, "psql", "-U", "postgres", "-d", database,
             "-v", "ON_ERROR_STOP=1", "-qAt", "-F", "\t", "-P", f"null={null}"], input=text)
    if p.returncode != 0:
        raise RuntimeError(f"psql script failed: {p.stderr.strip()[:600]}\n--- script ---\n{text[:600]}")
    return p.stdout


def psql_file(path_in_container, database):
    p = run(["docker", "exec", NAME, "psql", "-U", "postgres", "-d", database,
             "-v", "ON_ERROR_STOP=1", "-q", "-f", path_in_container])
    if p.returncode != 0:
        raise RuntimeError(f"psql -f {path_in_container} failed: {p.stderr.strip()[:500]}")
    return p.stdout


def copy_out(sql, database):
    """`COPY (query) TO STDOUT` as raw bytes, one text-format line per row."""
    p = subprocess.run(["docker", "exec", NAME, "psql", "-U", "postgres", "-d", database,
                        "-v", "ON_ERROR_STOP=1", "-qAt", "-c", f"COPY ({sql}) TO STDOUT"],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"COPY failed: {p.stderr.decode('utf-8', 'replace').strip()[:500]}\n--- {sql[:300]}")
    return p.stdout


def rows(sql, database="postgres"):
    out = psql(sql, database)
    return [line.split("\t") for line in out.splitlines() if line != ""]


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
