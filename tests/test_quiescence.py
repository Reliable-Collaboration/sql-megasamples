"""Readable filesystem evidence uses mount roots, never pathname text alone."""
import importlib.util
import os
from pathlib import Path

import pytest
from test_quiescence_capture import process

SPEC=importlib.util.spec_from_file_location('holder_gate',Path(os.environ.get('DL088_GATE_SOURCE', Path(__file__).parents[1]/'docs/validation/quiescence.py')))
gate=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(gate)


def scan(tmp_path,monkeypatch,device='8:9',root='/actual/data',point='/data',target='/data/file'):
    proc=tmp_path/'proc';proc.mkdir();p=process(proc)
    (p/'mountinfo').write_text(f'1 0 {device} {root} {point} rw - ext4 fixture rw\n')
    os.symlink(target,p/'fd/3')
    source=dict(device='8:9',root='/actual/data',canonical='/actual/data',path='/alias/data',inode=3)
    monkeypatch.setattr(gate,'classify_owner',lambda *args:'own')
    return proc,p,source


def test_alias_translation_reads_actual_filesystem(tmp_path,monkeypatch):
    proc,p,source=scan(tmp_path,monkeypatch)
    report=gate.holder_scan([source],[],proc)
    assert report['holders'][0]['reason']=='recorded data source held'
    assert any(r['kind']=='fd/3' for r in report['holders'][0]['holds'])


def test_same_path_on_different_filesystem_is_not_holder(tmp_path,monkeypatch):
    proc,p,source=scan(tmp_path,monkeypatch,device='8:10',root='/',point='/',target='/actual/data/file')
    report=gate.holder_scan([source],[],proc)
    assert not report['holders'] and not report['holds']


def test_mapping_closed_fd_uses_device_and_mount_translation(tmp_path,monkeypatch):
    proc,p,source=scan(tmp_path,monkeypatch,root='/actual',point='/mnt'); (p/'fd/3').unlink()
    (p/'maps').write_text('1000-2000 rw-s 0000 08:09 123 /mnt/data/pages (deleted)\n')
    assert gate.holder_scan([source],[],proc)['holders'][0]['holds'][0]['kind']=='mapping'
    (p/'maps').write_text('1000-2000 rw-s 0000 08:0a 123 /mnt/data/pages\n')
    assert not gate.holder_scan([source],[],proc)['holders']


def test_unrelated_private_asound_mount_is_skipped(tmp_path,monkeypatch):
    proc,p,source=scan(tmp_path,monkeypatch); (p/'fd/3').unlink()
    (p/'mountinfo').write_text('1 0 0:203 /asound /proc/asound rw - tmpfs tmpfs rw\n')
    assert not gate.holder_scan([source],[],proc)['holders']


def test_unreadable_required_descriptor_holds(tmp_path,monkeypatch):
    proc,p,source=scan(tmp_path,monkeypatch); original=Path.iterdir
    def denied(path):
        if path==p/'fd': raise PermissionError('fixture')
        return original(path)
    monkeypatch.setattr(Path,'iterdir',denied)
    report=gate.holder_scan([source],['0::/libpod-test.scope'],proc)
    assert report['holds'][0]['reason']=='required holder inspection unreadable'
    assert report['holds'][0]['operation']=='fd'


def test_diagnostic_does_not_read_arguments_or_environments(tmp_path,monkeypatch):
    proc,p,source=scan(tmp_path,monkeypatch); original=Path.open
    def guarded(path,*args,**kwargs):
        assert path.name not in ('cmdline','environ')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded)
    gate.holder_scan([source],[],proc)


def test_accessible_other_owner_holder_is_still_positive_evidence(tmp_path,monkeypatch):
    proc,p,source=scan(tmp_path,monkeypatch)
    monkeypatch.setattr(gate,'classify_owner',lambda *args:'other-owner')
    report=gate.holder_scan([source],[],proc)
    assert report['holders'] and report['holders'][0]['owner']=='other-owner'
