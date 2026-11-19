"""Every destructive paste block carries its own Bash failure semantics."""
import re
import subprocess

import pytest
from test_runbook_fragments import RUNBOOK


def destructive_blocks():
    # Match commands, excluding prose, --rm options and down-state labels.
    command = re.compile(r"^(?!\s*#).*?(?:\brm -f\b|podman (?:image rm|volume rm|system migrate)\b|docker compose[^\n]*\bdown(?: |$))", re.M)
    return [m[1] for m in re.finditer(r'^```sh\n(.*?)^```', RUNBOOK.read_text(), re.M | re.S)
            if command.search(m[1])]


@pytest.mark.parametrize('body', destructive_blocks(), ids=lambda s: next(l for l in s.splitlines() if l and l != 'set -eu')[:70])
def test_destructive_block_is_strict_in_plain_bash(body, tmp_path):
    # Use the block's actual entry (including the manual cleanup subshell).
    lines = body.splitlines()
    first = next(i for i, line in enumerate(lines) if line.strip() and not line.startswith('#'))
    if lines[first] == '(':
        prefix = '\n'.join(lines[:first+2]) + '\n'
        suffix = ')\n'
    else:
        prefix = '\n'.join(lines[:first+1]) + '\n'
        suffix = ''
    assert lines[first + (lines[first] == '(')].strip() == 'set -eu'
    # Execute every standalone test guard independently with its real arguments
    # and a failing test primitive; expansions use read-only command fixtures.
    guards = re.findall(r'^\s*(test [^\n]+)$', body, re.M) or ['test fixture = required']
    for guard in guards:
        if '||' in guard or '&&' in guard:
            continue  # Explicit status dispatch is checked by the fragment fixtures.
        stubs = '''
test() { return 73; }
git() { :; }; cat() { :; }; sed() { :; }
podman() { case "$1 $2" in "info --format"|"inspect -f"|"image inspect") :;; *) echo unsafe >> "$MARKER";; esac; }
rm() { echo unsafe >> "$MARKER"; }
docker() { echo unsafe >> "$MARKER"; }
'''
        script = stubs + prefix + guard + '\n'
        script += 'rm -f fixture\npodman image rm --all --force\npodman system migrate\npodman volume rm fixture\ndocker compose down\n' + suffix
        env = {name: 'fixture' for name in re.findall(r'\$\{?([a-zA-Z_][a-zA-Z_0-9]*)', guard)}
        env['MARKER'] = str(tmp_path/'unsafe')
        result = subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True)
        assert result.returncode == 73, (guard, result.stderr)
        assert not (tmp_path/'unsafe').exists(), guard
