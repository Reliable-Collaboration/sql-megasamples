"""DL-088 composed shell boundaries, using command stubs in strict fresh shells."""
import os
from pathlib import Path
import subprocess

import pytest
from test_runbook_fragments import block, context, RUNBOOK


@pytest.mark.parametrize('gate_rc',[0,1,2])
@pytest.mark.parametrize('diagnostic_rc',[0,1,2,37])
def test_diagnostic_status_never_changes_gate_or_ends_shell(tmp_path,gate_rc,diagnostic_rc):
    server=context(tmp_path,'rollback-down')
    try:
        script='. "$CONTEXT"\n'+r'''
python3() {
 case "$2" in verify) return "$GATE_RC";; diagnostic) return "$DIAGNOSTIC_RC";; esac
}
podman() { :; }
'''+block('# BEGIN four checks\n','# END four checks')+'\nprintf "gate=%s\\n" "$PROCESS_RC"\n'
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash'),GATE_RC=str(gate_rc),DIAGNOSTIC_RC=str(diagnostic_rc)),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert result.stdout.endswith(f'gate={gate_rc}\n')
        continuation=subprocess.run(['bash','-eu','-c',script+block('# BEGIN continuation dispatch\n','# END continuation dispatch')+'\necho MUTATION\n'],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash'),GATE_RC=str(gate_rc),DIAGNOSTIC_RC=str(diagnostic_rc)),capture_output=True,text=True)
        assert ('MUTATION' in continuation.stdout)==(gate_rc==0)
    finally:server.close()


def test_capture_is_saved_and_required_before_original_stop(tmp_path):
    text=RUNBOOK.read_text(); final=text.split('## Final backups and cutover',1)[1]
    setup=final[final.index('TEARDOWN_ATTEMPT='):final.index('date -u +%Y-%m-%dT%H:%M:%SZ')]
    assert 'capture "$TEARDOWN_SNAPSHOT" "$QUIESCENCE_CAPTURE"' in setup
    assert setup.index('save_context') < setup.index(' capture ')
    server=context(tmp_path,'stop')
    try:
        script='. "$CONTEXT"\npython3() { case "$2" in snapshot) echo {} > "$3";; capture) return 2;; esac; }; podman() { :; }\n'+setup+'\necho UNSAFE_STOP\n'
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==2 and 'UNSAFE_STOP' not in result.stdout
        fresh=subprocess.run(['bash','-eu','-c','. "$CONTEXT"; test -n "$QUIESCENCE_CAPTURE"'],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert fresh.returncode==0,fresh.stderr
    finally:server.close()


def test_copy_hold_never_blocks_unchanged_original_restart(tmp_path):
    server=context(tmp_path,'stop')
    try:
        (tmp_path/'retained/original-running-services.txt').write_text('postgres\n')
        script='. "$CONTEXT"\n'+r'''
ABORT_ID=fixture
python3() { case "$1" in */quiescence.py) return 2;; esac; }
docker() { printf 'restarted %s\n' "$*"; }
'''+block('# BEGIN original recovery checks\n','# END original recovery checks')+block('# BEGIN abort original start\n','# END abort original start')
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert 'start postgres' in result.stdout
    finally:server.close()


def test_superseded_inventory_policy_is_historical():
    text=(RUNBOOK.parent/'live-upgrade-evidence.md').read_text()
    paragraph=next(p for p in text.split('\n\n') if 'native-host UID/start-time inventory' in p)
    assert 'historical' in paragraph.lower()
    assert 'DL-088' in text


def test_fresh_shell_keeps_diagnostics_private(tmp_path):
    server=context(tmp_path,'rollback-down')
    try:
        script='umask 022\n. "$CONTEXT"\npython3() { :; }; podman() { :; }\n'+block('# BEGIN four checks\n','# END four checks')
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        for path in (tmp_path/'evidence').glob('*'):
            assert path.stat().st_mode & 0o777 == 0o600,path
    finally:server.close()


@pytest.mark.parametrize('copy_rc',[1,2])
def test_recreate_originals_on_retained_unchanged_data_is_not_copy_gated(tmp_path,copy_rc):
    server=context(tmp_path,'rollback-down')
    try:
        (tmp_path/'retained/original-running-services.txt').write_text('postgres\n')
        (tmp_path/'retained/rollback-image-tags.txt').write_text('')
        script='. "$CONTEXT"\n'+r'''
ORIGINAL_CAPTURE=fixture
PROCESS_RC="$COPY_RC"
python3() { if test "$1" = -; then command python3 "$@"; else case "$2" in verify|capture|extend) return "$COPY_RC";; esac; fi; }
docker() { printf 'recreated %s\n' "$*"; }
'''+block('# BEGIN unchanged volume recovery\n','# END unchanged volume recovery')
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash'),COPY_RC=str(copy_rc)),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert 'unchanged-original-data-' in result.stdout and 'up --no-deps' in result.stdout
    finally:server.close()


def test_failed_capture_has_exclusive_retry_route_before_downtime(tmp_path):
    server=context(tmp_path,'stop')
    try:
        script='. "$CONTEXT"\npython3() { case "$2" in capture) return 2;; esac; }\n'+block('# BEGIN capture retry\n','# END capture retry')+'\necho UNSAFE\n'
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==2 and 'UNSAFE' not in result.stdout
        fresh=subprocess.run(['bash','-eu','-c','. "$CONTEXT"; case "$QUIESCENCE_CAPTURE" in */capture-retry-*) :;; *) exit 43;; esac'],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert fresh.returncode==0,fresh.stderr
    finally:server.close()


def test_required_gate_runs_after_diagnostic_holder_discovery(tmp_path):
    server=context(tmp_path,'rollback-down')
    try:
        script='. "$CONTEXT"\n'+r'''
python3() { printf '%s\n' "$2" >> "$EVIDENCE_DIR/order"; }
podman() { :; }
'''+block('# BEGIN four checks\n','# END four checks')
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        order=(tmp_path/'evidence/order').read_text().splitlines()
        assert order.index('diagnostic') < order.index('verify')
    finally:server.close()


def test_original_restart_after_rotation_restores_config_then_engines_and_free_consoles(tmp_path):
    import hashlib
    server=context(tmp_path,'rollback-stop')
    checkout=tmp_path/'checkout';checkout.mkdir();(checkout/'consoles').mkdir()
    attempt=tmp_path/'attempt';config=attempt/'configuration';(config/'consoles').mkdir(parents=True)
    (config/'consoles/original').write_text('original');(checkout/'consoles/extra').write_text('candidate')
    for name in ('.env','compose.yaml','megasamples.yaml'):
        (config/name).write_text('# retained fixture\n');(checkout/name).write_text('# rotated fixture\n')
    (tmp_path/'retained/original-running-services.txt').write_text('postgres\nmysql\nsqlite\nlanding\nadminer\n')
    (tmp_path/'retained/rollback-branch.txt').write_text('original')
    (tmp_path/'retained/original-commit.txt').write_text('fixture')
    try:
        script='. "$CONTEXT"\ncd "$CHECKOUT"\nCONFIG_DIR="$ATTEMPT_DIR/configuration"\n'+r'''
python3() {
  case "$2" in
    ports) case " $* " in *' --service landing '*) return 37;; esac;;
  esac
  printf '%s\n' "$*" >> "$EVIDENCE_DIR/restart-calls"
}
git() { if test "$1" = rev-parse; then echo fixture; fi; }
sha256sum() { :; }
docker() { printf '%s\n' "$*" >> "$EVIDENCE_DIR/restart-calls"; }
'''
        script+=block('# BEGIN retained original restart\n','# END retained original restart')
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash'),CHECKOUT=str(checkout)),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert (checkout/'.env').read_bytes()==(config/'.env').read_bytes()
        assert (attempt/'failed-candidate.env').read_text()=='# rotated fixture\n'
        calls=(tmp_path/'evidence/restart-calls').read_text()
        assert 'start landing' not in calls and 'start adminer' in calls
        assert calls.index('wait-healthy sqlite') < calls.index('start adminer')
        assert (attempt/'original-consoles-held.txt').read_text()=='landing\n'
    finally:server.close()


def test_partial_stop_retry_keeps_capture_and_reruns_guarded_stop(tmp_path):
    server=context(tmp_path,'stop')
    try:
        script='. "$CONTEXT"\n'+r'''
ORIGINAL_CAPTURE="$QUIESCENCE_CAPTURE"
stop_project() { echo stopped >> "$EVIDENCE_DIR/calls"; }
python3() { case "$2" in capture) exit 47;; esac; }
'''+block('# BEGIN partial stop retry\n','# END partial stop retry')+'\ntest "$QUIESCENCE_CAPTURE" = "$ORIGINAL_CAPTURE"'
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert (tmp_path/'evidence/calls').exists(), 'guarded partial stop was not executed'
        assert (tmp_path/'evidence/calls').read_text()=='stopped\n'
    finally:server.close()


def test_unchanged_recovery_restores_saved_consoles_and_workspace_before_start(tmp_path):
    server=context(tmp_path,'rollback-down')
    backup=tmp_path/'retained'
    (backup/'original-running-services.txt').write_text('postgres\nsqlite\ncloudbeaver\nlanding\n')
    (backup/'rollback-image-tags.txt').write_text('localhost/sql-megasamples-cloudbeaver:rollback-fixture\nlocalhost/sql-megasamples-landing:rollback-fixture\n')
    workspace=backup/'cloudbeaver-workspace-final';workspace.mkdir();(workspace/'saved-query').write_text('select 42;')
    try:
        script='. "$CONTEXT"\n'+r'''
ORIGINAL_CAPTURE=fixture
python3() { case "$1" in -) command python3 "$@";; esac; }
docker() { printf 'compose %s\n' "$*" >> "$EVIDENCE_DIR/order"; }
podman() { printf 'podman %s\n' "$*" >> "$EVIDENCE_DIR/order"; }
'''+block('# BEGIN unchanged volume recovery\n','# END unchanged volume recovery')
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        calls=(tmp_path/'evidence/order').read_text().splitlines()
        stopped=next(i for i,r in enumerate(calls) if 'up --no-start' in r and r.endswith('cloudbeaver'))
        copied=next(i for i,r in enumerate(calls) if 'podman cp ' in r and 'cloudbeaver-workspace-final/.' in r)
        started=next(i for i,r in enumerate(calls) if 'up -d' in r and r.endswith('cloudbeaver'))
        assert stopped < copied < started
        assert all('rollback-consoles.override.json' in r for r in calls if r.startswith('compose '))
        import json
        images=json.loads((tmp_path/'attempt/rollback-consoles.override.json').read_text())['services']
        assert images['cloudbeaver']['image']=='localhost/sql-megasamples-cloudbeaver:rollback-fixture'
        assert images['landing']['pull_policy']=='never'
    finally:server.close()


@pytest.mark.parametrize('phase',['originals-restarted','rollback-starting','rollback-restored'])
def test_rollback_dispatch_never_tears_down_restarted_originals(tmp_path,phase):
    server=context(tmp_path,phase)
    try:
        script='. "$CONTEXT"\npython3() { echo ROUTE_WAS_RUN; exit 49; }\n'+block('# BEGIN rollback route dispatch\n','# END rollback route dispatch')
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==2 and 'ROUTE_WAS_RUN' not in result.stdout
        assert 'original' in result.stdout.lower()
    finally:server.close()


def test_rollback_route_hold_is_retained_with_its_status(tmp_path):
    import json
    server=context(tmp_path,'rollback-stop')
    try:
        script='. "$CONTEXT"\n'+r'''
python3() { echo '{"outcome":"HOLD","holds":[{"reason":"required deployment inspection unreadable"}]}'; return 2; }
'''+block('# BEGIN rollback route dispatch\n','# END rollback route dispatch')
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==2
        reports=list((tmp_path/'attempt').glob('rollback-route-*.json'));assert len(reports)==1
        assert json.loads(reports[0].read_text())['holds'][0]['reason']=='required deployment inspection unreadable'
        assert reports[0].with_suffix('.exit-code').read_text().strip()=='2'
        assert 'KeyError' not in result.stderr
    finally:server.close()


def test_restart_policy_failure_blocks_capture_and_has_guarded_restore(tmp_path):
    server=context(tmp_path,'stop')
    try:
        script='. "$CONTEXT"\n'+r'''
podman() { case "$1" in ps) echo fixture;; inspect) echo 'fixture|engine|unless-stopped';; update) return 37;; esac; }
'''+block('# BEGIN pause restart automation\n','# END pause restart automation')+'\necho UNSAFE_CAPTURE\n'
        result=subprocess.run(['bash','-eu','-c',script],env=dict(os.environ,CONTEXT=str(tmp_path/'resume-context.bash')),capture_output=True,text=True)
        assert result.returncode==37 and 'UNSAFE_CAPTURE' not in result.stdout
        assert block('# BEGIN restore restart automation\n','# END restore restart automation')
    finally:server.close()
