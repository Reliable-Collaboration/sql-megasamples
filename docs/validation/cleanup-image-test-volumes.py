"""Remove only anonymous volumes captured from this run's image-test containers."""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import time

OUT = Path('build/credential-upgrade')
assert Path.cwd() == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['podman', 'info', '--format', '{{.Store.GraphRoot}}'], text=True).strip() == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/graph'
while True:
    rows = json.loads((OUT / 'validation-steps.json').read_text())
    assert not any(row['status'] == 'Failed' for row in rows.values()), 'validation failed before volume cleanup'
    if all(rows.get('test-image-' + engine, {}).get('status') == 'Passed' for engine in ['mysql', 'postgres', 'sqlite']):
        break
    time.sleep(3)
(OUT / 'volume-observer.stop').touch()
time.sleep(2)
observations = json.loads((OUT / 'image-test-volumes.json').read_text())
assert observations['status'] == 'Passed'
start = datetime.datetime.fromisoformat(observations['started_at'])
volumes = set()
for row in observations['containers'].values():
    assert row['name'] in ['megasamples-test-' + e + s for e in ['mysql', 'postgres', 'sqlite'] for s in ['', '2']]
    assert datetime.datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')) >= start
    assert subprocess.run(['podman', 'container', 'exists', row['name']]).returncode == 1, 'an observed test container still exists'
    for name in row['anonymous_volumes']:
        assert re.fullmatch(r'[0-9a-f]{64}', name)
        volumes.add(name)
removed, already_removed = [], []
for name in sorted(volumes):
    exists = subprocess.run(['podman', 'volume', 'exists', name]).returncode
    if exists == 1:
        already_removed.append(name)
        continue
    assert exists == 0, 'could not determine volume existence'
    users = subprocess.check_output(['podman', 'ps', '-a', '--filter', 'volume=' + name, '--format', '{{.ID}}'], text=True).strip()
    assert not users, 'observed test volume is still attached'
    subprocess.run(['podman', 'volume', 'rm', name], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    removed.append(name)
result = dict(status='Passed', captured_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              removed=removed, already_removed_by_test=already_removed,
              source='image-test-volumes.json', only_recorded_new_test_volumes=True, global_prune=False)
(OUT / 'image-test-volume-cleanup.json').write_text(json.dumps(result, indent=2) + '\n')
print('Passed: removed', len(removed), 'recorded unattached test volumes;', len(already_removed), 'already removed by their tests', flush=True)
