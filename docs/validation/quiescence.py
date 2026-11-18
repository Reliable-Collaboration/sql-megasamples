#!/usr/bin/env python3
"""Read-only, owner-scoped /proc quiescence evidence. No arguments or environments.

Run in podman unshare for visibility into rootless descendants. Other owners are
counted, never implicitly certified. An unresolved own process refuses quiescence.
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
    if owners is not None:
        entry = owners.get(process.name, {})
        try:
            if entry.get('start') != start_time(process) or len(entry.get('uids', [])) != 4:
                return 'unresolved-owner'
        except (OSError, IndexError):
            return 'unresolved-owner'
        owned = any(outside <= host_uid < outside + size
                    for host_uid in entry['uids'] for _, outside, size in mappings)
        return 'owned-user-namespace' if owned else 'other-owner'
    # In rootless unshare, every non-overflow mapped UID represents this user's
    # own host UID or allocated subordinate range. uid_map's outside IDs are in
    # the parent namespace, so comparing them with caller UID 0 is not sufficient.
    rootless = mappings != [(0, 0, 4294967295)]
    if rootless and process_uid != overflow_uid() and any(start <= process_uid < start + size for start, _, size in mappings):
        return 'owned-user-namespace'
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


def evidence(snapshot, proc=Path('/proc'), owners=None):
    saved = json.loads(snapshot.read_text())
    sources = {src for row in saved['containers'] for src, _ in row.get('mounts', [])}
    counts = dict(own=0, **{'owned-user-namespace': 0, 'other-owner': 0, 'unresolved-owner': 0})
    holders, helpers, unreadable = [], [], []
    mounts = host_mounts(proc)
    for process in proc.iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        pid = int(process.name)
        try:
            owner = classify_owner(process, os.getuid(), owners)
            counts[owner] += 1
            if owner == 'other-owner':
                continue
            if owner == 'unresolved-owner':
                unreadable.append(dict(pid=pid, error='OwnershipUnresolved',
                                       reason='cannot prove this process belongs to another owner'))
                continue
            comm = (process / 'comm').read_text().strip()
            network = os.readlink(process / 'ns/net')
            if comm.startswith(('pasta', 'slirp4netns', 'rootlessport')):
                helpers.append(dict(pid=pid, owner=owner, comm=comm, network=network,
                                    cgroup=(process / 'cgroup').read_text().strip()))
            paths = [(key, os.readlink(process / key)) for key in ('root', 'cwd')]
            paths += [('fd/' + fd.name, os.readlink(fd)) for fd in (process / 'fd').iterdir()]
            for device, root, _ in mount_rows(process / 'mountinfo'):
                paths += [('mount-root', target) for target in resolve_roots(device, root, mounts)]
            # A shared mmap can retain a writable data file after its FD is closed.
            for line in (process / 'maps').read_text().splitlines():
                fields = line.split(maxsplit=5)
                if len(fields) == 6 and fields[5].startswith('/'):
                    paths.append(('mapping', fields[5]))
            matched = [(kind, target) for kind, target in paths
                       if any(under(target.removesuffix(' (deleted)'), src) for src in sources)]
            if matched:
                holders.append(dict(pid=pid, owner=owner, paths=matched))
        except (FileNotFoundError, ProcessLookupError) as error:
            if process.exists():
                unreadable.append(dict(pid=pid, error=type(error).__name__))
        except (PermissionError, OSError, ValueError) as error:
            item = dict(pid=pid, error=type(error).__name__)
            if isinstance(error, ValueError):
                item['reason'] = str(error)
            unreadable.append(item)
    return dict(scope='own and owned-user-namespace processes only', counts=counts,
                other_owner_inspection='Not run: requires privilege',
                holders=holders, helpers=helpers, unreadable=unreadable)


def main():
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
    if report['holders'] or report['helpers'] or report['unreadable']:
        sys.exit(1)


if __name__ == '__main__':
    main()
