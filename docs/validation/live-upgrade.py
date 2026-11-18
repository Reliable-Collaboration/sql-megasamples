#!/usr/bin/env python3
"""Replayable live-upgrade preparation. Container commands use the caller's store.

Never source .env or print rendered Compose/container configuration. Run from the
reviewed checkout; metadata selection comes from the compared candidate receipt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pod(*args):
    return subprocess.check_output(['podman', *args], text=True).strip()


def image_rows(backup):
    rows = []
    for line in (backup / 'rollback-image-ids.txt').read_text().splitlines():
        tag, image, _ = line.split(maxsplit=2)
        image = image.removeprefix('sha256:')
        if not re.fullmatch('[0-9a-f]{64}', image) or not tag.startswith('localhost/'):
            raise ValueError('invalid rollback image mapping')
        rows.append((tag, image))
    if not rows or len({tag for tag, _ in rows}) != len(rows):
        raise ValueError('empty or duplicate rollback image mapping')
    return rows


def check_archive(path, expected):
    """A tag is not identity: hash the single manifest's actual configuration."""
    try:
        with tarfile.open(path) as archive:
            manifest = json.load(archive.extractfile('manifest.json'))
            if len(manifest) != 1:
                raise ValueError('archive must contain exactly one image')
            content = archive.extractfile(manifest[0]['Config']).read()
            if hashlib.sha256(content).hexdigest() != expected.removeprefix('sha256:'):
                raise ValueError('archive configuration ID differs from recorded image')
    except (KeyError, TypeError, AttributeError, EOFError, tarfile.TarError) as error:
        raise ValueError('incomplete archive: ' + path.name) from error


def prepare_rollback(backup, attempt, checkout):
    """Read retained inputs; exclusively allocate all new rollback output."""
    if not re.fullmatch('[A-Za-z0-9-]+', attempt):
        raise ValueError('invalid rollback attempt')
    lines = (backup / 'original-configurations.sha256').read_text().splitlines()
    if len(lines) != 1:
        raise ValueError('configuration digest receipt must name one archive')
    digest, name = lines[0].split()
    if name != 'original-configurations.tar' or sha(backup / name) != digest:
        raise ValueError('configuration digest mismatch')
    target = backup / ('rollback-' + attempt)
    target.mkdir(mode=0o700)  # No exist_ok: never reuse an attempt.
    config = target / 'configuration'
    config.mkdir(mode=0o700)
    with tarfile.open(backup / name) as archive:
        archive.extractall(config, filter='data')
        # tar's data filter intentionally leaves directory modes to the caller's
        # umask. Restore safe recorded traversal modes, inside the private parent.
        modes = {m.name.rstrip('/'): m.mode & 0o755 for m in archive.getmembers() if m.isdir()}
        for directory in sorted(config.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if directory.is_dir() and not directory.is_symlink():
                directory.chmod(modes.get(directory.relative_to(config).as_posix(), 0o755))
    if (checkout / '.env').is_file():
        shutil.copyfile(checkout / '.env', target / 'failed-candidate.env')
        (target / 'failed-candidate.env').chmod(0o600)
    return target


def archive_name(image):
    return 'rollback-image-' + image + '.tar'


def save_images(backup, resume=False):
    rows = image_rows(backup)
    checksum = backup / 'rollback-images.sha256'
    if checksum.exists():
        if not resume:
            raise ValueError('archive receipt already exists; use resume-save-images to verify it')
        check_images(backup)
        return
    images = list(dict.fromkeys(image for _, image in rows))
    # Preflight ALL existing files before creating anything new.
    for image in images:
        path = backup / archive_name(image)
        if path.exists():
            if not resume:
                raise ValueError('archive already exists; use a new backup directory')
            check_archive(path, image)
    digests = []
    for image in images:
        path = backup / archive_name(image)
        if not path.exists():
            # One full image ID per docker archive. No multi-image positional arguments.
            pod('save', '--format=docker-archive', '-o', str(path), 'sha256:' + image)
            path.chmod(0o600)
        check_archive(path, image)
        digests.append(sha(path) + '  ' + path.name)
    with checksum.open('x') as out:
        out.write('\n'.join(digests) + '\n')
    check_images(backup)


def image_archives(backup, rows):
    """Return verified mapping inputs without rewriting retained backup receipts."""
    checksums = {}
    for line in (backup / 'rollback-images.sha256').read_text().splitlines():
        digest, name = line.split()
        if name in checksums or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('invalid or duplicate archive digest')
        checksums[name] = digest
    if set(checksums) == {'rollback-images.tar'}:
        # First live run: aggregate is malformed. Its checksum is NEVER used to
        # authorize a load. The phase-A correction receipt pins each replacement.
        saved = json.loads((backup / 'phase-a-resume-receipt.json').read_text())['saved_images']
        mapped, archives = [], {}
        for entry in saved:
            tag, image = entry['original_tag'], entry['image_id'].removeprefix('sha256:')
            service = entry['service']
            if not re.fullmatch('[a-z0-9-]+', service):
                raise ValueError('invalid service in phase-A receipt')
            name = 'rollback-image-' + service + '.tar'
            if Path(entry['archive']).name != name or name in archives:
                raise ValueError('invalid or duplicate phase-A archive')
            if not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
                raise ValueError('invalid phase-A digest')
            mapped.append((tag, image))
            archives[name] = (image, entry['sha256'])
        if len(mapped) != len(rows) or set(mapped) != set(rows):
            raise ValueError('phase-A receipt differs from rollback mapping')
        return archives
    expected = {archive_name(image): image for _, image in rows}
    if checksums.keys() != expected.keys():
        raise ValueError('archive digest list differs from image mapping')
    return {name: (image, checksums[name]) for name, image in expected.items()}


def check_space(backup, extra_bytes):
    if extra_bytes < 0:
        raise ValueError('extra space reserve must be nonnegative')
    images = {image for _, image in image_rows(backup)}
    image_bytes = sum(int(pod('image', 'inspect', '-f', '{{.Size}}', 'sha256:' + image)) for image in images)
    # Per-image archives duplicate shared layers; budget full Size for EACH image.
    # A second full set is loaded into scratch. 25% covers archive/metadata overhead.
    required = (2 * image_bytes * 125 + 99) // 100 + extra_bytes
    free = shutil.disk_usage(backup).free
    result = dict(unique_images=len(images), per_image_total_bytes=image_bytes,
                  copies=2, allowance_percent=25, extra_reserve_bytes=extra_bytes,
                  required_bytes=required, available_bytes=free)
    if free < required:
        raise ValueError('insufficient free space: ' + json.dumps(result))
    print(json.dumps(result))
    return result


def check_images(backup):
    rows = image_rows(backup)
    for name, (image, digest) in image_archives(backup, rows).items():
        path = backup / name
        if sha(path) != digest:
            raise ValueError('archive digest mismatch: ' + path.name)
        check_archive(path, image)
    return rows


def load_images(backup):
    rows = check_images(backup)  # Validate the WHOLE set before the first load.
    for name in image_archives(backup, rows):
        pod('load', '-i', str(backup / name))
    for tag, image in rows:
        pod('image', 'tag', 'sha256:' + image, tag)
    for tag, image in rows:
        actual = pod('image', 'inspect', '-f', '{{.Id}}', tag).removeprefix('sha256:')
        if actual != image:
            raise ValueError('rollback tag-to-ID mismatch: ' + tag)


# Deliberately select fields: full inspect output includes credential environments.
STATE_FORMAT = '{{.Name}}|{{.Id}}|{{.State.Status}}|{{.State.Running}}|{{.State.Pid}}|{{.State.ExitCode}}|{{.State.OOMKilled}}|{{.NetworkSettings.SandboxKey}}'


def container_state(container):
    name, identity, status, running, pid, code, oom, network = pod('inspect', '-f', STATE_FORMAT, container).split('|')
    return dict(name=name.lstrip('/'), id=identity, state=status, running=running == 'true',
                pid=int(pid), exit_code=int(code), oom=oom == 'true', network=network)


def write_receipt(path, data):
    with path.open('x') as out:
        json.dump(data, out, indent=2)
        out.write('\n')
    path.chmod(0o600)


def snapshot(output, project, engines, phase='original-stop', prior=None):
    rows = []
    for identity in pod('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project).split():
        row = container_state(identity)
        mounts = pod('inspect', '-f', r'{{range .Mounts}}{{printf "%s\t%s\n" .Source .Destination}}{{end}}', identity)
        row['mounts'] = [line.split('\t') for line in mounts.splitlines() if line]
        row['network_namespace'] = ''
        row['cgroups'] = []
        if row['pid'] > 0:
            process = Path('/proc') / str(row['pid'])
            try:
                row['network_namespace'] = os.readlink(process / 'ns/net')
                row['cgroups'] = (process / 'cgroup').read_text().splitlines()
            except OSError as error:
                raise ValueError('cannot record running container network/cgroup: ' + row['name']) from error
        rows.append(row)
    missing = set(engines) - {row['name'] for row in rows}
    if missing and phase in ('original-stop', 'original-restart'):
        raise ValueError('original container missing; use coordinator recovery; no cold copy or restart')
    rows += [dict(name=name, id=None, state='missing', running=False, pid=0,
                  exit_code=None, oom=False, mounts=[], network='') for name in sorted(missing)]
    if prior:
        previous = json.loads(prior.read_text())['containers']
        by_name = {r['name']: r for r in previous}
        for row in rows:
            old = by_name.get(row['name'], {})
            if row['id'] is None and old.get('id'):
                row.update(id=old['id'], mounts=old.get('mounts', []))
            if row['id'] == old.get('id'):
                for key in ('network_namespace', 'cgroups'):
                    if not row.get(key): row[key] = old.get(key, '' if key == 'network_namespace' else [])
        names = {r['name'] for r in rows}
        rows += [dict(r, state='missing', running=False, pid=0, exit_code=None, oom=False)
                 for r in previous if r['name'] not in names]
    write_receipt(output, dict(project=project, engines=engines, phase=phase, containers=rows))


def exited(before, output, removed_with=None, phase='original-stop'):
    """One state table; cold-copy eligibility is distinct from failed-candidate removal."""
    saved = json.loads(before.read_text())
    prior = json.loads(removed_with.read_text())['containers'] if removed_with else []
    prior = {row['id']: row for row in prior if row['id']}
    rows = []
    for original in saved['containers']:
        identity = original['id']
        try:
            if not identity:
                raise subprocess.CalledProcessError(1, ['missing'])
            pod('container', 'exists', identity)
        except subprocess.CalledProcessError as error:
            if error.returncode != 1:
                raise
            row = dict(original, state='missing', running=False, pid=0, exit_code=None, oom=False)
            if identity in prior:
                row['last_observed'] = prior[identity]
        else:
            row = container_state(identity)
            if row['id'] != identity:
                raise ValueError('container identity changed: ' + original['name'])
        if phase == 'original-restart' and row['state'] == 'missing':
            raise ValueError('original container missing; use coordinator recovery: ' + row['name'])
        if phase == 'restart-after':
            if row['oom']:
                raise ValueError('OOM after original start: ' + row['name'])
            if not row['running']:
                raise ValueError('running flag must be true: ' + row['name'])
            if row['pid'] <= 0:
                raise ValueError('PID must be positive: ' + row['name'])
            if row['state'] != 'running':
                raise ValueError('status must be running: ' + row['name'])
        else:
            if phase == 'original-stop' and row['oom']:
                raise ValueError('OOM before cold copy: ' + row['name'])
            if row['running']:
                raise ValueError('running flag must be false: ' + row['name'])
            if row['pid'] != 0:
                raise ValueError('PID must be 0: ' + row['name'])
            if row['state'] == 'running':
                raise ValueError('status must not be running: ' + row['name'])
            if phase == 'original-stop':
                if row['state'] not in ('created', 'exited'):
                    raise ValueError('missing/unexpected state before cold copy: ' + row['name'])
                if row['name'] in saved['engines']:
                    codes = (0, 137) if row['name'] == 'megasamples-sqlite' else (0,)
                    if row['state'] != 'exited' or row['exit_code'] not in codes:
                        raise ValueError('unexpected engine exit code before cold copy: ' + row['name'])
                row['expected_sqlite_137'] = row['name'] == 'megasamples-sqlite' and row['exit_code'] == 137
        rows.append(row)
    if phase != 'restart-after' and pod('ps', '-q', '--filter', 'label=com.docker.compose.project=' + saved['project']):
        raise ValueError('deployment container still running')
    write_receipt(output, dict(project=saved['project'], engines=saved['engines'], phase=phase, containers=rows))


def check_restored(backup, attempt, check_id):
    """Recheck selection, exact images and each independent post-start predicate."""
    if not re.fullmatch('[A-Za-z0-9-]+', check_id):
        raise ValueError('invalid restart check ID')
    selected = (backup / 'original-running-services.txt').read_text().splitlines()
    actual_names = set(pod('ps', '--filter', 'label=com.docker.compose.project=sql-megasamples',
                           '--format', '{{.Names}}').splitlines())
    if actual_names != {'megasamples-' + service for service in selected}:
        raise ValueError('running service set differs from original selection')
    images = dict(image_rows(backup))
    rows = []
    for service in selected:
        row = container_state('megasamples-' + service)
        rows.append(row)
        actual = pod('inspect', '-f', '{{.Image}}', row['id']).removeprefix('sha256:')
        expected = images['localhost/sql-megasamples-' + service + ':rollback-' + backup.name]
        if actual != expected:
            raise ValueError('restored image mismatch: ' + service)
    before = attempt / ('restart-after-' + check_id + '.json')
    write_receipt(before, dict(project='sql-megasamples', engines=[], containers=rows))
    exited(before, attempt / ('restart-after-gate-' + check_id + '.json'), phase='restart-after')


def restart_mounts(before, output, attempt):
    """Keep candidate sources after removal and include every NEW restore target."""
    if not re.fullmatch('[A-Za-z0-9-]+', attempt):
        raise ValueError('invalid rollback attempt')
    saved = json.loads(before.read_text())
    for engine in ('postgres', 'mysql', 'sqlite', 'sqlite-shared'):
        volume = 'megasamples-rollback-' + engine + '-' + attempt
        source = pod('volume', 'inspect', '-f', '{{.Mountpoint}}', volume)
        if not source.startswith('/'):
            raise ValueError('rollback volume has no absolute host mountpoint')
        saved['containers'].append(dict(name=volume, id=None, state='missing',
                                        mounts=[[source, '/restore-target']]))
    write_receipt(output, saved)


def check_ports(endpoints, allowed=()):
    for host, port in endpoints:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind((host, port))
        except OSError as error:
            if (host, port) not in allowed:
                raise ValueError(f'occupied or unavailable port: {host}:{port}') from error


def running_ports(project):
    """Only bindings of running containers in the explicitly selected project."""
    allowed = set()
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True).strip()
    ids = docker('ps', '--filter', 'label=com.docker.compose.project=' + project, '-q').split()
    for container in ids:
        # Project, state and ports only: never retrieve a credential environment.
        query = '{{json .NetworkSettings.Ports}}'
        for bindings in json.loads(docker('inspect', '-f', query, container)).values():
            for binding in bindings or []:
                allowed.add((binding['HostIp'], int(binding['HostPort'])))
    return allowed


def required_metadata():
    from megasamples import config, datasets
    candidate = json.loads((ROOT / 'docs/validation/credential-prerequisite-2026-11-18.json').read_text())['prepared_candidate']
    cfg = config.load()
    selected = {engine: cfg.datasets(engine) for engine in cfg.engines}
    if selected != candidate['datasets']:
        raise ValueError('configured datasets differ from compared candidate')
    models = {f'build/{engine}/{datasets.load(name)["database"]}/model.json'
              for engine, names in selected.items() if engine in ('postgres', 'sqlite') for name in names}
    observations = {f'build/live/{name}.observed.yaml'
                    for names in selected.values() for name in names if datasets.load(name).get('live')}
    return sorted(models | observations)


def export_metadata(root, bundle, paths):
    if bundle.exists():
        raise ValueError('metadata bundle already exists')
    for rel in paths:
        if not (root / rel).is_file():
            raise ValueError('missing verification metadata: ' + rel)
    bundle.mkdir(parents=True)
    entries = {}
    optional = [str(Path(rel).with_name('dropped.txt')) for rel in paths if '/sqlite/' in rel]
    for rel in paths + [rel for rel in optional if (root / rel).is_file()]:
        target = bundle / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, target)
        entries[rel] = sha(target)
    (bundle / 'metadata.json').write_text(json.dumps(entries, indent=2) + '\n')


def metadata_entries(bundle, paths):
    entries = json.loads((bundle / 'metadata.json').read_text())
    optional = {str(Path(rel).with_name('dropped.txt')) for rel in paths if '/sqlite/' in rel}
    if not set(paths) <= entries.keys() or not entries.keys() <= set(paths) | optional:
        raise ValueError('metadata manifest differs from compared selection')
    for rel, digest in entries.items():
        if sha(bundle / rel) != digest:
            raise ValueError('metadata bundle digest mismatch: ' + rel)
    return entries


def install_metadata(root, bundle, paths):
    entries = metadata_entries(bundle, paths)
    for rel, digest in entries.items():
        if (root / rel).exists() and sha(root / rel) != digest:
            raise ValueError('existing verification metadata differs: ' + rel)
    for rel in entries:
        target = root / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as out, (bundle / rel).open('rb') as source:
                shutil.copyfileobj(source, out)
            shutil.copymode(bundle / rel, target)
    check_metadata(root, bundle, paths)


def check_metadata(root, bundle, paths):
    for rel, digest in metadata_entries(bundle, paths).items():
        if not (root / rel).is_file():
            raise ValueError('missing verification metadata: ' + rel)
        if sha(root / rel) != digest:
            raise ValueError('verification metadata digest mismatch: ' + rel)


def receive(stream, count):
    data = b''
    while len(data) < count:
        block = stream.recv(count - len(data))
        if not block:
            raise ValueError('short protocol reply')
        data += block
    return data


def forwarded_protocol(engine, host, port):
    with socket.create_connection((host, port), timeout=5) as stream:
        if engine == 'postgres':
            stream.sendall(struct.pack('!II', 8, 80877103))  # SSLRequest
            if receive(stream, 1) not in (b'S', b'N'):
                raise ValueError('invalid PostgreSQL SSLRequest response')
            return 'PostgreSQL SSLRequest answered'
        header = receive(stream, 4)
        length = int.from_bytes(header[:3], 'little')
        if header[3] != 0 or not 1 < length <= 65536:
            raise ValueError('invalid MySQL greeting header')
        greeting = receive(stream, length)
        if greeting[0] != 10 or b'\0' not in greeting[1:]:
            raise ValueError('invalid MySQL greeting')
        return 'MySQL greeting: ' + greeting[1:].split(b'\0', 1)[0].decode('ascii')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for action in ('save-images', 'resume-save-images', 'check-images', 'load-images'):
        sub.add_parser(action).add_argument('backup', type=Path)
    for action in ('export-metadata', 'install-metadata', 'check-metadata'):
        p = sub.add_parser(action)
        p.add_argument('bundle', type=Path)
        p.add_argument('--root', type=Path, default=ROOT)
    p = sub.add_parser('check-restored')
    p.add_argument('backup', type=Path)
    p.add_argument('attempt', type=Path)
    p.add_argument('check_id')
    p = sub.add_parser('restart-mounts')
    p.add_argument('before', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--attempt', required=True)
    p = sub.add_parser('prepare-rollback')
    p.add_argument('backup', type=Path)
    p.add_argument('attempt')
    p.add_argument('checkout', type=Path)
    p = sub.add_parser('space')
    p.add_argument('backup', type=Path)
    p.add_argument('--extra-bytes', required=True, type=int)
    p = sub.add_parser('snapshot')
    p.add_argument('output', type=Path)
    p.add_argument('--project', required=True)
    p.add_argument('--engine', action='append', required=True)
    p.add_argument('--phase', choices=['original-stop', 'original-restart', 'candidate-teardown', 'restart-before', 'restart-after'], default='original-stop')
    p.add_argument('--prior', type=Path)
    p = sub.add_parser('exited')
    p.add_argument('before', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--removed-with', type=Path)
    p.add_argument('--phase', choices=['original-stop', 'original-restart', 'candidate-teardown', 'restart-before', 'restart-after'], default='original-stop')
    p = sub.add_parser('ports')
    p.add_argument('--allow-running-project')
    p.add_argument('--port-config', type=Path)
    p.add_argument('--services-file', type=Path)
    p.add_argument('--service', action='append')
    p = sub.add_parser('export-ports')
    p.add_argument('output', type=Path)
    p.add_argument('--config', type=Path)
    p = sub.choices['ports']
    p.add_argument('--consoles-only', action='store_true')
    p = sub.add_parser('forwarded-protocol')
    p.add_argument('engine', choices=['postgres', 'mysql'])
    p.add_argument('host')
    p.add_argument('port', type=int)
    args = parser.parse_args()
    if args.command == 'check-restored':
        check_restored(args.backup, args.attempt, args.check_id)
    elif args.command == 'restart-mounts':
        restart_mounts(args.before, args.output, args.attempt)
    elif args.command == 'prepare-rollback':
        print(prepare_rollback(args.backup, args.attempt, args.checkout))
    elif args.command == 'space':
        check_space(args.backup, args.extra_bytes)
    elif args.command == 'snapshot':
        snapshot(args.output, args.project, args.engine, args.phase, args.prior)
    elif args.command == 'exited':
        exited(args.before, args.output, args.removed_with, args.phase)
    elif args.command == 'resume-save-images':
        save_images(args.backup, resume=True)
    elif args.command.endswith('-images'):
        globals()[args.command.replace('-', '_')](args.backup)
    elif args.command.endswith('-metadata'):
        globals()[args.command.replace('-', '_')](args.root, args.bundle, required_metadata())
    elif args.command in ('ports', 'export-ports'):
        if args.command == 'ports' and args.port_config:
            raw = json.loads(args.port_config.read_text())
        else:
            from megasamples import config
            cfg = config.load(args.config) if args.command == 'export-ports' else config.load()
            problems = cfg.validate()
            if problems:
                raise ValueError('; '.join(problems))
            raw = dict(engines=list(cfg.engines), consoles=cfg.consoles, ports=cfg.ports)
        if args.command == 'export-ports':
            with args.output.open('x') as out:
                json.dump(raw, out, indent=2)
        else:
            services = raw['consoles'] if args.consoles_only else [*raw['engines'], *raw['consoles']]
            requested = args.services_file.read_text().splitlines() if args.services_file else args.service
            if requested is not None:
                if not set(requested) <= set(raw['engines']) | set(raw['consoles']):
                    raise ValueError('unknown service in port selection')
                services = [name for name in services if name in requested]
            endpoints = [('127.0.0.1', int(raw['ports'][name])) for name in services if name in raw['ports'] and name != 'sqlite']
            allowed = running_ports(args.allow_running_project) if args.allow_running_project else ()
            check_ports(endpoints, allowed)

    else:
        print(forwarded_protocol(args.engine, args.host, args.port))
    print('Passed: ' + args.command)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, tarfile.TarError, subprocess.CalledProcessError) as error:
        sys.exit('Failed: ' + str(error))
