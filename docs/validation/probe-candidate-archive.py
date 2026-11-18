"""Verify a candidate archive roundtrip only in this isolated store."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from megasamples import config

ROOT = Path.cwd()
OUT = ROOT / 'build/credential-upgrade'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://' + str(ROOT.parent / 'sql-megasamples-upgrade-env/podman.sock')
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip().startswith(str(ROOT.parent / 'sql-megasamples-upgrade-env/'))
while not (OUT / 'candidate-images.json').exists():
    steps = json.loads((OUT / 'validation-steps.json').read_text())
    assert not any(row['status'] == 'Failed' for row in steps.values()), 'validation failed before transport test'
    time.sleep(3)
manifest = json.loads((OUT / 'candidate-images.json').read_text())
archive = ROOT / manifest['archive']['path']
assert archive.resolve().is_relative_to(ROOT)
h = hashlib.sha256()
with archive.open('rb') as stream:
    for block in iter(lambda: stream.read(1 << 20), b''):
        h.update(block)
assert h.hexdigest() == manifest['archive']['sha256']


def stamp(service):
    row = json.loads(subprocess.check_output(['docker', 'inspect', 'megasamples-' + service], text=True))[0]
    assert row['Config']['Labels']['com.docker.compose.project'] == 'megasamples-upgrade'
    return dict(id=row['Id'], image=row['Image'], started_at=row['State']['StartedAt'], running=row['State']['Running'])


before = {name: stamp(name) for name in manifest['services']}
start = time.monotonic()
loaded = subprocess.run(['docker', 'load', '-i', str(archive)], capture_output=True, text=True)
assert loaded.returncode == 0, 'isolated candidate archive load failed'
assert not any(value in loaded.stdout + loaded.stderr for value in config.passwords().values())
for service, row in manifest['services'].items():
    actual = subprocess.check_output(['docker', 'image', 'inspect', '-f', '{{.Id}}', row['validated_reference']], text=True).strip()
    assert actual.removeprefix('sha256:') == row['image_id'].removeprefix('sha256:')
    reference = row['repository_reference']
    if '@' not in reference:
        subprocess.run(['docker', 'tag', actual, reference], check=True)
    actual_ref = subprocess.check_output(['docker', 'image', 'inspect', '-f', '{{.Id}}', reference], text=True).strip()
    assert actual_ref.removeprefix('sha256:') == row['image_id'].removeprefix('sha256:')
after = {name: stamp(name) for name in manifest['services']}
assert before == after, 'archive load changed a running application container'
row = dict(status='Passed', read_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
           archive_sha256=h.hexdigest(), seconds=time.monotonic() - start,
           every_loaded_image_id_matches=True, every_repository_reference_matches=True,
           application_ids_images_start_times_unchanged=True, containers=after)
(OUT / 'candidate-transport.json').write_text(json.dumps(row, indent=2) + '\n')
print('Passed: candidate archive load, exact image IDs/references, running application IDs/start times unchanged', flush=True)
