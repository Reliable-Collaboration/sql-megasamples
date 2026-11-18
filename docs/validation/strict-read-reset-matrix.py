"""Fast native whole-table read fingerprints for *every* reset checkpoint.

These supplement (not replace) the repository's canonical cross-engine matrix:
PostgreSQL folds a native MD5 of each complete JSON row; MySQL uses its native
extended table checksum. Compare only within the same engine. SQLite compares
both runtime files byte-for-byte. Every dataset alias is mapped to its database.
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from megasamples import config, datasets, registry
from megasamples.credentials import client, session
from megasamples.engines import unique_databases

assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
cfg = config.load()
out = Path(os.environ['MEGASAMPLES_VALIDATION_OUT'])
secret = config.passwords()
engine = sys.argv[1]
reference = Path(sys.argv[2]) if len(sys.argv)>2 else None
started = datetime.datetime.now(datetime.timezone.utc).isoformat()


def query(database, sql):
    with client(engine, 'megasamples-'+engine, 'demo', secret['DEMO_PASSWORD']) as command:
        args = (['-X','-d',database,'-v','ON_ERROR_STOP=1','-qAt','-F','\t'] if engine=='postgres'
                else ['--batch','-N','--raw',database])
        p = subprocess.run([*command,*args], input=sql, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr[:400]
    return p.stdout.strip()


rows = {}
with session():
    for db in unique_databases(cfg.datasets(engine)):
        want = {}
        for name in cfg.datasets(engine):
            if datasets.load(name)['database']==db:
                want.update(registry.image_counts(name))
        row = {'tables':{}}
        if engine=='postgres':
            for table, expected in sorted(want.items()):
                quoted = '"'+table.replace('"','""')+'"'
                value = query(db, "SELECT count(*),coalesce(bit_xor(h),0),coalesce(sum(h::numeric),0) FROM "
                              f"(SELECT ('x'||substr(md5(row_to_json(t)::text),1,16))::bit(64)::bigint AS h FROM {quoted} t) q")
                count, xor, total = value.split('\t')
                assert int(count)==expected, db+':'+table+' count differs'
                row['tables'][table] = {'count':int(count),'xor':xor,'sum':total}
        elif engine=='mysql':
            names = ','.join('`'+t.replace('`','``')+'`' for t in sorted(want))
            checksums = query(db, 'CHECKSUM TABLE '+names+' EXTENDED')
            native = {line.split('\t')[0].split('.',1)[1]:line.split('\t')[1] for line in checksums.splitlines()}
            for table, expected in sorted(want.items()):
                count = query(db, 'SELECT COUNT(*) FROM `'+table.replace('`','``')+'`')
                assert int(count)==expected, db+':'+table+' count differs'
                assert native[table]!='NULL', db+':'+table+' checksum unsupported'
                row['tables'][table] = {'count':int(count),'native_checksum':native[table]}
        else:
            hashes={}
            for directory in ['/data','/shared']:
                p=subprocess.run(['docker','exec','megasamples-sqlite','sha256sum',directory+'/'+db+'.sqlite'],text=True,capture_output=True)
                assert p.returncode==0
                hashes[directory]=p.stdout.split()[0]
            assert len(set(hashes.values()))==1, db+': SQLite runtime files differ'
            row['sha256']=hashes
        rows[db]=row
        print(engine, db, 'read fingerprint Passed', flush=True)
        receipt=dict(status='Running',engine=engine,started_at=started,databases=rows,
                     dataset_pairs={name:datasets.load(name)['database'] for name in cfg.datasets(engine)})
        (out/('reset-matrix-'+engine+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
if reference:
    previous=json.loads(reference.read_text())
    assert previous['databases']==rows, engine+': contents differ from baseline fingerprints'
receipt.update(status='Passed',completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               reference=str(reference) if reference else None)
(out/('reset-matrix-'+engine+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print('Passed:',engine,'all dataset pairs, counts and complete native fingerprints',flush=True)
