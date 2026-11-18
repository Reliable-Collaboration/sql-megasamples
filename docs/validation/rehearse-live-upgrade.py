#!/usr/bin/env python3
"""Archive regression rehearsal; isolated store READ ONLY.

Source the isolated env.sh first. Runs on the host (native Podman required).
Uses two small existing images, never a database volume, and fresh scratch stores.
Artifacts stay under build/dl086; no prune or existing-container operation.
"""
import importlib.util
import json
import os
import shutil
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
        raise subprocess.CalledProcessError(result.returncode, args, output=result.stdout, stderr=result.stderr)
    return result


def main():
    assert Path.cwd() == ROOT
    assert os.environ.get('CONTAINERS_STORAGE_CONF') == str(ENV / 'storage.conf')
    assert os.environ.get('DOCKER_HOST') == 'unix://' + str(ENV / 'podman.sock')
    assert upgrade.pod('info', '--format', '{{.Store.GraphRoot}}') == str(ENV / 'graph')
    out = Path(tempfile.mkdtemp(prefix='rehearsal-', dir=ROOT / 'build/dl086'))
    (out / 'started.json').write_text(json.dumps({'at': datetime.now(timezone.utc).isoformat()}))
    before = upgrade.pod('ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.ImageID}} {{.State}}')
    receipt = {'at': datetime.now(timezone.utc).isoformat(), 'artifacts': str(out.relative_to(ROOT)), 'checks': {}}
    candidate = json.loads((ROOT / 'docs/validation/credential-prerequisite-2026-11-18.json').read_text())['prepared_candidate']
    images = [candidate['services'][name]['image_id'] for name in ('adminer', 'landing')]
    assert len(set(images)) == 2
    image_bytes = sum(int(upgrade.pod('image', 'inspect', '-f', '{{.Size}}', image)) for image in images)
    required = image_bytes * 5 * 125 // 100
    assert shutil.disk_usage(out).free >= required, 'seed + old/new archives + two scratch stores need space'
    receipt['space_required_bytes'] = required
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
    target, target_env = scratch('load-store')
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
    # Exercise removal after a real stop, with only owned scratch containers.
    project = 'dl086-partial-removal'
    names = ['dl086-fixture-a', 'dl086-fixture-b']
    try:
        for name in names:
            target('run', '-d', '--network', 'none', '--name', name,
                   '--label', 'com.docker.compose.project=' + project,
                   '--entrypoint', '/bin/sh', images[1], '-c',
                   'trap "exit 0" TERM; while :; do sleep 1; done')
        snapshot = out / 'before-stop.json'
        upgrade.snapshot(snapshot, project, names)
        for name in names:
            target('stop', '--time', '10', name)
        exited = out / 'exited.json'
        try:
            upgrade.exited(snapshot, exited)
        except ValueError as error:
            assert 'crash-consistent' in str(error)
            receipt['checks']['fixture_exit_137_requires_ack'] = 'Passed'
            upgrade.exited(snapshot, exited, allow_crash_consistent=True)
        target('rm', names[0])  # partial down: one removed, one still exited
        try:
            upgrade.exited(snapshot, out / 'unsafe-missing.json')
        except ValueError as error:
            assert 'missing' in str(error)
        else:
            raise AssertionError('missing container accepted without exited evidence')
        upgrade.exited(snapshot, out / 'partial-removal.json', removed_with=exited, allow_crash_consistent=True)
        receipt['checks']['partial_removal_with_retained_exited_receipt'] = 'Passed'
    finally:
        for name in names:
            run(['podman', 'rm', '-f', name], target_env, check=False)
    # Drop only the two owned scratch stores; reset also terminates their pause processes.
    for pod, env in [(source, source_env), (target, target_env)]:
        assert not pod('ps', '-aq')
        graph = pod('info', '--format', '{{.Store.GraphRoot}}')
        assert Path(graph).is_relative_to(out)
        pod('system', 'reset', '--force')
    receipt['checks']['scratch_stores_and_pause_cleanup'] = 'Passed'
    (out / 'archive-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    upgrade.pod = lambda *args: run(['podman', *args]).stdout.strip()
    assert upgrade.pod('ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.ImageID}} {{.State}}') == before
    receipt['checks']['isolated_containers_unchanged'] = 'Passed'
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
