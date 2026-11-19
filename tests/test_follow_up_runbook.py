"""Follow-up shell behavior; container calls are fixtures only."""
import os
from pathlib import Path
import subprocess

import pytest
from test_runbook_fragments import block


@pytest.mark.parametrize('fail_sqlite', [False, True])
def test_cold_restore_waits_for_engines_before_consoles(tmp_path, fail_sqlite):
    (tmp_path/'original-running-services.txt').write_text('postgres\nmysql\nsqlite\nadminer\ndbgate\n')
    fragment = block('# END pre-up process gate\n', 'if test "$RESTORE_CLOUDBEAVER" = 1; then')
    stubs = r'''
save_context() { echo "phase:$TEARDOWN_PHASE" >> "$CALLS"; }
docker() { printf 'compose:%s\n' "$*" >> "$CALLS"; }
python3() {
 echo "health:$3" >> "$CALLS"
 if test "$3" = sqlite && test "$FAIL_SQLITE" = 1; then return 37; fi
}
'''
    result = subprocess.run(['bash', '-eu', '-c', stubs+fragment], text=True, capture_output=True,
        env=dict(os.environ, BACKUP_DIR=str(tmp_path), ATTEMPT_DIR=str(tmp_path), UPGRADE_HELPER='helper',
                 CALLS=str(tmp_path/'calls'), FAIL_SQLITE=str(int(fail_sqlite))))
    calls = (tmp_path/'calls').read_text().splitlines()
    assert calls[0] == 'phase:rollback-starting'
    starts = [line for line in calls if line.startswith('compose:')]
    assert all(' --no-deps ' in line for line in starts), calls
    assert starts[0].endswith(' postgres mysql sqlite'), calls
    assert not any(console in starts[0] for console in ('adminer', 'dbgate'))
    assert calls[2:5] == ['health:postgres', 'health:mysql', 'health:sqlite'], calls
    if fail_sqlite:
        assert result.returncode == 37 and len(starts) == 1, (calls, result.stderr)
    else:
        assert result.returncode == 0, result.stderr
        assert len(starts) == 2 and starts[1].endswith(' adminer dbgate'), calls
        assert calls.index(starts[1]) > calls.index('health:sqlite')


@pytest.mark.parametrize('route', ['cold', 'unchanged'])
@pytest.mark.parametrize('failure', ['snapshot', 'state', 'ports', 'health:postgres', 'health:mysql', 'health:sqlite'])
def test_real_restore_fence_failed_gate_in_plain_bash(tmp_path, route, failure):
    import re
    from test_runbook_fragments import RUNBOOK
    bodies = re.findall(r'^```sh\n(.*?)^```', RUNBOOK.read_text(), re.M | re.S)
    body = next(b for b in bodies if ('# BEGIN rollback population' if route == 'cold'
                                      else '# BEGIN unchanged volume recovery') in b)
    (tmp_path/'original-running-services.txt').write_text('postgres\nmysql\nsqlite\nadminer\ndbgate\n')
    stubs = r'''
save_context() { :; }
python3() {
  case " $* " in
    *' snapshot '*' --phase restart-before'*) gate=snapshot;;
    *' exited '*' --phase restart-before'*) gate=state;;
    *' ports '*) gate=ports;;
    *' wait-healthy '*) gate="health:$3";;
    *) gate=other;;
  esac
  printf '%s\n' "$gate" >> "$CALLS"
  if test "$gate" = "$FAILURE"; then echo REJECTED >> "$CALLS"; return 73; fi
}
podman() {
  case "$1 $2" in
    'volume exists') return 1;;
    'volume inspect') printf '%s' "$ATTEMPT_DIR/target";;
  esac
}
docker() { printf 'START:%s\n' "$*" >> "$CALLS"; }
'''
    # Every required input exists; no accidental nounset failure may stand in for
    # a gate rejection. Only fixture command implementations can run externally.
    env = {name: 'fixture' for name in re.findall(r'\$\{?([A-Za-z_][A-Za-z_0-9]*)', body)}
    env.update(BACKUP_DIR=str(tmp_path), ATTEMPT_DIR=str(tmp_path), EVIDENCE_DIR=str(tmp_path),
               XDG_RUNTIME_DIR=str(tmp_path), CALLS=str(tmp_path/'calls'), FAILURE=failure)
    result = subprocess.run(['bash', '-c', stubs+body], cwd=tmp_path, env=env,
                            capture_output=True, text=True)
    calls = (tmp_path/'calls').read_text().splitlines()
    assert 'REJECTED' in calls, (calls, result.stderr)
    assert result.returncode == 73, (calls, result.stderr)
    starts = [line for line in calls if line.startswith('START:')]
    if failure in ('snapshot', 'state', 'ports'):
        assert not starts, calls
    else:
        assert len(starts) == 1 and starts[0].endswith(' postgres mysql sqlite'), calls
        assert not any(console in starts[0] for console in ('adminer', 'dbgate'))
