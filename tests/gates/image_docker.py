#!/usr/bin/env python3
"""Route main's existing MySQL image test to containers owned by this invocation."""

import os
import subprocess
import sys

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
            return 89
        mapped[1:1] = ["--pull=never", "--memory=2g", "--label", f"{LABEL}={owner}"]
        mapped.extend(["mysqld", "--innodb-buffer-pool-size=256M", "--temptable-max-ram=1G"])
        if os.environ["DL077_IMAGE_BINLOG"] == "off":
            mapped.append("--skip-log-bin")
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
    else:
        return 89
    return call(mapped).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
