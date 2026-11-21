"""The PostgreSQL service's healthcheck: a sign-in as demo that answers a query, with no server error."""

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


def test_postgres_healthcheck_signs_in_as_demo_and_answers_a_query():
    test = probe()
    assert test[0] == "CMD-SHELL"
    assert "-U demo" in test[1] and "SELECT 1" in test[1] and "SET " not in test[1]
    assert test[1].rstrip().endswith("| grep -qx 1")


@unittest.skipUnless(os.environ.get("DL077_GATE_TARGET") and os.environ.get("DL077_PG_IMAGE"),
                     "requires the isolated store and a PostgreSQL image")
class HealthProbeTests(unittest.TestCase):
    def test_a_healthy_probe_raises_no_server_error(self):
        """The probe on a healthy server leaves no ERROR in the server's log."""
        from native import Target, capacity
        target = Target()
        name = "dl077-health-quiet-" + uuid4().hex

        def podman(*args, check=True):
            return subprocess.run(target.podman_args(*args), capture_output=True, text=True, timeout=90, check=check)

        capacity()
        try:
            podman("run", "-d", "--name", name, "--network", "none", "--memory", "1g",
                   os.environ["DL077_PG_IMAGE"], "postgres")
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
        finally:
            # Its anonymous data volume too; a failed removal fails the test.
            removed = podman("rm", "-fv", "--ignore", name, check=False)
            self.assertIn(removed.returncode, (0,), removed.stderr)
