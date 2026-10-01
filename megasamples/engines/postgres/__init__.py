"""PostgreSQL: a port of the verified MySQL corpus (ARCHITECTURE.md section 4.2).

    server.py      the throwaway build server and psql helpers
    port.py        model + dump -> build/postgres/<dataset>/ files, loaded with \\copy
    adapter.py     the verification adapter (counts, digests, foreign keys, indexes)
    image_test.py  the image-level tests

Building a dataset here means: make sure the hub holds it (loaded and verified in the MySQL build
server), port it, load it into the PostgreSQL build server, verify it against the same expectations.
"""
import os, shutil, subprocess, sys

from megasamples import datasets as inventory, registry, verify as verifier, workspace
from megasamples.engines import unique_databases
from megasamples.engines.base import Engine
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import image_test as tester, port, server
from megasamples.paths import ROOT, engine_build_dir, engine_dir, rel
from megasamples import container_engine


class Postgres(Engine):
    name = "postgres"
    title = "PostgreSQL"
    version = "18.6"
    image = os.environ.get("MEGASAMPLES_POSTGRES_IMAGE", "sql-megasamples-postgres:dev")
    container = "megasamples-postgres"
    port = 5432
    hub = False

    def build(self, dataset, fresh=False):
        from megasamples.engines import get
        rc = get("mysql").ensure(dataset)          # the hub holds it, is restored from its dump, or builds it
        if rc:
            return rc
        if fresh:
            server.start(fresh=True)
        port.write_files(dataset)
        port.load(dataset)
        return verifier.verify(dataset, engine=self.name)

    def verify(self, dataset, stages=None, pin=False):
        return verifier.verify(dataset, stages, engine=self.name, pin=pin)

    def image_build(self, datasets, keep=False, threads=4, from_dumps=False):
        from megasamples.engines.mysql import link_tree
        context = os.path.join(engine_build_dir(self.name), "image")
        shutil.rmtree(context, ignore_errors=True)
        os.makedirs(context)
        for s in unique_databases(datasets):
            src = os.path.join(engine_build_dir(self.name), s)
            if not os.path.exists(os.path.join(src, "complete")):
                sys.exit(f"no complete PostgreSQL port of `{s}` under {rel(src)}; run: make build ENGINE=postgres D=<dataset>")
            link_tree(src, os.path.join(context, s))
        with open(os.path.join(context, "registry.sql"), "w", encoding="utf-8") as fh:
            fh.write(registry.render(datasets, os.environ.get("MEGASAMPLES_BUILD_ID", "dev"), "postgres", "postgres"))
        cmd = ["docker", "build", "-f", os.path.join(engine_dir(self.name), "Dockerfile"), "-t", self.image, ROOT]
        print(f"  . docker build -t {self.image} ({len(datasets)} datasets from {rel(context)})")
        if subprocess.run(cmd, cwd=ROOT, env=container_engine.build_env()).returncode != 0:
            sys.exit(f"docker build failed for {self.image}")
        print(f"  . built {self.image} with: {' '.join(datasets)}")
        if not keep and not from_dumps:
            print("  . removing the build servers; set build.keep_build_server to keep them next time")
            workspace.clean()
        return 0

    def image_test(self, datasets):
        return tester.main(list(datasets))

    def compose_service(self, cfg):
        return {
            "image": f"${{MEGASAMPLES_POSTGRES_IMAGE:-{self.image}}}",
            "mem_limit": "1g",
            "container_name": self.container,
            "ports": [f"127.0.0.1:{cfg.ports.get('postgres', self.port)}:5432"],
            "environment": {"DEMO_PASSWORD": "${DEMO_PASSWORD:-demo}",
                            "ADMIN_PASSWORD": "${ADMIN_PASSWORD:-admin}"},
            "healthcheck": {"test": ["CMD-SHELL", "PGPASSWORD=\"$$DEMO_PASSWORD\" psql -h 127.0.0.1 -U demo -d megasamples -tAc 'SELECT 1'"],
                            "interval": "5s", "timeout": "5s", "retries": 30},
            "restart": "unless-stopped",
        }

    def console_environment(self, console, cfg):
        demo, admin = "${DEMO_PASSWORD:-demo}", "${ADMIN_PASSWORD:-admin}"
        if console == "adminer" and "mysql" not in cfg.engines:
            # the login form defaults to the hub when MySQL is in the stack; every engine's details
            # and a filled-in link are on the landing site's adminer.html either way
            return {} if "mysql" in cfg.engines else {"ADMINER_DEFAULT_SERVER": "postgres", "ADMINER_DEFAULT_DRIVER": "pgsql"}
        if console == "dbgate":
            return {"CONNECTIONS": "postgres_demo,postgres_admin",
                    "LABEL_postgres_demo": "PostgreSQL (read-only)", "SERVER_postgres_demo": "postgres",
                    "PORT_postgres_demo": "5432", "USER_postgres_demo": "demo", "PASSWORD_postgres_demo": demo,
                    "ENGINE_postgres_demo": "postgres@dbgate-plugin-postgres",
                    "LABEL_postgres_admin": "PostgreSQL (full access)", "SERVER_postgres_admin": "postgres",
                    "PORT_postgres_admin": "5432", "USER_postgres_admin": "admin", "PASSWORD_postgres_admin": admin,
                    "ENGINE_postgres_admin": "postgres@dbgate-plugin-postgres"}
        if console == "cloudbeaver":
            return {"DEMO_PASSWORD": demo, "ADMIN_PASSWORD": admin}
        return {}

    def query(self, container, sql, database="megasamples", user="postgres", password="root"):
        p = subprocess.run(["docker", "exec", "-e", f"PGPASSWORD={password}", container, "psql", "-h", "127.0.0.1",
                            "-U", user, "-d", database, "-tAF", "\t", "-c", sql], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"{container}: {p.stderr.strip()[:200]}")
        return [line.split("\t") for line in p.stdout.splitlines() if line.strip()]

    def registry_rows(self, container):
        return self.query(container, "SELECT name, tier, licenses::text, row_counts::text, record FROM datasets ORDER BY name")

    def sizes(self, container):
        out = {}
        for (name,) in self.query(container, "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname NOT IN ('postgres','megasamples')"):
            tables = int(self.query(container, "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'", database=name)[0][0])
            mb = float(self.query(container, f"SELECT round(pg_database_size('{name}')/1048576.0, 1)")[0][0])
            out[name] = (tables, mb)
        return out

    def connection_hint(self, cfg):
        from megasamples.engines import first_database
        return f"PGPASSWORD=demo psql -h 127.0.0.1 -p {cfg.ports.get('postgres', self.port)} -U demo {first_database(cfg, 'postgres')}"


ENGINE = Postgres()
