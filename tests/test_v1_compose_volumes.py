"""The stack's Compose routes keep no engine's anonymous data volume behind (Opus round 10, P2-1).

The engines' data directories are the anonymous volumes their images declare. Compose's `down` removes the
containers and leaves those volumes, and a later `up` makes fresh ones; `up --renew-anon-volumes` also leaves
the volume it replaced. Each route is driven against a fake docker daemon that models exactly that, and
must end with only the named volume (the SQLite files the consoles share) and the running containers'
own volumes in the store.
"""

import json
import subprocess
from types import SimpleNamespace

import pytest

from megasamples import job, workspace
import megasamples.console_config
import megasamples.console_images

SERVICES = {"mysql": "megasamples-mysql", "sqlite": "megasamples-sqlite"}
NAMED = "megasamples-sqlite"


class Daemon:
    def __init__(self, image="current"):
        self.serial = 0
        self.containers = {}            # name -> {"image", "anonymous"}
        self.volumes = {NAMED}
        self.calls = []
        for service in SERVICES:
            self.create(service, image)

    def anonymous(self):
        self.serial += 1
        volume = f"{self.serial:064x}"
        self.volumes.add(volume)
        return volume

    def create(self, service, image="current"):
        self.containers[SERVICES[service]] = {"image": image, "anonymous": self.anonymous()}

    def run(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append(argv)
        out, code = "", 0
        if argv[:2] == ["docker", "inspect"] and argv[3] == "{{.Image}}":
            container = self.containers.get(argv[4])
            out, code = (container["image"], 0) if container else ("", 1)
        elif argv[:3] == ["docker", "image", "inspect"]:
            out = "current"
        elif argv[:2] == ["docker", "inspect"] and argv[3] == "{{json .Mounts}}":
            container = self.containers.get(argv[4])
            if container is None:
                code = 1
            else:
                mounts = [{"Type": "volume", "Name": container["anonymous"]}]
                if argv[4] == SERVICES["sqlite"]:
                    mounts.append({"Type": "volume", "Name": NAMED})
                out = json.dumps(mounts)
        elif argv[:2] == ["docker", "volume"] and argv[2] == "rm":
            for volume in argv[3:]:
                if any(c["anonymous"] == volume for c in self.containers.values()):
                    code = 1
                else:
                    self.volumes.discard(volume)
        elif argv[:2] == ["docker", "compose"]:
            words = argv[2:]
            assert "-f" in words, "a Compose call names the generated file"
            if "down" in words:
                assert "-v" not in words and "--volumes" not in words, "down -v would remove the named volume"
                self.containers.clear()                    # anonymous volumes stay, as Compose leaves them
            elif "rm" in words:
                assert "--stop" in words and "--force" in words
                for container in self.containers.values():
                    if "--volumes" in words or "-v" in words:
                        self.volumes.discard(container["anonymous"])
                self.containers.clear()
            elif "up" in words:
                services = [w for w in words if w in SERVICES]
                if "--force-recreate" in words:
                    for service in services:
                        old = self.containers[SERVICES[service]]
                        renewed = "--renew-anon-volumes" in words
                        self.containers[SERVICES[service]] = {
                            "image": "current", "anonymous": self.anonymous() if renewed else old["anonymous"]}
                else:
                    for service in SERVICES:
                        if SERVICES[service] not in self.containers:
                            self.create(service)
        elif argv[:2] == ["docker", "ps"]:
            out = ""
        return subprocess.CompletedProcess(argv, code, out, "")

    def leftovers(self):
        attached = {c["anonymous"] for c in self.containers.values()}
        return self.volumes - attached - {NAMED}


@pytest.fixture
def daemon(monkeypatch):
    def install(image="current"):
        d = Daemon(image)
        monkeypatch.setattr(subprocess, "run", d.run)
        monkeypatch.setattr(job.os.path, "exists", lambda path: True)
        engines = {name: SimpleNamespace(name=name, container=SERVICES[name], image=f"img-{name}", title=name,
                                         port=None, connection_hint=lambda cfg: "") for name in SERVICES}
        monkeypatch.setattr(job.engine_registry, "get", engines.__getitem__)
        monkeypatch.setattr(job.stack, "load", lambda: SimpleNamespace(engines=list(SERVICES), consoles=[], ports={}))
        monkeypatch.setattr(megasamples.console_config, "main", lambda argv: 0)
        monkeypatch.setattr(job.compose, "main", lambda argv: 0)
        monkeypatch.setattr(megasamples.console_images, "build", lambda cfg: 0)
        return d
    return install


def test_down_takes_each_engines_anonymous_volume_and_keeps_the_named_one(daemon):
    d = daemon()
    assert job.down([]) == 0
    assert d.containers == {}
    assert d.leftovers() == set(), "down left the engines' data volumes"
    assert NAMED in d.volumes


def test_down_then_up_cycles_leave_nothing_behind(daemon):
    d = daemon()
    for _ in range(3):
        assert job.down([]) == 0
        assert job.up([]) == 0
    assert d.leftovers() == set()
    assert len(d.volumes) == 1 + len(SERVICES)          # the named one and the running containers' own


def test_clean_all_takes_the_stacks_anonymous_volumes(daemon):
    d = daemon()
    assert workspace.clean(also_stack=True) == 0
    assert d.containers == {}
    assert d.leftovers() == set()
    assert NAMED in d.volumes


def test_up_recreating_a_stale_engine_removes_the_volume_it_replaced(daemon):
    d = daemon(image="stale")
    before = {name: c["anonymous"] for name, c in d.containers.items()}
    assert job.up([]) == 0
    assert all(d.containers[name]["anonymous"] != volume for name, volume in before.items())
    assert d.leftovers() == set(), "up kept the data volume it replaced"
    assert NAMED in d.volumes
