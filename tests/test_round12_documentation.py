"""Round-twelve native-evidence boundary and recovery direction."""
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize('name,variable', [
    ('docs/history/live-upgrade-runbook.md', 'DL089_RUNBOOK_SOURCE'),
    ('docs/history/live-upgrade-evidence.md', 'DL086_EVIDENCE_SOURCE'),
])
def test_wildcard_native_limit_is_explicit(name, variable):
    document = Path(os.environ.get(variable, ROOT/name)).read_text()
    assert 'wildcard cases are fixture-tested' in document
    assert 'not natively proved' in document


def test_original_restart_hold_pointer_points_above():
    document = Path(os.environ.get('DL089_RUNBOOK_SOURCE', ROOT/'docs/history/live-upgrade-runbook.md')).read_text()
    assert 'partial-original-restart hold above' in document
    assert 'partial-original-restart hold below' not in document


@pytest.mark.parametrize('name,variable', [
    ('docs/history/live-upgrade-runbook.md', 'DL089_RUNBOOK_SOURCE'),
    ('docs/history/live-upgrade-evidence.md', 'DL086_EVIDENCE_SOURCE'),
])
def test_legacy_history_scope_names_source_and_holder_exclusions(name, variable):
    document = Path(os.environ.get(variable, ROOT/name)).read_text()
    assert "older capture's source and holder checks are not repeated" in document


def test_failed_rehearsal_resume_names_cleanup_and_extra_space():
    document = Path(os.environ.get('DL089_RUNBOOK_SOURCE', ROOT/'docs/history/live-upgrade-runbook.md')).read_text()
    section = document.split('### Resume or abort preparation', 1)[1].split('### Failed rehearsal store', 1)[0]
    assert '[manual cleanup](#failed-rehearsal-store-manual-cleanup)' in section
    assert 'third image set' in section and 'budgets two' in section
    assert 'space gate' in section


def test_fixed_pid_and_native_scratch_limits_are_retired():
    document = Path(os.environ.get('DL086_EVIDENCE_SOURCE', ROOT/'docs/history/live-upgrade-evidence.md')).read_text()
    assert 'its PID is lost from the capture' not in document
    assert 'has run only against stubbed Podman' not in document
    assert 'manual cleanup exit 0' in document
    assert 'one small image' in document
    assert 'Existing captures without the absence marker' in document
