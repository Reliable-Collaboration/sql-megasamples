"""Exercise retained-input preparation; no deployment payloads or credential values."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

import pytest
from test_live_upgrade import upgrade

ROOT = Path(__file__).parents[1]


def retained(tmp_path):
    backup = tmp_path / 'retained'; backup.mkdir()
    with tarfile.open(backup / 'original-configurations.tar', 'w') as out:
        for name in ['compose.yaml', 'megasamples.yaml', 'consoles/fixture']:
            entry = tarfile.TarInfo(name); entry.size = 3
            out.addfile(entry, io.BytesIO(b'{}\n'))
    digest = upgrade.sha(backup / 'original-configurations.tar')
    (backup / 'original-configurations.sha256').write_text(digest + '  original-configurations.tar\n')
    (backup / 'original-ports.json').write_text('{"engines":["postgres"],"consoles":[],"ports":{"postgres":5432}}')
    (backup / 'failed-candidate.env').write_text('# retained empty fixture\n')
    (backup / 'phase-a-resume-receipt.json').write_text('{}')
    return backup


def digests(backup):
    return {str(p.relative_to(backup)): upgrade.sha(p) for p in backup.rglob('*')
            if p.is_file() and not (len(p.relative_to(backup).parts) > 1 and p.relative_to(backup).parts[0].startswith('rollback-'))}


def project_ports_path(tmp_path):
    """Only the bootstrap helper's external project-port inventory is stubbed."""
    binary = tmp_path / 'bin'; binary.mkdir()
    docker = binary / 'docker'
    bindings = {str(port) + '/tcp': [dict(HostIp='127.0.0.1', HostPort=str(port))]
                for port in [3306, 5432, 8080, 8081, 8082, 8083, 8084]}
    docker.write_text('#!/bin/sh\ncase "$1" in\nps) echo fixture;;\ninspect) cat <<\'JSON\'\n'
                      + json.dumps(bindings) + '\nJSON\n;;\n*) exit 42;;\nesac\n')
    docker.chmod(0o755)
    return str(binary) + os.pathsep + os.environ['PATH']


def test_preparation_preserves_readonly_inputs_and_refuses_reuse(tmp_path):
    backup = retained(tmp_path)
    checkout = tmp_path / 'checkout'; checkout.mkdir()
    (checkout / '.env').write_text('# candidate empty fixture\n')
    before = digests(backup)
    # Inputs read-only, including directories. No write permission is bypassed.
    subprocess.run(['chmod', '-R', 'a-w', str(backup)], check=True)
    try:
        if os.geteuid() != 0:
            with pytest.raises(PermissionError):
                upgrade.prepare_rollback(backup, 'blocked', checkout)
            assert digests(backup) == before
        # Only the parent needs add-directory permission to allocate a new attempt.
        # All retained payloads remain read-only throughout preparation.
        backup.chmod(0o700)
        attempt = upgrade.prepare_rollback(backup, 'fixture', checkout)
        assert attempt == backup / 'rollback-fixture'
        assert (attempt / 'configuration/consoles/fixture').read_bytes() == b'{}\n'
        assert (attempt / 'failed-candidate.env').read_bytes() == (checkout / '.env').read_bytes()
        assert digests(backup) == before
        with pytest.raises(FileExistsError):
            upgrade.prepare_rollback(backup, 'fixture', checkout)
        assert digests(backup) == before
    finally:
        subprocess.run(['chmod', '-R', 'u+w', str(backup)], check=True)


def test_prepare_checks_digest_before_extraction(tmp_path):
    backup = retained(tmp_path)
    (backup / 'original-configurations.tar').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='digest'):
        upgrade.prepare_rollback(backup, 'bad', tmp_path)
    assert not (backup / 'rollback-bad').exists()


def test_truncated_archive_is_clean_refusal(tmp_path):
    path = tmp_path / 'truncated.tar'
    with tarfile.open(path, 'w'):
        pass
    with pytest.raises(ValueError, match='incomplete archive'):
        upgrade.check_archive(path, 'a' * 64)


@pytest.mark.parametrize('first_run_layout', [False, True])
def test_bootstrap_and_abort_execute_without_mutating_retained_inputs(tmp_path, first_run_layout):
    from test_runbook_fragments import block
    backup = retained(tmp_path)
    if first_run_layout:
        backup = backup.rename(tmp_path / '20261118T133807Z')
    # Minimal valid image receipt; no Podman calls during archive verification.
    from test_live_upgrade import archive
    digest, = archive(backup / 'rollback-image-fixture.tar', [b'fixture'])
    image_path = backup / ('rollback-image-' + digest + '.tar')
    (backup / 'rollback-image-fixture.tar').rename(image_path)
    (backup / 'rollback-image-ids.txt').write_text(f'localhost/fixture:old {digest} []\n')
    (backup / 'rollback-images.sha256').write_text(upgrade.sha(image_path) + '  ' + image_path.name + '\n')
    (backup / 'rollback-branch.txt').write_text('fixture-branch\n')
    (backup / 'original-commit.txt').write_text('fixture-commit\n')
    (backup / 'original-running-services.txt').write_text('postgres\n')
    receipt = tmp_path / 'retained-ports.json'
    if first_run_layout:
        # Names from the only retained live backup; no payloads copied.
        names = json.loads((ROOT / 'tests/fixtures/live-upgrade/retained-root-names.json').read_text())
        assert 'original-ports.json' not in names
        assert not any(n.startswith('rollback-') and n.endswith('/') for n in names)
        for name in names:
            target = backup / name.rstrip('/')
            if name.endswith('/'):
                target.mkdir(exist_ok=True)
            elif not target.exists():
                target.touch()
        # The retained checksum file names the unusable aggregate. Corrected
        # service-named payloads are authorized only by the phase-A receipt.
        corrected = backup / 'rollback-image-postgres.tar'
        image_path.rename(corrected)
        (backup / 'rollback-images.sha256').write_text('0'*64 + '  rollback-images.tar\n')
        (backup / 'phase-a-resume-receipt.json').write_text(json.dumps(dict(saved_images=[dict(
            original_tag='localhost/fixture:old', image_id=digest, service='postgres',
            archive='/retained/rollback-image-postgres.tar', sha256=upgrade.sha(corrected))])))
        (backup / 'original-ports.json').unlink()
        ports = json.loads((ROOT / 'docs/validation/retained-backups/20261118T133807Z-ports.json').read_text())
        # Bind the names-only fixture receipt to its synthetic archive, never live data.
        ports['backup_id'] = backup.name
        ports['configuration_archive_sha256'] = upgrade.sha(backup / 'original-configurations.tar')
        receipt.write_text(json.dumps(ports))
    checkout = tmp_path / 'checkout'; checkout.mkdir()
    (checkout / 'consoles').mkdir(); (checkout / 'consoles/file').write_text('candidate')
    (checkout / '.env').write_text('# empty fixture\n')
    runtime = tmp_path / 'runtime/podman'; runtime.mkdir(parents=True)
    import socket
    server = socket.socket(socket.AF_UNIX); server.bind(str(runtime / 'podman.sock'))
    before = digests(backup)
    subprocess.run(['chmod', '-R', 'a-w', str(backup)], check=True)
    # Directory allocation requires parent write permission; retained files stay read-only.
    backup.chmod(0o700)
    env = dict(os.environ, BACKUP_DIR=str(backup), REVIEWED_CHECKOUT=str(ROOT),
               UPGRADE_TOOLS_CONTAINER='fixture', XDG_RUNTIME_DIR=str(runtime.parent), CHECKOUT=str(checkout),
               PATH=project_ports_path(tmp_path))
    if first_run_layout:
        reviewed = tmp_path / 'reviewed'
        receipts = reviewed / 'docs/validation/retained-backups'; receipts.mkdir(parents=True)
        (receipts / (backup.name + '-ports.json')).write_bytes(receipt.read_bytes())
        for name in ['live-upgrade.py', 'quiescence.py']:
            (receipts.parent / name).symlink_to(ROOT / 'docs/validation' / name)
        (reviewed / 'docs/live-upgrade-runbook.md').symlink_to(ROOT / 'docs/live-upgrade-runbook.md')
        env['REVIEWED_CHECKOUT'] = str(reviewed)
    # Only external commands are stubbed. Actual bootstrap, extraction, function capture,
    # context save and filesystem restoration all execute.
    stubs = r'''
cd() { if test "$1" = /home/rcc-vstudio/working/sql-megasamples; then builtin cd "$CHECKOUT"; else builtin cd "$@"; fi; }
podman() { return 42; }  # Bootstrap must not need a tools-container inventory.

git() { if test "$1" = rev-parse; then echo fixture-commit; fi; }
docker() { printf '%s\n' "$*" >> "$CHECKOUT/docker-calls"; }
'''
    try:
        bootstrap = block('# BEGIN rollback bootstrap\n', '# END rollback bootstrap')
        result = subprocess.run(['bash', '-eu', '-c', stubs + bootstrap], cwd=checkout, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert digests(backup) == before
        attempts = list(backup.glob('rollback-*/resume-context.bash'))
        assert len(attempts) == 1
        attempt = attempts[0].parent
        # Freeze root and all retained inputs during the preparation-only repeat.
        # A reused attempt refuses, with no writes into the frozen tree.
        backup.chmod(0o500)
        with pytest.raises(FileExistsError):
            upgrade.prepare_rollback(backup, attempt.name.removeprefix('rollback-'), checkout)
        assert digests(backup) == before
        backup.chmod(0o700)
        # Abort opens the preparation context. Fixture context includes every saved variable.
        # Abort fixture resolves its original preparation context via a command stub,
        # without creating any sidecar at the retained root.
        env['ATTEMPT_CONTEXT'] = str(attempts[0])
        # This fixture is preparation-stage, before any stop was attempted.
        abort = block('# BEGIN abort preparation\n', '# END abort preparation').replace('. "$BACKUP_DIR/resume-context.bash"', '. "$ATTEMPT_CONTEXT"')
        result = subprocess.run(['bash', '-eu', '-c', stubs + abort], cwd=checkout, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert not (checkout / 'docker-calls').exists()
        assert (checkout / 'consoles/fixture').read_bytes() == b'{}\n'
        assert digests(backup) == before
    finally:
        server.close()
        subprocess.run(['chmod', '-R', 'u+w', str(backup)], check=True)


def test_bootstrap_checks_ports_before_allocating_or_hashing_images(tmp_path):
    from test_runbook_fragments import block
    import socket
    backup = retained(tmp_path)
    runtime = tmp_path / 'runtime/podman'; runtime.mkdir(parents=True)
    (backup / 'original-running-services.txt').write_text('postgres\n')
    server = socket.socket(socket.AF_UNIX); server.bind(str(runtime / 'podman.sock'))
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen()
        (backup / 'original-ports.json').write_text(json.dumps(dict(
            engines=['postgres'], consoles=[], ports={'postgres': listener.getsockname()[1]})))
        stubs = '''
cd() { :; }
podman() { test "$1" = ps; }
'''
        env = dict(os.environ, BACKUP_DIR=str(backup), REVIEWED_CHECKOUT=str(ROOT),
                   UPGRADE_TOOLS_CONTAINER='fixture', XDG_RUNTIME_DIR=str(runtime.parent), PATH=project_ports_path(tmp_path))
        try:
            result = subprocess.run(['bash', '-eu', '-c', stubs + block(
                '# BEGIN rollback bootstrap\n', '# END rollback bootstrap')], env=env, capture_output=True, text=True)
            assert result.returncode != 0
            assert 'occupied or unavailable port' in result.stderr
            assert not list(backup.glob('rollback-*/'))
            assert 'rollback-image-ids' not in result.stderr
        finally:
            server.close()


def test_retained_ports_receipt_is_bound_to_backup_and_checked_archive(tmp_path):
    backup = retained(tmp_path)
    receipt = tmp_path / 'ports.json'
    ports = dict(backup_id=backup.name, configuration_archive_sha256=upgrade.sha(backup/'original-configurations.tar'),
                 engines=['postgres'], consoles=[], ports={'postgres': 5432})
    receipt.write_text(json.dumps(ports))
    assert upgrade.retained_ports(backup, receipt)['ports'] == {'postgres': 5432}
    ports['backup_id'] = 'another-backup'; receipt.write_text(json.dumps(ports))
    with pytest.raises(ValueError, match='ports receipt backup'):
        upgrade.retained_ports(backup, receipt)
    ports['backup_id'] = backup.name; ports['configuration_archive_sha256'] = '0'*64
    receipt.write_text(json.dumps(ports))
    with pytest.raises(ValueError, match='ports receipt configuration digest'):
        upgrade.retained_ports(backup, receipt)
    (backup/'original-configurations.tar').write_bytes(b'changed')
    with pytest.raises(ValueError, match='configuration digest mismatch'):
        upgrade.retained_ports(backup, receipt)


def test_whole_rollback_preserves_frozen_retained_file_list_and_digests(tmp_path):
    from test_runbook_fragments import RUNBOOK, context
    import re
    server=context(tmp_path,'rollback-down')
    backup=tmp_path/'retained'; attempt=tmp_path/'attempt'; checkout=tmp_path/'checkout'; checkout.mkdir()
    for name,value in {'rollback-branch.txt':'fixture','original-commit.txt':'fixture',
                       'rollback-image-ids.txt':'','original-tool-images.txt':'','rollback-image-tags.txt':'',
                       'original-running-services.txt':'','original-configurations.sha256':'',
                       'original-ports.json':'{}'}.items(): (backup/name).write_text(value)
    config=attempt/'configuration';(config/'consoles/landing').mkdir(parents=True)
    for name in ['megasamples.yaml','compose.yaml']: (config/name).write_text('{}')
    (config/'consoles/landing/index.html').write_text('original')
    (checkout/'consoles').mkdir();(checkout/'consoles/candidate').write_text('candidate')
    (checkout/'.venv').mkdir();(checkout/'.venv/fixture').write_text('candidate')
    (backup/'python-venv').mkdir();(backup/'python-venv/fixture').write_text('original')
    before=digests(backup)
    subprocess.run(['chmod','-R','a-w',str(backup)],check=True)
    body=RUNBOOK.read_text().split('## Roll back\n',1)[1].split('### Partial original restart',1)[0]
    shell='\n'.join(re.findall(r'```sh\n(.*?)```',body,re.S))
    stubs=r'''
python3() {
 case "$2" in
 rollback-route) printf '{"outcome":"PASS","route":"down-capture"}';;
 *) if test "$1" = -c; then command python3 "$@"; else cat >/dev/null; fi;;
 esac
}
podman() {
 case "$1 $2" in
 'volume exists') return 1;;
 'volume inspect') printf /scratch/target;;
 esac
}
docker() { :; }
git() { if test "$1" = rev-parse; then echo fixture; fi; }
sha256sum() { :; }
bash() { :; }
'''
    # Context cd is retained by design: append an explicit fixture checkout after source.
    shell=shell.replace('. "$CONTEXT_FILE"','. "$CONTEXT_FILE"\ncd "$CHECKOUT"\nCONFIG_DIR="$ATTEMPT_DIR/configuration"')
    try:
        env=dict(os.environ,CONTEXT_FILE=str(tmp_path/'resume-context.bash'),CHECKOUT=str(checkout))
        result=subprocess.run(['bash','-eu','-c',stubs+shell],cwd=checkout,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert digests(backup)==before
        assert sorted(p.relative_to(backup).as_posix() for p in backup.rglob('*') if p.is_file())==sorted(before)
        # Execute configuration restoration again: no nested console or venv trees.
        from test_runbook_fragments import block
        repeat='. "$CONTEXT_FILE"\ncd "$CHECKOUT"\nCONFIG_DIR="$ATTEMPT_DIR/configuration"\n'+block('# BEGIN restore continuation\n','# END restore continuation')
        result=subprocess.run(['bash','-eu','-c',stubs+repeat],env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert not (checkout/'consoles/consoles').exists()
        assert not (checkout/'.venv/python-venv').exists()
        assert (checkout/'.venv/fixture').read_text()=='original'
        assert digests(backup)==before
    finally:
        server.close();subprocess.run(['chmod','-R','u+w',str(backup)],check=True)


def test_configuration_modes_survive_private_umask(tmp_path):
    backup=retained(tmp_path)
    previous=os.umask(0o077)
    try: target=upgrade.prepare_rollback(backup,'private-umask',tmp_path)
    finally: os.umask(previous)
    assert (target/'configuration/consoles').stat().st_mode & 0o777 == 0o755
    assert (target/'configuration/consoles/fixture').stat().st_mode & 0o777 == 0o644
    assert target.stat().st_mode & 0o777 == 0o700


def test_explicit_archived_directory_modes_restored(tmp_path):
    backup=retained(tmp_path)
    with tarfile.open(backup/'original-configurations.tar','w') as archive:
        for name,mode in [('consoles',0o755),('consoles/workspace',0o775),('consoles/private',0o700)]:
            member=tarfile.TarInfo(name);member.type=tarfile.DIRTYPE;member.mode=mode;archive.addfile(member)
    (backup/'original-configurations.sha256').write_text(upgrade.sha(backup/'original-configurations.tar')+'  original-configurations.tar\n')
    mask=os.umask(0o077)
    try: target=upgrade.prepare_rollback(backup,'directory-modes',tmp_path)
    finally: os.umask(mask)
    assert (target/'configuration/consoles/workspace').stat().st_mode & 0o777 == 0o775
    assert (target/'configuration/consoles/private').stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize('selected_console',[False,True])
def test_bootstrap_occupied_unselected_console_port(tmp_path,selected_console):
    from test_runbook_fragments import block
    import socket
    backup=retained(tmp_path)
    runtime=tmp_path/'runtime/podman';runtime.mkdir(parents=True)
    server=socket.socket(socket.AF_UNIX);server.bind(str(runtime/'podman.sock'))
    try:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            (backup/'original-ports.json').write_text(json.dumps(dict(engines=['sqlite'],consoles=['landing'],ports={'landing':listener.getsockname()[1]})))
            (backup/'original-running-services.txt').write_text('sqlite\n'+('landing\n' if selected_console else ''))
            prefix=block('# BEGIN rollback bootstrap\n','# END rollback bootstrap').split('TEARDOWN_ATTEMPT=',1)[0]
            env=dict(os.environ,BACKUP_DIR=str(backup),REVIEWED_CHECKOUT=str(ROOT),UPGRADE_TOOLS_CONTAINER='fixture',XDG_RUNTIME_DIR=str(runtime.parent),PATH=project_ports_path(tmp_path))
            result=subprocess.run(['bash','-eu','-c','cd() { :; }\n'+prefix+'\necho PORTS_PASSED'],env=env,capture_output=True,text=True)
            assert (result.returncode==0)==(not selected_console),result.stderr
            assert ('occupied or unavailable port' in result.stderr)==selected_console
    finally: server.close()
