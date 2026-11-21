"""SQLite gates whose assertions concern the filesystem."""

import errno
import fcntl
import hashlib
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from native import Unavailable, checked, require, same


def bind_directory(target):
    if "sqlite_bind" not in target.config:
        raise Unavailable("scratch target has no SQLite host/container bind mount")
    host = Path(target.config["sqlite_bind"]).resolve(strict=True)
    if host.stat().st_mode & 0o077:
        raise Unavailable("SQLite bind root is not private")
    target.container("sqlite_peer")
    return host


def container_fs(target, directory, expression, *args):
    return target.podman(
        "exec", target.container("sqlite_peer"), "sh", "-c",
        'cd "/scratch/$1" || exit 90; shift; ' + expression,
        "dl077", directory.name, *args,
    )


def publication(target):
    with tempfile.TemporaryDirectory(dir=bind_directory(target)) as scratch:
        directory = Path(scratch)
        final = directory / "copy"
        host_copy = directory / "host"
        host_copy.write_text("host")
        checked(container_fs(target, directory, 'printf container > container'))
        same((directory / "container").read_text(), "container")
        checked(container_fs(target, directory, 'set -C; printf original > copy'))
        same(final.read_text(), "original")
        for action in (lambda: final.open("x").close(), lambda: os.link(host_copy, final)):
            try:
                action()
            except FileExistsError as error:
                same(error.errno, errno.EEXIST)
            else:
                raise AssertionError("host operation replaced an occupied name")
        for expression in ('set -C; printf other > copy', 'ln container copy'):
            result = container_fs(target, directory, expression)
            require(result.returncode != 0 and "File exists" in result.stderr,
                    "container operation did not report an occupied name")
        same(final.read_text(), "original")
        final.unlink()

        for method in ("exclusive", "link"):
            def host_publish():
                deadline = time.monotonic() + 10
                while not (directory / "start").exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                require((directory / "start").exists(), "container did not reach the publication barrier")
                try:
                    if method == "exclusive":
                        with final.open("x") as output:
                            output.write("host")
                    else:
                        os.link(host_copy, final)
                except FileExistsError:
                    return 1
                return 0

            container_action = (
                'set -C; printf container > copy' if method == "exclusive" else 'ln container copy'
            )
            with ThreadPoolExecutor(max_workers=2) as pool:
                host = pool.submit(host_publish)
                peer = pool.submit(container_fs, target, directory,
                                   'touch start; ' + container_action)
                peer_result = peer.result()
                (directory / "start").touch()
                host_result = host.result()
            if peer_result.returncode:
                require("File exists" in peer_result.stderr,
                        "container race loser did not report an occupied name")
            same(sorted([host_result, int(peer_result.returncode != 0)]), [0, 1])
            same(final.read_text(), "host" if host_result == 0 else "container")
            final.unlink()
            (directory / "start").unlink()


def cross_mount_lock(target):
    with tempfile.TemporaryDirectory(dir=bind_directory(target)) as scratch:
        directory = Path(scratch)
        lock = directory / "copy.lock"
        expression = "flock -n -E 42 copy.lock true"
        lock.touch(exist_ok=False)
        checked(container_fs(target, directory, expression))
        with lock.open("rb") as holder:
            fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
            same(container_fs(target, directory, expression).returncode, 42)
            checked(container_fs(target, directory, "mv copy.lock retained.lock; touch copy.lock"))
            require(not os.path.samestat(os.fstat(holder.fileno()), lock.stat()),
                    "replacement of the opened lock file was not detected")
            require(os.path.samestat(os.fstat(holder.fileno()), (directory / "retained.lock").stat()),
                    "the old file did not retain the lock")
            checked(container_fs(target, directory, expression))


def bounded_mount(target):
    if "sqlite_full_mount" not in target.config:
        raise Unavailable("scratch target has no dedicated small SQLite filesystem")
    mount = Path(target.config["sqlite_full_mount"]).resolve(strict=True)
    capacity = os.statvfs(mount)
    if (not mount.is_mount() or mount.stat().st_dev == mount.parent.stat().st_dev
            or capacity.f_frsize * capacity.f_blocks > 128 * 1024 * 1024):
        raise Unavailable("expected a dedicated SQLite mount of at most 128 MiB")
    if any(mount.iterdir()):
        raise Unavailable("expected an empty task-owned SQLite mount")
    return mount


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def enospc_publication(target):
    mount = bounded_mount(target)
    block = os.statvfs(mount).f_frsize
    old, new = b'{"phase":"loading"}\n', b'{"phase":"done"}\n'
    old_hash, new_hash = [hashlib.sha256(record).hexdigest() for record in (old, new)]
    for kind, method, exists in (
        ("copy", os.link, False), ("sidecar", os.replace, False),
        ("reset", os.replace, True), ("operation", os.replace, True),
    ):
        with tempfile.TemporaryDirectory(dir=mount) as scratch:
            directory = Path(scratch)
            final, staged, filler = (directory / name for name in ("final", "staged", "fill"))
            if exists:
                final.write_bytes(old)
            before = old_hash if exists else None
            volume = b"new SQLite fixture" * block if kind in ("copy", "reset") else new
            expected = hashlib.sha256(volume).hexdigest()
            try:
                with filler.open("wb") as file:
                    free = os.statvfs(mount).f_bavail * block
                    os.posix_fallocate(file.fileno(), 0, free)
                with staged.open("wb") as file:
                    file.write(volume)
                    file.flush()
                    os.fsync(file.fileno())
            except OSError as error:
                same(error.errno, errno.ENOSPC)
                print(f"{kind}: stage reported ENOSPC")
            else:
                raise AssertionError(f"{kind}: the staging write did not reach ENOSPC")
            same(digest(final), before)
            require(digest(staged) != expected, "staging unexpectedly contains a whole new file")
            filler.unlink()
            staged.write_bytes(volume)
            try:
                with filler.open("wb") as file:
                    os.posix_fallocate(file.fileno(), 0, os.statvfs(mount).f_bavail * block)
            except OSError as error:
                same(error.errno, errno.ENOSPC)
            try:
                method(staged, final)
            except OSError as error:
                same(error.errno, errno.ENOSPC)
                same(digest(final), before)
                print(f"{kind}: publication at capacity reported ENOSPC")
            else:
                same(digest(final), expected)
                print(f"{kind}: publication at capacity published the whole file")
            if kind in ("sidecar", "operation"):
                same(expected, new_hash)


CASES = {
    "G-19a": publication,
    "G-19c": enospc_publication,
    "G-20": cross_mount_lock,
}
