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
    with tarfile.open(path) as archive:
        manifest = json.load(archive.extractfile('manifest.json'))
        if len(manifest) != 1:
            raise ValueError('archive must contain exactly one image')
        content = archive.extractfile(manifest[0]['Config']).read()
        if hashlib.sha256(content).hexdigest() != expected.removeprefix('sha256:'):
            raise ValueError('archive configuration ID differs from recorded image')


def archive_name(image):
    return 'rollback-image-' + image + '.tar'


def save_images(backup):
    rows = image_rows(backup)
    digests = []
    for image in dict.fromkeys(image for _, image in rows):
        path = backup / archive_name(image)
        if path.exists():
            raise ValueError('archive already exists; use a new backup directory')
        # One full image ID per docker archive. No multi-image positional arguments.
        pod('save', '--format=docker-archive', '-o', str(path), 'sha256:' + image)
        path.chmod(0o600)
        check_archive(path, image)
        digests.append(sha(path) + '  ' + path.name)
    (backup / 'rollback-images.sha256').write_text('\n'.join(digests) + '\n')
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
    for action in ('save-images', 'check-images', 'load-images'):
        sub.add_parser(action).add_argument('backup', type=Path)
    for action in ('export-metadata', 'install-metadata', 'check-metadata'):
        p = sub.add_parser(action)
        p.add_argument('bundle', type=Path)
        p.add_argument('--root', type=Path, default=ROOT)
    p = sub.add_parser('ports')
    p.add_argument('--allow-running-project')
    p.add_argument('--consoles-only', action='store_true')
    p = sub.add_parser('forwarded-protocol')
    p.add_argument('engine', choices=['postgres', 'mysql'])
    p.add_argument('host')
    p.add_argument('port', type=int)
    args = parser.parse_args()
    if args.command.endswith('-images'):
        globals()[args.command.replace('-', '_')](args.backup)
    elif args.command.endswith('-metadata'):
        globals()[args.command.replace('-', '_')](args.root, args.bundle, required_metadata())
    elif args.command == 'ports':
        from megasamples import config
        cfg = config.load()
        problems = cfg.validate()
        if problems:
            raise ValueError('; '.join(problems))
        services = cfg.consoles if args.consoles_only else [*cfg.engines, *cfg.consoles]
        endpoints = [('127.0.0.1', int(cfg.ports[name])) for name in services if name in cfg.ports and name != 'sqlite']
        allowed = running_ports(args.allow_running_project) if args.allow_running_project else ()
        check_ports(endpoints, allowed)
    else:
        print(forwarded_protocol(args.engine, args.host, args.port))
    print('Passed: ' + args.command)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit('Failed: ' + str(error))
