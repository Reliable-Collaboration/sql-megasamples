"""Native file/socket/process-environment checks; never retain password values."""
import datetime
import json
import os
from pathlib import Path
import stat
import subprocess

from megasamples import config
from megasamples.credentials import client

ROOT = Path.cwd()
OUT = ROOT / 'build/credential-upgrade'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip().startswith(str(ROOT.parent / 'sql-megasamples-upgrade-env/'))
values = config.passwords()
assert stat.S_IMODE((ROOT / '.env').stat().st_mode) == 0o600
assert stat.S_IMODE(Path(os.environ['DOCKER_HOST'].removeprefix('unix://')).stat().st_mode) == 0o600
records = {}
for engine, user, key, suffix in [('mysql', 'root', 'MYSQL_ROOT_PASSWORD', 'cnf'), ('postgres', 'postgres', 'POSTGRES_PASSWORD', 'pgpass')]:
    container = 'megasamples-' + engine
    inspected = subprocess.run(['docker', 'inspect', container], capture_output=True, text=True, check=True)
    item = json.loads(inspected.stdout)[0]
    assert item['Config']['Labels']['com.docker.compose.project'] == 'megasamples-upgrade'
    environment = subprocess.run(['docker', 'exec', '--user', 'mysql' if engine == 'mysql' else 'postgres', container, 'cat', '/proc/1/environ'], capture_output=True)
    env_mode = subprocess.run(['docker', 'exec', container, 'stat', '-c', '%a', '/proc/1/environ'], capture_output=True, text=True, check=True).stdout.strip()
    assert int(env_mode, 8) & 0o044 == 0, engine + ' process environment is group/world readable'
    if environment.returncode == 0:
        assert not any(value.encode() in environment.stdout for value in values.values()), engine + ' server retained a password in its process environment'
        content_status, cleared = 'Passed', True
    else:
        assert b'Permission denied' in environment.stderr, 'unexpected proc inspection failure'
        content_status, cleared = 'Unsupported', None
    with client(engine, container, user, values[key]) as command:
        path = next(arg.split('=', 1)[1] for arg in command if arg.startswith('--defaults-extra-file=' if engine == 'mysql' else 'PGPASSFILE='))
        directory = path.rsplit('/', 1)[0]
        observed = subprocess.run(['docker', 'exec', container, 'stat', '-c', '%a', directory, path, '/run/megasamples-health.' + suffix], capture_output=True, text=True, check=True)
        assert observed.stdout.split() == ['700', '600', '600']
        flags = ['-N', '-e', 'SELECT 1'] if engine == 'mysql' else ['-d', 'postgres', '-tAc', 'SELECT 1']
        native = subprocess.run([*command, *flags], capture_output=True, text=True)
        assert native.returncode == 0 and native.stdout.strip() == '1'
    removed = subprocess.run(['docker', 'exec', container, 'test', '!', '-e', directory], capture_output=True)
    assert removed.returncode == 0, engine + ' private client directory remained'
    records[engine] = dict(status='Passed', directory_mode='0700', client_file_mode='0600', health_file_mode='0600',
                           server_pid1_environment_has_no_password=cleared, pid1_environment_content_inspection=content_status,
                           pid1_environment_mode=env_mode, public_environment_access='Passed',
                           client_sign_in='Passed', private_directory_removed=True,
                           image_id=item['Image'])
row = dict(status='Passed', read_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), env_file_mode='0600',
           isolated_daemon_socket_mode='0600', engines=records,
           note='Container startup/console metadata remains inspectable by the daemon owner; process sampling checks public environments separately.')
(OUT / 'private-file-evidence.json').write_text(json.dumps(row, indent=2) + '\n')
print('Passed: .env/socket 0600, client files 0600/0700, health files 0600, public proc access denied, client directories removed; MySQL PID1 contents Unsupported (protected proc)', flush=True)
