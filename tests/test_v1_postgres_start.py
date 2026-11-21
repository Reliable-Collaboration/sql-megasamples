"""Start the policy entrypoint on a retained pre-policy PostgreSQL volume."""

import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent / "gates"))
from native import Target, capacity


@unittest.skipUnless(all(os.environ.get(key) for key in (
    "DL077_GATE_TARGET", "DL077_PG_POLICY_IMAGE", "DL077_PG_PRE_POLICY_IMAGE",
)), "requires an isolated store and the two PostgreSQL images")
class PolicyStartupTests(unittest.TestCase):
    def test_refuses_a_volume_from_before_the_policy(self):
        target = Target()
        name = "dl077-policy-start-" + uuid4().hex
        mount = name + ":/var/lib/postgresql"

        def podman(*args, check=True):
            return subprocess.run(target.podman_args(*args), capture_output=True, text=True,
                                  timeout=45, check=check)

        podman("volume", "create", name)
        try:
            capacity()
            podman("run", "-d", "--name", name + "-seed", "--network", "none", "--memory", "1g",
                   "-v", mount, os.environ["DL077_PG_PRE_POLICY_IMAGE"], "postgres")
            for _ in range(150):
                if podman("exec", name + "-seed", "pg_isready", "-U", "postgres", check=False).returncode == 0:
                    break
                time.sleep(0.2)
            else:
                self.fail("pre-policy image did not start")
            podman("stop", name + "-seed")
            capacity()
            podman("run", "-d", "--name", name, "--network", "none", "--memory", "1g",
                   "-v", mount, os.environ["DL077_PG_POLICY_IMAGE"], "postgres")
            for _ in range(100):
                state = podman("inspect", "--format", "{{.State.Status}}", name).stdout.strip()
                if state == "exited":
                    break
                self.assertNotEqual(podman("exec", name, "pg_isready", "-U", "postgres",
                                           check=False).returncode, 0, "pre-policy volume started")
                time.sleep(0.1)
            self.assertEqual(state, "exited")
            logs = podman("logs", name)
            self.assertIn("PostgreSQL data has no compatible megasamples read policy", logs.stderr + logs.stdout)
            self.assertNotIn("ready to accept connections", logs.stdout + logs.stderr)
        finally:
            podman("rm", "-f", name, name + "-seed", check=False)
            podman("volume", "rm", name)
