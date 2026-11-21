"""Inject a disconnection through the native driver at a copy write."""

import sys

from megasamples.cli import main
from megasamples.copy_mysql import MySQLCopies
from megasamples.copy_postgres import PostgresCopies


def run():
    engine, point, when, *args = sys.argv[1:]
    copies = {"mysql": MySQLCopies, "postgres": PostgresCopies}[engine]
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
