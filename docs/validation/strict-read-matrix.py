"""Run repository counts/fingerprints/views through authenticated demo clients.

Use MEGASAMPLES_VALIDATION_OUT for an existing receipt directory. No routine or
trigger mutation scenarios are run under demo: the native tests deny those.
"""
import os
import runpy
import subprocess
from pathlib import Path
from megasamples import config, verify
from megasamples.credentials import client, session
from megasamples.engines.postgres import server as pg
from megasamples.engines.mysql import server as my

assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
secrets = config.passwords()
original_verify = verify.verify
verify.verify = lambda dataset, **kw: original_verify(dataset, stages=['counts', 'digests', 'views'], **kw)


def pg_query(sql, database='postgres', binary=False):
    with client('postgres', pg.NAME, 'demo', secrets['DEMO_PASSWORD']) as command:
        p = subprocess.run([*command, '-X', '-d', database, '-v', 'ON_ERROR_STOP=1', '-qAt', '-F', '\t'],
                           input=sql.encode() if binary else sql, capture_output=True, text=not binary)
    if p.returncode:
        raise RuntimeError(p.stderr[:500])
    return p.stdout


def my_query(sql, database=None, raw=True, **kw):
    with client('mysql', my.NAME, 'demo', secrets['DEMO_PASSWORD']) as command:
        p = subprocess.run([*command, '--batch', '-N', *(['--raw'] if raw else []),
                            *(['-D', database] if database else [])], input=sql, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[:500])
    return p.stdout


pg.psql = lambda sql, database='postgres', **kw: pg_query(sql, database)
pg.copy_out = lambda sql, database: pg_query('COPY (' + sql + ') TO STDOUT', database, binary=True)
my.sql = my_query
with session():
    runpy.run_path(str(Path(__file__).with_name('validate-lts-stack.py')), run_name='__main__')
