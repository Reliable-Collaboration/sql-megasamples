"""DL-074: every selected MySQL path must stay on the owner's 9.7 LTS line."""
from pathlib import Path
import re
import yaml
from megasamples.engines import get
from megasamples.engines.mysql import server

ROOT = Path(__file__).resolve().parents[1]


def test_mysql_server_is_the_reviewed_lts_patch():
    assert get('mysql').version == '9.7.4'
    assert server.IMAGE == 'sql-megasamples-mysql-base:9.7.4-shell-9.7.1'
    text = (ROOT / 'engines/mysql/base.Dockerfile').read_text()
    assert 'container-registry.oracle.com/mysql/community-server:9.7.4@sha256:' in text
    assert 'mysql:9.7.4@sha256:' in text
    assert '9.7.1' in text
    assert 'VOLUME ["/var/lib/mysql"]' in text


def test_loader_cli_and_c_library_match_server_lts():
    text = (ROOT / 'engines/mysql/loader.Dockerfile').read_text()
    assert 'community-server:9.7.4@sha256:' in text
    assert 'libmysqlclient' in text
    assert 'mariadb-connector-c-' not in text
    assert 'mysql_config --version' in text
    assert 'ldd /usr/local/bin/sysbench' in text


def test_configured_jdbc_uses_latest_available_97_release():
    text = (ROOT / 'consoles/cloudbeaver/Dockerfile').read_text()
    assert '/mysql-connector-j/9.7.0/mysql-connector-j-9.7.0.jar' in text
    assert 'sha256sum -c' in text


def test_dbgate_uses_newest_compatible_node_lts():
    text = (ROOT / 'consoles/dbgate/Dockerfile').read_text()
    assert 'node:24.22.3' in text
    assert 'COPY --from=node' in text
    assert 'npm rebuild' in text  # native modules must match the runtime ABI


def test_locks_agree_with_lts_targets():
    images = yaml.safe_load((ROOT / 'engines/images.lock.yaml').read_text())
    clients = yaml.safe_load((ROOT / 'clients.lock.yaml').read_text())
    assert images['images']['mysql']['version'] == '9.7.4'
    assert clients['native_clients']['mysql']['version'] == '9.7.4'
    assert clients['drivers']['cloudbeaver-mysql-connector-j']['version'] == '9.7.0'


def test_build_server_explicitly_allows_only_loopback_root(monkeypatch, tmp_path):
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(server, 'STAGE', str(tmp_path))
    monkeypatch.setattr(server, 'container_state', lambda: None)
    monkeypatch.setattr(server.base_image, 'build', lambda: 0)
    monkeypatch.setattr(server, 'ready', lambda: True)
    monkeypatch.setattr(server, 'run', lambda args, **kw: calls.append(args) or SimpleNamespace(returncode=0))
    server.start()
    assert 'MYSQL_ROOT_HOST=127.0.0.1' in calls[0]


def test_start_refuses_to_reuse_a_different_build_server_image(monkeypatch):
    from types import SimpleNamespace
    import pytest
    calls = []
    monkeypatch.setattr(server, 'container_state', lambda: 'running')

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=('target-image' if args[1:3] == ['image', 'inspect'] else 'innovation-image')+'\n')

    monkeypatch.setattr(server, 'run', run)
    with pytest.raises(SystemExit, match='fresh'):
        server.start()
    assert all(args[1] in ['inspect', 'image'] for args in calls)
