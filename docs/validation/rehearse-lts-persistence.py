"""Rehearse a stop/start of only this Compose project and inspect every loaded table."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from megasamples import config,datasets
from megasamples.engines import unique_databases
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import server as pg
root=Path.cwd();out=root/'build/lts-audit';cfg=config.load()
assert root==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ.get('COMPOSE_PROJECT_NAME')=='megasamples-upgrade'
store=subprocess.run(['docker','info','--format','{{.DockerRootDir}}'],capture_output=True,text=True,check=True).stdout.strip()
assert store.startswith('/home/rcc-vstudio/working/sql-megasamples-upgrade-env/')
secrets=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if line and not line.startswith('#'))
mysql.NAME='megasamples-mysql';mysql.PW=secrets['MYSQL_ROOT_PASSWORD'];pg.NAME='megasamples-postgres'
def command(args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout.strip()
def sq(sql,db='pubs',directory='/data'):
 return command(['docker','exec','megasamples-sqlite','sqlite3','-tabs',f'{directory}/{db}.sqlite',sql])
def snapshot():
 result={}
 for engine in cfg.engines:
  entry={}
  for db in unique_databases(cfg.datasets(engine)):
   if engine=='mysql':
    tables=[row[0] for row in mysql.rows(f"SELECT table_name FROM information_schema.tables WHERE table_schema='{db}' AND table_type='BASE TABLE' ORDER BY table_name")]
    entry[db]={table:int(mysql.rows(f'SELECT COUNT(*) FROM `{db}`.`{table}`')[0][0]) for table in tables}
   elif engine=='postgres':
    tables=[row[0] for row in pg.rows("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name",db)]
    entry[db]={table:int(pg.rows(f'SELECT COUNT(*) FROM "{table}"',db)[0][0]) for table in tables}
   else:
    tables=sq("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",db).splitlines()
    entry[db]={'tables':{table:int(sq(f'SELECT COUNT(*) FROM "{table}"',db)) for table in tables},'sha256':command(['docker','exec','megasamples-sqlite','sha256sum',f'/data/{db}.sqlite']).split()[0]}
  result[engine]=entry
 return result
mysql.sql('DROP TABLE IF EXISTS pubs.upgrade_persistence_probe; CREATE TABLE pubs.upgrade_persistence_probe(id integer PRIMARY KEY, marker varchar(30)); INSERT INTO pubs.upgrade_persistence_probe VALUES(1,\'stop_start_probe\')')
pg.psql("DROP TABLE IF EXISTS upgrade_persistence_probe; CREATE TABLE upgrade_persistence_probe(id integer PRIMARY KEY, marker varchar(30)); INSERT INTO upgrade_persistence_probe VALUES(1,'stop_start_probe')",'pubs')
sq("DROP TABLE IF EXISTS upgrade_persistence_probe; CREATE TABLE upgrade_persistence_probe(id integer PRIMARY KEY, marker varchar(30)); INSERT INTO upgrade_persistence_probe VALUES(1,'stop_start_probe')")
before=snapshot();names=['megasamples-'+engine for engine in cfg.engines]
ids={name:command(['docker','inspect','--format','{{.Id}}',name]) for name in names}
(out/'persistence-before-snapshot.json').write_text(json.dumps({'actual_counts_before':before,'container_ids':ids},indent=2)+'\n')
start=time.time();compose=['docker','compose','-p','megasamples-upgrade','-f',str(root/'compose.yaml')]
with (out/'persistence-stop-start.log').open('w') as log:
 subprocess.run(compose+['stop'],stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run(compose+['start'],stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run([sys.executable,str(root/'docs/validation/wait-lts-stack.py')],stdout=log,stderr=subprocess.STDOUT,check=True)
elapsed=round(time.time()-start,2)
after=snapshot();assert before==after,'actual table counts or SQLite bytes changed across stop/start'
assert ids=={name:command(['docker','inspect','--format','{{.Id}}',name]) for name in names},'stop/start unexpectedly replaced a container'
assert mysql.rows('SELECT marker FROM pubs.upgrade_persistence_probe WHERE id=1')[0][0]=='stop_start_probe'
assert pg.rows('SELECT marker FROM upgrade_persistence_probe WHERE id=1','pubs')[0][0]=='stop_start_probe'
assert sq('SELECT marker FROM upgrade_persistence_probe WHERE id=1')=='stop_start_probe'
assert sq('SELECT marker FROM upgrade_persistence_probe WHERE id=1',directory='/shared')=='stop_start_probe'
(out/'persistence-results.json').write_text(json.dumps({'status':'Passed','stop_start_seconds':elapsed,'container_ids':ids,'actual_counts_before':before,'actual_counts_after':after,'probe_retained':True},indent=2)+'\n')
# Restore the probe databases from the images, including SQLite's byte-exact files.
with (out/'persistence-probe-reset.log').open('w') as log:
 subprocess.run(['make','reset','PY='+sys.executable,'R=mysql:pubs postgres:pubs sqlite:pubs'],stdout=log,stderr=subprocess.STDOUT,check=True)
print('Passed: every actual table count, all SQLite bytes, inserted markers and container IDs survived stop/start; probe databases restored. Downtime/readiness seconds:',elapsed,flush=True)
