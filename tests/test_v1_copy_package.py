"""The copy client needs only its two runtime drivers in an installed package."""

import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest


def test_copy_drivers_are_declared_as_runtime_dependencies():
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    installed = {requirement.split("==", 1)[0] for requirement in metadata["project"]["dependencies"]}
    assert installed == {"psycopg", "PyMySQL[rsa]"}


PIPELINE = ("yaml", "duckdb", "lxml", "sqlglot", "py7zr", "backports")
BLOCKER = """
import importlib.abc, runpy, sys
class Pipeline(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in {blocked!r}:
            raise ImportError('pipeline dependency imported by copy: ' + name)
sys.meta_path.insert(0, Pipeline())
sys.argv = ['megasamples', *sys.argv[1:]]
runpy.run_module('megasamples', run_name='__main__')
"""


def closed_port():
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.mark.parametrize("engine", ["sqlite", "mysql", "postgres"])
def test_copy_runs_without_pipeline_dependencies(engine, tmp_path):
    """T-28's reversal: a pipeline dependency imported by a copy module fails this."""
    if engine == "postgres":
        try:
            import psycopg  # noqa: F401
        except ImportError:
            pytest.skip("psycopg cannot load libpq here; the clean-install check covers it")
    if engine == "sqlite":
        (tmp_path / "templates").mkdir()
        (tmp_path / "copies").mkdir()
        (tmp_path / "templates" / "templates.json").write_text(
            json.dumps({"tag": "megasamples-manifest/1", "templates": []}))
        target = ["--templates", str(tmp_path / "templates"), "--dir", str(tmp_path / "copies")]
    else:
        secret = tmp_path / "password"
        secret.write_text("synthetic-test-key\n")
        secret.chmod(0o600)
        target = ["--host", "127.0.0.1", "--port", str(closed_port()), "--user", "copier",
                  "--password-file", str(secret)]
    result = subprocess.run(
        [sys.executable, "-c", BLOCKER.format(blocked=PIPELINE), "copy", "list", engine,
         "--prefix", "copy", *target],
        capture_output=True, text=True, timeout=30, cwd=Path(__file__).parents[1],
    )
    reply = json.loads(result.stdout)
    assert "pipeline dependency" not in result.stderr
    assert reply["error"] is None or reply["error"]["code"] != "internal", result.stdout + result.stderr
    assert result.returncode == (0 if engine == "sqlite" else 3), result.stdout + result.stderr
