#!/usr/bin/env python3
"""Round-eight removal controls in private copies; never edit the checked source."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    out=Path(tempfile.mkdtemp(prefix='reversals-',dir=ROOT/'build/dl092'))
    book=(ROOT/'docs/history/live-upgrade-runbook.md').read_text()
    gate=(ROOT/'docs/validation/quiescence.py').read_text()
    upgrade=(ROOT/'docs/validation/live-upgrade.py').read_text()
    runbook='DL089_RUNBOOK_SOURCE';scanner='DL088_GATE_SOURCE';config='DL086_UPGRADE_SOURCE'
    controls=[]
    def add(name,source,before,after,test,key=runbook):controls.append((name,source,before,after,test,key))
    early=book.split('# Early workspace recovery needs',1)[1].split('ABORT_ID=',1)[0]
    add('Z1 early workspace abort',book,early,'\n','tests/test_quiescence_runbook.py::test_workspace_copy_failure_fresh_shell_abort_uses_exact_existing_id[False]')
    add('Z2 retained conmon birth',gate,"                if fresh.get('conmon') == row.get('conmon'):\n                    fresh['conmon_start'] = row.get('conmon_start')\n",'','tests/test_quiescence_down.py::test_retained_down_conmon_pid_reuse_is_not_continuity[True]',scanner)
    add('Z3 separate abort table',book,'Early abort on unchanged volumes','Originals restart on unchanged volumes','tests/test_quiescence_runbook.py::test_state_table_separates_running_abort_from_clean_stop')
    add('Z4 configuration enumeration',upgrade,'os.walk(config, topdown=False, onerror=lambda error: (_ for _ in ()).throw(error))','os.walk(config, topdown=False)','tests/test_live_upgrade.py::test_configuration_enumeration_denial_raises_with_readable_reversal',config)
    for phase,test in [('preparation-workspace-stop','test_workspace_copy_failure_fresh_shell_abort_uses_exact_existing_id[False]'),('preparation-workspace-start','test_workspace_restart_failure_has_fresh_shell_early_abort')]:
        add('Z5 '+phase,book,'TEARDOWN_PHASE='+phase+'; save_context',':','tests/test_quiescence_runbook.py::'+test)
    add('Z5 abort preparation context',book,'  save_context  # Preparation resumptions must see the abort before its first start.','  :','tests/test_quiescence_runbook.py::test_recovery_partial_start_fresh_preparation_context_holds[start-abort]')
    add('Z5 clean-stop phase',book,'TEARDOWN_PHASE=original-clean-starting\nsave_context',':','tests/test_quiescence_runbook.py::test_recovery_partial_start_fresh_preparation_context_holds[start-clean-stop]')
    for phase in ('originals-restarting','original-clean-starting'):
        dispatch=book.split('# BEGIN rollback route dispatch\n',1)[1].split('# END rollback route dispatch',1)[0]
        add('Z5 dispatch '+phase,book,dispatch,dispatch.replace(phase+'|',''),'tests/test_quiescence_runbook.py::test_rollback_dispatch_never_tears_down_restarted_originals['+phase+']')
    eligible='  python3 "$EVIDENCE_DIR/quiescence.py" original-eligible "$TEARDOWN_SNAPSHOT" \\\n    --project sql-megasamples --allow-running\n'
    add('Z5 abort exact-ID gate',book,eligible,'','tests/test_quiescence_runbook.py::test_recovery_partial_start_fresh_preparation_context_holds[identity-abort]')
    # Move the real gate after the first effect; the composed failure must catch order.
    reordered=book.replace(eligible,'',1).replace('  docker compose -p sql-megasamples -f compose.yaml start "$@"\n','  docker compose -p sql-megasamples -f compose.yaml start "$@"\n'+eligible,1)
    add('Z5 abort gate order',book,book,reordered,'tests/test_quiescence_runbook.py::test_recovery_partial_start_fresh_preparation_context_holds[start-abort]')
    add('Z5 exact restart guard',book,'    TEARDOWN_PHASE=rollback-starting; save_context\n','', 'tests/test_quiescence_runbook.py::test_partial_exact_original_restart_persists_guard_before_first_start')
    add('Z5 port before checkpoint',book,'    python3 "$UPGRADE_HELPER" ports --port-config "$ATTEMPT_DIR/original-ports.json" --service "$engine"\n    TEARDOWN_PHASE=rollback-starting; save_context','    TEARDOWN_PHASE=rollback-starting; save_context\n    python3 "$UPGRADE_HELPER" ports --port-config "$ATTEMPT_DIR/original-ports.json" --service "$engine"','tests/test_quiescence_runbook.py::test_exact_restart_port_refusal_precedes_restart_checkpoint')
    add('Z5 API PID saved',book,'  MEGASAMPLES_LIVE_API_PID=$!\n  save_context','  MEGASAMPLES_LIVE_API_PID=$!','tests/test_runbook_fragments.py::test_api_start_failure_retains_preparation_phase_in_fresh_shell')
    add('Z5 ESRCH ordinary HOLD',gate,"            except ProcessLookupError as error:\n                if not down_allowed:\n                    hold('shared helper association unresolved; return to deciders', error=type(error).__name__)\n                else:\n                    saved['shared_helper_absence'] = dict(pidfile=str(pidfile), reason='store helper vanished during capture')","            except ProcessLookupError:\n                saved['shared_helper_absence'] = dict(pidfile=str(pidfile), reason='store helper vanished during capture')",'tests/test_quiescence_capture.py::test_ordinary_shared_helper_vanish_holds_consistently[ProcessLookupError]',scanner)
    for delimiter in ('PY_PAUSE_CAPTURE','PY_ORIGINAL_TREE'):
        add('Z5 embedded '+delimiter,book,', onerror=lambda error: (_ for _ in ()).throw(error)','', 'tests/test_runbook_fragments.py::test_embedded_traversal_denial_propagates_with_readable_reversal['+delimiter+']')
    add('Z5 rollback policy pointer',book,'# Pause restart automation here','# Policy pointer removed','tests/test_quiescence_runbook.py::test_rollback_points_to_policy_pause_between_dispatch_and_capture')
    add('Z5 partial retry save',book,'# BEGIN partial stop retry\ncase "$TEARDOWN_PHASE" in stop|rollback-stop) :;; *) exit 2;; esac\nsave_context','# BEGIN partial stop retry\ncase "$TEARDOWN_PHASE" in stop|rollback-stop) :;; *) exit 2;; esac','tests/test_quiescence_runbook.py::test_partial_stop_checkpoint_is_saved_before_stop_effect')
    add('Z5 unchanged recreation phase',book,'TEARDOWN_PHASE=rollback-starting\nsave_context',':','tests/test_quiescence_runbook.py::test_unchanged_recreation_partial_start_holds_in_fresh_shell')
    results=[]
    for name,source,before,after,test,key in controls:
        assert before in source,name
        path=out/(str(len(results))+('.md' if key==runbook else '.py'))
        path.write_text(source.replace(before,after))
        result=subprocess.run([sys.executable,'-m','pytest','-q',test],cwd=ROOT,env=dict(os.environ,**{key:str(path)}),text=True,capture_output=True,timeout=30)
        (out/(str(len(results))+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==1 and 'ERROR collecting' not in result.stdout and 'SyntaxError' not in result.stdout,(name,result.stdout[-1500:],result.stderr)
        results.append(dict(rule=name,status='Passed',control='Regression fails with rule removed or reordered'))
    (out/'receipt.json').write_text(json.dumps(dict(results=results),indent=2)+'\n')
    print(json.dumps(dict(status='Passed',controls=len(results),artifacts=str(out.relative_to(ROOT)))))
if __name__=='__main__':main()
