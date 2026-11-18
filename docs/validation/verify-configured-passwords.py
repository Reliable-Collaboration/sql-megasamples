"""Verify server passwords using native clients; print account outcomes only.

After cutover: python -m docs.validation.verify-configured-passwords --previous-dir BACKUP_DIR
The previous directory contains the private pre-cutover .env, or no .env when
that deployment used the published defaults. This is a read-only check.
"""
import argparse
import json
import os
import subprocess

from megasamples import config
from megasamples.credentials import client


def query(engine, container, user, password, local_root=False):
    # Use an address covered by the network authentication rules. PostgreSQL's
    # loopback is trusted in the baked cluster, so it cannot test password refusal.
    inspected = subprocess.run(['docker', 'inspect', '-f', '{{json .NetworkSettings.Networks}}', container],
                               capture_output=True, text=True)
    if inspected.returncode:
        raise RuntimeError('could not inspect the server network')
    networks = json.loads(inspected.stdout)
    host = '127.0.0.1' if local_root else next((n['IPAddress'] for n in networks.values() if n.get('IPAddress')), None)
    if not host:
        raise RuntimeError('server requires a network address for authentication verification')
    with client(engine, container, user, password, host=host) as command:
        command += ['-N', '--batch', '-e', 'SELECT CURRENT_USER(),1'] if engine == 'mysql' else ['-d', 'megasamples', '-tAc', 'SELECT current_user,1']
        return subprocess.run(command, capture_output=True, text=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--previous-dir', help='private rollback directory containing the old .env')
    args = ap.parse_args(argv)
    current = config.passwords()
    previous = None
    if args.previous_dir:
        if not os.path.isdir(args.previous_dir):
            ap.error('previous directory does not exist')
        root = config.ROOT
        try:
            config.ROOT = os.path.abspath(args.previous_dir)
            previous = config.passwords()
        finally:
            config.ROOT = root
    failures = 0
    for engine in config.load().engines:
        if engine not in ('mysql', 'postgres'):
            print('SQLite: Unsupported (files have no server passwords)')
            continue
        accounts = [('demo', 'DEMO_PASSWORD', False), ('admin', 'ADMIN_PASSWORD', False),
                    ('root', 'MYSQL_ROOT_PASSWORD', False), ('root', 'MYSQL_ROOT_PASSWORD', True)] if engine == 'mysql' else [
                    ('demo', 'DEMO_PASSWORD', False), ('admin', 'ADMIN_PASSWORD', False), ('postgres', 'POSTGRES_PASSWORD', False)]
        for user, key, local in accounts:
            label = engine + ':' + user + ('@localhost' if local else ' (network TCP)')
            accepted = query(engine, 'megasamples-' + engine, user, current[key], local)
            valid = accepted.returncode == 0 and accepted.stdout.strip().endswith('1')
            refused = True
            if previous is not None:
                rejected = query(engine, 'megasamples-' + engine, user, previous[key], local)
                error = 'Access denied' if engine == 'mysql' else 'password authentication failed'
                refused = current[key] != previous[key] and rejected.returncode != 0 and error in rejected.stderr
            good = valid and refused
            print(('Passed' if good else 'Failed') + ': ' + label + ': configured password' +
                  (' accepted' if valid else ' failed') + ('; previous password refused' if previous is not None and refused else
                  '; previous password NOT refused' if previous is not None else ''))
            failures += not good
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
