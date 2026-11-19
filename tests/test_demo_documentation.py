"""Account documentation checked against init grants, without reading credentials."""
import os
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).parents[1]


def demo_grants(engine):
    grants = []
    for path in sorted((ROOT/'engines'/engine/'init').glob('*.sql')):
        # Read SQL for grant extraction only; never include its source in a failure.
        sql = re.sub(r'--[^\n]*', '', path.read_text())
        for privileges, scope, roles in re.findall(r'GRANT\s+(.+?)\s+ON\s+(.+?)\s+TO\s+([^;]+);', sql, re.I):
            if re.search(r"(?:^|[,\s])'?demo'?(?:@|[,\s]|$)", roles, re.I):
                grants.append((tuple(p.strip().upper() for p in privileges.split(',')), scope.strip()))
    return grants


def text(name, variable):
    return Path(os.environ.get(variable, ROOT/name)).read_text()


def mysql_scope(document):
    grants = demo_grants('mysql')
    # Derive the documentation rule from the actual demo target and privileges.
    assert grants == [(('SELECT', 'SHOW VIEW'), '*.*')], 'Review changed MySQL demo grants'
    assert 'every database' in document and '`*.*`' in document
    assert 'system schemas included' in document and '`mysql`' in document
    assert 'account rows' in document and 'no write privilege' in document


def postgres_scope(document):
    grants = demo_grants('postgres')
    assert (('SELECT',), 'ALL TABLES IN SCHEMA public') in grants
    assert (('SELECT',), 'datasets') in grants
    # Init SQL grants demo reads; it does not revoke these inherited capabilities.
    assert all(set(privileges) <= {'SELECT', 'USAGE', 'CONNECT'} for privileges, _ in grants)
    assert 'sample' in document and 'tables' in document
    for capability in ('TEMPORARY', 'large objects', 'routines'):
        assert capability in document


@pytest.mark.parametrize('engine', ['mysql', 'postgres'])
def test_readme_demo_scope_matches_init_sql(engine):
    readme = text('README.md', 'DL086_README_SOURCE')
    if engine == 'mysql':
        section = readme.split('### MySQL\n', 1)[1].split('### PostgreSQL\n', 1)[0]
        cell = next(line for line in section.splitlines() if line.startswith('| `demo` |')).split('|')[3]
        mysql_scope(cell)
    else:
        postgres_scope(readme.split('### PostgreSQL\n', 1)[1].split('### SQLite\n', 1)[0])


@pytest.mark.parametrize('engine', ['mysql', 'postgres'])
def test_env_example_demo_scope_matches_init_sql(engine):
    # Only comments participate in checks and potential failure output.
    comments = '\n'.join(line for line in text('.env.example', 'DL086_ENV_EXAMPLE_SOURCE').splitlines() if line.startswith('#'))
    assert 'cannot write anything, anywhere' not in comments
    if engine == 'mysql':
        mysql_scope(comments.split('demo (MySQL):', 1)[1].split('demo (PostgreSQL):', 1)[0])
    else:
        postgres_scope(comments.split('demo (PostgreSQL):', 1)[1].split('admin ', 1)[0])
