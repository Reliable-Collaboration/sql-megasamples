import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from megasamples import config
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import server as pg
assert os.environ.get('COMPOSE_PROJECT_NAME')=='megasamples-upgrade'
assert os.environ.get('DOCKER_HOST')=='unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
store=subprocess.run(['docker','info','--format','{{.DockerRootDir}}'],capture_output=True,text=True,check=True).stdout.strip()
assert store.startswith('/home/rcc-vstudio/working/sql-megasamples-upgrade-env/')
root=Path.cwd();out=root/'build/lts-audit';cfg=config.load()
secrets=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if line and not line.startswith('#'))
mysql.NAME='megasamples-mysql';mysql.PW=secrets['MYSQL_ROOT_PASSWORD'];pg.NAME='megasamples-postgres'
def command(args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout.strip()
def sq(sql,directory='/data'):
 return command(['docker','exec','megasamples-sqlite','sqlite3',directory+'/pubs.sqlite',sql])
def sql_job(engine):
 if engine=='mysql':return mysql.rows('SELECT job_desc FROM pubs.jobs WHERE job_id=1')[0][0]
 if engine=='postgres':return pg.rows('SELECT job_desc FROM jobs WHERE job_id=1','pubs')[0][0]
 return sq('SELECT job_desc FROM jobs WHERE job_id=1')
def sqlite_hash(directory='/data'):
 return command(['docker','exec','megasamples-sqlite','sha256sum',directory+'/pubs.sqlite']).split()[0]
baseline={engine:sql_job(engine) for engine in cfg.engines}
identifier=mysql.rows("SELECT MIN(pub_id) FROM pubs.pub_info WHERE logo IS NOT NULL")[0][0]
assert identifier.isdigit()
def binary_value(engine,directory='/data'):
 if engine=='mysql':value=mysql.rows(f"SELECT HEX(logo) FROM pubs.pub_info WHERE pub_id='{identifier}'")[0][0]
 elif engine=='postgres':value=pg.rows(f"SELECT encode(logo,'hex') FROM pub_info WHERE pub_id='{identifier}'",'pubs')[0][0]
 else:value=sq(f"SELECT hex(logo) FROM pub_info WHERE pub_id='{identifier}'",directory)
 return hashlib.sha256(bytes.fromhex(value)).hexdigest()
binary_baseline={engine:binary_value(engine) for engine in cfg.engines}
assert len(set(binary_baseline.values()))==1,'pubs binary values differ between engines before reset'
sqlite_baseline=sqlite_hash();assert sqlite_baseline==sqlite_hash('/shared')
def mutate(engines,whole):
 for engine in engines:
  if engine=='mysql':
   mysql.sql("UPDATE pubs.jobs SET job_desc='UPGRADE_RESET_PROBE' WHERE job_id=1")
   mysql.sql(f"UPDATE pubs.pub_info SET logo=0x000102FEFF WHERE pub_id='{identifier}'")
   mysql.sql('CREATE TABLE pubs.upgrade_reset_probe(id INT)')
   if whole:mysql.sql('CREATE DATABASE upgrade_reset_probe')
  elif engine=='postgres':
   pg.psql("UPDATE jobs SET job_desc='UPGRADE_RESET_PROBE' WHERE job_id=1; CREATE TABLE upgrade_reset_probe(id integer)",'pubs')
   pg.psql(f"UPDATE pub_info SET logo=decode('000102feff','hex') WHERE pub_id='{identifier}'",'pubs')
   if whole:pg.psql('CREATE DATABASE upgrade_reset_probe')
  else:
   for directory in ['/data','/shared']:
    sq("UPDATE jobs SET job_desc='UPGRADE_RESET_PROBE' WHERE job_id=1; CREATE TABLE upgrade_reset_probe(id integer)",directory)
   for directory in ['/data','/shared']:sq(f"UPDATE pub_info SET logo=X'000102FEFF' WHERE pub_id='{identifier}'",directory)
   if whole:
    for directory in ['/data','/shared']:
     command(['docker','exec','megasamples-sqlite','sqlite3',directory+'/upgrade_reset_probe.sqlite','CREATE TABLE extra(id integer)'])
  assert sql_job(engine)!=baseline[engine],engine+' mutation did not take effect'
  assert binary_value(engine)!=binary_baseline[engine],engine+' binary mutation did not take effect'
def restored(engines,whole):
 for engine in engines:
  assert sql_job(engine)==baseline[engine],engine+' row did not reset'
  assert binary_value(engine)==binary_baseline[engine],engine+' binary value did not reset'
  if engine=='mysql':
   assert mysql.rows("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='pubs' AND table_name='upgrade_reset_probe'")[0][0]=='0'
   if whole:assert mysql.rows("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='upgrade_reset_probe'")[0][0]=='0'
  elif engine=='postgres':
   assert pg.rows("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='upgrade_reset_probe'",'pubs')[0][0]=='0'
   if whole:assert pg.rows("SELECT COUNT(*) FROM pg_database WHERE datname='upgrade_reset_probe'")[0][0]=='0'
  else:
   assert sqlite_hash()==sqlite_baseline and sqlite_hash('/shared')==sqlite_baseline
   if whole:
    for directory in ['/data','/shared']:
     assert subprocess.run(['docker','exec','megasamples-sqlite','test','-e',directory+'/upgrade_reset_probe.sqlite']).returncode!=0
# Exact definitions are held after each scope, so a later whole reset cannot
# conceal a constraint lost by an earlier dataset selector. SQLite is byte-checked.
MYSQL_FK = "SELECT rc.constraint_schema,rc.constraint_name,rc.table_name,k.ordinal_position,k.column_name,k.referenced_table_schema,k.referenced_table_name,k.referenced_column_name,rc.update_rule,rc.delete_rule FROM information_schema.referential_constraints rc JOIN information_schema.key_column_usage k ON k.constraint_schema=rc.constraint_schema AND k.constraint_name=rc.constraint_name WHERE rc.constraint_schema NOT IN ('mysql','sys','information_schema','performance_schema') ORDER BY 1,2,4"
PG_FK = "SELECT n.nspname,c.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE k.contype='f' AND n.nspname NOT IN ('pg_catalog','information_schema') ORDER BY 1,2,3"
def fk_definitions(engine):
 if engine=='mysql':return mysql.rows(MYSQL_FK)
 return {db:pg.rows(PG_FK,db) for db in __import__('megasamples.engines',fromlist=['unique_databases']).unique_databases(cfg.datasets('postgres'))}
fk_baseline={e:fk_definitions(e) for e in ['mysql','postgres']}
fk_results={'initial':fk_baseline}
def check_foreign_keys(engines,label):
 current={e:fk_definitions(e) for e in engines if e in fk_baseline}
 for e,value in current.items():assert value==fk_baseline[e],e+' foreign key definitions changed in '+label
 fk_results[label]={'status':'Passed','definitions':current}
 (out/'reset-foreign-keys.json').write_text(json.dumps(fk_results,indent=2)+'\n')
results={}
cases=[('pairs',list(cfg.engines),False,['R='+' '.join(e+':pubs' for e in cfg.engines)])]
cases += [(engine,[engine],True,['ENGINE='+engine]) for engine in cfg.engines]
cases += [('all',list(cfg.engines),True,['R=all'])]
for name,engines,whole,flags in cases:
 mutate(engines,whole);started=time.time()
 with (out/f'reset-{name}.log').open('w') as log:
  rc=subprocess.run(['make','reset','PY='+sys.executable,*flags],stdout=log,stderr=subprocess.STDOUT).returncode
 result={'status':'Passed' if rc==0 else 'Failed','returncode':rc,'seconds':round(time.time()-started,2)}
 if rc==0:
  try:
   restored(engines,whole);check_foreign_keys(engines,name);result['same_count_row_and_binary_values_restored']=True
  except Exception as exc:result.update(status='Failed',reason=type(exc).__name__+': '+str(exc))
 results[name]=result;print(name,result,flush=True)
 (out/'reset-results.json').write_text(json.dumps(results,indent=2)+'\n')
 if result['status']!='Passed':raise SystemExit(1)
subprocess.run([sys.executable,'-u',str(root/'docs/validation/rehearse-lts-append-reset.py')],check=True)
check_foreign_keys(list(cfg.engines),'append-selectors')
print('All reset scopes restored same-count row mutations and removed added tables/databases',flush=True)
# Every configured engine:dataset selector in one grouped invocation, including append aliases.
from megasamples.engines import unique_databases
physical={e:unique_databases(cfg.datasets(e)) for e in cfg.engines}
hashes_before={db:{directory:command(['docker','exec','megasamples-sqlite','sha256sum',directory+'/'+db+'.sqlite']).split()[0] for directory in ['/data','/shared']} for db in physical['sqlite']}
with __import__('megasamples.reset',fromlist=['sqlite_connections_closed']).sqlite_connections_closed():
 mutate(list(cfg.engines),False)
 for engine,databases in physical.items():
  for database in databases:
   if engine=='mysql':mysql.sql(f'CREATE TABLE `{database}`.client_upgrade_reset_probe(i INT)')
   elif engine=='postgres':pg.psql('CREATE TABLE client_upgrade_reset_probe(i INT)',database)
   else:
    for directory in ['/data','/shared']:
     command(['docker','exec','megasamples-sqlite','sqlite3',directory+'/'+database+'.sqlite','CREATE TABLE client_upgrade_reset_probe(i INT)'])
 selectors=[e+':'+name for e in cfg.engines for name in cfg.datasets(e)]
 start=time.monotonic()
 with (out/'reset-every-pair.log').open('w') as log:
  rc=subprocess.run(['make','reset','PY='+sys.executable,'R='+' '.join(selectors)],stdout=log,stderr=subprocess.STDOUT).returncode
 assert rc==0,'Grouped pair reset failed; see log'
 restored(list(cfg.engines),False)
 check_foreign_keys(list(cfg.engines),'every-selector')
 for engine,databases in physical.items():
  for database in databases:
   if engine=='mysql':assert mysql.rows(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='{database}' AND table_name='client_upgrade_reset_probe'")[0][0]=='0'
   elif engine=='postgres':assert pg.rows("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='client_upgrade_reset_probe'",database)[0][0]=='0'
   else:
    for directory in ['/data','/shared']:
     assert command(['docker','exec','megasamples-sqlite','sha256sum',directory+'/'+database+'.sqlite']).split()[0]==hashes_before[database][directory]
 result={'status':'Passed','returncode':rc,'seconds':round(time.monotonic()-start,2),'selectors':selectors,'physical_databases':physical,'all_markers_removed':True,'same_count_pubs_text_and_binary_restored':True,'every_sqlite_file_byte_identical':True}
 (out/'reset-every-pair-results.json').write_text(json.dumps(result,indent=2)+'\n');print('All configured pair selectors:',result['status'],result['seconds'],flush=True)
