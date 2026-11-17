"""Exercise the upgraded loader and its authentication/dump/generator paths on a disposable server."""
import contextlib,hashlib,io,json,os,secrets,subprocess,sys,time
from pathlib import Path
from megasamples.engines.mysql import server as mysql
from megasamples.sources import tpcc_load
assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'
assert os.environ['DOCKER_HOST']=='unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
out=Path('build/client-evidence');out.mkdir(parents=True,exist_ok=True);name='megasamples-upgrade-client-mysql';password=secrets.token_urlsafe(30);created=False;results={}
env={**os.environ,'MYSQL_ROOT_PASSWORD':password,'MYSQL_PWD':password}
image='docker.io/library/mysql:26.10.0@sha256:b401608b19ffafbc6aa3d84523acf783078c8cf01e0f7ee1dc3ca75a5701a999'
def run(args,**kw):
 p=subprocess.run(['docker',*args],capture_output=True,text=True,env=env,**kw)
 if p.returncode:raise RuntimeError((p.stderr or p.stdout).replace(password,'[redacted]')[-700:])
 return p.stdout.strip()
def query(sql):return run(['exec','-e','MYSQL_PWD',name,'mysql','-uroot','-N','-e',sql])
def save():
 text=json.dumps(results,indent=2)+'\n';assert password not in text
 (out/'loader-probe-results.json').write_text(text)
assert subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0,'Test container already exists'
try:
 run(['run','-d','--name',name,'--label','megasamples.transient=true','--label','megasamples.role=client-validation','--memory','2g','-e','MYSQL_ROOT_PASSWORD','-e','MYSQL_ROOT_HOST=%',image,'mysqld','--innodb-buffer-pool-size=256M']);created=True
 started=time.monotonic()
 for _ in range(240):
  try:
   if query('SELECT 1')=='1':break
  except RuntimeError:pass
  time.sleep(.5)
 else:raise RuntimeError('Scratch MySQL never answered')
 ip=run(['inspect','-f','{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',name]);env['MYSQL_HOST']=ip
 query('CREATE DATABASE client_loader_probe; CREATE TABLE client_loader_probe.t(id INT PRIMARY KEY,txt VARCHAR(100),b VARBINARY(20)); INSERT INTO client_loader_probe.t VALUES (1,CONVERT(0xCEB10A74616209 USING utf8mb4),0x000102FEFF)')
 shell='''set -eu
 mysql --version
 mysqldump --version
 mysql -h "$MYSQL_HOST" -uroot -N -e 'SELECT VERSION()'
 mysqldump -h "$MYSQL_HOST" -uroot --databases client_loader_probe --routines --triggers --events --hex-blob --set-gtid-purged=OFF > /evidence/loader-roundtrip.sql
 mysql -h "$MYSQL_HOST" -uroot -e 'DROP DATABASE client_loader_probe'
 mysql -h "$MYSQL_HOST" -uroot < /evidence/loader-roundtrip.sql
 mysql -h "$MYSQL_HOST" -uroot -N -e 'SELECT id,HEX(txt),HEX(b) FROM client_loader_probe.t'
 '''
 output=run(['run','--rm','--label','megasamples.transient=true','-e','MYSQL_HOST','-e','MYSQL_PWD','-v',str(out.resolve())+':/evidence','sql-megasamples-loader:dev','sh','-c',shell])
 assert output.splitlines()[-1]=='1\tCEB10A74616209\t000102FEFF'
 results['oracle_cli_dump_restore']={'status':'Passed','output':output,'dump_sha256':hashlib.sha256((out/'loader-roundtrip.sql').read_bytes()).hexdigest()};save()
 # A new remote account forces a first caching_sha2_password exchange with Connector/C.
 query("CREATE DATABASE connector_probe; CREATE USER 'connector_probe'@'%' IDENTIFIED BY '"+password+"'; GRANT ALL ON connector_probe.* TO 'connector_probe'@'%'")
 assert query("SELECT plugin FROM mysql.user WHERE user='connector_probe'")=='caching_sha2_password'
 env['MYSQL_HOST']='127.0.0.1'
 common='sysbench /usr/share/sysbench/oltp_read_only.lua --mysql-host="$MYSQL_HOST" --mysql-user=connector_probe --mysql-password="$MYSQL_PWD" --mysql-db=connector_probe --tables=1 --table-size=32'
 output=run(['run','--rm','--label','megasamples.transient=true','-e','MYSQL_HOST','-e','MYSQL_PWD','--network','container:'+name,'sql-megasamples-loader:dev','sh','-c',common+' prepare && '+common+' --events=10 --threads=1 run'])
 results['connector_c_first_auth_and_prepared_queries']={'status':'Passed','authentication_plugin':'caching_sha2_password','rows':query('SELECT COUNT(*) FROM connector_probe.sbtest1')};save()
 # Run the repository's exact TPC-C loader against this throwaway server.
 mysql.NAME=name;mysql.PW=password;mysql.start=lambda **kwargs:None
 capture=io.StringIO()
 with contextlib.redirect_stdout(capture),contextlib.redirect_stderr(capture):tpcc_load.main(['--warehouses','1','--threads','1'])
 text=capture.getvalue().replace(password,'[redacted]');(out/'loader-tpcc.log').write_text(text)
 results['repository_tpcc_loader']={'status':'Passed','scope':'one warehouse, repository cardinalities and order-line bounds; content is intentionally nondeterministic'};save()
 print('Loader CLI roundtrip, first caching_sha2 exchange/prepared queries, and repository TPC-C loader Passed',flush=True)
except BaseException as exc:
 results['failure']={'status':'Failed','reason':str(exc).replace(password,'[redacted]')[-700:]};save();raise SystemExit('Loader validation failed; see sanitized receipt')
finally:
 if created:run(['rm','-fv',name])
