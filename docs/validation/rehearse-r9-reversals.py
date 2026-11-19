#!/usr/bin/env python3
"""Round-nine removal/order controls in private runbook copies."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parent = ROOT/'build/dl093'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='reversals-', dir=parent))
    book = (ROOT/'docs/live-upgrade-runbook.md').read_text()
    controls = []

    def add(name, before, after, test):
        assert before in book, name
        controls.append((name, book.replace(before, after, 1), test))

    prefix = 'tests/test_round9_runbook.py::'
    empty_guard = book.split('# A successful empty listing needs no policy updates on the evidenced down route.\n', 1)[1].split('\nfor id in $AUTOMATION_IDS;', 1)[0]
    add('AA1 empty down-route listing',
        empty_guard,
        'test -n "$AUTOMATION_IDS"',
        prefix+'test_removed_candidates_dispatch_pause_then_down_capture[0]')
    pause = book.split('# BEGIN pause restart automation\n', 1)[1].split('# END pause restart automation', 1)[0]
    assignment = 'AUTOMATION_IDS=$(podman ps -aq --no-trunc --filter label=com.docker.compose.project=sql-megasamples)'
    add('AA1 listing error must refuse', pause, pause.replace(assignment, assignment+' || AUTOMATION_IDS='),
        prefix+'test_removed_candidates_dispatch_pause_then_down_capture[37]')
    add('AA1 empty originals listing must refuse',
        empty_guard, ':',
        prefix+'test_empty_original_listing_still_refuses_policy_pause')
    boundary = book.split('# END rollback input verification', 1)[1].split('# Stop candidates BEFORE down', 1)[0]
    add('AA2 paste-through boundary', boundary, '\n# Pause restart automation here\n',
        prefix+'test_rollback_policy_pause_is_a_separate_guarded_step')
    add('AA3 final preparation context',
        '  ( CONTEXT_FILE="$BACKUP_DIR/resume-context.bash"; save_context )\n', '',
        'tests/test_quiescence_runbook.py::test_original_recovery_restores_restart_policy_even_after_capture_hold[abort-running]')
    add('AA4 first port refusal re-entry',
        '    python3 "$UPGRADE_HELPER" ports --port-config "$ATTEMPT_DIR/original-ports.json" --service "$engine"\n    TEARDOWN_PHASE=rollback-starting; save_context',
        '    TEARDOWN_PHASE=rollback-starting; save_context\n    python3 "$UPGRADE_HELPER" ports --port-config "$ATTEMPT_DIR/original-ports.json" --service "$engine"',
        prefix+'test_first_port_refusal_then_fresh_shell_dispatch_completes')
    add('AA4 table matches eligibility',
        'Pass only with exact original IDs and consistent running/PID state',
        'Pass only with exact original IDs and unchanged mounts',
        'tests/test_quiescence_runbook.py::test_state_table_separates_running_abort_from_clean_stop')
    for identity, message in [('missing', 'CloudBeaver identity missing or replaced'),
                              ('wrong-project', 'CloudBeaver project identity missing or changed')]:
        add('AA4 coordinator message '+identity,
            "echo 'HOLD: "+message+"; keep coordinator hold.'; exit 2", 'exit 2',
            'tests/test_quiescence_runbook.py::test_workspace_copy_failure_fresh_shell_abort_uses_exact_existing_id['+identity+']')
    add('AA3 fresh-shell completion uses only saved context',
        '  ( CONTEXT_FILE="$BACKUP_DIR/resume-context.bash"; save_context )',
        '  ( CONTEXT_FILE="$PREPARATION_CONTEXT_FILE"; save_context )',
        prefix+'test_abort_completion_in_fresh_shell_saves_both_canonical_contexts')
    results = []
    for name, changed, test in controls:
        number = len(results)
        path = out/(str(number)+'.md'); path.write_text(changed)
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', test], cwd=ROOT,
            env=dict(os.environ, DL089_RUNBOOK_SOURCE=str(path)), capture_output=True, text=True, timeout=30)
        (out/(str(number)+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode == 1 and 'ERROR collecting' not in result.stdout and 'SyntaxError' not in result.stdout, (name, result.stdout, result.stderr)
        results.append(dict(rule=name, status='Passed', control='Regression fails with rule removed or reordered'))
    (out/'receipt.json').write_text(json.dumps(dict(results=results), indent=2)+'\n')
    print(json.dumps(dict(status='Passed', controls=len(results), artifacts=str(out.relative_to(ROOT)))))


if __name__ == '__main__':
    main()
