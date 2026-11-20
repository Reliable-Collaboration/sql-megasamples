"""Account documentation checked against init grants, without reading credentials."""
import os
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).parents[1]


def role_grants(engine, role):
    grants = []
    for path in sorted((ROOT/'engines'/engine/'init').glob('*.sql')):
        # Read SQL for grant extraction only; never include its source in a failure.
        sql = re.sub(r'--[^\n]*', '', path.read_text())
        for privileges, scope, roles in re.findall(r'GRANT\s+(.+?)\s+ON\s+(.+?)\s+TO\s+([^;]+);', sql, re.I):
            if re.search(r"(?:^|[,\s])'?"+re.escape(role)+r"'?(?:@|[,\s]|$)", roles, re.I):
                grants.append((tuple(p.strip().upper() for p in privileges.split(',')), scope.strip()))
    return grants


def demo_grants(engine):
    return role_grants(engine, 'demo')


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
    assert (('SELECT',), 'TABLES') in grants
    grant_sql = (ROOT/'engines/postgres/init/20-grants.sql').read_text()
    assert re.search(r'ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public GRANT SELECT ON TABLES TO demo;', grant_sql)
    assert 'tables `admin` later creates' in document and 'public' in document
    assert 'sample database' in document
    # Init SQL grants demo reads; it does not revoke these inherited capabilities.
    assert all(set(privileges) <= {'SELECT', 'USAGE', 'CONNECT'} for privileges, _ in grants)
    assert re.search(r'\breads (?:persistent )?sample tables\b', document)
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


def admin_scope(document, engine):
    grants = role_grants(engine, 'admin')
    if engine == 'mysql':
        assert grants == [(('ALL PRIVILEGES',), '*.*')], 'Review changed MySQL admin grants'
        sql = (ROOT/'engines/mysql/init/00-users.sql').read_text()
        assert re.search(r"GRANT ALL PRIVILEGES ON \*\.\* TO 'admin'@'%' WITH GRANT OPTION;", sql)
        assert 'ALL PRIVILEGES WITH GRANT OPTION' in document and '`*.*`' in document
    else:
        sql = (ROOT/'engines/postgres/init/00-users.sql').read_text()
        options = re.search(r'CREATE ROLE admin WITH ([^;]+)', sql).group(1)
        assert re.search(r'\bCREATEDB\b', options) and re.search(r'\bCREATEROLE\b', options)
        assert not re.search(r'\bSUPERUSER\b', options)
        assert (('ALL',), 'datasets') in grants
        for source in (ROOT/'engines/postgres/init').glob('*.sql'):
            grant_sql = re.sub(r'--[^\n]*', '', source.read_text())
            assert not re.search(r'GRANT[^;]+TO\s+(?:[^;]*,\s*)?(?:admin|"admin")(?:\s*,[^;]*?)?\s+WITH\s+GRANT\s+OPTION\s*;', grant_sql, re.I)
        dockerfile = (ROOT/'engines/postgres/Dockerfile').read_text()
        assert 'OWNER admin TEMPLATE template0' in dockerfile
        for clause in ('CREATEDB', 'CREATEROLE', 'owns the sample databases',
                       'registry', 'without grant option', 'not a superuser'):
            assert clause in document


@pytest.mark.parametrize('engine', ['mysql', 'postgres'])
def test_readme_admin_scope_matches_init_sql(engine):
    readme = text('README.md', 'DL086_README_SOURCE')
    section = readme.split('## Putting the data back\n', 1)[1].split('```sh', 1)[0]
    marker = 'MySQL `admin`' if engine == 'mysql' else 'PostgreSQL `admin`'
    assert marker in section
    admin_scope(section.split(marker, 1)[1].split('\n\n', 1)[0], engine)


@pytest.mark.parametrize('engine', ['mysql', 'postgres'])
def test_env_example_admin_scope_matches_init_sql(engine):
    comments = '\n'.join(line for line in text('.env.example', 'DL086_ENV_EXAMPLE_SOURCE').splitlines() if line.startswith('#'))
    marker = 'admin (MySQL):' if engine == 'mysql' else 'admin (PostgreSQL):'
    assert marker in comments
    admin_scope(comments.split(marker, 1)[1].split('#   admin ', 1)[0], engine)
