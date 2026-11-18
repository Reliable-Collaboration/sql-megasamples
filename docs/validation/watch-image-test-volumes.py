"""Record only this run's image-test volume IDs for exact-name cleanup afterwards."""
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
names = ['megasamples-test-' + e + suffix for e in ['mysql', 'postgres', 'sqlite'] for suffix in ['', '2']]
start = datetime.datetime.now(datetime.timezone.utc)
for name in names:
    assert subprocess.run(['podman', 'container', 'exists', name]).returncode != 0, 'an image-test container predates this observer'
rows = {}
while True:
    for name in names:
        p = subprocess.run(['podman', 'inspect', name], capture_output=True, text=True)
        if p.returncode:
            continue
        item = json.loads(p.stdout)[0]
        assert item['Config']['Labels'].get('megasamples.role') == 'test'
        created = datetime.datetime.fromisoformat(item['Created'].replace('Z', '+00:00'))
        assert created >= start, 'test container predates this task observer'
        volumes = [m['Name'] for m in item['Mounts'] if m.get('Type') == 'volume' and re.fullmatch(r'[0-9a-f]{64}', m.get('Name', ''))]
        rows[item['Id']] = dict(name=name, created_at=item['Created'], image=item['Image'], anonymous_volumes=volumes)
    (OUT / 'image-test-volumes.json').write_text(json.dumps(dict(status='Passed', started_at=start.isoformat(), containers=rows), indent=2) + '\n')
    if (OUT / 'volume-observer.stop').exists():
        break
    time.sleep(1)
print('Image-test volume observations:', len(rows), 'containers', flush=True)
