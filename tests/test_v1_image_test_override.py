"""The image tests' password overrides are checked only on the container the run started (Sol round 10, P2-1).

A run interrupted after its override container started leaves that container under the fixed name. The next
run's launch then fails on the name; if its result is ignored, the checks query the old container, whose
working passwords can make a broken wrapper in the new image pass. Against a fake docker: a leftover is
removed with its volumes before the launch, the launch's result is checked, and every query goes to the ID
the launch returned.
"""

import subprocess

import pytest

from megasamples.engines.mysql import image_test as mysql_image_test
from megasamples.engines.postgres import image_test as postgres_image_test

MODULES = [mysql_image_test, postgres_image_test]


class Docker:
    """A daemon holding one leftover override container from an interrupted run."""

    def __init__(self, module, launch_fails=False, leftover=True):
        self.name = module.NAME + "2"
        self.containers = {self.name: "old-id"} if leftover else {}
        self.launch_fails, self.calls = launch_fails, []

    def sh(self, *args, **kw):
        self.calls.append(args)
        code, out, err = 0, "", ""
        if args[:2] == ("docker", "rm"):
            for name in args[2:]:
                if not name.startswith("-"):
                    self.containers = {n: i for n, i in self.containers.items() if name not in (n, i)}
        elif args[:2] == ("docker", "run"):
            name = args[args.index("--name") + 1]
            if self.launch_fails or name in self.containers:
                code, err = 125, f'the container name "{name}" is already in use'
            else:
                self.containers[name] = "new-id"
                out = "new-id\n"
        return subprocess.CompletedProcess(args, code, out, err)


def drive(module, monkeypatch, docker):
    queried = []

    def query(sql, user="root", pw="root", database=None, container=module.NAME):
        queried.append(container)
        live = container in docker.containers.values() or container in docker.containers
        # Both containers answer as a correct image would; only which one is asked matters here.
        ok = live and (pw in ("sekret", "viewer"))
        return subprocess.CompletedProcess([], 0 if ok else 1, "1\n" if ok else "", "")
    monkeypatch.setattr(module, "sh", docker.sh)
    monkeypatch.setattr(module, "q", query)
    if hasattr(module, "q_net"):
        monkeypatch.setattr(module, "q_net", query)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)
    checks = module.Checks()
    module.override_checks(checks)
    return checks, queried


@pytest.mark.parametrize("module", MODULES, ids=["mysql", "postgres"])
def test_a_leftover_override_container_is_replaced_and_never_queried(module, monkeypatch):
    docker = Docker(module)
    checks, queried = drive(module, monkeypatch, docker)
    assert queried and set(queried) == {"new-id"}, queried
    assert checks.failures == []
    assert "old-id" not in docker.containers.values()
    assert docker.containers == {}, "the run's own override container is removed too"


@pytest.mark.parametrize("module", MODULES, ids=["mysql", "postgres"])
def test_a_failed_launch_fails_the_checks_and_queries_nothing(module, monkeypatch):
    docker = Docker(module, launch_fails=True)
    checks, queried = drive(module, monkeypatch, docker)
    assert queried == []
    assert checks.failures and "could not start" in checks.failures[0]
