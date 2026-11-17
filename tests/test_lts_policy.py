"""DL-074: every selected MySQL path must stay on the owner's 9.7 LTS line."""
from pathlib import Path
import re
import yaml
from megasamples.engines import get
from megasamples.engines.mysql import server

ROOT = Path(__file__).resolve().parents[1]


def test_mysql_server_is_the_reviewed_lts_patch():
    assert get('mysql').version == '9.7.4'
    assert re.fullmatch(r'docker.io/library/mysql:9\.7\.4@sha256:[0-9a-f]{64}', server.IMAGE)


def test_loader_cli_and_c_library_match_server_lts():
    text = (ROOT / 'engines/mysql/loader.Dockerfile').read_text()
    assert 'mysql:9.7.4@sha256:' in text
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
