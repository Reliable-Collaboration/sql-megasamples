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
