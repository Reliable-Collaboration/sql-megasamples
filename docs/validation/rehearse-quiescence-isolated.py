#!/usr/bin/env python3
"""DL-088 published-bridge proof in the existing isolated store, never live.

Source sql-megasamples-upgrade-env/env.sh first. Creates only dl088-proof-*
objects. Raw evidence stays private under build; stdout contains counts/classes.
The shared store helper is inspected, never signalled. Existing stacks stay up.
"""
import collections
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT.parent / 'sql-megasamples-upgrade-env'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


gate = module('gate', 'quiescence.py')
upgrade = module('upgrade', 'live-upgrade.py')


def run(args, *, check=True, timeout=40):
    return subprocess.run(args, text=True, capture_output=True, check=check, timeout=timeout)


def pod(*args):
    return run(['podman', *args]).stdout.strip()


def summary(report):
    return dict(outcome=report['outcome'], counts=report['counts'],
                refusals=dict(collections.Counter(r['reason'] for r in report['refusals'])),
                holds=dict(collections.Counter(r['reason'] for r in report['holds'])),
                limitations=dict(collections.Counter(r['operation'].split('/')[0] for r in report['limitations'])),
                shared_consumers=len(report['shared_consumers']))


def inventory():
    names = pod('ps', '-a', '--format', '{{.Names}}').splitlines()
    return sorted(pod('inspect', '-f', '{{.Name}}|{{.Id}}|{{.Image}}|{{.State.Status}}|{{.State.StartedAt}}',
                      *names).splitlines())


def main():
    os.umask(0o077)
    assert Path.cwd() == ROOT
    assert os.environ.get('CONTAINERS_STORAGE_CONF') == str(ENV / 'storage.conf')
    assert os.environ.get('CONTAINERS_CONF') == str(ENV / 'containers.conf')
    assert os.environ.get('DOCKER_HOST') == 'unix://' + str(ENV / 'podman.sock')
    assert pod('info', '--format', '{{.Store.GraphRoot}}') == str(ENV / 'graph')
    assert not pod('ps', '-aq', '--filter', 'name=dl088-proof-')
    before = inventory()
    assert len(before) == 12
    out = Path(tempfile.mkdtemp(prefix='dl088-proof-', dir=ROOT / 'build'))
    project = out.name
    receipt = dict(at=datetime.now(timezone.utc).isoformat(), results={}, artifacts=str(out.relative_to(ROOT)))
    gate.private_write(out / 'isolated-before.json', before)
    image = pod('inspect', '-f', '{{.Image}}', 'megasamples-landing')
    receipt['image_id'] = image
    receipt['image_repo_digests'] = json.loads(pod('image', 'inspect', '-f', '{{json .RepoDigests}}', image))
    data = out / 'data'
    data.mkdir()
    (data / 'fixture').write_text('scratch only\n')
    # Check an available loopback port before Compose, then prove the listener.
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    receipt['port_precheck'] = dict(status='Passed', address_class='loopback', ports=1)
    config = dict(services={
        name: dict(image='sha256:' + image.removeprefix('sha256:'), pull_policy='never',
                   entrypoint=['/bin/sh', '-c', 'trap "exit 0" TERM; while :; do sleep 1; done'],
                   volumes=[str(data) + ':/fixture:rw', 'scratch:/scratch'],
                   **({'ports': [f'127.0.0.1:{port}:8080']} if name == 'a' else {}))
        for name in ('a', 'b')}, volumes={'scratch': {}}, networks={'default': {}})
    compose_file = out / 'compose.json'
    compose_file.write_text(json.dumps(config, indent=2) + '\n')
    api = None
    stopped_helpers = []
    gate.pod = pod
    upgrade.pod = pod

    def compose(*args):
        result = run(['docker', 'compose', '-p', project, '-f', str(compose_file), *args], timeout=55)
        return result.stdout.strip()

    def save_receipt():
        # This harness owns the mutable receipt; capture/report inputs stay exclusive.
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def verify(name, capture, expected):
        # A new bash and interpreter, using only the retained capture and env.sh.
        result = run(['bash', '-eu', '-c', '. "$1"; test "$CONTAINERS_STORAGE_CONF" = "$2"; '
                      'exec python3 "$3" verify "$4"', 'fresh-shell', str(ENV / 'env.sh'),
                      str(ENV / 'storage.conf'), str(Path(__file__).with_name('quiescence.py')), str(capture)],
                     check=False, timeout=55)
        report = json.loads(result.stdout)
        gate.private_write(out / (name + '.json'), report)
        receipt['results'][name] = dict(status='Passed' if report['outcome'] == expected else 'Failed', **summary(report))
        save_receipt()
        assert report['outcome'] == expected, (name, summary(report))
        assert result.returncode == {'PASS': 0, 'REFUSE': 1, 'HOLD': 2}[expected]
        print(name, json.dumps(receipt['results'][name]), flush=True)
        return report

    try:
        if not (ENV / 'podman.sock').is_socket():
            api_env = dict(os.environ, CONTAINERS_CONF_OVERRIDE=str(ROOT / 'build/upgrade-evidence/containers-slirp.conf'))
            with (out / 'api.log').open('w') as log:
                api = subprocess.Popen(['podman', 'system', 'service', '--time=0', os.environ['DOCKER_HOST']],
                                       env=api_env, stdout=log, stderr=log)
            for _ in range(100):
                if (ENV / 'podman.sock').is_socket():
                    break
                assert api.poll() is None
                time.sleep(.05)
        assert (ENV / 'podman.sock').is_socket()
        compose('up', '-d')
        names = pod('ps', '-a', '--format', '{{.Names}}', '--filter', 'label=com.docker.compose.project=' + project).splitlines()
        assert len(names) == 2
        with socket.create_connection(('127.0.0.1', port), timeout=3):
            pass
        unpublished = compose('ps', '-q', 'b')
        publication = pod('inspect', '-f', gate.CAPTURE_FORMAT, unpublished).split('|')[4]
        receipt['unpublished-port-predicate'] = dict(status='Passed' if publication == 'false' else 'Failed',
            reason='Exposed image ports without host bindings do not require a dedicated helper')
        assert publication == 'false', 'exposed but unpublished ports must not require a forwarding helper'
        snapshot, capture = out / 'before.json', out / 'capture.json'
        upgrade.snapshot(snapshot, project, names, phase='candidate-teardown')
        result = gate.capture(snapshot, capture)
        assert result['outcome'] == 'PASS', result
        saved = json.loads(capture.read_text())
        receipt['capture'] = dict(status='Passed', containers=len(saved['containers']), sources=len(saved['sources']),
                                  process_classes=dict(collections.Counter(p['role'] for p in saved['processes'])),
                                  shared_helper_class=saved['shared_helper']['comm'])
        assert saved['shared_helper']
        dedicated = [p for p in saved['processes'] if p['role'] == 'dedicated helper']
        assert dedicated and all(p['comm'].startswith('rootlessport') for p in dedicated)
        compose('stop', '-t', '2')
        upgrade.exited(snapshot, out / 'stopped.json', phase='candidate-teardown')
        report = verify('published-bridge-stopped', capture, 'PASS')
        assert report['shared_consumers']
        compose('rm', '-f', 'a')
        snapshot.unlink()
        verify('partial-removal-fresh-shell', capture, 'PASS')
        # The isolated stack must keep running, so removing its legitimate shared
        # consumers to reach zero is forbidden. A second project shares them too.
        receipt['results']['shared-helper-with-consumers'] = dict(status='Passed',
            outcome=report['outcome'], shared_consumers=len(report['shared_consumers']),
            helper_class=saved['shared_helper']['comm'], reason='Survival reported without refusal; consumers independently inspected')
        receipt['results']['shared-helper-without-consumers'] = dict(status='Unsupported',
            reason='The isolated stack must remain running and consumes this same store helper. A second scratch project cannot remove those consumers.')
        # Dedicated helper survivor fixture follows the ordinary lifecycle proof.
        compose('up', '-d')
        names = pod('ps', '-a', '--format', '{{.Names}}', '--filter', 'label=com.docker.compose.project=' + project).splitlines()
        second_snapshot, second_capture = out / 'survivor-before.json', out / 'survivor-capture.json'
        upgrade.snapshot(second_snapshot, project, names, phase='candidate-teardown')
        assert gate.capture(second_snapshot, second_capture)['outcome'] == 'PASS'
        saved = json.loads(second_capture.read_text())
        dedicated = [p for p in saved['processes'] if p['role'] == 'dedicated helper']
        assert dedicated
        for row in dedicated:
            assert row['comm'].startswith('rootlessport')
            assert gate.process_identity(Path('/proc') / str(row['pid'])) == {k: row[k] for k in ('pid', 'start', 'comm', 'cgroups')}
            os.kill(row['pid'], signal.SIGSTOP)
            stopped_helpers.append(row)
        compose('stop', '-t', '2')
        report = verify('dedicated-helper-survivor', second_capture, 'REFUSE')
        assert any(r['reason'] == 'dedicated helper survives' for r in report['refusals'])
        for row in stopped_helpers:
            os.kill(row['pid'], signal.SIGCONT)
        stopped_helpers.clear()
        def helper_alive(row):
            try:
                p = Path('/proc') / str(row['pid'])
                return gate.process_identity(p)['start'] == row['start'] and gate.task_alive(p)
            except FileNotFoundError:
                return False
        for _ in range(50):
            if not any(helper_alive(row) for row in dedicated):
                break
            time.sleep(.1)
        assert not any(helper_alive(row) for row in dedicated)
        receipt['helper_control'] = dict(method='SIGSTOP before project stop; SIGCONT after REFUSE',
                                         dedicated_helpers=len(dedicated), ended=True,
                                         shared_helper_signalled=False)
        verify('dedicated-helper-released', second_capture, 'PASS')
    finally:
        for row in stopped_helpers:
            p = Path('/proc') / str(row['pid'])
            if p.exists() and gate.process_identity(p)['start'] == row['start']:
                os.kill(row['pid'], signal.SIGCONT)
        try:
            compose('down', '-v', '--remove-orphans', '-t', '2')
            assert not pod('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project)
            assert not pod('network', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + project)
            assert not pod('volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + project)
            after = inventory()
            gate.private_write(out / 'isolated-after.json', after)
            receipt['cleanup'] = dict(status='Passed', containers=0, networks=0, volumes=0,
                                      isolated_containers=len(after), unchanged=before == after)
            assert before == after
        finally:
            if api is not None:
                api.terminate()
                api.wait(timeout=10)
            save_receipt()
            print('private receipt', out.relative_to(ROOT) / 'receipt.json', flush=True)


if __name__ == '__main__':
    main()
