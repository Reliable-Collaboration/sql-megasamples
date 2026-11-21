#!/usr/bin/env python3
"""C1–C5 planted defects in private source copies; never operates a store."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = Path(tempfile.mkdtemp(prefix='reversals-', dir=ROOT/'build/dl086-review-r1'))
    scanner = (ROOT/'docs/validation/quiescence.py').read_text()
    runbook = (ROOT/'docs/history/live-upgrade-runbook.md').read_text()
    evidence = (ROOT/'docs/history/live-upgrade-evidence.md').read_text()
    upgrade = (ROOT/'docs/validation/live-upgrade.py').read_text()
    controls = []
    def change(source, before, after):
        assert before in source, before
        return source.replace(before, after, 1)
    def add(name, variable, source, tests): controls.append((name, variable, source, tests))
    down = 'tests/test_quiescence_down.py::'
    strict_tests = ['tests/test_runbook_strictness.py']
    # Remove strictness separately from each destructive fenced block.
    command = re.compile(r'^(?!\s*#).*?(?:\brm -f\b|podman (?:image rm|volume rm|system migrate)\b|docker compose[^\n]*\bdown(?: |$))', re.M)
    for number, match in enumerate(re.finditer(r'^```sh\n(.*?)^```', runbook, re.M | re.S)):
        if not command.search(match[1]): continue
        body = change(match[1], 'set -eu\n', ': # planted missing strictness\n')
        broken = runbook[:match.start(1)] + body + runbook[match.end(1):]
        tests = strict_tests + (['tests/test_scratch_runbook.py::test_failed_scratch_manual_cleanup_is_scoped_and_guarded'] if '# BEGIN failed scratch cleanup' in body else [])
        add('C1 strict entry block '+str(number), 'DL089_RUNBOOK_SOURCE', broken, tests)
    original_receipt = subprocess.check_output(['git', 'show', '9149ff93:docs/validation/live-upgrade-follow-up-2026-11-19.json'], cwd=ROOT, text=True)
    add('C2 original named attribution', 'DL086_FOLLOW_UP_RECEIPT_SOURCE', original_receipt, ['tests/test_review_records.py::test_committed_follow_up_files_do_not_name_reviewers'])
    for indent, site in [('                ', 'capture'), ('            ', 'verify')]:
        guard = indent+"if not re.fullmatch(r'[1-9][0-9]*', pid):\n"+indent+"    raise ValueError('store helper PID must be a positive decimal')\n"
        add('C3 missing '+site+' PID validation', 'DL088_GATE_SOURCE', change(scanner, guard, ''), [down+'test_malformed_shared_pidfile_holds'])
    add('C4 birth read before known absence', 'DL088_GATE_SOURCE', change(scanner,
        "if int(conmon) and not (row.get('conmon_absent') and int(conmon) == row.get('conmon')):", 'if int(conmon):'),
        [down+'test_known_absent_conmon_unreadable_reuse_keeps_independent_checks'])
    add('C4 lost cgroup refusal', 'DL088_GATE_SOURCE', change(scanner,
        "refusals.append(dict(reason='live deployment cgroup task', pid=int(pid)))", 'pass # planted missing cgroup obligation'),
        [down+'test_known_absent_conmon_unreadable_reuse_keeps_independent_checks'])
    add('C4 lost source holders', 'DL088_GATE_SOURCE', change(scanner,
        "report['refusals'] += scan['holders']", "report['refusals'] += []"),
        [down+'test_known_absent_conmon_unreadable_reuse_keeps_independent_checks'])
    start = runbook.index('# END pre-up process gate\n')
    for flag in ('--no-deps',):
        tail = change(runbook[start:], 'up -d '+flag+' --wait', 'up -d --wait')
        add('C5 engines lose '+flag, 'DL089_RUNBOOK_SOURCE', runbook[:start]+tail,
            ['tests/test_runbook_fragments.py::test_original_startup_never_adds_dependencies', 'tests/test_follow_up_runbook.py'])
    listing = '  SCRATCH_CONTAINERS=$(podman ps -aq)\n  test -z "$SCRATCH_CONTAINERS"'
    add('C5 B-3 listing error hidden by substitution', 'DL089_RUNBOOK_SOURCE', change(runbook, listing, '  test -z "$(podman ps -aq)"'),
        ['tests/test_scratch_runbook.py::test_scratch_rehearsal_reruns_in_new_store'])
    add('C5 B-3 non-empty listing ignored', 'DL089_RUNBOOK_SOURCE', change(runbook, listing, '  SCRATCH_CONTAINERS=$(podman ps -aq)'),
        ['tests/test_scratch_runbook.py::test_scratch_rehearsal_reruns_in_new_store'])
    add('C5 pre-marker row reinspection discarded', 'DL088_GATE_SOURCE', change(scanner,
        '            evidence.update(conmon=int(conmon), mode=mode)',
        "            if row.get('conmon') == 0: conmon = '0'\n            evidence.update(conmon=int(conmon), mode=mode)"),
        [down+'test_pre_marker_down_row_keeps_conservative_reuse_result'])
    add('C5 missing MySQL header validation', 'DL086_UPGRADE_SOURCE', change(upgrade,
        "raise ValueError('invalid MySQL greeting header')", "pass # planted missing header rejection"),
        ['tests/test_live_upgrade.py::test_forwarded_protocol_socket_fixture'])
    add('C5 inaccurate occupant wording', 'DL086_EVIDENCE_SOURCE', change(evidence,
        'containers, conmon-named and unrelated occupants', 'containers, helper and non-helper occupants'),
        ['tests/test_review_records.py::test_follow_up_wording_and_listing_record_match_behavior'])
    add('C5 omitted down-route PID guidance', 'DL089_RUNBOOK_SOURCE', change(runbook,
        'malformed PID file holds', 'invalid evidence is investigated'),
        ['tests/test_review_records.py::test_follow_up_wording_and_listing_record_match_behavior'])
    for name, before, after in (
        ('capture grammar', 'retains a dead-at-capture conmon PID with an absence marker and\nignores', 'retain a dead-at-capture conmon PID with an absence marker and\nignores'),
        ('B-3 listing record', 'B-3 also stops before cleanup on a failed or non-empty container listing', 'Rehearsal listing checked'),
        ('fixture correction record', '913a380', 'earlier test-only correction'),
    ):
        add('C5 '+name, 'DL086_EVIDENCE_SOURCE', change(evidence, before, after),
            ['tests/test_review_records.py::test_follow_up_wording_and_listing_record_match_behavior'])
    # Exercise the real account assertion against later, credential-free init SQL.
    for number, roles in enumerate(('admin', 'other, admin', '"admin"', '"other", "admin", another')):
        fixture = out/('grant-'+str(number)); init = fixture/'engines/postgres/init'; init.mkdir(parents=True)
        (init/'00-users.sql').write_text('CREATE ROLE admin WITH LOGIN CREATEDB CREATEROLE;\nGRANT ALL ON datasets TO admin;\n')
        (init/'99-extra.sql').write_text(f'GRANT SELECT ON extra TO {roles} WITH GRANT OPTION;\n')
        (fixture/'engines/postgres/Dockerfile').write_text('OWNER admin TEMPLATE template0\n')
        wrapper = out/('test_grant_'+str(number)+'.py')
        wrapper.write_text('''import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('checks', '''+repr(str(ROOT/'tests/test_demo_documentation.py'))+''')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_later_grant():
    m.ROOT = Path('''+repr(str(fixture))+''')
    m.admin_scope('CREATEDB CREATEROLE owns the sample databases registry without grant option not a superuser', 'postgres')
''')
        add('C5 later grant role shape '+str(number), None, None, [str(wrapper)])
    results = []
    for number, (name, variable, source, tests) in enumerate(controls):
        env = dict(os.environ)
        if variable:
            path = out/(str(number)+('.py' if variable in ('DL088_GATE_SOURCE', 'DL086_UPGRADE_SOURCE') else '.md'))
            path.write_text(source); env[variable] = str(path)
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', *tests], cwd=ROOT,
                                env=env, capture_output=True, text=True, timeout=45)
        (out/(str(number)+'.log')).write_text(result.stdout+result.stderr)
        count = re.search(r'(\d+) failed', result.stdout)
        assert result.returncode == 1 and count and 'ERROR collecting' not in result.stdout, (name, out, result.stdout[-700:])
        results.append(dict(control=name, status='Passed', failures=int(count[1]), log=str((out/(str(number)+'.log')).relative_to(ROOT))))
    (out/'receipt.json').write_text(json.dumps(dict(status='Passed', results=results), indent=2)+'\n')
    print(json.dumps(dict(status='Passed', controls=len(results), artifacts=str(out.relative_to(ROOT)))))


if __name__ == '__main__':
    main()
