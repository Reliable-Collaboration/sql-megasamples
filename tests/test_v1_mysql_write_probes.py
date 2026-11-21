"""MySQL test-image's write probes are refused by MySQL's permission error for each operation (Opus round
13, 3; Sol round 14, 1): 1142 for a table, 1370 for a routine. An authentication or database-access error
(1045, 1044), a client error or another operation's code is not a denial. The fake answers only the SQL a
real image would run: the probe fixtures by their exact names (Sol round 14, 2)."""

import subprocess

import pytest

from megasamples.engines.mysql import image_test

TABLE, CREATED, ROUTINE = "`chinook`.`_probe`", "`chinook`.`_create`", "`chinook`.`_routine`"
VALID = {
    "CREATE": f"CREATE TABLE {CREATED} (id integer)",
    "INSERT": f"INSERT INTO {TABLE} VALUES (2, 2)",
    "UPDATE": f"UPDATE {TABLE} SET n=2 WHERE id=1",
    "DELETE": f"DELETE FROM {TABLE} WHERE id=1",
    "DROP": f"DROP TABLE {TABLE}",
    "CALL": f"CALL {ROUTINE}()",
}
TABLE_DENIED = "ERROR 1142 (42000) at line 1: {kind} command denied to user 'demo'@'%' for table '_probe'\n"
ROUTINE_DENIED = "ERROR 1370 (42000) at line 1: execute command denied to user 'demo'@'%' for routine\n"
LABELS = {"CREATE": "demo cannot CREATE", "INSERT": "demo cannot INSERT", "UPDATE": "demo cannot UPDATE",
          "DELETE": "demo cannot DELETE", "DROP": "demo cannot DROP", "CALL": "demo cannot write through a routine"}


def run(monkeypatch, writable=(), answer=None, swap=False):
    def q(sql, user="root", pw="root", database=None, container=image_test.NAME):
        assert (user, pw) == ("demo", "demo"), (user, sql)
        kind = sql.split()[0]
        if VALID.get(kind) != sql:
            # What a real image answers for SQL that names no fixture of its own.
            code = "1305 (42000): PROCEDURE does not exist" if kind == "CALL" else "1146 (42S02): Table doesn't exist"
            return subprocess.CompletedProcess([], 1, "", f"ERROR {code}\n")
        if answer:
            return subprocess.CompletedProcess([], 1, "", answer)
        if kind in writable:
            return subprocess.CompletedProcess([], 0, "", "")
        denied = ROUTINE_DENIED if (kind == "CALL") != swap else TABLE_DENIED.format(kind=kind)
        return subprocess.CompletedProcess([], 1, "", denied)
    monkeypatch.setattr(image_test, "q", q)
    checks = image_test.Checks()
    image_test.demo_write_checks(checks, TABLE, CREATED, ROUTINE)
    return checks


def test_refused_writes_pass(monkeypatch):
    assert run(monkeypatch).failures == []


@pytest.mark.parametrize("kind", list(VALID))
def test_a_write_demo_can_make_fails(monkeypatch, kind):
    assert run(monkeypatch, writable={kind}).failures == [LABELS[kind]]


@pytest.mark.parametrize("answer", [
    "ERROR 2013 (HY000): Lost connection to MySQL server during query\n",
    "ERROR 1045 (28000): Access denied for user 'demo'@'10.0.0.2' (using password: YES)\n",
    "ERROR 1044 (42000): Access denied for user 'demo'@'%' to database 'chinook'\n",
    "mysql: [ERROR] unknown option '--batchx'.\n",
])
def test_a_refusal_for_another_reason_is_not_a_denial(monkeypatch, answer):
    assert len(run(monkeypatch, answer=answer).failures) == 6


def test_another_operations_refusal_is_not_this_ones(monkeypatch):
    # A table's 1142 for the routine call, and a routine's 1370 for each table statement.
    assert len(run(monkeypatch, swap=True).failures) == 6


def test_a_probe_aimed_at_a_name_the_image_lacks_fails(monkeypatch):
    checks = image_test.Checks()
    monkeypatch.setattr(image_test, "q", lambda sql, **kw: subprocess.CompletedProcess(
        [], 1, "", "ERROR 1305 (42000): PROCEDURE chinook._other does not exist\n"))
    image_test.demo_write_checks(checks, TABLE, CREATED, "`chinook`.`_other`")
    assert "demo cannot write through a routine" in checks.failures
