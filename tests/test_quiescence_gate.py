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
               processes=[dict(pid=999999999,start='42',comm='exited-server',cgroups=['0::/libpod-original.scope'],role='process')],
               cgroups=[dict(line='0::/libpod-original.scope',device='0:1',inode=1)],sources=[gate.source_identity(data)],shared_helper=None,holds=[])
    monkeypatch.setattr(gate,'boot_id',lambda:'boot')
    monkeypatch.setattr(gate,'store_identity',lambda:dict(graph='graph',run='run'))
    monkeypatch.setattr(gate,'caller_uid_mappings',lambda:[(0,0,4294967295)])
    monkeypatch.setattr(gate,'pod',lambda *args: '' if args[0]=='ps' else 'test|false|0')
    path=tmp_path/'capture.json'
    def verify(eligible=True):
        path.write_text(json.dumps(saved)); return gate.verify(path,proc=proc,cgroup_root=cg,phase_eligible=eligible)
    return saved,proc,cg,data,path,verify


def reasons(report,kind): return {r['reason'] for r in report[kind]}


def test_required_cgroup_enumeration_denial_holds_with_readable_reversal(fixture,monkeypatch):
    saved,proc,cg,data,path,verify=fixture
    parent=cg/'libpod-test.scope';parent.mkdir()
    child=parent/'exec';child.mkdir()
    for group in (parent,child):
        for name in ('cgroup.procs','cgroup.threads'):(group/name).write_text('')
    saved['cgroups']=[dict(line='0::/libpod-test.scope',**gate.object_identity(parent))]
    original=gate.os.scandir
    def denied(directory):
        if Path(directory)==child:raise PermissionError(13,'enumeration denied',str(child))
        return original(directory)
    monkeypatch.setattr(gate.os,'scandir',denied)
    assert (child/'cgroup.procs').read_text()==''
    report=verify()
    assert report['outcome']=='HOLD',report
    assert 'required cgroup inspection unreadable' in reasons(report,'holds')
    monkeypatch.setattr(gate.os,'scandir',original)
    assert verify()['outcome']=='PASS'


def test_recorded_cgroup_member_esrch_is_absent(fixture,monkeypatch):
    saved,proc,cg,data,path,verify=fixture
    group=cg/'libpod-test.scope';group.mkdir()
    for name in ('cgroup.procs','cgroup.threads'):(group/name).write_text('12349')
    saved['cgroups']=[dict(line='0::/libpod-test.scope',**gate.object_identity(group))]
    p=process(proc,12349,group='/other')
    original=gate.task_alive
    def reaped(path):
        if path==p:raise ProcessLookupError('task reaped')
        return original(path)
    monkeypatch.setattr(gate,'task_alive',reaped)
    assert verify()['outcome']=='PASS'
    def denied(path):
        if path==p:raise PermissionError('task unreadable')
        return original(path)
    monkeypatch.setattr(gate,'task_alive',denied)
    exists=Path.exists
    monkeypatch.setattr(Path,'exists',lambda path:False if path==p else exists(path))
    assert 'required cgroup inspection unreadable' in reasons(verify(),'holds')


@pytest.mark.parametrize('extra_current',[False,True])
def test_historical_mixed_generation_does_not_own_current_listing(fixture,monkeypatch,extra_current):
    saved,proc,cg,data,path,verify=fixture
    earlier=copy.deepcopy(saved)
    earlier['containers'].append(dict(id='old-console',name='console',pid=0,running=False,state='created'))
    earlier['down_evidence']=[dict(id='old-console',name='console',ports=[])]
    prior=data.parent/'rollback-first';prior.mkdir()
    (prior/'rollback-stop-capture-20261118T120000.json').write_text(json.dumps(earlier))
    saved['containers'][0]['id']='new-engine'
    saved['down_evidence']=[dict(id='new-engine',name='engine',ports=[])]
    def pod(*args):
        if args[0]=='ps':return '' if '-q' in args else 'new-engine'+(' late-console' if extra_current else '')
        if args[0]=='container':
            if args[-1] in ('test','old-console'):raise subprocess.CalledProcessError(1,args)
            return ''
        identity=args[-1]
        if identity in ('test','old-console'):raise subprocess.CalledProcessError(1,args)
        if args[2]==gate.CAPTURE_FORMAT:return identity+'|0|0|none|false|'
        if args[2]=='{{json .HostConfig.PortBindings}}':return '{}'
        return identity+'|false|0'
    monkeypatch.setattr(gate,'pod',pod)
    verify()
    report=gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)
    assert report['history'][0]['applicable']
    assert report['outcome']==('HOLD' if extra_current else 'PASS'),report
    assert ('container capture incomplete' in reasons(report,'holds'))==extra_current
    if extra_current:
        assert all('capture' not in row for row in report['holds'])


def test_history_does_not_list_load_rehearsal_or_abort_directories(fixture,monkeypatch):
    saved,proc,cg,data,path,verify=fixture
    verify()
    irrelevant=[data.parent/name for name in ('rollback-load-rehearsal-fixture','rollback-abort-fixture')]
    for directory in irrelevant:directory.mkdir()
    original=Path.iterdir
    def denied(directory):
        if directory in irrelevant:raise PermissionError('not a capture location')
        return original(directory)
    monkeypatch.setattr(Path,'iterdir',denied)
    assert gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)['outcome']=='PASS'


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


def test_reused_cgroup_does_not_attribute_its_new_members(fixture):
    saved,proc,cg,data,path,verify=fixture
    group=cg/'libpod-test.scope';group.mkdir();(group/'cgroup.procs').write_text('12345');(group/'cgroup.threads').write_text('12345')
    saved['cgroups']=[dict(line='0::/libpod-test.scope',**gate.object_identity(group))]
    saved['cgroups'][0]['inode']+=1
    process(proc)
    report=verify()
    assert report['outcome']=='HOLD'
    assert 'recorded cgroup identifier reused' in reasons(report,'holds')
    assert 'live deployment cgroup task' not in reasons(report,'refusals')


@pytest.mark.parametrize('field',['processes','cgroups'])
def test_empty_required_capture_is_never_pass(fixture,field):
    saved,proc,cg,data,path,verify=fixture
    old=saved[field];saved[field]=[]
    report=verify()
    assert report['outcome']=='HOLD'
    assert 'capture missing or incomplete' in reasons(report,'holds')
    saved[field]=old;assert verify()['outcome']=='PASS'


@pytest.mark.parametrize('mode,expected',[('bridge',['other']),('host',[]),('none',[])])
def test_remaining_consumers_inspects_live_store_objects(fixture,monkeypatch,mode,expected):
    saved,proc,cg,data,path,verify=fixture
    process(proc,group='/user.slice/libpod-other.scope')
    monkeypatch.setattr(gate,'pod',lambda *args:'other' if args[0]=='ps' else 'other|12345|0|'+mode+'|false|')
    assert gate.remaining_consumers(saved,proc)==expected
    if mode=='bridge':
        (proc/'12345/cgroup').write_text('0::/unattributed')
        with pytest.raises(ValueError,match='consumer association unresolved'):
            gate.remaining_consumers(saved,proc)


@pytest.mark.parametrize('change',['incomplete','reboot','store','pid-reuse','cgroup-reuse','unrelated'])
def test_history_applicability_is_mechanical_with_reversal(fixture,change):
    saved,proc,cg,data,path,verify=fixture
    current=copy.deepcopy(saved)
    assert gate.historical_applicability(saved,current,proc,cg)
    if change=='incomplete':saved['complete']=False
    if change=='reboot':saved['boot_id']='old'
    if change=='store':saved['store']['run']='different'
    if change=='pid-reuse':
        p=process(proc);saved['processes']=[dict(gate.process_identity(p),role='process')];saved['processes'][0]['start']='before'
    if change=='cgroup-reuse':
        group=cg/'scope';group.mkdir();saved['cgroups']=[dict(line='0::/scope',**gate.object_identity(group))];saved['cgroups'][0]['inode']+=1
    if change=='unrelated':saved['containers']=[dict(id='other')];saved['sources'][0]['root']='/other-data'
    assert gate.historical_applicability(saved,current,proc,cg) == (change in ('pid-reuse','cgroup-reuse'))
    assert gate.historical_applicability(current,current,proc,cg)


def test_exited_zombie_with_deleted_cgroup_is_not_unresolved(fixture):
    saved,proc,cg,data,path,verify=fixture
    p=process(proc,state='Z');saved['processes']=[dict(gate.process_identity(p),role='process')]
    (p/'cgroup').write_text('0::/ (deleted)')
    assert verify()['outcome']=='PASS'
    thread=p/'task/12346';thread.mkdir();(thread/'stat').write_text('12346 (thread) S '+' '.join(['0']*18+['43']))
    report=verify()
    assert 'required association unresolved' in reasons(report,'holds')
    assert 'recorded process survives' in reasons(report,'refusals')


def test_history_inventory_failure_holds_instead_of_dropping_prior_records(fixture,monkeypatch):
    saved,proc,cg,data,path,verify=fixture
    assert verify()['outcome']=='PASS'
    original=Path.iterdir
    def denied(root):
        if root==data.parent: raise PermissionError('history directory unreadable')
        return original(root)
    monkeypatch.setattr(Path,'iterdir',denied)
    report=gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)
    assert report['outcome']=='HOLD'
    assert 'capture history inspection unreadable' in reasons(report,'holds')


def test_history_ignores_unreadable_cold_data_but_keeps_earlier_survivor(fixture,monkeypatch):
    saved,proc,cg,data,path,verify=fixture
    assert verify()['outcome']=='PASS'
    cold=data.parent/'postgres';cold.mkdir(mode=0o700)
    attempt=data.parent/'rollback-fixture';attempt.mkdir()
    prior=copy.deepcopy(saved);p=process(proc,comm='rootlessport')
    prior['processes']=[dict(gate.process_identity(p),role='dedicated helper')]
    gate.write_capture(attempt/'stop-capture.json',prior)
    original_scan=gate.os.scandir
    def denied(root):
        if not isinstance(root,int) and Path(root)==cold: raise PermissionError(13,'cold data unreadable',str(root))
        return original_scan(root)
    monkeypatch.setattr(gate.os,'scandir',denied)
    report=gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)
    assert 'capture history inspection unreadable' not in reasons(report,'holds')
    assert 'dedicated helper survives' in reasons(report,'refusals')
    import shutil;shutil.rmtree(p)
    assert gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)['outcome']=='PASS'


def test_legacy_unindexed_capture_is_also_required(fixture):
    saved,proc,cg,data,path,verify=fixture
    assert verify()['outcome']=='PASS'
    prior=copy.deepcopy(saved);p=process(proc,comm='rootlessport')
    prior['processes']=[dict(gate.process_identity(p),role='dedicated helper')]
    legacy=data.parent/'stop-capture-20261118T120000.json';legacy.write_text(json.dumps(prior))
    report=gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)
    assert report['outcome']=='REFUSE'
    assert 'dedicated helper survives' in reasons(report,'refusals')
    legacy.unlink()
    assert gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)['outcome']=='PASS'


def test_history_reuse_is_judged_per_row_not_entire_capture(fixture):
    saved,proc,cg,data,path,verify=fixture
    saved['cgroups'][0]['line']='0::/current-gone.scope'
    assert verify()['outcome']=='PASS'
    prior=copy.deepcopy(saved);helper=process(proc,comm='rootlessport')
    prior['processes']=[dict(gate.process_identity(helper),role='dedicated helper')]
    group=cg/'libpod-original.scope';group.mkdir()
    for name in ('cgroup.procs','cgroup.threads'):(group/name).write_text('')
    prior['cgroups']=[dict(line='0::/libpod-original.scope',**gate.object_identity(group))]
    prior['cgroups'][0]['inode']+=1  # same path, new object after an original restart
    gate.write_capture(data.parent/'prior.json',prior)
    report=gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)
    assert 'dedicated helper survives' in reasons(report,'refusals')
    assert 'recorded cgroup identifier reused' not in reasons(report,'holds')
    import shutil;shutil.rmtree(helper)
    assert gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)['outcome']=='PASS'


def test_reaped_recorded_process_is_vanished_even_if_proc_entry_lingers(fixture,monkeypatch):
    saved,proc,cg,data,path,verify=fixture
    p=process(proc);saved['processes']=[dict(gate.process_identity(p),role='process')]
    original=gate.process_identity
    def reaped(path):
        if path==p:raise ProcessLookupError('reaped during read')
        return original(path)
    monkeypatch.setattr(gate,'process_identity',reaped)
    assert verify()['outcome']=='PASS'


@pytest.mark.parametrize('operation',['iterdir','stat'])
def test_unreadable_attempt_inventory_holds(fixture,monkeypatch,operation):
    saved,proc,cg,data,path,verify=fixture
    assert verify()['outcome']=='PASS'
    attempt=data.parent/'rollback-unreadable';attempt.mkdir()
    original=getattr(Path,operation)
    def denied(root,*args,**kwargs):
        if root==attempt:raise PermissionError('attempt capture inventory denied')
        return original(root,*args,**kwargs)
    monkeypatch.setattr(Path,operation,denied)
    report=gate.verify_all(path,data.parent,proc=proc,cgroup_root=cg)
    assert report['outcome']=='HOLD'
    assert 'capture history inspection unreadable' in reasons(report,'holds')
