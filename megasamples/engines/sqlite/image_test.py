#!/usr/bin/env python3
"""S8 for the SQLite image: run it and check the files as a user would receive them.

  python3 -m megasamples test-image --engine sqlite [dataset ...]

Asserts: the container starts and the sqlite3 shell answers; the registry lists exactly the built
datasets; every table's row count matches the pinned expectation; PRAGMA integrity_check passes and
PRAGMA foreign_key_check finds nothing for every file; every file uses the rollback journal.
"""
import os, subprocess, sys, time
import yaml

from megasamples.paths import ROOT
from megasamples.engines import unique_databases
from megasamples.registry import image_counts
from megasamples.engines.image_startup import probe_startup

IMAGE = os.environ.get("MEGASAMPLES_SQLITE_IMAGE", "sql-megasamples-sqlite:dev")
NAME = "megasamples-test-sqlite"


def sh(*args, **kw):
    return subprocess.run(list(args), capture_output=True, text=True, **kw)


def q(sql, database="megasamples", container=NAME):
    return sh("docker", "exec", container, "sqlite3", "-tabs", f"/data/{database}.sqlite", sql)


class Checks:
    def __init__(self): self.failures = []
    def ok(self, label): print(f"  . {label}")
    def fail(self, label): print(f"  x {label}"); self.failures.append(label)
    def expect(self, cond, label): (self.ok if cond else self.fail)(label)


def main(argv=None):
    datasets = list(sys.argv[1:] if argv is None else argv) or ["sakila"]
    c = Checks()
    sh("docker", "rm", "-fv", NAME)
    started = time.monotonic()
    run = sh("docker", "run", "-d", "--name", NAME, "--label", "megasamples.transient=true",
             "--label", "megasamples.role=test", IMAGE)
    if run.returncode != 0:
        sys.exit(f"could not start {IMAGE}: {run.stderr}")
    provisioned = time.monotonic() - started
    try:
        ready = probe_startup(c, "sqlite", started, provisioned, lambda: q("SELECT 1"))
        if ready is None:
            return 1
        registry = q("SELECT name FROM datasets ORDER BY name").stdout.split()
        c.expect(sorted(registry) == sorted(unique_databases(datasets)), f"registry lists exactly the built databases ({len(registry)})")
        total_mb = 0.0
        for name in datasets:
            cfg = yaml.safe_load(open(os.path.join(ROOT, "datasets", name, "dataset.yaml"), encoding="utf-8"))
            db = cfg["database"]
            counts = image_counts(name)
            bad = [f"{t}={q(f'SELECT count(*) FROM \"{t}\"', db).stdout.strip()} want {w}" for t, w in counts.items()
                   if q(f'SELECT count(*) FROM "{t}"', db).stdout.strip() != str(w)]
            c.expect(not bad, f"{db}: {len(counts)} tables match their expected snapshot counts" + (f" -- {bad[:3]}" if bad else ""))
            c.expect(q("PRAGMA integrity_check", db).stdout.strip() == "ok", f"{db}: integrity_check ok")
            c.expect(q("PRAGMA foreign_keys=ON; PRAGMA foreign_key_check", db).stdout.strip() == "",
                     f"{db}: foreign_key_check finds nothing")
            c.expect(q("PRAGMA journal_mode", db).stdout.strip() == "delete", f"{db}: rollback journal")
            total_mb += float(q("SELECT page_count * page_size / 1048576.0 FROM pragma_page_count(), pragma_page_size()", db).stdout.strip() or 0)
        print(f"  . files: {total_mb:,.0f} MB across {len(datasets)} databases; sqlite {q('SELECT sqlite_version()').stdout.strip()}")
    finally:
        sh("docker", "rm", "-fv", NAME)
    print(f"image test: {len(c.failures)} failure(s)")
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
