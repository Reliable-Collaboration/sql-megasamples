"""Slow provisioning must fail readiness without hiding the image's data checks."""
from types import SimpleNamespace

from megasamples.engines.sqlite import image_test


def test_late_ready_image_still_checks_data_and_fails_startup(monkeypatch):
    clock = [0.0]
    queries = []

    def shell(*args, **kwargs):
        if args[:2] == ('docker', 'run'):
            clock[0] = 35.0
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def query(sql, database='megasamples', container=image_test.NAME):
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
    monkeypatch.setattr(image_test, 'image_counts', lambda name: {'jobs': 1})

    assert image_test.main(['pubs']) == 1
    assert 'PRAGMA integrity_check' in queries
    assert 'PRAGMA foreign_keys=ON; PRAGMA foreign_key_check' in queries
    assert 'SELECT count(*) FROM "jobs"' in queries
