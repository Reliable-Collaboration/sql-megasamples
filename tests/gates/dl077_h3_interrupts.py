"""H-3 / DL-113 / DL-119: caller-induced interrupts of CREATE DATABASE, compared with the catalog.

    DL077_GATE_TARGET=MANIFEST dl077_h3_interrupts.py ATTEMPTS-PER-CELL

MANIFEST is a private target manifest (tests/gates/native.py) whose `postgres` container carries the
task's ownership label; nothing runs until that is checked. As the namespace owner over the
container's local socket: a statement_timeout of X ms, and a client cancel request (psql receiving
SIGINT) after D seconds, across each strategy's whole duration. Every catalog and directory read must
succeed; every attempt must end committed, with the server's own cancel message, or with the client
stopped before any reply (counted apart, never as a server interrupt); each strategy and method must
see at least one server interrupt; a committed copy
must be closed to PUBLIC; and a directory with no catalog row, seen at any point, fails the run.
Exit 0 only if all of that held. Random points are evidence, not proof (DL-119).
"""
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from native import Target

INTERRUPTED = ("canceling statement due to statement timeout", "canceling statement due to user request")


class ProbeFailed(Exception):
    pass


def main():
    attempts = int(sys.argv[1])
    target = Target()
    container = target.container("postgres")   # refuses a container without the owner's label
    random.seed(20261121)

    def podman(*args, check=True):
        result = subprocess.run(target.podman_args(*args), capture_output=True, text=True, timeout=120)
        if check and result.returncode:
            raise ProbeFailed(f"podman {args[0]} exited {result.returncode}: {result.stderr.strip()[:200]}")
        return result

    def psql(sql, user="postgres", prefix=(), check=True):
        args = ["exec", container, *prefix, "psql", "-XqAt", "-U", user, "-d", "megasamples"]
        for statement in sql:
            args += ["-c", statement]
        return podman(*args, check=check)

    def catalog():
        rows = set(psql(["SELECT oid FROM pg_database"]).stdout.split())
        files = set(podman("exec", "-u", "postgres", container, "sh", "-ec", 'ls "$PGDATA/base"').stdout.split())
        if not rows or not files or not rows <= files:
            raise ProbeFailed("the catalog or the directory listing could not be read whole")
        return rows, files

    def timed_create(strategy):
        name = "copy_chinook_" + uuid.uuid4().hex[:12]
        started = time.monotonic()
        psql([f"CREATE DATABASE {name} TEMPLATE chinook_start STRATEGY {strategy}"], user="copier")
        elapsed = time.monotonic() - started
        psql([f"DROP DATABASE {name}"])
        return elapsed

    seen = set()
    rows, files = catalog()
    seen |= files - rows
    print("before: catalog", len(rows), "directories", len(files), "orphans", sorted(files - rows), flush=True)
    unexpected = 0
    uncovered = []
    for strategy in ("wal_log", "file_copy"):
        baseline = sorted(timed_create(strategy) for _ in range(5))[2]
        print(f"{strategy}: median create through podman exec {baseline:.3f}s", flush=True)
        for method in ("statement_timeout", "cancel"):
            committed = interrupted = client_only = other = 0
            for _ in range(attempts):
                name = "copy_chinook_" + uuid.uuid4().hex[:12]
                create = f"CREATE DATABASE {name} TEMPLATE chinook_start STRATEGY {strategy}"
                if method == "statement_timeout":
                    ms = random.randint(1, max(2, int(baseline * 1000)))
                    r = psql([f"SET statement_timeout = '{ms}ms'", create], user="copier", check=False)
                else:
                    delay = random.uniform(0.0, baseline * 1.2)
                    r = psql([create], user="copier", prefix=("timeout", "-s", "INT", f"{delay:.3f}"), check=False)
                exists = psql([f"SELECT count(*) FROM pg_database WHERE datname='{name}'"]).stdout.strip()
                if exists == "1":
                    committed += 1
                    closed = psql([f"""SELECT NOT EXISTS (SELECT FROM aclexplode(coalesce(datacl, acldefault('d',datdba)))
                                       WHERE grantee=0 AND privilege_type IN ('CONNECT','TEMPORARY'))
                                       FROM pg_database WHERE datname='{name}'"""]).stdout.strip()
                    if closed != "t":
                        raise ProbeFailed(f"{name} committed open to PUBLIC")
                    psql([f"DROP DATABASE {name}"])
                elif exists == "0" and any(message in r.stderr for message in INTERRUPTED):
                    interrupted += 1
                elif exists == "0" and r.returncode in (124, 130) and not r.stderr.strip():
                    client_only += 1   # stopped before the server reported anything: not a server interrupt
                else:
                    other += 1
                    print(f"  unexpected outcome: exit {r.returncode}: {r.stderr.strip()[:160]}", flush=True)
            rows, files = catalog()
            seen |= files - rows
            unexpected += other
            if not interrupted:
                uncovered.append(f"{strategy} {method}")
            print(f"{strategy} {method}: attempts {attempts} committed {committed} server-interrupted {interrupted} "
                  f"client-only {client_only} other {other} orphan directories {sorted(files - rows)}", flush=True)
    podman("exec", container, "psql", "-XqAt", "-U", "postgres", "-c", "CHECKPOINT")
    rows, files = catalog()
    seen |= files - rows
    print("after: catalog", len(rows), "directories", len(files), "orphans", sorted(files - rows),
          "seen at any point", sorted(seen), "cells without a server interrupt", uncovered, flush=True)
    return 1 if seen or unexpected or uncovered else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ProbeFailed as failure:
        print("probe failed:", failure, flush=True)
        sys.exit(2)
