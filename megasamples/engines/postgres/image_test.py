#!/usr/bin/env python3
"""S8 for the PostgreSQL image: run it and check it as a user would receive it.

  python3 -m megasamples test-image --engine postgres [dataset ...]

Asserts: the container answers a real query within the time budget; the registry lists exactly the
built datasets; every table's row count matches the pinned expectation; `demo` can read and cannot
write; `admin` can write; no login role is passwordless; the password overrides take effect. Password
checks go over TCP, because the image's socket connections are trusted for local maintenance.
"""
import os, subprocess, sys, time
import yaml

from megasamples.paths import ROOT
from megasamples.engines import unique_databases
from megasamples.registry import image_counts

IMAGE = os.environ.get("MEGASAMPLES_POSTGRES_IMAGE", "sql-megasamples-postgres:dev")
NAME = "megasamples-test-postgres"
BUDGET_SECONDS = 30


def sh(*args, **kw):
    return subprocess.run(list(args), capture_output=True, text=True, **kw)


def q(sql, user="postgres", pw="root", database="postgres", container=NAME):
    """A query from inside the container. The role is what is asked for, so privilege checks are
    real; the password is not checked, because the official image trusts its own loopback."""
    return sh("docker", "exec", "-e", f"PGPASSWORD={pw}", container, "psql", "-h", "127.0.0.1",
              "-U", user, "-d", database, "-v", "ON_ERROR_STOP=1", "-tAc", sql)


def q_net(sql, user="postgres", pw="root", database="postgres", container=NAME):
    """A query from another container over the Docker network: the path a client takes, where
    pg_hba applies scram-sha-256, so a wrong password is refused."""
    ip = sh("docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", container).stdout.strip()
    return sh("docker", "run", "--rm", "--label", "megasamples.transient=true", "-e", f"PGPASSWORD={pw}",
              IMAGE, "psql", "-h", ip, "-U", user, "-d", database, "-v", "ON_ERROR_STOP=1", "-tAc", sql)


class Checks:
    def __init__(self): self.failures = []
    def ok(self, label): print(f"  . {label}")
    def fail(self, label): print(f"  x {label}"); self.failures.append(label)
    def expect(self, cond, label): (self.ok if cond else self.fail)(label)


def main(argv=None):
    datasets = list(sys.argv[1:] if argv is None else argv) or ["sakila"]
    c = Checks()
    sh("docker", "rm", "-f", NAME)
    started = time.time()
    run = sh("docker", "run", "-d", "--name", NAME,
             "--label", "megasamples.transient=true", "--label", "megasamples.role=test", IMAGE)
    if run.returncode != 0:
        sys.exit(f"could not start {IMAGE}: {run.stderr}")
    try:
        ready = None
        while time.time() - started < BUDGET_SECONDS * 2:
            if q("SELECT 1").returncode == 0:
                ready = time.time() - started
                break
            time.sleep(0.2)
        c.expect(ready is not None, "container answers a real query")
        c.expect(ready is not None and ready <= BUDGET_SECONDS,
                 f"ready in {ready:.1f}s (budget {BUDGET_SECONDS}s)" if ready else "never became ready")
        if ready is None:
            print(sh("docker", "logs", "--tail", "30", NAME).stdout); return 1
        logs = sh("docker", "logs", NAME).stdout + sh("docker", "logs", NAME).stderr
        c.expect("initdb" not in logs and "Success. You can now start" not in logs,
                 "entrypoint did not re-initialise the shipped cluster")

        registry = q("SELECT name FROM datasets ORDER BY name", database="megasamples").stdout.split()
        c.expect(sorted(registry) == sorted(unique_databases(datasets)),
                 f"registry lists exactly the built databases ({len(registry)})")

        for name in datasets:
            cfg = yaml.safe_load(open(os.path.join(ROOT, "datasets", name, "dataset.yaml"), encoding="utf-8"))
            schema = cfg["database"]
            counts = image_counts(name)
            bad = []
            for table, want in counts.items():
                got = q(f'SELECT count(*) FROM "{table}"', database=schema).stdout.strip()
                if got != str(want):
                    bad.append(f"{table}={got} want {want}")
            c.expect(not bad, f"{schema}: {len(counts)} tables match their expected snapshot counts"
                              + (f" -- {bad[:3]}" if bad else ""))

        first = datasets[0]
        schema = yaml.safe_load(open(os.path.join(ROOT, "datasets", first, "dataset.yaml"), encoding="utf-8"))["database"]
        table = next(iter(yaml.safe_load(open(os.path.join(ROOT, "datasets", first, "tests", "expected_counts.yaml"), encoding="utf-8"))))
        c.expect(q("SELECT 1", user="demo", pw="demo", database=schema).returncode == 0, "demo can connect")
        c.expect(q(f'SELECT count(*) FROM "{table}"', user="demo", pw="demo", database=schema).returncode == 0, "demo can read")
        for statement, label in [
                ("CREATE TABLE nope (i int)", "CREATE"),
                (f'DELETE FROM "{table}"', "DELETE"),
                (f'UPDATE "{table}" SET "{table}" = NULL', "UPDATE"),
                (f'DROP TABLE "{table}"', "DROP")]:
            c.expect(q(statement, user="demo", pw="demo", database=schema).returncode != 0, f"demo cannot {label}")
        w = q("CREATE TABLE t_probe (i int); DROP TABLE t_probe", user="admin", pw="admin", database=schema)
        c.expect(w.returncode == 0, "admin can write" + ("" if w.returncode == 0 else f" -- {w.stderr.strip()[:120]}"))
        # the baked tables are admin's own: the "full access" account can change and remove them
        w = q(f'BEGIN; ALTER TABLE "{table}" ADD COLUMN t_probe int; ALTER TABLE "{table}" DROP COLUMN t_probe; ROLLBACK',
              user="admin", pw="admin", database=schema)
        c.expect(w.returncode == 0, "admin owns the baked tables and can alter them" + ("" if w.returncode == 0 else f" -- {w.stderr.strip()[:120]}"))
        empty = q("SELECT count(*) FROM pg_authid WHERE rolcanlogin AND rolpassword IS NULL").stdout.strip()
        c.expect(empty == "0", "no login role is passwordless")
        size = sh("docker", "exec", NAME, "sh", "-c", "du -sm /var/lib/postgresql/18/docker | cut -f1").stdout.strip()
        n = q("SELECT count(*) FROM pg_database WHERE NOT datistemplate").stdout.strip()
        print(f"  . data directory: {size} MB across {n} databases")
    finally:
        sh("docker", "rm", "-f", NAME)
        sh("docker", "run", "-d", "--name", NAME + "2",
           "--label", "megasamples.transient=true", "--label", "megasamples.role=test",
           "-e", "POSTGRES_PASSWORD=sekret", "-e", "DEMO_PASSWORD=viewer", IMAGE)
        for _ in range(150):
            if q("SELECT 1", pw="sekret", container=NAME + "2").returncode == 0:
                break
            time.sleep(0.2)
        c.expect(q_net("SELECT 1", pw="sekret", container=NAME + "2").returncode == 0,
                 "POSTGRES_PASSWORD override applied by the wrapper (checked over the network)")
        c.expect(q_net("SELECT 1", pw="root", container=NAME + "2").returncode != 0,
                 "the baked default superuser password no longer works after an override")
        c.expect(q_net("SELECT 1", user="demo", pw="viewer", database="megasamples", container=NAME + "2").returncode == 0,
                 "DEMO_PASSWORD override applied")
        c.expect(q_net("SELECT 1", user="demo", pw="demo", database="megasamples", container=NAME + "2").returncode != 0,
                 "the baked demo password no longer works after an override")
        sh("docker", "rm", "-f", NAME + "2")
    print(f"image test: {len(c.failures)} failure(s)")
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
