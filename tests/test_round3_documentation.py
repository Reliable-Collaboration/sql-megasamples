"""Round-three documentation regressions; no service or secret inputs."""
from pathlib import Path

ROOT=Path(__file__).parents[1]


def test_superseded_scanner_policies_are_explicitly_historical():
    evidence=(ROOT/'docs/live-upgrade-evidence.md').read_text()
    for phrase in ['all engines exited','The owner-scoped scanner reports']:
        paragraph=next(p for p in evidence.split('\n\n') if phrase in p)
        assert 'historical' in paragraph.lower()
    assert '#teardown-and-rollback-states-and-gates' in evidence

