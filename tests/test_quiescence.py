"""Owner-scoped /proc attribution, helper variants and filesystem mount resolution."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('quiescence', Path(__file__).parents[1] / 'docs/validation/quiescence.py')
scanner = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(scanner)


def fixture(tmp_path, monkeypatch, comm='server'):
    monkeypatch.setattr(scanner, 'caller_uid_mappings', lambda: [(0,0,4294967295)])
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_text(json.dumps({'containers':[{'mounts':[['/store/data','/data']]}]}))
    proc = tmp_path / 'proc'; process = proc / '123456789'
    (process / 'fd').mkdir(parents=True); (process / 'ns').mkdir()
    for name,target in [('root','/'),('cwd','/unrelated'),('ns/net','net:[fixture]')]:
        os.symlink(target, process / name)
    (process / 'comm').write_text(comm)
    (process / 'stat').write_text('123 (fixture) S ' + ' '.join(['0']*19))
    (process / 'cgroup').write_text('fixture')
    (process / 'maps').write_text('')
    (process / 'mountinfo').write_text('10 1 8:2 / / rw - ext4 /dev/fixture rw\n')
    monkeypatch.setattr(scanner, 'host_mounts', lambda _: [('8:2','/','/')])
    return snapshot, proc, process


@pytest.mark.parametrize('comm',['pasta','pasta.avx2','slirp4netns','rootlessport'])
def test_helper_prefixes(tmp_path, monkeypatch, comm):
    snapshot,proc,process = fixture(tmp_path,monkeypatch,comm)
    report = scanner.evidence(snapshot,proc)
    assert report['helpers'][0]['comm'] == comm
    assert report['counts']['own'] == 1


def test_other_owner_not_an_unreadable_own_process(tmp_path,monkeypatch):
    snapshot,proc,process = fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(scanner,'classify_owner',lambda *args:'other-owner')
    (process / 'comm').unlink()  # Do not even try privileged fields for other owners.
    report = scanner.evidence(snapshot,proc)
    assert report['counts']['other-owner'] == 1
    assert report['unreadable'] == []
    assert report['scope'] == 'own and owned-user-namespace processes only'
    assert report['other_owner_inspection'] == 'Not run: requires privilege'


def test_owned_namespace_process_is_fully_inspected(tmp_path,monkeypatch):
    snapshot,proc,process = fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(scanner,'classify_owner',lambda *args:'owned-user-namespace')
    os.symlink('/store/data/file (deleted)', process / 'fd/3')
    report = scanner.evidence(snapshot,proc)
    assert report['counts']['owned-user-namespace'] == 1
    assert report['holders'][0]['pid'] == int(process.name)


def test_nonroot_filesystem_mount_root_resolves_host_path(tmp_path,monkeypatch):
    snapshot,proc,process = fixture(tmp_path,monkeypatch)
    # Host /store is root /private/store on filesystem 8:9.
    monkeypatch.setattr(scanner,'host_mounts',lambda _: [('8:9','/private/store','/store')])
    (process / 'mountinfo').write_text('10 1 8:9 /private/store/data /data rw - ext4 /dev/fixture rw\n')
    result = scanner.evidence(snapshot,proc)
    assert result['holders'][0]['paths'] == [('mount-root','/store/data')]
    assert result['unreadable'] == []


def test_unknown_unrelated_mount_device_is_skipped(tmp_path,monkeypatch):
    snapshot,proc,process = fixture(tmp_path,monkeypatch)
    (process / 'mountinfo').write_text('10 1 8:9 /private/store/data /data rw - ext4 /dev/fixture rw\n')
    result = scanner.evidence(snapshot,proc)
    assert result['unreadable'] == []
    assert result['refusals'] == []


def test_unreadable_own_or_racing_live_process_refuses(tmp_path,monkeypatch):
    snapshot,proc,process = fixture(tmp_path,monkeypatch)
    (process / 'comm').unlink()
    assert scanner.evidence(snapshot,proc)['unreadable'][0]['error'] == 'FileNotFoundError'
    original = Path.read_text
    def read(path,*args,**kwargs):
        if path.name == 'comm': raise PermissionError('fixture')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',read)
    assert scanner.evidence(snapshot,proc)['unreadable'][0]['error'] == 'PermissionError'


def test_namespace_owner_ioctl_and_primary_mapping(tmp_path,monkeypatch):
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,0,4294967295)])
    process = tmp_path / 'process'; (process / 'ns').mkdir(parents=True)
    (process / 'ns/user').write_bytes(b'fixture')
    uid = os.getuid() + 123
    def ioctl(fd, operation, owner, mutate):
        assert operation == 0xb704
        owner[0] = uid
    monkeypatch.setattr(scanner.fcntl,'ioctl',ioctl)
    assert scanner.classify_owner(process,uid) == 'owned-user-namespace'
    def denied(*args): raise PermissionError('fixture')
    monkeypatch.setattr(scanner.fcntl,'ioctl',denied)
    (process / 'uid_map').write_text(f'0 {uid} 1\n1 500000 65536\n')
    assert scanner.classify_owner(process,uid) == 'owned-user-namespace'
    (process / 'uid_map').write_text('0 0 4294967295\n')
    assert scanner.classify_owner(process,uid) == 'other-owner'


def test_mount_alias_never_hides_original_source(tmp_path,monkeypatch):
    snapshot,proc,process = fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(scanner,'host_mounts',lambda _: [('8:2','/','/'),('8:2','/store/data','/alias')])
    (process/'mountinfo').write_text('10 1 8:2 /store/data /data rw - ext4 /dev/fixture rw\n')
    report=scanner.evidence(snapshot,proc)
    assert report['holders'], 'a more-specific alias must not hide /store/data'


def test_closed_fd_shared_mapping_is_a_holder(tmp_path,monkeypatch):
    snapshot,proc,process = fixture(tmp_path,monkeypatch)
    (process/'maps').write_text('1000-2000 rw-s 0000 08:02 123 /store/data/pages (deleted)\n')
    report=scanner.evidence(snapshot,proc)
    assert report['holders'][0]['paths'] == [('mapping','/store/data/pages (deleted)')]


def test_unresolved_namespace_ownership_never_becomes_other_owner(tmp_path,monkeypatch):
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,0,4294967295)])
    process=tmp_path/'process'; (process/'ns').mkdir(parents=True)
    # stat UID is mapped subordinate relative to a synthetic caller UID.
    uid=os.getuid()+123
    original=Path.open
    def denied(path,*args,**kwargs):
        if path.name in ('user','uid_map'): raise PermissionError('fixture')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',denied)
    assert scanner.classify_owner(process,uid) == 'unresolved-owner'


def test_mapped_subordinate_uid_is_inspected_even_when_namespace_denied(tmp_path,monkeypatch):
    from types import SimpleNamespace
    process=tmp_path/'process'; (process/'ns').mkdir(parents=True)
    (process/'uid_map').write_text('0 1000 1\n1 100000 65536\n')
    original_stat=Path.stat
    monkeypatch.setattr(Path,'stat',lambda p,*a,**k: SimpleNamespace(st_uid=27) if p==process else original_stat(p,*a,**k))
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,1000,1),(1,100000,65536)])
    assert scanner.classify_owner(process,0) == 'owned-user-namespace'


def test_overflow_owner_with_mapping_extent_is_unresolved(tmp_path,monkeypatch):
    from types import SimpleNamespace
    process=tmp_path/'process'; (process/'ns').mkdir(parents=True)
    (process/'uid_map').write_text('0 4294967295 4294967295\n')
    original_stat=Path.stat
    monkeypatch.setattr(Path,'stat',lambda p,*a,**k: SimpleNamespace(st_uid=65534) if p==process else original_stat(p,*a,**k))
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,1000,1),(1,100000,65536)])
    assert scanner.classify_owner(process,0) == 'unresolved-owner'


def test_host_owner_inventory_disambiguates_overflow_uid(tmp_path,monkeypatch):
    from types import SimpleNamespace
    process=tmp_path/'12345'; process.mkdir()
    (process/'status').write_text('Uid:\t65534\t65534\t65534\t65534\n')
    original_stat=Path.stat
    monkeypatch.setattr(Path,'stat',lambda p,*a,**k: SimpleNamespace(st_uid=65534) if p==process else original_stat(p,*a,**k))
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,1000,1),(1,100000,65536)])
    monkeypatch.setattr(scanner,'start_time',lambda _: 'fixture-start')
    assert scanner.classify_owner(process,0,{'12345':{'start':'fixture-start','uids':[0,0,0,0]}}) == 'other-owner'
    assert scanner.classify_owner(process,0,{'12345':{'start':'fixture-start','uids':[165533]*4}}) == 'owned-user-namespace'
    assert scanner.classify_owner(process,0,{'12345':{'start':'old-start','uids':[0]*4}}) == 'unresolved-owner'


def test_native_inventory_records_only_uids_start_and_inspection_errors(tmp_path,monkeypatch):
    proc=tmp_path/'proc'; process=proc/'12345'; process.mkdir(parents=True)
    (process/'status').write_text('Name:\tfixture\nUid:\t1000\t1000\t1000\t1000\n')
    (proc/'54321').mkdir()
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,0,4294967295)])
    monkeypatch.setattr(scanner,'start_time',lambda _:'fixture-start')
    output=tmp_path/'owners.json'
    scanner.owner_inventory(output,proc)
    result=json.loads(output.read_text())
    assert result == dict(host_initial_namespace=True,processes={'12345':dict(start='fixture-start',uids=[1000]*4),'54321':dict(error='FileNotFoundError')})
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError): scanner.owner_inventory(output,proc)


def test_current_mapped_uid_overrides_stale_host_owner(tmp_path,monkeypatch):
    from types import SimpleNamespace
    process=tmp_path/'12345'; process.mkdir()
    original_stat=Path.stat
    monkeypatch.setattr(Path,'stat',lambda p,*a,**k: SimpleNamespace(st_uid=27) if p==process else original_stat(p,*a,**k))
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,1000,1),(1,100000,65536)])
    monkeypatch.setattr(scanner,'start_time',lambda _:'same-start')
    assert scanner.classify_owner(process,0,{'12345':dict(start='same-start',uids=[0]*4)}) == 'owned-user-namespace'


def test_native_final_owner_check_refuses_credential_transition(tmp_path,monkeypatch):
    proc=tmp_path/'proc'; process=proc/'12345'; process.mkdir(parents=True)
    (process/'status').write_text('Uid:\t165533\t165533\t165533\t165533\n')
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,0,4294967295)])
    monkeypatch.setattr(scanner,'start_time',lambda _:'same-start')
    report=tmp_path/'report.json'
    report.write_text(json.dumps({'other_owner_records':{'12345':dict(start='same-start',uids=[0]*4)}}))
    with pytest.raises(ValueError,match='ownership changed'):
        scanner.verify_owners(report,proc)
    (process/'status').write_text('Uid:\t0\t0\t0\t0\n')
    scanner.verify_owners(report,proc)

# Round-three shapes: persistent zombies, private /asound mounts, inaccessible
# descriptors and helpers in a different store. No retained arguments/environments.
def test_private_asound_device_is_unrelated(tmp_path, monkeypatch):
    snap, proc, p = fixture(tmp_path, monkeypatch)
    (p/'mountinfo').write_text('10 1 0:203 /asound /proc/asound ro - tmpfs tmpfs ro\n')
    report = scanner.evidence(snap, proc)
    assert report['unreadable'] == []
    assert report['refusals'] == []


@pytest.mark.parametrize('state,klass', [('Z','zombie'),('X','exited'),('x','exited')])
def test_dead_process_has_class_before_namespace_read(tmp_path, monkeypatch, state, klass):
    snap, proc, p = fixture(tmp_path, monkeypatch)
    (p/'stat').write_text('123 (python) ' + state + ' ' + ' '.join(['0']*19))
    (p/'ns/net').unlink()
    report = scanner.evidence(snap, proc)
    assert report['counts'][klass] == 1
    assert report['refusals'] == []


def test_named_unreadable_operation_is_reported_not_whole_host_refusal(tmp_path, monkeypatch):
    snap, proc, p = fixture(tmp_path, monkeypatch, 'ssh-agent')
    original = os.readlink
    def denied(path):
        if Path(path) == p/'ns/net': raise PermissionError('fixture')
        return original(path)
    monkeypatch.setattr(os, 'readlink', denied)
    report = scanner.evidence(snap, proc)
    assert any(r['comm']=='ssh-agent' and r['operation']=='ns/net' for r in report['unreadable'])
    assert report['refusals'] == []


@pytest.mark.parametrize('belongs', [False, True])
def test_helper_requires_recorded_network_or_container_cgroup(tmp_path, monkeypatch, belongs):
    snap, proc, p = fixture(tmp_path, monkeypatch, 'pasta.avx2')
    saved=json.loads(snap.read_text()); saved['containers'][0]['network_namespace']='net:[deployment]'
    snap.write_text(json.dumps(saved))
    (p/'ns/net').unlink(); os.symlink('net:[deployment]' if belongs else 'net:[tools]', p/'ns/net')
    report=scanner.evidence(snap, proc)
    assert report['helpers'][0]['deployment'] == belongs
    assert [r['reason'] for r in report['refusals']] == (['deployment network helper'] if belongs else [])


def test_mount_resolution_only_refuses_source_device(tmp_path,monkeypatch):
    snap,proc,p=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(scanner,'host_mounts',lambda _: [('8:9','/private/store','/store')])
    (p/'mountinfo').write_text('10 1 8:9 /unknown /data rw - ext4 /dev/fixture rw\n')
    report=scanner.evidence(snap,proc)
    assert report['refusals'][0]['reason'] == 'unresolvable mount on recorded source device'
    assert report['refusals'][0]['comm'] == 'server'

@pytest.mark.parametrize('via', ['cgroup','namespace-fd'])
def test_deployment_helper_attribution_alternatives(tmp_path,monkeypatch,via):
    snap,proc,p=fixture(tmp_path,monkeypatch,'rootlessport')
    saved=json.loads(snap.read_text()); saved['containers'][0].update(id='a'*64,network_namespace='net:[deployment]')
    snap.write_text(json.dumps(saved))
    if via=='cgroup': (p/'cgroup').write_text('0::/user.slice/libpod-'+ 'a'*64 + '.scope')
    else: os.symlink('net:[deployment]', p/'fd/5')
    report=scanner.evidence(snap,proc)
    assert report['helpers'][0]['deployment'] is True
    assert report['refusals'][0]['reason']=='deployment network helper'


def test_container_namespace_path_holds_recorded_source(tmp_path,monkeypatch):
    snap,proc,p=fixture(tmp_path,monkeypatch)
    (p/'cwd').unlink(); os.symlink('/data/subdir',p/'cwd')
    (p/'mountinfo').write_text('10 1 8:2 /store/data /data rw - ext4 /dev/fixture rw\n')
    report=scanner.evidence(snap,proc)
    assert ('cwd','/data/subdir') in report['holders'][0]['paths']
    assert report['refusals'][0]['reason']=='recorded data source held'
    assert report['refusals'][0]['comm']=='server'
    assert report['refusals'][0]['owner']=='own'


def test_scan_rejects_child_user_namespace(tmp_path,monkeypatch):
    snap,proc,p=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(scanner,'caller_uid_mappings',lambda:[(0,1000,1)])
    with pytest.raises(ValueError,match='scan must run in host initial user namespace'):
        scanner.evidence(snap,proc)


def test_unresolved_owner_is_named_without_certifying_it(tmp_path,monkeypatch):
    snap,proc,p=fixture(tmp_path,monkeypatch,'new-task')
    monkeypatch.setattr(scanner,'classify_owner',lambda *args:'unresolved-owner')
    report=scanner.evidence(snap,proc)
    assert report['counts']['unresolved-owner']==1
    assert report['unreadable']==[dict(pid=int(p.name),comm='new-task',owner='unresolved-owner',
                                       operation='owner',error='OwnershipUnresolved')]
    assert report['refusals']==[]


def test_vanished_task_is_classified(tmp_path,monkeypatch):
    snap,proc,p=fixture(tmp_path,monkeypatch,'gone')
    original=Path.exists
    monkeypatch.setattr(Path,'exists',lambda path: False if path==p else original(path))
    report=scanner.evidence(snap,proc)
    assert report['counts']['vanished']==1
    assert report['refusals']==[]


def test_shared_host_network_and_service_cgroup_do_not_attribute_helper(tmp_path,monkeypatch):
    snap,proc,p=fixture(tmp_path,monkeypatch,'pasta.avx2')
    host=os.readlink('/proc/self/ns/net')
    saved=json.loads(snap.read_text());saved['containers'][0].update(network_namespace=host,cgroups=['0::/podman.service'])
    snap.write_text(json.dumps(saved))
    (p/'ns/net').unlink();os.symlink(host,p/'ns/net');(p/'cgroup').write_text('0::/podman.service')
    report=scanner.evidence(snap,proc)
    assert report['helpers'][0]['deployment'] is False
    assert report['refusals']==[]
