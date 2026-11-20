"""Round-eleven abort boundary, exercised in a fresh strict shell."""
import os
from pathlib import Path
import subprocess

import pytest
from test_runbook_fragments import block, context


@pytest.mark.parametrize('phase', ['candidate-starting', 'stop'])
def test_abort_refuses_candidate_starting_before_first_effect(tmp_path, phase):
    server = context(tmp_path, phase)
    try:
        source = tmp_path/'resume-context.bash'
        (tmp_path/'retained/resume-context.bash').write_text(source.read_text())
        stubs = '''
python3() { echo "$2" >> "$EVIDENCE_DIR/effects"; return 37; }
'''
        script = '. "$CONTEXT"\n' + stubs
        script += block('# BEGIN abort preparation\n', '# END abort preparation')
        result = subprocess.run(['bash', '-eu', '-c', script], capture_output=True, text=True,
                                env=dict(os.environ, CONTEXT=str(source)))
        effects = tmp_path/'evidence/effects'
        if phase == 'candidate-starting':
            assert result.returncode == 2, result.stdout + result.stderr
            assert 'Roll back' in result.stdout
            assert not effects.exists(), 'Abort changed state after password rotation'
        else:
            assert result.returncode == 37, result.stdout + result.stderr
            assert effects.read_text().splitlines() == ['prepare-rollback']
    finally:
        server.close()
