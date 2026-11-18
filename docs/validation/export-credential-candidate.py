"""Export the exact validated application images for the coordinator's later cutover.

Run in the locked tools container with the isolated env.sh in effect. Runtime
volumes and .env are excluded: this saves images, never container writable layers.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from megasamples import config, engines, consoles

ROOT = Path.cwd()
OUT = ROOT / 'build/credential-upgrade'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip().startswith(str(ROOT.parent / 'sql-megasamples-upgrade-env/'))
parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument('--existing-archive', action='store_true', help='hash/check an archive already written by this export')
args = parser.parse_args()
os.umask(0o077)
required = ['test-image-mysql', 'test-image-postgres', 'test-image-sqlite', 'console-gate', 'console-deep', 'endpoints']
while True:
    steps = json.loads((OUT / 'validation-steps.json').read_text())
    assert not any(row['status'] == 'Failed' for row in steps.values()), 'validation failed before candidate export'
    if all(steps.get(name, {}).get('status') == 'Passed' for name in required):
        break
    time.sleep(3)


def output(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


revision = output(['git', 'rev-parse', 'HEAD'])
software_paths = ['megasamples', 'engines', 'consoles', 'datasets', 'pyproject.toml', 'uv.lock']
subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', *software_paths], check=True)
software_tree = output(['git', 'ls-tree', '-r', 'HEAD', '--', *software_paths])
cfg = config.load()
services = list(cfg.engines) + list(cfg.consoles)
assert len(set(services)) == len(services)
records = {}
for service in services:
    container = 'megasamples-' + service
    info = json.loads(output(['docker', 'inspect', container]))[0]
    assert info['State']['Running']
    assert info['Config']['Labels']['com.docker.compose.project'] == 'megasamples-upgrade'
    image_id = info['Image']
    reference = engines.get(service).image if service in cfg.engines else consoles.get(service).runtime_image
    assert output(['docker', 'image', 'inspect', '-f', '{{.Id}}', reference]).removeprefix('sha256:') == image_id.removeprefix('sha256:')
    tag = 'localhost/sql-megasamples-' + service + ':validated-dl079-' + revision[:12]
    existing = subprocess.run(['docker', 'image', 'inspect', tag], capture_output=True, text=True)
    if existing.returncode == 0:
        assert json.loads(existing.stdout)[0]['Id'].removeprefix('sha256:') == image_id.removeprefix('sha256:'), 'validated tag already identifies a different image'
    subprocess.run(['docker', 'tag', image_id, tag], check=True)
    records[service] = dict(image_id=image_id, validated_reference=tag, repository_reference=reference)
archive = OUT / 'candidate-images.tar'
start = time.monotonic()
if args.existing_archive:
    assert archive.is_file(), 'no existing candidate archive to verify'
else:
    assert not archive.exists(), 'candidate archive already exists; use --existing-archive to verify it'
    subprocess.run(['docker', 'save', '-o', str(archive), *[row['validated_reference'] for row in records.values()]], check=True)
archive.chmod(0o600)
hash_value = hashlib.sha256()
with archive.open('rb') as stream:
    for block in iter(lambda: stream.read(1 << 20), b''):
        hash_value.update(block)
for service, row in records.items():
    assert output(['docker', 'inspect', '-f', '{{.Image}}', 'megasamples-' + service]).removeprefix('sha256:') == row['image_id'].removeprefix('sha256:')
manifest = dict(status='Passed', captured_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), source_revision=revision,
                software_tree_sha256=hashlib.sha256(software_tree.encode()).hexdigest(), software_paths=software_paths,
                archive=dict(path=str(archive.relative_to(ROOT)), bytes=archive.stat().st_size, sha256=hash_value.hexdigest(), mode='0600'),
                services=records, datasets=cfg.engines, consoles=cfg.consoles,
                rehearsal_ports={name: cfg.ports[name] for name in services if name in cfg.ports},
                sqlite_access='files under /data and /shared; no TCP port',
                export_seconds=time.monotonic() - start,
                runtime_volumes_exported=False, env_file_exported=False)
(OUT / 'candidate-images.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Passed: exact candidate image archive and SHA-256 manifest; no runtime volumes or .env exported', flush=True)
