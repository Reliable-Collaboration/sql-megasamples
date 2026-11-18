"""Read-only comparison with the owner-supplied live baseline; no service actions."""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess

assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
out = Path(os.environ.get('MEGASAMPLES_VALIDATION_OUT', 'build/lts-audit'))
expected = {'megasamples-upgrade-tools', 'megasamples-upgrade-browser',
            'megasamples-landing', 'megasamples-phpmyadmin', 'megasamples-adminer',
            'megasamples-build-mysql', 'megasamples-build-postgres',
            'megasamples-sqlite', 'megasamples-mysql', 'megasamples-postgres',
            'megasamples-dbgate', 'megasamples-cloudbeaver'}


def command(*args, env=None):
    return subprocess.run(['podman', *args], env=env, capture_output=True, text=True, check=True).stdout


listing = command('ps', '-a', '--format', '{{.ID}} {{.Names}} {{.Status}}')
names = {line.split()[1] for line in listing.splitlines()}
assert names == expected, f'Unexpected isolated container set: {names ^ expected}'
graph_root = command('info', '--format', '{{.Store.GraphRoot}}').strip()
assert graph_root == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/graph'
(out / 'isolated-ps.txt').write_text(listing)

# The only default-store operation is the owner-requested read-only inspect.
live_env = {k: v for k, v in os.environ.items() if k not in {
    'CONTAINERS_STORAGE_CONF', 'CONTAINERS_CONF', 'CONTAINERS_CONF_OVERRIDE',
    'DOCKER_HOST', 'COMPOSE_PROJECT_NAME', 'CONTAINER_HOST', 'CONTAINER_CONNECTION'}}
live_names = ['megasamples-postgres', 'megasamples-mysql', 'megasamples-sqlite']
default_listing = command('ps', '-a', '--format', '{{.ID}} {{.Names}} {{.Status}}', env=live_env)
observed = json.loads(command('inspect', *live_names, env=live_env))
baseline = Path('/home/rcc-vstudio/working/RCC.DataIntent/.local/megasamples-upgrade/live-before.txt').read_text()


def stamp(value):
    match = re.fullmatch(r'(.*?)(\.\d+)(Z|[+-]\d\d:\d\d)', value)
    assert match, 'Unexpected timestamp format'
    seconds = datetime.datetime.fromisoformat(match[1]+match[3].replace('Z', '+00:00'))
    return seconds.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+match[2]+'Z'


def row(name, cid, image, start, status):
    return dict(name=name.lstrip('/'), id=cid, image=image.removeprefix('sha256:'),
                started_at=stamp(start), status=status)


before = []
for line in baseline.strip().splitlines():
    match = re.fullmatch(r'/?(\S+) id=(\S+) image=(\S+) started=(\S+) status=(\S+)', line)
    assert match, 'Unexpected baseline format'
    before.append(row(*match.groups()))
after = [row(r['Name'], r['Id'], r['Image'], r['State']['StartedAt'], r['State']['Status']) for r in observed]
assert sorted(before, key=lambda r: r['name']) == sorted(after, key=lambda r: r['name']), 'Live baseline mismatch'
application = json.loads(command('inspect', *['megasamples-'+name for name in ['mysql','postgres','sqlite','landing','phpmyadmin','adminer','dbgate','cloudbeaver']]))
assert all(row['State']['Running'] for row in application), 'an isolated application service is stopped'
assert all(row['Config']['Labels']['com.docker.compose.project'] == 'megasamples-upgrade' for row in application)
result = dict(status='Passed', read_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              isolated_ps=listing, graph_root=graph_root, live=after, default_ps=default_listing,
              all_eight_isolated_application_services_running=True,
              comparison='IDs, image IDs, full nanosecond start times and running states match live-before.txt',
              default_store_operations=[['podman', 'ps', '-a', '--format', '{{.ID}} {{.Names}} {{.Status}}'],
                                        ['podman', 'inspect', *live_names]], proxy_service_actions='None')
(out / 'isolation.json').write_text(json.dumps(result, indent=2)+'\n')
print(listing, end='')
print('Passed: isolated store contains only the twelve inherited project containers; all three live containers match the supplied baseline exactly.')
