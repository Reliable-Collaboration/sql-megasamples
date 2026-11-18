"""Authenticated wire checks for only the two alternate localhost endpoints."""
import datetime,json,os,sys
from pathlib import Path
import psycopg,pymysql
import psycopg.pq,importlib.metadata,secrets as random_secrets,uuid
assert psycopg.pq.__impl__ == "python"
assert psycopg.pq.version() == 180007
assert importlib.metadata.version("pymysql") == "1.2.4"
from megasamples import config,registry
root=Path.cwd();out=root/os.environ.get('MEGASAMPLES_VALIDATION_OUT', 'build/client-evidence')
assert root==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ.get('COMPOSE_PROJECT_NAME')=='megasamples-upgrade'
cfg=config.load();assert cfg.ports['mysql']==13306 and cfg.ports['postgres']==15432
secrets=config.passwords()
expected=registry.image_counts('pubs')['jobs'];results={}
for engine in ['mysql','postgres']:
 port=cfg.ports[engine]
 def connect(user,pw):
  if engine=='mysql':return pymysql.connect(host='127.0.0.1',port=port,user=user,password=pw,database='pubs',autocommit=True,connect_timeout=10)
  return psycopg.connect(host='127.0.0.1',port=port,user=user,password=pw,dbname='pubs',autocommit=True,connect_timeout=10)
 with connect('demo',secrets['DEMO_PASSWORD']) as db:
  with db.cursor() as cursor:
   cursor.execute('SELECT version()');version=cursor.fetchone()[0]
   cursor.execute('SELECT count(*) FROM jobs');count=cursor.fetchone()[0];assert count==expected
   try:cursor.execute('DELETE FROM jobs WHERE 1=0')
   except (pymysql.MySQLError,psycopg.Error) as exc:
    code=exc.args[0] if engine=='mysql' else exc.sqlstate
    assert code in [1142,'42501'],(engine,'unexpected denial code',code)
   else:raise AssertionError(engine+' demo unexpectedly has DELETE permission')
 try:
  db=connect('demo',secrets['DEMO_PASSWORD']+'-deliberately-wrong')
 except (pymysql.MySQLError,psycopg.Error) as exc:
  code=exc.args[0] if engine=='mysql' else exc.sqlstate
  # libpq may omit SQLSTATE for authentication failures before a session exists.
  if engine=='mysql':assert code==1045
  else:assert code in [None,'28P01']
 else:
  db.close();raise AssertionError(engine+' accepted an incorrect password')
 with connect('admin',secrets['ADMIN_PASSWORD']) as db:
  with db.cursor() as cursor:
   cursor.execute('CREATE TABLE upgrade_endpoint_probe(id integer PRIMARY KEY)')
   try:
    cursor.execute('INSERT INTO upgrade_endpoint_probe VALUES(1)')
    cursor.execute('SELECT count(*) FROM upgrade_endpoint_probe');assert cursor.fetchone()[0]==1
   finally:cursor.execute('DROP TABLE upgrade_endpoint_probe')
 results[engine]={'status':'Passed','endpoint':'127.0.0.1:'+str(port),'version':version,'pubs_jobs_count':count,'demo_read_only':True,'incorrect_password_rejected':True,'admin_writes':True}
(out/'endpoint-results.json').write_text(json.dumps({'read_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results},indent=2)+'\n')
print(json.dumps(results,indent=2))

# Fresh accounts exercise uncached authentication rather than only an existing login cache.
fresh={}
for engine in ['mysql','postgres']:
 port=cfg.ports[engine];user='client_probe_'+uuid.uuid4().hex[:12];password=random_secrets.token_urlsafe(30)
 if engine=='mysql':
  admin=pymysql.connect(host='127.0.0.1',port=port,user='admin',password=secrets['ADMIN_PASSWORD'],database='pubs',autocommit=True)
 else:
  admin=psycopg.connect(host='127.0.0.1',port=port,user='admin',password=secrets['ADMIN_PASSWORD'],dbname='pubs',autocommit=True)
 with admin:
  with admin.cursor() as c:
   if engine=='mysql':c.execute("CREATE USER %s@'%%' IDENTIFIED BY %s",(user,password))
   else:c.execute(psycopg.sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(psycopg.sql.Identifier(user),psycopg.sql.Literal(password)))
   try:
    if engine=='mysql':
     c.execute('SELECT plugin FROM mysql.user WHERE user=%s',(user,));assert c.fetchone()[0]=='caching_sha2_password'
     test=pymysql.connect(host='127.0.0.1',port=port,user=user,password=password,database='information_schema',autocommit=True)
    else:test=psycopg.connect(host='127.0.0.1',port=port,user=user,password=password,dbname='pubs',autocommit=True)
    with test:
     with test.cursor() as cur:cur.execute('SELECT 1');assert cur.fetchone()[0]==1
   finally:
    if engine=='mysql':c.execute("DROP USER %s@'%%'",(user,))
    else:c.execute(psycopg.sql.SQL('DROP ROLE {}').format(psycopg.sql.Identifier(user)))
 fresh[engine]={'status':'Passed','new_account_authentication':True,'temporary_account_removed':True}
value={'status':'Passed','read_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results,'fresh_authentication':fresh,'drivers':{'pymysql':importlib.metadata.version('pymysql'),'psycopg':psycopg.__version__,'psycopg_implementation':psycopg.pq.__impl__,'libpq_version':psycopg.pq.version()}}
(out/'endpoint-results.json').write_text(json.dumps(value,indent=2)+'\n')
print('Fresh driver authentication Passed; temporary accounts removed')
