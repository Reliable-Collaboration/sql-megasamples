"""The start tests' cleanup scope, against a fake podman (Opus round 8, P3-2; Sol round 8, P3-4).

Each resource is registered before the command that makes it, so a launch that creates its container and
then fails is still removed; a failed removal, a labeled leftover or a changed volume count fails the test;
and a failure in the test body is reported, not replaced by the cleanup's.
"""

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "gates"))
from start_scope import Scope  # noqa: E402


class FakePodman:
    """A store of containers and volumes; a container's run makes an anonymous volume, as the image's does."""

    def __init__(self, fail_launch=False, fail_rm=False, keep_anonymous=False, keep_container=False,
                 fail_inventory=None):
        self.containers, self.volumes, self.calls = {}, {}, []
        self.fail_launch, self.fail_rm, self.keep_anonymous = fail_launch, fail_rm, keep_anonymous
        self.keep_container, self.fail_inventory = keep_container, fail_inventory
        self.store_listings_ok = 1      # with fail_inventory="store": the opening listing succeeds
        self.anonymous = 0

    def __call__(self, *args, check=True):
        self.calls.append(args)
        code, out = 0, ""
        if args[:2] == ("volume", "create"):
            label = args[args.index("--label") + 1]
            self.volumes[args[-1]] = label
        elif args[0] == "run":
            name = args[args.index("--name") + 1]
            label = args[args.index("--label") + 1] if "--label" in args else ""
            self.anonymous += 1
            anonymous = f"anon{self.anonymous}"
            self.volumes[anonymous] = ""
            self.containers[name] = (label, anonymous)
            code = 125 if self.fail_launch else 0
        elif args[0] == "rm":
            names = [a for a in args[1:] if not a.startswith("-")]
            for name in names:
                if name in self.containers and not self.keep_container:
                    _, anonymous = self.containers.pop(name)
                    if "-fv" in args and not self.keep_anonymous:
                        self.volumes.pop(anonymous, None)
            code = 1 if self.fail_rm else 0
        elif args[:2] == ("volume", "exists"):
            code = 0 if args[2] in self.volumes else 1
        elif args[:2] == ("volume", "rm"):
            for name in args[2:]:
                self.volumes.pop(name, None)
        elif args[:2] == ("volume", "ls"):
            wanted = next((a.split("=", 1)[1] for a in args if a.startswith("label=")), None)
            out = "\n".join(v for v, label in self.volumes.items() if wanted is None or label == wanted)
            if wanted and self.fail_inventory == "volumes":
                code, out = 125, ""
            if not wanted and self.fail_inventory == "store" and self.calls.count(args) > self.store_listings_ok:
                code, out = 125, ""
        elif args[0] == "ps":
            wanted = next(a.split("=", 1)[1] for a in args if a.startswith("label="))
            out = "\n".join(c for c, (label, _) in self.containers.items() if label == wanted)
            if self.fail_inventory == "containers":
                code, out = 125, ""
        result = subprocess.CompletedProcess(args, code, out, "fake failure" if code else "")
        if check and code:
            raise subprocess.CalledProcessError(code, args, out, result.stderr)
        return result


def outcome(body, podman):
    """Run body(scope) as a test; return the unittest result."""
    class Case(unittest.TestCase):
        def runTest(self):
            body(Scope(self, podman))
    result = unittest.TestResult()
    Case().run(result)
    return result


class ScopeTests(unittest.TestCase):
    def test_everything_made_is_removed_with_its_anonymous_volume(self):
        podman = FakePodman()
        podman.volumes["unrelated"] = ""
        result = outcome(lambda scope: (scope.volume("v"), scope.run("c", "image")), podman)
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertEqual(podman.containers, {})
        self.assertEqual(list(podman.volumes), ["unrelated"])

    def test_a_launch_that_fails_after_creating_its_container_is_still_removed(self):
        podman = FakePodman(fail_launch=True)
        result = outcome(lambda scope: scope.run("c", "image"), podman)
        self.assertEqual(len(result.errors), 1)           # the launch's own error, reported
        self.assertIn("CalledProcessError", result.errors[0][1])
        self.assertEqual(podman.containers, {})
        self.assertEqual(podman.volumes, {})

    def test_a_failed_removal_fails_the_test(self):
        result = outcome(lambda scope: scope.run("c", "image"), FakePodman(fail_rm=True))
        self.assertFalse(result.wasSuccessful())
        self.assertIn("teardown", "".join(text for _, text in result.failures + result.errors))

    def test_an_anonymous_volume_left_behind_fails_the_test(self):
        # rm without its volumes (the round 7 leak) exits 0; the store's count still shows it.
        result = outcome(lambda scope: scope.run("c", "image"), FakePodman(keep_anonymous=True))
        self.assertFalse(result.wasSuccessful())
        self.assertIn("volume count", "".join(text for _, text in result.failures + result.errors))

    def test_a_labeled_container_left_behind_fails_the_test(self):
        result = outcome(lambda scope: scope.run("c", "image"), FakePodman(keep_container=True))
        self.assertFalse(result.wasSuccessful())
        self.assertIn("labeled leftovers: 1 containers", "".join(t for _, t in result.failures + result.errors))

    def test_a_failed_inventory_query_fails_the_test(self):
        # Round 9 (Sol 4): an empty answer from a failed query is not an empty inventory.
        for which in ("containers", "volumes"):
            with self.subTest(which=which):
                result = outcome(lambda scope: scope.run("c", "image"), FakePodman(fail_inventory=which))
                self.assertFalse(result.wasSuccessful())
                self.assertIn("inventory", "".join(t for _, t in result.failures + result.errors))

    def test_a_failed_store_listing_fails_the_test(self):
        # Opus round 10, N4: the store-wide listing, at the close and at the open, is checked too.
        result = outcome(lambda scope: scope.run("c", "image"), FakePodman(fail_inventory="store"))
        self.assertFalse(result.wasSuccessful())
        self.assertIn("inventory query volume ls", "".join(t for _, t in result.failures + result.errors))
        podman = FakePodman(fail_inventory="store")
        podman.store_listings_ok = 0
        result = outcome(lambda scope: None, podman)
        self.assertFalse(result.wasSuccessful())
        self.assertIn("inventory query volume ls", "".join(t for _, t in result.failures + result.errors))

    def test_a_concurrent_removal_does_not_hide_a_leak(self):
        # Round 9 (Opus N5): the check compares volume sets, so another removal cannot offset a leak.
        podman = FakePodman(keep_anonymous=True)
        podman.volumes["unrelated"] = ""

        def body(scope):
            scope.run("c", "image")
            del podman.volumes["unrelated"]
        result = outcome(body, podman)
        self.assertFalse(result.wasSuccessful())
        self.assertIn("anon1", "".join(t for _, t in result.failures + result.errors))

    def test_the_body_failure_is_reported_beside_a_teardown_failure(self):
        def body(scope):
            scope.run("c", "image")
            raise AssertionError("the body's own failure")
        result = outcome(body, FakePodman(fail_rm=True))
        reported = "".join(text for _, text in result.failures + result.errors)
        self.assertIn("the body's own failure", reported)
        self.assertIn("teardown", reported)

    def test_each_resource_is_registered_before_the_command_that_makes_it(self):
        podman = FakePodman()
        seen = []

        def body(scope):
            original = podman.__call__

            def spy(*args, check=True):
                if args[0] == "run" or args[:2] == ("volume", "create"):
                    seen.append((list(scope.containers), list(scope.volumes)))
                return original(*args, check=check)
            scope.podman = spy
            scope.volume("v")
            scope.run("c", "image")
        outcome(body, podman)
        self.assertEqual(seen, [([], ["v"]), (["c"], ["v"])])



class NamespaceCheckTests(unittest.TestCase):
    """Sol round 8, P3-5: only the hook's own refusal counts, and each attempt uses a fresh name."""

    HOOK = 'ERROR:  42501: database name does not match the namespace and template\nLOCATION:  x\n'

    def check(self, outside_error, inside_code=0):
        from start_scope import namespace_enforced
        names = []

        def podman(*args, check=True):
            sql = args[-1]
            if sql.startswith("CREATE DATABASE outside_"):
                names.append(sql.split()[2])
                return subprocess.CompletedProcess(args, 1, "", outside_error)
            if sql.startswith("CREATE DATABASE copy_"):
                names.append(sql.split()[2])
                return subprocess.CompletedProcess(args, inside_code, "", "" if inside_code == 0 else "ERROR")
            return subprocess.CompletedProcess(args, 0, "", "")
        return namespace_enforced(podman, "probe"), names

    def test_the_hooks_refusal_with_a_working_control_is_enforcement(self):
        self.assertTrue(self.check(self.HOOK)[0])

    def test_a_duplicate_name_error_is_not_enforcement(self):
        # A fixture that already holds the name: PostgreSQL's error names it, and says nothing of policy.
        duplicate = 'ERROR:  42P04: database "outside_namespace" already exists\n'
        self.assertFalse(self.check(duplicate)[0])

    def test_the_hooks_message_under_another_sqlstate_is_not_enforcement(self):
        # Round 9 (Sol 4): 42501 is required on its own, not only the message.
        self.assertFalse(self.check(self.HOOK.replace("42501", "42P01"))[0])

    def test_another_permission_error_is_not_enforcement(self):
        self.assertFalse(self.check('ERROR:  42501: permission denied to create database\n')[0])

    def test_a_failed_positive_control_is_not_enforcement(self):
        self.assertFalse(self.check(self.HOOK, inside_code=1)[0])

    def test_each_attempt_uses_a_fresh_name(self):
        first, second = self.check(self.HOOK)[1], self.check(self.HOOK)[1]
        self.assertEqual(len(set(first + second)), 4)


if __name__ == "__main__":
    unittest.main()
