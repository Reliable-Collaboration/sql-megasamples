"""Six fresh-volume MySQL starts against the existing, unchanged readiness gates."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

from megasamples.engines.image_startup import cold_copy_budget, SERVER_BUDGET_SECONDS

OUT = Path('build/lts-audit')
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
assert subprocess.check_output(['podman', 'info', '--format', '{{.Store.GraphRoot}}'], text=True).strip() == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/graph'


def run(*args, check=True):
    return subprocess.run(['podman', *args], capture_output=True, text=True, check=check,
                          env={**os.environ, 'MYSQL_PWD': 'root'})


image = run('image', 'inspect', 'sql-megasamples-mysql:dev', '--format', '{{.Id}}').stdout.strip()
records = []
for iteration in range(6):
    name = 'megasamples-lts-cold-mysql-' + str(iteration)
    assert run('inspect', name, check=False).returncode != 0
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    start = time.monotonic()
    run('run', '-d', '--name', name, '--label', 'megasamples.transient=true',
        '--label', 'megasamples.role=lts-cold-readiness', image)
    returned = time.monotonic()-start
    try:
        deadline = time.monotonic()+SERVER_BUDGET_SECONDS
        while time.monotonic() < deadline:
            result = run('exec', '-e', 'MYSQL_PWD', name, 'mysql', '-uroot', '-N', '-e', 'SELECT VERSION()', check=False)
            if result.returncode == 0:
                break
            time.sleep(.2)
        ready = time.monotonic()-start
        assert result.returncode == 0, 'MySQL never answered within the server budget'
        assert result.stdout.strip().startswith('9.7.4'), 'Wrong candidate image'
        logs = run('logs', '--timestamps', name)
        (OUT/f'cold-mysql-{iteration}.log').write_text(logs.stdout+logs.stderr)
        row = dict(iteration=iteration, image=image, started_at=started_at,
                   copy_run_seconds=returned, query_seconds=ready, server_seconds=ready-returned,
                   cold_budget=cold_copy_budget('mysql'), server_budget=SERVER_BUDGET_SECONDS,
                   data_allocated_bytes=int(run('exec', name, 'du', '-sk', '/var/lib/mysql').stdout.split()[0])*1024,
                   status='Passed' if returned <= cold_copy_budget('mysql') and ready-returned <= SERVER_BUDGET_SECONDS else 'Failed')
        records.append(row)
        (OUT/'cold-mysql.json').write_text(json.dumps(records, indent=2)+'\n')
        print(iteration, row['status'], f'copy/run={returned:.3f}s server={ready-returned:.3f}s', flush=True)
        assert row['status'] == 'Passed'
    finally:
        run('rm', '-fv', name)
