"""Cold copying and server readiness are independently bounded."""
import pytest
from types import SimpleNamespace

from megasamples.engines.sqlite import image_test


@pytest.mark.parametrize('copy_seconds,query_seconds,passes', [
    (35, 36, True),
    (2, 33, False),
    (1000, 1001, False),
])
def test_copy_and_server_limits_and_data_checks(monkeypatch, copy_seconds, query_seconds, passes):
    clock = [0.0]
    queries = []

    def shell(*args, **kwargs):
        if args[:2] == ('docker', 'run'):
            clock[0] = copy_seconds
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def query(sql, database='megasamples', container=image_test.NAME):
        if not queries:
            clock[0] = query_seconds
        queries.append(sql)
        answer = {
            'SELECT name FROM datasets ORDER BY name': 'pubs\n',
            'PRAGMA integrity_check': 'ok',
            'PRAGMA foreign_keys=ON; PRAGMA foreign_key_check': '',
            'PRAGMA journal_mode': 'delete',
            'SELECT sqlite_version()': '3.54.1',
        }.get(sql, '1')
        return SimpleNamespace(returncode=0, stdout=answer, stderr='')

    monkeypatch.setattr(image_test, 'sh', shell)
    monkeypatch.setattr(image_test, 'q', query)
    monkeypatch.setattr(image_test.time, 'time', lambda: clock[0])
    monkeypatch.setattr(image_test.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(image_test, 'image_counts', lambda name: {'jobs': 1})

    assert image_test.main(['pubs']) == (0 if passes else 1)
    assert 'PRAGMA integrity_check' in queries
    assert 'PRAGMA foreign_keys=ON; PRAGMA foreign_key_check' in queries
    assert 'SELECT count(*) FROM "jobs"' in queries
