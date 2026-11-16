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
