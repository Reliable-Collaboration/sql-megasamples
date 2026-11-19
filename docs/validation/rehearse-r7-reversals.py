#!/usr/bin/env python3
"""Round-seven focused removal controls; no production file is modified."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    out=Path(tempfile.mkdtemp(prefix='reversals-',dir=ROOT/'build/dl091'))
    code=(ROOT/'docs/validation/quiescence.py').read_text();book=(ROOT/'docs/live-upgrade-runbook.md').read_text()
    controls=[
      ('Y1 enumeration errors',code,'for directory, _, _ in os.walk(path, onerror=lambda error: (_ for _ in ()).throw(error)):', 'for directory, _, _ in os.walk(path):','tests/test_quiescence_gate.py::test_required_cgroup_enumeration_denial_holds_with_readable_reversal','DL088_GATE_SOURCE'),
      ('Y2 checkpoint before first start',book,'# Engines have individual port checks; SQLite must rebuild /shared before consoles.\nTEARDOWN_PHASE=rollback-starting\nsave_context', '# Engines have individual port checks; SQLite must rebuild /shared before consoles.','tests/test_quiescence_runbook.py::test_partial_exact_original_restart_persists_guard_before_first_start','DL089_RUNBOOK_SOURCE'),
      ('Y3 historical listing',code,'if not _historical:\n                listed', 'if True:\n                listed','tests/test_quiescence_gate.py::test_historical_mixed_generation_does_not_own_current_listing[False]','DL088_GATE_SOURCE'),
      ('Y3 current listing',code,"if listed - {r['id'] for r in saved['containers'] if r.get('id')}:", 'if False:','tests/test_quiescence_gate.py::test_historical_mixed_generation_does_not_own_current_listing[True]','DL088_GATE_SOURCE'),
      ('Y4 retained conmon continuity',code,'associated = start_time(process) == recorded_start','associated = True','tests/test_quiescence_down.py::test_retained_down_conmon_pid_reuse_is_not_continuity','DL088_GATE_SOURCE'),
      ('Y4 abort running originals',code,'if not allow_running and pod(', 'if pod(','tests/test_quiescence_down.py::test_abort_allows_running_exact_originals_but_requires_identity[none]','DL088_GATE_SOURCE'),
      ('Y4 exclude non-attempt directories',code,"and not p.name.startswith(('rollback-abort-', 'rollback-load-rehearsal-'))",'','tests/test_quiescence_gate.py::test_history_does_not_list_load_rehearsal_or_abort_directories','DL088_GATE_SOURCE'),
      ('Y4 restore policies',book,'if podman update --restart=unless-stopped "$id"','if true','tests/test_quiescence_runbook.py::test_original_recovery_restores_restart_policy_even_after_capture_hold','DL089_RUNBOOK_SOURCE'),
      ('Y4 recorded cgroup task vanished',code,'if not isinstance(error, ProcessLookupError) and (not isinstance(error, FileNotFoundError) or p.exists()):','if not isinstance(error, FileNotFoundError) or p.exists():','tests/test_quiescence_gate.py::test_recorded_cgroup_member_esrch_is_absent','DL088_GATE_SOURCE'),
      ('Y4 down cgroup task vanished',code,'if not isinstance(error, ProcessLookupError) and (not isinstance(error, FileNotFoundError) or (proc/pid).exists()):','if not isinstance(error, FileNotFoundError) or (proc/pid).exists():','tests/test_quiescence_down.py::test_neighbouring_proc_reads_treat_esrch_as_vanished[down-member]','DL088_GATE_SOURCE'),
      ('Y4 down helper vanished',code,'if associated and not isinstance(error, ProcessLookupError) and (not isinstance(error, FileNotFoundError) or process.exists()):','if associated and (not isinstance(error, FileNotFoundError) or process.exists()):','tests/test_quiescence_down.py::test_neighbouring_proc_reads_treat_esrch_as_vanished[down-helper]','DL088_GATE_SOURCE'),
      ('Y4 shared capture vanished',code,"except ProcessLookupError:\n                saved['shared_helper_absence']", "except ZeroDivisionError:\n                saved['shared_helper_absence']",'tests/test_quiescence_down.py::test_neighbouring_proc_reads_treat_esrch_as_vanished[shared-capture]','DL088_GATE_SOURCE'),
      ('Y4 shared verification vanished',code,'except ProcessLookupError:\n            pass  # A stale', 'except ZeroDivisionError:\n            pass  # A stale','tests/test_quiescence_down.py::test_neighbouring_proc_reads_treat_esrch_as_vanished[shared-verify]','DL088_GATE_SOURCE'),
    ]
    results=[]
    for name,text,before,after,test,key in controls:
        assert before in text,name
        target=out/(str(len(results))+('.md' if key=='DL089_RUNBOOK_SOURCE' else '.py'));target.write_text(text.replace(before,after))
        result=subprocess.run([sys.executable,'-m','pytest','-q',test],cwd=ROOT,env=dict(os.environ,**{key:str(target)}),capture_output=True,text=True,timeout=30)
        (out/(str(len(results))+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==1 and 'SyntaxError' not in result.stdout and 'ERROR collecting' not in result.stdout,(name,result.stdout[-1800:])
        results.append(dict(rule=name,status='Passed',control='Specific regression fails when its rule is removed'))
    (out/'receipt.json').write_text(json.dumps(dict(results=results),indent=2)+'\n')
    print(json.dumps(dict(status='Passed',controls=len(results),artifacts=str(out.relative_to(ROOT)))))
if __name__=='__main__':main()
