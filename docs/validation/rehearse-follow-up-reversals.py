#!/usr/bin/env python3
"""Plant follow-up defects in private copies; report actual pytest failures."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    out = Path(tempfile.mkdtemp(prefix='reversals-', dir=ROOT/'build/dl086-follow-up'))
    scanner = (ROOT/'docs/validation/quiescence.py').read_text()
    runbook = (ROOT/'docs/live-upgrade-runbook.md').read_text()
    evidence = (ROOT/'docs/live-upgrade-evidence.md').read_text()
    readme = (ROOT/'README.md').read_text()
    upgrade = (ROOT/'docs/validation/live-upgrade.py').read_text()
    controls = []
    def change(source, before, after):
        assert before in source, before
        return source.replace(before, after)
    def add(name, variable, source, tests): controls.append((name, variable, source, tests))
    down = 'tests/test_quiescence_down.py::'
    original = subprocess.check_output(['git', 'show', '3bef1436:docs/validation/quiescence.py'], cwd=ROOT, text=True)
    add('B-2 original lost PID', 'DL088_GATE_SOURCE', original, [down+'test_dead_at_capture_conmon_pid_reuse_is_not_continuity'])
    add('B-2 absent PID treated as live continuity', 'DL088_GATE_SOURCE', change(scanner,
        " and not r.get('conmon_absent')", ''), [down+'test_dead_at_capture_conmon_pid_reuse_is_not_continuity'])
    add('B-2 omitted retained-record limit', 'DL086_EVIDENCE_SOURCE', change(evidence,
        'Existing captures without the absence marker', 'Retained old captures'),
        ['tests/test_round12_documentation.py::test_fixed_pid_and_native_scratch_limits_are_retired'])
    add('B-5 original ENOENT hold', 'DL088_GATE_SOURCE', original, [down+'test_stale_shared_pidfile_with_missing_proc_entry_is_absent'])
    original_runbook = subprocess.check_output(['git', 'show', '3bef1436:docs/live-upgrade-runbook.md'], cwd=ROOT, text=True)
    add('B-4 and B-7 silent empty-listing exit', 'DL089_RUNBOOK_SOURCE', original_runbook,
        ['tests/test_round9_runbook.py::test_empty_original_listing_still_refuses_policy_pause'])
    add('B-7 lost shell boundary', 'DL089_RUNBOOK_SOURCE', change(runbook,
        '# Pause restart automation here; continue with the separate guarded step below.\n```',
        '# Pause restart automation here; continue with the separate guarded step below.'),
        ['tests/test_round9_runbook.py::test_rollback_policy_pause_is_a_separate_guarded_step'])
    add('B-3 missing graph guard', 'DL089_RUNBOOK_SOURCE', change(runbook,
        '  test "$(podman info --format \'{{.Store.GraphRoot}}\')" = "$SCRATCH_DIR/graph"', '  : # planted missing graph guard'),
        ['tests/test_scratch_runbook.py::test_failed_scratch_manual_cleanup_is_scoped_and_guarded'])
    add('B-6 missing retry space guidance', 'DL089_RUNBOOK_SOURCE', change(runbook,
        'third image set', 'additional copy'), ['tests/test_round12_documentation.py::test_failed_rehearsal_resume_names_cleanup_and_extra_space'])
    add('B-8 detached read grant clause', 'DL086_README_SOURCE', change(readme,
        'reads sample tables', 'uses sample relations'), ['tests/test_demo_documentation.py::test_readme_demo_scope_matches_init_sql[postgres]'])
    add('B-8 broken IPv6 word decoding', 'DL088_GATE_SOURCE', change(scanner,
        'address = ipaddress.ip_address(packed)', "address = ipaddress.ip_address(packed if name == 'tcp' else bytes(16))"),
        [down+'test_down_port_helper_matches_address_and_family'])
    for name, variable, source in [('runbook', 'DL089_RUNBOOK_SOURCE', runbook), ('evidence', 'DL086_EVIDENCE_SOURCE', evidence)]:
        add('B-9 omitted source/holder boundary '+name, variable, change(source,
            "older capture's source and holder checks are not repeated", 'obsolete checks are omitted'),
            ['tests/test_round12_documentation.py::test_legacy_history_scope_names_source_and_holder_exclusions'])
    add('B-10 misleading applicability flag', 'DL088_GATE_SOURCE', change(scanner,
        'entry = dict(path=str(path), applicable=applicable)', 'entry = dict(path=str(path), applicable=applicable and not legacy)'),
        [down+'test_legacy_history_checks_survivors_without_endpoint_hold'])
    add('B-11 missing legacy survivors', 'DL088_GATE_SOURCE', change(scanner,
        '            if applicable:\n                prior = verify(', '            if applicable and not legacy:\n                prior = verify('),
        [down+'test_legacy_ordinary_history_by_generation_or_data'])
    add('B-11 lost data-only overlap', 'DL088_GATE_SOURCE', change(scanner,
        'if not (generation or data):', 'if not generation:'), [down+'test_legacy_ordinary_history_by_generation_or_data'])
    add('B-11 ignored historical shared helper', 'DL088_GATE_SOURCE', change(scanner,
        "shared = saved['shared_helper']", "shared = None if _identity_only else saved['shared_helper']"),
        [down+'test_legacy_ordinary_history_by_generation_or_data'])
    # A new later init grant exercises the former vacuous scope assertion without copying credentials.
    fixture = out/'grant-fixture'
    init = fixture/'engines/postgres/init'; init.mkdir(parents=True)
    (init/'00-users.sql').write_text('CREATE ROLE admin WITH LOGIN CREATEDB CREATEROLE;\nGRANT ALL ON datasets TO admin;\n')
    (init/'99-extra.sql').write_text('GRANT SELECT ON extra TO admin WITH GRANT OPTION;\n')
    (fixture/'engines/postgres/Dockerfile').write_text('OWNER admin TEMPLATE template0\n')
    wrapper = out/'test_grant_control.py'
    wrapper.write_text('''import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('account_checks', '''+repr(str(ROOT/'tests/test_demo_documentation.py'))+''')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_later_grant_must_not_gain_grant_option():
    m.ROOT = Path('''+repr(str(fixture))+''')
    m.admin_scope('CREATEDB CREATEROLE owns the sample databases registry without grant option not a superuser', 'postgres')
''')
    add('B-12 later init grant option', None, None, [str(wrapper)])
    add('B-14 original combined start', 'DL089_RUNBOOK_SOURCE', original_runbook,
        ['tests/test_follow_up_runbook.py::test_cold_restore_waits_for_engines_before_consoles'])
    add('B-15 wrong archive refusal reason', 'DL086_UPGRADE_SOURCE', change(upgrade,
        "raise ValueError('phase-A receipt differs from rollback mapping')", "raise ValueError('unrelated archive failure')"),
        ['tests/test_live_upgrade.py::test_retained_live_phase_a_layout'])
    add('B-15 wrong protocol refusal reason', 'DL086_UPGRADE_SOURCE', change(upgrade,
        "raise ValueError('invalid PostgreSQL SSLRequest response')", "raise ValueError('unrelated protocol failure')"),
        ['tests/test_live_upgrade.py::test_forwarded_protocol_socket_fixture'])
    add('B-15 wrong SSLRequest bytes', 'DL086_UPGRADE_SOURCE', change(upgrade,
        'struct.pack(\'!II\', 8, 80877103)', 'struct.pack(\'!II\', 8, 80877104)'),
        ['tests/test_live_upgrade.py::test_forwarded_protocol_socket_fixture'])
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
        assert result.returncode == 1 and count and 'ERROR collecting' not in result.stdout, (name, out, result.stdout[-600:])
        results.append(dict(control=name, status='Passed', failures=int(count[1]), log=str((out/(str(number)+'.log')).relative_to(ROOT))))
    (out/'receipt.json').write_text(json.dumps(dict(status='Passed', results=results), indent=2)+'\n')
    print(json.dumps(dict(status='Passed', controls=len(results), artifacts=str(out.relative_to(ROOT)))))


if __name__ == '__main__':
    main()
