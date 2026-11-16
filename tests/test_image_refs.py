"""Digest pins may retain a readable tag; tags are not part of a registry repository path."""
import pytest

from megasamples.pull_image import split_ref


@pytest.mark.parametrize("ref, expected", [
    ("mysql:26.10.0@sha256:abc", ("registry-1.docker.io", "library/mysql", "sha256:abc")),
    ("docker.io/library/postgres:18.7-trixie@sha256:abc", ("docker.io", "library/postgres", "sha256:abc")),
    ("localhost:5000/team/tool:1@sha256:abc", ("localhost:5000", "team/tool", "sha256:abc")),
    ("debian@sha256:abc", ("registry-1.docker.io", "library/debian", "sha256:abc")),
    ("debian:13.7-slim", ("registry-1.docker.io", "library/debian", "13.7-slim")),
])
def test_registry_image_reference(ref, expected):
    assert split_ref(ref) == expected


@pytest.mark.parametrize("platform", ["linux/amd64", "linux/arm64"])
def test_podman_uses_native_digest_aware_import(monkeypatch, platform):
    from subprocess import CompletedProcess
    from megasamples import container_engine, pull_image
    monkeypatch.setattr(container_engine, "podman", lambda: True)
    monkeypatch.setattr(pull_image, "get_manifest", lambda *a: pytest.fail("Podman must use its native importer"))
    calls = []
    monkeypatch.setattr(pull_image.subprocess, "run", lambda args, **kw: calls.append(args) or CompletedProcess(args, 0))
    ref = "debian:13.7-slim@sha256:" + "a" * 64
    assert pull_image.main([ref, "--platform", platform]) == 0
    assert calls == [["docker", "pull", "--platform", platform, ref]]
