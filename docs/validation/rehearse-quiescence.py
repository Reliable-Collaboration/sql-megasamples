#!/usr/bin/env python3
"""Native /proc proof, using only an isolated scratch bind and owned processes.

Source the isolated env.sh. No existing container is stopped or modified. Private
reports stay in build; the portable receipt contains counts and classes only.
"""
import collections
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT.parent / 'sql-megasamples-upgrade-env'
spec = importlib.util.spec_from_file_location('scanner', Path(__file__).with_name('quiescence.py'))
scanner = importlib.util.module_from_spec(spec); spec.loader.exec_module(scanner)


def pod(*args):
    return subprocess.check_output(['podman', *args], text=True).strip()


def summary(report):
    return dict(counts=report['counts'], holders=len(report['holders']),
                helpers=dict(collections.Counter('deployment' if r['deployment'] else 'outside-deployment'
                                                 for r in report['helpers'])),
                unreadable=[dict(comm=comm, operation=operation, error=error, count=count)
                            for (comm, operation, error), count in sorted(collections.Counter(
                                (r['comm'], r['operation'].split('/')[0], r['error'])
                                for r in report['unreadable']).items())],
                refusals=dict(collections.Counter(r['reason'] for r in report['refusals'])),
                holder_classes=dict(collections.Counter((r['owner'] + ':' + r['comm']) for r in report['holders'])))


def main():
    assert Path.cwd() == ROOT
    assert os.environ.get('CONTAINERS_STORAGE_CONF') == str(ENV / 'storage.conf')
    assert os.environ.get('DOCKER_HOST') == 'unix://' + str(ENV / 'podman.sock')
    assert pod('info', '--format', '{{.Store.GraphRoot}}') == str(ENV / 'graph')
    out = Path(tempfile.mkdtemp(prefix='native-', dir=ROOT / 'build/dl086/r3'))
    out.chmod(0o700)
    data = out / 'data'; data.mkdir()
    snapshot = out / 'snapshot.json'
    snapshot.write_text(json.dumps(dict(containers=[dict(mounts=[[str(data), '/data']])])))
    receipt = dict(at=datetime.now(timezone.utc).isoformat(), results={})
    def scan(name, expected):
        result = subprocess.run(['python3', str(Path(__file__).with_name('quiescence.py')), str(snapshot)],
                                capture_output=True, text=True)
        private = out / (name + '.json'); private.write_text(result.stdout); private.chmod(0o600)
        report = json.loads(result.stdout)
        assert result.returncode == expected, (name, result.returncode)
        receipt['results'][name] = dict(status='Passed', exit_code=result.returncode, **summary(report))
        return report
    scan('unheld-with-stacks-up', 0)
    holder = subprocess.Popen(['python3', '-c',
        'import pathlib,sys,time; f=pathlib.Path(sys.argv[1]).open("w"); print("ready",flush=True); time.sleep(90)',
        str(data / 'held')], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == 'ready'
        report = scan('deliberate-host-holder', 1)
        assert any(r['pid'] == holder.pid and r['comm'].startswith('python') for r in report['holders'])
    finally:
        holder.terminate(); holder.wait(timeout=10)
    scan('host-holder-ended', 0)
    name = 'dl086-native-' + out.name
    created = False
    try:
        image = pod('inspect', '-f', '{{.Image}}', 'megasamples-sqlite')
        pod('run', '-d', '--pull=never', '--name', name, '--network=none', '--health-cmd=none',
            '-v', str(data) + ':/data:rw', '--workdir=/data', '--entrypoint=/bin/sh',
            image, '-c', 'exec sleep 90')
        created = True
        report = scan('scratch-rootless-holder', 1)
        assert any(r['comm'] == 'sleep' and r['owner'] in ('own', 'owned-user-namespace') for r in report['holders'])
        pod('stop', '--time=2', name)
        scan('scratch-rootless-stopped', 0)
    finally:
        if created:
            pod('rm', '-f', name)  # Only this uniquely named container.
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(artifacts=str(out.relative_to(ROOT)), receipt=receipt), indent=2))


if __name__ == '__main__':
    main()
