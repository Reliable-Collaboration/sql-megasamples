"""Read immutable image data sizes, without starting a server or a volume copy.

After sourcing env.sh: podman unshare python3 docs/validation/measure-lts-data.py
Mounts only the three isolated corrected images after successful packaging.
"""
import json
import os
from pathlib import Path
import stat
import subprocess

assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.geteuid() == 0, 'Run through rootless podman unshare, after sourcing env.sh'
out = Path('build/lts-audit')
steps = json.loads((out / 'build-steps.json').read_text())
assert steps['start-lts-stack']['status'] == 'Passed'
images = {(engine, 'DL-074'): subprocess.check_output(['podman', 'image', 'inspect', 'sql-megasamples-'+engine+':dev', '--format', '{{.Id}}'], text=True).strip().removeprefix('sha256:') for engine in ['mysql', 'postgres', 'sqlite']}
paths = {'mysql': 'var/lib/mysql', 'postgres': 'var/lib/postgresql/18/docker', 'sqlite': 'data'}


def run(*args):
    return subprocess.run(['podman', *args], capture_output=True, text=True, check=True).stdout


already_mounted = {line.split()[0].removeprefix('sha256:') for line in run('image', 'mount').splitlines()}
results = []
for (engine, variant), image in images.items():
    metadata = json.loads(run('image', 'inspect', image))[0]
    mount = Path(run('image', 'mount', image).strip())
    try:
        root = mount / paths[engine]
        assert root.is_dir(), str(root)
        seen = set()
        logical = allocated = files = 0
        for directory, _, filenames in os.walk(root):
            for filename in filenames:
                item = (Path(directory) / filename).lstat()
                key = (item.st_dev, item.st_ino)
                if stat.S_ISREG(item.st_mode) and key not in seen:
                    seen.add(key)
                    files += 1
                    logical += item.st_size
                    allocated += item.st_blocks * 512
        results.append(dict(engine=engine, variant=variant, image=image, image_total_bytes=metadata['Size'],
                            data_path='/'+paths[engine], regular_files=files,
                            data_regular_file_bytes=logical, data_allocated_file_bytes=allocated))
        print(engine, variant, 'baked data bytes', logical, 'image total bytes', metadata['Size'], flush=True)
    finally:
        if image not in already_mounted:
            run('image', 'unmount', image)
(out / 'image-sizes.json').write_text(json.dumps(results, indent=2)+'\n')
