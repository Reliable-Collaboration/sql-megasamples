#!/usr/bin/env python3
"""S8: image-level tests. Runs the built image and checks it as a user would receive it.

  python3 -m megasamples test-image sakila chinook northwind pubs

Asserts: the container answers a real query within the time budget (not `mysqladmin ping`, which
succeeds on access-denied); every expected database is present and matches the registry; row counts
match each dataset's pinned expectations; `demo` can read and cannot write, including through a
routine; no account has an empty password; CHECK TABLE passes; CONVERT_TZ works; and the password
override env vars take effect.
"""
import json, os, subprocess, sys, time
import yaml

from megasamples.paths import ROOT
from megasamples.engines import unique_databases
from megasamples.registry import image_counts
IMAGE = os.environ.get("MEGASAMPLES_MYSQL_IMAGE", "sql-megasamples-mysql:dev")
NAME = "megasamples-test-mysql"
BUDGET_SECONDS = 30


def sh(*args, **kw):
    return subprocess.run(list(args), capture_output=True, text=True, **kw)


def q(sql, user="root", pw="root", database=None, container=NAME):
    cmd = ["docker", "exec", container, "mysql", f"-u{user}", f"-p{pw}", "-N", "--batch"]
    if database:
        cmd += ["-D", database]
    cmd += ["-e", sql]
    return sh(*cmd)


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
             "--label", "megasamples.transient=true", "--label", "megasamples.role=test",
             "-e", "MYSQL_ROOT_PASSWORD=root", IMAGE)
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
            print(sh("docker", "logs", "--tail", "30", NAME).stdout); sys.exit(1)

        # the entrypoint must not have re-initialised the shipped data directory
        logs = sh("docker", "logs", NAME).stdout + sh("docker", "logs", NAME).stderr
        c.expect("Initializing database" not in logs, "entrypoint did not re-initialise the datadir")

        registry = q("SELECT name FROM megasamples.datasets ORDER BY name").stdout.split()
        c.expect(sorted(registry) == sorted(unique_databases(datasets)),
                 f"registry lists exactly the built databases ({len(registry)})")

        for name in datasets:
            cfg = yaml.safe_load(open(os.path.join(ROOT, "datasets", name, "dataset.yaml"), encoding="utf-8"))
            schema = cfg["database"]
            counts = image_counts(name)
            bad = []
            for table, want in counts.items():
                got = q(f"SELECT COUNT(*) FROM `{table}`", database=schema).stdout.strip()
                if got != str(want):
                    bad.append(f"{table}={got} want {want}")
            c.expect(not bad, f"{schema}: {len(counts)} tables match their expected snapshot counts"
                              + (f" -- {bad[:3]}" if bad else ""))
            check = q(f"SELECT CONCAT(table_name) FROM information_schema.tables "
                      f"WHERE table_schema='{schema}' AND table_type='BASE TABLE'").stdout.split()
            broken = [t for t in check
                      if "OK" not in q(f"CHECK TABLE `{t}`", database=schema).stdout]
            c.expect(not broken, f"{schema}: CHECK TABLE passes for {len(check)} tables")

            # A foreign key into another database is only resolved when both are present, and the
            # image loads each dataset from its own dump, so this is where it could quietly be lost.
            external = q("SELECT CONCAT(rc.constraint_name, ' ', kcu.referenced_table_schema, '.', "
                         "rc.referenced_table_name, ' ', kcu.column_name, ' ', "
                         "kcu.referenced_column_name, ' ', rc.table_name) "
                         "FROM information_schema.referential_constraints rc "
                         "JOIN information_schema.key_column_usage kcu "
                         "USING (constraint_schema, constraint_name) "
                         f"WHERE rc.constraint_schema='{schema}' "
                         f"AND kcu.referenced_table_schema<>'{schema}'").stdout.split("\n")
            external = [line.split() for line in external if line.strip()]
            if external:
                orphaned = []
                for name, target, col, rcol, table in external:
                    rschema, rtable = target.split(".")
                    n = q(f"SELECT COUNT(*) FROM `{schema}`.`{table}` c "
                          f"LEFT JOIN `{rschema}`.`{rtable}` p ON c.`{col}` = p.`{rcol}` "
                          f"WHERE c.`{col}` IS NOT NULL AND p.`{rcol}` IS NULL").stdout.strip()
                    if n != "0":
                        orphaned.append(f"{name} has {n} orphans")
                c.expect(not orphaned, f"{schema}: {len(external)} cross-database foreign key(s) "
                                       f"present with no orphans" + (f" -- {orphaned}" if orphaned else ""))

        c.expect(q("SELECT 1", user="demo", pw="demo").returncode == 0, "demo can connect")
        c.expect(q("SELECT COUNT(*) FROM sakila.actor", user="demo", pw="demo").returncode == 0,
                 "demo can read")
        for statement, label in [
                ("CREATE TABLE sakila.nope (i INT)", "CREATE"),
                ("INSERT INTO sakila.actor (first_name,last_name) VALUES ('a','b')", "INSERT"),
                ("UPDATE sakila.actor SET first_name='x' WHERE actor_id=1", "UPDATE"),
                ("DELETE FROM sakila.actor WHERE actor_id=1", "DELETE"),
                ("DROP DATABASE sakila", "DROP")]:
            c.expect(q(statement, user="demo", pw="demo").returncode != 0, f"demo cannot {label}")
        c.expect(q("CALL sakila.rewards_report(1,1,'2005-01-01')", user="demo", pw="demo").returncode != 0,
                 "demo cannot write through a routine")

        empty = q("SELECT COUNT(*) FROM mysql.user WHERE authentication_string='' "
                  "AND user NOT LIKE 'mysql.%'").stdout.strip()
        c.expect(empty == "0", "no account has an empty password")
        c.expect(q("SELECT CONVERT_TZ('2026-01-01 00:00:00','UTC','America/Chicago')")
                 .stdout.strip() == "2025-12-31 18:00:00", "CONVERT_TZ works (time-zone tables loaded)")
        c.expect(q("SELECT SHA2('a',256)").returncode == 0, "SHA2 available (SSL build)")

        # The data directory on disk, not information_schema: after a dump load the table
        # statistics have not been gathered, and they under-report by a wide margin (667 MB against
        # a real 1,785 MB when this was last measured). The datadir is also what a user pays for.
        datadir = sh("docker", "exec", NAME, "sh", "-c",
                     "du -sm /var/lib/mysql | cut -f1").stdout.strip()
        databases = q("SELECT COUNT(DISTINCT table_schema) FROM information_schema.tables "
                      "WHERE table_schema NOT IN "
                      "('mysql','information_schema','performance_schema','sys')").stdout.strip()
        print(f"  . data directory: {datadir} MB across {databases} databases")
    finally:
        # the override path needs its own container
        sh("docker", "rm", "-f", NAME)
        sh("docker", "run", "-d", "--name", NAME + "2",
           "--label", "megasamples.transient=true", "--label", "megasamples.role=test",
           "-e", "MYSQL_ROOT_PASSWORD=sekret", "-e", "DEMO_PASSWORD=viewer", IMAGE)
        for _ in range(150):
            if q("SELECT 1", pw="sekret", container=NAME + "2").returncode == 0:
                break
            time.sleep(0.2)
        c.expect(q("SELECT 1", pw="sekret", container=NAME + "2").returncode == 0,
                 "MYSQL_ROOT_PASSWORD override applied by the wrapper")
        c.expect(q("SELECT 1", pw="root", container=NAME + "2").returncode != 0,
                 "the baked default root password no longer works after an override")
        c.expect(q("SELECT 1", user="demo", pw="viewer", container=NAME + "2").returncode == 0,
                 "DEMO_PASSWORD override applied")
        sh("docker", "rm", "-f", NAME + "2")

    print(f"image test: {len(c.failures)} failure(s)")
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
