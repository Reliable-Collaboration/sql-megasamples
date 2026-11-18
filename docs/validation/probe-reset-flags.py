"""Native Make ENGINE/D flags: remove markers and restore a same-count row mutation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from megasamples import reset
from megasamples.credentials import session

OUT = Path('build/credential-upgrade')
assert Path.cwd() == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip().startswith('/home/rcc-vstudio/working/sql-megasamples-upgrade-env/')


def sql(engine, text, database='pubs', directory='/data'):
    if engine == 'mysql':
        result = reset.my('megasamples-mysql', text, database)
    elif engine == 'postgres':
        result = reset.pg('megasamples-postgres', text, database)
    else:
        result = subprocess.run(['docker', 'exec', 'megasamples-sqlite', 'sqlite3', directory + '/' + database + '.sqlite', text], capture_output=True, text=True)
    assert result.returncode == 0, engine + ' flag probe query failed'
    return result.stdout.strip()


def file_hash(database, directory):
    return subprocess.check_output(['docker', 'exec', 'megasamples-sqlite', 'sha256sum', directory + '/' + database + '.sqlite'], text=True).split()[0]


start = time.monotonic()
with session(), reset.sqlite_connections_closed():
    baseline = {engine: sql(engine, 'SELECT job_desc FROM jobs WHERE job_id=1') for engine in ['mysql', 'postgres', 'sqlite']}
    hashes = {(db, d): file_hash(db, d) for db in ['pubs', 'chinook'] for d in ['/data', '/shared']}
    for engine in baseline:
        directories = ['/data', '/shared'] if engine == 'sqlite' else ['/data']
        for directory in directories:
            sql(engine, "UPDATE jobs SET job_desc='CREDENTIAL_FLAG_PROBE' WHERE job_id=1", directory=directory)
            for database in ['pubs', 'chinook']:
                sql(engine, 'CREATE TABLE credential_flags_probe(i integer)', database, directory)
        assert sql(engine, 'SELECT job_desc FROM jobs WHERE job_id=1') != baseline[engine]
    command = ['make', 'reset', 'ENGINE=mysql,postgres,sqlite', 'D=pubs chinook', 'PY=' + sys.executable]
    with (OUT / 'reset-flags.log').open('w') as log:
        rc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    assert rc == 0, 'Make reset with ENGINE/D flags failed'
    for engine in baseline:
        assert sql(engine, 'SELECT job_desc FROM jobs WHERE job_id=1') == baseline[engine]
        for database in ['pubs', 'chinook']:
            if engine == 'mysql':
                assert sql(engine, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='credential_flags_probe'", database) == '0'
            elif engine == 'postgres':
                assert sql(engine, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='credential_flags_probe'", database) == '0'
            else:
                for directory in ['/data', '/shared']:
                    assert file_hash(database, directory) == hashes[database, directory]
row = dict(status='Passed', command=command, returncode=rc, seconds=time.monotonic() - start,
           engines=list(baseline), databases=['pubs', 'chinook'], same_count_text_restored=True,
           all_markers_removed=True, both_sqlite_copies_byte_identical=True)
(OUT / 'reset-flags.json').write_text(json.dumps(row, indent=2) + '\n')
print('Passed: Make ENGINE/D flags, multi-name expansion, row restoration, marker removal and SQLite bytes', flush=True)
