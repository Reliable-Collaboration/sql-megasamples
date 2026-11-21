"""Exercise the copy contract through python -m megasamples."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


@pytest.fixture
def copying(tmp_path):
    templates = tmp_path / "templates"
    copies = tmp_path / "copies"
    templates.mkdir()
    copies.mkdir()
    source = templates / "sample.sqlite"
    with sqlite3.connect(source) as db:
        db.executescript("CREATE TABLE sample(id int); INSERT INTO sample VALUES (42);")
    source.chmod(0o444)
    manifest = {
        "tag": "megasamples-manifest/1",
        "templates": [{"name": source.name, "size": source.stat().st_size,
                       "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
    }
    (templates / "templates.json").write_text(json.dumps(manifest))

    def run(*args, exit=0):
        completed = subprocess.run(
            [sys.executable, "-m", "megasamples", "copy", *args,
             "--templates", str(templates), "--dir", str(copies)],
            capture_output=True, text=True, timeout=30,
        )
        assert completed.returncode == exit, completed.stdout + completed.stderr
        assert len(completed.stdout.splitlines()) == 1
        reply = json.loads(completed.stdout)
        assert set(reply) == {"schema", "interface", "command", "ok", "exit",
                              "volume", "result", "error", "warnings"}
        assert (reply["interface"], reply["ok"], reply["exit"], reply["volume"]) == (1, exit == 0, exit, None)
        return reply

    return run, source, copies


def create(run, label="run1"):
    return run("create", "sqlite:sample", "--prefix", "copy", "--label", label)["result"]


def target(row):
    return "sqlite:" + row["name"]


def test_lifecycle_and_release(copying):
    run, source, copies = copying
    row = create(run)
    assert row["state"] == "ready"
    assert len(row["identity"]) == 32
    assert row["name"] == "copy_sample_" + row["identity"][:12]
    copy = copies / (row["name"] + ".sqlite")
    assert copy.read_bytes() == source.read_bytes()
    with sqlite3.connect(copy) as db:
        db.execute("UPDATE sample SET id=43")
    with sqlite3.connect(source) as db:
        assert db.execute("SELECT id FROM sample").fetchone() == (42,)
    shown = run("show", target(row))["result"]
    matches = run("list", "sqlite", "--prefix", "copy", "--label", "run1")["result"]
    assert shown["identity"] == row["identity"]
    assert [item["identity"] for item in matches["copies"]] == [row["identity"]]
    wrong = "0" * 32 if row["identity"] != "0" * 32 else "1" * 32
    run("drop", target(row), "--identity", wrong, exit=5)
    run("renew", target(row), "--identity", wrong, "--lease", "1h", exit=5)
    run("release", target(row), "--identity", wrong, exit=5)
    kept = run("sweep", "sqlite", "--prefix", "copy")["result"]
    assert not kept["removed"] and copy.exists()
    renewed = run("renew", target(row), "--identity", row["identity"], "--lease", "7d")["result"]
    assert renewed["revision"] > row["revision"]
    assert renewed["lease_until"] > row["lease_until"]
    run("release", target(row), "--identity", row["identity"])
    before = {p.relative_to(copies): p.read_bytes() for p in copies.rglob("*") if p.is_file()}
    dry_run = run("sweep", "sqlite", "--prefix", "copy", "--dry-run")["result"]
    assert dry_run["removed"] and copy.exists()
    assert {p.relative_to(copies): p.read_bytes() for p in copies.rglob("*") if p.is_file()} == before
    assert run("sweep", "sqlite", "--prefix", "copy")["result"]["removed"]
    assert not copy.exists()
    run("drop", target(row), "--identity", row["identity"])


def test_template_verification_and_adjacent_file_preservation(copying):
    run, source, copies = copying
    original = source.read_bytes()
    source.chmod(0o644)
    source.write_bytes(b"\0" * len(original))
    source.chmod(0o444)
    run("create", "sqlite:sample", "--label", "bad", "--prefix", "copy", exit=8)
    assert not list(copies.glob("*.sqlite"))
    source.chmod(0o644)
    source.write_bytes(original)
    source.chmod(0o444)
    row = create(run)
    file = copies / (row["name"] + ".sqlite")
    journal = Path(str(file) + "-journal")
    journal.write_bytes(b"unidentified")
    replaced = copies / "new"
    replaced.write_bytes(b"replacement")
    os.replace(replaced, file)
    assert run("show", target(row))["result"]["state"] == "inconsistent"
    run("drop", target(row), "--identity", row["identity"], exit=5)
    assert file.read_bytes() == b"replacement"
    assert journal.read_bytes() == b"unidentified"
    second = create(run, "second")
    second_file = copies / (second["name"] + ".sqlite")
    second_journal = Path(str(second_file) + "-journal")
    second_journal.write_bytes(b"unidentified")
    assert run("drop", target(second), "--identity", second["identity"])["warnings"]
    assert not second_file.exists()
    assert second_journal.read_bytes() == b"unidentified"


@pytest.mark.parametrize("arguments", [
    ("create", "sqlite:sample", "--prefix", "", "--label", "test"),
    ("create", "sqlite:sample", "--prefix", "copy", "--label", ""),
    ("create", "sqlite:sample", "--prefix", "cöpy", "--label", "test"),
    ("create", "sqlite:sample", "--prefix", "copy", "--label", "tést"),
    ("create", "sqlite:sample", "--prefix", "a" * 17, "--label", "test"),
    ("create", "sqlite:sample", "--prefix", "copy", "--label", "a" * 25),
    ("create", "sqlite:sample", "--prefix", "copy", "--label", "ok", "--lease", "59s"),
    ("create", "sqlite:sample", "--prefix", "copy", "--label", "ok", "--lease", "8d"),
    ("show", "sqlite:../sample"),
    ("show", "sqlite:" + "a" * 64),
    ("drop", "sqlite:copy_sample_000000000000", "--identity", "z" * 32),
])
def test_invalid_names_and_limits(copying, arguments):
    run, _, copies = copying
    run(*arguments, exit=2)
    assert list(copies.iterdir()) == []


def test_duplicate_labels_and_limit_under_concurrent_creation(copying):
    run, _, copies = copying
    assert create(run, "a" * 24)["label"] == "a" * 24
    assert run("create", "sqlite:sample", "--prefix", "copy", "--label", "a" * 24,
               exit=5)["error"]["code"] == "label-in-use"
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(lambda index: create(run, f"trial{index}"), range(31)))
    assert len({row["identity"] for row in rows}) == len(rows)
    assert len(list(copies.glob("*.sqlite"))) == 32
    assert run("create", "sqlite:sample", "--prefix", "copy", "--label", "overflow",
               exit=5)["error"]["code"] == "limit"
