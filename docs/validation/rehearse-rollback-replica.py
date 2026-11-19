#!/usr/bin/env python3
"""Structure-faithful populated backup proof; invoked by original-restart rehearsal.

Only owned scratch engine mounts are copied. The retained backup contributes
names/modes/owners only, audited separately; none of its contents are read here.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
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
    # This proof must exercise the route a running deployment takes today.
    assert g.rollback_route(backup/'original-stop.json',project)['route']=='ordinary-capture'
    ids=n.pod('ps','-aq','--filter','label=com.docker.compose.project='+project).split()
    assert len(ids)==4
    assert all(n.pod('inspect','-f','{{.State.Running}}|{{.HostConfig.RestartPolicy.Name}}',i)=='true|unless-stopped' for i in ids)
    # Create a genuinely new attempt and context; subsequent fresh shells use
    # only the saved context, without injecting phase/attempt/evidence variables.
    prior_attempt=attempt
    attempt_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    attempt=backup/('rollback-'+attempt_id);attempt.mkdir(mode=0o700)
    receipt['replica']=dict(attempt=attempt_id)
    shutil.copytree(prior_attempt/'configuration',attempt/'configuration')
    for name in ('original-ports.json','live-upgrade.py','quiescence.py'):
        shutil.copyfile(prior_attempt/name,attempt/name)
    # The caller already cold-copied these four sources while stopped, using
    # the runbook's unshare cp -a command. Never recopy a running source here.
    # The real metadata audit records both cold roots as subordinate UID/GID
    # 100998, mode 1777. UID/GID 999 maps there in this isolated user namespace.
    for name in ('postgres','mysql'):
        n.pod('unshare','chown','999:999',str(backup/name))
        n.pod('unshare','chmod','1777',str(backup/name))
        root=(backup/name).stat()
        assert root.st_uid==100998 and root.st_gid==100998 and root.st_mode & 0o7777==0o1777
    unreadable=[]
    for name in ('postgres','mysql'):
        def denied(error):unreadable.append(dict(engine=name,error=type(error).__name__))
        for _ in os.walk(backup/name,onerror=denied):pass
    assert unreadable and any(r['engine']=='postgres' for r in unreadable)
    pg=(backup/'postgres/18/docker').stat()
    assert pg.st_mode & 0o777 == 0o700 and pg.st_uid != os.getuid()
    receipt['replica'].update(dict(root_metadata=dict(uid=100998,gid=100998,mode='1777'),top_level_names='tests/fixtures/live-upgrade/retained-root-names.json',
        attempt_under_backup=True,cold_copy='podman unshare cp -a from stopped scratch PostgreSQL, MySQL, SQLite and shared mounts',
        unreadable_cold_directories=len(unreadable),unreadable_classes=sorted({r['error'] for r in unreadable}),postgres_data_mode='0700',postgres_data_subordinate_owner=True,
        differences=['Tiny fresh scratch data, fewer unreadable directories; MySQL internal UID/depth differs',
                     'Non-data retained names include placeholders; smaller deployment and different bridge ports',
                     'No full bootstrap, configuration/image restore or live restoration']) )
    text=(ROOT/'docs/live-upgrade-runbook.md').read_text()
    def block(start,end):return text.split(start+'\n',1)[1].split(end,1)[0]
    def adapt(fragment):
        return fragment.replace('sql-megasamples',project).replace('megasamples-',project+'-').replace('-f compose.yaml','-f '+shlex.quote(str(compose)))
    context=attempt/'context.bash'
    # Existing context comes from the runbook save_context function, namespace
    # adapted by the caller. Update only the phase/attempt and copied helpers.
    start='. "$1"; test "$CONTAINERS_STORAGE_CONF" = "$2"; . "$3"; '
    setup=start+'ATTEMPT_DIR="$4"; EVIDENCE_DIR="$ATTEMPT_DIR"; CONFIG_DIR="$ATTEMPT_DIR/configuration"; CONTEXT_FILE="$ATTEMPT_DIR/context.bash"; UPGRADE_HELPER="$ATTEMPT_DIR/live-upgrade.py"; TEARDOWN_PHASE=; TEARDOWN_ATTEMPT="$5"; save_context'
    subprocess.run(['bash','-eu','-c',setup,'new-attempt',str(ENV/'env.sh'),str(ENV/'storage.conf'),str(prior_attempt/'context.bash'),str(attempt),attempt_id],cwd=compose.parent,check=True)
    def shell(label,fragment):
        result=subprocess.run(['bash','-eu','-c',start+adapt(fragment),'replica',str(ENV/'env.sh'),str(ENV/'storage.conf'),str(context)],
            cwd=compose.parent,env=dict(os.environ,PROJECT=project,COMPOSE_FILE=str(compose)),text=True,capture_output=True,timeout=180)
        (out/(label+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==0,(label,result.stderr[-1000:])
        print(label,'Passed',flush=True)
    shell('replica-ordinary-dispatch',block('# BEGIN rollback route dispatch','# END rollback route dispatch'))
    # Policy changes are confined to scratch IDs, checked before/after both blocks.
    shell('restart-policy-pause',block('# BEGIN pause restart automation','# END pause restart automation'))
    ids=n.pod('ps','-aq','--filter','label=com.docker.compose.project='+project).split()
    assert all(n.pod('inspect','-f','{{.HostConfig.RestartPolicy.Name}}',i)=='no' for i in ids)
    assert all(n.pod('inspect','-f','{{.State.Running}}',i)=='true' for i in ids)
    shell('restart-policy-restore',block('# BEGIN restore restart automation','# END restore restart automation'))
    assert all(n.pod('inspect','-f','{{.HostConfig.RestartPolicy.Name}}',i)=='unless-stopped' for i in ids)
    shell('restart-policy-pause-before-capture',block('# BEGIN pause restart automation','# END pause restart automation'))
    (attempt/'quiescence.py').write_bytes((ROOT/'docs/validation/quiescence.py').read_bytes())
    fragment=block('# Stop candidates BEFORE down can remove evidence. Keep every failed candidate volume.','# END restore process gate')
    shell('replica-fresh-shell-rollback-restore-gate',fragment)
    capture=json.loads(next(attempt.glob('rollback-stop-capture-*.json')).read_text())
    assert capture['kind']=='ordinary' and capture['processes']
    receipt['results']['replica-ordinary-route']=dict(status='Passed',capture_kind=capture['kind'],processes=len(capture['processes']),dispatch='ordinary-capture',fresh_context_without_phase_injection=True)
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
        target=n.pod('volume','inspect','-f','{{.Mountpoint}}',project+'-rollback-'+engine+'-'+attempt_id)
        assert tree_digest(backup/engine)==tree_digest(target),engine+' restoration differs'
    receipt['results']['replica-population-content']=dict(status='Passed',trees=len(sources),numeric_ownership_modes_and_bytes_equal=True)
    shell('replica-fresh-shell-pre-up-gate',block('# BEGIN pre-up checkpoint','# END pre-up process gate'))
    for label,pattern in [('restore','process-restore-*.json'),('populate','populate-process-*.json'),('pre-up','process-pre-up-*.json')]:
        reports=list(attempt.glob(pattern));assert len(reports)==1,(label,reports)
        report=json.loads(reports[0].read_text());assert report['outcome']=='PASS',n.summary(report)
        assert report['history'],label+' must verify earlier capture history'
        receipt['results']['replica-'+label]=dict(status='Passed',**n.summary(report),history_records=len(report['history']))
    receipt['results']['native-restart-policy']=dict(status='Passed',containers=len(ids),initial_running_policy='unless-stopped',pause='no',restore='unless-stopped',paused_again_before_capture=True)
