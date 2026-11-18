#!/usr/bin/env python3
"""Read-only, owner-scoped /proc quiescence evidence. No arguments or environments.

Walk from the host initial user namespace. Other owners and unreadable operations
are reported separately; decide over inspectable evidence, never certify that scope.
"""
import argparse
import array
import fcntl
import json
import os
from pathlib import Path
import sys


def under(path, base):
    return path == base or path.startswith(base.rstrip('/') + '/')


def caller_uid_mappings():
    return [tuple(map(int, line.split())) for line in Path('/proc/self/uid_map').read_text().splitlines()]


def overflow_uid():
    return int(Path('/proc/sys/kernel/overflowuid').read_text())


def start_time(process):
    # stat's comm can contain spaces and parentheses; starttime is field 22.
    return (process / 'stat').read_text().rsplit(') ', 1)[1].split()[19]


def owner_inventory(output, proc=Path('/proc')):
    """Native-host UID evidence, paired with starttime to reject PID reuse."""
    if caller_uid_mappings() != [(0, 0, 4294967295)]:
        raise ValueError('owner inventory must run in the host initial user namespace')
    rows = {}
    for process in proc.iterdir():
        if not process.name.isdigit():
            continue
        try:
            start = start_time(process)
            line = next(line for line in (process / 'status').read_text().splitlines() if line.startswith('Uid:'))
            uids = list(map(int, line.split()[1:]))
            if len(uids) != 4 or start != start_time(process):
                raise ValueError('ownership changed during inventory')
            rows[process.name] = dict(start=start, uids=uids)
        except (OSError, ValueError, StopIteration, IndexError) as error:
            if process.exists():
                rows[process.name] = dict(error=type(error).__name__)
    with output.open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(dict(host_initial_namespace=True, processes=rows), stream)


def classify_owner(process, uid, owners=None):
    process_uid = process.stat().st_uid
    if process_uid == uid:
        return 'own'
    mappings = caller_uid_mappings()
    # In rootless unshare, every non-overflow mapped UID represents this user's
    # own host UID or allocated subordinate range. uid_map's outside IDs are in
    # the parent namespace, so comparing them with caller UID 0 is not sufficient.
    rootless = mappings != [(0, 0, 4294967295)]
    if rootless and process_uid != overflow_uid() and any(start <= process_uid < start + size for start, _, size in mappings):
        return 'owned-user-namespace'
    if owners is not None:
        entry = owners.get(process.name, {})
        try:
            if entry.get('start') != start_time(process) or len(entry.get('uids', [])) != 4:
                return 'unresolved-owner'
        except (OSError, IndexError):
            return 'unresolved-owner'
        owned = any(outside <= host_uid < outside + size
                    for host_uid in entry['uids'] for _, outside, size in mappings)
        if not owned:
            line = next(line for line in (process / 'status').read_text().splitlines() if line.startswith('Uid:'))
            current = list(map(int, line.split()[1:]))
            translated = []
            for host_uid in entry['uids']:
                translated.append(next((inside + host_uid - outside for inside, outside, size in mappings
                                        if outside <= host_uid < outside + size), overflow_uid()))
            if current != translated:
                return 'unresolved-owner'
        return 'owned-user-namespace' if owned else 'other-owner'
    # Linux NS_GET_OWNER_UID: owner of a user namespace, translated to caller's UID space.
    # Opening namespace entries of other owners may be denied: do not inspect their FDs.
    try:
        with (process / 'ns/user').open('rb') as ns:
            owner = array.array('I', [0])
            fcntl.ioctl(ns.fileno(), 0xb704, owner, True)
        if owner[0] == uid:
            return 'owned-user-namespace'
    except (PermissionError, OSError):
        pass
    # When native ptrace rules deny ns/user, uid_map remains readable. The single
    # primary mapping to our UID identifies rootless namespaces rooted in our UID.
    # Run in podman unshare so subordinate processes can then be fully inspected.
    try:
        mappings = [tuple(map(int, line.split())) for line in (process / 'uid_map').read_text().splitlines()]
        if any(inside == 0 and outside == uid and size == 1 for inside, outside, size in mappings):
            return 'owned-user-namespace'
    except (PermissionError, OSError, ValueError):
        return 'unresolved-owner'
    # A full identity map proves the initial/privileged namespace, outside our
    # rootless ownership scope. Any other unproved relationship remains unresolved.
    return 'other-owner' if mappings == [(0, 0, 4294967295)] else 'unresolved-owner'


def verify_owners(report, proc=Path('/proc')):
    """Bracket assumed-other owners with a second native-host credential sample."""
    if caller_uid_mappings() != [(0, 0, 4294967295)]:
        raise ValueError('owner verification must run in host initial user namespace')
    for pid, entry in json.loads(report.read_text())['other_owner_records'].items():
        process = proc / pid
        try:
            start = start_time(process)
            line = next(line for line in (process / 'status').read_text().splitlines() if line.startswith('Uid:'))
            current = list(map(int, line.split()[1:]))
            if start != entry['start'] or start != start_time(process) or current != entry['uids']:
                raise ValueError('ownership changed during process scan; repeat complete inventory and scan')
        except (FileNotFoundError, ProcessLookupError):
            if process.exists():
                raise ValueError('ownership inspection incomplete')


def unescape(value):
    for code, char in [('040',' '),('011','\t'),('012','\n'),('134','\\')]:
        value = value.replace('\\' + code, char)
    return value


def mount_rows(path):
    rows = []
    for line in path.read_text().splitlines():
        fields = line.split()
        rows.append((fields[2], unescape(fields[3]), unescape(fields[4])))
    return rows


def host_mounts(proc):
    return mount_rows(proc / 'self/mountinfo')


def resolve_roots(device, root, mounts):
    candidates = [(len(base), point.rstrip('/') + root[len(base):] if base != '/' else point.rstrip('/') + root)
                  for dev, base, point in mounts if dev == device and under(root, base)]
    if candidates:
        return sorted({path or '/' for _, path in candidates})
    # A namespace-private filesystem's whole root cannot itself identify a host bind.
    if root == '/':
        return []
    raise ValueError('cannot resolve mount root to host path: ' + device + ' ' + root)


def source_roots(sources, mounts):
    """Map each recorded host source onto its filesystem device and root."""
    result = []
    for source in sources:
        matches = [(len(point), dev, root, point) for dev, root, point in mounts if under(source, point)]
        if not matches:
            raise ValueError('recorded source has no host mount: ' + source)
        _, dev, root, point = max(matches)
        result.append((dev, root.rstrip('/') + source[len(point.rstrip('/')):], source))
    return result


def process_state(process):
    return (process / 'stat').read_text().rsplit(') ', 1)[1].split()[0]


def evidence(snapshot, proc=Path('/proc'), owners=None):
    if caller_uid_mappings() != [(0, 0, 4294967295)]:
        raise ValueError('scan must run in host initial user namespace, never podman unshare')
    saved = json.loads(snapshot.read_text())
    sources = {src for row in saved['containers'] for src, _ in row.get('mounts', [])}
    mounts = host_mounts(proc)
    roots = source_roots(sources, mounts)
    devices = {dev for dev, _, _ in roots}
    host_net = os.readlink('/proc/self/ns/net')
    networks = {row.get('network_namespace') for row in saved['containers']} - {None, '', host_net}
    # Only container-specific cgroups count, never shared shell/API service cgroups.
    groups = {g for row in saved['containers'] for g in row.get('cgroups', []) if '/libpod-' in g}
    identities = {row.get('id') for row in saved['containers']} - {None, ''}
    counts = dict(own=0, **{'owned-user-namespace': 0, 'other-owner': 0,
                          'unresolved-owner': 0, 'zombie': 0, 'exited': 0, 'vanished': 0})
    holders, helpers, unreadable, refusals = [], [], [], []
    for process in proc.iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        pid = int(process.name)
        row = dict(pid=pid, comm='<unreadable>', owner='unresolved-owner')
        def read(operation, action):
            try:
                return action()
            except (FileNotFoundError, ProcessLookupError):
                # Descriptor close and process exit are normal scan races.
                if not process.exists() or operation.startswith('fd/'):
                    return None
                unreadable.append(dict(row, operation=operation, error='FileNotFoundError'))
            except (OSError, ValueError) as error:
                unreadable.append(dict(row, operation=operation, error=type(error).__name__))
            return None
        owner = read('owner', lambda: classify_owner(process, os.getuid()))
        row['owner'] = owner or 'unresolved-owner'
        counts[row['owner']] += 1
        if owner == 'other-owner':
            continue
        comm = read('comm', lambda: (process / 'comm').read_text().strip())
        if comm is not None:
            row['comm'] = comm
        state = read('stat', lambda: process_state(process))
        if state in ('Z', 'X', 'x'):
            counts['zombie' if state == 'Z' else 'exited'] += 1
            continue  # No address space, descriptors or network namespace remain.
        if not process.exists():
            counts['vanished'] += 1
            continue
        if owner not in ('own', 'owned-user-namespace'):
            unreadable.append(dict(row, operation='owner', error='OwnershipUnresolved'))
            continue  # Named inspection limit, not a claim about inaccessible data.
        network = read('ns/net', lambda: os.readlink(process / 'ns/net'))
        cgroup = read('cgroup', lambda: (process / 'cgroup').read_text().splitlines()) or []
        paths = []
        for key in ('root', 'cwd'):
            target = read(key, lambda key=key: os.readlink(process / key))
            if target is not None:
                paths.append((key, target))
        fds = read('fd', lambda: list((process / 'fd').iterdir())) or []
        for fd in fds:
            target = read('fd/' + fd.name, lambda fd=fd: os.readlink(fd))
            if target is not None:
                paths.append(('fd/' + fd.name, target))
        if row['comm'].startswith(('pasta', 'slirp4netns', 'rootlessport')):
            net_refs = {network} | {target for _, target in paths if target.startswith('net:[')}
            by_network = bool(networks & net_refs)
            by_group = bool(groups & set(cgroup)) or any(
                '/libpod-' + identity + '.scope' in group for identity in identities for group in cgroup)
            belongs = by_network or by_group
            helpers.append(dict(row, network=network, cgroups=cgroup, deployment=belongs,
                                attribution='recorded network namespace' if by_network else
                                'recorded container cgroup' if by_group else 'outside recorded deployment'))
            if belongs:
                refusals.append(dict(row, reason='deployment network helper',
                                     holds=sorted(networks & net_refs) if by_network else cgroup))
        process_mounts = read('mountinfo', lambda: mount_rows(process / 'mountinfo')) or []
        for device, root, _ in process_mounts:
            if device not in devices:
                continue  # e.g. retained /asound on private /proc devices.
            try:
                targets = resolve_roots(device, root, mounts)
            except ValueError:
                refusals.append(dict(row, reason='unresolvable mount on recorded source device',
                                     holds=dict(device=device, root=root)))
                continue
            paths += [('mount-root', target) for target in targets]
        maps = read('maps', lambda: (process / 'maps').read_text()) or ''
        for line in maps.splitlines():
            fields = line.split(maxsplit=5)
            if len(fields) == 6 and fields[5].startswith('/'):
                paths.append(('mapping', fields[5]))
        matched = []
        for kind, target in paths:
            clean = target.removesuffix(' (deleted)')
            direct = any(under(clean, src) for src in sources)
            # Resolve namespace paths too (e.g. /data/file), by device and root.
            candidates = [(len(point), dev, root, point) for dev, root, point in process_mounts
                          if under(clean, point)]
            translated = False
            if candidates:
                _, dev, root, point = max(candidates)
                resolved = root.rstrip('/') + clean[len(point.rstrip('/')):]
                translated = any(dev == source_dev and under(resolved, source_root)
                                 for source_dev, source_root, _ in roots)
            if direct or translated:
                matched.append((kind, target))
        if matched:
            holders.append(dict(row, paths=matched))
            refusals.append(dict(row, reason='recorded data source held', holds=matched))
    return dict(scope='own and owned-user-namespace processes only', counts=counts,
                decision_scope='inspectable operations only; unreadable rows are not certified',
                other_owner_inspection='Not run: requires privilege',
                holders=holders, helpers=helpers, unreadable=unreadable, refusals=refusals)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == 'verify-owners':
        verify_owners(Path(sys.argv[2]))
        return
    if len(sys.argv) == 3 and sys.argv[1] == 'inventory':
        owner_inventory(Path(sys.argv[2]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--owners', type=Path)
    args = parser.parse_args()
    owners = None
    if args.owners:
        data = json.loads(args.owners.read_text())
        if data.get('host_initial_namespace') is not True:
            raise ValueError('owner inventory lacks host-namespace evidence')
        owners = data['processes']
    report = evidence(args.snapshot, owners=owners)
    print(json.dumps(report, indent=2))
    if report['refusals']:
        sys.exit(1)


if __name__ == '__main__':
    main()
