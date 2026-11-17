"""Client pins must agree with the reviewed release inventory and reproducible lock."""
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = {'pyyaml': '6.0.3', 'pymysql': '1.2.4', 'duckdb': '2.0.0',
            'lxml': '6.1.3', 'sqlglot': '30.33.0', 'py7zr': '1.1.4',
            'backports-zstd': '1.8.0', 'pytest': '9.2.0', 'psycopg': '3.3.9'}


@pytest.mark.parametrize('name,version', RELEASES.items())
def test_direct_python_client_pin_and_lock(name, version):
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    requirements = project['project']['dependencies'] + project['dependency-groups']['dev']
    normalized = [r.lower().replace('_', '-').replace('.', '-') for r in requirements]
    assert any(re.match(re.escape(name) + r'(?:\[(?:rsa|binary)\])?==' + re.escape(version).replace(r'\.', '-') + r'(?:;|$)', r)
               for r in normalized), f'{name} needs an exact reviewed release in pyproject.toml'
    packages = tomllib.loads((ROOT / 'uv.lock').read_text())['package']
    assert next(p['version'] for p in packages if p['name'] == name) == version


def test_loader_uses_oracle_client_and_pinned_connector():
    text = (ROOT / 'engines/mysql/loader.Dockerfile').read_text()
    assert 'default-mysql-client' not in text
    assert 'mysql:9.7.4@sha256:' in text
    assert 'libmysqlclient24_9.7.4' in text
    assert 'sha256sum -c' in text
    assert 'sysbench=1.0.20+ds-7' not in text
    assert 'sysbench_1.0.20+ds-7.debian.tar.xz' in text


def test_console_driver_pins_are_built_and_selected():
    from megasamples import compose, config
    from megasamples.consoles import get
    cfg = config.Config({'engines': {e: {'datasets': ['pubs']} for e in ['mysql', 'postgres', 'sqlite']},
                         'consoles': ['cloudbeaver', 'dbgate', 'adminer']})
    for name,versions in [('cloudbeaver', ['9.7.0', '3.54.1.0']), ('dbgate', ['13.2.0']), ('adminer', ['18.7'])]:
        text = (ROOT / f'consoles/{name}/Dockerfile').read_text()
        assert get(name).image in text
        assert all(version in text for version in versions)
        service = __import__('yaml').safe_load(compose.render(cfg))['services'][name]
        assert service['build'] == {'context': f'consoles/{name}', 'dockerfile': 'Dockerfile'}
        assert service['image'] != get(name).image


def test_console_locks_are_in_the_build_context():
    patterns = Path('.dockerignore').read_text().splitlines()
    assert '!consoles/cloudbeaver/Dockerfile' in patterns
    assert '!consoles/dbgate/Dockerfile' in patterns
    assert '!consoles/dbgate/driver/' in patterns


def test_loader_build_does_not_send_baked_engine_data():
    makefile = (ROOT / 'Makefile').read_text()
    recipe = makefile.split('loader-image:\n', 1)[1].split('\n\n', 1)[0]
    assert '-f engines/mysql/loader.Dockerfile -t sql-megasamples-loader:dev engines/mysql' in recipe


def test_postgres_probe_does_not_bundle_an_older_libpq():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert 'psycopg==3.3.9' in project['dependency-groups']['dev']
    packages = tomllib.loads((ROOT / 'uv.lock').read_text())['package']
    assert all(p['name'] != 'psycopg-binary' for p in packages)
