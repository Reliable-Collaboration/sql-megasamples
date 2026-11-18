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
    (backup / 'failed-candidate.env').write_text('# retained empty fixture\n')
    (backup / 'phase-a-resume-receipt.json').write_text('{}')
    return backup


def digests(backup):
    return {str(p.relative_to(backup)): upgrade.sha(p) for p in backup.rglob('*')
            if p.is_file() and not (len(p.relative_to(backup).parts) > 1 and p.relative_to(backup).parts[0].startswith('rollback-'))}


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


def test_bootstrap_and_abort_execute_without_mutating_retained_inputs(tmp_path):
    from test_runbook_fragments import block
    backup = retained(tmp_path)
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
               UPGRADE_TOOLS_CONTAINER='fixture', XDG_RUNTIME_DIR=str(runtime.parent), CHECKOUT=str(checkout))
    # Only external commands are stubbed. Actual bootstrap, extraction, function capture,
    # context save and filesystem restoration all execute.
    stubs = r'''
cd() { if test "$1" = /home/rcc-vstudio/working/sql-megasamples; then builtin cd "$CHECKOUT"; else builtin cd "$@"; fi; }
podman() {
  while test "$#" -gt 0; do
    if test "$1" = export-ports; then shift; printf '{"engines":["postgres"],"consoles":[],"ports":{"postgres":5432}}' > "$1"; return; fi
    shift
  done
  return 42
}
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
