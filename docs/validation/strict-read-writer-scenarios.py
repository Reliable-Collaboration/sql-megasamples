"""Run the repository's stored-routine and trigger scenarios as actual writers."""
import contextlib
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from megasamples import config, verify
from megasamples.credentials import client, session
from megasamples.engines.mysql import server as my
from megasamples.engines.postgres import server as pg

assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF']=='/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
engine,user=sys.argv[1:]
assert (engine,user) in [('postgres','admin'),('postgres','postgres'),('mysql','admin'),('mysql','root')]
out=Path(os.environ['MEGASAMPLES_VALIDATION_OUT'])
password=config.passwords()[{'postgres':'POSTGRES_PASSWORD','root':'MYSQL_ROOT_PASSWORD'}.get(user,'ADMIN_PASSWORD')]


def execute(sql,database=None,raw=True,**kwargs):
    with client(engine,'megasamples-'+engine,user,password) as cmd:
        args=(['-X','-d',database or 'postgres','-v','ON_ERROR_STOP=1','-qAt','-F','\t','-P','null=NULL']
              if engine=='postgres' else ['--batch','-N',*(['--raw'] if raw else []),*(['-D',database] if database else [])])
        p=subprocess.run([*cmd,*args],input=sql,text=True,capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr[:500])
    return p.stdout


pg.NAME='megasamples-postgres'
pg.psql=execute
pg.psql_script=execute
my.NAME='megasamples-mysql'
my.sql=execute
results={}
with session():
    for name in config.load().datasets(engine):
        with (out/f'writer-{engine}-{user}-{name}.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            try:
                failures=verify.verify(name,stages=['routines','triggers'],engine=engine)
            except (Exception,SystemExit) as exc:
                print(type(exc).__name__,str(exc))
                failures=1
        results[name]=dict(status='Passed' if failures==0 else 'Failed',failures=failures)
        (out/f'writer-{engine}-{user}.json').write_text(json.dumps(dict(engine=engine,account=user,results=results),indent=2)+'\n')
        print(engine,user,name,results[name]['status'],flush=True)
assert all(row['status']=='Passed' for row in results.values())
