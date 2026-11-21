"""Opus round 3, 1, in depth: the PostgreSQL service is healthy only while read_policy is loaded."""

import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from uuid import uuid4

import yaml

from megasamples import compose, config

sys.path.insert(0, str(Path(__file__).parent / "gates"))


def probe():
    cfg = config.Config({"engines": {"postgres": {"datasets": ["pubs"]}}, "consoles": []})
    return yaml.safe_load(compose.render(cfg))["services"]["postgres"]["healthcheck"]["test"]


def test_postgres_healthcheck_requires_the_registered_policy_setting():
    test = probe()
    assert test[0] == "CMD-SHELL"
    # Round 5 (Sol P2-6, Opus P3-2): the probe raises no server error. It calls the library's own
    # report of whether it was loaded during preload, which a placeholder setting cannot answer.
    assert "megasamples_policy_loaded()" in test[1] and "SET " not in test[1]
    assert test[1].rstrip().endswith("| grep -qx t")


@unittest.skipUnless(os.environ.get("DL077_GATE_TARGET") and os.environ.get("DL077_PG_POLICY_IMAGE"),
                     "requires the isolated store and the policy image")
class HealthPlaceholderTests(unittest.TestCase):
    def test_a_placeholder_setting_does_not_pass_the_healthcheck(self):
        from native import Target, capacity
        target = Target()
        name = "dl077-health-" + uuid4().hex

        def podman(*args, check=True, stdin=None):
            return subprocess.run(target.podman_args(*args), capture_output=True, text=True, timeout=90,
                                  check=check, input=stdin)

        capacity()
        # The wrapper bypassed and the library not loaded: the route the in-depth check exists for.
        podman("run", "-d", "--name", name, "--network", "none", "--memory", "1g", "--entrypoint",
               "docker-entrypoint.sh", os.environ["DL077_PG_POLICY_IMAGE"], "postgres", "-c",
               "shared_preload_libraries=")
        try:
            for _ in range(150):
                if podman("exec", name, "pg_isready", "-U", "postgres", check=False).returncode == 0:
                    break
                time.sleep(0.2)
            podman("exec", name, "psql", "-XqAt", "-U", "postgres", "-c",
                   "ALTER ROLE demo SET read_policy.loaded = 'on'")
            podman("exec", "-i", name, "sh", "-c", "umask 077; cat > /run/megasamples-health.pgpass",
                   stdin="*:*:*:demo:demo\n")
            self.assertNotEqual(podman("exec", name, "sh", "-c", probe()[1], check=False).returncode, 0)
        finally:
            podman("rm", "-fv", name, check=False)   # its anonymous data volume too (Sol round 6, P3-10)

    def test_a_healthy_probe_raises_no_server_error(self):
        """Round 5: the probe on a healthy server leaves no ERROR in the server's log."""
        from native import Target, capacity
        target = Target()
        name = "dl077-health-quiet-" + uuid4().hex

        def podman(*args, check=True):
            return subprocess.run(target.podman_args(*args), capture_output=True, text=True, timeout=90, check=check)

        capacity()
        podman("run", "-d", "--name", name, "--network", "none", "--memory", "1g",
               os.environ["DL077_PG_POLICY_IMAGE"], "postgres")
        try:
            for _ in range(150):
                if podman("exec", name, "pg_isready", "-U", "postgres", check=False).returncode == 0:
                    break
                time.sleep(0.2)
            before = podman("logs", name)
            for _ in range(5):
                self.assertEqual(podman("exec", name, "sh", "-c", probe()[1], check=False).returncode, 0)
            after = podman("logs", name)
            new = (after.stdout + after.stderr)[len(before.stdout + before.stderr):]
            self.assertNotIn("ERROR", new)
            # The probe's own account may call the report, and only through its grant.
            # Rounds 6 and 7 (Sol P2-1, Opus P3-1): of every role that is not built in, only demo, the
            # probe's account, and the superuser may call it, in every connectable database.
            databases = podman("exec", name, "psql", "-XqAt", "-U", "postgres", "-d", "postgres", "-c",
                               "SELECT datname FROM pg_database WHERE datallowconn ORDER BY 1").stdout.split()
            self.assertTrue({"megasamples", "postgres", "template1"} <= set(databases), databases)
            for database in databases:
                allowed = podman("exec", name, "psql", "-XqAt", "-U", "postgres", "-d", database, "-c",
                                 "SELECT string_agg(rolname, ',' ORDER BY rolname) FROM pg_roles "
                                 "WHERE rolname NOT LIKE 'pg\\_%' AND has_function_privilege(oid, "
                                 "'pg_catalog.megasamples_policy_loaded()', 'EXECUTE')")
                self.assertEqual(allowed.stdout.strip(), "demo,postgres", database)
        finally:
            podman("rm", "-fv", name, check=False)   # its anonymous data volume too (Sol round 6, P3-10)
