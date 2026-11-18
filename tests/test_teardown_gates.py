"""Each state/phase cell, for every engine and console in the live records."""
import json
from pathlib import Path
import subprocess

import pytest
from test_live_upgrade import upgrade

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/live-teardown-states.json').read_text())
NAMES = [r['name'] for r in FIXTURE['candidates']]
ENGINES = [r['name'] for r in FIXTURE['originals']]
STATES = ['running', 'created', 'exited-0', 'exited-137', 'exited-other', 'oom-killed', 'missing']
PHASES = ['original-stop', 'candidate-teardown', 'restart-before', 'restart-after']


def expected(name, state, phase):
    if phase == 'restart-after':
        return state == 'running'
    if phase in ('candidate-teardown', 'restart-before'):
        return state != 'running'
    if state in ('running', 'missing', 'oom-killed'):
        return False
    if name in ENGINES:
        return state == 'exited-0' or (name == 'megasamples-sqlite' and state == 'exited-137')
    return True


@pytest.mark.parametrize('name', NAMES)
@pytest.mark.parametrize('state', STATES)
@pytest.mark.parametrize('phase', PHASES)
def test_state_phase_cell(tmp_path, monkeypatch, name, state, phase):
    before, after = tmp_path / 'before.json', tmp_path / 'after.json'
    before.write_text(json.dumps(dict(project='fixture', engines=ENGINES, containers=[dict(name=name, id='id')])))
    status = 'running' if state == 'running' else 'created' if state == 'created' else 'exited'
    code = {'exited-137': 137, 'exited-other': 1, 'oom-killed': 137}.get(state, 0)
    def pod(*args):
        if args[:2] == ('container', 'exists') and state == 'missing':
            raise subprocess.CalledProcessError(1, args)
        if args[0] == 'inspect':
            return f'{name}|id|{status}|{str(state == "running").lower()}|{22 if state == "running" else 0}|{code}|{str(state == "oom-killed").lower()}|/netns'
        return ''
    monkeypatch.setattr(upgrade, 'pod', pod)
    if expected(name, state, phase):
        upgrade.exited(before, after, phase=phase)
        row = json.loads(after.read_text())['containers'][0]
        assert row['state'] == ('missing' if state == 'missing' else status)
        assert row['exit_code'] == (None if state == 'missing' else code)
    else:
        with pytest.raises(ValueError):
            upgrade.exited(before, after, phase=phase)
        assert not after.exists()


def test_live_original_stop_and_created_candidate(tmp_path, monkeypatch):
    for row in FIXTURE['originals']:
        test_state_phase_cell(tmp_path, monkeypatch, row['name'], 'exited-' + str(row['exit_code']), 'original-stop')
        (tmp_path / 'after.json').unlink()
    assert next(r for r in FIXTURE['candidates'] if r['name'] == 'megasamples-landing')['status'] == 'created'
    test_state_phase_cell(tmp_path, monkeypatch, 'megasamples-landing', 'created', 'candidate-teardown')


def test_candidate_snapshot_allows_missing_engines(tmp_path, monkeypatch):
    monkeypatch.setattr(upgrade, 'pod', lambda *args: '')
    upgrade.snapshot(tmp_path / 'snapshot.json', 'fixture', ENGINES, phase='candidate-teardown')
    assert {r['name'] for r in json.loads((tmp_path / 'snapshot.json').read_text())['containers']} == set(ENGINES)
