"""Process evidence must retain holders, helpers and unreadable processes."""
import importlib.util
import json
import os
from pathlib import Path


def test_mount_root_and_deleted_fd_are_detected(tmp_path):
    spec = importlib.util.spec_from_file_location('quiescence', Path(__file__).parents[1] / 'docs/validation/quiescence.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    snapshot = tmp_path / 'snapshot.json'
    snapshot.write_text(json.dumps({'containers': [{'mounts': [['/fixture/data', '/data']]}]}))
    proc = tmp_path / 'proc'; process = proc / '123456789'
    (process / 'fd').mkdir(parents=True); (process / 'ns').mkdir()
    for name, target in [('cwd', '/unrelated'), ('root', '/'), ('fd/3', '/fixture/data/file (deleted)'), ('ns/net', 'net:[fixture]')]:
        os.symlink(target, process / name)
    (process / 'comm').write_text('rootlessport\n')
    (process / 'cgroup').write_text('fixture\n')
    (process / 'mountinfo').write_text('10 1 0:1 /fixture/data /data rw - overlay overlay rw\n')
    result = module.evidence(snapshot, proc)
    assert result['holders'][0]['paths'] == [('fd/3', '/fixture/data/file (deleted)'), ('mount-root', '/fixture/data')]
    assert result['helpers'] == [{'pid': 123456789, 'comm': 'rootlessport', 'network': 'net:[fixture]', 'cgroup': 'fixture'}]
    assert result['unreadable'] == []
    (process / 'comm').write_text('server\n')
    (process / 'fd/3').unlink()
    (process / 'mountinfo').write_text('10 1 0:1 /other /other rw - overlay overlay rw\n')
    assert module.evidence(snapshot, proc) == dict(holders=[], helpers=[], unreadable=[])
