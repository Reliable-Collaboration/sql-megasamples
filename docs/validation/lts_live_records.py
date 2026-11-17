"""Compare a rebuilt live corpus to the original frozen core/append receipts."""
from copy import deepcopy


def compare_frozen_records(previous, current, specs):
    expected = deepcopy(previous)
    for name in previous:
        if specs[name].get('append'):
            continue
        for alias, record in previous.items():
            if not specs[alias].get('append') or specs[alias]['database'] != specs[name]['database']:
                continue
            for stage, tables in record.items():
                for table, value in tables.items():
                    target = expected[name].setdefault(stage, {})
                    if table in target:
                        assert target[table] == value, 'Original frozen receipts disagree'
                    target[table] = deepcopy(value)
    assert current == expected, 'Rebuilt live-feed records differ from the original frozen core/append corpus'
    return expected
