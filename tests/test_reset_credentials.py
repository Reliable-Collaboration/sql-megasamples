"""Credential rotation must reach servers and maintenance clients without argv secrets."""
import subprocess
from contextlib import contextmanager

import pytest
import yaml

from megasamples import compose, config, reset


def test_native_root_verifier_uses_socket_for_localhost(monkeypatch):
    from importlib import import_module
    verifier = import_module("docs.validation.verify-configured-passwords")
    calls = []
    @contextmanager
    def private(*args, **kwargs):
        yield ['docker', 'exec', 'target', 'mysql', '--defaults-extra-file=/private',
               '--host=127.0.0.1', '--protocol=TCP']
    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0,
            '{"stack":{"IPAddress":"10.89.0.2"}}' if 'inspect' in args else 'root@localhost\t1', '')
    monkeypatch.setattr(verifier, 'client', private)
    monkeypatch.setattr(verifier.subprocess, 'run', run)
    verifier.query('mysql', 'target', 'root', 'unit_canary', local_root=True)
    assert '--protocol=SOCKET' in calls[-1]
    assert '--protocol=TCP' not in calls[-1]
    assert '--host=localhost' in calls[-1]


def test_native_root_verifier_rejects_wrong_authenticated_account(monkeypatch):
    from importlib import import_module
    verifier = import_module("docs.validation.verify-configured-passwords")
    monkeypatch.setattr(verifier.config, 'load', lambda: config.Config({'engines': {'mysql': {'datasets': ['pubs']}}}))
    monkeypatch.setattr(verifier, 'query', lambda engine, container, user, password, local:
                        subprocess.CompletedProcess([], 0, user + '@%\t1', ''))
    assert verifier.main([]) == 1


def test_all_password_overrides_reach_the_servers():
    cfg = config.Config({'engines': {'mysql': {'datasets': ['pubs']},
                                      'postgres': {'datasets': ['pubs']}}, 'consoles': []})
    services = yaml.safe_load(compose.render(cfg))['services']
    for engine, superuser in [('mysql', 'MYSQL_ROOT_PASSWORD'), ('postgres', 'POSTGRES_PASSWORD')]:
        env = services[engine]['environment']
        for key, default in [('DEMO_PASSWORD', 'demo'), ('ADMIN_PASSWORD', 'admin'), (superuser, 'root')]:
            assert env[key] == '${' + key + ':-' + default + '}'
        probe = str(services[engine]['healthcheck']['test'])
        assert '-p"' not in probe and 'PGPASSWORD=' not in probe


def test_configuration_reads_all_four_passwords_privately(monkeypatch, tmp_path):
    path = tmp_path / '.env'
    path.write_text("DEMO_PASSWORD='demo quoted # space'\nADMIN_PASSWORD=admin_override\n"
                    'MYSQL_ROOT_PASSWORD=mysql_override\nPOSTGRES_PASSWORD=pg_override\n')
    monkeypatch.setattr(config, 'ROOT', str(tmp_path), raising=False)
    for key in ['DEMO_PASSWORD', 'ADMIN_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'POSTGRES_PASSWORD']:
        monkeypatch.delenv(key, raising=False)
    assert config.passwords() == dict(DEMO_PASSWORD='demo quoted # space', ADMIN_PASSWORD='admin_override',
                                      MYSQL_ROOT_PASSWORD='mysql_override', POSTGRES_PASSWORD='pg_override')


@pytest.mark.parametrize('engine,helper,key', [('mysql', 'my', 'MYSQL_ROOT_PASSWORD'),
                                              ('postgres', 'pg', 'POSTGRES_PASSWORD')])
def test_reset_queries_and_counts_use_configured_private_clients(monkeypatch, engine, helper, key):
    calls = []
    @contextmanager
    def client(kind, container, user, password):
        calls.append((kind, container, user, password))
        yield ['private-client']
    monkeypatch.setattr(reset, 'client', client, raising=False)
    monkeypatch.setattr(config, 'passwords', lambda: {key: 'unit_rotation_canary'}, raising=False)
    def sh(*args, **kw):
        assert args[0] == 'private-client'
        text = 'jobs\n' if 'table' in str(args).lower() else '14\n'
        return subprocess.CompletedProcess(args, 0, text, '')
    monkeypatch.setattr(reset, 'sh', sh)
    counts = getattr(reset, helper + '_counts')('target', 'pubs')
    assert counts == {'jobs': '14'}
    assert calls and all(c == (engine, 'target', 'root' if engine == 'mysql' else 'postgres',
                               'unit_rotation_canary') for c in calls)


@pytest.mark.parametrize('helper', ['my_counts', 'pg_counts'])
def test_failed_count_query_cannot_be_reported_as_empty_success(monkeypatch, helper):
    query = 'my' if helper.startswith('my') else 'pg'
    monkeypatch.setattr(reset, query, lambda *a: subprocess.CompletedProcess(a, 1, '', 'authentication failed'))
    with pytest.raises(SystemExit, match='count|tables'):
        getattr(reset, helper)('target', 'pubs')


@pytest.mark.parametrize('engine', ['mysql', 'postgres'])
@pytest.mark.parametrize('failure', ['none', 'write', 'body'])
def test_private_client_files_are_0600_and_removed_even_on_failure(monkeypatch, engine, failure):
    from megasamples import credentials
    calls = []
    canary = 'unit_canary:with\\quote\" #\t'
    def run(args, **kw):
        assert all(canary not in arg for arg in args)
        assert canary not in str(kw.get('env', {}))
        calls.append((args, kw))
        if 'inspect' in args:
            return subprocess.CompletedProcess(args, 0, '{"stack": {"IPAddress": "10.89.0.7"}}', '')
        if 'mktemp' in args:
            return subprocess.CompletedProcess(args, 0, '/tmp/megasamples-auth.test\n', '')
        if kw.get('input') and failure == 'write':
            return subprocess.CompletedProcess(args, 1, '', 'write failed')
        return subprocess.CompletedProcess(args, 0, '', '')
    monkeypatch.setattr(credentials.subprocess, 'run', run)
    def use():
        with credentials.client(engine, 'target', 'root' if engine == 'mysql' else 'postgres', canary) as command:
            assert canary not in str(command)
            assert '--defaults-extra-file=/tmp/megasamples-auth.test/client.cnf' in command if engine == 'mysql' else 'PGPASSFILE=/tmp/megasamples-auth.test/pgpass' in command
            assert '-p' not in command and not any('PGPASSWORD' in arg for arg in command)
            if failure == 'body':
                raise RuntimeError('restore failed')
    if failure != 'none':
        with pytest.raises(RuntimeError):
            use()
    else:
        use()
    written = [kw['input'] for _, kw in calls if kw.get('input')]
    assert len(written) == 1
    assert 'umask 077' in str(calls)
    assert calls[-1][0] == ['docker', 'exec', 'target', 'rm', '-rf', '/tmp/megasamples-auth.test']


def test_count_failure_after_table_listing_is_not_silent(monkeypatch):
    calls = iter([subprocess.CompletedProcess([], 0, 'jobs\n', ''),
                  subprocess.CompletedProcess([], 1, '', 'query failed')])
    monkeypatch.setattr(reset, 'my', lambda *a: next(calls))
    with pytest.raises(SystemExit, match='count'):
        reset.my_counts('target', 'pubs')


@pytest.mark.parametrize('engine,suffix', [('mysql', 'cnf'), ('postgres', 'pgpass')])
def test_health_probes_have_private_files_generated_at_startup(engine, suffix):
    from pathlib import Path
    script = (Path(config.ROOT) / 'engines' / engine / 'entrypoint-wrapper.sh').read_text()
    assert '/run/megasamples-health.' + suffix in script
    assert 'umask 077' in script
    assert 'unset ' in script


def test_mysql_adapter_query_never_puts_rotated_password_in_argv(monkeypatch):
    from megasamples.engines.mysql import server
    canary = 'unit_adapter_password_canary'
    monkeypatch.setattr(server, 'PW', canary)
    @contextmanager
    def protected(*args, **kwargs):
        yield ['private-client']
    monkeypatch.setattr(server, 'client', protected, raising=False)
    def run(args, **kwargs):
        assert canary not in str(args)
        assert args[0] == 'private-client'
        return subprocess.CompletedProcess(args, 0, '1\n', '')
    monkeypatch.setattr(server, 'run', run)
    assert server.sql('SELECT 1') == '1\n'


@pytest.mark.parametrize('engine', ['mysql', 'postgres'])
def test_image_account_checks_use_private_native_clients(monkeypatch, engine):
    from importlib import import_module
    module = import_module('megasamples.engines.' + engine + '.image_test')
    canary = 'unit_image_password_canary'
    @contextmanager
    def protected(*args, **kwargs):
        yield ['private-client']
    monkeypatch.setattr(module, 'client', protected, raising=False)
    def sh(*args, **kw):
        assert canary not in str(args)
        assert args[0] == 'private-client'
        return subprocess.CompletedProcess(args, 0, '1\n', '')
    monkeypatch.setattr(module, 'sh', sh)
    assert module.q('SELECT 1', pw=canary).stdout == '1\n'


def test_postgres_maintenance_authenticates_on_non_loopback_tcp(monkeypatch):
    from megasamples import credentials
    def run(args, **kw):
        if 'inspect' in args:
            return subprocess.CompletedProcess(args, 0, '{"stack": {"IPAddress": "10.89.0.7"}}', '')
        return subprocess.CompletedProcess(args, 0, '/tmp/megasamples-auth.test\n' if 'mktemp' in args else '', '')
    monkeypatch.setattr(credentials.subprocess, 'run', run)
    with credentials.client('postgres', 'target', 'postgres', 'unit_private_password') as command:
        assert command[command.index('-h') + 1] == '10.89.0.7'


def test_private_session_reuses_files_but_never_a_different_password(monkeypatch):
    from megasamples import credentials
    calls = []
    def run(args, **kw):
        calls.append((args, kw))
        count = sum('mktemp' in a for a, _ in calls)
        return subprocess.CompletedProcess(args, 0, '/tmp/megasamples-auth.' + str(count) + '\n' if 'mktemp' in args else '', '')
    monkeypatch.setattr(credentials.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='probe failed'):
        with credentials.session():
            with credentials.client('mysql', 'target', 'root', 'unit_first') as first:
                first.append('local caller flag')
            with credentials.client('mysql', 'target', 'root', 'unit_first') as again:
                assert 'local caller flag' not in again
            with credentials.client('mysql', 'target', 'root', 'unit_second') as second:
                assert second != again
            assert sum('mktemp' in a for a, _ in calls) == 2
            assert not any('rm' in a for a, _ in calls)
            raise RuntimeError('probe failed')
    assert sum('rm' in a for a, _ in calls) == 2


def test_connection_help_prompts_instead_of_putting_passwords_in_commands():
    import re
    from megasamples import console_page
    from megasamples.engines import get
    cfg = config.Config({'engines': {'mysql': {'datasets': ['pubs']}, 'postgres': {'datasets': ['pubs']}}})
    html = console_page.connect_cards(cfg, {'mysql': {'pubs': {}}, 'postgres': {'pubs': {}}}, 'unit_demo_canary', 'unit_admin_canary')
    clients = re.findall(r'<th>client</th><td>(.*?)</td>', html)
    assert len(clients) == 2
    assert all('unit_demo_canary' not in command and 'PGPASSWORD=' not in command for command in clients)
    assert 'root / root' not in html and 'postgres / root' not in html
    for engine in ['mysql', 'postgres']:
        hint = get(engine).connection_hint(cfg)
        assert '-pdemo' not in hint and 'PGPASSWORD=' not in hint


def test_invalid_compose_configuration_aborts_before_reset(monkeypatch, tmp_path):
    monkeypatch.setattr(reset.tempfile, "tempdir", str(tmp_path))
    cfg = config.Config({'engines': {'mysql': {'datasets': ['pubs']}}})
    monkeypatch.setattr(reset.stack, 'load', lambda: cfg)
    monkeypatch.setattr(reset.compose, 'main', lambda *a: 2)
    monkeypatch.setitem(reset.RESET_DATABASES, 'mysql', lambda *a: pytest.fail('reset after failed configuration'))
    assert reset.main(['mysql:pubs']) == 2


def test_landing_help_escapes_rotated_password_once_and_encodes_its_url(monkeypatch):
    import html, re, urllib.parse
    from megasamples import console_page
    password = 'unit<&"\'@: demo\\'
    monkeypatch.setattr(console_page, 'passwords', lambda: (password, 'unit_admin'))
    cfg = config.Config({'engines': {'mysql': {'datasets': ['pubs']}}, 'consoles': []})
    page, _ = console_page.render(cfg, {'mysql': {}})
    accounts = re.search(r'<th>accounts</th><td>(.*?)</td>', page)[1]
    url = html.unescape(re.search(r'<th>URL</th><td><code>(.*?)</code></td>', page)[1])
    assert password in html.unescape(accounts)
    assert urllib.parse.quote(password, safe='') in url
