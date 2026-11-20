#!/usr/bin/env python3
"""Native DL-088 lifecycle in a fresh, guarded rootless scratch store.

Source the isolated env.sh first. No existing stack is mutated. Receipts contain
counts/classes only. Raw private evidence is mode 0600 beneath a 0700 directory.
No process arguments/environments are inspected. No host software is installed.
"""
import collections
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
ENV=ROOT.parent/'sql-megasamples-upgrade-env'
SPEC=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('quiescence.py'))
gate=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(gate)
SPEC=importlib.util.spec_from_file_location('upgrade',Path(__file__).with_name('live-upgrade.py'))
upgrade=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(upgrade)


def run(args,env,check=True,timeout=40):
    result=subprocess.run(args,env=env,text=True,capture_output=True,timeout=timeout)
    if check and result.returncode:
        raise subprocess.CalledProcessError(result.returncode,args,output=result.stdout,stderr=result.stderr)
    return result


def summary(report):
    return dict(outcome=report['outcome'],counts=report['counts'],
                refusals=dict(collections.Counter(r['reason'] for r in report['refusals'])),
                holds=dict(collections.Counter(r['reason'] for r in report['holds'])),
                limitations=dict(collections.Counter(r['operation'] for r in report['limitations'])),
                shared_consumers=len(report['shared_consumers']))


def main():
    os.umask(0o077)
    assert Path.cwd()==ROOT
    assert os.environ.get('CONTAINERS_STORAGE_CONF')==str(ENV/'storage.conf')
    assert os.environ.get('DOCKER_HOST')=='unix://'+str(ENV/'podman.sock')
    isolated=dict(os.environ)
    def original(*args):return run(['podman',*args],isolated).stdout.strip()
    assert original('info','--format','{{.Store.GraphRoot}}')==str(ENV/'graph')
    baseline=[line.split('|')[0] for line in (ROOT/'build/dl086/dl088/isolated-before.txt').read_text().splitlines()]
    before=original('inspect','-f','{{.Id}}|{{.Image}}|{{.State.Status}}',*baseline)
    out=Path(tempfile.mkdtemp(prefix='q088-',dir=ROOT/'build'));out.chmod(0o700)
    receipt=dict(at=datetime.now(timezone.utc).isoformat(),results={},unsupported={})
    image=original('inspect','-f','{{.Image}}','megasamples-landing')
    size=int(original('image','inspect','-f','{{.Size}}',image))
    assert shutil.disk_usage(out).free > size*4+100_000_000
    original('save','--format=docker-archive','-o',str(out/'seed.tar'),image)
    base=out/'store';base.mkdir();(base/'xdg').mkdir(mode=0o700)
    (base/'storage.conf').write_text(f'[storage]\ndriver="overlay"\ngraphroot="{base}/graph"\nrunroot="{base}/run"\n')
    (base/'containers.conf').write_text(f'[engine]\ntmp_dir="{base}/tmp"\n[network]\ndefault_rootless_network_cmd="pasta"\n')
    env=dict(isolated,CONTAINERS_STORAGE_CONF=str(base/'storage.conf'),CONTAINERS_CONF=str(base/'containers.conf'),XDG_RUNTIME_DIR=str(base/'xdg'))
    env.pop('CONTAINERS_CONF_OVERRIDE',None);env.pop('DOCKER_HOST',None)
    def pod(*args):return run(['podman',*args],env).stdout.strip()
    assert pod('info','--format','{{.Store.GraphRoot}}')==str(base/'graph')
    gate.pod=pod;upgrade.pod=pod
    project='dl088-'+out.name
    names=[project+'-a',project+'-b'];consumer=project+'-consumer';owned=[]
    data=out/'data';data.mkdir();(data/'held').write_text('fixture')
    def record(name,report,expected):
        gate.private_write(out/(name+'.json'),report)
        assert report['outcome']==expected,(name,summary(report))
        receipt['results'][name]=dict(status='Passed',**summary(report))
    try:
        pod('load','-i',str(out/'seed.tar'))
        network=True
        try:
            for name in names:
                owned.append(name)
                pod('run','-d','--pull=never','--name',name,'--label','com.docker.compose.project='+project,
                    '--network','bridge','-p','127.0.0.1::8080','-v',str(data)+':/fixture:rw',
                    '--entrypoint','/bin/sh',image,'-c','trap "exit 0" TERM; while :; do sleep 1; done')
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as error:
            network=False
            receipt['unsupported']['published-bridge-lifecycle-and-network-survivors']=dict(status='Unsupported',failure_class=type(error).__name__,stage='scratch published bridge startup',reason='Scratch bridge startup failed or exceeded its command deadline; network-independent cases do not pass this acceptance case')
            (out/'bridge-start-error.txt').write_text((error.stderr or '') if isinstance(error,subprocess.CalledProcessError) else 'scratch bridge startup exceeded command deadline\n')
            for name in owned:run(['podman','rm','-f',name],env,check=False)
            owned.clear()
            pidfile=base/'run/networks/rootless-netns/rootless-netns-conn.pid'
            pid=pidfile.read_text().strip() if pidfile.exists() else ''
            if pid and (Path('/proc')/pid).exists():
                helper=gate.process_identity(Path('/proc')/pid)
                assert gate.helper_names(helper['comm']) and any('/rootless-netns-' in g for g in helper['cgroups'])
                assert gate.process_identity(Path('/proc')/pid)==helper
                import signal
                os.kill(int(pid),signal.SIGTERM)
            # Network-independent native cases remain useful but do not pass case 1.
            for name in names:
                owned.append(name)
                pod('run','-d','--pull=never','--name',name,'--label','com.docker.compose.project='+project,
                    '--network','none','-v',str(data)+':/fixture:rw','--entrypoint','/bin/sh',image,
                    '-c','trap "exit 0" TERM; while :; do sleep 1; done')
        snapshot=out/'before.json';capture=out/'capture.json'
        upgrade.snapshot(snapshot,project,names,phase='candidate-teardown')
        result=gate.capture(snapshot,capture)
        gate.private_write(out/'capture-result.json',result)
        assert result['outcome']=='PASS',result
        saved=json.loads(capture.read_text())
        receipt['results']['capture']=dict(status='Passed',containers=len(saved['containers']),process_classes=dict(collections.Counter(p['role'] for p in saved['processes'])),sources=len(saved['sources']),shared_helper_class=saved['shared_helper']['comm'] if saved['shared_helper'] else 'none: network-independent fallback')
        report=gate.verify(capture);record('recorded-survivors',report,'REFUSE')
        assert 'recorded process survives' in {r['reason'] for r in report['refusals']}
        if network:
            assert 'dedicated helper survives' in {r['reason'] for r in report['refusals']}
            assert 'shared helper without verified consumer' in {r['reason'] for r in report['refusals']}
        pod('exec','-d',names[0],'/bin/sh','-c','exec sleep 180')
        report=gate.verify(capture);record('new-exec-descendant',report,'REFUSE')
        assert 'live deployment cgroup task' in {r['reason'] for r in report['refusals']}
        if network:
            owned.append(consumer)
            pod('run','-d','--pull=never','--name',consumer,'--network','bridge','--entrypoint','sleep',image,'180')
            report=gate.verify(capture);record('shared-helper-with-consumer-and-project-running',report,'REFUSE')
            assert report['shared_consumers'] and 'shared helper without verified consumer' not in {r['reason'] for r in report['refusals']}
        for name in names:pod('stop','--time','2',name)
        # Container removal cannot delete capture; verify with a genuinely fresh interpreter.
        pod('rm',names[0]);owned.remove(names[0]);snapshot.unlink()
        def fresh(name,expected):
            result=run([sys.executable,str(Path(__file__).with_name('quiescence.py')),'verify',str(capture)],env,check=False)
            report=json.loads(result.stdout);record(name,report,expected)
            assert result.returncode=={'PASS':0,'REFUSE':1,'HOLD':2}[expected]
            return report
        report=fresh('partial-removal-fresh-shell','PASS')
        if network:
            assert report['shared_consumers']
            pod('stop','--time','2',consumer)
            fresh('project-stopped-no-other-consumer','PASS')
        # Changed identity holds; retaining the same directory restores the evidence.
        original_data=out/'data-retained';data.rename(original_data);data.mkdir()
        fresh('replaced-source','HOLD')
        data.rmdir();original_data.rename(data)
        fresh('source-restored','PASS')
        # Required evidence unreadable: hide a captured process's stat with a
        # deliberately denied open in the native interpreter, never chmod /proc.
        original_read=Path.read_text
        # The shared helper exited at last stop: use a currently alive recorded
        # process owned by this harness for fault injection, not a native denial.
        probe=dict(saved);probe['processes']=[dict(gate.process_identity(Path('/proc')/str(os.getpid())),role='process')]
        denied_pid=os.getpid()
        def denied(path,*a,**k):
            if path==Path('/proc')/str(denied_pid)/'stat':raise PermissionError('deliberate required inspection denial')
            return original_read(path,*a,**k)
        private=out/'unreadable-capture.json';gate.private_write(private,probe)
        Path.read_text=denied
        try:record('deliberately-unreadable-required-process',gate.verify(private),'HOLD')
        finally:Path.read_text=original_read
        # Cross-filesystem symlink aliases and positive readable descriptor evidence.
        external=Path(tempfile.mkdtemp(prefix='dl088-',dir='/dev/shm'))
        try:
            alias=out/'alias';alias.symlink_to(external,target_is_directory=True)
            source=gate.source_identity(alias)
            assert source['canonical']==str(external) and source['device']!=gate.source_identity(data)['device']
            held=external/'held';held.write_text('fixture')
            holder=subprocess.Popen([sys.executable,'-c','import sys,time; f=open(sys.argv[1]); print("ready",flush=True); time.sleep(120)',str(held)],stdout=subprocess.PIPE,text=True)
            try:
                assert holder.stdout.readline().strip()=='ready'
                probe=dict(saved,sources=[source]);alias_capture=out/'alias-capture.json';gate.private_write(alias_capture,probe)
                report=gate.verify(alias_capture);record('cross-filesystem-alias-holder',report,'REFUSE')
                assert any(r.get('pid')==holder.pid and r['reason']=='recorded data source held' for r in report['refusals'])
            finally:holder.terminate();holder.wait(timeout=10)
            record('cross-filesystem-alias-released',gate.verify(alias_capture),'PASS')
        finally:shutil.rmtree(external)
        # A subordinate UID holds only a descriptor under data. The mount root
        # is its parent, cwd is /, and no mapping or cwd names the recorded source.
        scope=out/'scope';scope.mkdir(mode=0o755);scope.chmod(0o755)
        subdata=scope/'data';subdata.mkdir(mode=0o755);subdata.chmod(0o755)
        (subdata/'held').write_text('fixture');(subdata/'held').chmod(0o644)
        subname=project+'-subuid';subproject=project+'-subuid';owned.append(subname)
        pod('run','-d','--pull=never','--name',subname,'--label','com.docker.compose.project='+subproject,
            '--network','none','--user','101','-v',str(scope)+':/scope:ro','--entrypoint','/bin/sh',image,
            '-c','cd /; exec 3</scope/data/held; exec sleep 180')
        pod('exec','--user','101',subname,'/bin/sh','-c','test -e /proc/1/fd/3')
        sub_snapshot=out/'subuid-before.json';sub_capture=out/'subuid-capture.json'
        upgrade.snapshot(sub_snapshot,subproject,[subname],phase='candidate-teardown')
        result=gate.capture(sub_snapshot,sub_capture,data_only=True,extra_sources=[subdata])
        assert result['outcome']=='PASS',result
        subpid=int(pod('inspect','-f','{{.State.Pid}}',subname))
        assert (Path('/proc')/str(subpid)).stat().st_uid!=os.getuid()
        report=gate.verify(sub_capture)
        assert report['outcome'] in ('REFUSE','HOLD')
        assert any(r['reason']=='required holder inspection unreadable' and r.get('operation')=='fd' and r.get('error')=='PermissionError' for r in report['holds']), report
        record('subordinate-uid-descriptor-only',report,report['outcome'])
        pod('stop','--time','2',subname)
        record('subordinate-uid-holder-stopped',gate.verify(sub_capture),'PASS')
        # Unrelated overlay filesystem uses exactly the host source path text.
        same=project+'-samepath';owned.append(same)
        pod('run','-d','--pull=never','--name',same,'--network','none','--entrypoint','/bin/sh',image,
            '-c','mkdir -p "$1"; cd "$1"; exec sleep 180','fixture',str(data))
        record('same-path-different-filesystem',gate.verify(capture),'PASS')
        pod('stop','--time','2',same)
        # Compile only inside the existing isolated tools container, without
        # installing anything on the host. The native program leaves a zombie
        # leader while its worker remains alive holding the recorded data file.
        program=out/'thread.c';binary=out/'thread'
        program.write_text('''#include <pthread.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
void *worker(void *arg) { int fd=open((char*)arg,O_RDONLY); if(fd<0) _exit(3); puts("ready"); fflush(stdout); sleep(120); close(fd); return 0; }
int main(int argc,char **argv) { pthread_t t; if(pthread_create(&t,0,worker,argv[1])) return 4; pthread_exit(0); }
''')
        compile_result=run(['podman','exec','megasamples-upgrade-tools','cc','-pthread',str(program),'-o',str(binary)],isolated,check=False)
        if compile_result.returncode:
            receipt['unsupported']['zombie-leader-live-thread']='Compiler in tools container could not build native pthread fixture'
        else:
            zombie=subprocess.Popen([str(binary),str(data/'held')],stdout=subprocess.PIPE,text=True)
            try:
                assert zombie.stdout.readline().strip()=='ready'
                proc=Path('/proc')/str(zombie.pid)
                for _ in range(50):
                    if (proc/'stat').read_text().rsplit(') ',1)[1].split()[0]=='Z':break
                    time.sleep(.02)
                assert (proc/'stat').read_text().rsplit(') ',1)[1].split()[0]=='Z'
                probe=dict(saved,processes=[dict(gate.process_identity(proc),role='process')])
                zcapture=out/'zombie-capture.json';gate.private_write(zcapture,probe)
                report=gate.verify(zcapture);record('zombie-leader-live-thread',report,'REFUSE')
                assert 'recorded process survives' in {r['reason'] for r in report['refusals']}
            finally:zombie.terminate();zombie.wait(timeout=10)
            record('zombie-thread-ended',gate.verify(zcapture),'PASS')

    finally:
        for name in reversed(owned):run(['podman','rm','-f',name],env,check=False)
        assert not pod('ps','-aq')
        assert Path(pod('info','--format','{{.Store.GraphRoot}}')).is_relative_to(out)
        pod('rmi','--all','--force')
        pause=base/'xdg/libpod/tmp/pause.pid'
        pause_pid=int(pause.read_text()) if pause.exists() else None
        pod('system','migrate')
        if pause_pid:
            assert not Path('/proc',str(pause_pid)).exists() or not gate.task_alive(Path('/proc')/str(pause_pid))
        after=original('inspect','-f','{{.Id}}|{{.Image}}|{{.State.Status}}',*baseline)
        receipt['isolation_unchanged']=sorted(before.splitlines())==sorted(after.splitlines())
        gate.private_write(out/'receipt.json',receipt)
        assert receipt['isolation_unchanged']
        print(json.dumps(dict(artifacts=str(out.relative_to(ROOT)),receipt=receipt),indent=2))

if __name__=='__main__':main()
