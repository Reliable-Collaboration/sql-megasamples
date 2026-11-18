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
        script='. "$CONTEXT"\npython3() { case "$2" in capture) return 2;; esac; }; podman() { :; }\n'+setup+'\necho UNSAFE_STOP\n'
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
        script='. "$CONTEXT"\n'+r'''
ORIGINAL_CAPTURE=fixture
PROCESS_RC="$COPY_RC"
python3() { case "$2" in verify|capture|extend) return "$COPY_RC";; esac; }
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
