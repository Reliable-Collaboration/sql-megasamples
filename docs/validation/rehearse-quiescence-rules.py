#!/usr/bin/env python3
"""Remove one gate rule at a time in a private copy; its focused test must fail.

Runs with the already installed test interpreter, inside the isolated tools
container. The production helper and tests are never edited by this rehearsal.
"""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'docs/validation/quiescence.py'
# Each removal is independently observable as a reason/outcome assertion failure.
RULES=[
 ('recorded process survives', 'test_recorded_survivor_refuses_with_reversal[process-recorded process survives]'),
 ('dedicated helper survives', 'test_recorded_survivor_refuses_with_reversal[dedicated helper-dedicated helper survives]'),
 ('live deployment cgroup task','test_new_cgroup_descendant_refuses_with_reversal'),
 ('shared helper without verified consumer','test_shared_helper_consumer_rule_with_reversal[False]'),
 ('required process inspection unreadable','test_hold_branches_with_reversal[unreadable-required process inspection unreadable]'),
 ('required association unresolved','test_hold_branches_with_reversal[association-required association unresolved]'),
 ('source identity changed','test_hold_branches_with_reversal[source-source identity changed]'),
 ('recorded process identifier reused','test_hold_branches_with_reversal[reuse-recorded process identifier reused]'),
 ('recorded cgroup identifier reused','test_hold_branches_with_reversal[cgroup-reuse-recorded cgroup identifier reused]'),
 ('required cgroup inspection unreadable','test_hold_branches_with_reversal[cgroup-unreadable-required cgroup inspection unreadable]'),
 ('phase state ineligible','test_hold_branches_with_reversal[phase-phase state ineligible]'),
 ('deployment container running','test_container_running_refuses_with_reversal'),
 ('capture crosses reboot','test_hold_branches_with_reversal[reboot-capture crosses reboot]'),
 ('capture store changed','test_hold_branches_with_reversal[store-capture store changed]'),
 ('capture missing or incomplete','test_missing_capture_is_hold'),
 ('recorded data source held','test_readable_unrelated_holder_refuses_with_reversal'),
]

def main():
    out=Path(tempfile.mkdtemp(prefix='rule-removals-',dir=ROOT/'build/dl086/dl088'))
    out.chmod(0o700); original=SOURCE.read_text(); results=[]
    for index,(reason,test) in enumerate(RULES):
        # Remove the decision action, retaining other rules so an unrelated
        # refusal cannot make a reason-specific test accidentally succeed.
        mutated=out/f'rule-{index}.py'
        assert repr(reason) in original, reason
        class RemoveRule(ast.NodeTransformer):
            def visit_Expr(self, node):
                call = node.value
                if isinstance(call, ast.Call) and any(isinstance(part, ast.Constant) and part.value == reason for part in ast.walk(call)):
                    return ast.copy_location(ast.Pass(), node)
                return self.generic_visit(node)
        tree=RemoveRule().visit(ast.parse(original)); ast.fix_missing_locations(tree)
        mutated.write_text(ast.unparse(tree)+'\n')
        result=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_quiescence_gate.py::'+test],
            cwd=ROOT,env=dict(os.environ,DL088_GATE_SOURCE=str(mutated)),capture_output=True,text=True,timeout=30)
        (out/f'rule-{index}.log').write_text(result.stdout+result.stderr)
        assert result.returncode==1 and 'AssertionError' in result.stdout,(reason,result.stdout,result.stderr)
        results.append(dict(rule=reason,status='Passed',control='Failed as required after rule removal'))
    (out/'receipt.json').write_text(json.dumps(dict(results=results),indent=2)+'\n')
    print(json.dumps(dict(artifacts=str(out.relative_to(ROOT)),rules=len(results),status='Passed')))

if __name__=='__main__': main()
