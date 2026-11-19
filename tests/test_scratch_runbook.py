"""Execute rerunnable scratch rehearsal and restricted cleanup, plus journal failures."""
import os
from pathlib import Path
import re
import subprocess

import pytest
from test_runbook_fragments import RUNBOOK, block


def test_scratch_rehearsal_reruns_in_new_store(tmp_path):
    script = block('# Rehearse the COMPLETE rollback set', '# Back in the original maintenance shell/store.')
    script = script.split('\n',1)[1]
    stubs = r'''
podman() {
 case "$1 $2" in
 'info --format') printf '%s/graph\n' "$SCRATCH_DIR";;
 'ps -aq') :;;
 'image rm'|'system migrate') printf '%s\n' "$*" >> "$BACKUP_DIR/cleanup-calls";;
 *) return 42;;
 esac
}
python3() { if test "$2" = load-images; then :; else command python3 "$@"; fi; }
'''
    for attempt in range(2):
        result = subprocess.run(['bash','-eu','-c',stubs + script],
                                env=dict(os.environ,BACKUP_DIR=str(tmp_path),UPGRADE_HELPER='helper'),
                                capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
    assert len(list(tmp_path.glob('rollback-load-rehearsal-*'))) == 2
    calls = (tmp_path/'cleanup-calls').read_text()
    assert calls.count('image rm --all --force') == 2
    assert 'reset' not in calls


@pytest.mark.parametrize('status,stderr,expected',[(0,'',''),(0,'access hint','Not run'),(1,'denied','Not run')])
def test_kernel_stderr_means_not_run(tmp_path,status,stderr,expected):
    text=RUNBOOK.read_text()
    body=re.search(r'if journalctl -k .*?^fi',text,re.M|re.S)[0]
    stub='journalctl() { printf "%s" "$ERR" >&2; return "$RC"; }\n'
    result=subprocess.run(['bash','-eu','-c',stub+body],env=dict(os.environ,EVIDENCE_DIR=str(tmp_path),
        FAILURE_SINCE='fixture',FAILURE_UNTIL='fixture',CHECK_ID='fixture',ERR=stderr,RC=str(status)),capture_output=True,text=True)
    assert result.returncode == 0
    assert ('Not run' in result.stdout) == bool(expected)


@pytest.mark.parametrize('failure', ['none', 'path', 'graph', 'listing', 'containers'])
def test_failed_scratch_manual_cleanup_is_scoped_and_guarded(tmp_path, failure):
    backup = tmp_path/'backup'; backup.mkdir()
    scratch = backup/('unrelated' if failure == 'path' else 'rollback-load-rehearsal-owned')
    scratch.mkdir()
    for name in ('storage.conf', 'containers.conf'): (scratch/name).touch()
    for name in ('xdg', 'tmp', 'run'): (scratch/name).mkdir()
    stubs = r'''
podman() {
 printf '%s\n' "$*" >> "$CALLS"
 case "$1 $2" in
 'info --format') if test "$FAILURE" = graph; then echo /wrong/graph; else echo "$SCRATCH_DIR/graph"; fi;;
 'ps -aq')
   if test "$FAILURE" = listing; then return 37; fi
   if test "$FAILURE" = containers; then echo owned-but-not-empty; fi;;
 'image rm'|'system migrate') :;;
 *) return 49;;
 esac
}
'''
    result = subprocess.run(['bash', '-eu', '-c', stubs+block(
        '# BEGIN failed scratch cleanup\n', '# END failed scratch cleanup')], capture_output=True, text=True,
        env=dict(os.environ, BACKUP_DIR=str(backup), SCRATCH_DIR=str(scratch),
                 CALLS=str(tmp_path/'calls'), FAILURE=failure))
    calls = (tmp_path/'calls').read_text().splitlines() if (tmp_path/'calls').exists() else []
    if failure == 'none':
        assert result.returncode == 0, result.stdout+result.stderr
        assert calls == ['info --format {{.Store.GraphRoot}}', 'ps -aq', 'image rm --all --force', 'system migrate']
        assert (scratch/'pause-pids.json').exists()
    else:
        assert result.returncode == (37 if failure == 'listing' else 1), result.stdout+result.stderr
        assert not any(call.startswith(('image rm', 'system migrate')) for call in calls)
        if failure == 'path': assert calls == []
