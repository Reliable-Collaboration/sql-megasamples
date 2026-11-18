"""Regression checks for the live run's archive and preparation failures."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tarfile
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location('live_upgrade', Path(__file__).parents[1] / 'docs/validation/live-upgrade.py')
upgrade = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upgrade)


def archive(path, configs):
    with tarfile.open(path, 'w') as out:
        entries = []
        for content in configs:
            digest = hashlib.sha256(content).hexdigest()
            filename = digest + '.json'
            info = tarfile.TarInfo(filename)
            info.size = len(content)
            out.addfile(info, io.BytesIO(content))
            entries.append({'Config': filename, 'RepoTags': ['localhost/first:old', 'localhost/second:old'], 'Layers': []})
        content = json.dumps(entries).encode()
        info = tarfile.TarInfo('manifest.json')
        info.size = len(content)
        out.addfile(info, io.BytesIO(content))
    return [hashlib.sha256(c).hexdigest() for c in configs]


def test_old_multi_tag_archive_is_not_two_images(tmp_path):
    path = tmp_path / 'old.tar'
    first, = archive(path, [b'first image'])
    upgrade.check_archive(path, first)
    with pytest.raises(ValueError, match='configuration'):
        upgrade.check_archive(path, hashlib.sha256(b'second image').hexdigest())


def test_archive_checks_configuration_bytes_and_single_image(tmp_path):
    path = tmp_path / 'image.tar'
    first, second = archive(path, [b'first', b'second'])
    with pytest.raises(ValueError, match='one image'):
        upgrade.check_archive(path, first)
    archive(path, [b'changed'])
    with pytest.raises(ValueError, match='configuration'):
        upgrade.check_archive(path, first)


def test_save_load_retags_and_checks_ids(tmp_path, monkeypatch):
    ids = {tag: hashlib.sha256(content).hexdigest() for tag, content in [('localhost/a:old', b'a'), ('localhost/b:old', b'b')]}
    (tmp_path / 'rollback-image-ids.txt').write_text(''.join(f'{tag} sha256:{digest} []\n' for tag, digest in ids.items()))
    store = {}  # Loading must establish image identity; tagging must preserve it.
    calls = []
    def pod(*args):
        calls.append(args)
        if args[0] == 'save':
            archive(Path(args[args.index('-o') + 1]), [b'a' if args[-1].removeprefix('sha256:') == ids['localhost/a:old'] else b'b'])
        elif args[0] == 'load':
            with tarfile.open(args[-1]) as src:
                for entry in json.load(src.extractfile('manifest.json')):
                    image = hashlib.sha256(src.extractfile(entry['Config']).read()).hexdigest()
                    store[image] = image
                    for tag in entry['RepoTags']:
                        store[tag] = image
        elif args[:2] == ('image', 'tag'):
            store[args[-1]] = store[args[-2].removeprefix('sha256:')]
        elif args[:2] == ('image', 'inspect'):
            return 'sha256:' + store[args[-1]]
        return ''
    monkeypatch.setattr(upgrade, 'pod', pod)
    upgrade.save_images(tmp_path)
    upgrade.load_images(tmp_path)
    assert {tag: store[tag] for tag in ids} == ids
    assert len([c for c in calls if c[0] == 'save']) == 2
    # A wrong restoration must be detected, even if both tags exist.
    def wrong(*args):
        if args[:2] == ('image', 'tag'):
            return pod('image', 'tag', next(iter(ids.values())), args[-1])
        return pod(*args)
    monkeypatch.setattr(upgrade, 'pod', wrong)
    with pytest.raises(ValueError, match='tag-to-ID'):
        upgrade.load_images(tmp_path)
    # Corrupt the LATER archive: even the first must not be loaded.
    (tmp_path / upgrade.archive_name(list(ids.values())[1])).write_bytes(b'corrupt')
    calls.clear()
    with pytest.raises(ValueError, match='digest'):
        upgrade.load_images(tmp_path)
    assert not calls


def test_retained_live_phase_a_layout(tmp_path, monkeypatch):
    layout = json.loads((Path(__file__).parent / 'fixtures/live-phase-a-layout.json').read_text())
    rows, saved = [], []
    for entry in layout['archives']:
        path = tmp_path / entry['archive']
        image, = archive(path, [entry['service'].encode()])
        tag = 'localhost/sql-megasamples-' + entry['service'] + ':rollback-20261118T133807Z'
        rows.append(f'{tag} sha256:{image} []')
        saved.append(dict(entry, image_id='sha256:' + image, original_tag=tag,
                          sha256=upgrade.sha(path)))
    (tmp_path / 'rollback-image-ids.txt').write_text('\n'.join(rows) + '\n')
    (tmp_path / 'rollback-images.sha256').write_text(layout['checksum_file'])
    (tmp_path / 'phase-a-resume-receipt.json').write_text(json.dumps({'saved_images': saved}))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert len(upgrade.check_images(tmp_path)) == len(saved)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    # Receipt cannot silently substitute another tag or an unchecked archive.
    saved[-1]['original_tag'] = saved[0]['original_tag']
    (tmp_path / 'phase-a-resume-receipt.json').write_text(json.dumps({'saved_images': saved}))
    with pytest.raises(ValueError):
        upgrade.check_images(tmp_path)


def test_port_precheck_refuses_own_listener():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        endpoint = ('127.0.0.1', listener.getsockname()[1])
        with pytest.raises(ValueError, match='occupied'):
            upgrade.check_ports([endpoint])
    upgrade.check_ports([endpoint])


def test_running_ports_uses_selected_docker_socket_without_reading_credentials(monkeypatch):
    calls = []
    def command(args, **kwargs):
        calls.append(args)
        if args[1] == 'ps':
            return 'owned-container\n'
        return json.dumps({'80/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '8080'}]})
    monkeypatch.setattr(upgrade.subprocess, 'check_output', command)
    assert upgrade.running_ports('selected-project') == {('127.0.0.1', 8080)}
    assert all(call[0] == 'docker' for call in calls)
    assert calls[0] == ['docker', 'ps', '--filter', 'label=com.docker.compose.project=selected-project', '-q']
    assert calls[1] == ['docker', 'inspect', '-f', '{{json .NetworkSettings.Ports}}', 'owned-container']


def test_missing_model_blocks_scratch_checkout_and_transfer_checks_digest(tmp_path):
    source, target, bundle = [tmp_path / name for name in ('source', 'checkout', 'bundle')]
    paths = ['build/postgres/wideworldimporters_dw/model.json', 'build/sqlite/wideworldimporters_dw/model.json']
    for rel in paths:
        path = source / rel
        path.parent.mkdir(parents=True)
        path.write_text('{"tables": []}')
    upgrade.export_metadata(source, bundle, paths)
    upgrade.install_metadata(target, bundle, paths)
    upgrade.check_metadata(target, bundle, paths)
    (target / paths[1]).unlink()
    with pytest.raises(ValueError, match='missing'):
        upgrade.check_metadata(target, bundle, paths)
    (bundle / paths[0]).write_text('changed')
    with pytest.raises(ValueError, match='digest'):
        upgrade.install_metadata(target, bundle, paths)
    assert not (target / paths[1]).exists()


def test_metadata_does_not_overwrite_different_existing_model(tmp_path):
    source, target, bundle = [tmp_path / name for name in ('source', 'checkout', 'bundle')]
    rel = 'build/postgres/sakila/model.json'
    for root, content in [(source, '{}'), (target, 'different')]:
        (root / rel).parent.mkdir(parents=True)
        (root / rel).write_text(content)
    upgrade.export_metadata(source, bundle, [rel])
    with pytest.raises(ValueError, match='differs'):
        upgrade.install_metadata(target, bundle, [rel])
    assert (target / rel).read_text() == 'different'


def test_metadata_includes_hub_observations_for_live_counts(tmp_path, monkeypatch):
    from megasamples import config, datasets
    path = tmp_path / 'docs/validation/credential-prerequisite-2026-11-18.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'prepared_candidate': {'datasets': {'postgres': ['feed']}}}))
    monkeypatch.setattr(upgrade, 'ROOT', tmp_path)
    monkeypatch.setattr(config, 'load', lambda: SimpleNamespace(engines=['postgres'], datasets=lambda _: ['feed']))
    monkeypatch.setattr(datasets, 'load', lambda _: {'database': 'feed_db', 'live': True})
    assert upgrade.required_metadata() == ['build/live/feed.observed.yaml', 'build/postgres/feed_db/model.json']


@pytest.mark.parametrize('gate', ['save-images', 'check-metadata', 'ports --allow-running-project'])
def test_runbook_prepares_before_downtime(gate):
    text = (Path(__file__).parents[1] / 'docs/live-upgrade-runbook.md').read_text()
    preparation, _ = text.split('# Downtime starts here.', 1)
    assert gate in preparation, f'missing pre-downtime gate: {gate}'


def test_runbook_ms_tool_executes_heredoc(tmp_path):
    text = (Path(__file__).parents[1] / 'docs/live-upgrade-runbook.md').read_text()
    function = re.search(r'^ms_tool\(\) \{\n.*?^\}', text, re.M | re.S)[0]
    # Emulate exec's documented stdin behavior without requiring a container daemon.
    fake = tmp_path / 'podman'
    fake.write_text('#!/bin/sh\nif [ "$2" = "-i" ]; then exec python3 -; fi\n')
    fake.chmod(0o755)
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + os.environ['PATH'],
               DOCKER_HOST='unix:///unused-test-socket', UPGRADE_TOOLS_CONTAINER='fixture')
    result = subprocess.run(['bash', '-c', function + "\nms_tool python3 - <<'PY'\nprint('stdin-executed')\nPY\n"],
                            env=env, capture_output=True, text=True, check=True)
    assert result.stdout == 'stdin-executed\n'


@pytest.mark.parametrize('action,log', [('stop', 'stop.log'), ('down', 'rollback-down.log')])
def test_runbook_teardown_preserves_compose_status(tmp_path, action, log):
    text = (Path(__file__).parents[1] / 'docs/live-upgrade-runbook.md').read_text()
    guard = re.search(r'if (?:! )?docker compose[^\n]* ' + action + r' > .*?^fi', text, re.M | re.S)[0]
    env = dict(os.environ, BACKUP_DIR=str(tmp_path))
    result = subprocess.run(['bash', '-c', 'docker() { return 37; }\n' + guard + '\necho unsafe-fallthrough'],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 37
    assert (tmp_path / (log + '.exit-code')).read_text() == '37\n'
    assert 'unsafe-fallthrough' not in result.stdout


def test_runbook_context_restores_fresh_maintenance_shell(tmp_path):
    text = (Path(__file__).parents[1] / 'docs/live-upgrade-runbook.md').read_text()
    snapshot = re.search(r'# Save non-secret maintenance context\.\n(.*?)# End saved context\.', text, re.S)
    assert snapshot, 'missing recoverable maintenance shell context'
    function = re.search(r'^ms_tool\(\) \{\n.*?^\}', text, re.M | re.S)[0]
    names = ['UPGRADE_ID', 'UPGRADE_HELPER', 'UPGRADE_TOOLS_CONTAINER', 'MEGASAMPLES_PY',
             'METADATA_BUNDLE', 'DOCKER_HOST', 'MEGASAMPLES_LIVE_API_PID']
    env = dict(os.environ, **{name: "fixture 'with spaces' $" for name in names}, BACKUP_DIR=str(tmp_path))
    subprocess.run(['bash', '-c', function + '\n' + snapshot[1]], env=env, cwd=tmp_path, check=True)
    result = subprocess.run(['bash', '-c', '. "$CONTEXT"; type ms_tool >/dev/null; printf "%s" "$UPGRADE_ID"'],
                            env={'PATH': os.environ['PATH'], 'CONTEXT': str(tmp_path / 'resume-context.bash')},
                            capture_output=True, text=True, check=True)
    assert result.stdout == env['UPGRADE_ID']
    assert (tmp_path / 'resume-context.bash').stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('engine,reply,expected', [
    ('postgres', b'S', 'PostgreSQL'), ('postgres', b'N', 'PostgreSQL'),
    ('mysql', b'\x0a\x00\x00\x00\x0ascratch\x00x', 'scratch'),
    ('postgres', b'X', None), ('postgres', b'', None),
    ('mysql', b'\x0a\x00', None),
    ('mysql', b'\x03\x00\x00\x00\xffxx', None),
    ('mysql', b'\x03\x00\x00\x00\x09x\x00', None),
])
def test_forwarded_protocol_socket_fixture(engine, reply, expected):
    import threading
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        def serve():
            with listener.accept()[0] as stream:
                if engine == 'postgres':
                    assert upgrade.receive(stream, 8) == bytes.fromhex('0000000804d2162f')
                stream.sendall(reply)
        worker = threading.Thread(target=serve)
        worker.start()
        try:
            if expected:
                assert expected in upgrade.forwarded_protocol(engine, *listener.getsockname())
            else:
                with pytest.raises(ValueError):
                    upgrade.forwarded_protocol(engine, *listener.getsockname())
        finally:
            worker.join(timeout=5)
            assert not worker.is_alive()


def test_retained_helper_ports_needs_no_checkout(tmp_path):
    helper = tmp_path / 'live-upgrade.py'
    helper.write_bytes(Path(upgrade.__file__).read_bytes())
    ports = tmp_path / 'ports.json'
    ports.write_text(json.dumps({'engines': ['postgres'], 'consoles': ['landing'],
                                 'ports': {'postgres': 0, 'landing': 0}}))
    result = subprocess.run(['python3', '-I', str(helper), 'ports', '--port-config', str(ports)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_port_selection_and_exemption(monkeypatch):
    from megasamples import config
    cfg = SimpleNamespace(engines=['postgres', 'sqlite'], consoles=['landing'],
                          ports={'postgres': 5432, 'landing': 8080, 'sqlite': 999}, validate=lambda: [])
    monkeypatch.setattr(config, 'load', lambda *a: cfg)
    check = upgrade.check_ports
    calls = []
    monkeypatch.setattr(upgrade, 'check_ports', lambda endpoints, allowed: calls.append((endpoints, allowed)))
    monkeypatch.setattr(upgrade, 'running_ports', lambda project: {('127.0.0.1', 8080)} if project == 'owned' else set())
    monkeypatch.setattr('sys.argv', ['helper', 'ports', '--consoles-only', '--allow-running-project', 'owned'])
    upgrade.main()
    assert calls == [([('127.0.0.1', 8080)], {('127.0.0.1', 8080)})]
    calls.clear()
    monkeypatch.setattr('sys.argv', ['helper', 'ports'])
    upgrade.main()
    assert calls == [([('127.0.0.1', 5432), ('127.0.0.1', 8080)], ())]
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen()
        endpoint = listener.getsockname()
        # Test real refusal/exemption separately from selection's call recorder.
        check([endpoint], {endpoint})
        with pytest.raises(ValueError, match='occupied'):
            check([endpoint], {('127.0.0.1', endpoint[1] + 1)})
