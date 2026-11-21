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
            # sol round 2, P2-2: the marker must certify the directory the server opens.
            retained = name + ":/retained"
            # Round 3 (Sol P2-1, Opus 1): setting names are case-insensitive, and the command may be a path.
            for index, override in enumerate((["postgres", "-D", "/retained/18/docker"],
                                              ["postgres", "-D/retained/18/docker"],
                                              ["postgres", "--pgdata=/retained/18/docker"],
                                              ["postgres", "-c", "data_directory=/retained/18/docker"],
                                              ["postgres", "--data-directory=/retained/18/docker"],
                                              ["postgres", "-c", "DATA_DIRECTORY=/retained/18/docker"],
                                              ["postgres", "--Data-Directory=/retained/18/docker"],
                                              ["/usr/lib/postgresql/18/bin/postgres", "-D", "/retained/18/docker"])):
                with self.subTest(override=override):
                    capacity()
                    probe = f"{name}-override{index}"
                    podman("run", "-d", "--name", probe, "--network", "none", "--memory", "1g",
                           "-v", retained, os.environ["DL077_PG_POLICY_IMAGE"], *override)
                    try:
                        for _ in range(100):
                            if podman("inspect", "--format", "{{.State.Status}}", probe).stdout.strip() == "exited":
                                break
                            self.assertNotEqual(podman("exec", probe, "pg_isready", "-U", "postgres",
                                                       check=False).returncode, 0, "the override started")
                            time.sleep(0.1)
                        logs = podman("logs", probe)
                        # postgres has no --pgdata option; asked for its configuration it refuses that
                        # argument, so the wrapper refuses it unread. Either refusal is the outcome.
                        self.assertTrue(any(message in logs.stdout + logs.stderr for message in (
                            "refuses a data directory other than PGDATA",
                            "could not read the server configuration")), logs.stdout + logs.stderr)
                        self.assertNotIn("ready to accept connections", logs.stdout + logs.stderr)
                    finally:
                        podman("rm", "-f", probe, check=False)
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

    def test_refuses_a_server_without_the_policy_library(self):
        """Opus round 3, 1: the marker proves the data; the server must also load read_policy."""
        target = Target()
        name = "dl077-policy-preload-" + uuid4().hex
        mount = name + ":/var/lib/postgresql"
        image = os.environ["DL077_PG_POLICY_IMAGE"]

        def podman(*args, check=True):
            return subprocess.run(target.podman_args(*args), capture_output=True, text=True,
                                  timeout=60, check=check)

        def start(probe, *command):
            capacity()
            podman("run", "-d", "--name", probe, "--network", "none", "--memory", "1g", "-v", mount, image, *command)
            for _ in range(150):
                if podman("inspect", "--format", "{{.State.Status}}", probe).stdout.strip() == "exited":
                    return False
                if podman("exec", probe, "pg_isready", "-U", "postgres", check=False).returncode == 0:
                    return True
                time.sleep(0.2)
            self.fail("neither started nor exited")

        def psql(probe, sql, user="postgres", database="postgres"):
            return podman("exec", probe, "psql", "-XqAt", "-U", user, "-d", database, "-c", sql, check=False)

        def refused(probe):
            logs = podman("logs", probe)
            self.assertIn("refuses a server without the read_policy library", logs.stdout + logs.stderr)
            self.assertNotIn("ready to accept connections", logs.stdout + logs.stderr)

        podman("volume", "create", name)
        probes = []
        try:
            probes.append(name + "-replace")
            self.assertFalse(start(probes[-1], "postgres", "-c", "shared_preload_libraries=pg_stat_statements"))
            refused(probes[-1])
            probes.append(name + "-upper")
            self.assertFalse(start(probes[-1], "postgres", "-c", "SHARED_PRELOAD_LIBRARIES=pg_stat_statements"))
            refused(probes[-1])
            probes.append(name + "-both")
            self.assertTrue(start(probes[-1], "postgres", "-c",
                                  "shared_preload_libraries=read_policy,pg_stat_statements"))
            self.assertEqual(psql(probes[-1], "SHOW read_policy.loaded").stdout.strip(), "on")
            outside = psql(probes[-1], "CREATE DATABASE outside_namespace TEMPLATE chinook_start",
                           user="copier", database="megasamples")
            self.assertNotEqual(outside.returncode, 0)
            self.assertIn("namespace", outside.stderr)
            # ALTER SYSTEM persists in the volume; the next start must refuse it.
            self.assertEqual(psql(probes[-1], "ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements'").returncode, 0)
            podman("stop", probes[-1])
            probes.append(name + "-persisted")
            self.assertFalse(start(probes[-1], "postgres"))
            refused(probes[-1])
        finally:
            podman("rm", "-f", *probes, check=False)
            podman("volume", "rm", name, check=False)
