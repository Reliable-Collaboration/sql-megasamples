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
PHASES = ['original-stop', 'candidate-teardown', 'restart-before', 'restart-after', 'original-restart']


def expected(name, state, phase):
    if phase == 'original-restart':
        return state not in ('running','missing')
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
        reason = ('original container missing' if phase == 'original-restart' and state == 'missing' else
                  'OOM' if state == 'oom-killed' else
                  'running flag must be true' if phase == 'restart-after' else
                  'running flag must be false' if state == 'running' else
                  'missing/unexpected state' if state == 'missing' else
                  'unexpected engine exit code')
        with pytest.raises(ValueError,match=reason):
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


def independent_gate(tmp_path,monkeypatch,phase,changes):
    row=dict(name='megasamples-postgres',id='id',state='exited',running=False,pid=0,exit_code=0,oom=False)
    if phase=='restart-after': row.update(state='running',running=True,pid=22)
    row.update(changes)
    before=tmp_path/'independent.json'; out=tmp_path/'independent-out.json'
    before.write_text(json.dumps(dict(project='fixture',engines=ENGINES,containers=[dict(name=row['name'],id='id')])))
    def pod(*args):
        if args[0]=='inspect': return '|'.join(str(row[k]).lower() if isinstance(row[k],bool) else str(row[k]) for k in ['name','id','state','running','pid','exit_code','oom'])+'|'
        return ''
    monkeypatch.setattr(upgrade,'pod',pod)
    upgrade.exited(before,out,phase=phase)
    out.unlink()


@pytest.mark.parametrize('phase',[p for p in PHASES if p!='restart-after'])
@pytest.mark.parametrize('field,value,reason', [('running',True,'running flag'),('pid',22,'PID must be 0'),('state','running','status must not be running')])
def test_independent_stopped_predicates_with_reversal(tmp_path,monkeypatch,phase,field,value,reason):
    with pytest.raises(ValueError,match=reason): independent_gate(tmp_path,monkeypatch,phase,{field:value})
    independent_gate(tmp_path,monkeypatch,phase,{})


@pytest.mark.parametrize('field,value,reason', [('running',False,'running flag'),('pid',0,'PID must be positive'),('state','exited','status must be running'),('oom',True,'OOM')])
def test_independent_started_predicates_with_reversal(tmp_path,monkeypatch,field,value,reason):
    with pytest.raises(ValueError,match=reason): independent_gate(tmp_path,monkeypatch,'restart-after',{field:value})
    independent_gate(tmp_path,monkeypatch,'restart-after',{})


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('code',[0,9,137])
def test_oom_rule_independent_of_engine_exit_with_reversal(tmp_path,monkeypatch,name,code):
    with pytest.raises(ValueError,match='OOM before cold copy'):
        independent_gate(tmp_path,monkeypatch,'original-stop',dict(name=name,oom=True,exit_code=code))
    # Exit-zero makes removing OOM the only difference for every engine, not just SQLite.
    independent_gate(tmp_path,monkeypatch,'original-stop',dict(name=name,oom=False,exit_code=0))


def test_still_running_deployment_branch(tmp_path,monkeypatch):
    original=upgrade.pod
    def inspect(*args):
        if args[0]=='ps': return 'unrecorded-running-id'
        return ''
    before=tmp_path/'before';before.write_text(json.dumps(dict(project='fixture',engines=[],containers=[])))
    monkeypatch.setattr(upgrade,'pod',inspect)
    with pytest.raises(ValueError,match='deployment container still running'):
        upgrade.exited(before,tmp_path/'out',phase='candidate-teardown')
    monkeypatch.setattr(upgrade,'pod',lambda *args:'')
    upgrade.exited(before,tmp_path/'out',phase='candidate-teardown')


def test_snapshot_missing_original_refuses_with_reason_and_reversal(tmp_path,monkeypatch):
    monkeypatch.setattr(upgrade,'pod',lambda *args:'')
    with pytest.raises(ValueError,match='original container missing; use coordinator recovery'):
        upgrade.snapshot(tmp_path/'out','fixture',['megasamples-postgres'])
    upgrade.snapshot(tmp_path/'out','fixture',[])

@pytest.mark.parametrize('failure', ['selection','image','running','pid','status','oom',None])
def test_post_start_logic_and_repeatable_receipts(tmp_path,monkeypatch,failure):
    backup=tmp_path/'retained';backup.mkdir();attempt=tmp_path/'attempt';attempt.mkdir()
    (backup/'original-running-services.txt').write_text('postgres\n')
    expected='a'*64
    (backup/'rollback-image-ids.txt').write_text(f'localhost/sql-megasamples-postgres:rollback-retained {expected} []\n')
    def pod(*args):
        if args[0]=='ps': return 'wrong' if failure=='selection' else 'megasamples-postgres'
        if args[0]=='inspect' and args[2]=='{{.Image}}': return 'b'*64 if failure=='image' else expected
        if args[0]=='inspect':
            status='exited' if failure=='status' else 'running'
            running='false' if failure=='running' else 'true'
            pid=0 if failure=='pid' else 22
            oom='true' if failure=='oom' else 'false'
            return f'megasamples-postgres|id|{status}|{running}|{pid}|0|{oom}|'
        return ''
    monkeypatch.setattr(upgrade,'pod',pod)
    reasons={'selection':'running service set differs','image':'restored image mismatch','running':'running flag',
             'pid':'PID must be positive','status':'status must be running','oom':'OOM after original start'}
    if failure:
        with pytest.raises(ValueError,match=reasons[failure]): upgrade.check_restored(backup,attempt,'first')
    else:
        upgrade.check_restored(backup,attempt,'first');upgrade.check_restored(backup,attempt,'repeat')
        assert len(list(attempt.glob('restart-after-gate-*.json')))==2


def test_stopped_or_removed_snapshot_retains_helper_attribution(tmp_path,monkeypatch):
    prior=tmp_path/'prior.json';out=tmp_path/'out.json'
    prior.write_text(json.dumps(dict(containers=[dict(name='megasamples-postgres',id='old-id',
        network_namespace='net:[retained]',cgroups=['0::/libpod-old-id.scope'],mounts=[['/retained/data','/data']])],engines=ENGINES)))
    monkeypatch.setattr(upgrade,'pod',lambda *args:'')
    upgrade.snapshot(out,'fixture',['megasamples-postgres'],phase='candidate-teardown',prior=prior)
    row=json.loads(out.read_text())['containers'][0]
    assert row['network_namespace']=='net:[retained]'
    assert row['mounts']==[['/retained/data','/data']]
    assert row['state']=='missing'
    assert row['id']=='old-id'
