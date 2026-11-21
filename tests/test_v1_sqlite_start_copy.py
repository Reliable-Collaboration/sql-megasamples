"""The SQLite service's start copy must not leave a journal beside a freshly copied sample.

A console that was writing to a shared SQLite file when the stack stopped can leave a hot `-journal`
(or `-wal` and `-shm`). The start copy replaces the file from the image; SQLite would then apply the
old journal to the new file on its next open and corrupt the sample. The copy removes each file's
three siblings before moving the copy into place.
"""
import subprocess

import pytest

from megasamples import config as stack
from megasamples.engines import get

CFG = stack.Config({"engines": {"sqlite": {"datasets": ["sakila"]}}})
SUFFIXES = ("-journal", "-wal", "-shm")


def run_start_copy(data, shared):
    command = get("sqlite").compose_service(CFG)["command"][2]
    local = (command.replace("$$", "$").replace("/data/", f"{data}/").replace("/shared/", f"{shared}/")
             .replace("exec sleep infinity", "true"))
    return subprocess.run(["sh", "-c", local], capture_output=True, text=True)


@pytest.mark.parametrize("suffix", SUFFIXES)
def test_start_copy_removes_each_files_stale_journal(tmp_path, suffix):
    data, shared = tmp_path / "data", tmp_path / "shared"
    data.mkdir()
    shared.mkdir()
    names = ["sakila.sqlite", "chinook.sqlite"]
    for name in names:
        (data / name).write_bytes(b"fresh " + name.encode())
        (shared / name).write_bytes(b"old")
        for every in SUFFIXES:
            (shared / (name + every)).write_bytes(b"stale")
    (shared / "unrelated.txt").write_bytes(b"kept")
    result = run_start_copy(data, shared)
    assert result.returncode == 0, result.stderr
    for name in names:
        assert (shared / name).read_bytes() == b"fresh " + name.encode()
        assert not (shared / (name + suffix)).exists(), f"{name}{suffix} left beside the fresh copy"
    assert (shared / ".complete").exists()
    assert (shared / "unrelated.txt").read_bytes() == b"kept"
