"""MySQL: the hub engine.

Every dataset's converter emits MySQL SQL; the throwaway build server (server.py) is where it is
loaded (load.py) and verified (megasamples/verify.py); the verified databases are dumped with MySQL
Shell (dump.py) and baked into the image by engines/mysql/Dockerfile. The other engines are ports
of what this one verified.
"""
import os, shutil, subprocess, sys

from megasamples import datasets as inventory, registry, stage as stager, verify as verifier, workspace
from megasamples.engines.base import Engine
from megasamples.engines import expected_tables, unique_databases
from megasamples.engines.mysql import dump as dumper, image_test as tester, load as loader, server
from megasamples.paths import ROOT, engine_build_dir, engine_dir, rel


def link_tree(src, dst):
    """Hardlink a directory tree: the image context gets exactly the dumps being baked, at no cost in
    bytes, and Docker copies a hardlink as an ordinary file."""
    for dirpath, _dirs, files in os.walk(src):
        target = os.path.join(dst, os.path.relpath(dirpath, src))
        os.makedirs(target, exist_ok=True)
        for f in files:
            s, d = os.path.join(dirpath, f), os.path.join(target, f)
            try:
                os.link(s, d)
            except OSError:
                shutil.copy2(s, d)


class MySQL(Engine):
    name = "mysql"
    title = "MySQL"
    version = "9.7.2"
    image = os.environ.get("MEGASAMPLES_MYSQL_IMAGE", "sql-megasamples-mysql:dev")
    container = "megasamples-mysql"
    port = 3306
    hub = True

    # --- building --------------------------------------------------------------------------------
    def build(self, dataset, fresh=False):
        stager.stage(dataset)
        loader.main([dataset] + (["--fresh"] if fresh else []))
        rc = verifier.verify(dataset, engine="mysql")
        if rc == 0:
            # the dump a port restores from (ensure) must be this build, not one an earlier image
            # bake left behind: a live dataset rebuilt from today's feed would otherwise port
            # yesterday's rows, which the ports' check against build/live/ then fails
            from megasamples.engines.mysql import dump as dumper
            dumper.dump(dataset)
        return rc

    def verify(self, dataset, stages=None, pin=False):
        return verifier.verify(dataset, stages, engine="mysql", pin=pin)

    def holds(self, dataset):
        """True when the build server has the dataset: its database, and for an `append: true`
        dataset every table its expected_counts.yaml names, since the base dataset made the database."""
        cfg = inventory.load(dataset)
        schema = cfg["database"]
        server.start()
        if not server.rows(f"SELECT schema_name FROM information_schema.schemata WHERE schema_name = '{schema}'"):
            return False
        if not cfg.get("append"):
            return True
        tables = {r[0] for r in server.rows(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'")}
        return all(t in tables for t in expected_tables(dataset))

    def ensure(self, dataset):
        """The dataset is in the build server when this returns 0: already there, restored from a
        complete dump (what `make image` leaves behind after removing the server), or built."""
        from megasamples.engines import expected_tables
        from megasamples.engines.mysql import dump as dumper, restore as restorer
        if self.holds(dataset):
            return 0
        schema = inventory.load(dataset)["database"]
        if not inventory.load(dataset).get("append") and dumper.complete(schema, expected_tables(dataset)):
            print(f"  . {dataset}: not in the MySQL build server; restoring it from its dump")
            restorer.restore(dataset)
            return 0
        print(f"  . {dataset}: not in the MySQL build server yet; building it there first (the hub)")
        return self.build(dataset)

    def image_build(self, datasets, keep=False, threads=4, from_dumps=False):
        dumps = os.path.join(engine_build_dir(self.name), "dumps")
        databases = unique_databases(datasets)
        if from_dumps:
            missing = [s for s in databases if not os.path.exists(os.path.join(dumps, f"{s}.json"))]
            if missing:
                sys.exit(f"no dump under {rel(dumps)} for: {' '.join(missing)}; build them first")
            print(f"  . baking from the {len(databases)} dump(s) already in {rel(dumps)}")
        else:
            server.start()
            for d in datasets:
                if not inventory.load(d).get("append"):          # the base's dump carries the appended tables
                    dumper.dump(d)
        context = os.path.join(engine_build_dir(self.name), "image")
        shutil.rmtree(context, ignore_errors=True)
        for s in databases:
            link_tree(os.path.join(dumps, s), os.path.join(context, "dumps", s))
        registry.main(list(datasets) + ["--dialect", "mysql", "--out", os.path.join(context, "registry.sql")])
        cmd = ["docker", "build", "-f", os.path.join(engine_dir(self.name), "Dockerfile"),
               "-t", self.image, ROOT]
        print(f"  . docker build -t {self.image} ({len(datasets)} datasets from {rel(context)})")
        if subprocess.run(cmd, cwd=ROOT, env={**os.environ, "DOCKER_BUILDKIT": "1"}).returncode != 0:
            sys.exit(f"docker build failed for {self.image}")
        print(f"  . built {self.image} with: {' '.join(datasets)}")
        if from_dumps:
            pass
        elif keep:
            print("  . keeping the build server up (keep_build_server); `make clean` removes it")
        else:
            print("  . removing the build server; set build.keep_build_server to keep it next time")
            workspace.clean()
        return 0

    def image_test(self, datasets):
        return tester.main(list(datasets))

    # --- running ---------------------------------------------------------------------------------
    def compose_service(self, cfg):
        return {
            "image": f"${{MEGASAMPLES_MYSQL_IMAGE:-{self.image}}}",
            # MySQL sizes its buffer pool from the host's memory rather than the container's, so a
            # limit without an explicit pool size makes it plan for more than it may have
            "mem_limit": "1g",
            "command": ["mysqld", "--innodb-buffer-pool-size=256M"],
            "container_name": self.container,
            "ports": [f"127.0.0.1:{cfg.ports.get('mysql', self.port)}:3306"],
            "environment": {"DEMO_PASSWORD": "${DEMO_PASSWORD:-demo}",
                            "ADMIN_PASSWORD": "${ADMIN_PASSWORD:-admin}"},
            "healthcheck": {"test": ["CMD-SHELL", "mysql -udemo -p\"$$DEMO_PASSWORD\" -e 'SELECT 1'"],
                            "interval": "5s", "timeout": "5s", "retries": 30},
            "restart": "unless-stopped",
        }

    def console_environment(self, console, cfg):
        demo, admin = "${DEMO_PASSWORD:-demo}", "${ADMIN_PASSWORD:-admin}"
        if console == "phpmyadmin":
            # no PMA_USER: the two servers, one per account, are defined in the mounted config
            return {"PMA_HOST": "mysql", "PMA_PORT": "3306", "DEMO_PASSWORD": demo,
                    "ADMIN_PASSWORD": admin, "UPLOAD_LIMIT": "256M"}
        if console == "adminer":
            return {"ADMINER_DEFAULT_SERVER": "mysql"}
        if console == "dbgate":
            return {"CONNECTIONS": "mysql_demo,mysql_admin",
                    "LABEL_mysql_demo": "MySQL (read-only)", "SERVER_mysql_demo": "mysql",
                    "PORT_mysql_demo": "3306", "USER_mysql_demo": "demo", "PASSWORD_mysql_demo": demo,
                    "ENGINE_mysql_demo": "mysql@dbgate-plugin-mysql",
                    "LABEL_mysql_admin": "MySQL (full access)", "SERVER_mysql_admin": "mysql",
                    "PORT_mysql_admin": "3306", "USER_mysql_admin": "admin", "PASSWORD_mysql_admin": admin,
                    "ENGINE_mysql_admin": "mysql@dbgate-plugin-mysql"}
        if console == "cloudbeaver":
            return {
                    "DEMO_PASSWORD": demo, "ADMIN_PASSWORD": admin}
        return {}

    def query(self, container, sql, user="root", password="root"):
        p = subprocess.run(["docker", "exec", container, "mysql", f"-u{user}", f"-p{password}",
                            "-N", "--batch", "-e", sql], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"{container}: {p.stderr.strip()[:200]}")
        return [line.split("\t") for line in p.stdout.splitlines() if line.strip()]

    def registry_rows(self, container):
        return self.query(container, "SELECT name, tier, licenses, row_counts, record "
                                     "FROM megasamples.datasets ORDER BY name")

    def sizes(self, container):
        return {r[0]: (int(r[1]), float(r[2])) for r in self.query(
            container, "SELECT table_schema, COUNT(*), ROUND(SUM(data_length+index_length)/1048576,1) "
                       "FROM information_schema.tables WHERE table_type='BASE TABLE' "
                       "AND table_schema NOT IN ('mysql','information_schema','performance_schema','sys') "
                       "GROUP BY table_schema")}

    def connection_hint(self, cfg):
        from megasamples.engines import first_database
        return f"mysql -h 127.0.0.1 -P {cfg.ports.get('mysql', self.port)} -u demo -pdemo {first_database(cfg, 'mysql')}"


ENGINE = MySQL()
