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
            # The positive control (Sol round 7, P3-8): a create of the namespace's own form succeeds.
            inside = psql(probes[-1], "CREATE DATABASE copy_chinook_0123456789ab TEMPLATE chinook_start",
                          user="copier", database="megasamples")
            self.assertEqual(inside.returncode, 0, inside.stderr)
            self.assertEqual(psql(probes[-1], "DROP DATABASE copy_chinook_0123456789ab").returncode, 0)
            # ALTER SYSTEM persists in the volume; the next start must refuse it.
            self.assertEqual(psql(probes[-1], "ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements'").returncode, 0)
            podman("stop", probes[-1])
            probes.append(name + "-persisted")
            self.assertFalse(start(probes[-1], "postgres"))
            refused(probes[-1])
        finally:
            podman("rm", "-f", *probes, check=False)
            podman("volume", "rm", name, check=False)

    def test_round_four_start_routes(self):
        """Sol round 4, P2-1 and P3-7; Opus round 4, P3-1 and P3-4."""
        target = Target()
        name = "dl077-policy-r4-" + uuid4().hex
        mount = name + ":/var/lib/postgresql"
        image = os.environ["DL077_PG_POLICY_IMAGE"]
        secret = Path(os.environ["DL077_GATE_TARGET"]).parent / (name + ".env")
        secret.write_text("POSTGRES_PASSWORD=r4-synthetic-key\n")
        secret.chmod(0o600)

        def podman(*args, check=True, env=None):
            return subprocess.run(target.podman_args(*args), capture_output=True, text=True, timeout=90,
                                  check=check, env=env)

        def start(probe, *command, options=(), volume=None):
            capacity()
            podman("run", "-d", "--name", probe, "--memory", "1g", "-v", volume or mount, *options, image, *command)
            for _ in range(150):
                if podman("inspect", "--format", "{{.State.Status}}", probe).stdout.strip() == "exited":
                    return False
                if podman("exec", probe, "pg_isready", "-U", "postgres", check=False).returncode == 0:
                    return True
                time.sleep(0.2)
            self.fail("neither started nor exited")

        def logs(probe):
            out = podman("logs", probe)
            return out.stdout + out.stderr

        def psql(probe, sql, user="postgres", database="postgres"):
            return podman("exec", probe, "psql", "-XqAt", "-U", user, "-d", database, "-c", sql, check=False)

        def tcp_key(probe, key="r4-synthetic-key"):
            # Password-authenticated TCP. The image trusts its own loopback, so the probe connects to the
            # container's network address, where pg_hba requires scram-sha-256; the key reaches psql
            # through the podman call's environment.
            return podman("exec", "-e", "PGPASSWORD", probe, "sh", "-c",
                          'psql -XqAt -w -h "$(hostname -i | cut -d" " -f1)" -U postgres -d postgres -c "SELECT 1"',
                          check=False, env={**os.environ, "PGPASSWORD": key})

        def tcp_key_accepted(probe, key="r4-synthetic-key"):
            result = tcp_key(probe, key)
            return result.returncode == 0 and result.stdout.strip() == "1"

        def tcp_key_refused(probe, key):
            # A refusal for the stated reason: scram rejected this key, not a failed exec or connection.
            result = tcp_key(probe, key)
            return result.returncode == 2 and "password authentication failed" in result.stderr

        def namespace_enforced(probe):
            # Opus round 3, 1 and Sol round 7, P3-8: the owner's out-of-namespace create is refused for
            # its namespace, and a create of the namespace's own form succeeds, as a positive control.
            outside = psql(probe, "CREATE DATABASE outside_namespace TEMPLATE chinook_start", "copier", "megasamples")
            inside = psql(probe, "CREATE DATABASE copy_chinook_0123456789ab TEMPLATE chinook_start", "copier",
                          "megasamples")
            if inside.returncode == 0:
                psql(probe, "DROP DATABASE copy_chinook_0123456789ab")
            return outside.returncode != 0 and "namespace" in outside.stderr and inside.returncode == 0

        # Round 6 (Sol P2-6, Opus 1): a case whose outcome is a credential gets a volume of its own, so
        # an earlier case's password change cannot satisfy it.
        volumes, probes = [], []
        try:
            # Sol round 7, P3-9: every resource is created inside the cleanup scope, and tracked.
            for volume in (name, name + "-nonroot", name + "-path"):
                podman("volume", "create", volume)
                volumes.append(volume)
            # Opus P3-1, reconciled by test: as a non-root user the image exits before the public server
            # starts, because its health passfile is root's to write. With an override set, the private
            # password start runs first and applies it (Sol round 5, P3-7, a workstream 1 input), so the
            # outcome asserted is the container's exit and what it left behind, not readiness.
            nonroot = name + "-nonroot:/var/lib/postgresql"
            probes.append(name + "-nonroot")
            capacity()
            podman("run", "-d", "--name", probes[-1], "--memory", "1g", "-v", nonroot, "--user", "postgres",
                   "--env-file", str(secret), image, "/usr/lib/postgresql/18/bin/postgres")
            for _ in range(150):
                if podman("inspect", "--format", "{{.State.Status}}", probes[-1]).stdout.strip() == "exited":
                    break
                time.sleep(0.2)
            self.assertEqual(podman("inspect", "--format", "{{.State.Status}}", probes[-1]).stdout.strip(), "exited")
            self.assertNotEqual(podman("inspect", "--format", "{{.State.ExitCode}}", probes[-1]).stdout.strip(), "0")
            # What it leaves behind, pinned until workstream 1 decides: nothing listened on TCP, and the
            # private start had already applied the override before the exit.
            # The private server's log goes to /dev/null, so these lines witness the public server only.
            self.assertNotIn("listening on IPv4", logs(probes[-1]), "a public server listened on IPv4")
            self.assertNotIn("listening on IPv6", logs(probes[-1]), "a public server listened on IPv6")
            probes.append(name + "-nonroot-after")
            self.assertTrue(start(probes[-1], "postgres", volume=nonroot))
            self.assertTrue(tcp_key_accepted(probes[-1]), "the non-root start had not applied the override")
            self.assertTrue(tcp_key_refused(probes[-1], "root"), "the probe did not reach scram authentication")
            podman("stop", probes[-1])
            # The path form as root is the server named by its path: on a volume of its own, it starts with
            # the override applied and the image's default key refused.
            probes.append(name + "-path")
            self.assertTrue(start(probes[-1], "/usr/lib/postgresql/18/bin/postgres",
                                  options=("--env-file", str(secret)), volume=name + "-path:/var/lib/postgresql"),
                            logs(probes[-1])[-300:])
            self.assertTrue(tcp_key_accepted(probes[-1]), "the path form skipped the password override")
            # Under scram a role has one key: this witnesses the probe reaching scram, not a second key.
            self.assertTrue(tcp_key_refused(probes[-1], "root"), "the probe did not reach scram authentication")
            # Sol P3-7: a quoted preload entry is refused rather than split on its commas.
            probes.append(name + "-quoted")
            podman("stop", probes[-2])
            self.assertFalse(start(probes[-1], "postgres", "-c",
                                   'shared_preload_libraries="pg_stat_statements,read_policy"'))
            self.assertIn("refuses a quoted preload entry", logs(probes[-1]))
            # Sol P2-1: a preload persisted without read_policy, restored only on the command line.
            probes.append(name + "-base")
            self.assertTrue(start(probes[-1], "postgres"))
            self.assertEqual(psql(probes[-1], "ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements'").returncode, 0)
            podman("stop", probes[-1])
            probes.append(name + "-private")
            self.assertFalse(start(probes[-1], "postgres", "-c", "shared_preload_libraries=read_policy",
                                   options=("--env-file", str(secret))))
            self.assertIn("refuses a server without the read_policy library", logs(probes[-1]))
            # Without password overrides there is no private start, and the public one has the hook.
            probes.append(name + "-public")
            self.assertTrue(start(probes[-1], "postgres", "-c", "shared_preload_libraries=read_policy"))
            self.assertTrue(namespace_enforced(probes[-1]), "the public start lacks the namespace hook")
            self.assertEqual(psql(probes[-1], "ALTER SYSTEM RESET shared_preload_libraries").returncode, 0)
            podman("stop", probes[-1])
            # Opus P3-4: files the upstream image would repair are repaired before the check.
            podman("run", "--rm", "--name", name + "-chown", "--user", "root", "--entrypoint", "chown", "-v", mount,
                   image, "-R", "4321", "/var/lib/postgresql/18/docker")
            probes.append(name + "-owned")
            self.assertTrue(start(probes[-1], "postgres"), logs(probes[-1])[-400:])
        finally:
            removed = [podman("rm", "-f", "--ignore", *probes, check=False).returncode if probes else 0,
                       podman("volume", "rm", *volumes, check=False).returncode if volumes else 0]
            secret.unlink()
            self.assertEqual(removed, [0, 0], "teardown left task containers or volumes")
