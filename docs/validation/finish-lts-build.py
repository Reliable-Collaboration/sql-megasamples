"""Complete DL-074 packaging after the recorded input-rebuild process succeeds.

This driver is isolated-store-only. It refuses failed/incomplete input verification,
checks the existing frozen live-feed fingerprints, and stops at the first failed
step. It never disables MySQL Shell version checks or changes dataset pins.
"""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import yaml
from lts_live_records import compare_frozen_records

ROOT = Path.cwd()
OUT = ROOT / 'build/lts-audit'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://' + str(ROOT.parent / 'sql-megasamples-upgrade-env/podman.sock')
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['podman', 'info', '--format', '{{.Store.GraphRoot}}'], text=True).strip() == str(ROOT.parent / 'sql-megasamples-upgrade-env/graph')

resume = sys.argv[1] == '--resume-after-restore'
if not resume:
    pid = int(sys.argv[1])
    while True:
        try:
            command = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:
            break
        if b'megasamples' not in command or b'--no-fetch' not in command:
            break
        time.sleep(5)

text = (OUT / 'build-mysql-all.log').read_text()
assert text.rstrip().endswith('build: 0 failure(s)'), 'Input rebuild did not finish successfully'
cfg = yaml.safe_load((ROOT / 'megasamples.yaml').read_text())
configured = cfg['engines']['mysql']['datasets']
verified = dict(re.findall(r'^([\w_]+) on mysql: (\d+) failure\(s\)$', text, re.M))
assert set(verified) == set(configured) and all(value == '0' for value in verified.values())
results = json.loads((OUT/'build-steps.json').read_text()) if resume else {
    'input_rebuild': {'status': 'Passed', 'dataset_results': verified,
                      'log_completed_at': datetime.datetime.fromtimestamp((OUT / 'build-mysql-all.log').stat().st_mtime, datetime.timezone.utc).isoformat()}}
if resume:
    for step in ['input_rebuild', 'uv-sync-handoff', 'fresh-oracle-build-server', 'restore-oracle-all', 'verify-expanded-core']:
        assert results[step]['status'] == 'Passed', 'Resume requires successful '+step
    running = subprocess.check_output(['podman', 'inspect', '--format', '{{.Image}}', 'megasamples-build-mysql'], text=True).strip()
    expected = subprocess.check_output(['podman', 'image', 'inspect', '--format', '{{.Id}}', 'sql-megasamples-mysql-base:9.7.4-shell-9.7.1'], text=True).strip()
    assert running.removeprefix('sha256:') == expected.removeprefix('sha256:'), 'Resume build-server image changed'
(OUT / 'build-steps.json').write_text(json.dumps(results, indent=2)+'\n')


def run(label, args):
    command = ['podman', 'exec', '-e', 'CONTAINERS_STORAGE_CONF', '-e', 'CONTAINERS_CONF',
               '-e', 'DOCKER_HOST', '-e', 'COMPOSE_PROJECT_NAME', '-e', 'PYTHONPATH=.', '-e', 'PYTHONUNBUFFERED=1',
               'megasamples-upgrade-tools', *args]
    start = time.monotonic()
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (OUT / (label+'.log')).open('w') as log:
        rc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    results[label] = dict(status='Passed' if rc == 0 else 'Failed', returncode=rc,
                          started_at=started_at, seconds=time.monotonic()-start, command=command)
    (OUT / 'build-steps.json').write_text(json.dumps(results, indent=2)+'\n')
    print(label, results[label]['status'], f'{time.monotonic()-start:.2f}s', flush=True)
    assert rc == 0, label+' failed; inspect the retained log'


if not resume:
    run('uv-sync-handoff', ['/opt/venv/bin/uv', 'sync', '--locked', '--python', '/usr/local/bin/python3'])
    run('fresh-oracle-build-server', ['.venv/bin/python', '-m', 'megasamples', 'build-server', 'fresh'])
    physical = [name for name in configured if not yaml.safe_load((ROOT/'datasets'/name/'dataset.yaml').read_text()).get('append')]
    run('restore-oracle-all', ['make', 'restore', 'PY=.venv/bin/python', 'D='+' '.join(physical)])
    # Exercise both directions of the patched embedded runtime with binary data,
    # routines and WWI's richer JSON/spatial types, retaining all expected values.
    run('shell-dump-lts', ['.venv/bin/python', '-m', 'megasamples', 'dump', 'pubs', 'wideworldimporters'])
    run('shell-restore-lts', ['make', 'restore', 'PY=.venv/bin/python', 'D=pubs wideworldimporters'])
    for name in ['pubs', 'wideworldimporters']:
        run('verify-shell-roundtrip-'+name, ['.venv/bin/python', '-m', 'megasamples', 'verify', name, '--engine', 'mysql'])
    # Refresh the expanded core, then compare against the original core+append receipts.
    run('verify-expanded-core', ['.venv/bin/python', '-m', 'megasamples', 'verify', 'chicago_crimes', '--engine', 'mysql'])
previous = json.loads((ROOT / 'build/client-evidence/client-final-mysql-frozen-live-records.json').read_text())
current = {name: yaml.safe_load((ROOT/'build/live'/f'{name}.observed.yaml').read_text()) for name in previous}
specs = {name: yaml.safe_load((ROOT/'datasets'/name/'dataset.yaml').read_text()) for name in previous}
compare_frozen_records(previous, current, specs)
results['frozen_live_comparison'] = dict(status='Passed', datasets=sorted(current), records=current,
                                         original_records=previous,
                                         comparison='Exact original core+append counts, canonical fingerprints and views; no regenerated expectations')
(OUT / 'build-steps.json').write_text(json.dumps(results, indent=2)+'\n')
run('ports-lts', ['.venv/bin/python', '-m', 'megasamples', 'ports-check'])
run('catalogue-lts', ['make', 'catalogue', 'PY=.venv/bin/python'])
run('bake-mysql-lts', ['make', 'image', 'ENGINE=mysql', 'FROM_DUMPS=1', 'PY=.venv/bin/python'])
run('start-lts-stack', ['make', 'up', 'PY=.venv/bin/python'])
