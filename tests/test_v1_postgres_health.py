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
    # Opus round 4, P3-2 / Sol round 4, P3-6: the value, and that it is the registered internal
    # setting: demo may not read pg_settings (pg_show_all_settings is outside its allow-list), so
    # the probe shows registration by the server refusing to change it (55P02), which a
    # placeholder never does.
    assert "current_setting('read_policy.loaded')" in test[1]
    assert "SET read_policy.loaded" in test[1] and "55P02" in test[1]


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
            podman("rm", "-f", name, check=False)
