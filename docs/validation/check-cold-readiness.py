"""Run all configured image checks and the whole repository gate in isolation.

Source the supplied env.sh before running this driver. Each command's unabridged
log stays under build/cold-readiness; no running application stack is changed.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
out = Path('build/cold-readiness')
results = {}
commands = [(f'test-image-{engine}', ['make', 'test-image', f'ENGINE={engine}', 'PY=.venv/bin/python'])
            for engine in ['mysql', 'postgres', 'sqlite']]
commands.append(('repository-gate', ['make', 'check', 'PY=.venv/bin/python']))
for label, args in commands:
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    started = time.monotonic()
    command = ['podman', 'exec', '-e', 'PYTHONPATH=.', '-e', 'PYTHONUNBUFFERED=1',
               'megasamples-upgrade-tools', *args]
    with (out / f'{label}.log').open('w') as log:
        status = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    results[label] = dict(status='Passed' if status == 0 else 'Failed', returncode=status,
                          seconds=time.monotonic()-started, started_at=started_at, command=command)
    (out / 'checks.json').write_text(json.dumps(results, indent=2)+'\n')
    print(label, results[label]['status'], f"{results[label]['seconds']:.2f}s", flush=True)
raise SystemExit(int(any(r['status'] != 'Passed' for r in results.values())))
