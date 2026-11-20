"""G-16. Test whether MySQL can retain demo sign-in while refusing its password change."""

import re
import uuid
from pathlib import Path

from consoles import console_logins
from mysql import value
from native import Unavailable, checked, require, same


class Demo:
    def __init__(self, target):
        self.target = target
        self.container = target.container("mysql")
        directory = Path(target.config["canary_dir"]).resolve(strict=True)
        if ".local" not in directory.parts or directory.stat().st_mode & 0o077:
            raise Unavailable("password canaries must be in a private .local directory")
        self.original = self.read(directory / "mysql-demo")
        self.alternate = self.read(directory / "mysql-demo-alternate")
        require(self.original != self.alternate, "demo canaries must differ")

    @staticmethod
    def read(file):
        if file.stat().st_mode & 0o077:
            raise Unavailable("canary file is not private")
        value = file.read_text().rstrip("\n")
        if not re.fullmatch(r"[A-Za-z0-9_!@%+.-]{16,128}", value):
            raise Unavailable("canary is outside the permitted test alphabet")
        return value

    def change(self, sql, user):
        args = self.target.mysql_args(user=user)
        result = self.target.podman(*args, stdin=sql + "\n", show_input=False, show_output=False)
        match = re.search(r"ERROR (\d+) \(([0-9A-Z]+)\)", result.stderr)
        return result.returncode, match.groups() if match else ()

    def restore(self):
        rc, _ = self.change(f"ALTER USER 'demo'@'%' IDENTIFIED BY '{self.original}'", "root")
        require(rc == 0, "could not restore the initial synthetic password")

    def route(self, password, name):
        file = "/tmp/dl077-auth-" + uuid.uuid4().hex
        try:
            checked(self.target.podman(
                "exec", "-i", self.container, "sh", "-ec", 'umask 077; set -C; cat > "$1"',
                "dl077", file, stdin=f"[client]\npassword={password}\n",
                show_input=False, show_output=False,
            ))
            result = self.target.podman(
                "exec", "-i", self.container, "mysql", f"--defaults-extra-file={file}",
                "--host=127.0.0.1", "--protocol=TCP", "--batch", "--skip-column-names",
                "-u", "demo", stdin="SELECT CURRENT_USER();\n", show_output=False,
            )
            accepted = result.returncode == 0 and result.stdout.strip() == "demo@%"
            print(f"{name} client: {'accepted' if accepted else 'refused'}", flush=True)
            return accepted
        finally:
            checked(self.target.podman("exec", self.container, "rm", "-f", file))

    def usability(self):
        probe = self.target.podman(
            "exec", self.container, "mysql",
            "--defaults-extra-file=/run/megasamples-health.cnf", "-e", "SELECT 1",
        )
        usable = {"probe": probe.returncode == 0, "client": self.route(self.original, "original")}
        usable.update(console_logins(self.target, self.original))
        print(f"probe: {'accepted' if usable['probe'] else 'refused'}")
        return usable


def own_password(target):
    same(value(target, "SELECT @@global.log_raw"), "0")
    same(value(target, "SELECT @@global.read_only, @@global.super_read_only"), "0\t0")
    demo = Demo(target)
    original, alternate = demo.original, demo.alternate
    statements = (
        ("ALTER USER CURRENT_USER()", f"ALTER USER CURRENT_USER() IDENTIFIED BY '{alternate}'"),
        ("ALTER USER explicit demo account", f"ALTER USER 'demo'@'%' IDENTIFIED BY '{alternate}'"),
        ("SET PASSWORD", f"SET PASSWORD = '{alternate}'"),
        ("SET PASSWORD with REPLACE", f"SET PASSWORD = '{alternate}' REPLACE '{original}'"),
    )
    mechanisms = (
        ("existing demo privileges", "SELECT 1", "SELECT 1"),
        ("PASSWORD REQUIRE CURRENT", "ALTER USER 'demo'@'%' PASSWORD REQUIRE CURRENT",
         "ALTER USER 'demo'@'%' PASSWORD REQUIRE CURRENT DEFAULT"),
        ("ACCOUNT LOCK", "ALTER USER 'demo'@'%' ACCOUNT LOCK",
         "ALTER USER 'demo'@'%' ACCOUNT UNLOCK"),
        ("PASSWORD EXPIRE", "ALTER USER 'demo'@'%' PASSWORD EXPIRE", "SELECT 1"),
        ("global read_only", "SET GLOBAL read_only=ON", "SET GLOBAL read_only=OFF"),
        ("global super_read_only", "SET GLOBAL super_read_only=ON",
         "SET GLOBAL super_read_only=OFF; SET GLOBAL read_only=OFF"),
    )
    baseline = demo.usability()
    require(all(baseline.values()), "baseline did not show every intended demo sign-in")
    candidates = []
    observed = {}
    for mechanism, enable, disable in mechanisms:
        statuses = {}
        for label, statement in statements:
            value(target, enable)
            try:
                usability = demo.usability()
                rc, code = demo.change(statement, "demo")
                changed = rc == 0 and demo.route(alternate, "alternate") and not demo.route(original, "old")
                require(rc != 0 or changed, "accepted change did not replace the old credential")
                statuses[label] = (changed, all(usability.values()))
                print(f"{mechanism}; {label}; client exit {rc}; server error {code or 'none'}", flush=True)
            finally:
                value(target, disable)
                demo.restore()
        observed[mechanism] = statuses
    native_changes = {label for label, (changed, _) in observed["existing demo privileges"].items() if changed}
    require(native_changes, "no baseline statement demonstrated a real password change")
    for name, changes in observed.items():
        if all(not changes[label][0] and changes[label][1] for label in native_changes):
            candidates.append(name)
    print("Mechanisms refusing all demonstrated changes with working sign-ins: "
          + (", ".join(candidates) or "none found"))


CASES = {"G-16": own_password}
