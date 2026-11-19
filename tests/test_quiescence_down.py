"""DL-089 down evidence and original restart routing, with reason reversals."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from test_quiescence_capture import capture_fixture, process, gate


@pytest.fixture
def down(capture_fixture,monkeypatch):
    snap,out,proc,cg,data=capture_fixture
    for p in list(proc.iterdir()):shutil.rmtree(p)
    for p in cg.iterdir():shutil.rmtree(p)
    saved=json.loads(snap.read_text());saved['phase']='candidate-teardown'
    saved['containers'][0].update(pid=0,running=False,state='exited',exit_code=0,oom=False)
    snap.write_text(json.dumps(saved))
    def pod(*args):
        if args[0]=='ps':return '' if '-q' in args else 'test'
        if args[0]=='container':return ''
        if args[0]=='inspect':
            if args[2]==gate.CAPTURE_FORMAT:return 'test|0|0|none|false|'
            if args[2]=='{{json .HostConfig.PortBindings}}':return '{}'
            return 'test|false|0'
        raise AssertionError(args)
    monkeypatch.setattr(gate,'pod',pod)
    return snap,out,proc,cg,data


@pytest.mark.parametrize('state,code,oom',[('created',0,False),('exited',0,False),('exited',137,False),('exited',23,False),('exited',1,True)])
def test_down_capture_complete_and_reverified(down,state,code,oom):
    snap,out,proc,cg,data=down
    saved=json.loads(snap.read_text());saved['containers'][0].update(state=state,exit_code=code,oom=oom);snap.write_text(json.dumps(saved))
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
    saved=json.loads(out.read_text());assert saved['kind']=='down-state'
    assert saved['down_evidence'][0]['cgroup_state']=='absent'
    report=gate.verify(out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='PASS' and 'outside the identified cgroups' in report['assurance']


def test_original_stop_all_down_still_holds(down):
    snap,out,proc,cg,data=down
    saved=json.loads(snap.read_text());saved['phase']='original-stop';snap.write_text(json.dumps(saved))
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)
    assert report['outcome']=='HOLD'
    assert any(r['reason']=='deployment process capture missing; cannot capture after stop' for r in report['holds'])


@pytest.mark.parametrize('mode',['live-task','unreadable-group','started','conmon','path-helper','port-helper','unreadable-conmon','conmon-identity-contradicted'])
def test_down_live_evidence_blocks_with_reversal(down,monkeypatch,mode):
    snap,out,proc,cg,data=down
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
    original=gate.pod
    reason='live deployment cgroup task';kind='refusals';expected='REFUSE'
    if mode in ('live-task','unreadable-group'):
        directory=cg/'libpod-test.scope';directory.mkdir()
        for name in ('cgroup.procs','cgroup.threads'):(directory/name).write_text('12349' if mode=='live-task' else '')
        if mode=='live-task':process(proc,12349)
        else:
            (directory/'cgroup.threads').unlink();reason='down cgroup evidence unreadable';kind='holds';expected='HOLD'
    elif mode=='started':
        monkeypatch.setattr(gate,'pod',lambda *a:'test|true|12349' if a[0]=='inspect' and a[2]!=gate.CAPTURE_FORMAT else original(*a))
        reason='deployment container running'
    else:
        p=process(proc,12349,'conmon' if 'conmon' in mode else 'rootlessport','/shell')
        reason='positively associated down helper survives'
        if 'conmon' in mode:
            monkeypatch.setattr(gate,'pod',lambda *a:'test|0|12349|none|false|' if a[0]=='inspect' and a[2]==gate.CAPTURE_FORMAT else original(*a))
            if mode=='conmon-identity-contradicted':
                (p/'comm').write_text('reused-process');reason='down helper association unreadable';kind='holds';expected='HOLD'
            if mode=='unreadable-conmon':
                (p/'stat').unlink();reason='down helper association unreadable';kind='holds';expected='HOLD'
        if mode=='path-helper':(p/'cwd').unlink();(p/'cwd').symlink_to('/store/overlay-containers/test/userdata')
        if mode=='port-helper':
            # Captured published host port, then a helper owning its listener inode.
            saved=json.loads(out.read_text());saved['down_evidence'][0]['ports']=[48080];out.write_text(json.dumps(saved))
            (proc/'net').mkdir();(proc/'net/tcp').write_text('header\n 0: 0100007F:BBD0 00000000:0000 0A 0:0 0:0 0 0 0 123\n');(proc/'net/tcp6').write_text('header\n')
            (p/'fd/3').symlink_to('socket:[123]')
    report=gate.verify(out,proc=proc,cgroup_root=cg)
    assert report['outcome']==expected,report
    assert any(r['reason']==reason for r in report[kind]),report
    monkeypatch.setattr(gate,'pod',original)
    for p in list(proc.iterdir()):
        if p.is_dir():shutil.rmtree(p)
    for p in list(cg.iterdir()):shutil.rmtree(p)
    if mode=='port-helper':
        (proc/'net').mkdir()
        for name in ('tcp','tcp6'):(proc/'net'/name).write_text('header\n')
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='PASS'


def test_empty_present_cgroup_and_missing_container_evidence(down,monkeypatch):
    snap,out,proc,cg,data=down
    directory=cg/'libpod-test.scope';directory.mkdir()
    for name in ('cgroup.procs','cgroup.threads'):(directory/name).write_text('')
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
    assert json.loads(out.read_text())['down_evidence'][0]['cgroup_state']=='empty'
    original=gate.pod
    def missing(*args):
        if args[0]=='ps':return ''
        if args[0] in ('inspect','container'):raise subprocess.CalledProcessError(1,args)
        return original(*args)
    monkeypatch.setattr(gate,'pod',missing)
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='PASS'


@pytest.mark.parametrize('change',['none','running','missing','replaced','extra'])
def test_exact_original_restart_eligibility_and_route(down,monkeypatch,change):
    snap,out,proc,cg,data=down
    original=gate.pod
    def pod(*args):
        if args[0]=='ps':
            return {'missing':'','replaced':'other','extra':'test other'}.get(change,'test') if '-aq' in args else ('test' if change=='running' else '')
        return original(*args)
    monkeypatch.setattr(gate,'pod',pod)
    if change=='none':
        assert gate.rollback_route(snap,'project')['route']=='original-restart'
        gate.original_eligible(snap,'project')
    else:
        with pytest.raises(ValueError,match='original restart'):
            gate.original_eligible(snap,'project')
        assert gate.rollback_route(snap,'project')['route']!= 'original-restart'


def test_missing_never_created_container_has_completed_listing_evidence(down,monkeypatch):
    snap,out,proc,cg,data=down
    saved=json.loads(snap.read_text());saved['containers'][0].update(id=None,state='missing');snap.write_text(json.dumps(saved))
    original=gate.pod
    monkeypatch.setattr(gate,'pod',lambda *a:'' if a[0]=='ps' else original(*a))
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)
    assert report['outcome']=='PASS'
    saved=json.loads(out.read_text())
    assert saved['project_listing']==[]
    assert saved['down_evidence'][0]['cgroup_state']=='no retained identifier; missing from completed project listing'
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='PASS'


def test_down_shared_helper_appearing_after_absent_pidfile_is_checked(down,monkeypatch):
    snap,out,proc,cg,data=down
    original=gate.pod
    monkeypatch.setattr(gate,'pod',lambda *a:'test|0|0|bridge|false|' if a[0]=='inspect' and a[2]==gate.CAPTURE_FORMAT else original(*a))
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
    pidfile=Path(gate.store_identity()['run'])/'networks/rootless-netns/rootless-netns-conn.pid';pidfile.parent.mkdir(parents=True)
    pidfile.write_text('12349');process(proc,12349,'pasta.avx2','/rootless-netns-store.scope')
    monkeypatch.setattr(gate,'remaining_consumers',lambda *a:[])
    report=gate.verify(out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='REFUSE'
    assert any(r['reason']=='shared helper without verified consumer' for r in report['refusals'])
    monkeypatch.setattr(gate,'remaining_consumers',lambda *a:['other'])
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='PASS'


def test_down_capture_requires_one_evidence_row_per_container(down):
    snap,out,proc,cg,data=down
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
    saved=json.loads(out.read_text());saved['containers'].append(dict(saved['containers'][0],id='second'))
    out.write_text(json.dumps(saved))
    report=gate.verify(out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='HOLD'
    assert any(r['reason']=='capture missing or incomplete' for r in report['holds'])


def test_positive_down_conmon_refuses_even_when_descriptors_unreadable(down,monkeypatch):
    snap,out,proc,cg,data=down
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
    original_pod=gate.pod
    monkeypatch.setattr(gate,'pod',lambda *a:'test|0|12349|none|false|' if a[0]=='inspect' and a[2]==gate.CAPTURE_FORMAT else original_pod(*a))
    p=process(proc,12349,'conmon','/shell')
    listing=Path.iterdir
    def denied(path):
        if path==p/'fd':raise PermissionError('required helper descriptors')
        return listing(path)
    monkeypatch.setattr(Path,'iterdir',denied)
    report=gate.verify(out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='REFUSE'
    assert any(r['reason']=='positively associated down helper survives' for r in report['refusals'])
    monkeypatch.setattr(Path,'iterdir',listing);monkeypatch.setattr(gate,'pod',original_pod);shutil.rmtree(p)
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='PASS'


@pytest.mark.parametrize('unreadable',['snapshot','state'])
def test_rollback_route_holds_unreadable_required_original_evidence(down,monkeypatch,unreadable):
    snap,out,proc,cg,data=down
    original=gate.pod
    if unreadable=='snapshot':snap.write_text('{broken')
    else:
        monkeypatch.setattr(gate,'pod',lambda *a:'incomplete state' if a[0]=='inspect' else original(*a))
    with pytest.raises(ValueError,match='original restart evidence unreadable'):
        gate.rollback_route(snap,'project')


@pytest.mark.parametrize('number',[2,19])
def test_unrelated_cgroup_vanish_is_absent_and_search_runs_once(down,monkeypatch,number):
    snap,out,proc,cg,data=down
    saved=json.loads(snap.read_text());saved['containers'].append(dict(saved['containers'][0],id='other',name='other',state='exited'))
    snap.write_text(json.dumps(saved))
    original_pod=gate.pod
    def pod(*args):
        if args[0]=='ps':return '' if '-q' in args else 'test other'
        result=original_pod(*args)
        return result.replace('test|','other|') if args[-1]=='other' and args[0]=='inspect' else result
    monkeypatch.setattr(gate,'pod',pod)
    original=gate.os.walk;walks=[]
    def racing(root,onerror=None):
        if root==cg:
            walks.append(root)
            onerror(OSError(number,'vanished',str(cg/'unrelated')))
        yield from original(root,onerror=onerror)
    monkeypatch.setattr(gate.os,'walk',racing)
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
    assert walks==[cg]
    walks.clear()
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='PASS'
    assert walks==[cg]


def test_recorded_cgroup_vanish_error_holds(down,monkeypatch):
    snap,out,proc,cg,data=down
    def racing(root,onerror=None):
        onerror(FileNotFoundError(2,'vanished',str(cg/'libpod-test.scope')))
        return iter(())
    monkeypatch.setattr(gate.os,'walk',racing)
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)
    assert report['outcome']=='HOLD'
    assert any(r['reason']=='down cgroup evidence unreadable' for r in report['holds'])


def test_mixed_capture_states_its_down_evidence_limit(down):
    snap,out,proc,cg,data=down
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
    saved=json.loads(out.read_text());saved['kind']='ordinary'
    saved['processes']=[dict(pid=999999999,start='1',role='process',cgroups=['0::/gone'])]
    saved['cgroups']=[dict(line='0::/gone',device='0:1',inode=1)]
    out.write_text(json.dumps(saved))
    report=gate.verify(out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='PASS'
    assert 'Mixed' in report['assurance'] and 'outside the identified cgroups' in report['assurance']


def test_retained_down_conmon_pid_reuse_is_not_continuity(down,monkeypatch):
    snap,out,proc,cg,data=down
    p=process(proc,12349,'conmon','/shell')
    original=gate.pod
    monkeypatch.setattr(gate,'pod',lambda *a:'test|0|12349|none|false|' if a[0]=='inspect' and a[2]==gate.CAPTURE_FORMAT else original(*a))
    gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)
    def removed(*args):
        if args[0]=='ps':return ''
        raise subprocess.CalledProcessError(1,args)
    monkeypatch.setattr(gate,'pod',removed)
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='REFUSE'
    for stat in (p/'stat',p/'task/12349/stat'):stat.write_text(stat.read_text().replace('42','43'))
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='PASS'
    for stat in (p/'stat',p/'task/12349/stat'):stat.write_text(stat.read_text().replace('43','42'))
    assert gate.verify(out,proc=proc,cgroup_root=cg)['outcome']=='REFUSE'


@pytest.mark.parametrize('site',['down-member','down-helper','shared-capture','shared-verify'])
def test_neighbouring_proc_reads_treat_esrch_as_vanished(down,monkeypatch,site):
    snap,out,proc,cg,data=down
    p=process(proc,12349,'slirp4netns' if site.startswith('shared') else 'conmon','/rootless-netns-store.scope')
    original_pod=gate.pod
    if site=='down-member':
        group=cg/'libpod-test.scope';group.mkdir()
        for name in ('cgroup.procs','cgroup.threads'):(group/name).write_text('12349')
    if site=='down-helper':
        monkeypatch.setattr(gate,'pod',lambda *a:'test|0|12349|none|false|' if a[0]=='inspect' and a[2]==gate.CAPTURE_FORMAT else original_pod(*a))
    if site.startswith('shared'):
        pidfile=Path(gate.store_identity()['run'])/'networks/rootless-netns/rootless-netns-conn.pid'
        pidfile.parent.mkdir(parents=True);pidfile.write_text('12349')
        monkeypatch.setattr(gate,'pod',lambda *a:'test|0|0|bridge|false|' if a[0]=='inspect' and a[2]==gate.CAPTURE_FORMAT else original_pod(*a))
    identity=gate.process_identity;alive=gate.task_alive
    def reaped_identity(path):
        if path==p:raise ProcessLookupError('reaped identity')
        return identity(path)
    def reaped_alive(path):
        if path==p:raise ProcessLookupError('reaped task')
        return alive(path)
    if site in ('down-member','down-helper'):monkeypatch.setattr(gate,'task_alive',reaped_alive)
    if site=='shared-capture':monkeypatch.setattr(gate,'process_identity',reaped_identity)
    if site=='shared-verify':
        pidfile.unlink()
        assert gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)['outcome']=='PASS'
        pidfile.write_text('12349');monkeypatch.setattr(gate,'process_identity',reaped_identity)
        report=gate.verify(out,proc=proc,cgroup_root=cg)
    else:report=gate.capture(snap,out,proc=proc,cgroup_root=cg,allow_down=True)
    assert report['outcome']=='PASS',report
    # Permission denial at the same required read still holds.
    def denied(path):
        if path==p:raise PermissionError('required read denied')
        return identity(path) if site.startswith('shared') else alive(path)
    monkeypatch.setattr(gate,'process_identity' if site.startswith('shared') else 'task_alive',denied)
    if site=='shared-verify':report=gate.verify(out,proc=proc,cgroup_root=cg)
    else:report=gate.capture(snap,data.parent/'denied.json',proc=proc,cgroup_root=cg,allow_down=True)
    assert report['outcome']=='HOLD',report
