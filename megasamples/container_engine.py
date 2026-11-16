"""What the container engine behind `docker` is, where that changes how the corpus calls it.

Rootful Docker is what the corpus was built on. A rootless engine (rootless Docker, or Podman
without root) maps the caller onto container root, and Podman builds images with Buildah rather
than BuildKit, so two calls depend on which engine answers.
"""
import functools, os, subprocess


@functools.lru_cache(maxsize=None)
def _info(template):
    return subprocess.run(["docker", "info", "-f", template], capture_output=True, text=True).stdout


def rootless():
    return "name=rootless" in _info("{{json .SecurityOptions}}")


def podman():
    return "Podman" in subprocess.run(["docker", "version", "-f", "{{json .Server.Components}}"],
                                      capture_output=True, text=True).stdout


def host_user():
    """The container user that writes files the caller owns, for `docker exec -u`: the caller's own
    uid on rootful Docker, which maps container uids straight onto the host's; container root on a
    rootless engine, which maps the caller onto root and every other uid onto a subordinate range
    the caller cannot write to or delete from."""
    return "0:0" if rootless() else f"{os.getuid()}:{os.getgid()}"


def build_env():
    """The environment for `docker build`. The Dockerfiles use dockerfile:1.7 syntax (heredocs),
    which Docker builds only with BuildKit; Podman builds them with Buildah, and Docker's client
    refuses DOCKER_BUILDKIT=1 against it without the buildx plugin."""
    return {**os.environ} if podman() else {**os.environ, "DOCKER_BUILDKIT": "1"}
