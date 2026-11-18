#!/usr/bin/env python3
"""Archive regression and rootless teardown rehearsal; isolated store READ ONLY.

Source the isolated env.sh first. Runs on the host (native Podman required).
Uses two small existing images, never a database volume, and fresh scratch stores.
Artifacts stay under build/dl086; no prune or existing-container operation.
"""
import importlib.util
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT.parent / 'sql-megasamples-upgrade-env'
SPEC = importlib.util.spec_from_file_location('upgrade', Path(__file__).with_name('live-upgrade.py'))
upgrade = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upgrade)


def run(args, env=None, check=True):
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=45)
    if check and result.returncode:
        raise RuntimeError(f'{args[0:3]} failed ({result.returncode}): {result.stderr}')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--teardown', action='store_true', help='also attempt scratch Compose stop/down (requires rootless networking)')
    args = parser.parse_args()
    assert Path.cwd() == ROOT
    assert os.environ.get('CONTAINERS_STORAGE_CONF') == str(ENV / 'storage.conf')
    assert os.environ.get('DOCKER_HOST') == 'unix://' + str(ENV / 'podman.sock')
    assert upgrade.pod('info', '--format', '{{.Store.GraphRoot}}') == str(ENV / 'graph')
    out = Path(tempfile.mkdtemp(prefix='rehearsal-', dir=ROOT / 'build/dl086'))
    before = upgrade.pod('ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.ImageID}} {{.State}}')
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'artifacts': str(out.relative_to(ROOT)), 'checks': {}}
    candidate = json.loads((ROOT / 'docs/validation/credential-prerequisite-2026-11-18.json').read_text())['prepared_candidate']
    images = [candidate['services'][name]['image_id'] for name in ('adminer', 'landing')]
    assert len(set(images)) == 2
    # Seed archives are single-image saves by ID from the isolated store.
    for index, image in enumerate(images):
        upgrade.pod('save', '--format=docker-archive', '-o', str(out / f'seed-{index}.tar'), image)

    def scratch(name):
        base = out / name
        base.mkdir()
        storage = base / 'storage.conf'
        storage.write_text(f'[storage]\ndriver="overlay"\ngraphroot="{base}/graph"\nrunroot="{base}/run"\n')
        conf = base / 'containers.conf'
        conf.write_text(f'[engine]\ntmp_dir="{base}/tmp"\n[network]\ndefault_rootless_network_cmd="slirp4netns"\n')
        env = dict(os.environ, CONTAINERS_STORAGE_CONF=str(storage), CONTAINERS_CONF=str(conf))
        env.pop('CONTAINERS_CONF_OVERRIDE', None)
        def pod(*args):
            return run(['podman', *args], env).stdout.strip()
        assert pod('info', '--format', '{{.Store.GraphRoot}}') == str(base / 'graph')
        return pod, env

    source, source_env = scratch('save-store')
    target, _ = scratch('load-store')
    backup = out / 'backup'
    backup.mkdir()
    tags = [f'localhost/dl086-{i}:rollback' for i in range(len(images))]
    for index, (tag, image) in enumerate(zip(tags, images)):
        source('load', '-i', str(out / f'seed-{index}.tar'))
        source('tag', image, tag)
    (backup / 'rollback-image-ids.txt').write_text(''.join(f'{tag} {image} []\n' for tag, image in zip(tags, images)))

    # Exact old save form. A tag count cannot prove the second image exists.
    legacy = out / 'old-rollback-images.tar'
    source('save', '-o', str(legacy), *tags)
    rejected = []
    for image in images:
        try:
            upgrade.check_archive(legacy, image)
        except ValueError:
            rejected.append(image)
    assert rejected == images[1:], 'old command did not reproduce the first-image-only defect'
    receipt['checks']['old_archive_completeness'] = 'Failed (expected red): second image configuration absent'
    # Show that old load also silently maps the second tag to the first ID.
    target('load', '-i', str(legacy))
    actual = target('image', 'inspect', '-f', '{{.Id}}', tags[1]).removeprefix('sha256:')
    assert actual == images[0].removeprefix('sha256:')
    receipt['checks']['old_rollback_tag_identity'] = 'Failed (expected red): second tag points at first image'
    upgrade.pod = source
    upgrade.save_images(backup)
    upgrade.pod = target
    upgrade.load_images(backup)
    receipt['checks']['per_image_save_check_load_retag'] = 'Passed'
    (out / 'archive-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if not args.teardown:
        upgrade.pod = lambda *args: run(['podman', *args]).stdout.strip()
        assert upgrade.pod('ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.ImageID}} {{.State}}') == before
        receipt['checks']['isolated_containers_unchanged'] = 'Passed'
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))
        return

    # The same teardown paths as Compose, with a scratch-only Compose project/socket.
    compose = out / 'compose.yaml'
    compose.write_text('services:\n  fixture:\n    image: ' + images[1] + '\n    entrypoint: ["sh", "-c", "sleep 300"]\n    ports: ["127.0.0.1::80"]\n')
    socket_path = out / 'api.sock'
    api = subprocess.Popen(['podman', 'system', 'service', '--time=0', 'unix://' + str(socket_path)],
                           env=source_env, stdout=(out / 'api.log').open('w'), stderr=subprocess.STDOUT)
    try:
        import time
        for _ in range(100):
            if socket_path.is_socket():
                break
            if api.poll() is not None:
                raise RuntimeError('scratch API exited')
            time.sleep(.1)
        env = dict(source_env, DOCKER_HOST='unix://' + str(socket_path), COMPOSE_PROJECT_NAME='dl086-rehearsal')
        command = ['docker', 'compose', '-p', 'dl086-rehearsal', '-f', str(compose)]
        observations = []
        for cycle in range(3):
            run([*command, 'up', '-d', '--pull', 'never'], env)
            for action in ('stop', 'down'):
                result = run([*command, action], env, check=False)
                observations.append({'cycle': cycle, 'action': action, 'exit_code': result.returncode, 'stderr': result.stderr})
                if result.returncode:
                    raise RuntimeError('teardown failed; inspect scratch artifacts')
        receipt['netns_observations'] = observations
        receipt['checks']['compose_stop_down'] = 'Passed: three cycles; permission error not reproduced; cause unknown'
        assert not source('ps', '-a', '-q'), 'scratch container left behind'
    finally:
        if api.poll() is None and socket_path.is_socket():
            run(['docker', 'compose', '-p', 'dl086-rehearsal', '-f', str(compose), 'down'],
                dict(source_env, DOCKER_HOST='unix://' + str(socket_path)), check=False)
        api.terminate()
        api.wait(timeout=10)
    upgrade.pod = lambda *args: run(['podman', *args]).stdout.strip()
    assert upgrade.pod('ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.ImageID}} {{.State}}') == before
    receipt['checks']['isolated_containers_unchanged'] = 'Passed'
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
