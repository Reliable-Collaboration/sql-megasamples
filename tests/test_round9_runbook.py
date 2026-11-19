"""Round-nine composed recovery regressions and their successful reversals."""
import json
import os
from pathlib import Path
import subprocess

import pytest
from test_runbook_fragments import RUNBOOK, block, context


@pytest.mark.parametrize('listing_rc', [0, 37])
def test_removed_candidates_dispatch_pause_then_down_capture(tmp_path, listing_rc):
    server = context(tmp_path, 'rollback-stop')
    for name in ('postgres', 'mysql', 'sqlite', 'sqlite-shared'):
        (tmp_path / 'retained' / name).mkdir()
    driver = tmp_path / 'driver.py'
    # Run the real routing, snapshot and capture implementations. Only Podman
    # and the host process/cgroup/store evidence are replaced by empty fixtures.
    driver.write_text('''
import importlib.util, json, os, pathlib, subprocess, sys
base = pathlib.Path(os.environ['FIXTURE'])
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
root = pathlib.Path(os.environ['REPO'])
gate = load('gate', root/'docs/validation/quiescence.py')
upgrade = load('upgrade', root/'docs/validation/live-upgrade.py')
def pod(*args):
    if args[0] == 'ps': return ''
    if args[0] == 'container': raise subprocess.CalledProcessError(1, args)
    raise AssertionError(args)
gate.pod = upgrade.pod = pod
gate.boot_id = lambda: 'boot'
gate.store_identity = lambda: dict(graph=str(base/'graph'), run=str(base/'run'))
gate.caller_uid_mappings = lambda: [(0, 0, 4294967295)]
mode = sys.argv[2]
with (base/'evidence/order').open('a') as out: out.write(mode+'\\n')
if mode == 'rollback-route':
    print(json.dumps(gate.rollback_route(pathlib.Path(sys.argv[3]), 'sql-megasamples')))
elif mode == 'snapshot':
    upgrade.snapshot(pathlib.Path(sys.argv[3]), 'sql-megasamples',
        ['megasamples-postgres','megasamples-mysql','megasamples-sqlite'], phase='candidate-teardown')
elif mode == 'capture':
    args = sys.argv[3:]
    assert '--allow-down' in args
    sources = [args[i+1] for i, arg in enumerate(args) if arg == '--source']
    report = gate.capture(pathlib.Path(args[0]), pathlib.Path(args[1]),
        proc=base/'proc', cgroup_root=base/'cgroup', extra_sources=sources,
        data_only=True, allow_down=True)
    print(json.dumps(report)); sys.exit({'PASS':0, 'REFUSE':1, 'HOLD':2}[report['outcome']])
''')
    for name in ('proc', 'cgroup', 'run'):
        (tmp_path / name).mkdir()
    stubs = r'''
python3() {
 case "${2-}" in rollback-route|snapshot|capture) command python3 "$DRIVER" "$@";;
 *) command python3 "$@";; esac
}
podman() {
 test "$1" = ps || return 49
 echo pause-listing >> "$EVIDENCE_DIR/order"
 return "$LISTING_RC"
}
'''
    capture = block('# Stop candidates BEFORE down can remove evidence. Keep every failed candidate volume.\n', 'date -u +%Y-%m-%dT%H:%M:%SZ >> "$EVIDENCE_DIR/rollback-stop.log.timestamps"')
    script = '. "$CONTEXT"\n' + stubs
    script += block('# BEGIN rollback route dispatch\n', '# END rollback route dispatch')
    script += block('# BEGIN pause restart automation\n', '# END pause restart automation')
    script += capture + '\necho CAPTURED\n'
    try:
        result = subprocess.run(['bash', '-eu', '-c', script], capture_output=True, text=True,
            env=dict(os.environ, CONTEXT=str(tmp_path/'resume-context.bash'),
                REPO=str(Path(__file__).parents[1]), FIXTURE=str(tmp_path),
                DRIVER=str(driver), LISTING_RC=str(listing_rc)))
        route = next((tmp_path/'attempt').glob('rollback-route-*.json'))
        assert json.loads(route.read_text())['route'] == 'down-capture'
        order = (tmp_path/'evidence/order').read_text().splitlines()
        if listing_rc:
            assert result.returncode == listing_rc, result.stdout + result.stderr
            assert 'capture' not in order and 'CAPTURED' not in result.stdout
        else:
            assert result.returncode == 0, result.stdout + result.stderr
            assert order == ['rollback-route', 'pause-listing', 'snapshot', 'capture']
            saved = json.loads(next((tmp_path/'evidence').glob('rollback-stop-capture-*.json')).read_text())
            assert saved['complete'] and saved['kind'] == 'down-state'
            assert saved['project_listing'] == [] and len(saved['down_evidence']) == 3
    finally:
        server.close()


def test_empty_original_listing_still_refuses_policy_pause(tmp_path):
    server = context(tmp_path, 'stop')
    try:
        script = '. "$CONTEXT"\npodman() { :; }\n'
        script += block('# BEGIN pause restart automation\n', '# END pause restart automation')
        result = subprocess.run(['bash', '-eu', '-c', script+'\necho UNSAFE\n'],
            env=dict(os.environ, CONTEXT=str(tmp_path/'resume-context.bash')), capture_output=True, text=True)
        assert result.returncode != 0 and 'UNSAFE' not in result.stdout
    finally:
        server.close()


def test_rollback_policy_pause_is_a_separate_guarded_step():
    text = RUNBOOK.read_text().split('## Roll back', 1)[1]
    # Pasting the dispatch/input block must end before capture or stop.
    before_capture = text.split('# Stop candidates BEFORE down', 1)[0]
    after_inputs = before_capture.split('# END rollback input verification', 1)[1]
    assert '```\n' in after_inputs and after_inputs.rstrip().endswith('```sh')
    prose = after_inputs.split('```\n', 1)[1].rsplit('```sh', 1)[0]
    assert 'guarded' in prose and 'pause restart automation' in prose
    assert 'before' in prose and 'capture' in prose


def test_first_port_refusal_then_fresh_shell_dispatch_completes(tmp_path):
    server = context(tmp_path, 'rollback-stop')
    backup = tmp_path/'retained'; attempt = tmp_path/'attempt'; checkout = tmp_path/'checkout'
    checkout.mkdir(); (checkout/'consoles').mkdir()
    config = attempt/'configuration'; (config/'consoles').mkdir(parents=True)
    for name in ('.env', 'compose.yaml', 'megasamples.yaml'):
        (config/name).write_text('# retained fixture\n')
        (checkout/name).write_text('# candidate fixture\n')
    (backup/'original-running-services.txt').write_text('postgres\nmysql\n')
    (backup/'rollback-branch.txt').write_text('original')
    (backup/'original-commit.txt').write_text('fixture')
    blocked = tmp_path/'port-blocked'; blocked.touch()
    stubs = r'''
python3() {
 if test "$1" = -c; then command python3 "$@"; return; fi
 printf '%s\n' "$*" >> "$EVIDENCE_DIR/calls"
 case "$2" in
 rollback-route) echo '{"route":"original-restart"}';;
 ports) if test -f "$BLOCKED"; then echo 'REFUSE: original port occupied'; return 37; fi;;
 esac
}
git() { if test "$1" = rev-parse; then echo fixture; fi; }
sha256sum() { :; }
docker() { echo "start $*" >> "$EVIDENCE_DIR/calls"; }
podman() { case "$1" in ps) echo exact-original-id;; inspect) echo 'exact-original-id|postgres|no';; esac; }
'''
    script = '. "$CONTEXT"\ncd "$CHECKOUT"\nCONFIG_DIR="$ATTEMPT_DIR/configuration"\n' + stubs
    script += block('# BEGIN rollback route dispatch\n', '# END rollback route dispatch')
    env = dict(os.environ, CONTEXT=str(tmp_path/'resume-context.bash'),
               CHECKOUT=str(checkout), BLOCKED=str(blocked))
    try:
        refused = subprocess.run(['bash', '-eu', '-c', script], env=env, capture_output=True, text=True)
        assert refused.returncode == 37 and 'port occupied' in refused.stdout, refused.stdout + refused.stderr
        assert 'start compose' not in (tmp_path/'evidence/calls').read_text()
        blocked.unlink()
        fresh = subprocess.run(['bash', '-eu', '-c', script], env=env, capture_output=True, text=True)
        assert fresh.returncode == 0, fresh.stdout + fresh.stderr
        calls = (tmp_path/'evidence/calls').read_text()
        assert calls.count(' rollback-route ') == 2
        assert 'start compose -p sql-megasamples -f compose.yaml start postgres' in calls
        assert 'start compose -p sql-megasamples -f compose.yaml start mysql' in calls
        assert (attempt/'failed-candidate.env').read_text() == '# candidate fixture\n'
        checked = subprocess.run(['bash', '-eu', '-c','. "$CONTEXT"; test "$TEARDOWN_PHASE" = originals-restarted'],
                                 env=env, capture_output=True, text=True)
        assert checked.returncode == 0, checked.stderr
    finally:
        server.close()
