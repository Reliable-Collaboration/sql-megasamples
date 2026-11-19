#!/usr/bin/env python3
"""Round-twelve defect controls in private copies; never edits tracked inputs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parent = ROOT/'build/dl095'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='reversals-', dir=parent))
    scanner = (ROOT/'docs/validation/quiescence.py').read_text()
    focused = ['tests/test_quiescence_capture.py::test_capture_is_exclusive_private_complete_and_retains_sources',
               'tests/test_quiescence_down.py::test_legacy_history_checks_survivors_without_endpoint_hold',
               'tests/test_quiescence_down.py::test_current_legacy_schema_still_holds']
    controls = []

    def old(path):
        return subprocess.check_output(['git', 'show', 'd2b417a:'+path], cwd=ROOT, text=True)

    controls.append(('AC1 old schema and history policy', old('docs/validation/quiescence.py'),
                     'DL088_GATE_SOURCE', focused, 7))
    before = '            if applicable:\n                prior = verify('
    assert before in scanner
    controls.append(('AC1 missing survivor enforcement', scanner.replace(before,
                     '            if applicable and not legacy:\n                prior = verify(', 1),
                     'DL088_GATE_SOURCE', focused[1:2], 4))
    before = 'schema=1 if _identity_only else 2'
    assert before in scanner
    controls.append(('AC1 current old schema admitted', scanner.replace(before,
                     "schema=1 if _identity_only else saved['schema']", 1),
                     'DL088_GATE_SOURCE', focused[2:], 1))
    controls.append(('AC2 README account omissions', old('README.md'),
                     'DL086_README_SOURCE', ['tests/test_demo_documentation.py'], 3))
    # Only comments are necessary; do not duplicate credential assignments.
    example = '\n'.join(line for line in old('.env.example').splitlines() if line.startswith('#'))
    controls.append(('AC2 environment account omissions', example,
                     'DL086_ENV_EXAMPLE_SOURCE', ['tests/test_demo_documentation.py'], 3))
    controls.append(('AC2 runbook proof and pointer', old('docs/live-upgrade-runbook.md'),
                     'DL089_RUNBOOK_SOURCE', ['tests/test_round12_documentation.py'], 2))
    controls.append(('AC2 evidence proof limit', old('docs/live-upgrade-evidence.md'),
                     'DL086_EVIDENCE_SOURCE', ['tests/test_round12_documentation.py'], 1))
    results = []
    for number, (name, changed, variable, tests, failures) in enumerate(controls):
        path = out/(str(number)+('.py' if variable == 'DL088_GATE_SOURCE' else '.md'))
        path.write_text(changed)
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *tests], cwd=ROOT,
            env=dict(os.environ, **{variable: str(path)}), capture_output=True, text=True, timeout=40)
        (out/(str(number)+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode == 1 and f'{failures} failed' in result.stdout, name
        assert 'ERROR collecting' not in result.stdout and 'SyntaxError' not in result.stdout, name
        results.append(dict(rule=name, status='Passed', failures=failures,
                            control='Regression fails with defect restored'))
    (out/'receipt.json').write_text(json.dumps(dict(results=results), indent=2)+'\n')
    print(json.dumps(dict(status='Passed', controls=len(results), artifacts=str(out.relative_to(ROOT)))))


if __name__ == '__main__':
    main()
