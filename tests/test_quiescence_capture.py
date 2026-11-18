"""DL-088 pre-stop capture: no arguments, environments or retained secrets."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('gate_capture', Path(os.environ.get('DL088_GATE_SOURCE', Path(__file__).parents[1]/'docs/validation/quiescence.py')))
gate = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(gate)


def process(proc, pid=12345, comm='server', group='/libpod-test.scope', start='42', state='S'):
    p=proc/str(pid); (p/'task'/str(pid)).mkdir(parents=True)
    stat=f'{pid} ({comm}) {state} ' + ' '.join(['0']*18+[start])
    (p/'stat').write_text(stat); (p/'task'/str(pid)/'stat').write_text(stat)
    (p/'cgroup').write_text('0::'+group+'\n'); (p/'comm').write_text(comm)
    (p/'fd').mkdir(); (p/'ns').mkdir()
    (p/'mountinfo').write_text('1 0 0:1 / / rw - tmpfs tmpfs rw\n')
    (p/'maps').write_text('')
    os.symlink('/',p/'cwd'); os.symlink('/',p/'root')
    os.symlink('net:[fixture]',p/'ns/net')
    return p


@pytest.fixture
def capture_fixture(tmp_path, monkeypatch):
    proc=tmp_path/'proc'; proc.mkdir(); cg=tmp_path/'cgroup'; cg.mkdir()
    group=cg/'libpod-test.scope'; group.mkdir(); (group/'cgroup.procs').write_text('12345\n')
    (group/'cgroup.threads').write_text('12345\n')
    process(proc); process(proc,12346,'conmon','/libpod-conmon-test.scope')
    mon=cg/'libpod-conmon-test.scope'; mon.mkdir(); (mon/'cgroup.procs').write_text('12346\n'); (mon/'cgroup.threads').write_text('12346\n')
    data=tmp_path/'data'; data.mkdir()
    run=tmp_path/'run'; run.mkdir()
    snapshot=tmp_path/'snapshot.json'
    row=dict(name='engine',id='test',pid=12345,running=True,state='running',mounts=[[str(data),'/data']])
    snapshot.write_text(json.dumps(dict(project='project',containers=[row])))
    monkeypatch.setattr(gate,'boot_id',lambda:'boot')
    monkeypatch.setattr(gate,'store_identity',lambda:dict(graph=str(tmp_path/'graph'),run=str(run)))
    def pod(*args):
        if args[0]=='ps': return 'test'
        if args[0]=='inspect':
            if args[2]==gate.CAPTURE_FORMAT: return 'test|12345|12346|none|false|'
        raise AssertionError(args)
    monkeypatch.setattr(gate,'pod',pod)
    return snapshot,tmp_path/'capture.json',proc,cg,data


def test_capture_is_exclusive_private_complete_and_retains_sources(capture_fixture):
    snap,out,proc,cg,data=capture_fixture
    gate.capture(snap,out,proc=proc,cgroup_root=cg)
    saved=json.loads(out.read_text())
    assert saved['schema']==1 and saved['complete'] and saved['boot_id']=='boot'
    assert {r['role'] for r in saved['processes']}=={'process','conmon'}
    assert {r['start'] for r in saved['processes']}=={'42'}
    assert saved['sources'][0]['canonical']==str(data.resolve())
    assert saved['sources'][0]['inode']==data.stat().st_ino
    assert out.stat().st_mode & 0o777==0o600
    snap.unlink()  # Capture is independent of snapshot/container retention.
    assert json.loads(out.read_text())['containers'][0]['id']=='test'
    with pytest.raises(FileExistsError): gate.capture(snap,out,proc=proc,cgroup_root=cg)


def test_capture_canonicalises_cross_filesystem_alias(tmp_path):
    alias=tmp_path/'alias'; alias.symlink_to('/dev/shm',target_is_directory=True)
    source=gate.source_identity(alias)
    assert source['canonical']=='/dev/shm'
    assert source['device']==f'{os.major(alias.stat().st_dev)}:{os.minor(alias.stat().st_dev)}'


@pytest.mark.parametrize('failure,reason', [('missing-cgroup','cgroup'),('missing-process','process'),('missing-conmon','conmon'),('missing-source','source'),('empty-project','container')])
def test_incomplete_capture_holds(capture_fixture,monkeypatch,failure,reason):
    snap,out,proc,cg,data=capture_fixture
    if failure=='missing-cgroup': (cg/'libpod-test.scope/cgroup.procs').unlink()
    if failure=='missing-process': (proc/'12345/stat').unlink()
    if failure=='missing-conmon': (proc/'12346/stat').unlink()
    if failure=='missing-source': data.rmdir()
    if failure=='empty-project': snap.write_text('{"project":"project","containers":[]}')
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='HOLD'
    assert any(reason in r['reason'] for r in report['holds'])
    assert not json.loads(out.read_text())['complete']


def test_shared_helper_uses_store_pid_file_not_arguments(capture_fixture,monkeypatch):
    snap,out,proc,cg,data=capture_fixture
    run=Path(gate.store_identity()['run']); helper=run/'networks/rootless-netns'; helper.mkdir(parents=True)
    (helper/'rootless-netns-conn.pid').write_text('12347')
    process(proc,12347,'slirp4netns','/rootless-netns-test.scope')
    monkeypatch.setattr(gate,'pod',lambda *a:'test' if a[0]=='ps' else 'test|12345|12346|bridge|false|')
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='PASS'
    assert json.loads(out.read_text())['shared_helper']['pid']==12347


def test_missing_shared_helper_stops_for_deciders(capture_fixture,monkeypatch):
    snap,out,proc,cg,data=capture_fixture
    monkeypatch.setattr(gate,'pod',lambda *a:'test' if a[0]=='ps' else 'test|12345|12346|bridge|false|')
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='HOLD'
    assert any(r['reason']=='shared helper association unresolved; return to deciders' for r in report['holds'])


def test_extend_preserves_prestop_processes_and_adds_only_new_sources(capture_fixture):
    snap,out,proc,cg,data=capture_fixture
    gate.capture(snap,out,proc=proc,cgroup_root=cg)
    before=json.loads(out.read_text()); source=data.parent/'target';source.mkdir()
    snap.write_text(json.dumps(dict(containers=[dict(mounts=[[str(source),'/restore-target']])])) )
    extended=data.parent/'extended.json'
    gate.extend_capture(out,extended,snap)
    after=json.loads(extended.read_text())
    assert after['processes']==before['processes'] and after['cgroups']==before['cgroups']
    assert after['sources']==before['sources']+[gate.source_identity(source)]
    assert json.loads(out.read_text())==before
    assert extended.stat().st_mode & 0o777==0o600


def test_copy_paths_must_match_retained_canonical_identity(capture_fixture):
    snap,out,proc,cg,data=capture_fixture
    gate.capture(snap,out,proc=proc,cgroup_root=cg)
    gate.check_source(out,data)
    other=data.parent/'other';other.mkdir()
    with pytest.raises(ValueError,match='copy path differs from captured source'):
        gate.check_source(out,other)
    original=data.parent/'retained-data'; data.rename(original);data.mkdir()
    with pytest.raises(ValueError,match='copy path differs from captured source'):
        gate.check_source(out,data)


def test_full_container_ids_required_for_capture_completeness(capture_fixture,monkeypatch):
    snap,out,proc,cg,data=capture_fixture
    saved=json.loads(snap.read_text()); saved['containers'][0]['id']='a'*64;snap.write_text(json.dumps(saved))
    def pod(*args):
        if args[0]=='ps':return 'a'*64 if '--no-trunc' in args else 'a'*12
        return 'a'*64+'|12345|12346|none|false|'
    monkeypatch.setattr(gate,'pod',pod)
    assert gate.capture(snap,out,proc=proc,cgroup_root=cg)['outcome']=='PASS'


def test_conmon_from_inspect_does_not_attribute_shared_shell_cgroup(capture_fixture):
    snap,out,proc,cg,data=capture_fixture
    (proc/'12346/cgroup').write_text('0::/shared-shell')
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='PASS'
    saved=json.loads(out.read_text())
    assert any(r['role']=='conmon' for r in saved['processes'])
    assert not any(r['line']=='0::/shared-shell' for r in saved['cgroups'])


def test_capture_after_stop_cannot_manufacture_historical_evidence(capture_fixture,monkeypatch):
    snap,out,proc,cg,data=capture_fixture
    saved=json.loads(snap.read_text());saved['containers'][0].update(pid=0,running=False,state='exited');snap.write_text(json.dumps(saved))
    monkeypatch.setattr(gate,'pod',lambda *args:'test' if args[0]=='ps' else 'test|0|0|none|false|')
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='HOLD'
    assert any(r['reason']=='deployment process capture missing; cannot capture after stop' for r in report['holds'])


def test_capture_namespace_object_comes_from_live_process_not_host_placeholder(capture_fixture,monkeypatch):
    snap,out,proc,cg,data=capture_fixture
    (proc/'12345/ns/net').unlink();(proc/'12345/ns/net').symlink_to('/proc/self/ns/net')
    helper=process(proc,12348,'rootlessport','/shell')
    (helper/'ns/net').unlink();(helper/'ns/net').symlink_to('/proc/self/ns/net')
    run=Path(gate.store_identity()['run']);shared=run/'networks/rootless-netns';shared.mkdir(parents=True)
    (shared/'rootless-netns-conn.pid').write_text('12347');process(proc,12347,'slirp4netns','/rootless-netns-test.scope')
    placeholder=data.parent/'netns-placeholder';placeholder.touch()
    monkeypatch.setattr(gate,'pod',lambda *a:'test' if a[0]=='ps' else 'test|12345|12346|bridge|true|'+str(placeholder))
    report=gate.capture(snap,out,proc=proc,cgroup_root=cg)
    assert report['outcome']=='PASS'
    assert any(r['pid']==12348 and r['role']=='dedicated helper' for r in json.loads(out.read_text())['processes'])
