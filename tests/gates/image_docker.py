#!/usr/bin/env python3
"""Route main's existing MySQL image test to containers owned by this invocation."""

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

NAME = "megasamples-test-mysql"
LABEL = "org.sql-megasamples.gates.owner"

def call(argv, **kwargs):
    return subprocess.run(
        ["bash", "-c", 'source "$1" || exit; shift; exec podman "$@"',
         "dl077-image", os.environ["DL077_IMAGE_ENV"], *argv], **kwargs,
    )


def main(args):
    owner = os.environ["DL077_IMAGE_OWNER"]
    names = {old: owner + suffix for old, suffix in ((NAME, ""), (NAME + "2", "-override"))}
    mapped = [names.get(argument, argument) for argument in args]
    if args[0] == "run":
        with open("/proc/meminfo") as meminfo:
            available = next(int(line.split()[1]) for line in meminfo if line.startswith("MemAvailable:"))
        if available < 15 * 1024 * 1024:
            Path(os.environ["DL077_IMAGE_CAPACITY_FAILURE"]).write_text(str(available))
            return 89
        mapped[1:1] = ["--pull=never", "--memory=2g", "--memory-swap=4g",
                        "--network=none", "--label", f"{LABEL}={owner}"]
        mapped.append("mysqld")
        if os.environ["DL077_IMAGE_BINLOG"] == "off":
            mapped.append("--skip-log-bin")
        if "--env-file" in mapped:
            index = mapped.index("--env-file")
            env_file = Path(mapped[index + 1])
            with tempfile.TemporaryDirectory(prefix="dl077-mysql-startup-") as directory:
                wrapper = Path(directory) / "start"
                assignments = []
                for line in env_file.read_text().splitlines():
                    key, value = line.split("=", 1)
                    if key not in ("MYSQL_ROOT_PASSWORD", "ADMIN_PASSWORD", "DEMO_PASSWORD"):
                        return 89
                    assignments.append(f"{key}={shlex.quote(value)}")
                wrapper.write_text("#!/bin/bash\n" + "\n".join(assignments)
                                   + "\n. /usr/local/bin/entrypoint-wrapper.sh\n")
                wrapper.chmod(0o700)
                mapped[index:index + 2] = ["--volume", f"{wrapper}:/run/dl077-start:ro",
                                           "--entrypoint", "/run/dl077-start"]
                return call(mapped).returncode
    elif args[0] in ("exec", "logs", "rm"):
        used = set(mapped).intersection(names.values())
        if len(used) != 1:
            return 89
        container = used.pop()
        inspected = call(
            ["inspect", "--type", "container", "--format",
             '{{index .Config.Labels "' + LABEL + '"}}', container],
            capture_output=True, text=True, timeout=10,
        )
        if inspected.returncode or inspected.stdout.strip() != owner:
            return 89
        if args[0] == "rm":
            mapped.insert(1, "--volumes")
    else:
        return 89
    return call(mapped).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
