"""Raw clients for disposable DL-077 gate targets."""

import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

OWNER_LABEL = "org.sql-megasamples.gates.owner"
MIN_AVAILABLE_KIB = 15 * 1024 * 1024
TARGET_ENV = "DL077_GATE_TARGET"
class Unavailable(Exception):
    pass


class ControlNotShown(Exception):
    pass


def require(condition, reason):
    if not condition:
        raise AssertionError(reason)


def same(actual, expected):
    require(actual == expected, f"expected {expected!r}, observed {actual!r}")


def capacity():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            available = int(line.split()[1])
            if available >= MIN_AVAILABLE_KIB:
                return
            raise Unavailable(f"MemAvailable={available} KiB is below 15 GiB")
    raise Unavailable("MemAvailable could not be read")


def checked(result):
    require(result.returncode == 0, f"client exited {result.returncode}")
    return result.stdout.strip()


def denied(result, code):
    require(result.returncode != 0, "statement unexpectedly succeeded")
    pattern = rf"(?:ERROR|FATAL):\s+{code}:|ERROR {code} \("
    # psql's connection handshake runs before its verbose error setting is used.
    startup = {
        "55000": r"FATAL:\s+database .* is not currently accepting connections",
        "42501": r"FATAL:\s+permission denied for database",
    }
    if code in startup:
        pattern += "|" + startup[code]
    require(re.search(pattern, result.stderr), f"expected server error {code}")


class Target:
    def __init__(self):
        name = os.environ.get(TARGET_ENV)
        if not name:
            raise Unavailable(f"set {TARGET_ENV} to an explicitly provisioned scratch target")
        config = Path(name)
        if not config.is_file() or config.stat().st_mode & 0o077:
            raise Unavailable("target manifest must be a private file")
        self.config = json.loads(config.read_text())
        self.env_script = Path(self.config["env_script"]).resolve(strict=True)
        self.owner = self.config["owner"]
        if not re.fullmatch(r"dl077-[a-z0-9-]{8,}", self.owner):
            raise Unavailable("missing task ownership marker")
        self.containers = {}
        self.private_values = set()
        identity = subprocess.run(self.podman_args("info", "--format", "{{.Store.GraphRoot}}"),
                                  capture_output=True, text=True, timeout=15)
        if identity.returncode:
            print("$ podman info --format '{{.Store.GraphRoot}}'", flush=True)
            print(f"exit {identity.returncode}", flush=True)
            self.safe_print(identity.stderr.strip())
            raise Unavailable("isolated Podman store could not be opened")
        if Path(identity.stdout.strip()).resolve() != Path(self.config["graph_root"]).resolve(strict=True):
            raise Unavailable("Podman store did not match the target manifest")

    def safe_print(self, value):
        for private in self.private_values:
            value = value.replace(private, "<port>")
        print(value, flush=True)

    def podman_args(self, *args):
        return [
            "bash", "-c", 'source "$1" || exit; shift; exec podman "$@"',
            "dl077", str(self.env_script), *args,
        ]

    def podman(self, *args, stdin=None, timeout=90, show_input=True, show_output=True):
        if args and args[0] in ("run", "start", "restart"):
            capacity()
        self.safe_print(f"$ podman {shlex.join(args)}")
        if stdin and show_input:
            self.safe_print(stdin.strip())
        binary = isinstance(stdin, bytes)
        result = subprocess.run(
            self.podman_args(*args), input=stdin, text=not binary,
            capture_output=True, timeout=timeout,
        )
        if binary:
            result.stdout = result.stdout.decode(errors="replace")
            result.stderr = result.stderr.decode(errors="replace")
        print(f"exit {result.returncode}", flush=True)
        if show_output:
            for output in (result.stdout, result.stderr):
                if output:
                    self.safe_print(output.rstrip())
        return result

    def container(self, key):
        if key not in self.containers:
            if key not in self.config["containers"]:
                raise Unavailable(f"scratch target has no {key} container")
            name = self.config["containers"][key]
            inspection = self.podman(
                "inspect", "--type", "container", "--format",
                '{{.Id}} {{index .Config.Labels "' + OWNER_LABEL + '"}}', name,
            )
            if inspection.returncode:
                raise Unavailable(f"could not inspect the {key} scratch container")
            fields = inspection.stdout.strip().split()
            if len(fields) != 2 or fields[1] != self.owner:
                raise Unavailable(f"{key} container has no matching ownership marker")
            self.containers[key] = fields[0]
        return self.containers[key]

    def psql_args(self, database="postgres", user="postgres", key="postgres", *extra):
        return (
            "exec", "-i", self.container(key), "psql", "-X", "--no-password",
            "--no-align", "--tuples-only", "--quiet", "--set=ON_ERROR_STOP=1",
            "--set=VERBOSITY=verbose", "-U", user, "-d", database, *extra,
        )

    def pg(self, sql, database="postgres", user="postgres", key="postgres"):
        return self.podman(*self.psql_args(database, user, key), stdin=sql + "\n")

    def image(self, key):
        return checked(self.podman(
            "inspect", "--type", "container", "--format", "{{.Image}}", self.container(key),
        ))

    def mounts(self, key):
        result = subprocess.run(self.podman_args(
            "inspect", "--type", "container", "--format", "{{json .Mounts}}", self.container(key),
        ), capture_output=True, text=True, timeout=10)
        mounts = checked(result)
        return {entry["Destination"]: entry["Source"] for entry in json.loads(mounts) or []}

    def ipv4(self, key):
        result = subprocess.run(self.podman_args(
            "inspect", "--type", "container", "--format", "{{json .NetworkSettings.Networks}}",
            self.container(key),
        ), capture_output=True, text=True, timeout=10)
        networks = json.loads(checked(result))
        addresses = {network["IPAddress"] for network in networks.values() if network["IPAddress"]}
        if not addresses or not all(re.fullmatch(r"[0-9.]+", addr) for addr in addresses):
            raise Unavailable(f"{key} has no IPv4 address on the scratch stack")
        self.private_values.update(addresses)
        return addresses

    def pg_restore_archive(self, source, key="postgres"):
        args = ("exec", self.container(key), "pg_dump", "-U", "postgres", "-Fc", source)
        self.safe_print(f"$ podman {shlex.join(args)}")
        result = subprocess.run(self.podman_args(*args), capture_output=True, timeout=180)
        require(result.returncode == 0 and result.stdout.startswith(b"PGDMP"),
                "pg_dump did not produce a native archive")
        print(f"pg_dump produced {len(result.stdout)} archive bytes", flush=True)
        return result.stdout

    def pg_database_dirs(self, key):
        rows = checked(self.podman(
            "exec", "--user", "postgres", self.container(key), "sh", "-ec",
            'find "$PGDATA/base" -mindepth 1 -maxdepth 1 -type d -printf "%f\\n" | sort',
        ))
        directories = set(rows.splitlines())
        require(directories and all(value.isdecimal() for value in directories),
                "could not enumerate PostgreSQL database directories")
        return directories

    def pg_network_args(self, database, user, route):
        if route == "network":
            peer = self.container("postgres_peer")
            server = self.config["containers"]["postgres"]
            self.container("postgres")
            args = ("-h", server)
        else:
            peer = self.container("postgres_published_peer")
            args = ("-h", "127.0.0.1", "-p", str(self.published_port("postgres", "5432")))
        return (
            "exec", "-i", peer, "psql", "-X", "--no-password", "-Atq",
            "--set=ON_ERROR_STOP=1", "-U", user, "-d", database, *args,
        )

    def pg_network(self, sql, database, user, route):
        return self.podman(*self.pg_network_args(database, user, route), stdin=sql + "\n")

    def published_port(self, key, internal_port):
        result = subprocess.run(self.podman_args(
            "port", self.container(key), f"{internal_port}/tcp",
        ), capture_output=True, text=True, timeout=10)
        output = result.stdout.strip()
        if result.returncode or not re.fullmatch(r"127\.0\.0\.1:[0-9]+", output):
            raise Unavailable(f"{key} has no unambiguous loopback publication")
        port = int(output.split(":")[1])
        self.private_values.add(str(port))
        return port

    def mysql_args(self, database=None, user="root", key="mysql"):
        options = ()
        if user in ("root", "admin", "demo"):
            options = (f"--defaults-extra-file=/run/dl077/mysql-{user}.cnf",)
        args = (
            "exec", "-i", self.container(key), "mysql", *options,
            "--batch", "--raw", "--skip-column-names", "--skip-reconnect", "--unbuffered",
            "--protocol=socket", "-u", user,
        )
        return args + ((database,) if database else ())

    def mysql(self, sql, database=None, user="root", key="mysql"):
        return self.podman(*self.mysql_args(database, user, key), stdin=sql + "\n")

    def mysql_dump(self, key, database):
        args = (
            "exec", self.container(key), "mysqldump", "--defaults-extra-file=/run/dl077/mysql-root.cnf",
            "--protocol=socket", "--single-transaction", "--no-tablespaces",
            "--skip-lock-tables", "--add-drop-database", "--databases", database,
        )
        self.safe_print(f"$ podman {shlex.join(args)}")
        result = subprocess.run(self.podman_args(*args), capture_output=True, timeout=180)
        require(result.returncode == 0 and b"DROP DATABASE" in result.stdout,
                "mysqldump did not produce a database replacement stream")
        print(f"mysqldump produced {len(result.stdout)} bytes", flush=True)
        return result.stdout

    def mysql_network_args(self, user, route):
        if route == "network":
            peer = self.container("mysql_peer")
            self.container("mysql")
            host = self.config["containers"]["mysql"]
            port = "3306"
        else:
            peer = self.container("mysql_published_peer")
            host = "127.0.0.1"
            port = str(self.published_port("mysql", "3306"))
        return (
            "exec", "-i", peer, "mysql", f"--defaults-extra-file=/run/dl077/mysql-{user}.cnf",
            "--protocol=TCP", "-h", host, "-P", port, "-u", user, "--batch",
            "--skip-column-names", "--skip-reconnect", "--unbuffered",
        )

    def mysql_network(self, sql, user, route):
        return self.podman(*self.mysql_network_args(user, route), stdin=sql + "\n")

    def restart(self, key, probe):
        checked(self.podman("restart", self.container(key), timeout=180))
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if probe().returncode == 0:
                return
            time.sleep(1)
        raise Unavailable(f"{key} did not recover after restart")


def run(gate, case):
    target = None
    try:
        target = Target()
        case(target)
    except Unavailable as error:
        print(f"{gate}: Not run ({error}); control not shown", file=sys.stderr)
        return 77
    except ControlNotShown as error:
        print(f"{gate}: Not run ({error}); control not shown", file=sys.stderr)
        return 77
    except (AssertionError, subprocess.TimeoutExpired) as error:
        if target:
            target.safe_print(f"{gate}: Failed ({error}); control not shown")
        else:
            print(f"{gate}: Not run (could not verify the scratch target); control not shown", file=sys.stderr)
            return 77
        return 1
    except (OSError, KeyError, ValueError) as error:
        print(f"{gate}: Not run ({type(error).__name__} in scratch setup); control not shown", file=sys.stderr)
        return 77
    print(f"{gate}: Passed; control shown")
    return 0
