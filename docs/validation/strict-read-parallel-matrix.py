"""Canonical repository read gates as demo, with independent dataset workers.

Frozen upstream observations and canonical expectations are never rewritten.
SQLite's verified build file is used only after matching both runtime copies.
"""
import concurrent.futures
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import yaml
from megasamples import config, datasets, registry, verify
from megasamples.credentials import client, session
from megasamples.engines import unique_databases
from megasamples.engines.mysql import server as my
from megasamples.engines.postgres import server as pg
from docs.validation.lts_registry import sqlite_registry_rows

ROOT=Path.cwd()
OUT=ROOT/os.environ['MEGASAMPLES_VALIDATION_OUT']
assert ROOT==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF']==str(ROOT.parent/'sql-megasamples-upgrade-env/storage.conf')
CFG=config.load()
SECRETS=config.passwords()


def container(engine):
    return os.environ.get('STRICT_READ_'+engine.upper()+'_CONTAINER','megasamples-'+engine)


def command(*args):
    p=subprocess.run(['docker',*args],text=True,capture_output=True)
    assert p.returncode==0, p.stderr[:300]
    return p.stdout.strip()


def pg_query(sql, database='postgres', binary=False):
    with client('postgres',container('postgres'),'demo',SECRETS['DEMO_PASSWORD']) as cmd:
        p=subprocess.run([*cmd,'-X','-d',database,'-v','ON_ERROR_STOP=1','-qAt','-F','\t'],
            input=sql.encode() if binary else sql,capture_output=True,text=not binary)
    if p.returncode:
        raise RuntimeError(p.stderr[:500])
    return p.stdout


def my_query(sql, database=None, raw=True, **kw):
    with client('mysql',container('mysql'),'demo',SECRETS['DEMO_PASSWORD']) as cmd:
        p=subprocess.run([*cmd,'--batch','-N',*(['--raw'] if raw else []),*(['-D',database] if database else [])],
            input=sql,text=True,capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr[:500])
    return p.stdout


def worker(engine,name):
    start=time.monotonic()
    at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    pg.NAME='megasamples-postgres'
    pg.psql=lambda sql,database='postgres',**kw:pg_query(sql,database)
    pg.copy_out=lambda sql,database:pg_query('COPY ('+sql+') TO STDOUT',database,binary=True)
    my.NAME='megasamples-mysql'
    my.sql=my_query
    frozen={n:yaml.safe_load((ROOT/'build/live'/f'{n}.observed.yaml').read_text())
            for n in CFG.datasets(engine) if datasets.load(n).get('live')}
    def frozen_hub(spec,ad,stage,observed,result):
        expected=frozen[spec.get('name') or spec['database']].get(stage)
        if expected is None:
            result.fail('missing frozen '+stage)
            return None
        if ad.name=='mysql':
            if {key:observed.get(key) for key in expected}!=expected:
                result.fail('differs from frozen build record for '+stage)
            return None
        return expected
    verify.live_hub_observed=frozen_hub
    cls=type(verify.adapter_for(engine,name))
    count,fingerprint=cls.count,cls.fingerprint
    observed={'counts':{},'fingerprints':[]}
    def counted(self,schema,table):
        value=count(self,schema,table)
        observed['counts'][table]=value
        return value
    def fingerprinted(self,schema,table,columns):
        value=fingerprint(self,schema,table,columns)
        observed['fingerprints'].append(dict(table=table,columns=[c for c,_ in columns],n=value[0],x=value[1],s=value[2]))
        return value
    cls.count,cls.fingerprint=counted,fingerprinted
    try:
        with (OUT/f'runtime-{engine}-{name}.log').open('w') as log, contextlib.redirect_stdout(log),contextlib.redirect_stderr(log),session():
            try:
                failures=verify.verify(name,stages=['counts','digests','fks','indexes','views'],engine=engine)
            except (Exception,SystemExit) as exc:
                print(type(exc).__name__,str(exc))
                failures=1
        return name,dict(status='Passed' if failures==0 else 'Failed',failures=failures,started_at=at,
                         seconds=time.monotonic()-start,**observed)
    finally:
        cls.count,cls.fingerprint=count,fingerprint


def main():
    engine=sys.argv[1]
    assert command('info','--format','{{.DockerRootDir}}').startswith(str(ROOT.parent/'sql-megasamples-upgrade-env/'))
    image=command('inspect','--format','{{.Image}}',container(engine))
    sqlite_hashes={}
    with session():
        if engine=='postgres':
            version=pg_query('SHOW server_version').strip()
            data=pg_query('SELECT name,row_counts::text FROM datasets ORDER BY name','megasamples')
            rows=[line.split('\t') for line in data.splitlines()]
        elif engine=='mysql':
            version=my_query('SELECT VERSION()').strip()
            data=my_query('SELECT name,CAST(row_counts AS CHAR) FROM megasamples.datasets ORDER BY name')
            rows=[line.split('\t') for line in data.splitlines()]
        else:
            version=command('exec','megasamples-sqlite','sqlite3',':memory:','SELECT sqlite_version()')
            rows=sqlite_registry_rows(command('exec','megasamples-sqlite','sqlite3','-tabs','/data/megasamples.sqlite','SELECT name,row_counts FROM datasets ORDER BY name'))
            def hash_database(db):
                digest=hashlib.sha256()
                with (ROOT/'build/sqlite'/db/(db+'.sqlite')).open('rb') as stream:
                    for block in iter(lambda:stream.read(1<<20),b''):
                        digest.update(block)
                values={'verified_build':digest.hexdigest()}
                for directory in ['/data','/shared']:
                    values[directory]=command('exec','megasamples-sqlite','sha256sum',directory+'/'+db+'.sqlite').split()[0]
                assert len(set(values.values()))==1,db+': SQLite bytes differ'
                return db,values
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                sqlite_hashes=dict(pool.map(hash_database,unique_databases(CFG.datasets(engine))))
        registry_rows={name:json.loads(counts) for name,counts in rows}
        expected={}
        for name in CFG.datasets(engine):
            expected.setdefault(datasets.load(name)['database'],{}).update(registry.image_counts(name))
        assert expected==registry_rows,engine+': registry differs'
    receipt=dict(engine=engine,version=version,image=image,account='demo' if engine!='sqlite' else 'SQLite file (no server account)',
                 registry_counts=registry_rows,sqlite_hashes=sqlite_hashes,results={})
    # Each worker restores its adapter wrappers before taking another dataset.
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        pending=[pool.submit(worker,engine,name) for name in CFG.datasets(engine)]
        for future in concurrent.futures.as_completed(pending):
            name,row=future.result()
            receipt['results'][engine+':'+name]=row
            (OUT/f'runtime-{engine}.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print(engine,name,row['status'],f"{row['seconds']:.2f}s",flush=True)
    assert all(row['status']=='Passed' for row in receipt['results'].values()),'dataset read failed'
    print('Passed:',engine,'all canonical dataset reads',flush=True)


if __name__=='__main__':
    main()
