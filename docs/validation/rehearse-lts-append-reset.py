"""An append selector must reset its shared database, including the core's changed rows."""
import json,os,subprocess,sys,time
from pathlib import Path
from megasamples import reset
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import server as pg
root=Path.cwd();out=root/'build/lts-audit'
assert root==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ.get('COMPOSE_PROJECT_NAME')=='megasamples-upgrade'
assert os.environ.get('DOCKER_HOST')=='unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
store=subprocess.check_output(['docker','info','--format','{{.DockerRootDir}}'],text=True).strip();assert store.startswith('/home/rcc-vstudio/working/sql-megasamples-upgrade-env/')
secrets=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if line and not line.startswith('#'))
mysql.NAME='megasamples-mysql';mysql.PW=secrets['MYSQL_ROOT_PASSWORD'];pg.NAME='megasamples-postgres'
def cmd(args):return subprocess.run(args,capture_output=True,text=True,check=True).stdout.strip()
def sq(sql,directory='/data'):return cmd(['docker','exec','megasamples-sqlite','sqlite3','-tabs',directory+'/dvdstore.sqlite',sql])
identifier=int(mysql.rows('SELECT MIN(customerid) FROM dvdstore.customers WHERE age IS NOT NULL')[0][0])
query=f'SELECT age FROM customers WHERE customerid={identifier}'
baseline={'mysql':mysql.rows(query.replace('FROM customers','FROM dvdstore.customers'))[0][0],'postgres':pg.rows(query,'dvdstore')[0][0],'sqlite':sq(query)}
assert len(set(baseline.values()))==1
replacement=19 if int(baseline['mysql'])==18 else 18
hash_before={d:cmd(['docker','exec','megasamples-sqlite','sha256sum',d+'/dvdstore.sqlite']).split()[0] for d in ['/data','/shared']}
assert len(set(hash_before.values()))==1
start=time.time()
with reset.sqlite_connections_closed():
 mysql.sql(f'UPDATE dvdstore.customers SET age={replacement} WHERE customerid={identifier}; CREATE TABLE dvdstore.upgrade_alias_probe(id integer)')
 pg.psql(f'UPDATE customers SET age={replacement} WHERE customerid={identifier}; CREATE TABLE upgrade_alias_probe(id integer)','dvdstore')
 for directory in ['/data','/shared']:sq(f'UPDATE customers SET age={replacement} WHERE customerid={identifier}; CREATE TABLE upgrade_alias_probe(id integer)',directory)
 assert mysql.rows(query.replace('FROM customers','FROM dvdstore.customers'))[0][0]!=baseline['mysql']
 assert pg.rows(query,'dvdstore')[0][0]!=baseline['postgres']
 assert sq(query)!=baseline['sqlite']
 with (out/'reset-append-pairs.log').open('w') as log:
  subprocess.run(['make','reset','PY='+sys.executable,'R=mysql:dvdstore_reviews postgres:dvdstore_reviews sqlite:dvdstore_reviews'],stdout=log,stderr=subprocess.STDOUT,check=True)
 assert mysql.rows(query.replace('FROM customers','FROM dvdstore.customers'))[0][0]==baseline['mysql']
 assert pg.rows(query,'dvdstore')[0][0]==baseline['postgres']
 assert sq(query)==baseline['sqlite']
 assert mysql.rows("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='dvdstore' AND table_name='upgrade_alias_probe'")[0][0]=='0'
 assert pg.rows("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='upgrade_alias_probe'",'dvdstore')[0][0]=='0'
 for directory in ['/data','/shared']:
  assert sq("SELECT COUNT(*) FROM sqlite_schema WHERE name='upgrade_alias_probe'",directory)=='0'
  assert cmd(['docker','exec','megasamples-sqlite','sha256sum',directory+'/dvdstore.sqlite']).split()[0]==hash_before[directory]
result={'status':'Passed','seconds':round(time.time()-start,2),'selectors':['mysql:dvdstore_reviews','postgres:dvdstore_reviews','sqlite:dvdstore_reviews'],'core_row_restored':True,'added_table_removed':True,'sqlite_bytes_restored':True}
(out/'reset-append-results.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
