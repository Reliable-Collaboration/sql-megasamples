#!/usr/bin/env python3
"""DL-089 case five, native scratch project in the isolated store.

Executes the runbook's actual guarded stop/down/process-gate block in fresh Bash,
with project/container names mapped to the scratch namespace. Does not execute
cold restoration; the exact-original restart route has a separate rehearsal.
No live mutation, arguments/environments inspection or shared-helper signals.
"""
import collections
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
ENV=ROOT.parent/'sql-megasamples-upgrade-env'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


gate=module('down_gate',Path(__file__).with_name('quiescence.py'))
upgrade=module('down_upgrade',Path(__file__).with_name('live-upgrade.py'))


def run(args,check=True,timeout=60):
    return subprocess.run(args,text=True,capture_output=True,check=check,timeout=timeout)


def pod(*args,timeout=60):return run(['podman',*args],timeout=timeout).stdout.strip()


def summary(report):
    return dict(outcome=report['outcome'], assurance=report.get('assurance'),
                refusals=dict(collections.Counter(r['reason'] for r in report.get('refusals',[]))),
                holds=dict(collections.Counter(r['reason'] for r in report.get('holds',[]))),
                counts=report.get('counts',{}),shared_consumers=len(report.get('shared_consumers',[])))


def main():
    os.umask(0o077)
    assert Path.cwd()==ROOT
    assert os.environ.get('CONTAINERS_STORAGE_CONF')==str(ENV/'storage.conf')
    assert os.environ.get('DOCKER_HOST')=='unix://'+str(ENV/'podman.sock')
    assert pod('info','--format','{{.Store.GraphRoot}}')==str(ENV/'graph')
    def inventory():
        names=pod('ps','-a','--format','{{.Names}}').splitlines()
        return sorted(pod('inspect','-f','{{.Name}}|{{.Id}}|{{.Image}}|{{.State.Status}}|{{.State.StartedAt}}',*names).splitlines())
    before=inventory();assert len(before)==12
    out=Path(tempfile.mkdtemp(prefix='dl089-proof-',dir=ROOT/'build'))
    project=out.name; receipt=dict(at=datetime.now(timezone.utc).isoformat(),results={},artifacts=str(out.relative_to(ROOT)))
    data=out/'data';data.mkdir();(data/'held').write_text('scratch fixture\n')
    config=out/'compose.json'
    image=pod('inspect','-f','{{.Image}}','megasamples-landing')
    receipt['image_id']=image
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    config.write_text(json.dumps(dict(services={name:dict(image='sha256:'+image.removeprefix('sha256:'),pull_policy='never',
        entrypoint=['sh','-c','trap "exit 0" TERM; while :; do sleep 1; done'],
        volumes=[str(data)+':/fixture','scratch:/scratch'],
        **({'ports':[f'127.0.0.1:{port}:8080']} if name=='a' else {})) for name in ('a','b')},volumes={'scratch':{}})))
    api=None;holder=None
    gate.pod=pod;upgrade.pod=pod
    def compose(*args):return run(['docker','compose','-p',project,'-f',str(config),*args],timeout=90)
    def record(name,report,expected):
        receipt['results'][name]=dict(status='Passed' if report['outcome']==expected else 'Failed',**summary(report))
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        assert report['outcome']==expected,(name,summary(report))
        print(name,report['outcome'],flush=True)
    def capture(name,phase='candidate-teardown'):
        snap=out/(name+'-before.json');cap=out/(name+'-capture.json')
        names=pod('ps','-a','--format','{{.Names}}','--filter','label=com.docker.compose.project='+project).splitlines()
        upgrade.snapshot(snap,project,names or [project+'-removed'],phase=phase)
        result=gate.capture(snap,cap,allow_down=True,data_only=False)
        receipt.setdefault('capture_attempts',{})[name]=[summary(result)]
        return snap,cap,result
    def verify(name,cap,expected):
        result=run(['bash','-eu','-c','. "$1"; test "$CONTAINERS_STORAGE_CONF" = "$2"; exec python3 "$3" verify "$4"',
            'fresh',str(ENV/'env.sh'),str(ENV/'storage.conf'),str(Path(__file__).with_name('quiescence.py')),str(cap)],check=False)
        report=json.loads(result.stdout);record(name,report,expected);return report
    try:
        if not (ENV/'podman.sock').is_socket():
            api_env=dict(os.environ,CONTAINERS_CONF_OVERRIDE=str(ROOT/'build/upgrade-evidence/containers-slirp.conf'))
            log=(out/'api.log').open('w')
            api=subprocess.Popen(['podman','system','service','--time=0',os.environ['DOCKER_HOST']],env=api_env,stdout=log,stderr=log)
            for _ in range(100):
                if (ENV/'podman.sock').is_socket():break
                assert api.poll() is None;time.sleep(.05)
        compose('up','-d')
        # A mixed running/exited project requires per-container down evidence.
        compose('stop','-t','2','b')
        snap,cap,result=capture('mixed');record('mixed-capture',result,'PASS')
        assert json.loads(cap.read_text())['down_evidence']
        compose('stop','-t','2','a');verify('mixed-stopped',cap,'PASS')
        snap,cap,result=capture('all-down');record('all-down-capture',result,'PASS')
        report=verify('all-down-same-boot',cap,'PASS')
        assert 'outside the identified cgroups' in report['assurance']
        assert report['shared_consumers']
        _,_,result=capture('original-stop-all-down',phase='original-stop')
        record('original-stop-all-down',result,'HOLD')
        holder=subprocess.Popen([sys.executable,'-c','import sys,time; f=open(sys.argv[1]); print("ready",flush=True); time.sleep(120)',str(data/'held')],stdout=subprocess.PIPE,text=True)
        assert holder.stdout.readline().strip()=='ready'
        report=verify('down-cold-directory-holder',cap,'REFUSE')
        assert any(r['reason']=='recorded data source held' and r.get('pid')==holder.pid for r in report['refusals'])
        holder.terminate();holder.wait(timeout=10);holder=None
        verify('down-holder-released',cap,'PASS')
        compose('start','a');verify('started-after-capture',cap,'REFUSE');compose('stop','-t','2','a')
        verify('started-then-stopped',cap,'PASS')
        # Full-down lifecycle only. The populated cold-backup Roll back gates
        # belong to rehearse-original-restart.py + rehearse-rollback-replica.py;
        # empty cold-copy directories cannot prove that composition.
        compose('down')
        # Verification after a full down retains prior running-generation evidence.
        verify('ordinary-capture-after-full-down',out/'mixed-capture.json','PASS')
        verify('down-capture-after-full-down',out/'all-down-capture.json','PASS')
        # Actual created/exited codes and one removed container in another cycle.
        compose('create');snap,created,result=capture('created');record('created-capture',result,'PASS')
        verify('created-verification',created,'PASS')
        for code in (0,137,23):
            case=json.loads(config.read_text())
            for service in case['services'].values():service['entrypoint']=['sh','-c','exit '+str(code)]
            config.write_text(json.dumps(case));compose('up','-d','--force-recreate')
            time.sleep(1)
            snap,cap,result=capture('exit-'+str(code));record('exit-'+str(code)+'-capture',result,'PASS')
            verify('exit-'+str(code)+'-verification',cap,'PASS')
        compose('rm','-f','a');verify('one-container-removed',cap,'PASS')
        for name,reason in [('oom-killed','A real OOM was not induced; fixture and rule reversal cover OOM state eligibility.'),
                            ('exited-cgroup-live-task','Retaining a live task in a container cgroup after its native exited state was not safely arranged.'),
                            ('reboot','Requires a separately approved disposable host; both running stacks must remain unchanged.'),
                            ('shared-helper-zero-consumers','The unchanged isolated stack consumes this store helper; a second scratch project cannot remove its consumers.')]:
            receipt['results'][name]=dict(status='Unsupported',reason=reason)
    finally:
        if holder is not None:holder.terminate();holder.wait(timeout=10)
        try:
            compose('down','-v','--remove-orphans','-t','2')
            assert not pod('ps','-aq','--filter','label=com.docker.compose.project='+project)
            assert not pod('network','ls','-q','--filter','label=com.docker.compose.project='+project)
            assert not pod('volume','ls','-q','--filter','label=com.docker.compose.project='+project)
            after=inventory();assert before==after
            receipt['cleanup']=dict(status='Passed',containers=0,networks=0,volumes=0,isolated_containers=len(after),unchanged=True)
        finally:
            if api is not None:api.terminate();api.wait(timeout=10)
            (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
            print('private receipt',out.relative_to(ROOT)/'receipt.json',flush=True)


if __name__=='__main__':main()
