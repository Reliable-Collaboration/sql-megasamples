#!/usr/bin/env python3
"""S8: image-level tests. Runs the built image and checks it as a user would receive it.

  python3 -m megasamples test-image sakila chinook northwind pubs

Asserts: the container answers a real query within the time budget (not `mysqladmin ping`, which
succeeds on access-denied); every expected database is present and matches the registry; row counts
match each dataset's pinned expectations; `demo` can read and cannot write, including through a
routine; unkeyed accounts are declared and locked; CHECK TABLE passes; CONVERT_TZ works; the password
override env vars take effect.
"""
import json, os, subprocess, sys, time
import yaml

from megasamples import config
from megasamples.copy_config import CopySettings
from megasamples.paths import ROOT
from megasamples.credentials import client, environment_file, session
from megasamples.engines import unique_databases
from megasamples.registry import image_counts
from megasamples.engines.image_startup import probe_startup
IMAGE = os.environ.get("MEGASAMPLES_MYSQL_IMAGE", "sql-megasamples-mysql:dev")
NAME = "megasamples-test-mysql"


def sh(*args, **kw):
    return subprocess.run(list(args), capture_output=True, text=True, **kw)


def q(sql, user="root", pw="root", database=None, container=NAME):
    with client("mysql", container, user, pw) as command:
        return sh(*command, "-N", "--batch", *(["-D", database] if database else []), "-e", sql)



def expected_demo_grants(datasets, foreign=()):
    # mysql --batch renders each literal backslash as two backslashes.
    schemas = [*unique_databases(datasets), *(prefix + "_%" for prefix, readable in foreign if readable)]
    scopes = [schema.replace("_", r"\\_") for schema in schemas]
    principal = ' TO `demo`@`%`'
    return {grant + principal for grant in [
        'GRANT USAGE ON *.*',
        'GRANT SELECT ON `megasamples`.`copy_service`',
        'GRANT SELECT ON `megasamples`.`datasets`',
        *(f'GRANT SELECT, SHOW VIEW ON `{scope}`.*' for scope in scopes),
    ]}


class Checks:
    def __init__(self): self.failures = []
    def ok(self, label): print(f"  . {label}")
    def fail(self, label): print(f"  x {label}"); self.failures.append(label)
    def expect(self, cond, label): (self.ok if cond else self.fail)(label)


def account_checks(checks, schema, read_table, expected_count):
    """Exercise valid statements against fixtures in a database this image actually carries."""
    reader, writer = "demo", "admin"
    table = f"`{schema}`.`_megasamples_access_probe`"
    created = f"`{schema}`.`_megasamples_create_probe`"
    routine = f"`{schema}`.`_megasamples_write_probe`"
    try:
        setup = q(f"CREATE TABLE {table} (id integer PRIMARY KEY, n integer); "
                  f"INSERT INTO {table} VALUES (1, 1)")
        checks.expect(setup.returncode == 0, "account probe table exists in a shipped database")
        if setup.returncode:
            return
        setup = q(f"CREATE PROCEDURE {routine}() INSERT INTO {table} VALUES (3, 3)")
        checks.expect(setup.returncode == 0, "account probe routine exists")
        if setup.returncode:
            return
        checks.expect(q("SELECT 1", user=reader, pw=reader).returncode == 0, "demo can connect")
        result = q(f"SELECT COUNT(*) FROM `{schema}`.`{read_table}`", user=reader, pw=reader)
        checks.expect(result.returncode == 0 and result.stdout.strip() == str(expected_count), "demo can read")
        for statement, label in [
                (f"CREATE TABLE {created} (id integer)", "CREATE"),
                (f"INSERT INTO {table} VALUES (2, 2)", "INSERT"),
                (f"UPDATE {table} SET n=2 WHERE id=1", "UPDATE"),
                (f"DELETE FROM {table} WHERE id=1", "DELETE"),
                (f"DROP TABLE {table}", "DROP")]:
            checks.expect(q(statement, user=reader, pw=reader).returncode != 0, f"demo cannot {label}")
        checks.expect(q(f"CALL {routine}()", user=reader, pw=reader).returncode != 0,
                      "demo cannot write through a routine")
        checks.expect(q(f"INSERT INTO {table} VALUES (2, 2)", user=writer, pw=writer).returncode == 0,
                      "admin can write")
    finally:
        q(f"DROP PROCEDURE IF EXISTS {routine}")
        q(f"DROP TABLE IF EXISTS {table}, {created}")


@session()
def main(argv=None):
    datasets = list(sys.argv[1:] if argv is None else argv) or ["sakila"]
    c = Checks()
    filesystem = sh("docker", "run", "--rm", "--network", "none", "--entrypoint", "sh", IMAGE,
                    "-ec", "test -d /var/lib/mysql/mysql; test ! -e /var/lib/mysql/auto.cnf; "
                           "test ! -L /var/lib/mysql/auto.cnf")
    c.expect(filesystem.returncode == 0, "the image has no baked auto.cnf before server startup")
    sh("docker", "rm", "-fv", NAME)
    started = time.monotonic()
    run = sh("docker", "run", "-d", "--name", NAME,
             "--label", "megasamples.transient=true", "--label", "megasamples.role=test",
             IMAGE)
    if run.returncode != 0:
        sys.exit(f"could not start {IMAGE}: {run.stderr}")
    provisioned = time.monotonic() - started
    try:
        ready = probe_startup(c, "mysql", started, provisioned, lambda: q("SELECT 1"))
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

        grants = q("SHOW GRANTS", user="demo", pw="demo")
        settings = CopySettings(config.load(), "mysql", datasets)
        c.expect(grants.returncode == 0 and set(grants.stdout.splitlines()) ==
                 expected_demo_grants(datasets, settings.foreign),
                 "demo holds exactly the configured read grants")
        for database in [*unique_databases(datasets), "megasamples"]:
            result = q("CREATE TEMPORARY TABLE read_probe(i int)", user="demo", pw="demo", database=database)
            c.expect(result.returncode != 0 and "denied" in result.stderr.lower(),
                     f"{database}: demo cannot create temporary objects")

        first_counts = image_counts(datasets[0])
        read_table = sorted(first_counts)[0]
        account_checks(c, unique_databases(datasets)[0], read_table, first_counts[read_table])

        empty = q("SELECT user,host,account_locked FROM mysql.user WHERE authentication_string='' "
                  "AND user NOT LIKE 'mysql.%'")
        declared = {item.owner for item in settings.namespaces} | settings.readers.keys() | settings.writers.keys()
        allowed = {f"{account}\t%\tY" for account in declared}
        c.expect(empty.returncode == 0 and set(empty.stdout.splitlines()) <= allowed,
                 "every unkeyed account is declared and locked")
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
        sh("docker", "rm", "-fv", NAME)
        with environment_file({"MYSQL_ROOT_PASSWORD": "sekret", "DEMO_PASSWORD": "viewer"}) as path:
            sh("docker", "run", "-d", "--name", NAME + "2",
               "--label", "megasamples.transient=true", "--label", "megasamples.role=test",
               "--env-file", path, IMAGE)
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
        sh("docker", "rm", "-fv", NAME + "2")

    print(f"image test: {len(c.failures)} failure(s)")
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
