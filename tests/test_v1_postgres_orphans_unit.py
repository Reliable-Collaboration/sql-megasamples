"""DL-119's detective control, through fakes: every PostgreSQL data directory with no database is reported."""

import json
from types import SimpleNamespace

import pytest

from megasamples import postgres_orphans

LISTING = ("pg_default 1 7524 base/1\npg_default 5 7600 base/5\npg_default 16384 9000 base/16384\n"
           "pg_default 99999 1200 base/99999\nspace 16500\n16500 16390 64 pg_tblspc/16500/PG_18_202506291/16390\n")
CATALOG = "1\n5\n16384\n"
SPACES = "1663 pg_default\n1664 pg_global\n16500 archive\n"


def fake(outputs):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        key = "list" if "sh" in args else ("spaces" if "pg_tablespace" in args[-1] else "catalog")
        code, out = outputs[key]
        return SimpleNamespace(returncode=code, stdout=out, stderr="")
    return run, calls


def test_reports_each_directory_without_a_database(monkeypatch):
    run, _ = fake({"list": (0, LISTING), "catalog": (0, CATALOG), "spaces": (0, SPACES)})
    monkeypatch.setattr(postgres_orphans.subprocess, "run", run)
    warnings = postgres_orphans.scan("megasamples-postgres")
    assert warnings == [
        {"code": "orphan-directory", "engine": "postgres", "tablespace": "pg_default", "oid": 99999,
         "name": None, "path": "base/99999", "kib": 1200},
        {"code": "orphan-directory", "engine": "postgres", "tablespace": "archive", "oid": 16390,
         "name": None, "path": "pg_tblspc/16500/PG_18_202506291/16390", "kib": 64},
    ]


@pytest.mark.parametrize("failing", ["list", "catalog", "spaces"])
def test_a_scan_that_cannot_complete_says_so(monkeypatch, failing):
    outputs = {"list": (0, LISTING), "catalog": (0, CATALOG), "spaces": (0, SPACES)}
    outputs[failing] = (1, "")
    run, _ = fake(outputs)
    monkeypatch.setattr(postgres_orphans.subprocess, "run", run)
    warnings = postgres_orphans.scan("megasamples-postgres")
    assert warnings[-1]["code"] == "orphan-scan-incomplete" and warnings[-1]["engine"] == "postgres"
    assert not any(item["code"] == "orphan-directory" for item in warnings)


def test_an_empty_catalog_reading_is_incomplete_not_every_directory(monkeypatch):
    run, _ = fake({"list": (0, LISTING), "catalog": (0, ""), "spaces": (0, SPACES)})
    monkeypatch.setattr(postgres_orphans.subprocess, "run", run)
    assert [item["code"] for item in postgres_orphans.scan("c")] == ["orphan-scan-incomplete"]


def test_reset_status_reports_the_scan(monkeypatch, capsys):
    from megasamples import reset
    planted = [{"code": "orphan-directory", "engine": "postgres", "tablespace": "pg_default", "oid": 99999,
                "name": None, "path": "base/99999", "kib": 1200}]
    monkeypatch.setattr(postgres_orphans, "scan", lambda container: planted)
    assert reset.main(["--status", "postgres"]) == 0
    reply = json.loads(capsys.readouterr().out)
    assert reply["command"] == "reset --status" and reply["exit"] == 0 and reply["warnings"] == planted
    assert reply["result"] == {"engine": "postgres", "orphan_scan": "complete"}


def test_up_reports_the_scan_after_the_stack_starts(monkeypatch, capsys):
    from megasamples import compose, console_config, console_images, job
    planted = [{"code": "orphan-directory", "engine": "postgres", "tablespace": "pg_default", "oid": 99999,
                "name": None, "path": "base/99999", "kib": 1200}]
    order = []
    monkeypatch.setattr(job.stack, "load", lambda: SimpleNamespace(engines=["postgres"], consoles=[], ports={}, datasets=lambda engine=None: []))
    monkeypatch.setattr(console_config, "main", lambda argv: 0)
    monkeypatch.setattr(compose, "main", lambda argv: 0)
    monkeypatch.setattr(console_images, "build", lambda cfg: 0)

    def run(args, **kwargs):
        order.append(args[:3])
        return SimpleNamespace(returncode=0, stdout="same\n", stderr="")
    monkeypatch.setattr(job.subprocess, "run", run)
    monkeypatch.setattr(postgres_orphans, "scan", lambda container: order.append("scan") or planted)
    assert job.up([]) == 0
    assert order.index("scan") > order.index(["docker", "compose", "-f"])
    err = capsys.readouterr().err
    assert "base/99999" in err and "no database" in err


@pytest.mark.parametrize("listing", [
    LISTING + "pg_default 99998\n",                       # a size that could not be read
    LISTING + "unreadable base/99997\n",                  # du failed on a directory still there
    LISTING + "pg_default x 12 base/x\n",                 # not an OID
])
def test_a_malformed_or_failed_observation_is_incomplete(monkeypatch, listing):
    """Sol round 3, P2-2 / Opus round 3, 5: never a traceback, never a partial verdict."""
    run, _ = fake({"list": (0, listing), "catalog": (0, CATALOG), "spaces": (0, SPACES)})
    monkeypatch.setattr(postgres_orphans.subprocess, "run", run)
    assert [item["code"] for item in postgres_orphans.scan("c")] == ["orphan-scan-incomplete"]


def run_listing(tmp_path, du_body):
    """Run the real listing script under sh against a fake data directory, with a du shim."""
    import os
    import stat
    import subprocess
    shims = tmp_path / "shims"
    shims.mkdir()
    du = shims / "du"
    du.write_text("#!/bin/sh\n" + du_body)
    du.chmod(du.stat().st_mode | stat.S_IEXEC)
    return subprocess.run(["sh", "-c", postgres_orphans.LIST], capture_output=True, text=True,
                          env={**os.environ, "PGDATA": str(tmp_path / "data"),
                               "PATH": f"{shims}:{os.environ['PATH']}"})


def data_tree(tmp_path, *oids):
    for oid in oids:
        (tmp_path / "data" / "base" / str(oid)).mkdir(parents=True)
    (tmp_path / "data" / "pg_tblspc").mkdir(parents=True, exist_ok=True)


def test_a_directory_dropped_during_the_scan_is_skipped(tmp_path):
    """Opus round 4, P3-3: as behaviour. du finds the directory gone and fails: nothing is printed."""
    data_tree(tmp_path, 1, 99999)
    result = run_listing(tmp_path, 'case "$2" in *99999) rm -rf "$2"; exit 1;; esac; echo "8 $2"\n')
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["pg_default 1 8 base/1"]


def test_a_directory_du_cannot_read_is_reported_unreadable(tmp_path):
    data_tree(tmp_path, 1, 99999)
    result = run_listing(tmp_path, 'case "$2" in *99999) echo "4 $2"; exit 1;; esac; echo "8 $2"\n')
    assert "unreadable base/99999" in result.stdout.splitlines()


def test_an_unreadable_or_dangling_tablespace_is_reported(tmp_path):
    """Sol round 4, P2-3."""
    data_tree(tmp_path, 1)
    (tmp_path / "data" / "pg_tblspc" / "16500").symlink_to(tmp_path / "missing-mount")
    result = run_listing(tmp_path, 'echo "8 $2"\n')
    assert "unreadable pg_tblspc/16500" in result.stdout.splitlines()


def test_a_catalogued_tablespace_the_listing_never_inspected_is_incomplete(monkeypatch):
    listing = "pg_default 1 7524 base/1\npg_default 5 7600 base/5\npg_default 16384 9000 base/16384\n"
    run, _ = fake({"list": (0, listing), "catalog": (0, CATALOG), "spaces": (0, SPACES)})
    monkeypatch.setattr(postgres_orphans.subprocess, "run", run)
    assert [item["code"] for item in postgres_orphans.scan("c")] == ["orphan-scan-incomplete"]
