"""Cold copying has its own gate and must still reach MySQL data checks."""
import pytest
from types import SimpleNamespace

from megasamples.engines.mysql import image_test


@pytest.mark.parametrize('copy_seconds,query_seconds,passes', [
    (65, 66, True),     # full baked image copies slowly; server answers promptly
    (2, 33, False),     # fast copy cannot hide a server taking over 30 seconds
    (1000, 1001, False),  # copying remains bounded
])
def test_copy_and_server_limits_and_data_checks(monkeypatch, capsys, copy_seconds, query_seconds, passes):
    clock = [0.0]
    queries = []
    baked_password = image_test.q.__defaults__[1]

    def shell(*args, **kwargs):
        if args[:2] == ('docker', 'run'):
            clock[0] = copy_seconds
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def query(sql, **kwargs):
        if not queries:
            clock[0] = query_seconds
        queries.append(sql)
        answers = {
            'SELECT name FROM megasamples.datasets ORDER BY name': 'pubs\n',
            'SELECT COUNT(*) FROM `jobs`': '1',
            'CHECK TABLE `jobs`': 'pubs.jobs\tcheck\tstatus\tOK',
        }
        if 'authentication_string' in sql:
            answer = '0'
        elif 'CONVERT_TZ' in sql:
            answer = '2025-12-31 18:00:00'
        elif 'SELECT CONCAT(table_name)' in sql:
            answer = 'jobs'
        elif 'referential_constraints' in sql:
            answer = ''
        else:
            answer = answers.get(sql, '1')
        rejected_override = (kwargs.get('container') == image_test.NAME + '2'
                             and kwargs.get('pw') == baked_password)
        return SimpleNamespace(returncode=int(rejected_override), stdout=answer, stderr='')

    monkeypatch.setattr(image_test, 'sh', shell)
    monkeypatch.setattr(image_test, 'q', query)
    monkeypatch.setattr(image_test.time, 'time', lambda: clock[0])
    monkeypatch.setattr(image_test.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(image_test, 'image_counts', lambda name: {'jobs': 1})
    monkeypatch.setattr(image_test, 'account_checks', lambda *args: None)

    assert image_test.main(['pubs']) == (0 if passes else 1)
    assert 'SELECT COUNT(*) FROM `jobs`' in queries
    assert 'CHECK TABLE `jobs`' in queries
    failures = [line for line in capsys.readouterr().out.splitlines() if line.startswith('  x ')]
    assert bool(failures) is not passes
