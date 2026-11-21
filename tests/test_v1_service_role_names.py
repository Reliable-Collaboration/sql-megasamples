"""Configured account names cannot take a role the PostgreSQL service creates (Sol round 14, 6).

A reader named megasamples_read passed validation, and the generated CREATE ROLE then duplicated the group
image initialisation creates, aborting the build. The class: every role engines/postgres/init creates, and
every role name the generated DDL derives (megasamples_copy_<prefix>_owner and _read).
"""

import re
from pathlib import Path

import pytest

from megasamples import config
from megasamples.copy_config import CopySettings

ROOT = Path(__file__).parents[1]
SHIPPED = sorted({name for sql in (ROOT / "engines/postgres/init").glob("*.sql")
                  for name in re.findall(r"CREATE ROLE\s+\"?([a-z_][a-z0-9_]*)", sql.read_text())})


def settings(**accounts):
    raw = {"engines": {"postgres": {"datasets": ["chinook"]}}, "accounts": accounts}
    return CopySettings(config.Config(raw), "postgres", ["chinook"])


def test_the_shipped_roles_are_found():
    assert {"admin", "demo", "megasamples_read", "megasamples_working_read"} <= set(SHIPPED)


@pytest.mark.parametrize("name", [*SHIPPED, "megasamples_copy_copy_read", "megasamples_copy_copy_owner",
                                  "megasamples_anything", "megasamples_x"])
@pytest.mark.parametrize("kind", ["readers", "writers"])
def test_a_service_role_name_is_refused_as_an_account(name, kind):
    with pytest.raises(ValueError, match="invalid or duplicate account"):
        settings(**{kind: [{"name": name, "scopes": ["working"]}]})


def test_an_ordinary_account_name_is_accepted():
    assert "reader_b" in settings(readers=[{"name": "reader_b", "scopes": ["working"]}]).readers
