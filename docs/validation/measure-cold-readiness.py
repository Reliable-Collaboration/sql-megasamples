"""Fresh anonymous-volume starts, sequential and alternating, in the isolated store only.

Run after sourcing the supplied env.sh. Never drops host caches or publishes ports.
Image IDs come from the dataset and client validation receipts; no images are rebuilt.
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
OUT = Path('build/cold-readiness')
OUT.mkdir(parents=True, exist_ok=True)
IMAGES = {
    ('mysql', 'main'): '77813c185ab5c5a07f0606e5f7291796a1d962d65f80d597b33d3994da696662',
    ('mysql', 'pr11'): '93e5c70696fbf527aaa7a4c611cea467f3885f942be47156163dc73385475658',
    ('sqlite', 'main'): 'd314f2d8343fe43f48f6c9ed556b9087d96715cb2f5f741e2085541e4f22b67a',
    ('sqlite', 'pr11'): '090695cab2b5085144862daaedc9839036058f5ec0387a866c653eb8b9670ebb',
    ('postgres', 'pr11'): '8ec3c3143a2bf5d36134f6576b8c3b487af2c10a0578246f4a45c52dee053449',
}
PATHS = {'mysql': '/var/lib/mysql', 'postgres': '/var/lib/postgresql/18/docker', 'sqlite': '/data'}


def run(*args, check=True):
    return subprocess.run(['podman', *args], capture_output=True, text=True, check=check)


def query(engine, name, sql, registry=False):
    if engine == 'mysql':
        args = ['mysql', '-uroot', '-proot', '-N', '--batch', '-e', sql]
    elif engine == 'postgres':
        args = ['psql', '-U', 'postgres', '-h', '127.0.0.1', '-d',
                'megasamples' if registry else 'postgres', '-tAc', sql]
    else:
        args = ['sqlite3', '/data/megasamples.sqlite', sql]
    return run('exec', name, *args, check=False)


records = []
for iteration in range(6):
    sequence = list(IMAGES)
    if iteration % 2:
        sequence.reverse()
    for engine, variant in sequence:
        name = f'megasamples-cold-gate-{engine}-{variant}-{iteration}'
        image = IMAGES[engine, variant]
        started_at = datetime.datetime.now(datetime.timezone.utc)
        start = time.monotonic()
        run('run', '-d', '--name', name, '--label', 'megasamples.transient=true',
            '--label', 'megasamples.role=cold-readiness', image)
        returned = time.monotonic() - start
        try:
            while time.monotonic() - start < returned + 30:
                result = query(engine, name, 'SELECT 1')
                if result.returncode == 0:
                    break
                time.sleep(.2)
            assert result.returncode == 0, result.stderr
            ready = time.monotonic() - start
            inspected = json.loads(run('inspect', name).stdout)[0]
            logs = run('logs', '--timestamps', name)
            log_text = logs.stdout + logs.stderr
            (OUT / f'{engine}-{variant}-{iteration}.log').write_text(log_text)
            # SQLite's image is a file container; StartedAt is its process-ready event.
            marker = 'ready for connections' if engine == 'mysql' else 'ready to accept connections'
            ready_lines = [line for line in log_text.splitlines() if marker in line]
            reported = ready_lines[-1].split()[0] if ready_lines else inspected['State']['StartedAt']
            report_time = datetime.datetime.fromisoformat(reported.replace('Z', '+00:00'))
            registry_sql = ('SELECT name FROM megasamples.datasets ORDER BY name' if engine == 'mysql'
                            else 'SELECT name FROM datasets ORDER BY name')
            registry = query(engine, name, registry_sql, registry=True)
            assert registry.returncode == 0, registry.stderr
            size = int(run('exec', name, 'du', '-sk', PATHS[engine]).stdout.split()[0]) * 1024
            row = dict(engine=engine, variant=variant, iteration=iteration, image=image,
                       wall_start=started_at.isoformat(), run_return_seconds=returned,
                       query_ready_seconds=ready, server_seconds=ready-returned,
                       reported_ready_at=reported,
                       reported_ready_kind='server log' if ready_lines else 'container StartedAt (no server)',
                       reported_ready_to_query_seconds=(started_at + datetime.timedelta(seconds=ready)-report_time).total_seconds(),
                       data_allocated_bytes=size, registry=registry.stdout.split(),
                       mounts=[{k: m[k] for k in ('Type', 'Name', 'Destination') if k in m}
                               for m in inspected['Mounts']])
            records.append(row)
            (OUT / 'measurements.json').write_text(json.dumps(records, indent=2)+'\n')
            print(engine, variant, iteration, f'copy/run={returned:.3f}s query={ready:.3f}s server={ready-returned:.3f}s bytes={size}', flush=True)
        finally:
            run('rm', '-fv', name)
