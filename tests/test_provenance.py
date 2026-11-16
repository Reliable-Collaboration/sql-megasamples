"""Generated provenance must distinguish fixed inputs from changing live-feed snapshots."""
from megasamples.provenance import build_provenance


def render(live=False, measured=False):
    cfg = {'record': 'knowledge/datasets/chicago_crimes.md', 'licenses': [], 'live': live}
    artifacts = [{'id': 'sample.csv', 'size_bytes': 12, 'sha256': 'a' * 64, 'live': live}]
    return build_provenance('chicago_crimes', cfg, artifacts, ({}, {}), measured, {})


def test_fixed_artifacts_remain_described_as_pinned():
    assert 'Every byte this database is built from, pinned.' in render()


def test_live_artifacts_identify_the_observed_snapshot_provenance():
    text = render(live=True)
    assert 'historical snapshot' in text
    assert '`megasamples.datasets.artifacts`' in text
    assert '.meta.json' in text
    assert 'Every byte this database is built from, pinned.' not in text


def test_live_measurements_are_floors_and_ports_match_the_build_snapshot():
    text = render(live=True, measured=True)
    assert 'snapshot floors' in text
    assert 'exact' in text
    assert 'query plans and canonical query results are pinned' not in text
