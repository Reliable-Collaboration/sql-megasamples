"""Observe process arguments/public environments and task logs without retaining secrets.

Run on the isolated rehearsal host. No process data is saved: receipts contain
only counts and whether one of this run's private random canaries was found.
"""
import datetime
import json
from pathlib import Path
import time

OUT = Path('build/credential-upgrade')
assert Path.cwd() == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = dict(started_at=started, status='Passed', samples=0, process_arguments_checked=0,
              public_environments_checked=0, private_environment_canaries=0,
              password_in_process_arguments=False, password_in_public_environment=False,
              password_in_logs=False, client_process_samples=0, log_files_checked=0)


def needles():
    values = set()
    for path in [Path('.env'), OUT / 'original.env', *OUT.glob('rotation-*.env')]:
        for line in path.read_text().splitlines():
            if '=' not in line or line.startswith('#'):
                continue
            value = line.split('=', 1)[1]
            if value.startswith("'") and value.endswith("'"):
                value = value[1:-1].replace("\\'", "'")
            if len(value) >= 12:
                values.add(value.encode())
    assert values, 'private canaries not available'
    return values


def scan_logs(values):
    count = 0
    for path in OUT.rglob('*.log'):
        if path.name == 'canary-monitor.log':
            continue
        content = path.read_bytes()
        count += 1
        if any(value in content for value in values):
            result['password_in_logs'] = True
    result['log_files_checked'] = count


while True:
    values = needles()
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes()
            result['process_arguments_checked'] += 1
            if any(value in args for value in values):
                result['password_in_process_arguments'] = True
            if b'--defaults-extra-file=/tmp/megasamples-auth.' in args or b'PGPASSFILE=/tmp/megasamples-auth.' in args:
                result['client_process_samples'] += 1
            env_path = path.with_name('environ')
            environment = env_path.read_bytes()
            public = bool(env_path.stat().st_mode & 0o044)
            if public:
                result['public_environments_checked'] += 1
                if any(value in environment for value in values):
                    result['password_in_public_environment'] = True
            elif any(value in environment for value in values):
                result['private_environment_canaries'] += 1
        except (OSError, PermissionError, ProcessLookupError):
            continue
    result['samples'] += 1
    if result['samples'] % 100 == 0 or (OUT / 'canary.stop').exists():
        scan_logs(values)
        result['captured_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['status'] = 'Failed' if any(result[k] for k in ['password_in_process_arguments', 'password_in_public_environment', 'password_in_logs']) else 'Passed'
        (OUT / 'canary-results.json').write_text(json.dumps(result, indent=2) + '\n')
    if (OUT / 'canary.stop').exists():
        break
    time.sleep(.05)
print(json.dumps(result), flush=True)
