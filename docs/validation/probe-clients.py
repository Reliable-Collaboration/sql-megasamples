"""Read the dataset lists through each isolated console's actual UI or driver."""
import http.cookiejar,json,os,subprocess,time,urllib.parse,urllib.request
from html.parser import HTMLParser
from pathlib import Path
from megasamples import config,datasets
from megasamples.engines import unique_databases
from megasamples.console_test import passwords
assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'
assert os.environ['DOCKER_HOST']=='unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
out=Path(os.environ.get('MEGASAMPLES_VALIDATION_OUT', 'build/client-evidence'));out.mkdir(parents=True,exist_ok=True);cfg=config.load();demo,admin= passwords();results={}
expected={e:set(unique_databases(cfg.datasets(e))) for e in cfg.engines}
def save():
 (out/'console-deep-results.json').write_text(json.dumps(results,indent=2)+'\n')
def complete(name,fn):
 try:results[name]={'status':'Passed',**fn()}
 except Exception as e:results[name]={'status':'Failed','reason':type(e).__name__+': '+str(e)[:300]}
 print(name,results[name]['status'],results[name].get('reason',''),flush=True);save()
def opener():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def phpmyadmin():
 records={}
 for server in [1,2]:
  with opener().open(f'http://127.0.0.1:{cfg.ports["phpmyadmin"]}/index.php?route=/server/databases&server={server}',timeout=60) as r:body=r.read().decode()
  missing=[name for name in expected['mysql'] if name not in body];assert not missing,'Missing databases: '+str(missing)
  records[str(server)]=sorted(expected['mysql'])
 return {'http_ui_database_lists':records}
complete('phpmyadmin',phpmyadmin)
def adminer():
 records={}
 for engine,driver,account,password in [(e,d,a,p) for e,d in [('mysql','server'),('postgres','pgsql')] for a,p in [('demo',demo),('admin',admin)]]:
  op=opener();url=f'http://127.0.0.1:{cfg.ports["adminer"]}/'
  class Token(HTMLParser):
   def handle_starttag(self,t,a):
    d=dict(a)
    if t=='input' and d.get('name')=='token':self.value=d.get('value','')
  with op.open(url,timeout=60) as response:html=response.read().decode()
  token=Token();token.feed(html)
  data=urllib.parse.urlencode({'token':token.value,'auth[driver]':driver,'auth[server]':engine,'auth[username]':account,'auth[password]':password,'auth[db]':''}).encode()
  with op.open(urllib.request.Request(url,data=data),timeout=60) as r:body=r.read().decode()
  missing=[name for name in expected[engine] if name not in body];assert not missing,engine+' missing databases: '+str(missing)
  records[engine+'-'+account]=sorted(expected[engine])
 return {'authenticated_http_ui_database_lists':records}
complete('adminer',adminer)
def dbgate():
 script=r'''(async()=>{
 const e=process.env, accounts={};
 for(const account of ['demo','admin']){
  const mkey='mysql_'+account,pkey='postgres_'+account;
  const my=await require('mysql2/promise').createConnection({host:e['SERVER_'+mkey],port:+e['PORT_'+mkey],user:e['USER_'+mkey],password:e['PASSWORD_'+mkey],database:'megasamples'});
  const [m]=await my.query('SELECT name FROM datasets ORDER BY name');await my.end();
  const {Client}=require('pg'),pg=new Client({host:e['SERVER_'+pkey],port:+e['PORT_'+pkey],user:e['USER_'+pkey],password:e['PASSWORD_'+pkey],database:'megasamples'});
  await pg.connect();const p=await pg.query('SELECT name FROM datasets ORDER BY name');await pg.end();
  accounts[account]={mysql:m.map(x=>x.name),postgres:p.rows.map(x=>x.name)};
 }
 const D=require('better-sqlite3'),s=new D('/data/megasamples.sqlite',{readonly:true}),names=s.prepare('SELECT name FROM datasets ORDER BY name').all();
 const version=s.prepare('SELECT sqlite_version() v').get().v;s.close();
 for(const {name} of names){const db=new D('/data/'+name+'.sqlite',{readonly:true});if(!db.prepare("SELECT count(*) n FROM sqlite_master WHERE type='table'").get().n)throw new Error('No tables in '+name);db.close()}
 console.log(JSON.stringify({accounts,mysql:accounts.demo.mysql,postgres:accounts.demo.postgres,sqlite:names.map(x=>x.name),versions:{mysql2:require('mysql2/package.json').version,pg:require('pg/package.json').version,better_sqlite3:require('better-sqlite3/package.json').version,sqlite_runtime:version}}));
 })().catch(()=>{console.error('Console driver probe failed');process.exit(1)})'''
 p=subprocess.run(['docker','exec','megasamples-dbgate','node','-e',script],capture_output=True,text=True)
 assert p.returncode==0,p.stderr[:200]
 r=json.loads(p.stdout)
 for e in expected:assert set(r[e])==expected[e],e+' registry mismatch'
 for account in ['demo','admin']:
  for e in ['mysql','postgres']:assert set(r['accounts'][account][e])==expected[e],e+' '+account+' registry mismatch'
 return r
complete('dbgate',dbgate)
def cloudbeaver():
 op=opener();url=f'http://127.0.0.1:{cfg.ports["cloudbeaver"]}/api/gql'
 def call(query):
  req=urllib.request.Request(url,data=json.dumps({'query':query}).encode(),headers={'Content-Type':'application/json'})
  with op.open(req,timeout=60) as r:d=json.load(r)
  assert not d.get('errors'),str(d.get('errors'))[:200]
  return d['data']
 call('mutation{openSession{valid}}')
 infos=call('{userConnections{id nodePath}}')['userConnections'];by_id={i['id']:i for i in infos}
 wanted=[f'{e}-{a}' for e in ['mysql','postgres'] for a in ['demo','admin']]+['sqlite-'+n for n in sorted(expected['sqlite'])]
 records={}
 for ident in wanted:
  d=call('mutation{initConnection(projectId:"g_GlobalConfiguration",id:'+json.dumps(ident)+'){connected clientVersion serverVersion}}')['initConnection'];assert d['connected'],ident+' could not connect'
  nodes=call('{navNodeChildren(parentPath:'+json.dumps(by_id[ident]['nodePath'])+'){uri name plainName hasChildren}}')['navNodeChildren']
  records[ident]={'client_version':d.get('clientVersion'),'server_version':d.get('serverVersion'),'children':nodes}
  if ident.startswith(('mysql-','postgres-')):
   engine=ident.split('-')[0]
   names={n['plainName'] or n['name'] for n in nodes}
   if not expected[engine].issubset(names):
    for node in nodes:
     children=call('{navNodeChildren(parentPath:'+json.dumps(node['uri'])+'){uri name plainName hasChildren}}')['navNodeChildren']
     names.update(n['plainName'] or n['name'] for n in children)
   assert expected[engine].issubset(names),ident+' missing catalogues '+str(sorted(expected[engine]-names))
 return {'opened_connections':len(wanted),'connections':records}
complete('cloudbeaver',cloudbeaver)
assert all(v['status']=='Passed' for v in results.values())
