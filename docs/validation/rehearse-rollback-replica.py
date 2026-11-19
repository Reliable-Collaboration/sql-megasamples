#!/usr/bin/env python3
"""Structure-faithful populated backup proof; invoked by original-restart rehearsal.

Only owned scratch engine mounts are copied. The retained backup contributes
names/modes/owners only, audited separately; none of its contents are read here.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[2]
ENV=ROOT.parent/'sql-megasamples-upgrade-env'


def populate_names(backup):
    names=json.loads((ROOT/'tests/fixtures/live-upgrade/retained-root-names.json').read_text())
    for name in names:
        target=backup/name.rstrip('/')
        if name.endswith('/'):target.mkdir(exist_ok=True)
        elif not target.exists():target.touch()


def prove(n,g,u,out,backup,attempt,project,compose,sources,receipt):
    assert os.environ['CONTAINERS_STORAGE_CONF']==str(ENV/'storage.conf')
    assert n.pod('info','--format','{{.Store.GraphRoot}}')==str(ENV/'graph')
    assert attempt.parent==backup and attempt.name.startswith('rollback-')
    # Repeat the runbook's own cold-copy command from stopped scratch engines.
    for name,source in sources.items():n.pod('unshare','cp','-a',source+'/.',str(backup/name)+'/')
    unreadable=[]
    for name in ('postgres','mysql'):
        def denied(error):unreadable.append(dict(engine=name,error=type(error).__name__))
        for _ in os.walk(backup/name,onerror=denied):pass
    assert unreadable and any(r['engine']=='postgres' for r in unreadable)
    pg=(backup/'postgres/fixture').stat()
    assert pg.st_mode & 0o777 == 0o700 and pg.st_uid != os.getuid()
    receipt['replica']=dict(top_level_names='tests/fixtures/live-upgrade/retained-root-names.json',
        attempt_under_backup=True,cold_copy='podman unshare cp -a from stopped scratch PostgreSQL, MySQL, SQLite and shared mounts',
        unreadable_cold_directories=len(unreadable),unreadable_classes=sorted({r['error'] for r in unreadable}),postgres_data_mode='0700',postgres_data_subordinate_owner=True)
    text=(ROOT/'docs/live-upgrade-runbook.md').read_text()
    def block(start,end):return text.split(start+'\n',1)[1].split(end,1)[0]
    def adapt(fragment):
        return fragment.replace('sql-megasamples',project).replace('megasamples-',project+'-').replace('-f compose.yaml','-f '+shlex.quote(str(compose)))
    context=attempt/'context.bash'
    # Existing context comes from the runbook save_context function, namespace
    # adapted by the caller. Update only the phase/attempt and copied helpers.
    start='. "$1"; test "$CONTAINERS_STORAGE_CONF" = "$2"; . "$3"; '
    start+='TEARDOWN_PHASE=rollback-stop; TEARDOWN_ATTEMPT=replica; EVIDENCE_DIR="$ATTEMPT_DIR"; '
    def shell(label,fragment):
        result=subprocess.run(['bash','-eu','-c',start+adapt(fragment),'replica',str(ENV/'env.sh'),str(ENV/'storage.conf'),str(context)],
            cwd=compose.parent,env=dict(os.environ,PROJECT=project,COMPOSE_FILE=str(compose)),text=True,capture_output=True,timeout=180)
        (out/(label+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==0,(label,result.stderr[-1000:])
        print(label,'Passed',flush=True)
    # Policy changes are confined to scratch IDs, checked before/after both blocks.
    shell('restart-policy-pause',block('# BEGIN pause restart automation','# END pause restart automation'))
    ids=n.pod('ps','-aq','--filter','label=com.docker.compose.project='+project).split()
    assert all(n.pod('inspect','-f','{{.HostConfig.RestartPolicy.Name}}',i)=='no' for i in ids)
    shell('restart-policy-restore',block('# BEGIN restore restart automation','# END restore restart automation'))
    assert all(n.pod('inspect','-f','{{.HostConfig.RestartPolicy.Name}}',i)=='unless-stopped' for i in ids)
    (attempt/'quiescence.py').write_bytes((ROOT/'docs/validation/quiescence.py').read_bytes())
    fragment=block('# Stop candidates BEFORE down can remove evidence. Keep every failed candidate volume.','# END restore process gate')
    shell('replica-fresh-shell-rollback-restore-gate',fragment)
    # Red control on this same populated layout, using the reviewed old helper.
    old=attempt/'history-before.py'
    old.write_text(subprocess.check_output(['git','show','e161d921:docs/validation/quiescence.py'],cwd=ROOT,text=True))
    captures=list(attempt.glob('rollback-stop-capture-*.json'));assert len(captures)==1
    red=n.run(['python3',str(old),'verify',str(captures[0]),'--history-dir',str(backup)],check=False)
    report=json.loads(red.stdout)
    assert red.returncode==2 and any(r['reason']=='capture history inspection unreadable' for r in report['holds'])
    (out/'replica-history-red.json').write_text(json.dumps(n.summary(report),indent=2)+'\n')
    receipt['results']['replica-old-history-red']=dict(status='Passed',control='Old helper HOLDs on unreadable cold payload',**n.summary(report))
    # Saved context from the actual down block carries its capture/snapshot.
    shell('replica-fresh-shell-populate-gate',block('# BEGIN rollback population','# END rollback population'))
    def tree_digest(path):
        command=['podman','unshare','tar','--sort=name','--numeric-owner','--format=gnu','--atime-preserve=system','-C',str(path),'-cf','-','.']
        digest=hashlib.sha256()
        with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
            for chunk in iter(lambda:process.stdout.read(1024*1024),b''):digest.update(chunk)
            error=process.stderr.read();assert process.wait(timeout=30)==0,error.decode()[-500:]
        return digest.hexdigest()
    for engine in sources:
        target=n.pod('volume','inspect','-f','{{.Mountpoint}}',project+'-rollback-'+engine+'-replica')
        assert tree_digest(backup/engine)==tree_digest(target),engine+' restoration differs'
    receipt['results']['replica-population-content']=dict(status='Passed',trees=len(sources),numeric_ownership_modes_and_bytes_equal=True)
    shell('replica-fresh-shell-pre-up-gate',block('# BEGIN pre-up checkpoint','# END pre-up process gate'))
    for label,pattern in [('restore','process-restore-*.json'),('populate','populate-process-*.json'),('pre-up','process-pre-up-*.json')]:
        reports=list(attempt.glob(pattern));assert len(reports)==1,(label,reports)
        report=json.loads(reports[0].read_text());assert report['outcome']=='PASS',n.summary(report)
        assert report['history'],label+' must verify earlier capture history'
        receipt['results']['replica-'+label]=dict(status='Passed',**n.summary(report),history_records=len(report['history']))
    receipt['results']['native-restart-policy']=dict(status='Passed',containers=len(ids),pause='no',restore='unless-stopped')
