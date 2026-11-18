"""Owner-scoped /proc attribution, helper variants and filesystem mount resolution."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('quiescence', Path(__file__).parents[1] / 'docs/validation/quiescence.py')
scanner = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(scanner)


def fixture(tmp_path, monkeypatch, comm='server'):
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_text(json.dumps({'containers':[{'mounts':[['/store/data','/data']]}]}))
    proc = tmp_path / 'proc'; process = proc / '123456789'
    (process / 'fd').mkdir(parents=True); (process / 'ns').mkdir()
    for name,target in [('root','/'),('cwd','/unrelated'),('ns/net','net:[fixture]')]:
        os.symlink(target, process / name)
    (process / 'comm').write_text(comm)
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


def test_unknown_mount_root_refuses_with_reason(tmp_path,monkeypatch):
    snapshot,proc,process = fixture(tmp_path,monkeypatch)
    (process / 'mountinfo').write_text('10 1 8:9 /private/store/data /data rw - ext4 /dev/fixture rw\n')
    result = scanner.evidence(snapshot,proc)
    assert result['unreadable'][0]['reason'] == 'cannot resolve mount root to host path: 8:9 /private/store/data'


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
    process=tmp_path/'process'; (process/'ns').mkdir(parents=True)
    # stat UID is mapped subordinate relative to a synthetic caller UID.
    uid=os.getuid()+123
    original=Path.open
    def denied(path,*args,**kwargs):
        if path.name in ('user','uid_map'): raise PermissionError('fixture')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',denied)
    assert scanner.classify_owner(process,uid) == 'unresolved-owner'
