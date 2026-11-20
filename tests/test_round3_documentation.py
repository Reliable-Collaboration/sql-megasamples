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


def test_recovery_health_fallback_and_resume_directions():
    text=(ROOT/'docs/live-upgrade-runbook.md').read_text()
    recovery=text.split('For a clean-stop recovery,',1)[1].split('# BEGIN original clean stop',1)[0]
    assert '#manual-health-probe-fallback' in recovery
    assert 'selected engine only' in recovery
    resume=text.split('For **rollback-populate**,',1)[1].split('checkpoint.',1)[0]
    assert '# BEGIN rollback input verification' in resume
    assert '# END rollback input verification' in resume
    assert 'beginning of Roll back' not in resume
    abort=text.split('If abandoning before `.env` rotation',1)[1].split('```sh',1)[0]
    assert 'original recovery checks above' in abort
