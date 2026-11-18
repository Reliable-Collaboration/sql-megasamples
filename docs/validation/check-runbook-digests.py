"""Exercise the runbook's cold-copy digest on fixtures, never on live files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path.cwd()
OUT = ROOT / 'build/credential-upgrade'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert subprocess.check_output(['podman', 'info', '--format', '{{.Store.GraphRoot}}'], text=True).strip() == str(ROOT.parent / 'sql-megasamples-upgrade-env/graph')
fixture = OUT / 'runbook-digest-fixture'
fixture.mkdir(mode=0o700, exist_ok=True)
for name in ['postgres', 'mysql', 'sqlite', 'sqlite-shared']:
    (fixture / name).mkdir(exist_ok=True)
    (fixture / name / 'sample').write_bytes(b'fixture bytes\n')
link = fixture / 'sqlite' / 'link'
if link.is_symlink():
    link.unlink()
link.symlink_to('sample')


def digest():
    command = ['podman', 'unshare', 'tar', '--sort=name', '--numeric-owner', '--format=gnu', '--atime-preserve=system',
               '-C', str(fixture), '-cf', '-', 'postgres', 'mysql', 'sqlite', 'sqlite-shared']
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    h = hashlib.sha256()
    for block in iter(lambda: process.stdout.read(1 << 20), b''):
        h.update(block)
    error = process.stderr.read()
    assert process.wait() == 0, 'fixture tar stream failed'
    assert not error, 'fixture tar stream emitted diagnostics'
    return h.hexdigest()


results = {}
first = digest()
assert first == digest(), 'unchanged cold copies did not reproduce their digest'
results['unchanged_bytes_and_metadata_reproduce_digest'] = 'Passed'
file = fixture / 'mysql' / 'sample'
file.write_bytes(b'changed bytes\n')
assert digest() != first
results['changed_bytes_detected'] = 'Passed'
file.write_bytes(b'fixture bytes\n')
file.chmod(0o600)
first = digest()
file.chmod(0o640)
assert digest() != first
results['changed_permissions_detected'] = 'Passed'
first = digest()
link.unlink()
link.symlink_to('../mysql/sample')
assert digest() != first
results['changed_symlink_target_detected'] = 'Passed'
row = dict(status='Passed', results=results, live_files_read=False, live_commands_executed=False)
(OUT / 'runbook-digests.json').write_text(json.dumps(row, indent=2) + '\n')
print('Passed: cold-copy digest reproduces and detects changed bytes, permissions and symlink targets', flush=True)
