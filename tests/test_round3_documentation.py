"""Round-three documentation regressions; no service or secret inputs."""
from pathlib import Path

ROOT=Path(__file__).parents[1]


def test_superseded_scanner_policies_are_explicitly_historical():
    evidence=(ROOT/'docs/live-upgrade-evidence.md').read_text()
    for phrase in ['all engines exited','The owner-scoped scanner reports']:
        paragraph=next(p for p in evidence.split('\n\n') if phrase in p)
        assert 'historical' in paragraph.lower()
    assert '#teardown-and-rollback-states-and-gates' in evidence


def test_failure_windows_use_command_time_not_attempt_id():
    text=(ROOT/'docs/live-upgrade-runbook.md').read_text()
    for line in text.splitlines():
        if '.log.timestamps' in line and '>>' in line:
            assert line.lstrip().startswith('date -u '),line


def test_author_logs_never_claim_independence():
    receipt=(ROOT/'docs/validation/live-upgrade-review-r2-2026-11-18.json').read_text()
    assert 'independent-review-' not in receipt
