"""Finish account rotation, canonical reads and writer scenarios after all resets.

Run in the isolated tools container with env.sh and the candidate image selected.
Successful steps are retained so an interrupted evidence run can resume safely.
"""
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE=Path('build/strict-read')
assert Path.cwd()==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF']=='/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['MEGASAMPLES_POSTGRES_IMAGE']=='localhost/sql-megasamples-postgres:strict-read'
CASES=['pairs','dataset-flags','append-selectors','every-pair','mysql','postgres','sqlite','all']
while True:
    try:
        checkpoints=json.loads((BASE/'checkpoints.json').read_text())
    except (FileNotFoundError,json.JSONDecodeError):
        checkpoints={}
    if any(row.get(stage,{}).get('status')=='Failed' for row in checkpoints.values() for stage in ['reset','native']):
        raise SystemExit('a reset or native checkpoint failed')
    if all(name in checkpoints and all(checkpoints[name].get(stage,{}).get('status')=='Passed' for stage in ['reset','native'])
           and all(checkpoints[name].get('reads',{}).get(e,{}).get('status')=='Passed' for e in ['mysql','postgres','sqlite']) for name in CASES):
        break
    time.sleep(5)

path=BASE/'final-validation-steps.json'
results=json.loads(path.read_text()) if path.exists() else {}


def run(label,args,directory=BASE):
    if results.get(label,{}).get('status')=='Passed':
        return results[label]
    directory.mkdir(exist_ok=True,parents=True)
    env={**os.environ,'MEGASAMPLES_VALIDATION_OUT':str(directory),'STRICT_READ_NATIVE_DRIVER':'library',
         'MEGASAMPLES_NATIVE_READ_TESTS':'1'}
    start=time.monotonic()
    at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (BASE/(label+'.log')).open('w') as log:
        rc=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
    row=dict(status='Passed' if rc==0 else 'Failed',returncode=rc,seconds=time.monotonic()-start,started_at=at,command=args)
    print(label,row['status'],f"{row['seconds']:.2f}s",flush=True)
    return row


def save(label,row):
    results[label]=row
    path.write_text(json.dumps(results,indent=2)+'\n')
    assert row['status']=='Passed',label+' failed; retained log has the native result'


save('rotation',run('rotation',[sys.executable,'docs/validation/strict-read-rotation.py']))
save('rotation-native',run('rotation-native',[sys.executable,'-m','pytest','tests/test_strict_read_native.py','-q','--tb=short']))

def rotated_reads(engine):
    label='rotation-reads-'+engine
    return label,run(label,[sys.executable,'docs/validation/strict-read-reset-matrix.py',engine,
         str(BASE/'baseline'/('reset-matrix-'+engine+'.json'))],BASE/'rotation')

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for label,row in pool.map(rotated_reads,['mysql','postgres','sqlite']):
        save(label,row)

# The final PostgreSQL canonical matrix ran on the pristine candidate while the
# stack reset checkpoints ran. The unchanged MySQL/SQLite images are checked here.
def canonical(engine):
    label='canonical-final-'+engine
    return label,run(label,[sys.executable,'docs/validation/strict-read-parallel-matrix.py',engine],BASE/'final-candidate')

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for label,row in pool.map(canonical,['mysql','sqlite']):
        save(label,row)

# Keep writers on one engine sequential: routines/trigger scenarios share data.
def writers(engine):
    accounts=['admin','postgres'] if engine=='postgres' else ['admin','root']
    return [(engine+'-'+account,run('writer-'+engine+'-'+account,
             [sys.executable,'docs/validation/strict-read-writer-scenarios.py',engine,account],BASE/'final-candidate'))
            for account in accounts]

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for rows in pool.map(writers,['postgres','mysql']):
        for label,row in rows:
            save('writer-'+label,row)
save('repository-final',run('repository-final',['make','check','PY='+sys.executable]))
print('Passed: candidate rotation, all dataset reads, writer scenarios and repository gate',flush=True)
