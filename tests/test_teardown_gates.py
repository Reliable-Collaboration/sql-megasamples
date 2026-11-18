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


def test_restart_mounts_include_new_targets_and_missing_candidate_evidence(tmp_path,monkeypatch):
    before=tmp_path/'candidate.json'; after=tmp_path/'restart.json'
    before.write_text(json.dumps(dict(project='fixture',engines=[],containers=[dict(name='removed',id=None,state='missing',mounts=[['/old/data','/data']])])) )
    monkeypatch.setattr(upgrade,'pod',lambda *args:'/new/'+args[-1])
    upgrade.restart_mounts(before,after,'fixture')
    rows=json.loads(after.read_text())['containers']
    assert rows[0]['mounts'] == [['/old/data','/data']]
    assert {r['mounts'][0][0] for r in rows[1:]} == {'/new/megasamples-rollback-'+e+'-fixture' for e in ['postgres','mysql','sqlite','sqlite-shared']}

@pytest.mark.parametrize('code,oom', [(0,False),(137,False),(1,False),(0,True),(9,True)])
def test_original_restart_records_any_stopped_exit(tmp_path,monkeypatch,code,oom):
    before=tmp_path/'before.json'; after=tmp_path/'after.json'
    before.write_text(json.dumps(dict(project='fixture',engines=ENGINES,containers=[dict(name='megasamples-postgres',id='id')])))
    monkeypatch.setattr(upgrade,'pod',lambda *args: f'megasamples-postgres|id|exited|false|0|{code}|{str(oom).lower()}|' if args[0]=='inspect' else '')
    upgrade.exited(before,after,phase='original-restart')
    row=json.loads(after.read_text())['containers'][0]
    assert (row['exit_code'],row['oom']) == (code,oom)


def test_missing_original_restart_refuses_specifically(tmp_path,monkeypatch):
    before=tmp_path/'before.json'
    before.write_text(json.dumps(dict(project='fixture',engines=ENGINES,containers=[dict(name='megasamples-postgres',id=None)])))
    monkeypatch.setattr(upgrade,'pod',lambda *args:'')
    with pytest.raises(ValueError,match='original container missing; use coordinator recovery'):
        upgrade.exited(before,tmp_path/'out',phase='original-restart')
