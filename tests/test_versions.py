"""Release upgrade regressions: advertised versions and reproducible build inputs."""
import re
from pathlib import Path

import pytest

from megasamples import consoles
from megasamples.engines import get
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import server as postgres

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r".+@sha256:[0-9a-f]{64}$")


@pytest.mark.parametrize("engine, version", [("mysql", "9.7.4"), ("postgres", "18.7"), ("sqlite", "3.54.1")])
def test_advertised_engine_release(engine, version):
    assert get(engine).version == version


@pytest.mark.parametrize("engine, server", [("mysql", mysql), ("postgres", postgres)])
def test_build_server_and_baked_image_use_identical_pinned_input(engine, server):
    text = (ROOT / "engines" / engine / "Dockerfile").read_text()
    arguments = dict(re.findall(r"^ARG (\w+)=(\S+)$", text, re.M))
    inputs = re.findall(r"^FROM (\S+)", text, re.M)
    resolved = [re.sub(r"\$\{(\w+)\}", lambda m: arguments[m[1]], item) for item in inputs]
    assert resolved
    if engine == "postgres":
        assert all(PIN.fullmatch(item) for item in resolved)
    else:
        base = (ROOT / "engines/mysql/base.Dockerfile").read_text()
        upstream = re.findall(r"^FROM (\S+)", base, re.M)
        assert len(upstream) == 3 and all(PIN.fullmatch(item) for item in upstream)
    assert all(item == server.IMAGE for item in resolved)


def test_every_console_is_pinned():
    assert all(PIN.fullmatch(c.image) for c in consoles.CONSOLES)


@pytest.mark.parametrize("name, version", [("landing", "1.31.8"), ("cloudbeaver", "26.2.5"), ("dbgate", "7.3.6"), ("adminer", "6.3.0"), ("phpmyadmin", "5.2.3")])
def test_console_release(name, version):
    assert f":{version}@sha256:" in consoles.get(name).image


def test_optional_oracle_verifier_is_pinned():
    from megasamples.sources.verify_oracle import IMAGE
    assert PIN.fullmatch(IMAGE)


def test_sql_server_exporter_uses_current_release():
    from megasamples.sources.mssql import IMAGE
    assert "2025-CU11-ubuntu-24.04@sha256:" in IMAGE


def test_build_tools_use_current_pinned_releases():
    makefile = (ROOT / "Makefile").read_text()
    assert "python:v1.65.2-noble@sha256:" in makefile
    assert "playwright==1.65.2" in makefile
    assert "debian:13.7-slim@sha256:" in (ROOT / "engines/mysql/loader.Dockerfile").read_text()


def test_sqlite_release_is_built_from_verified_vendor_source():
    text = (ROOT / "engines/sqlite/Dockerfile").read_text()
    assert "sqlite-autoconf-3540100.tar.gz" in text
    assert "b6ced585c750916b1052667239a12c25a7ff34e7f06e1e6e01ecb0427657d9c4" in text
    assert "sha3_256" in text or "sha3-256" in text
