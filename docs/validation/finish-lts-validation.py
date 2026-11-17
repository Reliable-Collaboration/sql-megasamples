"""Run the isolated DL-074 gates after the successful packaging driver.

Commands stop at their first failure; the three final read-only runtime matrices
run concurrently against different engines. Logs and timed results stay private.
"""
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path.cwd()
OUT = ROOT / 'build/lts-audit'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://' + str(ROOT.parent / 'sql-megasamples-upgrade-env/podman.sock')
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['podman', 'info', '--format', '{{.Store.GraphRoot}}'], text=True).strip() == str(ROOT.parent / 'sql-megasamples-upgrade-env/graph')

while True:
    steps = json.loads((OUT/'build-steps.json').read_text()) if (OUT/'build-steps.json').exists() else {}
    assert not any(row.get('status') == 'Failed' for row in steps.values()), 'Packaging failed; inspect its retained logs'
    if steps.get('start-lts-stack', {}).get('status') == 'Passed':
        break
    time.sleep(5)

results = {}


def run(label, args, native=False):
    command = args if native else ['podman', 'exec', '-e', 'CONTAINERS_STORAGE_CONF', '-e', 'CONTAINERS_CONF',
                                  '-e', 'DOCKER_HOST', '-e', 'COMPOSE_PROJECT_NAME', '-e', 'PYTHONPATH=.',
                                  '-e', 'PYTHONUNBUFFERED=1', '-e', 'MEGASAMPLES_VALIDATION_OUT=build/lts-audit',
                                  'megasamples-upgrade-tools', *args]
    start = time.monotonic()
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (OUT/(label+'.log')).open('w') as log:
        rc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    row = dict(status='Passed' if rc == 0 else 'Failed', returncode=rc,
               started_at=started_at, seconds=time.monotonic()-start, command=command)
    print(label, row['status'], f"{row['seconds']:.2f}s", flush=True)
    return label, row


def save(result):
    label, row = result
    results[label] = row
    (OUT/'validation-steps.json').write_text(json.dumps(results, indent=2)+'\n')
    assert row['status'] == 'Passed', label+' failed; inspect the retained log'


save(run('wait-lts-stack', ['.venv/bin/python', 'docs/validation/wait-lts-stack.py']))
save(run('persistence-lts', ['.venv/bin/python', '-u', 'docs/validation/rehearse-lts-persistence.py']))
save(run('resets-lts', ['.venv/bin/python', '-u', 'docs/validation/rehearse-lts-resets.py']))
for engine in ['mysql', 'postgres', 'sqlite']:
    save(run('test-image-'+engine, ['make', 'test-image', 'ENGINE='+engine, 'PY=.venv/bin/python']))
save(run('cold-mysql-six', ['python3', '-u', 'docs/validation/measure-lts-readiness.py'], native=True))
save(run('repository-gate', ['make', 'check', 'PY=.venv/bin/python']))
save(run('asset-audit', ['make', 'audit-assets', 'PY=.venv/bin/python']))
save(run('console-gate', ['make', 'test-console', 'PY=.venv/bin/python']))
save(run('console-deep', ['.venv/bin/python', '-u', 'docs/validation/probe-clients.py']))
save(run('endpoints-lts', ['.venv/bin/python', '-u', 'docs/validation/probe-endpoints.py']))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures = [pool.submit(run, 'runtime-'+engine, ['.venv/bin/python', '-u', 'docs/validation/validate-lts-stack.py', engine])
               for engine in ['mysql', 'postgres', 'sqlite']]
    for future in concurrent.futures.as_completed(futures):
        save(future.result())
print('Passed: all isolated DL-074 command gates and all three runtime matrices', flush=True)
