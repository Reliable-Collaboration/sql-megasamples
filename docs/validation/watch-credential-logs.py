"""Scan isolated application/pristine logs; retain outcomes without password values."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

OUT = Path('build/credential-upgrade')
assert Path.cwd() == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['podman', 'info', '--format', '{{.Store.GraphRoot}}'], text=True).strip() == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/graph'
base = {'megasamples-' + name for name in ['mysql', 'postgres', 'sqlite', 'landing', 'adminer', 'phpmyadmin', 'dbgate', 'cloudbeaver']}
results = dict(status='Passed', started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), scans=0, containers={})
while True:
    values = set()
    for path in [Path('.env'), OUT / 'original.env', *OUT.glob('rotation-*.env')]:
        for line in path.read_text().splitlines():
            if '=' not in line or line.startswith('#'):
                continue
            value = line.split('=', 1)[1]
            if value.startswith("'") and value.endswith("'"):
                value = value[1:-1].replace("\\'", "'")
            if len(value) >= 12:
                values.add(value.encode())
    listed = subprocess.run(['podman', 'ps', '-a', '--format', '{{.Names}}'], capture_output=True, text=True, check=True)
    names = [name for name in listed.stdout.splitlines() if name in base or name.startswith('megasamples-reset-')]
    for name in names:
        inspected = subprocess.run(['podman', 'inspect', name], capture_output=True, text=True)
        if inspected.returncode:
            continue
        item = json.loads(inspected.stdout)[0]
        labels = item['Config'].get('Labels') or {}
        assert labels.get('com.docker.compose.project') == 'megasamples-upgrade' if name in base else labels.get('megasamples.role') == 'reset'
        logged = subprocess.run(['podman', 'logs', name], capture_output=True)
        if logged.returncode:
            continue  # removed between inspect and logs; another sample may have captured it
        raw = logged.stdout + logged.stderr
        exposed = any(value in raw for value in values)
        if exposed:
            results['status'] = 'Failed'
        results['containers'][item['Id']] = dict(name=name, status='Failed' if exposed else 'Passed', password_found=exposed,
                                                log_bytes=len(raw), log_sha256=hashlib.sha256(raw).hexdigest(),
                                                read_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    results['scans'] += 1
    results['captured_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (OUT / 'container-log-canaries.json').write_text(json.dumps(results, indent=2) + '\n')
    if (OUT / 'log-canary.stop').exists():
        break
    time.sleep(3)
print('Container log canaries:', results['status'], results['scans'], 'scans', flush=True)
