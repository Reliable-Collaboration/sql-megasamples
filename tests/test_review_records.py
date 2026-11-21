"""Committed evidence identifies source rounds and notes without personal attribution."""
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).parents[1]


def test_committed_follow_up_files_do_not_name_reviewers():
    # Split aliases so the check itself contains no named attribution.
    pattern = re.compile(r'\b(?:' + '|'.join(('As'+'tra', 'Fa'+'ble')) + r')\b', re.I)
    # The attribution rule governs review/validation records, not dataset provenance.
    files = ['docs/history/live-upgrade-evidence.md', *(
        str(path.relative_to(ROOT)) for path in
        sorted((ROOT/'docs/validation').glob('live-upgrade*.json')))]
    override = os.environ.get('DL086_FOLLOW_UP_RECEIPT_SOURCE')
    offending = []
    for name in filter(None, files):
        path = Path(override) if override and name == 'docs/validation/live-upgrade-follow-up-2026-11-19.json' else ROOT/name
        if path.is_file() and pattern.search(path.read_bytes().decode('utf-8', errors='replace')):
            offending.append(name)
    assert not offending, offending


def test_follow_up_wording_and_listing_record_match_behavior():
    evidence = Path(os.environ.get('DL086_EVIDENCE_SOURCE', ROOT/'docs/history/live-upgrade-evidence.md')).read_text()
    runbook = Path(os.environ.get('DL089_RUNBOOK_SOURCE', ROOT/'docs/history/live-upgrade-runbook.md')).read_text()
    assert 'containers, conmon-named and unrelated occupants' in evidence
    assert 'retains a dead-at-capture conmon PID with an absence marker and\nignores' in evidence
    assert 'B-3 also stops before cleanup on a failed or non-empty container listing' in evidence
    assert '913a380' in evidence and '614ecc3' in evidence
    assert 'positive decimal PID' in runbook and 'malformed PID file holds' in runbook
    assert 'valid PID with no /proc entry is absent on the down route' in runbook


def test_attribution_check_uses_only_record_paths_without_git(tmp_path, monkeypatch):
    import sys
    module = sys.modules[__name__]
    records = tmp_path/'docs/validation'
    records.mkdir(parents=True)
    (records/'live-upgrade-follow-up-2026-11-19.json').write_text('{}')
    (tmp_path/'docs/history').mkdir(parents=True)
    (tmp_path/'docs/history/live-upgrade-evidence.md').write_text('Source round and note')
    knowledge = tmp_path/'knowledge/example.md'
    knowledge.parent.mkdir()
    knowledge.write_text('by: claude-code/claude-' + 'fa' + 'ble-example')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    def forbidden_git(*args, **kwargs):
        raise AssertionError('record attribution must work without Git or a base object')
    monkeypatch.setattr(subprocess, 'check_output', forbidden_git)
    test_committed_follow_up_files_do_not_name_reviewers()


def test_manual_cleanup_entry_and_zero_image_metadata_wording():
    evidence = Path(os.environ.get('DL086_EVIDENCE_SOURCE', ROOT/'docs/history/live-upgrade-evidence.md')).read_text()
    runbook = Path(os.environ.get('DL089_RUNBOOK_SOURCE', ROOT/'docs/history/live-upgrade-runbook.md')).read_text()
    cleanup = runbook.split('### Failed rehearsal store: manual cleanup', 1)[1].split('```sh', 1)[0]
    assert 'Use a fresh Bash shell' in cleanup
    assert 'fresh strict Bash shell' not in cleanup
    native = evidence.split('The expanded native B-3 proof', 1)[1].split('The [round-one receipt]', 1)[0]
    assert "zero-image store's metadata file was never created" in native
    assert 'all image metadata was empty' not in native
