#!/usr/bin/env python3
"""Repair round-six test-first evidence without changing pushed history.

Archive each fix's parent locally, apply only its named test, and retain the red.
The unchanged recorded-cgroup test instead gets a focused planted-bug control.
"""
import ast
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[2]

def function(text,name):
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
    start=min([node.lineno]+[d.lineno for d in node.decorator_list])-1
    return start,node.end_lineno,'\n'.join(text.splitlines()[start:node.end_lineno])+'\n'

def main():
    out=Path(tempfile.mkdtemp(prefix='test-audit-',dir=ROOT/'build/dl091'));results=[]
    cases=[('e3125bc^','tests/test_quiescence_gate.py','test_history_applicability_is_mechanical_with_reversal'),
           ('3d29797^','tests/test_rollback_preparation.py','test_bootstrap_route_hold_retains_reason_in_new_attempt')]
    for parent,file,name in cases:
        checkout=out/name;checkout.mkdir()
        payload=subprocess.check_output(['git','archive',parent],cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(payload)) as archive:archive.extractall(checkout,filter='data')
        source=(ROOT/file).read_text();target=checkout/file;old=target.read_text()
        _,_,test=function(source,name)
        try:
            start,end,_=function(old,name);old='\n'.join(old.splitlines()[:start]+old.splitlines()[end:])+'\n'
        except StopIteration:pass
        target.write_text(old+'\n'+test)
        env=dict(os.environ);env.pop('DL088_GATE_SOURCE',None);env.pop('DL089_RUNBOOK_SOURCE',None)
        result=subprocess.run([sys.executable,'-m','pytest','-q',file+'::'+name],cwd=checkout,env=env,text=True,capture_output=True)
        (out/(name+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==1 and 'AssertionError' in result.stdout,(name,result.stdout[-1400:])
        results.append(dict(test=name,parent=subprocess.check_output(['git','rev-parse',parent],cwd=ROOT,text=True).strip(),status='Passed',result='Red: test alone fails on fix parent'))
    code=(ROOT/'docs/validation/quiescence.py').read_text()
    before='and not names_container(error.filename, identity)'
    assert before in code
    bug=out/'swallow-recorded-vanish.py';bug.write_text(code.replace(before,''))
    result=subprocess.run([sys.executable,'-m','pytest','-q','tests/test_quiescence_down.py::test_recorded_cgroup_vanish_error_holds'],cwd=ROOT,env=dict(os.environ,DL088_GATE_SOURCE=str(bug)),text=True,capture_output=True)
    (out/'recorded-cgroup-vanish-control.log').write_text(result.stdout+result.stderr)
    assert result.returncode==1 and 'AssertionError' in result.stdout,result.stdout[-1200:]
    results.append(dict(test='test_recorded_cgroup_vanish_error_holds',status='Passed',result='Planted bug: suppress recorded cgroup ENOENT; reason-specific regression fails'))
    (out/'receipt.json').write_text(json.dumps(dict(results=results),indent=2)+'\n')
    print(json.dumps(dict(status='Passed',cases=len(results),artifacts=str(out.relative_to(ROOT)))))

if __name__=='__main__':main()
