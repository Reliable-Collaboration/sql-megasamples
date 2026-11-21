"""The copy client needs only its two runtime drivers in an installed package."""

from pathlib import Path
import tomllib


def test_copy_drivers_are_declared_as_runtime_dependencies():
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    installed = {requirement.split("==", 1)[0] for requirement in metadata["project"]["dependencies"]}
    assert installed == {"psycopg", "PyMySQL[rsa]"}
