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
