#!/usr/bin/env python3
"""Native B-3 proof: owned scratch stores only; read-only seed from isolated store."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ENV = Path('/home/rcc-vstudio/working/sql-megasamples-upgrade-env')
assert Path.cwd() == ROOT
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ENV/'storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://'+str(ENV/'podman.sock')
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'


def pod(*args, env=None):
    return subprocess.check_output(['podman', *args], env=env, text=True).strip()


def main():
    assert pod('info', '--format', '{{.Store.GraphRoot}}') == str(ENV/'graph')
    parent = ROOT/'build/dl086-follow-up'; parent.mkdir(exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='native-scratch-', dir=parent))
    backup = out/'backup'; backup.mkdir(mode=0o700)
    helper = ROOT/'docs/validation/live-upgrade.py'
    image = pod('image', 'inspect', '-f', '{{.Id}}', 'localhost/sql-megasamples-landing:validated-dl079-c5a39beba6e3')
    tag = 'localhost/dl086-follow-up:rollback'
    # Save by full ID; do not add a tag or alter the isolated store's images.
    (backup/'rollback-image-ids.txt').write_text(f'{tag} {image} []\n')
    subprocess.run(['python3', str(helper), 'save-images', str(backup)], check=True,
                   stdout=(out/'save.log').open('w'), stderr=subprocess.STDOUT)
    text = (ROOT/'docs/live-upgrade-runbook.md').read_text()
    script = text.split('# Rehearse the COMPLETE rollback set', 1)[1].split(
        '# Back in the original maintenance shell/store.', 1)[0].split('\n', 1)[1]
    env = dict(os.environ, BACKUP_DIR=str(backup), UPGRADE_HELPER=str(helper))
    def run(name, source, expected, *, strict=True):
        with (out/(name+'.log')).open('w') as log:
            result = subprocess.run(['bash', *(['-eu'] if strict else []), '-c', source], env=env, stdout=log, stderr=subprocess.STDOUT)
        assert result.returncode == expected, (name, result.returncode, out)
        return result.returncode
    run('ordinary-rehearsal', script, 0)
    successful = next(backup.glob('rollback-load-rehearsal-*'))
    manual = text.split('# BEGIN failed scratch cleanup\n', 1)[1].split('# END failed scratch cleanup', 1)[0]
    failed_stores = []
    loaded = []
    for state in ('loaded', 'empty'):
        # Fail either after loading or immediately before the first load. The
        # latter already has the private pause process created by podman info.
        needle = ('  SCRATCH_CONTAINERS=$(podman ps -aq)' if state == 'loaded' else
                  '  python3 "$UPGRADE_HELPER" load-images "$BACKUP_DIR"')
        failed_script = script.replace(needle, '  exit 73 # deliberately interrupted rehearsal\n'+needle, 1)
        assert failed_script != script
        before = set(backup.glob('rollback-load-rehearsal-*'))
        run('deliberate-failure-'+state, failed_script, 73)
        created = set(backup.glob('rollback-load-rehearsal-*')) - before
        assert len(created) == 1
        failed = created.pop()
        scratch_env = dict(env, CONTAINERS_STORAGE_CONF=str(failed/'storage.conf'),
                           CONTAINERS_CONF=str(failed/'containers.conf'), XDG_RUNTIME_DIR=str(failed/'xdg'))
        scratch_env.pop('CONTAINERS_CONF_OVERRIDE', None)
        assert pod('info', '--format', '{{.Store.GraphRoot}}', env=scratch_env) == str(failed/'graph')
        images = pod('images', '-q', '--no-trunc', env=scratch_env).splitlines()
        if state == 'loaded':
            loaded = images
            assert loaded and image.removeprefix('sha256:') in [value.removeprefix('sha256:') for value in loaded]
        else:
            assert images == [], images
        assert not pod('ps', '-aq', env=scratch_env)
        env['SCRATCH_DIR'] = str(failed)
        # The manual paste block supplies its own strictness in ordinary Bash.
        run('manual-cleanup-'+state, manual, 0, strict=False)
        failed_stores.append((failed, state, len(images)))
    stores = []
    for path, state, count in [(successful, 'ordinary', 1), *failed_stores]:
        # Never call Podman in a cleaned store: doing so can recreate its pause process.
        pids = json.loads((path/'pause-pids.json').read_text())
        assert pids, 'Native runtime inventory must find an actual pause PID'
        states = []
        for pid in pids:
            stat = Path(f'/proc/{pid}/stat')
            process_state = stat.read_text().split(') ', 1)[1].split()[0] if stat.exists() else 'absent'
            assert process_state in ('Z', 'absent'), (path, pid, process_state)
            states.append(dict(pid=pid, after=process_state))
        metadata = path/'graph/overlay-images/images.json'
        assert not metadata.exists() or json.loads(metadata.read_text()) == []
        stores.append(dict(path=str(path.relative_to(ROOT)), failure_state=state, images_before_cleanup=count, pause_processes=states,
                           image_metadata_empty=True, podman_after_final_migrate=False))
    result = dict(status='Passed', read_at=datetime.now(timezone.utc).isoformat(),
        artifacts=str(out.relative_to(ROOT)), native_real_podman=True,
        seed_image_id=image, fixture_scope='One small real image; no engine-size archive or restored-stack startup claim',
        ordinary_rehearsal_exit=0, deliberately_failed_exit=73, manual_cleanup_exit=0,
        loaded_images_before_manual_cleanup=loaded, empty_store_manual_cleanup_exit=0,
        manual_cleanup_shell='bash -c; strictness supplied by the pasted block', stores=stores,
        isolated_or_live_image_pause_mutations='None; seed save/inspect only in isolated store')
    (out/'receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
