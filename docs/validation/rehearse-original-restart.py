#!/usr/bin/env python3
"""Native DL-089 exact-original restart using tiny fresh databases in existing images.

Isolated-store only. No shipped datasets, live values or image builds. The actual
runbook route-dispatch block runs from fresh Bash with scratch namespace mapping.
Generated scratch credentials stay in private files and are never displayed.
"""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import sqlite3
import subprocess
import tarfile
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[2];ENV=ROOT.parent/'sql-megasamples-upgrade-env'
spec=importlib.util.spec_from_file_location('native_down',Path(__file__).with_name('rehearse-quiescence-down.py'))
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)


def main():
    os.umask(0o077)
    assert Path.cwd()==ROOT
    assert os.environ.get('CONTAINERS_STORAGE_CONF')==str(ENV/'storage.conf')
    assert os.environ.get('DOCKER_HOST')=='unix://'+str(ENV/'podman.sock')
    pod=n.pod;run=n.run
    assert pod('info','--format','{{.Store.GraphRoot}}')==str(ENV/'graph')
    def inventory():
        names=pod('ps','-a','--format','{{.Names}}').splitlines()
        return sorted(pod('inspect','-f','{{.Name}}|{{.Id}}|{{.Image}}|{{.State.Status}}|{{.State.StartedAt}}',*names).splitlines())
    before=inventory();assert len(before)==12
    out=Path(tempfile.mkdtemp(prefix='dl089-original-',dir=ROOT/'build'));project=out.name
    receipt=dict(at=datetime.now(timezone.utc).isoformat(),results={},artifacts=str(out.relative_to(ROOT)))
    checkout=out/'checkout'
    run(['git','clone','--shared','--no-hardlinks',str(ROOT),str(checkout)])
    (checkout/'consoles').mkdir(exist_ok=True)
    backup=out/'backup';backup.mkdir()
    attempt=backup/'rollback-replica';attempt.mkdir()
    for name in ('postgres','mysql','sqlite','sqlite-shared'):(backup/name).mkdir()
    replica=n.module('replica',Path(__file__).with_name('rehearse-rollback-replica.py'))
    replica.populate_names(backup)
    data={name:out/name for name in ('postgres','mysql','sqlite')}
    for path in data.values():path.mkdir()
    data['postgres'].chmod(0o755)  # official entrypoint traverses the PGDATA parent as postgres
    con=sqlite3.connect(data['sqlite']/'fixture.sqlite');con.execute('create table probe(value integer)');con.execute('insert into probe values (86)');con.commit();con.close()
    images={name:pod('inspect','-f','{{.Image}}','megasamples-'+name) for name in ('postgres','mysql','sqlite','landing')}
    ports={}
    for name in ('postgres','mysql','landing'):
        with socket.socket() as listener:listener.bind(('127.0.0.1',0));ports[name]=listener.getsockname()[1]
    envpath=checkout/'.env'
    original={key:secrets.token_hex(24) for key in ('POSTGRES_PASSWORD','MYSQL_ROOT_PASSWORD')}
    rotated={key:secrets.token_hex(24) for key in original}
    def write_env(values):envpath.write_text(''.join(k+'='+v+'\n' for k,v in values.items()));envpath.chmod(0o600)
    write_env(original)
    config=dict(services={
      'postgres':dict(image='sha256:'+images['postgres'],pull_policy='never',container_name=project+'-postgres',entrypoint=['/usr/local/bin/docker-entrypoint.sh'],command=['postgres'],
          environment=dict(POSTGRES_PASSWORD='${POSTGRES_PASSWORD}',PGDATA='/var/lib/postgresql/18/docker'),volumes=[dict(type='volume',target='/var/lib/postgresql',volume=dict(nocopy=True))],ports=[f'127.0.0.1:{ports["postgres"]}:5432'],healthcheck=dict(test=['CMD','pg_isready','-U','postgres'],interval='2s',timeout='2s',retries=90)),
      'mysql':dict(image='sha256:'+images['mysql'],pull_policy='never',container_name=project+'-mysql',entrypoint=['/entrypoint.sh'],command=['mysqld'],
          environment=dict(MYSQL_ROOT_PASSWORD='${MYSQL_ROOT_PASSWORD}',MYSQL_ROOT_HOST='%'),volumes=[dict(type='volume',target='/var/lib/mysql',volume=dict(nocopy=True))],ports=[f'127.0.0.1:{ports["mysql"]}:3306'],healthcheck=dict(test=['CMD','mysqladmin','ping','-h','127.0.0.1'],interval='2s',timeout='2s',retries=90)),
      'sqlite':dict(image='sha256:'+images['sqlite'],pull_policy='never',container_name=project+'-sqlite',entrypoint=['sh','-c',
          'rm -f /shared/.complete; for f in /data/*.sqlite; do n=$$(basename "$$f"); cp -f "$$f" "/shared/.$$n.part" && mv -f "/shared/.$$n.part" "/shared/$$n" || exit 1; done; touch /shared/.complete; exec sleep infinity'],
          volumes=[dict(type='volume',target='/data',volume=dict(nocopy=True)),'shared:/shared'],healthcheck=dict(test=['CMD-SHELL','test -f /shared/.complete'],interval='2s',timeout='2s',retries=90)),
      'landing':dict(image='sha256:'+images['landing'],pull_policy='never',container_name=project+'-landing',entrypoint=['sh','-c','trap "exit 0" TERM; while :; do sleep 1; done'],ports=[f'127.0.0.1:{ports["landing"]}:8080'])},volumes={'shared':dict(name=project+'-shared')})
    for service in config['services'].values():service['restart']='unless-stopped'
    compose=checkout/'compose.yaml';compose.write_text(json.dumps(config));(checkout/'megasamples.yaml').write_text('{}')
    retained_ports=dict(engines=['postgres','mysql','sqlite'],consoles=['landing'],ports=ports)
    (attempt/'original-ports.json').write_text(json.dumps(retained_ports))
    (backup/'original-running-services.txt').write_text('postgres\nmysql\nsqlite\nlanding\n')
    (backup/'rollback-branch.txt').write_text(run(['git','-C',str(checkout),'branch','--show-current']).stdout)
    (backup/'original-commit.txt').write_text(run(['git','-C',str(checkout),'rev-parse','HEAD']).stdout)
    with tarfile.open(backup/'original-configurations.tar','w') as archive:
        for name in ('.env','compose.yaml','megasamples.yaml','consoles'):archive.add(checkout/name,arcname=name)
    digest=hashlib.sha256((backup/'original-configurations.tar').read_bytes()).hexdigest()
    (backup/'original-configurations.sha256').write_text(digest+'  original-configurations.tar\n')
    configdir=attempt/'configuration';configdir.mkdir()
    with tarfile.open(backup/'original-configurations.tar') as archive:archive.extractall(configdir,filter='data')
    # Namespace adaptation only: helper's fixed service prefix and runbook project.
    helper=attempt/'live-upgrade.py';helper.write_text(Path(__file__).with_name('live-upgrade.py').read_text().replace('megasamples-',project+'-'))
    gatepath=attempt/'quiescence.py';gatepath.write_bytes(Path(__file__).with_name('quiescence.py').read_bytes())
    u=n.module('original_upgrade',helper);g=n.gate
    u.pod=pod;g.pod=pod
    api=None
    anonymous_volumes=[]
    def comp(*args):return run(['docker','compose','-p',project,'-f',str(compose),*args],timeout=180)
    def save(): (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    # Authentication uses the existing host-network tools container's installed
    # native drivers. Only fixture file paths cross argv; credentials never do.
    auth=out/'auth.py'
    auth.write_text('''import hashlib,json,pathlib,sys
import psycopg,pymysql
root=pathlib.Path(sys.argv[1]);ports=json.loads((root/'backup/rollback-replica/original-ports.json').read_text())['ports']
values=dict(line.split('=',1) for line in (root/'checkout/.env').read_text().splitlines())
refused=sys.argv[2]=='refuse';init=sys.argv[2]=='init';out={}
for engine in ('postgres','mysql'):
 try:
  if engine=='postgres':
   conn=psycopg.connect(host='127.0.0.1',port=ports[engine],user='postgres',password=values['POSTGRES_PASSWORD'],dbname='postgres',connect_timeout=5)
  else:
   conn=pymysql.connect(host='127.0.0.1',port=ports[engine],user='root',password=values['MYSQL_ROOT_PASSWORD'],connect_timeout=5)
 except Exception as error:
  assert refused
  assert ('password authentication failed' in str(error)) if engine=='postgres' else (error.args[0]==1045)
  out[engine]='authentication refused';continue
 assert not refused
 with conn.cursor() as cur:
  if init:
   if engine=='mysql':cur.execute('CREATE DATABASE fixture');cur.execute('USE fixture')
   cur.execute('CREATE TABLE probe(value INTEGER)');cur.execute('INSERT INTO probe VALUES (86)');conn.commit()
  elif engine=='mysql':cur.execute('USE fixture')
  cur.execute('SELECT value FROM probe ORDER BY value');out[engine]=hashlib.sha256(json.dumps(cur.fetchall()).encode()).hexdigest()
 conn.close()
(root/('auth-'+sys.argv[2]+'.json')).write_text(json.dumps(out))
''')
    def authcheck(mode):
        result=run(['podman','exec','megasamples-upgrade-tools','.venv/bin/python',str(auth),str(out),mode],check=False)
        (out/('auth-'+mode+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==0,'authentication assertion failed; private log retained'
        return json.loads((out/('auth-'+mode+'.json')).read_text())
    try:
        assert not (ENV/'podman.sock').is_socket()
        api_env=dict(os.environ,CONTAINERS_CONF_OVERRIDE=str(ROOT/'build/upgrade-evidence/containers-slirp.conf'))
        with (out/'api.log').open('w') as log:api=subprocess.Popen(['podman','system','service','--time=0',os.environ['DOCKER_HOST']],env=api_env,stdout=log,stderr=log)
        for _ in range(100):
            if (ENV/'podman.sock').is_socket():break
            assert api.poll() is None;time.sleep(.05)
        comp('create')
        for engine,destination in (('postgres','/var/lib/postgresql'),('mysql','/var/lib/mysql'),('sqlite','/data')):
            mounted=next(row for row in json.loads(pod('inspect','-f','{{json .Mounts}}',project+'-'+engine)) if row['Destination']==destination)
            anonymous_volumes.append(mounted['Name'])
            data[engine]=Path(mounted['Source'])
            # Only our newly allocated, never-started anonymous data volume.
            # Explicitly empty it: the image carries sample data, and this API
            # route did not yield fresh data with Compose's nocopy alone.
            assert pod('volume','inspect','-f','{{.Anonymous}}',mounted['Name'])=='true'
            pod('unshare','sh','-c','find "$1" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +','owned-scratch',str(data[engine]))
            pod('unshare','chmod','755',str(data[engine]))
            pod('unshare','touch',str(data[engine]/'.scratch-empty'))
            print(engine,'owned anonymous volume before start',pod('volume','inspect','-f','{{.NeedsCopyUp}}|{{.MountCount}}',mounted['Name']),flush=True)
        pod('unshare','cp','-a',str(out/'sqlite')+'/.',str(data['sqlite'])+'/')
        pod('unshare','chmod','755',str(data['sqlite']))
        comp('up','-d')
        # The proof must match candidate anonymous engine data volumes.
        for engine,destination in (('postgres','/var/lib/postgresql'),('mysql','/var/lib/mysql'),('sqlite','/data')):
            mounts=json.loads(pod('inspect','-f','{{json .Mounts}}',project+'-'+engine))
            mounted=next(row for row in mounts if row['Destination']==destination)
            assert mounted['Type']=='volume',engine+' proof data must use an anonymous volume'
            assert pod('volume','inspect','-f','{{.Anonymous}}',mounted['Name'])=='true'
        for engine in ('postgres','mysql','sqlite'):
            deadline=time.monotonic()+180
            while True:
                result=run(['podman','healthcheck','run',project+'-'+engine],check=False)
                if result.returncode==0:break
                assert time.monotonic()<deadline,'scratch health deadline: '+engine
                time.sleep(1)
            u.wait_healthy(engine,30)
        print('scratch data before auth',pod('unshare','sh','-c','test -f "$1/18/docker/PG_VERSION" && echo initialized','owned-scratch',str(data['postgres'])),flush=True)
        fingerprints=authcheck('init');sqlite_digest=hashlib.sha256((data['sqlite']/'fixture.sqlite').read_bytes()).hexdigest()
        names=[project+'-'+name for name in ('postgres','mysql','sqlite','landing')]
        original_ids={name:pod('inspect','-f','{{.Id}}',name) for name in names}
        mounts={name:pod('inspect','-f','{{range .Mounts}}{{.Source}}|{{.Destination}}{{"\\n"}}{{end}}',name) for name in names}
        u.snapshot(backup/'original-stop.json',project,names[:3],phase='original-stop')
        record=g.capture(backup/'original-stop.json',backup/'original-capture.json',data_only=True)
        assert record['outcome']=='PASS',record
        comp('stop','-t','10')
        u.exited(backup/'original-stop.json',out/'original-stopped.json',phase='original-stop')
        report=g.verify(backup/'original-capture.json');assert report['outcome']=='PASS',n.summary(report)
        # Execute the cutover's cold-copy shape on only this scratch project's mounts.
        sources={name:str(data[name]) for name in ('postgres','mysql','sqlite')}
        sources['sqlite-shared']=pod('volume','inspect','-f','{{.Mountpoint}}',project+'-shared')
        for name,source in sources.items():pod('unshare','cp','-a',source+'/.',str(backup/name)+'/')
        write_env(rotated)
        for path in Path(sources['sqlite-shared']).iterdir():path.unlink()
        assert not list(Path(sources['sqlite-shared']).iterdir())
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',ports['landing']));listener.listen()
            result=run(['python3',str(helper),'ports','--port-config',str(attempt/'original-ports.json')],check=False)
            assert result.returncode!=0 and 'occupied or unavailable port' in result.stderr
            receipt['results']['rotation-port-refusal']=dict(status='Passed',ports=1)
            text=(ROOT/'docs/live-upgrade-runbook.md').read_text()
            functions='\n'.join(re.search(r'^'+name+r'\(\) \{\n.*?^\}$(?=\n)',text,re.M|re.S)[0] for name in ('ms_tool','save_context','stop_project'))
            functions=functions.replace('sql-megasamples',project)
            functions=functions.replace("'unset CONTAINERS_STORAGE_CONF CONTAINERS_CONF CONTAINERS_CONF_OVERRIDE'",shlex.quote('. '+str(ENV/'env.sh')))
            variables=re.search(r'  declare -p (.*?)\n  printf',functions,re.S)[1].replace('\\\n','').split()
            values={key:'fixture' for key in variables}
            values.update(BACKUP_DIR=str(backup),ATTEMPT_DIR=str(attempt),EVIDENCE_DIR=str(attempt),CONFIG_DIR=str(configdir),UPGRADE_HELPER=str(helper),CONTEXT_FILE=str(attempt/'context.bash'),DOCKER_HOST=os.environ['DOCKER_HOST'],XDG_RUNTIME_DIR=os.environ['XDG_RUNTIME_DIR'],TEARDOWN_PHASE='rollback-stop')
            context='\n'.join(k+'='+shlex.quote(v) for k,v in values.items())+'\n'+functions+'\nsave_context\n'
            subprocess.run(['bash','-eu','-c',context],cwd=checkout,check=True)
            fragment=text.split('# BEGIN rollback route dispatch\n',1)[1].split('# END rollback route dispatch',1)[0].replace('sql-megasamples',project)
            shell='. "$1"; test "$CONTAINERS_STORAGE_CONF" = "$2"; . "$3"; '+fragment
            # Documented second-shell fallback: execute actual configured probes,
            # never edit health state. This host does not reliably schedule them.
            health_stop=threading.Event()
            def manual_probes():
                while not health_stop.wait(1):
                    for engine in ('postgres','mysql','sqlite'):
                        run(['podman','healthcheck','run',project+'-'+engine],check=False,timeout=15)
            health_thread=threading.Thread(target=manual_probes,daemon=True);health_thread.start()
            try:
                result=run(['bash','-eu','-c',shell,'fresh-original',str(ENV/'env.sh'),str(ENV/'storage.conf'),str(attempt/'context.bash')],check=False,timeout=180)
            finally:
                health_stop.set();health_thread.join(timeout=20)
            receipt['manual_health_fallback']='Configured probes executed from separate native process; no health state edited'
            (out/'actual-runbook-original.log').write_text(result.stdout+result.stderr)
            assert result.returncode==0,'runbook original restart failed; private log retained'
            assert (attempt/'original-consoles-held.txt').read_text()=='landing\n'
            assert pod('inspect','-f','{{.State.Running}}',project+'-landing')=='false'
        assert hashlib.sha256(envpath.read_bytes()).digest()==hashlib.sha256((configdir/'.env').read_bytes()).digest()
        assert authcheck('accept')==fingerprints
        # Test the rotated credential set, then restore the retained file privately.
        write_env(rotated);authcheck('refuse');shutil.copyfile(configdir/'.env',envpath)
        assert hashlib.sha256((data['sqlite']/'fixture.sqlite').read_bytes()).hexdigest()==sqlite_digest
        assert hashlib.sha256((Path(sources['sqlite-shared'])/'fixture.sqlite').read_bytes()).hexdigest()==sqlite_digest
        assert (Path(sources['sqlite-shared'])/'.complete').exists()
        assert original_ids=={name:pod('inspect','-f','{{.Id}}',name) for name in names}
        assert mounts=={name:pod('inspect','-f','{{range .Mounts}}{{.Source}}|{{.Destination}}{{"\\n"}}{{end}}',name) for name in names}
        receipt['results']['exact-original-restart-fresh-shell']=dict(status='Passed',containers=4,engines_healthy=3,consoles_held=1,ids_unchanged=True,mounts_unchanged=True,sql_fingerprints_unchanged=True,sqlite_fingerprint_unchanged=True,shared_rebuilt=True,original_credentials_accepted=True,rotated_credentials_refused=True,env_digest_restored=True)
        save();print('exact-original-restart-fresh-shell Passed',flush=True)
        def must_refuse(name):
            try: g.original_eligible(backup/'original-stop.json',project)
            except ValueError as error:
                assert 'original restart' in str(error)
                receipt['results'][name]=dict(status='Passed',outcome='REFUSE',reason_class='exact original restart eligibility')
            else: raise AssertionError(name+' unexpectedly allowed')
        must_refuse('original-restart-refuses-running')
        comp('stop','-t','10')
        g.original_eligible(backup/'original-stop.json',project)
        extra=project+'-extra'
        pod('run','-d','--pull=never','--name',extra,'--label','com.docker.compose.project='+project,
            '--network','none','--entrypoint','sleep','sha256:'+images['landing'],'120')
        must_refuse('original-restart-refuses-candidate-present')
        pod('stop','-t','2',extra);pod('rm',extra)
        g.original_eligible(backup/'original-stop.json',project)
        comp('rm','-f','landing');must_refuse('original-restart-refuses-missing-ID')
        comp('create','landing');must_refuse('original-restart-refuses-replaced-ID')
        # Ordinary rollback begins with the scratch project running, including
        # the recreated console, all with the configured restart policy.
        comp('up','-d')
        for engine in ('postgres','mysql','sqlite'):
            deadline=time.monotonic()+60
            while run(['podman','healthcheck','run',project+'-'+engine],check=False).returncode:
                assert time.monotonic()<deadline,'recreated scratch health deadline: '+engine
                time.sleep(1)
            u.wait_healthy(engine,30)
        replica.prove(n,g,u,out,backup,attempt,project,compose,sources,receipt)
        save()
    finally:
        try:
            comp('down','-v','--remove-orphans','-t','10')
            for engine in ('postgres','mysql','sqlite','sqlite-shared'):
                replica_attempt=receipt.get('replica',{}).get('attempt','replica')
                volume=project+'-rollback-'+engine+'-'+replica_attempt
                if n.run(['podman','volume','exists',volume],check=False).returncode==0:
                    assert pod('volume','inspect','-f','{{index .Labels "dl086.rollback-attempt"}}',volume)==replica_attempt
                    pod('volume','rm',volume)
            for volume in anonymous_volumes:
                if run(['podman','volume','exists',volume],check=False).returncode==0:
                    assert pod('volume','inspect','-f','{{.Anonymous}}|{{.MountCount}}',volume)=='true|0'
                    pod('volume','rm',volume)
            assert not pod('ps','-aq','--filter','label=com.docker.compose.project='+project)
            assert not pod('network','ls','-q','--filter','label=com.docker.compose.project='+project)
            assert not pod('volume','ls','-q','--filter','label=com.docker.compose.project='+project)
            assert before==inventory()
            receipt['cleanup']=dict(status='Passed',containers=0,networks=0,volumes=0,isolated_unchanged=True)
        finally:
            if api is not None:api.terminate();api.wait(timeout=10)
            save();print('private receipt',out.relative_to(ROOT)/'receipt.json',flush=True)


if __name__=='__main__':main()
