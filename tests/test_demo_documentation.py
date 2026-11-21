"""Account documentation checked against init grants, without reading credentials."""
import os
from pathlib import Path
import re

import pytest

from megasamples.mysql_templates import demo_read_grants

ROOT = Path(__file__).parents[1]


def role_grants(engine, role):
    grants = []
    for path in sorted((ROOT/'engines'/engine/'init').glob('*.sql')):
        # Read SQL for grant extraction only; never include its source in a failure.
        sql = re.sub(r'--[^\n]*', '', path.read_text())
        for privileges, scope, roles in re.findall(r'^[ \t]*GRANT[ \t]+(.+?)\s+ON\s+(.+?)\s+TO\s+([^;]+);', sql, re.I | re.M):
            if re.search(r"(?:^|[,\s])'?"+re.escape(role)+r"'?(?:@|[,\s]|$)", roles, re.I):
                grants.append((tuple(p.strip().upper() for p in privileges.split(',')), scope.strip()))
    return grants


def demo_grants(engine):
    return role_grants(engine, 'demo')


def text(name, variable):
    return Path(os.environ.get(variable, ROOT/name)).read_text()


def mysql_scope(document):
    assert demo_grants('mysql') == [], 'Review additional MySQL bootstrap grants'
    grants = set(demo_read_grants(['working_example'], [('external', True), ('private', False)]))
    assert grants == {
        ('SELECT, SHOW VIEW', r'`working\_example`.*'),
        ('SELECT, SHOW VIEW', r'`external\_%`.*'),
        ('SELECT', 'megasamples.datasets'),
        ('SELECT', 'megasamples.copy_service'),
    }, 'Review changed MySQL demo grants'
    assert all(term in document for term in ('working schemas', 'explicitly enabled foreign namespaces',
                                              'registry tables', 'no write privilege'))
    assert 'every database' not in document and 'system schemas included' not in document


def postgres_scope(document):
    users = (ROOT/'engines/postgres/init/00-users.sql').read_text()
    assert 'GRANT megasamples_read TO megasamples_working_read WITH INHERIT TRUE' in users
    assert 'GRANT megasamples_working_read TO demo WITH INHERIT TRUE' in users
    grants = role_grants('postgres', 'megasamples_read')
    assert (('SELECT',), 'ALL TABLES IN SCHEMA public') in grants
    assert (('SELECT',), 'datasets') in role_grants('postgres', 'PUBLIC')
    grant_sql = (ROOT/'engines/postgres/init/20-grants.sql').read_text()
    assert re.search(r'ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public GRANT SELECT ON TABLES TO megasamples_read;', grant_sql)
    assert 'tables `admin` later creates' in document and 'public' in document
    assert 'sample database' in document
    # An allow-list: any privilege beyond reading (TRUNCATE, ALL, ...) fails.
    assert all(set(privileges) <= {'SELECT', 'USAGE', 'CONNECT'} for privileges, _ in grants), grants
    assert re.search(r'\breads (?:persistent )?sample tables\b', document)
    for capability in ('TEMPORARY', 'large objects', 'routines'):
        assert capability in document
    assert 'cannot create large objects' in document and 'allowlisted routines' in document
    assert 'no `TEMPORARY` privilege' in document


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


def test_strict_read_guide_describes_the_current_demo_grants():
    """Sol round 7, 6: docs/strict-read-account.md states what the image grants today."""
    guide = (ROOT / 'docs/strict-read-account.md').read_text()
    assert 'gives `demo` exactly `SELECT, SHOW VIEW ON *.*`' not in guide
    assert all(term in guide for term in ('working schemas', 'explicitly enabled foreign namespaces',
                                          '`megasamples.datasets`', '`megasamples.copy_service`'))
    assert '`pg_catalog, pg_temp`' in guide and 'installed in `pg_catalog`' in guide
    assert '`megasamples_policy_loaded()`' in guide and 'STRICT_READ_OWNER' in guide


def test_strict_read_guide_states_the_grants_the_generator_makes():
    """Sol round 8, P3-3: the guide's MySQL privileges and scopes are the grant generator's, and its
    PostgreSQL report names every role that can call it (the health test's demo and postgres)."""
    guide = (ROOT / 'docs/strict-read-account.md').read_text()
    grants = demo_read_grants(['working'], [('foreign', True), ('closed', False)])
    schemas = {privileges for privileges, scope in grants if scope.endswith('.*')}
    tables = [scope for privileges, scope in grants if not scope.endswith('.*')]
    assert len(schemas) == 1 and {privileges for privileges, scope in grants if scope in tables} == {'SELECT'}
    assert ('gives `demo` exactly `' + schemas.pop() + '` on the working schemas and on explicitly enabled '
            'foreign namespaces') in guide
    assert '`SELECT` on the registry tables ' + ' and '.join(f'`{t}`' for t in tables) + ', and `USAGE`' in guide
    assert not any('closed' in scope for _, scope in grants)
    # Sol round 9, 5: the scope's escaping as well. The generator's exact patterns (pinned in
    # mysql_scope) escape each underscore, so a working schema matches only itself and a foreign
    # namespace only its own prefix; the guide must say so.
    assert {scope for _, scope in demo_read_grants(['working_example'], [('external', True)])
            if scope.endswith('.*')} == {r'`working\_example`.*', r'`external\_%`.*'}
    assert "(each pattern's underscores escaped)" in guide and 'unescaped' not in guide
    # The report: granted to demo directly, and executable otherwise only by the superuser.
    assert 'granted to `demo` directly' in guide
    assert '`admin` and every other role except the superuser `postgres` are refused it' in guide
