"""Reset every public scope, then rerun native privileges and complete-table reads.

The PostgreSQL candidate must already be running. All commands execute inside
this repository's existing isolated tools container with env.sh in effect.
"""
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from megasamples import config

assert Path.cwd()==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF']=='/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['MEGASAMPLES_POSTGRES_IMAGE']=='localhost/sql-megasamples-postgres:strict-read'
BASE=Path('build/strict-read')
CFG=config.load()
results={}


def run(label,args,directory=BASE,extra=None):
    directory.mkdir(exist_ok=True,parents=True)
    env={**os.environ,'MEGASAMPLES_VALIDATION_OUT':str(directory),'MEGASAMPLES_NATIVE_READ_TESTS':'1',**(extra or {})}
    started=time.monotonic()
    with (directory/(label+'.log')).open('w') as log:
        rc=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    row=dict(status='Passed' if rc==0 else 'Failed',returncode=rc,seconds=time.monotonic()-started,command=args)
    print(label,row['status'],f"{row['seconds']:.2f}s",flush=True)
    return row


cases=[('pairs',['R='+' '.join(e+':pubs' for e in CFG.engines)]),
       ('dataset-flags',['ENGINE=postgres','D=pubs']),
       ('append-selectors',['R=postgres:nyc_taxi_yellow mysql:nyc_taxi_yellow sqlite:nyc_taxi_yellow']),
       ('every-pair',['R='+' '.join(e+':'+n for e in CFG.engines for n in CFG.datasets(e))]),
       *[(e,['R='+e]) for e in CFG.engines],('all',['R=all'])]
for name,flags in cases:
    directory=BASE/('checkpoint-'+name)
    row=run('reset',['make','reset','PY='+sys.executable,*flags],directory)
    results[name]={'reset':row}
    (BASE/'checkpoints.json').write_text(json.dumps(results,indent=2)+'\n')
    assert row['status']=='Passed',name+' reset failed'
    row=run('native',[sys.executable,'-m','pytest','tests/test_strict_read_native.py','-q','--tb=short'],directory)
    results[name]['native']=row
    assert row['status']=='Passed',name+' privileges failed'
    def matrix(engine):
        return engine,run('reads-'+engine,[sys.executable,'docs/validation/strict-read-reset-matrix.py',engine,
            str(BASE/'baseline'/('reset-matrix-'+engine+'.json'))],directory)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results[name]['reads']=dict(pool.map(matrix,CFG.engines))
    (BASE/'checkpoints.json').write_text(json.dumps(results,indent=2)+'\n')
    assert all(v['status']=='Passed' for v in results[name]['reads'].values()),name+' read fingerprint failed'
print('Passed: every reset scope, native privilege gates and all dataset read fingerprints',flush=True)
