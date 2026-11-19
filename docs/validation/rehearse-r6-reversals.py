#!/usr/bin/env python3
"""Round-six focused controls: each removed rule must fail its regression."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=Path(tempfile.mkdtemp(prefix='reversals-',dir=ROOT/'build/dl090'))
    code=(ROOT/'docs/validation/quiescence.py').read_text()
    book=(ROOT/'docs/live-upgrade-runbook.md').read_text()
    controls=[
        ('X1 cold data traversal',code,"directories = [history_dir] + [p for p in entries if p.name.startswith('rollback-') and stat.S_ISDIR(p.stat().st_mode)]", "directories = [Path(d) for d,_,_ in os.walk(history_dir, onerror=lambda e: (_ for _ in ()).throw(e))]",'tests/test_quiescence_gate.py::test_history_ignores_unreadable_cold_data_but_keeps_earlier_survivor','DL088_GATE_SOURCE'),
        ('X2 workspace',book,'    podman cp "$CB_WORKSPACE_BACKUP/." megasamples-cloudbeaver:/opt/cloudbeaver/workspace/',': # workspace copy removed','tests/test_quiescence_runbook.py::test_unchanged_recovery_restores_saved_consoles_and_workspace_before_start','DL089_RUNBOOK_SOURCE'),
        ('X2 saved console images',book,'-f "$ATTEMPT_DIR/rollback-consoles.override.json" up','up','tests/test_quiescence_runbook.py::test_unchanged_recovery_restores_saved_consoles_and_workspace_before_start','DL089_RUNBOOK_SOURCE'),
        ('X3 unrelated vanished cgroup',code,'if error.errno in (errno.ENOENT, errno.ENODEV)', 'if False and error.errno in (errno.ENOENT, errno.ENODEV)','tests/test_quiescence_down.py::test_unrelated_cgroup_vanish_is_absent_and_search_runs_once','DL088_GATE_SOURCE'),
        ('X3 one inventory',code,"if 'directories' not in cache:", 'if True:', 'tests/test_quiescence_down.py::test_unrelated_cgroup_vanish_is_absent_and_search_runs_once','DL088_GATE_SOURCE'),
        ('X4 per row reuse',code,'prior = verify(path, _historical=True, **kwargs)','prior = verify(path, **kwargs)','tests/test_quiescence_gate.py::test_history_reuse_is_judged_per_row_not_entire_capture','DL088_GATE_SOURCE'),
        ('X4 mount evidence',code,"if not candidates or not {dest for row in candidates for _,dest in row.get('mounts', [])} >= {'/var/lib/postgresql','/var/lib/mysql','/data'}:", 'if not candidates:', 'tests/test_quiescence_capture.py::test_original_override_requires_positive_candidate_mount_evidence','DL088_GATE_SOURCE'),
        ('X4 mixed assurance',code,"if saved.get('down_evidence'):\n        report['assurance']", "if down:\n        report['assurance']",'tests/test_quiescence_down.py::test_mixed_capture_states_its_down_evidence_limit','DL088_GATE_SOURCE'),
        ('X4 reaped process',code,'if not isinstance(error, ProcessLookupError) and (not isinstance(error, FileNotFoundError) or p.exists()):','if not isinstance(error, FileNotFoundError) or p.exists():','tests/test_quiescence_gate.py::test_reaped_recorded_process_is_vanished_even_if_proc_entry_lingers','DL088_GATE_SOURCE'),
        ('X4 restart phase guard',book,'originals-restarted|rollback-starting|rollback-restored)','rollback-starting|rollback-restored)','tests/test_quiescence_runbook.py::test_rollback_dispatch_never_tears_down_restarted_originals[originals-restarted]','DL089_RUNBOOK_SOURCE'),
        ('X4 route report',book,'> "$ROUTE_REPORT"; then :;', '> /dev/null; then :;', 'tests/test_quiescence_runbook.py::test_rollback_route_hold_is_retained_with_its_status','DL089_RUNBOOK_SOURCE'),
        ('X4 policy guard',book,'if podman update --restart=no "$id"', 'if true # podman update --restart=no "$id"', 'tests/test_quiescence_runbook.py::test_restart_policy_failure_blocks_capture_and_has_guarded_restore','DL089_RUNBOOK_SOURCE'),
    ]
    controls.insert(1,('X1 attempt stat inventory',code,'stat.S_ISDIR(p.stat().st_mode)','p.is_dir()',
        'tests/test_quiescence_gate.py::test_unreadable_attempt_inventory_holds[stat]','DL088_GATE_SOURCE'))
    # Policy removal remains syntactically valid; a shell syntax failure isn't proof.
    controls[-1]=(controls[-1][0],book,'if podman update --restart=no "$id"','if true',controls[-1][4],controls[-1][5])
    results=[]
    for name,text,before,after,test,key in controls:
        assert before in text,name
        target=out/(str(len(results))+('.md' if key=='DL089_RUNBOOK_SOURCE' else '.py'))
        target.write_text(text.replace(before,after))
        result=subprocess.run([sys.executable,'-m','pytest','-q',test],cwd=ROOT,env=dict(os.environ,**{key:str(target)}),text=True,capture_output=True,timeout=30)
        (out/(str(len(results))+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==1 and ('AssertionError' in result.stdout or 'StopIteration' in result.stdout or 'DID NOT RAISE' in result.stdout),(name,result.stdout[-1800:])
        results.append(dict(rule=name,status='Passed',proof='Removing this rule fails its specific regression'))
    (out/'receipt.json').write_text(json.dumps(dict(results=results),indent=2)+'\n')
    print(json.dumps(dict(status='Passed',controls=len(results),artifacts=str(out.relative_to(ROOT)))))


if __name__=='__main__':main()
