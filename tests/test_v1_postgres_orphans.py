"""DL-119 through the real image: planted data directories with no database are reported by
`reset --status postgres`, later creates still succeed, and none takes a planted directory."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent / "gates"))
from native import Target

ROOT = Path(__file__).parents[1]


@unittest.skipUnless(os.environ.get("DL077_GATE_TARGET") and os.environ.get("DL077_PG_RESET_CHECKOUT"),
                     "requires an owned PostgreSQL fixture, a checkout without .env and a Docker socket")
class OrphanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target = Target()
        cls.container = cls.target.container("postgres")

    def run_in(self, *args, user=None):
        return subprocess.run(self.target.podman_args("exec", *(["-u", user] if user else []), self.container, *args),
                              capture_output=True, text=True, timeout=120)

    def accept(self, sql, user="postgres"):
        result = self.run_in("psql", "-XqAt", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", "postgres", "-c", sql)
        self.assertEqual(result.returncode, 0, result.stderr[-400:])
        return result.stdout.strip()

    def status(self):
        checkout = Path(os.environ["DL077_PG_RESET_CHECKOUT"])
        self.assertFalse((checkout / ".env").exists())
        result = subprocess.run([sys.executable, str(ROOT / "tests/gates/dl077_reset_target.py"), self.container,
                                 "--status", "postgres"], cwd=checkout, capture_output=True, text=True, timeout=300,
                                env={**os.environ, "PYTHONPATH": str(checkout) + os.pathsep + os.environ.get("PYTHONPATH", "")})
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-800:])
        return json.loads(result.stdout)

    def test_planted_orphans_are_reported_and_skipped_by_later_creates(self):
        self.accept("CREATE DATABASE v1_orphan_probe")
        probe = int(self.accept("SELECT oid FROM pg_database WHERE datname='v1_orphan_probe'"))
        self.accept("DROP DATABASE v1_orphan_probe")
        planted = list(range(probe + 1, probe + 41))
        made = self.run_in("sh", "-ec", 'cd "$PGDATA/base"; for o in "$@"; do mkdir "$o"; echo x > "$o/1"; done',
                           "plant", *map(str, planted), user="postgres")
        self.assertEqual(made.returncode, 0, made.stderr)
        created = []
        try:
            reply = self.status()
            reported = {item["oid"] for item in reply["warnings"] if item["code"] == "orphan-directory"}
            self.assertEqual(reported, set(planted))
            self.assertEqual(reply["result"], {"engine": "postgres", "orphan_scan": "complete"})
            self.assertTrue(all(item["tablespace"] == "pg_default" and item["path"] == f"base/{item['oid']}"
                                and item["kib"] > 0 and item["name"] is None
                                for item in reply["warnings"] if item["code"] == "orphan-directory"))
            for index in range(5):
                self.accept(f"CREATE DATABASE v1_after_orphan_{index}", "admin")
                created.append(int(self.accept(f"SELECT oid FROM pg_database WHERE datname='v1_after_orphan_{index}'")))
            self.assertFalse(set(created) & set(planted), created)
            self.assertGreater(min(created), max(planted))
            # Each planted directory is untouched: still only its own marker file.
            listing = self.run_in("sh", "-ec", 'cd "$PGDATA/base"; for o in "$@"; do echo "$o $(ls "$o") $(cat "$o/1")"; done',
                                  "check", *map(str, planted), user="postgres")
            self.assertEqual(listing.stdout.split("\n")[:-1], [f"{oid} 1 x" for oid in planted])
        finally:
            for index in range(len(created)):
                self.accept(f"DROP DATABASE IF EXISTS v1_after_orphan_{index}")
            self.run_in("sh", "-ec", 'cd "$PGDATA/base"; for o in "$@"; do rm -rf "./$o"; done',
                        "clear", *map(str, planted), user="postgres")
        self.assertEqual([item for item in self.status()["warnings"] if item["code"] == "orphan-directory"], [])


    def test_an_orphan_in_a_tablespace_is_reported_with_its_real_path(self):
        made = self.run_in("sh", "-ec", "mkdir -p /var/lib/postgresql/v1_space", user="postgres")
        self.assertEqual(made.returncode, 0, made.stderr)
        self.accept("CREATE TABLESPACE v1_space LOCATION '/var/lib/postgresql/v1_space'")
        space = self.accept("SELECT oid FROM pg_tablespace WHERE spcname='v1_space'")
        try:
            self.accept("CREATE DATABASE v1_in_space TABLESPACE v1_space")
            planted = self.run_in("sh", "-ec", 'cd "$PGDATA"/pg_tblspc/"$1"/PG_*; mkdir 4242424; echo x > 4242424/1; '
                                  'echo "pg_tblspc/$1/${PWD##*/}/4242424"', "plant", space, user="postgres")
            self.assertEqual(planted.returncode, 0, planted.stderr)
            warnings = [item for item in self.status()["warnings"] if item["code"] == "orphan-directory"]
            self.assertEqual([(item["tablespace"], item["oid"], item["path"]) for item in warnings],
                             [("v1_space", 4242424, planted.stdout.strip())])
            check = self.run_in("sh", "-ec", 'test -f "$PGDATA/$1/1"', "check", planted.stdout.strip(), user="postgres")
            self.assertEqual(check.returncode, 0)
        finally:
            self.run_in("sh", "-ec", 'rm -rf "$PGDATA"/pg_tblspc/"$1"/PG_*/4242424', "clear", space, user="postgres")
            self.accept("DROP DATABASE IF EXISTS v1_in_space")
            self.accept("DROP TABLESPACE IF EXISTS v1_space")


if __name__ == "__main__":
    unittest.main()
