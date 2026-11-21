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

    def __init__(self, fail_launch=False, fail_rm=False, keep_anonymous=False):
        self.containers, self.volumes, self.calls = {}, {}, []
        self.fail_launch, self.fail_rm, self.keep_anonymous = fail_launch, fail_rm, keep_anonymous
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
                if name in self.containers:
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
        elif args[0] == "ps":
            wanted = next(a.split("=", 1)[1] for a in args if a.startswith("label="))
            out = "\n".join(c for c, (label, _) in self.containers.items() if label == wanted)
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


if __name__ == "__main__":
    unittest.main()
