"""Run whole runbook fences with command fixtures, never a real container tool.

The shell body is written unchanged. Fixtures log actual source-line calls;
each reached assertion/helper gate is then rejected individually. Real shell
branches, loops, substitutions, redirections and error handling remain in use.
"""
from pathlib import Path
import re
import subprocess

STUBS = r'''
_hit() {
  local line=$1 tool=$2; shift 2
  printf '%s|%s|%s\n' "$line" "$tool" "$*" >> "$FIXTURE/calls"
  if [[ "$FAIL_LINE" = "$line" && "$FAIL_TOOL" = "$tool" ]]; then
    printf '%s\n' "$line|$tool" >> "$FIXTURE/rejected"
    return 73
  fi
}
_effect() {
  if [[ -f "$FIXTURE/rejected" ]]; then
    printf '%s\n' "$*" >> "$FIXTURE/unsafe"
  fi
}
test() {
  _hit "${BASH_LINENO[0]}" test "$@" || return 73
  case " $* " in
    *'git-status.txt '*) return 0;;
    ' -S '*|' -s '*|' -d '*) return 0;;
    ' -f '*) [[ "$2" != *'/.env' && "$2" != .env ]]; return;;
    ' -e '*) return 1;;
    ' ! -e '*) return 0;;
    ' ! -s '*) return 0;;
    *) builtin test "$@"; return;;
  esac
}
cd() { if [[ "$1" = /home/rcc-vstudio/working/sql-megasamples ]]; then builtin cd "$FIXTURE"; else builtin cd "$@"; fi; }
date() { printf fixture; }
chmod() { :; }
sleep() { :; }
cp() { _hit "${BASH_LINENO[0]}" cp "$@" || return 73; _effect cp "$@"; }
mv() { _hit "${BASH_LINENO[0]}" mv "$@" || return 73; }
rm() {
  # The bootstrap's EXIT trap removes only its temporary route report. It is
  # expected even on refusal, unlike data/store cleanup.
  if [[ -n "${BOOTSTRAP_REPORT:-}" && "${@: -1}" = "$BOOTSTRAP_REPORT" &&
        "$BOOTSTRAP_REPORT" = "$FIXTURE"/build/rollback-route.*.json ]]; then
    return 0
  fi
  _effect rm "$@"
}
mkdir() { command mkdir -p "$@" 2>/dev/null || :; }
mktemp() { command mktemp "$@"; }
git() {
  _hit "${BASH_LINENO[0]}" git "$@" || return 73
  case "$*" in
    'merge-base --is-ancestor fixture HEAD')
      [[ -f "$FIXTURE/ancestor-checked" ]] || { : > "$FIXTURE/ancestor-checked"; return 1; };;
    'rev-parse '*) printf fixture;;
    'status '*) :;;
    'show '*) printf '# fixture\n';;
  esac
}
gh() { _hit "${BASH_LINENO[0]}" gh "$@" || return 73; printf fixture; }
sha256sum() { _hit "${BASH_LINENO[0]}" sha256sum "$@" || return 73; }
cmp() { _hit "${BASH_LINENO[0]}" cmp "$@" || return 73; }
tar() { _hit "${BASH_LINENO[0]}" tar "$@" || return 73; }
bash() { _hit "${BASH_LINENO[0]}" bash "$@" || return 73; }
ms_tool() { _hit "${BASH_LINENO[0]}" ms_tool "$@" || return 73; }
save_context() { :; }
stop_project() { _hit "${BASH_LINENO[0]}" stop_project "$@" || return 73; _effect stop_project; }
python3() {
  _hit "${BASH_LINENO[0]}" python3 "$@" || return 73
  case " $* " in
    *' prepare-rollback '*)
      command mkdir -p "$3/rollback-$4/configuration" "$BACKUP_DIR/rollback-fixture/configuration" "$BACKUP_DIR/rollback-abort-fixture/configuration";;
  esac
  if [[ "$1" = -c ]]; then printf '%s' "${FIXTURE_ROUTE:-original-restart}"; fi
  if [[ "$1" = - && "${3-}" = */recovery-functions.bash ]]; then
    printf 'save_context() { :; }\n' > "$3"
  fi
}
podman() {
  if [[ "${FUNCNAME[1]}" = ms_tool ]]; then
    _hit "${BASH_LINENO[1]}" ms_tool "$@" || return 73
  else
    _hit "${BASH_LINENO[0]}" podman "$@" || return 73
  fi
  case "$1 ${2-}" in
    'info --format') printf '%s/graph' "$SCRATCH_DIR";;
    'ps -aq') if [[ "$*" = *--filter* ]]; then printf fixture; fi;;
    'volume exists') return 0;;
    'volume inspect')
      if [[ "$*" = *Mountpoint* ]]; then printf '%s/target' "$FIXTURE"; else printf fixture; fi;;
    'inspect -f')
      case "$3" in
        *com.docker.compose.project*) printf sql-megasamples;;
        *State.Running*) printf true;;
        *Source*) printf '%s/source' "$FIXTURE";;
        *) printf fixture;;
      esac;;
    'image inspect') printf 9cfca77f5b88e23f25e76429d70f0c72959ff13a6d933610c58ae74da67cd710;;
    'exec -i') printf stdin-executed;;
    'image rm'|'system migrate'|'system reset'|'volume rm'|'unshare cp'|'stop '*) _effect podman "$@";;
  esac
}
docker() {
  _hit "${BASH_LINENO[0]}" docker "$@" || return 73
  case " $* " in
    *' config --services '*|*' ps --services '*) printf 'postgres\nmysql\nsqlite\nadminer\n';;
    *' up '*|*' start '*|*' stop '*|*' down '*|*' --force-recreate '*|*' run '*) _effect docker "$@";;
  esac
}
'''


def run_fence(body, directory, fail=None, route='original-restart'):
    directory.mkdir(parents=True)
    # PATH contains only fail-closed executable fixtures. Function stubs above
    # provide modeled commands; a forgotten external command cannot reach tools.
    bin_dir = directory/'bin'; bin_dir.mkdir()
    real_mkdir = Path('/bin/mkdir')
    real_mktemp = Path('/bin/mktemp')
    for tool, real in [('mkdir', real_mkdir), ('mktemp', real_mktemp)]:
        (bin_dir/tool).symlink_to(real)
    for tool in ('podman', 'docker', 'git', 'gh', 'python3', 'cp', 'rm', 'mv', 'kill', 'curl'):
        path = bin_dir/tool
        path.write_text('#!/bin/bash\nexit 97\n'); path.chmod(0o700)
    # cat/sed are read-only on these private fixture paths.
    for tool in ('cat', 'sed', 'basename', 'seq'):
        (bin_dir/tool).symlink_to('/usr/bin/'+tool)
    for name in ('rollback-image-ids.txt', 'original-tool-images.txt'):
        (directory/name).write_text('')
    for name in ('rollback-branch.txt', 'original-commit.txt'):
        (directory/name).write_text('fixture\n')
    (directory/'original-running-services.txt').write_text('postgres\nmysql\nsqlite\nadminer\ncloudbeaver\n')
    (directory/'resume-context.bash').write_text(': # entry strictness belongs to the fence\n')
    for name in ('configuration', 'evidence', 'attempt', 'source', 'target', 'consoles'):
        (directory/name).mkdir()
    (directory/'calls').touch()
    body_file = directory/'body.bash'; body_file.write_text(body)
    env = {name: 'fixture' for name in re.findall(r'\$\{?([A-Za-z_][A-Za-z_0-9]*)', body)}
    env.update(PATH=str(bin_dir), FIXTURE=str(directory), BODY=str(body_file),
               FAIL_LINE=str(fail[0]) if fail else '', FAIL_TOOL=fail[1] if fail else '',
               FIXTURE_ROUTE=route, TEARDOWN_PHASE='stop', CB_WAS_RUNNING='true',
               RECOVER_ENGINE='postgres', EXTRA_RESERVE_BYTES='0')
    for name in ('BACKUP_DIR', 'EVIDENCE_DIR', 'ATTEMPT_DIR', 'CONFIG_DIR', 'XDG_RUNTIME_DIR',
                 'REVIEWED_CHECKOUT', 'METADATA_BUNDLE'):
        env[name] = str(directory)
    env['CONTEXT_FILE'] = str(directory/'resume-context.bash')
    env['DOCKER_HOST'] = 'unix://'+str(directory/'socket')
    env['SCRATCH_DIR'] = str(directory)
    # Use plain Bash and source the complete production body; no caller strictness.
    result = subprocess.run(['/bin/bash', '-c', STUBS+'\n. "$BODY"'], cwd=directory,
                            env=env, capture_output=True, text=True, timeout=10)
    calls = [line.split('|', 2) for line in (directory/'calls').read_text().splitlines()]
    return result, calls


def guard_calls(body, calls):
    """Reached assertion and external validation sites, excluding branch probes.

    Optional file/existence probes choose routes; they are not assertions.
    Destructive commands themselves and final pause verification cannot guard a
    later operation. Each selected call is a real source-line gate, not an
    appended synthetic guard.
    """
    lines = body.splitlines()
    guards = set()
    for line, tool, args in calls:
        number = int(line)
        if not 0 < number <= len(lines):
            continue
        source = lines[number-1].strip()
        if tool == 'test':
            if source.startswith('test ') and '&&' not in source and '||' not in source:
                guards.add((number, tool))
        elif tool in ('stop_project', 'python3', 'ms_tool', 'cmp', 'sha256sum', 'bash', 'gh'):
            # A heredoc helper, snapshot, state/port/health gate or archive check.
            guards.add((number, tool))
        elif tool == 'git' and source.startswith(('git cat-file ', 'git merge-base ')):
            guards.add((number, tool))
    return sorted(guards)
