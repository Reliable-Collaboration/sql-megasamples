"""Run the shipped image suite in an isolated store with the selected log mode."""

import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from mysql import value
from native import Unavailable, checked, require, same


def image_tests(target, key, expected):
    same(value(target, "SELECT @@global.log_bin", key=key), expected)
    image = target.image(key)
    for fixture in ("mysql", "mysql_no_binlog"):
        checked(target.podman("stop", target.container(fixture), timeout=90))
    datasets = target.config.get("mysql_image_datasets")
    if not datasets or not all(re.fullmatch(r"[a-z0-9_]+", dataset) for dataset in datasets):
        raise Unavailable("supply the exact dataset list used to build the scratch image")
    from native import capacity

    capacity()
    repo = Path(__file__).resolve().parents[2]
    mode = "on" if expected == "1" else "off"
    with tempfile.TemporaryDirectory(prefix="dl077-image-cli-") as directory:
        (Path(directory) / "docker").symlink_to(Path(__file__).with_name("image_docker.py"))
        capacity_failure = Path(directory) / "capacity-failure"
        env = {
            **os.environ,
            "DL077_IMAGE_CAPACITY_FAILURE": str(capacity_failure),
            "DL077_IMAGE_ENV": str(target.env_script),
            "DL077_IMAGE_BINLOG": mode,
            "DL077_IMAGE_OWNER": "dl077-image-" + uuid.uuid4().hex[:12],
            "MEGASAMPLES_MYSQL_IMAGE": image,
            "PATH": directory + os.pathsep + os.environ["PATH"],
        }
        args = (sys.executable, "-m", "megasamples.engines.mysql.image_test", *datasets)
        print(f"python -m megasamples.engines.mysql.image_test {' '.join(datasets)} (binary log {mode})")
        result = subprocess.run(args, cwd=repo, capture_output=True, text=True, timeout=3600, env=env)
        for line in result.stdout.splitlines():
            if line.startswith(("  . ", "  x ", "image test: ")):
                print(line)
        print(f"image suite exit {result.returncode}")
        if capacity_failure.exists():
            raise Unavailable(f"an image-suite start required 15 GiB, observed {int(capacity_failure.read_text())} KiB")
        require(result.returncode == 0 and "image test: 0 failure(s)" in result.stdout,
                "shipped MySQL image suite did not pass")


def binlog_off(target):
    same(value(target, "SELECT @@global.log_bin", key="mysql"), "1")
    image_tests(target, "mysql_no_binlog", "0")


def binlog_on(target):
    same(value(target, "SELECT @@global.log_bin", key="mysql_no_binlog"), "0")
    image_tests(target, "mysql", "1")


CASES = {"G-18a": binlog_off, "G-18b": binlog_on}
