"""Execute recovery fragments in fresh strict shells and compile embedded code."""
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess

import pytest

RUNBOOK = Path(os.environ.get('DL089_RUNBOOK_SOURCE', Path(__file__).parents[1] / 'docs/live-upgrade-runbook.md'))


def block(start, end):
    return RUNBOOK.read_text().split(start, 1)[1].split(end, 1)[0]


def functions():
    text = RUNBOOK.read_text()
    return '\n'.join(re.search(r'^' + n + r'\(\) \{\n.*?^\}$(?=\n)', text, re.M | re.S)[0]
                     for n in ('ms_tool', 'save_context', 'stop_project') if n + '() {' in text)


def context(tmp_path, phase):
    text = functions()
    names = re.search(r'  declare -p (.*?)\n  printf', text, re.S)[1].replace('\\\n', '').split()
    assignments = '\n'.join(n + '=' + shlex.quote('fixture') for n in names)
    socket_path = tmp_path / 'podman.sock'
    server = socket.socket(socket.AF_UNIX); server.bind(str(socket_path))
    for name in ('retained','evidence','attempt'): (tmp_path/name).mkdir()
    extra = dict(BACKUP_DIR=str(tmp_path/'retained'), EVIDENCE_DIR=str(tmp_path/'evidence'), ATTEMPT_DIR=str(tmp_path/'attempt'),
                 CONTEXT_FILE=str(tmp_path / 'resume-context.bash'), DOCKER_HOST='unix://' + str(socket_path),
                 TEARDOWN_PHASE=phase, TEARDOWN_ATTEMPT='fixture-attempt',
                 TEARDOWN_SNAPSHOT=str(tmp_path / 'evidence/before.json'), EXITED_RECEIPT='')
    assignments += '\n' + '\n'.join(n + '=' + shlex.quote(v) for n,v in extra.items())
    subprocess.run(['bash', '-eu', '-c', assignments + '\n' + text + '\nsave_context'], cwd=tmp_path, check=True)
    return server


@pytest.mark.parametrize('phase', ['stop', 'rollback-stop', 'rollback-down'])
def test_failure_fresh_shell_checks_then_continuation(tmp_path, phase):
    server = context(tmp_path, phase)
    try:
        text = RUNBOOK.read_text()
        action = 'down' if phase == 'rollback-down' else 'stop'
        guard = next(g for g in re.findall(r'if (?:docker compose[^\n]* (?:stop(?: --timeout 300)?|down)|stop_project) >> .*?^fi', text, re.M | re.S)
                     if '"$EVIDENCE_DIR/' + phase + '.log"' in g)
        env = {'PATH': os.environ['PATH'], 'CONTEXT': str(tmp_path / 'resume-context.bash')}
        result = subprocess.run(['bash', '-eu', '-c', '. "$CONTEXT"\ndocker() { return 37; }\n' + guard], env=env)
        assert result.returncode == 37
        # Entire documented resume sequence; no variables inherited from the failed shell.
        script = '. "$CONTEXT"\n' + block('# BEGIN resume socket gate\n', '# END resume socket gate')
        script += '''
python3() { printf '%s\\n' "$*" >> "$EVIDENCE_DIR/calls"; }
podman() { :; }
'''
        script += block('# BEGIN four checks\n', '# END four checks')
        script += block('# BEGIN continuation dispatch\n', '# END continuation dispatch')
        script += '\ntest "$TEARDOWN_ATTEMPT" = fixture-attempt\nprintf "%s" "$RESUME_AT"\n'
        resumed = subprocess.run(['bash', '-eu', '-c', script], env=env, capture_output=True, text=True)
        assert resumed.returncode == 0, resumed.stderr
        assert resumed.stdout.endswith({'stop':'cold-copy','rollback-stop':'pre-down','rollback-down':'restore'}[phase])
        assert list((tmp_path/'evidence').glob('process-evidence-*.exit-code'))
    finally:
        server.close()


@pytest.mark.parametrize('log', ['stop', 'rollback-stop'])
@pytest.mark.parametrize('services', ['postgres\nmysql\nsqlite\nlanding\nadminer', 'postgres\nsqlite'])
@pytest.mark.parametrize('failure', ['', 'config', 'consoles', 'sqlite', 'engines'])
def test_project_stop_selects_timeouts_and_preserves_failures(tmp_path, log, services, failure):
    text = RUNBOOK.read_text()
    guard = next(g for g in re.findall(r'if (?:docker compose[^\n]* stop --timeout 300|stop_project) >> .*?^fi', text, re.M | re.S)
                 if '"$EVIDENCE_DIR/' + log + '.log"' in g)
    stubs = r'''
docker() {
  printf '%s\n' "$*" >> "$EVIDENCE_DIR/compose-calls"
  if test "$6" = config; then
    test "$FAILURE" != config || return 37
    printf '%s\n' "$SERVICES"; return
  fi
  case "${9-}" in
    landing) stage=consoles;; sqlite) stage=sqlite;; *) stage=engines;;
  esac
  test "$FAILURE" != "$stage" || return 37
}
'''
    env = dict(os.environ, EVIDENCE_DIR=str(tmp_path), SERVICES=services, FAILURE=failure)
    result = subprocess.run(['bash', '-eu', '-c', functions() + '\n' + stubs + guard],
                            env=env, capture_output=True, text=True)
    groups = [('config', 'config --services')]
    if 'landing' in services:
        groups.append(('consoles', 'stop --timeout 10 landing adminer'))
    groups += [('sqlite', 'stop --timeout 2 sqlite'),
               ('engines', 'stop --timeout 300 postgres' + (' mysql' if 'mysql' in services else ''))]
    expected = []
    code = 0
    for stage, command in groups:
        expected.append('compose -p sql-megasamples -f compose.yaml ' + command)
        if failure == stage:
            code = 37; break
    assert (tmp_path / 'compose-calls').read_text().splitlines() == expected
    assert result.returncode == code, result.stderr
    assert (tmp_path / (log + '.log.exit-code')).read_text() == str(code) + '\n'


def test_context_does_not_change_caller_umask(tmp_path):
    text = functions()
    declarations = re.search(r'  declare -p (.*?)\n  printf', text, re.S)[1].replace('\\\n','').split()
    script = '\n'.join(n + '=fixture' for n in declarations)
    script += '\nBACKUP_DIR=' + shlex.quote(str(tmp_path)) + '\nCONTEXT_FILE="$BACKUP_DIR/context"\n'
    script += text + '\numask 022\nsave_context\ntest "$(umask)" = 0022\n'
    subprocess.run(['bash', '-eu', '-c', script], check=True)


def test_all_executable_fragments_compile():
    text = RUNBOOK.read_text()
    bodies = re.findall(r'```sh\n(.*?)```', text, re.S)
    count = 0
    for index, body in enumerate(bodies):
        subprocess.run(['bash', '-n'], input=body, text=True, capture_output=True, check=True)
        # Compile every Python heredoc; validate every other heredoc as data.
        docs = []
        for match in re.finditer(r"<<-?['\"]?([A-Z_][A-Z_0-9]*)['\"]?[^\n]*\n", body):
            delimiter = match[1]
            end = re.search(r'^' + re.escape(delimiter) + r'\s*$', body[match.end():], re.M)
            assert end, delimiter
            content = body[match.end():match.end()+end.start()]
            docs.append((match.start(), match.end()+end.end()))
            if delimiter.startswith('PY'):
                compile(content, f'block-{index}-{delimiter}', 'exec'); count += 1
            elif delimiter == 'YAML':
                import yaml
                yaml.safe_load(content)
            else:
                assert delimiter in ('DATA_MOUNTS', 'SQL', 'TOOL_IMAGES'), delimiter
        # shlex on command text only: heredoc source isn't shell code.
        shell = body
        for doc in reversed(docs):
            shell = shell[:doc[0]] + shell[doc[1]:]
        tokens = shlex.split(shell, comments=True)
        for pos, token in enumerate(tokens):
            if token == '-c' and pos and ('PY' in tokens[pos-1] or 'python' in tokens[pos-1]):
                compile(tokens[pos+1], f'block-{index}-python-c', 'exec'); count += 1
    assert count > 10


def test_scanner_failure_is_saved_without_exiting_strict_shell(tmp_path):
    server = context(tmp_path, 'rollback-down')
    try:
        script = '. "$CONTEXT"\npython3() { case "$1" in */quiescence.py) return 1;; esac; }; podman() { :; }\n'
        script += block('# BEGIN four checks\n', '# END four checks')
        script += '\ntest "$PROCESS_RC" = 1\necho captured-refusal\n'
        result = subprocess.run(['bash', '-eu', '-c', script],
                                env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')},
                                capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.endswith('captured-refusal\n')
        assert next((tmp_path/'evidence').glob('process-evidence-*.exit-code')).read_text() == '1\n'
    finally:
        server.close()


@pytest.mark.parametrize('phase', ['stop', 'rollback-stop', 'rollback-down'])
def test_actual_continuation_in_fresh_strict_shell(tmp_path,phase):
    server = context(tmp_path,phase)
    (tmp_path/'retained/rollback-branch.txt').write_text('fixture-branch\n')
    (tmp_path/'retained/original-commit.txt').write_text('fixture-commit\n')
    (tmp_path/'retained/rollback-image-ids.txt').write_text('')
    (tmp_path/'retained/original-tool-images.txt').write_text('')
    point = {'stop':'cold-copy','rollback-stop':'pre-down','rollback-down':'restore'}[phase]
    stubs = r'''
python3() { printf 'python %s\n' "$*" >> "$EVIDENCE_DIR/continuation-calls"; }
podman() {
 printf 'podman %s\n' "$*" >> "$EVIDENCE_DIR/continuation-calls"
 case "$1 $2" in
 'container exists') return 1;;
 'inspect -f') printf /fixture/mount;;
 esac
}
docker() { printf 'docker %s\n' "$*" >> "$EVIDENCE_DIR/continuation-calls"; }
git() { printf 'git %s\n' "$*" >> "$EVIDENCE_DIR/continuation-calls"; if test "$1" = rev-parse; then echo fixture-commit; fi; }
cp() { printf 'cp %s\n' "$*" >> "$EVIDENCE_DIR/continuation-calls"; }
mv() { printf 'mv %s\n' "$*" >> "$EVIDENCE_DIR/continuation-calls"; }
bash() { printf 'bash digest\n' >> "$EVIDENCE_DIR/continuation-calls"; }
'''
    try:
        script = '. "$CONTEXT"\n' + stubs
        script += block('# BEGIN resume socket gate\n','# END resume socket gate')
        script += block('# BEGIN four checks\n','# END four checks')
        script += block('# BEGIN continuation dispatch\n','# END continuation dispatch')
        script += '\nCONFIG_DIR="$ATTEMPT_DIR/configuration"\n'
        script += block('# BEGIN ' + point + ' continuation\n','# END ' + point + ' continuation')
        result = subprocess.run(['bash','-eu','-c',script],env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')},capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
        calls = (tmp_path/'evidence/continuation-calls').read_text()
        assert {'stop':'unshare cp -a','rollback-stop':'docker compose -p sql-megasamples -f compose.yaml down',
                'rollback-down':'git switch fixture-branch'}[phase] in calls
    finally:
        server.close()


def test_early_preparation_retains_helper_before_source_switch(tmp_path):
    text=RUNBOOK.read_text()
    early=text.split('UPGRADE_ID=$(date',1)[1]
    early='UPGRADE_ID=$(date'+early.split('\n# Older branches tracked',1)[0]
    script=r'''
date() { echo fixture; }
git() { if test "$1" = show; then printf '# reviewed helper fixture\n'; else return 42; fi; }
'''+early+'\ntest -s "$UPGRADE_HELPER"\n'
    result=subprocess.run(['bash','-eu','-c',script],cwd=tmp_path,env=dict(os.environ,
        APPROVED_UPGRADE_MERGE='fixture-commit',METADATA_BUNDLE='fixture',EXTRA_RESERVE_BYTES='0',
        DOCKER_HOST='unix:///fixture',XDG_RUNTIME_DIR=str(tmp_path)),capture_output=True,text=True)
    assert result.returncode == 0,result.stderr


@pytest.mark.parametrize('name', ['cold-copy', 'restore', 'pre-up'])
def test_success_path_scanner_refusal_prevents_next_mutation(tmp_path,name):
    server=context(tmp_path,'stop' if name=='cold-copy' else 'rollback-down')
    try:
        script='. "$CONTEXT"\npython3() { case "$1" in */quiescence.py) return 1;; esac; }; podman() { :; }\n'
        script+=block('# BEGIN '+name+' process gate\n','# END '+name+' process gate')
        script+='\necho UNSAFE\n'
        result=subprocess.run(['bash','-eu','-c',script],env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')},capture_output=True,text=True)
        assert result.returncode != 0
        assert 'UNSAFE' not in result.stdout
        assert list((tmp_path/'evidence').glob('process-*.exit-code'))
    finally:
        server.close()


@pytest.mark.parametrize('services',[['postgres','landing'],['cloudbeaver'],[]])
def test_original_startup_never_adds_dependencies(tmp_path,services):
    (tmp_path/'original-running-services.txt').write_text(''.join(n+'\n' for n in services))
    text=RUNBOOK.read_text()
    start='set --\nRESTORE_CLOUDBEAVER=0'
    body=start+text.split(start,1)[1].split('# Check only originally selected services',1)[0].split('```',1)[0]
    stubs=r'''
save_context() { :; }
python3() { :; }
podman() { :; }
docker() {
 case " $* " in
 *' up '*|*' create '*) case " $* " in *' --no-deps '*) :;; *) return 43;; esac;;
 esac
 printf '%s\n' "$*" >> "$BACKUP_DIR/starts"
}
'''
    result=subprocess.run(['bash','-eu','-c',stubs+body],env=dict(os.environ,BACKUP_DIR=str(tmp_path),
        ATTEMPT_DIR=str(tmp_path),UPGRADE_HELPER='fixture'),cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode == 0,result.stderr
    if services:
        calls=(tmp_path/'starts').read_text()
        assert '--no-deps' in calls
        if services==['cloudbeaver']:
            assert sum(' up ' in line and '--no-start' not in line for line in calls.splitlines()) == 1
            assert 'up --no-start --no-deps' in calls
    else:
        assert not (tmp_path/'starts').exists()


def test_pre_up_checkpoint_resumes_without_restoring_again(tmp_path):
    server=context(tmp_path,'rollback-pre-up')
    try:
        # Represents the saved combined inventory, including newly populated targets.
        (tmp_path/'evidence/before.json').write_text(json.dumps({'containers':[{'mounts':[['/new/rollback-data','/restore-target']]}]}))
        env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')}
        failed=subprocess.run(['bash','-eu','-c','. "$CONTEXT"\npython3() { case "$1" in */quiescence.py) return 1;; esac; }; podman() { :; }\n'+block('# BEGIN pre-up process gate\n','# END pre-up process gate')],env=env,capture_output=True,text=True)
        assert failed.returncode == 1
        (tmp_path/'retained/original-running-services.txt').write_text('')
        script='. "$CONTEXT"\n' + r'''
python3() { printf '%s\n' "$*" >> "$EVIDENCE_DIR/calls"; cat >/dev/null; }
podman() { :; }
'''

        script+=block('# BEGIN four checks\n','# END four checks')
        script+=block('# BEGIN continuation dispatch\n','# END continuation dispatch')
        script+='\ntest "$RESUME_AT" = pre-up\ntest "$TEARDOWN_SNAPSHOT" = "$EVIDENCE_DIR/before.json"\n'
        script+=block('# BEGIN pre-up continuation\n','# END pre-up continuation')
        result=subprocess.run(['bash','-eu','-c',script],env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')},capture_output=True,text=True)
        assert result.returncode == 0,result.stderr
        assert '--phase restart-before' in (tmp_path/'evidence/calls').read_text()
    finally:
        server.close()


def test_cloudbeaver_creation_uses_supported_up_flags():
    text=RUNBOOK.read_text()
    assert 'create --no-deps' not in text
    assert 'up --no-start --no-deps --force-recreate --no-build cloudbeaver' in text


@pytest.mark.parametrize('refusal',['ports','state'])
def test_pre_up_first_refusal_already_saved_checkpoint(tmp_path,refusal):
    server=context(tmp_path,'rollback-down')
    try:
        (tmp_path/'retained/original-running-services.txt').write_text('postgres\n')
        script='. "$CONTEXT"\n'+r'''
python3() {
  case " $* " in
    *' restart-mounts '*) printf '{"containers":[{"mounts":[["/new/target","/restore-target"]]}]}' > "$TEARDOWN_SNAPSHOT";;
    *' ports '*) if test "$REFUSAL" = ports; then return 44; fi;;
    *' exited '*) if test "$REFUSAL" = state; then return 44; fi;;
  esac
}
podman() { :; }
'''
        script+=block('# BEGIN pre-up checkpoint\n','# END pre-up process gate')
        result=subprocess.run(['bash','-eu','-c',script],env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash'),'REFUSAL':refusal},capture_output=True,text=True)
        assert result.returncode == 44,result.stderr
        fresh=subprocess.run(['bash','-eu','-c','. "$CONTEXT"; test "$TEARDOWN_PHASE" = rollback-pre-up; grep -q /new/target "$TEARDOWN_SNAPSHOT"'],env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')},capture_output=True,text=True)
        assert fresh.returncode == 0,fresh.stderr
    finally:
        server.close()


def test_start_boundary_saves_partial_restart_hold(tmp_path):
    server=context(tmp_path,'rollback-pre-up')
    try:
        script='. "$CONTEXT"\n'+block('# BEGIN original start boundary\n','# END original start boundary')
        script+='\nexit 37\n'
        result=subprocess.run(['bash','-eu','-c',script],env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')})
        assert result.returncode == 37
        subprocess.run(['bash','-eu','-c','. "$CONTEXT"; test "$TEARDOWN_PHASE" = rollback-starting'],env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')},check=True)
    finally:
        server.close()

@pytest.mark.parametrize('mode',['clean-stop','abort'])
def test_refused_original_stop_recovery_from_fresh_shell(tmp_path,mode):
    server=context(tmp_path,'stop')
    try:
        script='. "$CONTEXT"\n'+r'''
RECOVER_ENGINE=postgres
ABORT_ID=fixture
python3() { printf '%s\n' "$*" >> "$EVIDENCE_DIR/recovery-calls"; }
docker() { printf '%s\n' "$*" >> "$EVIDENCE_DIR/recovery-calls"; }
'''
        script+=block('# BEGIN original recovery checks\n','# END original recovery checks')
        if mode=='clean-stop': script+=block('# BEGIN original clean stop\n','# END original clean stop')
        else:
            # Execute abort's start path after its separately tested extraction.
            script+=block('# BEGIN abort original start\n','# END abort original start')
            (tmp_path/'retained/original-running-services.txt').write_text('postgres\n')
        r=subprocess.run(['bash','-eu','-c',script],env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')},capture_output=True,text=True)
        assert r.returncode==0,r.stderr
        calls=(tmp_path/'evidence/recovery-calls').read_text()
        assert '--phase original-restart' in calls
        assert 'start postgres' in calls
        assert 'wait-healthy postgres --timeout 300' in calls
        assert 'start --wait' not in calls
        if mode=='clean-stop':
            assert 'stop --timeout 300 postgres' in calls
            assert calls.index('stop --timeout') < calls.rindex('--phase original-stop')
            snapshot_call = next(line for line in calls.splitlines() if ' snapshot ' in line)
            assert '--prior ' + str(tmp_path/'evidence/before.json') in snapshot_call
    finally: server.close()


def test_clean_stop_recovery_refuses_sqlite_before_any_commands(tmp_path):
    server = context(tmp_path, 'stop')
    try:
        script = '. "$CONTEXT"\nRECOVER_ENGINE=sqlite\n' + r'''
python3() { echo unexpected-command >> "$EVIDENCE_DIR/calls"; }
docker() { echo unexpected-command >> "$EVIDENCE_DIR/calls"; }
'''
        script += block('# BEGIN original clean stop\n', '# END original clean stop')
        result = subprocess.run(['bash','-eu','-c',script], capture_output=True, text=True,
                                env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')})
        assert result.returncode != 0
        assert 'SQLite exit 137 is expected' in result.stdout
        assert not (tmp_path/'evidence/calls').exists()
    finally: server.close()


def test_population_resume_digest_fragment_cannot_stop_candidates(tmp_path):
    server = context(tmp_path, 'rollback-populate')
    try:
        script = '. "$CONTEXT"\nCONFIG_DIR="$ATTEMPT_DIR/configuration"\nmkdir -p "$CONFIG_DIR"\n' + r'''
python3() { printf '%s\n' "$*" >> "$EVIDENCE_DIR/input-calls"; }
sha256sum() { :; }
bash() { printf '%s\n' "$*" >> "$EVIDENCE_DIR/input-calls"; }
docker() { echo unexpected-stop; return 42; }
'''
        script += block('# BEGIN rollback input verification\n', '# END rollback input verification')
        result = subprocess.run(['bash','-eu','-c',script], capture_output=True, text=True,
                                env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')})
        assert result.returncode == 0, result.stderr
        assert 'unexpected-stop' not in result.stdout
        calls=(tmp_path/'evidence/input-calls').read_text()
        assert 'check-images' in calls and 'cold-copies.stream.sha256' in calls
        assert 'snapshot' not in calls
    finally: server.close()


def test_population_failure_resumes_in_fresh_shell_without_restore(tmp_path):
    server=context(tmp_path,'rollback-down')
    try:
        script='. "$CONTEXT"\n' + r'''
python3() { :; }
podman() { case "$1 $2" in 'volume exists') return 1;; 'volume create') return 0;; 'volume inspect') printf /scratch/target;; 'unshare cp') return 45;; esac; }
'''
        script+=block('# BEGIN rollback population\n','# END rollback population')
        env={'PATH':os.environ['PATH'],'CONTEXT':str(tmp_path/'resume-context.bash')}
        failed=subprocess.run(['bash','-eu','-c',script],env=env,capture_output=True,text=True)
        assert failed.returncode==45,failed.stderr
        script='. "$CONTEXT"\ntest "$TEARDOWN_PHASE" = rollback-populate\n'+r'''
python3() { printf '%s\n' "$*" >> "$EVIDENCE_DIR/populate-calls"; }
podman() {
 case "$1 $2" in
 'volume exists') return 0;;
 'volume inspect') case "$*" in *Labels*) printf '%s' "$TEARDOWN_ATTEMPT";; *) printf /scratch/target;; esac;;
 'volume create') return 46;;
 'unshare cp') printf 'copy\n' >> "$EVIDENCE_DIR/populate-calls";;
 esac
}
'''
        script+=block('# BEGIN rollback population\n','# END rollback population')
        resumed=subprocess.run(['bash','-eu','-c',script],env=env,capture_output=True,text=True)
        assert resumed.returncode==0,resumed.stderr
        assert (tmp_path/'evidence/populate-calls').read_text().count('copy\n')==4
    finally: server.close()
