"""PostgreSQL test-image's write probes are refused for the stated reason (Sol round 12, P3-6).

The UPDATE probe assigned to a column named like its table, which Chinook's `album` lacks, so the error was
"column does not exist" and any non-zero exit passed. Each probe must name a real column where it needs one
and be refused by permission, as a fake server here answers.
"""

import subprocess

import pytest

from megasamples.engines.postgres import image_test

DENIED = "ERROR:  permission denied for table album\n"


def run(monkeypatch, writable):
    """A server where demo can write `writable` (a set of statement kinds) and the table has real columns."""
    statements = []

    def q(sql, user="postgres", pw="root", database="postgres", container=image_test.NAME):
        statements.append(sql)
        if sql.startswith("SELECT column_name"):
            return subprocess.CompletedProcess([], 0, "albumid\n", "")
        kind = sql.split()[0]
        if kind == "UPDATE" and '"album" = ' in sql:
            return subprocess.CompletedProcess([], 1, "", 'ERROR:  column "album" of relation "album" does not exist\n')
        if kind in writable:
            return subprocess.CompletedProcess([], 0, "", "")
        return subprocess.CompletedProcess([], 1, "", DENIED)
    monkeypatch.setattr(image_test, "q", q)
    checks = image_test.Checks()
    image_test.demo_write_checks(checks, "chinook", "album")
    return checks, statements


def test_refused_writes_pass(monkeypatch):
    checks, _ = run(monkeypatch, writable=set())
    assert checks.failures == []


@pytest.mark.parametrize("kind", ["CREATE", "DELETE", "UPDATE", "DROP"])
def test_a_write_demo_can_make_fails(monkeypatch, kind):
    checks, _ = run(monkeypatch, writable={kind})
    assert checks.failures == [f"demo cannot {kind}"]


def test_the_update_probe_names_a_real_column_and_needs_a_permission_error(monkeypatch):
    _, statements = run(monkeypatch, writable=set())
    update = next(s for s in statements if s.startswith("UPDATE"))
    assert '"albumid"' in update and '"album" =' not in update


def test_a_refusal_for_another_reason_is_not_a_denial(monkeypatch):
    def q(sql, **kw):
        if sql.startswith("SELECT column_name"):
            return subprocess.CompletedProcess([], 0, "albumid\n", "")
        return subprocess.CompletedProcess([], 2, "", "psql: error: connection to server failed\n")
    monkeypatch.setattr(image_test, "q", q)
    checks = image_test.Checks()
    image_test.demo_write_checks(checks, "chinook", "album")
    assert checks.failures == ["demo cannot CREATE", "demo cannot DELETE", "demo cannot UPDATE", "demo cannot DROP"]
