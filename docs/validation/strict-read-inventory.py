"""Credential-free grants and executable-routine inventory from isolated servers."""
import datetime
import json
import os
import re
import subprocess
from pathlib import Path
from megasamples import config
from megasamples.credentials import client, session
from megasamples.engines import unique_databases

assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
out = Path(os.environ['MEGASAMPLES_VALIDATION_OUT'])
cfg = config.load()
secret = config.passwords()
reasons = dict(re.findall(r"\('([^']+)','([^']+)'\)", Path('engines/postgres/init/read-routine-names.sql').read_text()))


def query(engine, user, database, sql):
    key = {'postgres': 'POSTGRES_PASSWORD', 'root': 'MYSQL_ROOT_PASSWORD'}.get(user, user.upper() + '_PASSWORD')
    with client(engine, 'megasamples-' + engine, user, secret[key]) as command:
        args = ['-X', '-d', database, '-v', 'ON_ERROR_STOP=1', '-qAt', '-c', sql] if engine == 'postgres' else ['--batch', '-N', database, '-e', sql]
        p = subprocess.run([*command, *args], text=True, capture_output=True)
    assert p.returncode == 0, p.stderr[:300]
    return p.stdout.strip()


result = dict(read_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), postgres={}, mysql={})
with session():
    operators = set(query('postgres','postgres','postgres', "SELECT DISTINCT p.oid::regprocedure::text FROM pg_proc p JOIN pg_operator o ON o.oprcode=p.oid WHERE o.oid<16384 AND p.oid<16384").splitlines())
    casts = set(query('postgres','postgres','postgres', "SELECT DISTINCT p.oid::regprocedure::text FROM pg_proc p JOIN pg_cast c ON c.castfunc=p.oid WHERE c.oid<16384 AND p.oid<16384").splitlines())
    for db in unique_databases(cfg.datasets('postgres')) + ['postgres', 'megasamples', 'template1']:
        sql = """SELECT json_build_object('database',current_database(),'database_acl',
          (SELECT datacl::text FROM pg_database WHERE datname=current_database()),
          'accounts',(SELECT json_agg(json_build_object('account',rolname,'superuser',rolsuper,'createdb',rolcreatedb,
            'createrole',rolcreaterole,'temporary',has_database_privilege(oid,current_database(),'TEMP'),
            'create_database_objects',has_database_privilege(oid,current_database(),'CREATE'))) FROM pg_roles
            WHERE rolname IN ('demo','admin','postgres')),
          'routines',(SELECT json_agg(json_build_object('signature',p.oid::regprocedure::text,'name',proname,
            'namespace',n.nspname,'kind',prokind,'volatility',provolatile,
            'demo_execute',has_function_privilege('demo',p.oid,'EXECUTE'),
            'admin_execute',has_function_privilege('admin',p.oid,'EXECUTE'),
            'superuser_execute',has_function_privilege('postgres',p.oid,'EXECUTE')) ORDER BY p.oid::regprocedure::text)
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace))"""
        row = json.loads(query('postgres','postgres',db,sql))
        for routine in row['routines']:
            if routine['demo_execute']:
                if routine['namespace']=='information_schema' and routine['name'].startswith('_pg_'):
                    reason = 'Upstream information-schema helper: expands supplied arrays or reads type and index metadata'
                elif routine['signature'] in operators:
                    reason = 'Implements an initdb operator: compares or computes supplied values without changing stored state'
                elif routine['signature'] in casts:
                    reason = 'Implements an initdb cast: converts supplied values without changing stored state'
                elif routine['namespace']=='pg_catalog':
                    reason = reasons.get(routine['name'], 'NOT in explicit read policy')
                else:
                    reason = 'NOT in explicit read policy'
                routine['reason'] = reason
        result['postgres'][db] = row
    for user in ['demo','admin','root']:
        result['mysql'][user] = {'grants': query('mysql', user, 'megasamples', 'SHOW GRANTS').splitlines()}
    # Stored-routine inventory is privileged because MySQL hides it from demo.
    result['mysql']['routines'] = query('mysql','root','megasamples',
        "SELECT routine_schema,routine_name,routine_type,security_type FROM information_schema.routines ORDER BY 1,2").splitlines()
(out / 'privileges.json').write_text(json.dumps(result, indent=2) + '\n')
print('Passed: inventory recorded without passwords', flush=True)
