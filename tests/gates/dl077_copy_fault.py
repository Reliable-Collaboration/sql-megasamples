"""Run the real copy CLI with one fault planted through the native driver.

    dl077_copy_fault.py ENGINE POINT WHEN COPY-ARGS...

POINT is a server copy method (`insert`, `change`, ...): the connection closes before or after
that write (WHEN is `before` or `after`). POINT `short-fill` (MySQL; WHEN ignored) makes each
table fill of a copy select one row, as an engine that lost rows would.
"""

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
