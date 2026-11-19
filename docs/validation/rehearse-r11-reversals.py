#!/usr/bin/env python3
"""Round-eleven defect controls in private source copies; never edits tracked code."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parent = ROOT/'build/dl094'
    parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix='reversals-', dir=parent))
    scanner = (ROOT/'docs/validation/quiescence.py').read_text()
    readme = (ROOT/'README.md').read_text()
    example = '\n'.join(line for line in (ROOT/'.env.example').read_text().splitlines() if line.startswith('#'))
    book = (ROOT/'docs/live-upgrade-runbook.md').read_text()
    controls = []

    def add(name, source, before, after, variable, test, failures):
        assert before in source, name
        controls.append((name, source.replace(before, after, 1), variable, test, failures))

    condition = """if any(endpoint['family'] == address.version and endpoint['port'] == int(port, 16)
                           and (endpoint['address'] == str(address) or address.is_unspecified
                                or ipaddress.ip_address(endpoint['address']).is_unspecified)
                           for endpoint in ports):"""
    add('AB1 port-only attribution', scanner, condition,
        "if any(endpoint['port'] == int(port, 16) for endpoint in ports):",
        'DL088_GATE_SOURCE', 'tests/test_quiescence_down.py::test_down_port_helper_matches_address_and_family', 8)
    add('AB2 understated MySQL grant', readme,
        '`SELECT`, `SHOW VIEW` on every database (`*.*`), system schemas included, including `mysql`, where account rows live; no write privilege',
        '`SELECT`, `SHOW VIEW` on the sample data',
        'DL086_README_SOURCE', 'tests/test_demo_documentation.py::test_readme_demo_scope_matches_init_sql', 1)
    add('AB3 absolute write prohibition', example,
        '#   demo (MySQL): SELECT and SHOW VIEW on every database (`*.*`), system schemas included,\n'
        '#     including `mysql`, where account rows live; no write privilege.\n'
        '#   demo (PostgreSQL): reads persistent sample tables; still has TEMPORARY,\n'
        '#     can create large objects and execute granted routines.',
        '#   demo   SELECT and SHOW VIEW only -- cannot write anything, anywhere',
        'DL086_ENV_EXAMPLE_SOURCE', 'tests/test_demo_documentation.py::test_env_example_demo_scope_matches_init_sql', 2)
    add('AB4 missing abort guard', book,
        "  candidate-starting)\n    echo 'HOLD: password rotation reached; use Roll back, not the preparation abort.'; exit 2 ;;\n", '',
        'DL089_RUNBOOK_SOURCE', 'tests/test_round11_runbook.py', 1)
    results = []
    for name, changed, variable, test, failures in controls:
        number = len(results)
        path = out/(str(number)+('.py' if variable == 'DL088_GATE_SOURCE' else '.md'))
        path.write_text(changed)
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', test], cwd=ROOT,
            env=dict(os.environ, **{variable: str(path)}), capture_output=True, text=True, timeout=30)
        (out/(str(number)+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode == 1 and f'{failures} failed' in result.stdout, (name, result.stdout, result.stderr)
        assert 'ERROR collecting' not in result.stdout and 'SyntaxError' not in result.stdout
        results.append(dict(rule=name, status='Passed', failures=failures,
                            control='Regression fails with original defect restored'))
    (out/'receipt.json').write_text(json.dumps(dict(results=results), indent=2)+'\n')
    print(json.dumps(dict(status='Passed', controls=len(results), artifacts=str(out.relative_to(ROOT)))))


if __name__ == '__main__':
    main()
