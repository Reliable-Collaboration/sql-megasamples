#!/usr/bin/env python3
"""DL-088: record deployment identities, then verify a bounded maintenance claim.

PASS means the recorded deployment stopped using the exact recorded data over
readable required evidence. It does not prove host-wide absence of writers.
Never reads process arguments or environments. Run in the host initial namespace.
"""
import argparse
import array
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys


def under(path, base):
    return path == base or path.startswith(base.rstrip('/') + '/')


def caller_uid_mappings():
    return [tuple(map(int, line.split())) for line in Path('/proc/self/uid_map').read_text().splitlines()]


def start_time(process):
    # stat's comm can contain spaces and parentheses; starttime is field 22.
    return (process / 'stat').read_text().rsplit(') ', 1)[1].split()[19]



def classify_owner(process, uid):
    process_uid = process.stat().st_uid
    if process_uid == uid:
        return 'own'
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
    # Descriptor permission failures remain required HOLDs in deployment scope.
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



# DL-088 capture is independent of container lifetime and never reads cmdline/environ.
# NetworkSettings.Ports also lists image EXPOSE entries with null bindings.
# Only actual host bindings require a dedicated publishing helper.
CAPTURE_FORMAT = '{{.Id}}|{{.State.Pid}}|{{.State.ConmonPid}}|{{.HostConfig.NetworkMode}}|{{if .HostConfig.PortBindings}}true{{else}}false{{end}}|{{.NetworkSettings.SandboxKey}}'


def pod(*args):
    import subprocess
    return subprocess.check_output(['podman', *args], text=True, timeout=30).strip()


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def store_identity():
    graph, run = pod('info', '--format', '{{.Store.GraphRoot}}|{{.Store.RunRoot}}').split('|')
    return dict(graph=str(Path(graph).resolve(strict=True)), run=str(Path(run).resolve(strict=True)))


def object_identity(path):
    st = path.stat()
    return dict(device=f'{os.major(st.st_dev)}:{os.minor(st.st_dev)}', inode=st.st_ino)


def source_identity(path):
    original = str(Path(path).absolute())
    canonical = Path(original).resolve(strict=True)
    identity = object_identity(canonical)
    mounts = mount_rows(Path('/proc/self/mountinfo'))
    candidates = [(len(point), root, point) for dev, root, point in mounts
                  if dev == identity['device'] and under(str(canonical), point)]
    if not candidates:
        raise ValueError('source filesystem root unresolved')
    _, root, point = max(candidates)
    return dict(path=original, canonical=str(canonical),
                root=root.rstrip('/') + str(canonical)[len(point.rstrip('/')):], **identity)


def process_identity(process):
    start = start_time(process)
    row = dict(pid=int(process.name), start=start, comm=(process/'comm').read_text().strip(),
               cgroups=(process/'cgroup').read_text().splitlines())
    if start != start_time(process):
        raise ValueError('process identity reused during inspection')
    return row


def cgroup_path(line):
    fields = line.split(':', 2)
    if len(fields) != 3 or fields[:2] != ['0', ''] or not fields[2].startswith('/'):
        raise ValueError('required cgroup v2 membership unresolved')
    return fields[2]


def in_groups(lines, groups):
    return any(under(cgroup_path(line), cgroup_path(group)) for line in lines for group in groups)


def group_capture(line, cgroup_root):
    path = cgroup_root / cgroup_path(line).lstrip('/')
    identity = object_identity(path)
    # Both files are required, including threaded cgroups; no empty-on-error fallback.
    (path/'cgroup.procs').read_text(); (path/'cgroup.threads').read_text()
    return dict(line=line, **identity)


def group_members(path):
    """Complete recursive cgroup membership, including threads; errors propagate."""
    members = set()
    for directory, _, _ in os.walk(path, onerror=lambda error: (_ for _ in ()).throw(error)):
        for name in ('cgroup.procs', 'cgroup.threads'):
            members.update((Path(directory)/name).read_text().split())
    return members


def private_write(path, data):
    with path.open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(data, stream, indent=2)
        stream.write('\n')


def helper_names(comm):
    return comm.startswith(('pasta', 'slirp4netns', 'rootlessport'))


def network_refs(process):
    refs = set()
    for entry in [process/'ns/net', *list((process/'fd').iterdir())]:
        try:
            target = os.readlink(entry)
            if entry.name == 'net' or target.startswith('net:[') or '/netns/' in target:
                stat = entry.stat()
                refs.add((stat.st_dev, stat.st_ino))
        except FileNotFoundError:
            if entry == process/'ns/net':
                raise
    return refs


DATA_DESTINATIONS = {'/var/lib/postgresql', '/var/lib/mysql', '/data', '/shared', '/restore-target'}


def capture(snapshot, output, *, proc=Path('/proc'), cgroup_root=Path('/sys/fs/cgroup'), extra_sources=(), data_only=False):
    if output.exists():
        raise FileExistsError(output)
    if caller_uid_mappings() != [(0,0,4294967295)]:
        report = dict(outcome='HOLD', holds=[dict(reason='host initial user namespace required')])
        private_write(output, dict(schema=1, complete=False, holds=report['holds']))
        return report
    saved = dict(schema=1, complete=False, boot_id=boot_id(), store=store_identity(),
                 containers=[], processes=[], cgroups=[], sources=[], shared_helper=None, holds=[])
    def hold(reason, **detail):
        saved['holds'].append(dict(reason=reason, **detail))
    try:
        source = json.loads(snapshot.read_text())
        saved['project'] = source['project']
        saved['containers'] = source['containers']
        if not saved['containers']:
            hold('container capture missing')
        listed = set(pod('ps', '-aq', '--no-trunc', '--filter', 'label=com.docker.compose.project='+saved['project']).split())
        recorded = {r['id'] for r in saved['containers'] if r.get('id')}
        if listed != recorded:
            hold('container capture incomplete')
        groups, identities, networks = {}, {}, {}
        bridge = False
        for row in saved['containers']:
            if not row.get('id'):
                row['nothing_recorded'] = 'missing container, explicitly recorded'
                continue
            try:
                identity, pid, conmon, mode, published, net = pod('inspect', '-f', CAPTURE_FORMAT, row['id']).split('|')
                if identity != row['id'] or int(pid) != row['pid']:
                    raise ValueError('container identity changed during capture')
                if not row['running']:
                    row['nothing_recorded'] = 'not running before stop'
                    continue
                bridge |= mode == 'bridge'
                for value, role in [(pid, 'process'), (conmon, 'conmon')]:
                    try:
                        p = process_identity(proc/value)
                        p.update(role=role, container=identity)
                        identities[p['pid']] = p
                        for line in p['cgroups']:
                            specific = any('/libpod-'+identity+'.scope' in line or '/libpod-conmon-'+identity+'.scope' in line
                                           for identity in recorded)
                            if role == 'conmon' and not specific:
                                continue  # Inspect identifies conmon; shared shell is not deployment scope.
                            if not specific and cgroup_root == Path('/sys/fs/cgroup'):
                                raise ValueError('container-specific cgroup association unresolved')
                            try:
                                groups[line] = group_capture(line, cgroup_root)
                            except (OSError, ValueError) as error:
                                hold('cgroup capture incomplete', error=type(error).__name__)
                    except (OSError, ValueError) as error:
                        hold(role+' capture incomplete', container=identity, error=type(error).__name__)
                if published == 'true' and mode == 'bridge':
                    # SandboxKey may be a host-visible placeholder whose bind
                    # exists only inside the rootless namespace. Inspect the
                    # current container process's actual namespace object.
                    st = (proc/pid/'ns/net').stat()
                    if start_time(proc/pid) != identities[int(pid)]['start']:
                        raise ValueError('process identity changed during namespace capture')
                    networks[identity] = (st.st_dev, st.st_ino)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                hold('container capture incomplete', container=row['id'], error=type(error).__name__)
        # Capture all current cgroup members and dedicated helpers, not only PID 1.
        found_networks = set()
        for process in proc.iterdir():
            if not process.name.isdigit():
                continue
            belongs = False
            try:
                lines = (process/'cgroup').read_text().splitlines()
                comm = (process/'comm').read_text().strip()
                belongs = in_groups(lines, groups)
                if belongs:
                    identities.setdefault(int(process.name), dict(process_identity(process), role='process'))
                if helper_names(comm):
                    try:
                        matched = {i for i, ns in networks.items() if ns in network_refs(process)}
                        if matched or belongs:
                            found_networks |= matched
                            identities[int(process.name)] = dict(process_identity(process), role='dedicated helper')
                    except OSError:
                        if belongs:
                            hold('dedicated helper association unresolved', pid=int(process.name))
            except (OSError, ValueError) as error:
                # Missing global evidence is diagnostic unless scope is established.
                if belongs or int(process.name) in identities:
                    if not isinstance(error, FileNotFoundError) or process.exists():
                        hold('required cgroup member identity unreadable', pid=int(process.name), error=type(error).__name__)
        # /proc iteration is not a membership inventory (and omits non-leader
        # threads). Reconcile independently established scope even if stat failed.
        for line in groups:
            try:
                for pid in group_members(cgroup_root/cgroup_path(line).lstrip('/')):
                    try:
                        identity = process_identity(proc/pid)
                        identities.setdefault(int(pid), dict(identity, role='process'))
                    except (OSError, ValueError) as error:
                        if not isinstance(error, FileNotFoundError) or (proc/pid).exists():
                            hold('required cgroup member identity unreadable', pid=int(pid), error=type(error).__name__)
            except OSError as error:
                hold('cgroup capture incomplete', error=type(error).__name__)
        if set(networks) != found_networks:
            hold('dedicated helper association unresolved')
        if bridge:
            try:
                pidfile = Path(saved['store']['run'])/'networks/rootless-netns/rootless-netns-conn.pid'
                pid = pidfile.read_text().strip()
                shared = process_identity(proc/pid)
                if not helper_names(shared['comm']) or not any('/rootless-netns-' in g for g in shared['cgroups']):
                    raise ValueError('store PID does not identify a rootless helper')
                if pidfile.read_text().strip() != pid:
                    raise ValueError('store helper changed during capture')
                saved['shared_helper'] = dict(shared, role='shared helper', pidfile=str(pidfile))
            except (OSError, ValueError) as error:
                hold('shared helper association unresolved; return to deciders', error=type(error).__name__)
        if not any(row.get('running') for row in saved['containers']) or not groups:
            hold('deployment process capture missing; cannot capture after stop')
        saved['processes'] = list(identities.values())
        saved['cgroups'] = list(groups.values())
        paths = {p for r in saved['containers'] for p, dest in r.get('mounts', []) if not data_only or dest in DATA_DESTINATIONS} | set(map(str, extra_sources))
        if not paths:
            hold('source capture missing')
        for path in sorted(paths):
            try:
                saved['sources'].append(source_identity(path))
            except (OSError, ValueError) as error:
                hold('source capture incomplete', error=type(error).__name__)
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        hold('required capture incomplete', error=type(error).__name__)
    saved['complete'] = not saved['holds']
    private_write(output, saved)
    return dict(outcome='PASS' if saved['complete'] else 'HOLD', holds=saved['holds'])


def extend_capture(capture_path, output, snapshot=None, extra_sources=()):
    """Retain pre-stop evidence; add never-started restoration sources/targets.

    This cannot repair missing historical capture or substitute new processes.
    The resulting capture must still pass verify before any copy or restoration.
    """
    saved = json.loads(capture_path.read_text())
    if not saved.get('complete') or saved['boot_id'] != boot_id() or saved['store'] != store_identity():
        raise ValueError('HOLD: missing, incomplete or stale pre-stop capture')
    for source in saved['sources']:
        if source_identity(source['path']) != source:
            raise ValueError('HOLD: source identity changed')
    paths = set(map(str, extra_sources))
    if snapshot:
        paths |= {src for row in json.loads(snapshot.read_text())['containers']
                  for src, dest in row.get('mounts', []) if dest in DATA_DESTINATIONS}
    existing = {source['path'] for source in saved['sources']}
    saved['sources'] += [source_identity(path) for path in sorted(paths - existing)]
    private_write(output, saved)


def original_override(capture_path, output, upgrade_id, candidate_capture):
    """Restart only unchanged original data; this is not a copy/restore gate.

    Process/boot quiescence is deliberately inapplicable. Each actual original
    data object must independently match its retained canonical filesystem identity.
    """
    import re
    if not re.fullmatch('[A-Za-z0-9-]+', upgrade_id):
        raise ValueError('invalid retained upgrade identifier')
    saved = json.loads(capture_path.read_text())
    if not saved.get('complete'):
        raise ValueError('unchanged original data identity requires complete original evidence')
    candidates = json.loads(candidate_capture.read_text()).get('containers')
    if not candidates:
        raise ValueError('independent candidate mount evidence required for unchanged originals')
    candidate_sources = [source_identity(src) for row in candidates for src, _ in row.get('mounts', [])]
    services = {}
    for service, destinations in [('postgres', ['/var/lib/postgresql']), ('mysql', ['/var/lib/mysql']), ('sqlite', ['/data','/shared'])]:
        rows = [r for r in saved['containers'] if r['name'] == 'megasamples-'+service]
        if len(rows) != 1:
            raise ValueError('unchanged original data identity: missing original engine')
        volumes = []
        for destination in destinations:
            sources = [src for src, dest in rows[0]['mounts'] if dest == destination]
            if len(sources) != 1:
                raise ValueError('unchanged original data identity: missing original mount')
            identity = source_identity(sources[0])
            if not any(identity == row for row in saved['sources']):
                raise ValueError('unchanged original data identity differs from retained evidence')
            if any(row['device'] == identity['device'] and
                   (under(row['root'],identity['root']) or under(identity['root'],row['root']))
                   for row in candidate_sources):
                raise ValueError('candidate used original data; unchanged-data recovery unavailable for that source')
            volumes.append(dict(type='bind',source=identity['canonical'],target=destination,
                                bind=dict(create_host_path=False)))
        services[service] = dict(image='localhost/sql-megasamples-'+service+':rollback-'+upgrade_id,
                                 pull_policy='never',volumes=volumes)
    private_write(output,dict(services=services))


def check_source(capture_path, path):
    saved = json.loads(capture_path.read_text())
    if not saved.get('complete') or saved['boot_id'] != boot_id() or saved['store'] != store_identity():
        raise ValueError('HOLD: missing, incomplete or stale pre-stop capture')
    identity = source_identity(path)
    if not any(all(identity[k] == source[k] for k in ('canonical', 'device', 'inode', 'root'))
               for source in saved['sources']):
        raise ValueError('HOLD: copy path differs from captured source')


def task_alive(process):
    """A zombie leader may still have live threads; inspect every task."""
    fields = (process/'stat').read_text().rsplit(') ', 1)[1].split()
    if fields[0] not in ('Z', 'X', 'x'):
        return True
    for task in (process/'task').iterdir():
        try:
            if (task/'stat').read_text().rsplit(') ', 1)[1].split()[0] not in ('Z', 'X', 'x'):
                return True
        except FileNotFoundError:
            if task.exists():
                raise
    return False


def translated(path, mounts):
    clean = path.removesuffix(' (deleted)')
    candidates = [(len(point), device, root, point) for device, root, point in mounts if under(clean, point)]
    if not candidates:
        return None
    _, device, root, point = max(candidates)
    return device, root.rstrip('/') + clean[len(point.rstrip('/')):]


def holder_scan(sources, groups, proc=Path('/proc')):
    holders, holds, limitations = [], [], []
    counts = dict(inspected=0, other_owner=0, vanished=0, zombie_or_exited=0)
    for leader in proc.iterdir():
        if not leader.name.isdigit() or int(leader.name) == os.getpid():
            continue
        row = dict(pid=int(leader.name), comm='<unreadable>', owner='unattributed', cgroups=[])
        required = False
        try:
            row['cgroups'] = (leader/'cgroup').read_text().splitlines()
            required = in_groups(row['cgroups'], groups)
            row['comm'] = (leader/'comm').read_text().strip()
            row['owner'] = classify_owner(leader, os.getuid())
            if not required and row['owner'] not in ('own', 'owned-user-namespace'):
                counts['other_owner'] += 1
                # Positive readable evidence counts for any owner. Inaccessible
                # unrelated evidence remains a diagnostic limitation below.
            if not task_alive(leader):
                counts['zombie_or_exited'] += 1
                continue
            counts['inspected'] += 1
            tasks = list((leader/'task').iterdir())
        except (OSError, ValueError) as error:
            if not leader.exists():
                counts['vanished'] += 1
                continue
            (holds if required else limitations).append(dict(row, reason='required holder inspection unreadable' if required else 'unattributed inspection limit', operation='process', error=type(error).__name__))
            continue
        matched = []
        # Include live non-leader threads; their cwd/FD state can outlive the leader.
        for task in tasks:
            access = leader if task.name == leader.name else task
            def read(operation, action):
                try:
                    return action()
                except (OSError, ValueError) as error:
                    if not task.exists():
                        return None
                    (holds if required else limitations).append(dict(row, reason='required holder inspection unreadable' if required else 'unattributed inspection limit', operation=operation, error=type(error).__name__))
                    return None
            mounts = read('mountinfo', lambda: mount_rows(access/'mountinfo'))
            # Synthetic proc fixtures keep shared fields at the leader only.
            if mounts is None:
                continue
            paths = []
            for key in ('root', 'cwd'):
                target = read(key, lambda key=key: os.readlink(access/key))
                if target and target.startswith('/'):
                    paths.append((key, target, None))
            fds = read('fd', lambda: list((access/'fd').iterdir()))
            for fd in fds or []:
                try:
                    target = os.readlink(fd)
                    if target.startswith('/'):
                        paths.append(('fd/'+fd.name, target, None))
                except FileNotFoundError:
                    continue  # A descriptor may close during inspection.
                except OSError as error:
                    read('fd/'+fd.name, lambda: (_ for _ in ()).throw(error))
            maps = read('maps', lambda: (access/'maps').read_text())
            for line in (maps or '').splitlines():
                fields = line.split(maxsplit=5)
                if len(fields) == 6 and fields[5].startswith('/'):
                    major, minor = fields[3].split(':')
                    paths.append(('mapping', fields[5], f'{int(major,16)}:{int(minor,16)}'))
            for device, root, _ in mounts:
                if any(device == s['device'] and under(root, s['root']) for s in sources):
                    matched.append(dict(kind='mount-root', device=device, root=root))
            for kind, target, map_device in paths:
                result = translated(target, mounts)
                if result:
                    device, root = result
                    if map_device is not None and map_device != device:
                        continue
                    if any(device == s['device'] and under(root, s['root']) for s in sources):
                        matched.append(dict(kind=kind, device=device, root=root))
        if matched:
            holders.append(dict(row, reason='recorded data source held', holds=matched))
    return dict(holders=holders, holds=holds, limitations=limitations, counts=counts)


def remaining_consumers(saved, proc):
    """Independently inspect currently running bridge consumers of this store."""
    result = []
    ids = {r['id'] for r in saved['containers']}
    for identity in pod('ps', '-q', '--no-trunc').split():
        if identity in ids:
            continue
        found, pid, _, mode, _, _ = pod('inspect', '-f', CAPTURE_FORMAT, identity).split('|')
        if found != identity:
            raise ValueError('consumer identity changed')
        if mode == 'bridge':
            process = proc/pid
            before = process_identity(process)
            if not task_alive(process) or not any('/libpod-'+identity+'.scope' in g for g in before['cgroups']):
                raise ValueError('consumer association unresolved')
            if process_identity(process) != before:
                raise ValueError('consumer identity changed')
            result.append(identity)
    return result


def verify(capture_path, *, proc=Path('/proc'), cgroup_root=Path('/sys/fs/cgroup'), phase_eligible=True):
    report = dict(outcome='HOLD', assurance='The recorded deployment stopped using the exact recorded data; bounded by readable required evidence. This does not prove the host quiet or prevent new writers.',
                  refusals=[], holds=[], limitations=[], shared_consumers=[], counts={})
    def hold(reason, **detail): report['holds'].append(dict(reason=reason, **detail))
    def refuse(reason, **detail): report['refusals'].append(dict(reason=reason, **detail))
    try:
        if caller_uid_mappings() != [(0,0,4294967295)]:
            raise ValueError('host initial user namespace required')
        saved = json.loads(capture_path.read_text())
        required = {'schema','complete','boot_id','store','containers','processes','cgroups','sources','shared_helper','holds','project'}
        if not required <= saved.keys() or saved['schema'] != 1 or not saved['complete'] or not saved['containers'] or not saved['sources'] or not saved['processes'] or not saved['cgroups']:
            hold('capture missing or incomplete')
            return report
        if saved['boot_id'] != boot_id():
            hold('capture crosses reboot')
            return report
        if saved['store'] != store_identity():
            hold('capture store changed')
            return report
    except (OSError, ValueError, KeyError) as error:
        hold('capture missing or incomplete', error=type(error).__name__)
        return report
    for row in saved['holds']:
        hold('required association unresolved', evidence=row)
    if not phase_eligible:
        hold('phase state ineligible')
    for source in saved['sources']:
        try:
            if source_identity(source['path']) != source:
                hold('source identity changed')
        except (OSError, ValueError):
            hold('source identity changed')
    for row in saved['processes'] + ([saved['shared_helper']] if saved['shared_helper'] else []):
        p = proc/str(row['pid'])
        try:
            current = process_identity(p)
            if current['start'] != row['start']:
                hold('recorded process identifier reused', pid=row['pid'])
                continue
            if current['cgroups'] != row['cgroups']:
                hold('required association unresolved', pid=row['pid'])
            if not task_alive(p):
                continue
            if row['role'] == 'shared helper':
                try:
                    report['shared_consumers'] = remaining_consumers(saved, proc)
                    if not report['shared_consumers']:
                        refuse('shared helper without verified consumer', **current)
                except (OSError, ValueError, subprocess.SubprocessError):
                    hold('required association unresolved', pid=row['pid'])
            else:
                refuse('dedicated helper survives' if row['role'] == 'dedicated helper' else 'recorded process survives', **current)
        except (OSError, ValueError) as error:
            if not isinstance(error, FileNotFoundError) or p.exists():
                hold('required process inspection unreadable', pid=row['pid'], error=type(error).__name__)
    groups = []  # Only continuous cgroup objects establish deployment scope.
    for row in saved['cgroups']:
        path = cgroup_root/cgroup_path(row['line']).lstrip('/')
        try:
            if object_identity(path) != {k:row[k] for k in ('device','inode')}:
                hold('recorded cgroup identifier reused')
                continue
            groups.append(row['line'])
            for group in [path, *(p for p in path.rglob('*') if p.is_dir())]:
                for name in ('cgroup.procs','cgroup.threads'):
                    for pid in (group/name).read_text().split():
                        p = proc/pid
                        try:
                            if task_alive(p):
                                refuse('live deployment cgroup task', pid=int(pid))
                        except OSError:
                            if p.exists():
                                hold('required cgroup inspection unreadable')
        except (OSError, ValueError) as error:
            if not isinstance(error, FileNotFoundError) or path.exists():
                hold('required cgroup inspection unreadable')
    try:
        for p in proc.iterdir():
            if not p.name.isdigit(): continue
            try:
                if in_groups((p/'cgroup').read_text().splitlines(), groups) and task_alive(p):
                    refuse('live deployment cgroup task', pid=int(p.name))
            except (OSError, ValueError):
                pass  # Recorded identities/cgroup files are independently required above.
        running = pod('ps', '-q', '--filter', 'label=com.docker.compose.project='+saved['project'])
        if running:
            refuse('deployment container running')
        for row in saved['containers']:
            if not row['id']: continue
            try:
                identity, running, pid = pod('inspect', '-f', '{{.Id}}|{{.State.Running}}|{{.State.Pid}}', row['id']).split('|')
                if identity != row['id']:
                    hold('required association unresolved')
                elif running == 'true' or int(pid) != 0:
                    refuse('deployment container running')
            except subprocess.CalledProcessError:
                # Down/partial removal is valid only when exists confirms absence.
                try: pod('container','exists',row['id'])
                except subprocess.CalledProcessError as error:
                    if error.returncode != 1: raise
                else: hold('required container inspection unreadable')
        scan = holder_scan(saved['sources'], groups, proc)
        report['refusals'] += scan['holders']
        report['holds'] += scan['holds']
        report['limitations'] += scan['limitations']
        report['counts'] = scan['counts']
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        hold('required deployment inspection unreadable', error=type(error).__name__)
    report['outcome'] = 'REFUSE' if report['refusals'] else 'HOLD' if report['holds'] else 'PASS'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    cap = sub.add_parser('capture'); cap.add_argument('snapshot', type=Path); cap.add_argument('output', type=Path)
    cap.add_argument('--source', action='append', default=[])
    cap.add_argument('--data-only', action='store_true')
    ext = sub.add_parser('extend'); ext.add_argument('capture',type=Path); ext.add_argument('output',type=Path)
    ext.add_argument('--snapshot',type=Path); ext.add_argument('--source',action='append',default=[])
    original = sub.add_parser('original-override'); original.add_argument('capture',type=Path); original.add_argument('output',type=Path); original.add_argument('--upgrade-id',required=True); original.add_argument('--candidate-capture',type=Path,required=True)
    source = sub.add_parser('check-source'); source.add_argument('capture',type=Path); source.add_argument('path',type=Path)
    check = sub.add_parser('verify'); check.add_argument('capture', type=Path)
    diagnostic = sub.add_parser('diagnostic'); diagnostic.add_argument('capture', type=Path)
    args = parser.parse_args()
    if args.command == 'capture':
        report = capture(args.snapshot, args.output, extra_sources=args.source, data_only=args.data_only)
    elif args.command == 'extend':
        extend_capture(args.capture,args.output,args.snapshot,args.source)
        report = dict(outcome='PASS', assurance='Sources added; verify remains mandatory before use')
    elif args.command == 'original-override':
        original_override(args.capture,args.output,args.upgrade_id,args.candidate_capture)
        report = dict(outcome='PASS', assurance='Original data identities match; no copy or restoration authorized')
    elif args.command == 'check-source':
        check_source(args.capture,args.path)
        report = dict(outcome='PASS', assurance='Copy path matches retained identity')
    elif args.command == 'verify':
        report = verify(args.capture)
    else:
        # Diagnostic status must never be used as the continuation gate.
        if caller_uid_mappings() != [(0,0,4294967295)]:
            raise ValueError('host initial user namespace required')
        saved = json.loads(args.capture.read_text())
        report = holder_scan(saved['sources'], [], Path('/proc'))
        print(json.dumps(report, indent=2)); return
    print(json.dumps(report, indent=2))
    sys.exit({'PASS':0, 'REFUSE':1, 'HOLD':2}[report['outcome']])


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(outcome='HOLD', holds=[dict(reason='required deployment inspection unreadable', error=type(error).__name__)])))
        sys.exit(2)
