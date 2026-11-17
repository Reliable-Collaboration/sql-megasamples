"""The LTS receipt must cover append tables without changing frozen values."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('lts_live_records', Path(__file__).parents[1] / 'docs/validation/lts_live_records.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
compare = module.compare_frozen_records


def records():
    previous = {'core': {'counts': {'base': 2}, 'digests': {'base': {'n': 2, 'x': 10, 's': 20}}, 'views': {}},
                'extra': {'counts': {'appended': 3}, 'digests': {'appended': {'n': 3, 'x': 30, 's': 40}}, 'views': {}}}
    expanded = {'core': {stage: {**previous['core'][stage], **previous['extra'][stage]} for stage in previous['core']},
                'extra': previous['extra']}
    specs = {'core': {'database': 'db'}, 'extra': {'database': 'db', 'append': True}}
    return previous, expanded, specs


def test_original_append_receipt_completes_expanded_core():
    previous, expanded, specs = records()
    assert compare(previous, expanded, specs) == expanded
    assert previous['core']['counts'] == {'base': 2}


@pytest.mark.parametrize('stage', ['counts', 'digests'])
@pytest.mark.parametrize('table', ['base', 'appended'])
def test_every_original_frozen_value_still_required(stage, table):
    previous, expanded, specs = records()
    expanded['core'][stage][table] = 999
    with pytest.raises(AssertionError):
        compare(previous, expanded, specs)


def test_unfrozen_extra_table_rejected():
    previous, expanded, specs = records()
    expanded['core']['counts']['unfrozen'] = 4
    with pytest.raises(AssertionError):
        compare(previous, expanded, specs)
