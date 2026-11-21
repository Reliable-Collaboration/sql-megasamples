"""H-3 / sol P2-4: caller-induced interrupts of CREATE DATABASE on the candidate, compared with the catalog.

As the namespace owner over the container's local socket: a statement_timeout of X ms, and a client
cancel request (psql receiving SIGINT) after D seconds, across each strategy's whole duration. After
every attempt: a committed copy must be closed to PUBLIC; at the end every base/ directory must have
a catalog row. Usage: DL077_ISOLATED_ENV=ENV-SCRIPT dl077_h3_interrupts.py CONTAINER ATTEMPTS-PER-CELL
CONTAINER is a task-owned container started from the candidate image. Exit 1 if any directory
under base/ has no catalog row.
"""
import random, subprocess, sys, time, uuid

import os
ENV = os.environ.get("DL077_ISOLATED_ENV") or sys.exit("set DL077_ISOLATED_ENV to the isolated store's env script")
container, attempts = sys.argv[1], int(sys.argv[2])
random.seed(20261121)


def podman(*args, check=False):
    return subprocess.run(["bash", "-c", 'source "$1"; shift; exec podman "$@"', "h3", ENV, *args],
                          capture_output=True, text=True, timeout=120)


def psql(sql, user="postgres", db="megasamples", prefix=()):
    return podman("exec", container, *prefix, "psql", "-XqAt", "-U", user, "-d", db, *sum((["-c", s] for s in sql), []))


def catalog():
    rows = psql(["SELECT oid FROM pg_database"]).stdout.split()
    files = podman("exec", container, "ls", "/var/lib/postgresql/18/docker/base").stdout.split()
    return set(rows), set(files)


def timed_create(strategy):
    name = "copy_chinook_" + uuid.uuid4().hex[:12]
    started = time.monotonic()
    r = psql([f"CREATE DATABASE {name} TEMPLATE chinook_start STRATEGY {strategy}"], user="copier")
    assert r.returncode == 0, r.stderr
    elapsed = time.monotonic() - started
    psql([f"DROP DATABASE {name}"])
    return elapsed


rows, files = catalog()
print("before: catalog", len(rows), "directories", len(files), "orphans", sorted(files - rows), flush=True)
results = {}
for strategy in ("wal_log", "file_copy"):
    baseline = sorted(timed_create(strategy) for _ in range(5))[2]
    print(f"{strategy}: median create through podman exec {baseline:.3f}s", flush=True)
    for method in ("statement_timeout", "cancel"):
        committed = refused = other = 0
        for _ in range(attempts):
            name = "copy_chinook_" + uuid.uuid4().hex[:12]
            create = f"CREATE DATABASE {name} TEMPLATE chinook_start STRATEGY {strategy}"
            if method == "statement_timeout":
                ms = random.randint(1, max(2, int(baseline * 1000)))
                r = psql([f"SET statement_timeout = '{ms}ms'", create], user="copier")
            else:
                delay = random.uniform(0.0, baseline * 1.2)
                r = psql([create], user="copier", prefix=("timeout", "-s", "INT", f"{delay:.3f}"))
            exists = psql([f"SELECT count(*) FROM pg_database WHERE datname='{name}'"]).stdout.strip()
            if exists == "1":
                committed += 1
                closed = psql([f"""SELECT NOT EXISTS (SELECT FROM aclexplode(coalesce(datacl, acldefault('d',datdba)))
                                   WHERE grantee=0 AND privilege_type IN ('CONNECT','TEMPORARY'))
                                   FROM pg_database WHERE datname='{name}'"""]).stdout.strip()
                assert closed == "t", f"{name} committed open to PUBLIC"
                psql([f"DROP DATABASE {name}"])
            elif "canceling statement" in r.stderr or r.returncode != 0:
                refused += 1
            else:
                other += 1
        rows, files = catalog()
        results[(strategy, method)] = (committed, refused, other, sorted(files - rows))
        print(f"{strategy} {method}: attempts {attempts} committed {committed} interrupted {refused} other {other} "
              f"orphan directories {sorted(files - rows)}", flush=True)
podman("exec", container, "psql", "-XqAt", "-U", "postgres", "-c", "CHECKPOINT")
rows, files = catalog()
print("after: catalog", len(rows), "directories", len(files), "orphans", sorted(files - rows), flush=True)
sys.exit(1 if files - rows else 0)
