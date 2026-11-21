#!/usr/bin/env python3
"""Fail focused tests by reversing each round-five fix in private source copies."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=Path(tempfile.mkdtemp(prefix='reversals-',dir=ROOT/'build/dl089'))
    source=(ROOT/'docs/validation/quiescence.py').read_text()
    book=(ROOT/'docs/history/live-upgrade-runbook.md').read_text()
    controls=[
        ('W1 earlier captures',source,"if applicable:","if False:",'tests/test_quiescence_capture.py::test_clean_stop_verifies_first_capture_other_engine_survivor','DL088_GATE_SOURCE'),
        ('W3 selected console',book,'--allow-running-project sql-megasamples "$@"','--allow-running-project sql-megasamples','tests/test_rollback_preparation.py::test_bootstrap_occupied_unselected_console_port[False]','DL089_RUNBOOK_SOURCE'),
        ('W4 all-down evidence',source,"down_allowed = allow_down and source.get('phase') == 'candidate-teardown'","down_allowed = False",'tests/test_quiescence_down.py::test_down_capture_complete_and_reverified[created-0-False]','DL088_GATE_SOURCE'),
        ('W4 exact original IDs',source,"or listed != ids", "or False",'tests/test_quiescence_down.py::test_exact_original_restart_eligibility_and_route[extra]','DL088_GATE_SOURCE'),
        ('W5 fresh shared volume',source,"if destination == '/shared':","if False:",'tests/test_quiescence_capture.py::test_unchanged_originals_real_shared_mount_overlap_gets_fresh_volume','DL088_GATE_SOURCE'),
        ('W6 zombie order',source,"if current['cgroups'] != row['cgroups']:","if current['cgroups'] != row['cgroups']:",None,None),
    ]
    # Explicitly move the identity comparison back before the zombie/task test.
    before="""            if not task_alive(p):
                continue
            if current['cgroups'] != row['cgroups']:
                hold('required association unresolved', pid=row['pid'])"""
    after="""            if current['cgroups'] != row['cgroups']:
                hold('required association unresolved', pid=row['pid'])
            if not task_alive(p):
                continue"""
    controls[-1]=('W6 zombie order',source,before,after,'tests/test_quiescence_gate.py::test_exited_zombie_with_deleted_cgroup_is_not_unresolved','DL088_GATE_SOURCE')
    controls += [
        ('W2 membership reconciliation',source,"for pid in group_members(cgroup_root/cgroup_path(line).lstrip('/')):","for pid in ():",'tests/test_quiescence_capture.py::test_cgroup_members_reconciled_even_when_proc_listing_misses_member','DL088_GATE_SOURCE'),
        ('W6 partial stop route',book,'if stop_project >> "$EVIDENCE_DIR/partial-stop-$PARTIAL_ID.log" 2>&1; then','if true >> "$EVIDENCE_DIR/partial-stop-$PARTIAL_ID.log" 2>&1; then','tests/test_quiescence_runbook.py::test_partial_stop_retry_keeps_capture_and_reruns_guarded_stop','DL089_RUNBOOK_SOURCE'),
        ('W4 retained environment',book,'if test -f "$CONFIG_DIR/.env"; then cp "$CONFIG_DIR/.env" .env; chmod 600 .env; else rm -f .env; fi',': # removed retained environment restoration','tests/test_quiescence_runbook.py::test_original_restart_after_rotation_restores_config_then_engines_and_free_consoles','DL089_RUNBOOK_SOURCE'),
    ]
    results=[]
    def execute(name,mutated,test,key):
        path=out/(str(len(results))+('.md' if key=='DL089_RUNBOOK_SOURCE' else '.py'));path.write_text(mutated)
        run=subprocess.run([sys.executable,'-m','pytest','-q',test],cwd=ROOT,env=dict(os.environ,**{key:str(path)}),text=True,capture_output=True,timeout=30)
        (out/(str(len(results))+'.log')).write_text(run.stdout+run.stderr)
        assert run.returncode==1 and ('AssertionError' in run.stdout or 'DID NOT RAISE' in run.stdout or 'ValueError: candidate used original data' in run.stdout),(name,run.stdout,run.stderr)
        results.append(dict(rule=name,status='Passed',control='Focused test failed after reversal'))
    for name,text,before,after,test,key in controls:
        assert before in text,name
        execute(name,text.replace(before,after),test,key)
    for reason,test in [
        ('required cgroup member identity unreadable','tests/test_quiescence_capture.py::test_surviving_cgroup_member_identity_failure_holds'),
        ('down cgroup evidence unreadable','tests/test_quiescence_down.py::test_down_live_evidence_blocks_with_reversal[unreadable-group]'),
        ('live deployment cgroup task','tests/test_quiescence_down.py::test_down_live_evidence_blocks_with_reversal[live-task]'),
        ('deployment process capture missing; cannot capture after stop','tests/test_quiescence_down.py::test_original_stop_all_down_still_holds'),
        ('shared helper without verified consumer','tests/test_quiescence_down.py::test_down_shared_helper_appearing_after_absent_pidfile_is_checked'),
        ('positively associated down helper survives','tests/test_quiescence_down.py::test_down_live_evidence_blocks_with_reversal[path-helper]'),
        ('down helper association unreadable','tests/test_quiescence_down.py::test_down_live_evidence_blocks_with_reversal[unreadable-conmon]'),
    ]:
        class Remove(ast.NodeTransformer):
            def visit_Expr(self,node):
                if isinstance(node.value,ast.Call) and any(isinstance(part,ast.Constant) and part.value==reason for part in ast.walk(node.value)):
                    return ast.copy_location(ast.Pass(),node)
                return self.generic_visit(node)
        tree=Remove().visit(ast.parse(source));ast.fix_missing_locations(tree)
        execute(reason,ast.unparse(tree)+'\n',test,'DL088_GATE_SOURCE')
    (out/'receipt.json').write_text(json.dumps(dict(results=results),indent=2)+'\n')
    print(json.dumps(dict(status='Passed',controls=len(results),artifacts=str(out.relative_to(ROOT)))))


if __name__=='__main__':main()
