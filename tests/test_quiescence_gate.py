"""Every DL-088 decision-table branch asserts its own reason and reversal."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest
from test_quiescence_capture import process

SPEC=importlib.util.spec_from_file_location('bounded_gate',Path(os.environ.get('DL088_GATE_SOURCE', Path(__file__).parents[1]/'docs/validation/quiescence.py')))
gate=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(gate)


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    proc=tmp_path/'proc'; proc.mkdir(); cg=tmp_path/'cgroup'; cg.mkdir()
    data=tmp_path/'data'; data.mkdir()
    saved=dict(schema=1,complete=True,boot_id='boot',project='project',store=dict(graph='graph',run='run'),
               containers=[dict(id='test',name='engine',pid=0,running=False,state='exited')],
               processes=[],cgroups=[],sources=[gate.source_identity(data)],shared_helper=None,holds=[])
    monkeypatch.setattr(gate,'boot_id',lambda:'boot')
    monkeypatch.setattr(gate,'store_identity',lambda:dict(graph='graph',run='run'))
    monkeypatch.setattr(gate,'caller_uid_mappings',lambda:[(0,0,4294967295)])
    monkeypatch.setattr(gate,'pod',lambda *args: '' if args[0]=='ps' else 'test|false|0')
    path=tmp_path/'capture.json'
    def verify(eligible=True):
        path.write_text(json.dumps(saved)); return gate.verify(path,proc=proc,cgroup_root=cg,phase_eligible=eligible)
    return saved,proc,cg,data,path,verify


def reasons(report,kind): return {r['reason'] for r in report[kind]}


@pytest.mark.parametrize('role,reason',[('process','recorded process survives'),('conmon','recorded process survives'),('dedicated helper','dedicated helper survives')])
def test_recorded_survivor_refuses_with_reversal(fixture,role,reason):
    saved,proc,cg,data,path,verify=fixture
    p=process(proc); saved['processes']=[dict(gate.process_identity(p),role=role)]
    report=verify(); assert report['outcome']=='REFUSE' and reason in reasons(report,'refusals')
    (p/'stat').unlink(); (p/'task/12345/stat').unlink()
    assert verify()['outcome']=='HOLD'  # Existing PID directory with unreadable stat is not absence.
    import shutil; shutil.rmtree(p)
    assert verify()['outcome']=='PASS'


def test_new_cgroup_descendant_refuses_with_reversal(fixture):
    saved,proc,cg,data,path,verify=fixture
    parent=cg/'libpod-test.scope'; parent.mkdir(); (parent/'cgroup.procs').write_text(''); (parent/'cgroup.threads').write_text('')
    saved['cgroups']=[dict(line='0::/libpod-test.scope',**gate.object_identity(parent))]
    child=parent/'exec'; child.mkdir(); (child/'cgroup.procs').write_text('12345'); (child/'cgroup.threads').write_text('12345')
    p=process(proc,group='/libpod-test.scope/exec')
    assert 'live deployment cgroup task' in reasons(verify(),'refusals')
    (child/'cgroup.procs').write_text(''); (child/'cgroup.threads').write_text('')
    # Membership from readable proc corroborates even a racing cgroup list.
    assert verify()['outcome']=='REFUSE'
    (p/'cgroup').write_text('0::/elsewhere')
    assert verify()['outcome']=='PASS'


@pytest.mark.parametrize('consumer',[False,True])
def test_shared_helper_consumer_rule_with_reversal(fixture,monkeypatch,consumer):
    saved,proc,cg,data,path,verify=fixture
    p=process(proc,comm='slirp4netns',group='/rootless-netns-store.scope')
    saved['shared_helper']=dict(gate.process_identity(p),role='shared helper',pidfile='fixture')
    monkeypatch.setattr(gate,'remaining_consumers',lambda *args:['other-container'] if consumer else [])
    report=verify()
    assert report['outcome']==('PASS' if consumer else 'REFUSE')
    assert ('shared helper without verified consumer' in reasons(report,'refusals')) == (not consumer)
    assert report['shared_consumers']==(['other-container'] if consumer else [])
    monkeypatch.setattr(gate,'remaining_consumers',lambda *args:[] if consumer else ['other-container'])
    assert verify()['outcome']==('REFUSE' if consumer else 'PASS')


@pytest.mark.parametrize('case,reason',[
    ('incomplete','capture missing or incomplete'),('reboot','capture crosses reboot'),
    ('reuse','recorded process identifier reused'),('source','source identity changed'),
    ('unreadable','required process inspection unreadable'),('association','required association unresolved'),
    ('cgroup-unreadable','required cgroup inspection unreadable'),('cgroup-reuse','recorded cgroup identifier reused'),
    ('phase','phase state ineligible'),('store','capture store changed')])
def test_hold_branches_with_reversal(fixture,monkeypatch,case,reason):
    saved,proc,cg,data,path,verify=fixture; old=copy.deepcopy(saved); eligible=True
    if case=='incomplete': saved['complete']=False
    if case=='reboot': saved['boot_id']='previous-boot'
    if case in ('reuse','unreadable'):
        p=process(proc); saved['processes']=[dict(gate.process_identity(p),role='process')]
        if case=='reuse': saved['processes'][0]['start']='old'
        else: (p/'stat').unlink()
    if case=='source': saved['sources'][0]['inode']+=1
    if case=='association': saved['holds']=[dict(reason='required association unresolved')]
    if case.startswith('cgroup-'):
        group=cg/'libpod-test.scope';group.mkdir(); (group/'cgroup.procs').write_text(''); (group/'cgroup.threads').write_text('')
        saved['cgroups']=[dict(line='0::/libpod-test.scope',**gate.object_identity(group))]
        if case=='cgroup-unreadable': (group/'cgroup.procs').unlink()
        else: saved['cgroups'][0]['inode']+=1
    if case=='phase': eligible=False
    if case=='store': saved['store']['run']='different'
    report=verify(eligible)
    assert report['outcome']=='HOLD' and reason in reasons(report,'holds')
    saved.clear(); saved.update(old)
    assert verify()['outcome']=='PASS'


def test_missing_capture_is_hold(fixture):
    saved,proc,cg,data,path,verify=fixture
    report=gate.verify(path,proc=proc,cgroup_root=cg)
    assert report['outcome']=='HOLD' and 'capture missing or incomplete' in reasons(report,'holds')
    assert verify()['outcome']=='PASS'


def test_readable_unrelated_holder_refuses_with_reversal(fixture):
    saved,proc,cg,data,path,verify=fixture
    p=process(proc,group='/unrelated'); source=saved['sources'][0]
    (p/'mountinfo').write_text(f"1 0 {source['device']} / / rw - ext4 fixture rw\n")
    os.symlink(str(data/'held'),p/'fd/3')
    report=verify(); assert report['outcome']=='REFUSE'
    assert 'recorded data source held' in reasons(report,'refusals')
    (p/'fd/3').unlink(); assert verify()['outcome']=='PASS'


def test_unreadable_unattributed_is_diagnostic_not_outside(fixture,monkeypatch):
    saved,proc,cg,data,path,verify=fixture; p=process(proc,group='/unattributed')
    original=Path.iterdir
    def denied(path):
        if path==p/'fd': raise PermissionError('fixture')
        return original(path)
    monkeypatch.setattr(Path,'iterdir',denied)
    report=verify(); assert report['outcome']=='PASS'
    assert any(r['operation']=='fd' for r in report['limitations'])
    assert 'outside recorded deployment' not in json.dumps(report)
    assert not report['holds']


def test_zombie_leader_with_live_thread_is_alive(fixture):
    saved,proc,cg,data,path,verify=fixture
    p=process(proc,state='Z'); saved['processes']=[dict(gate.process_identity(p),role='process')]
    thread=p/'task/12346';thread.mkdir(); (thread/'stat').write_text('12346 (thread) S '+' '.join(['0']*18+['43']))
    assert 'recorded process survives' in reasons(verify(),'refusals')
    (thread/'stat').write_text('12346 (thread) Z '+' '.join(['0']*18+['43']))
    assert verify()['outcome']=='PASS'


def test_container_running_refuses_with_reversal(fixture,monkeypatch):
    saved,proc,cg,data,path,verify=fixture
    monkeypatch.setattr(gate,'pod',lambda *a:'test' if a[0]=='ps' else 'test|true|12345')
    assert 'deployment container running' in reasons(verify(),'refusals')
    monkeypatch.setattr(gate,'pod',lambda *a:'' if a[0]=='ps' else 'test|false|0')
    assert verify()['outcome']=='PASS'
