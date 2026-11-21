"""DL-079: native account authentication across .env rotation, isolated stack only.

Run in the locked tools container with the supplied isolated env.sh in effect.
Only status, account names and commands without secret values become evidence.
The original/intermediate .env copies remain private and untracked.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from megasamples import config, reset
from megasamples.credentials import client
from megasamples.engines.mysql import base_image
from megasamples.engines.postgres import server as pg

ROOT = Path.cwd()
OUT = ROOT / 'build/strict-read'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://' + str(ROOT.parent / 'sql-megasamples-upgrade-env/podman.sock')
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip().startswith(str(ROOT.parent / 'sql-megasamples-upgrade-env/'))


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def private_copy(name, contents):
    with (OUT / name).open('w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(contents)


# Compare the current private canaries against the baked public defaults, then
# rotate to the other existing canary set from the prerequisite rehearsal.
original = dict(config.PASSWORD_DEFAULTS)
before = config.passwords()
private_copy('rotation-A.env', (ROOT / '.env').read_text())
results = {'read_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'rounds': {}}
clients = {'mysql': 'megasamples-credential-mysql-client', 'postgres': 'megasamples-credential-postgres-client'}
accounts = [('mysql', 'demo', 'DEMO_PASSWORD', False), ('mysql', 'admin', 'ADMIN_PASSWORD', False),
            ('mysql', 'root', 'MYSQL_ROOT_PASSWORD', False), ('mysql', 'root', 'MYSQL_ROOT_PASSWORD', True),
            ('postgres', 'demo', 'DEMO_PASSWORD', False), ('postgres', 'admin', 'ADMIN_PASSWORD', False),
            ('postgres', 'postgres', 'POSTGRES_PASSWORD', False)]


def native(engine, user, password, local=False):
    container = 'megasamples-mysql' if local else clients[engine]
    port = 3306 if local else config.load().ports[engine]
    with client(engine, container, user, password, host='127.0.0.1', port=port) as command:
        if local:
            command = [arg for arg in command if not arg.startswith(('--host=', '--protocol='))]
            command += ['--host=localhost', '--protocol=SOCKET']
        if engine == 'mysql':
            args = [*command, '-N', '--batch', '-e', 'SELECT CURRENT_USER(),1']
        else:
            args = [*command, '-d', 'megasamples', '-tAc', 'SELECT current_user,1']
        return run(args)


def check_round(label, current, previous):
    records = []
    for engine, user, key, local in accounts:
        assert current[key] != previous[key], 'test needs a different password for every account'
        accepted = native(engine, user, current[key], local)
        rejected = native(engine, user, previous[key], local)
        identity = accepted.stdout.strip()
        expected = (user + ('@localhost' if local else '@%') + '\t1'
                    if engine == 'mysql' else user + '|1')
        assert accepted.returncode == 0 and identity == expected, engine + ':' + user + ' new credential or identity failed'
        expected_error = 'Access denied' if engine == 'mysql' else 'password authentication failed'
        assert rejected.returncode != 0 and expected_error in rejected.stderr, engine + ':' + user + ' previous credential was not refused by authentication'
        records.append(dict(engine=engine, account=user, route='container Unix socket' if local else 'published localhost TCP',
                            authenticated_identity=identity, new_password='Passed', previous_password_refused='Passed'))
    # A configured root/postgres password must also reach reset's count helpers.
    for engine in ['mysql', 'postgres']:
        counts = (reset.my_counts if engine == 'mysql' else reset.pg_counts)('megasamples-' + engine, 'pubs')
        assert counts and all(value.isdigit() for value in counts.values()), engine + ' count helper failed'
    results['rounds'][label] = dict(status='Passed', accounts=records, count_helpers='Passed')
    (OUT / 'rotation-results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(label, 'Passed: every new password accepted and previous password refused; count helpers passed', flush=True)


cfg = config.load()
assert cfg.ports['mysql'] == 13306 and cfg.ports['postgres'] == 15432
for engine in ['mysql', 'postgres']:
    record = json.loads(run(['docker', 'inspect', 'megasamples-' + engine]).stdout)[0]
    assert record['State']['Running'], engine + ' is stopped'
    assert record['Config']['Labels']['com.docker.compose.project'] == 'megasamples-upgrade'
    internal = '3306/tcp' if engine == 'mysql' else '5432/tcp'
    bindings = record['HostConfig']['PortBindings'][internal]
    assert bindings == [{'HostIp': '127.0.0.1', 'HostPort': str(cfg.ports[engine])}], engine + ' endpoint drift'

started_clients = []
try:
    for engine, image in [('mysql', base_image.IMAGE), ('postgres', pg.IMAGE)]:
        name = clients[engine]
        assert run(['docker', 'inspect', name]).returncode != 0, 'credential client already exists'
        created = run(['docker', 'run', '--rm', '-d', '--name', name, '--network', 'host', '--memory', '512m',
                       '--label', 'megasamples.transient=true', '--label', 'megasamples.role=credential-check',
                       '--entrypoint', 'sleep', image, 'infinity'])
        assert created.returncode == 0, 'could not start native client'
        started_clients.append(name)
    check_round('A-versus-original', before, original)
    other = OUT / 'rotation-choice'
    other.mkdir(exist_ok=True)
    other.chmod(0o700)
    with (other / '.env').open('w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write((ROOT / 'build/credential-upgrade/rotation-A.env').read_text())
    original_root = config.ROOT
    try:
        config.ROOT = str(other)
        rotated = config.passwords()
    finally:
        config.ROOT = original_root
    assert all(rotated[key] != before[key] for key in before), 'need distinct existing canaries'
    # Single quotes keep dollar signs literal in Compose; escaped apostrophes stay part of the password.
    text = ''.join(key + "='" + value.replace("'", "\\'") + "'\n" for key, value in rotated.items())
    with (ROOT / '.env').open('w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(text)
    private_copy('rotation-B.env', text)
    assert config.passwords() == rotated, 'repository .env parsing differs from intended rotation'
    start = time.monotonic()
    with (OUT / 'rotation-B-recreate.log').open('w') as log:
        rc = subprocess.run(['docker', 'compose', 'up', '-d', '--no-deps', '--force-recreate', 'mysql', 'postgres'],
                            stdout=log, stderr=subprocess.STDOUT).returncode
    assert rc == 0, 'rotation recreate failed'
    for engine in ['mysql', 'postgres']:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            key = 'MYSQL_ROOT_PASSWORD' if engine == 'mysql' else 'POSTGRES_PASSWORD'
            account = 'root' if engine == 'mysql' else 'postgres'
            p = native(engine, account, rotated[key])
            if p.returncode == 0:
                break
            time.sleep(.5)
        else:
            raise AssertionError(engine + ' never accepted the configured rotated password')
    check_round('B-versus-A', rotated, before)
    results['rotation_recreate_seconds'] = time.monotonic() - start
    # Real health commands must succeed and their credential files must be owner-only.
    health = {}
    for engine, extension in [('mysql', 'cnf'), ('postgres', 'pgpass')]:
        container = 'megasamples-' + engine
        path = '/run/megasamples-health.' + extension
        permissions = run(['docker', 'exec', container, 'stat', '-c', '%a', path])
        assert permissions.returncode == 0 and permissions.stdout.strip() == '600'
        record = json.loads(run(['docker', 'inspect', container]).stdout)[0]
        test = record['Config']['Healthcheck']['Test']
        assert test[0] == 'CMD-SHELL'
        probe = run(['docker', 'exec', container, 'sh', '-c', test[1]])
        assert probe.returncode == 0, engine + ' health probe failed'
        wrapper = ROOT / 'engines' / engine / 'entrypoint-wrapper.sh'
        contents = run(['docker', 'exec', container, 'sha256sum', '/usr/local/bin/entrypoint-wrapper.sh'])
        assert contents.stdout.split()[0] == hashlib.sha256(wrapper.read_bytes()).hexdigest()
        health[engine] = dict(status='Passed', credential_file_mode='0600', probe=test,
                              image_id=record['Image'], wrapper_matches_checkout=True)
    results.update(status='Passed', health=health, password_values_recorded=False)
    (OUT / 'rotation-results.json').write_text(json.dumps(results, indent=2) + '\n')
finally:
    for name in started_clients:
        run(['docker', 'rm', '-fv', name])
print('Passed: native rotation, both root host accounts, count helpers and private health probes', flush=True)
