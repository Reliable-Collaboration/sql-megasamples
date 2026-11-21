"""Native MySQL write denials and the built-in-function account-ACL boundary.

This is an evidence probe, not an assertion that SELECT-only grants forbid every
stateful built-in. The named lock is released on the same connection and again
automatically when that connection closes. No stored dataset rows are changed.
"""
import datetime
import json
import os
from pathlib import Path

from megasamples import config
from megasamples.engines import unique_databases
from docs.validation.strict_read_clients import query

assert Path.cwd() == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
container = 'megasamples-mysql'


def read(database, sql):
    result = query('mysql', container, 'demo', database, sql)
    assert result.returncode == 0, 'native read failed'
    return result.stdout.strip()


def refused(database, sql):
    result = query('mysql', container, 'demo', database, sql)
    assert result.returncode != 0 and 'denied' in result.stderr.lower(), 'expected permission denial'
    return 'Passed'


databases = {}
for database in unique_databases(config.load().datasets('mysql')) + ['megasamples']:
    assert read(database, 'SHOW GRANTS') == 'GRANT SELECT, SHOW VIEW ON *.* TO `demo`@`%`'
    checks = {'create': refused(database, 'CREATE TABLE strict_boundary_table(i int)')}
    table = read(database, "SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() "
                 "AND table_type='BASE TABLE' ORDER BY table_name LIMIT 1")
    if table:
        quoted = '`' + table.replace('`', '``') + '`'
        column = read(database, "SELECT column_name FROM information_schema.columns WHERE table_schema=DATABASE() "
                      "AND table_name='" + table.replace("'", "''") + "' ORDER BY ordinal_position LIMIT 1")
        column = '`' + column.replace('`', '``') + '`'
        for label, sql in [('insert', f'INSERT INTO {quoted} SELECT * FROM {quoted} LIMIT 0'),
                           ('update', f'UPDATE {quoted} SET {column}={column} WHERE false'),
                           ('delete', f'DELETE FROM {quoted} WHERE false'),
                           ('alter', f'ALTER TABLE {quoted} ADD COLUMN strict_boundary_column int'),
                           ('drop', f'DROP TABLE {quoted}')]:
            checks[label] = refused(database, sql)
    databases[database] = checks

lock = 'megasamples.strict_read_boundary_probe'
obtained_and_released = read('megasamples', f"SELECT GET_LOCK('{lock}',0); SELECT RELEASE_LOCK('{lock}')")
assert obtained_and_released.splitlines() == ['1', '1']
assert read('megasamples', f"SELECT IS_FREE_LOCK('{lock}')") == '1'
receipt = {
    'read_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'write_denials': {'status': 'Passed', 'databases': databases},
    'temporary_and_stored_routines': 'Covered separately by test_strict_read_native.py',
    'strict_read_builtin_denial': {
        'status': 'Failed', 'expected': 'The strict read rule would refuse acquiring a named lock',
        'observed': 'SELECT-only demo acquired and released the lock successfully'},
    'builtin_function_read_only_enforcement': {
        'status': 'Unsupported', 'demo_get_lock_succeeded': True, 'release_succeeded': True,
        'lock_free_after_connection_closed': True,
        'reason': 'Stored-routine EXECUTE grants do not govern built-in GET_LOCK. SELECT-only account grants alone do not enforce an all-statements read allow-list.'},
    'sources_read_at': '2026-11-18 09:56:36 UTC',
    'sources': ['https://dev.mysql.com/doc/refman/9.7/en/locking-functions.html',
                'https://dev.mysql.com/doc/refman/9.7/en/privileges-provided.html']}
Path('build/strict-read/mysql-boundary.json').write_text(json.dumps(receipt, indent=2) + '\n')
print('Passed: native write denials; Failed: strict named-lock denial; Unsupported: enforcing it using stored-routine grants')

raise SystemExit(1 if receipt['strict_read_builtin_denial']['status']=='Failed' else 0)
