"""MySQL test-image's write probes are refused by MySQL's permission errors (Opus round 13, 3), as
PostgreSQL's are (Sol round 12, P3-6): a refusal for another reason is not a denial."""

import subprocess

import pytest

from megasamples.engines.mysql import image_test

TABLE, CREATED, ROUTINE = "`chinook`.`_probe`", "`chinook`.`_create`", "`chinook`.`_routine`"
DENIED = {"CALL": "ERROR 1370 (42000) at line 1: execute command denied to user 'demo'@'%' for routine\n"}


def run(monkeypatch, writable=(), other=False):
    def q(sql, user="root", pw="root", database=None, container=image_test.NAME):
        assert (user, pw) == ("demo", "demo"), (user, sql)
        kind = sql.split()[0]
        if other:
            return subprocess.CompletedProcess([], 1, "", "ERROR 2013 (HY000): Lost connection to MySQL server\n")
        if kind in writable:
            return subprocess.CompletedProcess([], 0, "", "")
        return subprocess.CompletedProcess([], 1, "", DENIED.get(kind, f"ERROR 1142 (42000) at line 1: {kind} "
                                                                     "command denied to user 'demo'@'%' for table\n"))
    monkeypatch.setattr(image_test, "q", q)
    checks = image_test.Checks()
    image_test.demo_write_checks(checks, TABLE, CREATED, ROUTINE)
    return checks


def test_refused_writes_pass(monkeypatch):
    assert run(monkeypatch).failures == []


@pytest.mark.parametrize("kind, label", [("CREATE", "demo cannot CREATE"), ("INSERT", "demo cannot INSERT"),
                                         ("UPDATE", "demo cannot UPDATE"), ("DELETE", "demo cannot DELETE"),
                                         ("DROP", "demo cannot DROP"), ("CALL", "demo cannot write through a routine")])
def test_a_write_demo_can_make_fails(monkeypatch, kind, label):
    assert run(monkeypatch, writable={kind}).failures == [label]


def test_a_refusal_for_another_reason_is_not_a_denial(monkeypatch):
    assert len(run(monkeypatch, other=True).failures) == 6
