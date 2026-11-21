"""The cleanup scope of the PostgreSQL start tests (Opus round 8, P3-2; Sol round 8, P3-4).

Every container and volume a test makes carries the scope's label and is registered before the command
that makes it, so a command that creates its resource and then fails is still cleaned up. Cleanup runs
through the test's addCleanup, so a failure in the body is reported, not replaced; it removes containers
with their anonymous volumes, and fails the test when a removal fails, an inventory query fails, a labeled
resource remains, or the store holds a volume it did not hold when the scope opened (an anonymous volume
has no label). Comparing volume sets, not counts, means a volume someone else removes meanwhile cannot hide
a leak; a volume someone else creates meanwhile would be reported, so the store is assumed to be used by one
test at a time, as the task's runs are.
"""

from uuid import uuid4


class Scope:
    def __init__(self, test, podman):
        self.podman = podman
        self.label = "org.sql-megasamples.start-test=" + uuid4().hex
        self.containers, self.volumes = [], []
        self.before = self._inventory("volume", "ls", "-q")
        test.addCleanup(self.close)

    def _inventory(self, *arguments):
        result = self.podman(*arguments, check=False)
        if result.returncode:
            raise AssertionError(f"teardown: inventory query {' '.join(arguments[:2])} exited {result.returncode}")
        return set(result.stdout.split())

    def volume(self, name):
        self.volumes.append(name)
        self.podman("volume", "create", "--label", self.label, name)
        return name

    def run(self, name, *arguments, check=True):
        """podman run -d --name NAME, labeled; ARGUMENTS are the rest of the run command."""
        self.containers.append(name)
        return self.podman("run", "-d", "--name", name, "--label", self.label, *arguments, check=check)

    def run_once(self, name, *arguments):
        """A foreground podman run --rm, labeled and registered like any other container."""
        self.containers.append(name)
        return self.podman("run", "--rm", "--name", name, "--label", self.label, *arguments)

    def close(self):
        problems = []
        if self.containers:
            result = self.podman("rm", "-fv", "--ignore", *self.containers, check=False)
            if result.returncode:
                problems.append(f"container removal exited {result.returncode}: {result.stderr[-300:]}")
        present = [v for v in self.volumes if self.podman("volume", "exists", v, check=False).returncode == 0]
        if present:
            result = self.podman("volume", "rm", *present, check=False)
            if result.returncode:
                problems.append(f"volume removal exited {result.returncode}: {result.stderr[-300:]}")
        try:
            containers = self._inventory("ps", "-aq", "--filter", "label=" + self.label)
            volumes = self._inventory("volume", "ls", "-q", "--filter", "label=" + self.label)
            if containers or volumes:
                problems.append(f"labeled leftovers: {len(containers)} containers, {len(volumes)} volumes")
            after = self._inventory("volume", "ls", "-q")
            if after - self.before:
                problems.append(f"store volume count {len(self.before)} before, {len(after)} after; "
                                f"new volumes: {sorted(after - self.before)}")
        except AssertionError as failed:
            problems.append(str(failed))
        if problems:
            raise AssertionError("teardown: " + "; ".join(problems))


def namespace_enforced(podman, probe):
    """The owner's out-of-namespace create is refused by the hook itself, and a create of the namespace's
    own form succeeds (Opus round 3, 1; Sol round 7, P3-8; Sol round 8, P3-5). Fresh names each time, so
    a name left by an earlier attempt cannot answer with a duplicate-database error instead."""
    def psql(sql):
        return podman("exec", probe, "psql", "-XqAt", "-v", "VERBOSITY=verbose", "-U", "copier", "-d",
                      "megasamples", "-c", sql, check=False)
    outside = psql(f"CREATE DATABASE outside_{uuid4().hex[:12]} TEMPLATE chinook_start")
    inside_name = f"copy_chinook_{uuid4().hex[:12]}"
    inside = psql(f"CREATE DATABASE {inside_name} TEMPLATE chinook_start")
    if inside.returncode == 0:
        podman("exec", probe, "psql", "-XqAt", "-U", "postgres", "-d", "postgres", "-c",
               f"DROP DATABASE {inside_name}")
    return (outside.returncode != 0 and inside.returncode == 0 and
            "ERROR:  42501: database name does not match the namespace and template" in outside.stderr)
