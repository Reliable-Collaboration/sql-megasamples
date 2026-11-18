#!/usr/bin/env python3
"""Conservative /proc evidence for the runbook's two manual teardown checks.

Run in podman unshare. Never read cmdline or environ. Unreadable processes remain
unresolved; only the coordinator can exclude them with independent attribution.
"""
import argparse
import json
import os
from pathlib import Path
import sys


def under(path, base):
    return path == base or path.startswith(base.rstrip('/') + '/')


def evidence(snapshot, proc=Path('/proc')):
    saved = json.loads(snapshot.read_text())
    sources = {src for row in saved['containers'] for src, _ in row.get('mounts', [])}
    own = {str(os.getpid())}
    holders, helpers, unreadable = [], [], []
    for process in proc.iterdir():
        if not process.name.isdigit() or process.name in own:
            continue  # the scanner reads only the snapshot, never deployment data
        pid = int(process.name)
        try:
            comm = (process / 'comm').read_text().strip()
            network = os.readlink(process / 'ns/net')
            if comm in ('pasta', 'slirp4netns', 'rootlessport'):
                helpers.append(dict(pid=pid, comm=comm, network=network,
                                    cgroup=(process / 'cgroup').read_text().strip()))
            paths = [(key, os.readlink(process / key)) for key in ('root', 'cwd')]
            paths += [('fd/' + fd.name, os.readlink(fd)) for fd in (process / 'fd').iterdir()]
            for line in (process / 'mountinfo').read_text().splitlines():
                fields = line.split()
                # Linux mountinfo escapes spaces, tabs, newlines and backslashes.
                def unescape(value):
                    for code, char in [('040', ' '), ('011', '\t'), ('012', '\n'), ('134', '\\')]:
                        value = value.replace('\\' + code, char)
                    return value
                paths += [('mount-root', unescape(fields[3])), ('mountpoint', unescape(fields[4]))]
            matched = [(kind, target) for kind, target in paths
                       if any(under(target.removesuffix(' (deleted)'), src) for src in sources)]
            if matched:
                holders.append(dict(pid=pid, paths=matched))
        except (FileNotFoundError, ProcessLookupError) as error:
            if process.exists():
                unreadable.append(dict(pid=pid, error=type(error).__name__))
            # If /proc/PID itself vanished, the process exited during enumeration.
        except (PermissionError, OSError) as error:
            unreadable.append(dict(pid=pid, error=type(error).__name__))
    return dict(holders=holders, helpers=helpers, unreadable=unreadable)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    report = evidence(args.snapshot)
    print(json.dumps(report, indent=2))
    # No automatic exception: unresolved evidence blocks continuation.
    if report['holders'] or report['helpers'] or report['unreadable']:
        sys.exit(1)


if __name__ == '__main__':
    main()
