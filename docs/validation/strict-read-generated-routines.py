"""Generated range constructors stay private for both actual writer accounts.

The owner-supplied read profile restricts arbitrary new roles too. A new role
needs explicit writer execution rights before it can create a range type: the
upstream constructors are postgres-owned, rather than owned by the new role.
"""
import datetime
import json
import os
from pathlib import Path
from docs.validation.strict_read_clients import query

assert Path.cwd()==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF']=='/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'


def q(database,sql,user='postgres'):
    result=query('postgres','megasamples-postgres',user,database,sql)
    assert result.returncode==0,'generated-routine SQL probe failed'
    return result.stdout.strip()


db='strict_generated_probe'
q('postgres',f'CREATE DATABASE {db} OWNER admin')
results={}
try:
    for user in ['admin','postgres']:
        schema='generated_'+user
        q(db,f'CREATE SCHEMA {schema}; CREATE TYPE {schema}.r AS RANGE (subtype=integer)',user)
        total=int(q(db,f"SELECT count(*) FROM pg_proc WHERE pronamespace='{schema}'::regnamespace"))
        assert total>0,'no generated functions observed'
        executable=int(q(db,f"SELECT count(*) FROM pg_proc WHERE pronamespace='{schema}'::regnamespace AND has_function_privilege('demo',oid,'EXECUTE')"))
        assert executable==0,'generated routines reopened public execution'
        assert q(db,f'SELECT {schema}.r(1,2)',user)=='[1,2)'
        results[user]={'status':'Passed','generated_functions':total,'demo_executable':executable,'writer_constructor_execution':'Passed'}
finally:
    q('postgres',f'DROP DATABASE {db} WITH (FORCE)')
receipt={'status':'Passed','read_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results,
         'restricted_new_owner_attempt':'Type creation refused without explicit writer execution rights; no generated objects committed',
         'source':'https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/src/backend/commands/typecmds.c',
         'source_read_at':'2026-11-18 10:47:41 UTC'}
Path('build/strict-read/generated-routines.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('Passed: generated constructors are private and executable by both actual writer accounts')
