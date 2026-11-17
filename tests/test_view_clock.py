"""Time-dependent view baselines must keep their original values across UTC midnight."""
import copy
import json

import pytest

from megasamples import verify
from megasamples.engines.mysql import adapter


def test_clock_applies_to_each_fingerprint_without_leaking_to_other_checks(monkeypatch):
    sql = []
    monkeypatch.setattr(adapter.db, 'rows', lambda statement: sql.append(statement) or [['1', '2', '3']])
    ordinary = adapter.MySQLAdapter()
    frozen = ordinary.with_clock('2026-11-16T00:00:00Z')
    assert frozen.fingerprint('example', 'ages', [('age', 'int')]) == (1, 2, 3)
    assert sql[-1].startswith('SET timestamp=1794787200; ')
    assert '`age`' in sql[-1]
    ordinary.fingerprint('example', 'ages', [('age', 'int')])
    assert not sql[-1].startswith('SET timestamp=')


@pytest.mark.parametrize('value', ['2026-11-16', '2026-11-16T00:00:00-06:00', '1970-01-01T00:00:00Z', '2040-01-01T00:00:00Z', '2026-11-16T00:00:00.5Z', "'; DROP DATABASE example", 12])
def test_invalid_clock_is_rejected(value):
    with pytest.raises(ValueError):
        adapter.MySQLAdapter().with_clock(value)


def test_view_stage_compares_all_existing_digest_fields_under_the_recorded_clock(tmp_path):
    class Ad:
        name = 'mysql'
        exact_decimals = True
        frozen = False
        def with_clock(self, value):
            assert value == '2026-11-16T00:00:00Z'
            result = copy.copy(self)
            result.frozen = True
            return result
        def views(self, schema): return ['ages']
        def view_columns(self, schema, view): return [('age', 'int')]
        def fingerprint(self, schema, view, cols): return (1, 2, 3) if self.frozen else (1, 99, 99)
        def views_not_ported(self, schema): return set()
        def view_has_unordered_aggregate(self, schema, view): return False
    (tmp_path / 'tests').mkdir()
    expected = {'ages': {'n': 1, 'x': 2, 's': 3, 'columns': ['age'], 'excluded': []}}
    (tmp_path / 'tests/views.yaml').write_text(json.dumps(expected))
    result = verify.Result()
    verify.stage_views(Ad(), {'database': 'example', 'mysql_view_clock': '2026-11-16T00:00:00Z'}, 'example', str(tmp_path), False, result)
    assert not result.failures
    # A changed real value must still fail under the same clock.
    expected['ages']['x'] = 4
    (tmp_path / 'tests/views.yaml').write_text(json.dumps(expected))
    result = verify.Result()
    verify.stage_views(Ad(), {'database': 'example', 'mysql_view_clock': '2026-11-16T00:00:00Z'}, 'example', str(tmp_path), False, result)
    assert any('digest x' in failure for failure in result.failures)


def test_verification_clock_sets_session_timezone_before_computing_rows(monkeypatch):
    sql = []
    monkeypatch.setattr(adapter.db, 'rows', lambda statement: sql.append(statement) or [['1', '2', '3']])
    adapter.MySQLAdapter().with_clock('2026-11-16T00:00:00Z').fingerprint('example', 'ages', [('age', 'int')])
    assert "SET time_zone='+00:00';" in sql[0]
    assert sql[0].index("SET time_zone='+00:00';") < sql[0].index('SELECT')
