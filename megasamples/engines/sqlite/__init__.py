"""SQLite: a port of the verified MySQL corpus, one file per database (ARCHITECTURE.md section 4.3).

    port.py        model + dump -> build/sqlite/<dataset>/<database>.sqlite, written with the stdlib driver
    adapter.py     the verification adapter (counts, digests, foreign keys, indexes), digest in Python
    image_test.py  the tests of the data image

There is no build server: the file is the database. The image carries the files under /data with
the sqlite3 command-line shell, so `docker run` and `docker exec` work as they do for the servers.
"""
import os, shutil, sqlite3, subprocess, sys

from megasamples import datasets as inventory, registry, verify as verifier
from megasamples.engines import unique_databases
from megasamples.engines.base import Engine
from megasamples.engines.mysql import server as mysql
from megasamples.engines.sqlite import image_test as tester, port
from megasamples.paths import ROOT, engine_build_dir, engine_dir, rel
from megasamples import container_engine


class SQLite(Engine):
    name = "sqlite"
    title = "SQLite"
    version = sqlite3.sqlite_version
    image = os.environ.get("MEGASAMPLES_SQLITE_IMAGE", "sql-megasamples-sqlite:dev")
    container = "megasamples-sqlite"
    port = 0
    hub = False

    def build(self, dataset, fresh=False):
        from megasamples.engines import get
        rc = get("mysql").ensure(dataset)          # the hub holds it, is restored from its dump, or builds it
        if rc:
            return rc
        port.write(dataset)
        return verifier.verify(dataset, engine=self.name)

    def verify(self, dataset, stages=None, pin=False):
        return verifier.verify(dataset, stages, engine=self.name, pin=pin)

    def image_build(self, datasets, keep=False, threads=4, from_dumps=False):
        context = os.path.join(engine_build_dir(self.name), "image")
        shutil.rmtree(context, ignore_errors=True)
        os.makedirs(os.path.join(context, "data"))
        for database in unique_databases(datasets):
            src = os.path.join(engine_build_dir(self.name), database, f"{database}.sqlite")
            if not os.path.exists(src):
                sys.exit(f"no SQLite port of `{database}` at {rel(src)}; run: make build ENGINE=sqlite D=<dataset>")
            os.link(src, os.path.join(context, "data", f"{database}.sqlite"))
        port.write_registry(os.path.join(context, "data", "megasamples.sqlite"), datasets)
        cmd = ["docker", "build", "-f", os.path.join(engine_dir(self.name), "Dockerfile"), "-t", self.image, ROOT]
        print(f"  . docker build -t {self.image} ({len(datasets)} datasets from {rel(context)})")
        if subprocess.run(cmd, cwd=ROOT, env=container_engine.build_env()).returncode != 0:
            sys.exit(f"docker build failed for {self.image}")
        print(f"  . built {self.image} with: {' '.join(datasets)}")
        return 0

    def image_test(self, datasets):
        return tester.main(list(datasets))

    def compose_service(self, cfg):
        # a container that holds the files: `docker exec megasamples-sqlite sqlite3 /data/sakila.sqlite`
        # is the client. At start it copies the image's files into the named volume the consoles
        # mount, so a rebuilt image replaces what they see rather than leaving a stale volume behind.
        # Each file is copied under a temporary name and moved into place, and a marker is written
        # last: the health check waits for the marker, so a console never opens a half-copied file
        # and `up --wait` waits for the whole 900 MB rather than for the first file. The copy of
        # that much data was OOM-killed under a 64 MB limit on the first start (2026-09-10), so the
        # limit is 256 MB and the health check has a start period long enough for a slow disk.
        # `$$`: Compose interpolates a single `$` in compose.yaml; the doubled one reaches the shell
        copy = ("rm -f /shared/.complete; for f in /data/*.sqlite; do n=$$(basename \"$$f\"); "
                "cp -f \"$$f\" \"/shared/.$$n.part\" && mv -f \"/shared/.$$n.part\" \"/shared/$$n\" || exit 1; done; "
                "touch /shared/.complete && exec sleep infinity")
        return {
            "image": f"${{MEGASAMPLES_SQLITE_IMAGE:-{self.image}}}",
            "mem_limit": "256m",
            "container_name": self.container,
            "command": ["sh", "-c", copy],
            "volumes": ["megasamples-sqlite:/shared"],
            "healthcheck": {"test": ["CMD-SHELL", "test -f /shared/.complete"],
                            "interval": "5s", "timeout": "5s", "retries": 12, "start_period": "180s"},
            "restart": "unless-stopped",
        }

    def console_environment(self, console, cfg):
        if console == "dbgate":
            names = [inventory.load(d)["database"] for d in cfg.datasets("sqlite")]
            env = {"CONNECTIONS": ",".join(f"sqlite_{n}" for n in names)}
            for n in names:
                env[f"LABEL_sqlite_{n}"] = f"SQLite {n}"
                env[f"FILE_sqlite_{n}"] = f"/data/{n}.sqlite"
                env[f"ENGINE_sqlite_{n}"] = "sqlite@dbgate-plugin-sqlite"
            return env
        return {}

    def query(self, container, sql, database="megasamples"):
        p = subprocess.run(["docker", "exec", container, "sqlite3", "-tabs", f"/data/{database}.sqlite", sql],
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"{container}: {p.stderr.strip()[:200]}")
        return [line.split("\t") for line in p.stdout.splitlines() if line.strip()]

    def registry_rows(self, container):
        return self.query(container, "SELECT name, tier, licenses, row_counts, record FROM datasets ORDER BY name")

    def sizes(self, container):
        out = {}
        for (name,) in self.query(container, "SELECT name FROM datasets"):
            tables = int(self.query(container, "SELECT count(*) FROM sqlite_master WHERE type='table'", name)[0][0])
            mb = float(self.query(container, "SELECT round(page_count * page_size / 1048576.0, 1) FROM pragma_page_count(), pragma_page_size()", name)[0][0])
            out[name] = (tables, mb)
        return out

    def connection_hint(self, cfg):
        from megasamples.engines import first_database
        return f"docker exec -it megasamples-sqlite sqlite3 /data/{first_database(cfg, 'sqlite')}.sqlite"


ENGINE = SQLite()
