"""Committed evidence identifies source rounds and notes without personal attribution."""
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).parents[1]


def test_committed_follow_up_files_do_not_name_reviewers():
    # Split aliases so the check itself contains no named attribution.
    pattern = re.compile(r'\b(?:' + '|'.join(('As'+'tra', 'Fa'+'ble')) + r')\b', re.I)
    # Preserve pre-existing dataset provenance outside this PR and its fixed base.
    files = subprocess.check_output(['git', 'diff', '--name-only', '-z', '3bef1436', 'HEAD'], cwd=ROOT).decode().split('\0')
    override = os.environ.get('DL086_FOLLOW_UP_RECEIPT_SOURCE')
    offending = []
    for name in filter(None, files):
        path = Path(override) if override and name == 'docs/validation/live-upgrade-follow-up-2026-11-19.json' else ROOT/name
        if path.is_file() and pattern.search(path.read_bytes().decode('utf-8', errors='replace')):
            offending.append(name)
    assert not offending, offending


def test_follow_up_wording_and_listing_record_match_behavior():
    evidence = Path(os.environ.get('DL086_EVIDENCE_SOURCE', ROOT/'docs/live-upgrade-evidence.md')).read_text()
    runbook = Path(os.environ.get('DL089_RUNBOOK_SOURCE', ROOT/'docs/live-upgrade-runbook.md')).read_text()
    assert 'containers, conmon-named and unrelated occupants' in evidence
    assert 'retains a dead-at-capture conmon PID with an absence marker and\nignores' in evidence
    assert 'B-3 also stops before cleanup on a failed or non-empty container listing' in evidence
    assert '913a380' in evidence and '614ecc3' in evidence
    assert 'positive decimal PID' in runbook and 'malformed PID file holds' in runbook
    assert 'valid PID with no /proc entry is absent on the down route' in runbook
