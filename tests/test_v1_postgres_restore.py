"""Every database the PostgreSQL image ships survives its own dump and restore, account rules included.

The class is any object the image makes outside an extension that pg_dump carries and that a new
database from template0 already has. The restore is pg_restore --exit-on-error into a database made
from template0, as reset's `pg_restore --create` makes it. The second case runs the real
`megasamples reset postgres:chinook` against the owned container.
"""

import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent / "gates"))
from native import Target

ROOT = Path(__file__).parents[1]


@unittest.skipUnless(os.environ.get("DL077_GATE_TARGET"), "requires an owned PostgreSQL fixture")
class RestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target = Target()

    def run_in(self, *args, stdin=None):
        return subprocess.run(self.target.podman_args("exec", "-i", self.target.container("postgres"), *args),
                              input=stdin, capture_output=True, text=True, timeout=300)

    def sql(self, statement, database="postgres", user="postgres"):
        result = self.run_in("psql", "-XqAt", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", database, stdin=statement + "\n")
        return result

    def accept(self, statement, database="postgres", user="postgres"):
        result = self.sql(statement, database, user)
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        return result.stdout.strip()

    def assert_accounts(self, database):
        """A restored database keeps the image's account rules: demo reads through pg_read_all_data and is
        refused every write to the restored tables."""
        self.assertEqual(self.accept("SELECT pg_has_role('demo', 'pg_read_all_data', 'USAGE'), "
                                     "pg_has_role('demo', 'pg_write_all_data', 'USAGE'), "
                                     "coalesce(bool_or(has_table_privilege('demo', c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE')), false) "
                                     "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                     "WHERE c.relkind = 'r' AND n.nspname NOT IN ('pg_catalog', 'information_schema')",
                                     database), "t|f|f")

    def counts(self, database):
        return self.accept("""SELECT format('SELECT %L || '':'' || count(*) FROM %I.%I', n.nspname || '.' || c.relname,
                                     n.nspname, c.relname)
                              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                              WHERE c.relkind = 'r' AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                              ORDER BY 1 \\gexec""", database)

    def test_every_shipped_database_restores_into_a_template0_database(self):
        # Every connectable database the image ships, template1 included; this suite's own scratch
        # databases (v1_) are excluded by name.
        databases = self.accept("SELECT datname FROM pg_database WHERE datallowconn "
                                "AND datname NOT LIKE 'v1\\_%' ORDER BY 1").split()
        self.assertTrue({"chinook", "template1", "megasamples", "postgres"} <= set(databases), databases)
        for database in databases:
            with self.subTest(database=database):
                scratch = "v1_restore_" + database
                dumped = self.run_in("pg_dump", "-U", "postgres", "-Fc", "-f", "/tmp/v1-restore.dump", database)
                self.assertEqual(dumped.returncode, 0, dumped.stderr[-500:])
                self.accept(f'CREATE DATABASE "{scratch}" TEMPLATE template0')
                self.accept(f'GRANT CONNECT ON DATABASE "{scratch}" TO admin')
                try:
                    restored = self.run_in("pg_restore", "-U", "postgres", "-d", scratch, "--exit-on-error",
                                           "/tmp/v1-restore.dump")
                    self.assertEqual(restored.returncode, 0, restored.stderr[-800:])
                    self.assertEqual(self.counts(scratch), self.counts(database))
                    self.assert_accounts(scratch)
                finally:
                    self.accept(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)')

    @unittest.skipUnless(os.environ.get("DL077_PG_RESET_CHECKOUT"), "requires a checkout without .env and a Docker socket")
    def test_megasamples_reset_restores_chinook_with_its_accounts(self):
        checkout = Path(os.environ["DL077_PG_RESET_CHECKOUT"])
        self.assertFalse((checkout / ".env").exists())
        before = self.counts("chinook")
        self.accept("UPDATE album SET title = 'edited before reset' WHERE albumid = 1", "chinook", "admin")
        result = subprocess.run([sys.executable, str(ROOT / "tests/gates/dl077_reset_target.py"),
                                 self.target.container("postgres"), "postgres:chinook"],
                                cwd=checkout, capture_output=True, text=True, timeout=900,
                                env={**os.environ, "PYTHONPATH": str(checkout) + os.pathsep + os.environ.get("PYTHONPATH", "")})
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-1500:])
        self.assertEqual(self.counts("chinook"), before)
        self.assertNotEqual(self.accept("SELECT title FROM album WHERE albumid = 1", "chinook"), "edited before reset")
        self.assert_accounts("chinook")


if __name__ == "__main__":
    unittest.main()
