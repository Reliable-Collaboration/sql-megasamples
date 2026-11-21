#!/usr/bin/env python3
"""D1–D4 reversals in private copies; shell/container calls remain test fixtures."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = Path(tempfile.mkdtemp(prefix='reversals-', dir=ROOT/'build/dl086-review-r2'))
    runbook = (ROOT/'docs/history/live-upgrade-runbook.md').read_text()
    evidence = (ROOT/'docs/history/live-upgrade-evidence.md').read_text()
    controls = []

    def add(name, variable, source, tests, required=None):
        controls.append((name, variable, source, tests, required))

    records = ['tests/test_review_records.py::test_committed_follow_up_files_do_not_name_reviewers']
    original = subprocess.check_output(['git', 'show', '9149ff93:docs/validation/live-upgrade-follow-up-2026-11-19.json'], cwd=ROOT, text=True)
    add('D1 original receipt attribution', 'DL086_FOLLOW_UP_RECEIPT_SOURCE', original, records)
    # Reverse only the record-path implementation, keeping the no-Git regression.
    current = (ROOT/'tests/test_review_records.py').read_text()
    old = subprocess.check_output(['git', 'show', 'e1d7b07:tests/test_review_records.py'], cwd=ROOT, text=True)
    start = current.index('    # The attribution rule')
    end = current.index('    override = ', start)
    old_start = old.index('    # Preserve pre-existing')
    old_end = old.index('    override = ', old_start)
    broken = current[:start]+old[old_start:old_end]+current[end:]
    broken = broken.replace('ROOT = Path(__file__).parents[1]', 'ROOT = Path('+repr(str(ROOT))+')')
    path = out/'test_old_record_scan.py'; path.write_text(broken)
    add('D1 Git-dependent expanding scan', None, None,
        [str(path)+'::test_attribution_check_uses_only_record_paths_without_git'], 'must work without Git')

    strict = ['tests/test_runbook_strictness.py']
    # Each new D2 fence has its own reversal, including actual state/port/health
    # tests for both recovery fences. The class still checks its entry too.
    for marker in ('partial stop retry', 'original clean stop', 'rollback population', 'unchanged volume recovery'):
        needle = 'set -eu\n# BEGIN '+marker+'\n'
        assert needle in runbook
        broken = runbook.replace(needle, '# BEGIN '+marker+'\n', 1)
        add('D2 missing strict entry '+marker, 'DL089_RUNBOOK_SOURCE', broken,
            strict+['tests/test_follow_up_runbook.py::test_real_restore_fence_failed_gate_in_plain_bash'])
    needle = "'set -eu' 'umask 077'"
    assert needle in runbook
    add('D2 saved context loses strictness', 'DL089_RUNBOOK_SOURCE', runbook.replace(needle, "'umask 077'", 1),
        ['tests/test_runbook_strictness.py::test_saved_context_supplies_strictness_in_plain_bash'])
    # Reverse the command discovery refinements in a private test copy.
    current = (ROOT/'tests/test_runbook_strictness.py').read_text()
    broken = current.replace(r'(?<![\w-])rm(?:\s|$)', r'\brm(?:\s|$)').replace('.replace("\\\\\\n", " ")', '')
    assert broken != current
    path = out/'test_old_discovery.py'; path.write_text(broken)
    add('D2 disposable option misclassified', None, None,
        [str(path)+'::test_class_ignores_disposable_option_and_joins_continuations'])

    match = next(m for m in re.finditer(r'^```sh\n(.*?)^```', runbook, re.M | re.S) if 'save_context() {' in m[1])
    broken_body = match[1].replace('set -eu\n', 'set -eu\nset +e\n', 1)
    broken = runbook[:match.start(1)]+broken_body+runbook[match.end(1):]
    add('D3 actual preparation disables errexit after entry', 'DL089_RUNBOOK_SOURCE', broken,
        ['tests/test_runbook_strictness.py::test_destructive_block_is_strict_in_plain_bash'],
        'guard did not stop|destructive command followed')
    wording = ['tests/test_review_records.py::test_manual_cleanup_entry_and_zero_image_metadata_wording']
    add('D4 obsolete strict-shell wording', 'DL089_RUNBOOK_SOURCE',
        runbook.replace('Use a fresh Bash shell with the same initial', 'Use a fresh strict Bash shell with the same initial', 1), wording)
    needle = "The loaded stores' image metadata\nwas empty; the zero-image store's metadata file was never created."
    assert needle in evidence
    add('D4 absent metadata described as empty', 'DL086_EVIDENCE_SOURCE',
        evidence.replace(needle, 'All image metadata was empty.', 1), wording)

    results = []
    for number, (name, variable, source, tests, required) in enumerate(controls):
        env = dict(os.environ, PYTHONPATH=str(ROOT/'tests')+os.pathsep+str(ROOT))
        if variable:
            path = out/(str(number)+'.md'); path.write_text(source); env[variable] = str(path)
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *tests], cwd=ROOT,
                                env=env, capture_output=True, text=True, timeout=60)
        log = out/(str(number)+'.log'); log.write_text(result.stdout+result.stderr)
        failures = re.search(r'(\d+) failed', result.stdout)
        assert result.returncode == 1 and failures and 'ERROR collecting' not in result.stdout, (name, log, result.stdout[-900:])
        assert not required or re.search(required, result.stdout), (name, log)
        results.append(dict(control=name, status='Passed', failures=int(failures[1]), log=str(log.relative_to(ROOT))))
    receipt = dict(status='Passed', results=results)
    (out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(dict(status='Passed', controls=len(results), artifacts=str(out.relative_to(ROOT)))))


if __name__ == '__main__':
    main()
