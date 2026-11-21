"""PostgreSQL test-image's write probes are refused for the stated reason (Sol round 12, P3-6).

The UPDATE probe assigned to a column named like its table, which Chinook's `album` lacks, so the error was
"column does not exist" and any non-zero exit passed. Each probe must name a real column where it needs one
and be refused by permission, as a fake server here answers.
"""

import re
import subprocess

import pytest

from megasamples.engines.postgres import image_test

DENIED = "ERROR:  permission denied for table album\n"


def run(monkeypatch, writable):
    """A server where demo can write `writable` (a set of statement kinds) and the table has real columns."""
    statements = []

    def q(sql, user="postgres", pw="root", database="postgres", container=image_test.NAME):
        statements.append(sql)
        # Sol round 13, 2: every probe goes to the dataset's database, as demo.
        assert (database, user, pw) == ("chinook", "demo", "demo"), (database, user, sql)
        if sql.startswith("SELECT column_name"):
            return subprocess.CompletedProcess([], 0, "albumid\n", "")
        kind = sql.split()[0]
        # Sol round 14, 2: SQL naming a column the table lacks is what a real image refuses for that reason.
        named = set(re.findall(r'"([a-z_]+)"', sql)) - {"album"}
        if kind in ("INSERT", "UPDATE") and named != {"albumid"}:
            return subprocess.CompletedProcess([], 1, "", 'ERROR:  column of relation "album" does not exist\n')
        if kind in ("INSERT", "UPDATE", "DELETE", "DROP") and '"album"' not in sql:
            return subprocess.CompletedProcess([], 1, "", 'ERROR:  relation does not exist\n')
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


@pytest.mark.parametrize("kind", ["CREATE", "INSERT", "DELETE", "UPDATE", "DROP"])
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
    assert checks.failures == ["demo cannot CREATE", "demo cannot INSERT", "demo cannot DELETE", "demo cannot UPDATE",
                               "demo cannot DROP"]


@pytest.mark.parametrize("wrong", ["album", "title"])
def test_a_probe_naming_a_column_the_table_lacks_fails(monkeypatch, wrong):
    """The INSERT and UPDATE must name the column the lookup returned; another name is not a denial."""
    original = image_test.demo_write_checks

    def lookup_returns(column):
        def q(sql, user="postgres", pw="root", database="postgres", container=image_test.NAME):
            if sql.startswith("SELECT column_name"):
                return subprocess.CompletedProcess([], 0, column + "\n", "")
            if '"albumid"' not in sql and sql.split()[0] in ("INSERT", "UPDATE"):
                return subprocess.CompletedProcess([], 1, "", 'ERROR:  column does not exist\n')
            return subprocess.CompletedProcess([], 1, "", DENIED)
        return q
    monkeypatch.setattr(image_test, "q", lookup_returns(wrong))
    checks = image_test.Checks()
    original(checks, "chinook", "album")
    assert {"demo cannot INSERT", "demo cannot UPDATE"} <= set(checks.failures)
