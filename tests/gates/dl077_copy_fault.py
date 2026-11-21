"""Run the real copy CLI with one fault planted through the native driver.

    dl077_copy_fault.py ENGINE POINT WHEN COPY-ARGS...

POINT is a server copy method (`insert`, `change`, ...): the connection closes before or after
that write (WHEN is `before` or `after`). POINT `short-fill` (MySQL; WHEN ignored) makes each
table fill of a copy select one row, as an engine that lost rows would. POINT `renew-first` (WHEN is
`NAME:IDENTITY`) runs a separate `copy renew` of that copy for seven days just before the sweep takes
that name's change lock the second time: the selection has read the copy under its first lock, so the
renewal lands between the sweep's selection and its removal. POINT `metadata` closes the connection
just before the command's first metadata read after sign-in. POINT `corrupt-after-first` (WHEN is
the NAME of another copy) rewrites that copy's ledger record to an unknown tag right after the
sweep's first removal. POINT `corrupt-before-recheck` (WHEN is a copy's NAME) rewrites that
record just before the sweep takes its change lock the second time. POINT `unlock-fails` makes the
change-lock release fail after the sweep's first removal. POINT `state-second` closes the connection
just before the command's second state read (a drop's proof read at the removal). POINT
`forget-fails` makes the ledger row's deletion fail after the database or schema is dropped. POINT
`revoke-fails` (PostgreSQL) makes the copy's closure to PUBLIC fail right after CREATE DATABASE.
"""

import subprocess
import sys

from megasamples.cli import main
from megasamples.copy_mysql import MySQLCopies
from megasamples.copy_postgres import PostgresCopies


def run():
    engine, point, when, *args = sys.argv[1:]
    copies = {"mysql": MySQLCopies, "postgres": PostgresCopies}[engine]
    if point == "short-fill":
        execute = copies.execute

        def short(self, sql, params=()):
            if sql.startswith("INSERT INTO ") and " SELECT " in sql and "megasamples" not in sql.split()[2]:
                sql += " LIMIT 1"
            return execute(self, sql, params)

        copies.execute = short
        return main(["copy", *args])
    if point == "renew-first":
        target, identity = when.split(":")
        engine_name = args[1]
        options = [arg for index, arg in enumerate(args) if index >= 2 and (
            arg.startswith("--") and arg not in ("--prefix", "--dry-run") or args[index - 1] in (
                "--host", "--port", "--user", "--password-file"))]
        lock = copies.lock
        calls = {"count": 0}

        def renew_first(self, name, *rest, **keywords):
            if name == target:
                calls["count"] += 1
            if name == target and calls["count"] == 2:
                subprocess.run([sys.executable, "-m", "megasamples", "copy", "renew", engine_name + ":" + name,
                                "--identity", identity, "--lease", "7d", *options],
                               check=True, capture_output=True, timeout=45)
            return lock(self, name, *rest, **keywords)

        copies.lock = renew_first
        return main(["copy", *args])
    if point == "metadata":
        one = copies.one
        state = {"done": False}

        def first_read(self, sql, params=()):
            if not state["done"]:
                state["done"] = True
                self.connection.close()
            return one(self, sql, params)

        copies.one = first_read
        return main(["copy", *args])
    if point == "corrupt-after-first":
        remove = copies.remove
        state = {"done": False}

        def remove_then_corrupt(self, row, *rest, **keywords):
            result = remove(self, row, *rest, **keywords)
            if not state["done"]:
                state["done"] = True
                if engine == "postgres":
                    sql = (f"UPDATE {self.ledger} SET record = jsonb_set(record, '{{tag}}', "
                           "'\"megasamples-copy/99\"') WHERE name = %s")
                else:
                    sql = f"UPDATE {self.ledger} SET record = JSON_SET(record, '$.tag', 'megasamples-copy/99') WHERE name = %s"
                if engine == "postgres":
                    self.connection.execute(sql, (when,))
                else:
                    self.execute(sql, (when,))
            return result

        copies.remove = remove_then_corrupt
        return main(["copy", *args])
    if point == "corrupt-before-recheck":
        lock = copies.lock
        calls = {"count": 0}

        def corrupt_then_lock(self, name, *rest, **keywords):
            if name == when:
                calls["count"] += 1
                if calls["count"] == 2:
                    if engine == "postgres":
                        self.connection.execute(f"UPDATE {self.ledger} SET record = jsonb_set(record, '{{tag}}', "
                                                "'\"megasamples-copy/99\"') WHERE name = %s", (when,))
                    else:
                        self.execute(f"UPDATE {self.ledger} SET record = JSON_SET(record, '$.tag', "
                                     "'megasamples-copy/99') WHERE name = %s", (when,))
            return lock(self, name, *rest, **keywords)

        copies.lock = corrupt_then_lock
        return main(["copy", *args])
    if point == "unlock-fails":
        remove, one = copies.remove, copies.one
        state = {"removed": False}

        def remove_and_mark(self, *arguments, **keywords):
            result = remove(self, *arguments, **keywords)
            state["removed"] = True
            return result

        def failing_unlock(self, sql, params=()):
            if state["removed"] and ("advisory_unlock" in sql or "RELEASE_LOCK" in sql):
                state["removed"] = False
                raise self.errors.OperationalError("planted failure releasing the change lock")
            return one(self, sql, params)

        copies.remove, copies.one = remove_and_mark, failing_unlock
        return main(["copy", *args])
    if point == "state-second":
        state_read = copies.state
        calls = {"count": 0}

        def second_read(self, *arguments, **keywords):
            calls["count"] += 1
            if calls["count"] == 2:
                self.connection.close()
            return state_read(self, *arguments, **keywords)

        copies.state = second_read
        return main(["copy", *args])
    if point == "revoke-fails":
        # PostgreSQL: the copy's closure to PUBLIC fails right after CREATE DATABASE, as a server error.
        import psycopg

        create_reserved = copies.create_reserved

        def failing_revoke(self, row, strategy):
            connection = self.connection

            class Planted:
                def __getattr__(self, name):
                    return getattr(connection, name)

                def execute(self, sql, *rest, **keywords):
                    if sql.startswith("REVOKE CONNECT, TEMPORARY ON DATABASE"):
                        raise psycopg.errors.InternalError_("planted closure failure")
                    return connection.execute(sql, *rest, **keywords)

            self.connection = Planted()
            try:
                return create_reserved(self, row, strategy)
            finally:
                self.connection = connection

        copies.create_reserved = failing_revoke
        return main(["copy", *args])
    if point == "forget-fails":
        def failing_forget(self, name):
            raise self.errors.OperationalError("planted failure deleting the ledger row")

        copies.forget = failing_forget
        return main(["copy", *args])
    original = getattr(copies, point)

    def disconnect(self, *arguments, **keywords):
        if when == "after":
            original(self, *arguments, **keywords)
        self.connection.close()
        self.one("SELECT 1")
        raise AssertionError("the closed connection unexpectedly accepted a query")

    setattr(copies, point, disconnect)
    return main(["copy", *args])


if __name__ == "__main__":
    sys.exit(run())
