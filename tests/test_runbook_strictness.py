"""Every destructive paste block carries its own Bash failure semantics."""
import re
import subprocess

import pytest
from test_runbook_fragments import RUNBOOK, context


def destructive_blocks():
    # Match commands, excluding prose, --rm options and down-state labels.
    command = re.compile(
        r"^(?!\s*#).*?(?:(?<![\w-])rm(?:\s|$)|\bsystem (?:migrate|reset)\b|"
        r"\b(?:docker compose|podman)\b[^\n]*\b(?:stop|down)\b|"
        r"\bstop_project(?:\s|$)|\bup\b[^\n]*--force-recreate\b|"
        r"\bpodman unshare cp -a\b)", re.M)
    return [m[1] for m in re.finditer(r'^```sh\n(.*?)^```', RUNBOOK.read_text(), re.M | re.S)
            if command.search(m[1].replace("\\\n", " "))]


@pytest.mark.parametrize('body', destructive_blocks(), ids=lambda s: next(l for l in s.splitlines() if l and l != 'set -eu')[:70])
def test_destructive_block_is_strict_in_plain_bash(body, tmp_path):
    from runbook_fence_fixture import guard_calls, run_fence
    lines = body.splitlines()
    first = next(i for i, line in enumerate(lines) if line.strip() and not line.startswith('#'))
    assert lines[first + (lines[first] == '(')].strip() == 'set -eu'
    routes = ('original-restart', 'ordinary-capture') if any(
        marker in body for marker in ('# BEGIN rollback route dispatch', '# BEGIN rollback bootstrap')) else ('original-restart',)
    for route in routes:
        baseline, calls = run_fence(body, tmp_path/route/'baseline', route=route)
        assert baseline.returncode == 0, (baseline.stderr, calls[-8:])
        guards = guard_calls(body, calls)
        assert guards, calls
        for number, guard in enumerate(guards):
            directory = tmp_path/route/('failure-'+str(number))
            result, reached = run_fence(body, directory, guard, route=route)
            assert (directory/'rejected').exists(), (guard, reached, result.stderr)
            # A refused console port intentionally holds only that console and
            # continues to policy restoration; no guarded start may follow it.
            optional_console = 'if python3 ' in lines[guard[0]-1] and '--service "$service"' in lines[guard[0]-1]
            assert result.returncode != 0 or (optional_console and 'HOLD: console adminer stays stopped' in result.stdout), ('guard did not stop', guard, result.stdout, result.stderr)
            assert not (directory/'unsafe').exists(), ('destructive command followed', guard, (directory/'unsafe').read_text())


@pytest.mark.parametrize('command', [
    'rm -rf fixture', 'podman rm fixture', 'podman system reset',
    'docker compose up --force-recreate', 'podman unshare cp -a source/. target/',
    'docker compose stop', 'stop_project',
])
def test_destructive_class_includes_all_requested_families(tmp_path, monkeypatch, command):
    import sys
    source = tmp_path/'runbook.md'
    source.write_text('```sh\n'+command+'\n```\n')
    monkeypatch.setattr(sys.modules[__name__], 'RUNBOOK', source)
    assert destructive_blocks() == [command+'\n']


@pytest.mark.parametrize('failure', ['false', 'printf "%s" "$DL086_UNSET_FIXTURE"'])
def test_saved_context_supplies_strictness_in_plain_bash(tmp_path, failure):
    server = context(tmp_path, 'rollback-down')
    try:
        result = subprocess.run(['bash', '-c', '. "$CONTEXT"\n'+failure+'\necho UNSAFE'],
            env={'CONTEXT': str(tmp_path/'resume-context.bash')}, capture_output=True, text=True)
        assert result.returncode != 0, result.stdout
        assert 'UNSAFE' not in result.stdout
    finally:
        server.close()


def test_class_fixture_catches_errexit_disabled_after_entry(tmp_path):
    preparation = next(body for body in destructive_blocks() if 'save_context() {' in body)
    broken = preparation.replace('set -eu\n', 'set -eu\nset +e\n', 1)
    with pytest.raises(AssertionError, match='guard did not stop|destructive command followed'):
        test_destructive_block_is_strict_in_plain_bash(broken, tmp_path)


def test_class_ignores_disposable_option_and_joins_continuations(tmp_path, monkeypatch):
    import sys
    source = tmp_path/'runbook.md'
    source.write_text('```sh\ndocker compose run --rm fixture\n```\n')
    monkeypatch.setattr(sys.modules[__name__], 'RUNBOOK', source)
    assert destructive_blocks() == []
    source.write_text('```sh\ndocker compose -f fixture \\\n  stop\n```\n')
    assert len(destructive_blocks()) == 1
