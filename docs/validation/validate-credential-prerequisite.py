"""Run DL-079's full isolated gates, preserving separate logs and timed receipts."""
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path.cwd()
OUT = ROOT / 'build/credential-upgrade'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://' + str(ROOT.parent / 'sql-megasamples-upgrade-env/podman.sock')
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['podman', 'info', '--format', '{{.Store.GraphRoot}}'], text=True).strip() == str(ROOT.parent / 'sql-megasamples-upgrade-env/graph')
results = {}


def run(label, args):
    command = ['podman', 'exec', '-e', 'CONTAINERS_STORAGE_CONF', '-e', 'CONTAINERS_CONF',
               '-e', 'DOCKER_HOST', '-e', 'COMPOSE_PROJECT_NAME', '-e', 'PYTHONPATH=.',
               '-e', 'PYTHONUNBUFFERED=1', '-e', 'MEGASAMPLES_VALIDATION_OUT=build/credential-upgrade',
               'megasamples-upgrade-tools', *args]
    start = time.monotonic()
    at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (OUT / (label + '.log')).open('w') as log:
        rc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    row = dict(status='Passed' if rc == 0 else 'Failed', returncode=rc, started_at=at,
               seconds=time.monotonic() - start, command=command)
    print(label, row['status'], f"{row['seconds']:.2f}s", flush=True)
    return label, row


def save(result):
    label, row = result
    results[label] = row
    (OUT / 'validation-steps.json').write_text(json.dumps(results, indent=2) + '\n')
    assert row['status'] == 'Passed', label + ' failed; inspect the retained log'


save(run('repository-gate-before', ['make', 'check', 'PY=.venv/bin/python']))
save(run('native-postgres-reset', ['make', 'reset', 'R=postgres:pubs', 'PY=.venv/bin/python']))
save(run('all-reset-scopes', ['.venv/bin/python', '-u', 'docs/validation/rehearse-lts-resets.py']))
save(run('dataset-flags-reset', ['.venv/bin/python', '-u', 'docs/validation/probe-reset-flags.py']))
for engine in ['mysql', 'postgres', 'sqlite']:
    save(run('test-image-' + engine, ['make', 'test-image', 'ENGINE=' + engine, 'PY=.venv/bin/python']))
# Refresh only console configuration, credentials and their generated private local pages.
save(run('up-consoles', ['make', 'up', 'PY=.venv/bin/python']))
save(run('wait-stack', ['.venv/bin/python', 'docs/validation/wait-lts-stack.py']))
save(run('console-gate', ['make', 'test-console', 'PY=.venv/bin/python']))
save(run('console-deep', ['.venv/bin/python', '-u', 'docs/validation/probe-clients.py']))
save(run('endpoints', ['.venv/bin/python', '-u', 'docs/validation/probe-endpoints.py']))
save(run('repository-gate', ['make', 'check', 'PY=.venv/bin/python']))
save(run('asset-audit', ['make', 'audit-assets', 'PY=.venv/bin/python']))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures = [pool.submit(run, 'runtime-' + engine, ['.venv/bin/python', '-u', 'docs/validation/validate-lts-stack.py', engine])
               for engine in ['mysql', 'postgres', 'sqlite']]
    for future in concurrent.futures.as_completed(futures):
        save(future.result())
print('Passed: all isolated credential-prerequisite gates and all runtime matrices', flush=True)
