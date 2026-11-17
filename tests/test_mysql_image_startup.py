"""Late cold provisioning must fail readiness and still reach MySQL data checks."""
from types import SimpleNamespace

from megasamples.engines.mysql import image_test


def test_late_ready_image_checks_data_without_relaxing_budget(monkeypatch, capsys):
    clock = [0.0]
    queries = []
    baked_password = image_test.q.__defaults__[1]

    def shell(*args, **kwargs):
        if args[:2] == ('docker', 'run'):
            clock[0] = 65.0
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def query(sql, **kwargs):
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
    monkeypatch.setattr(image_test, 'image_counts', lambda name: {'jobs': 1})
    monkeypatch.setattr(image_test, 'account_checks', lambda *args: None)

    assert image_test.BUDGET_SECONDS == 30
    assert image_test.main(['pubs']) == 1
    assert 'SELECT COUNT(*) FROM `jobs`' in queries
    assert 'CHECK TABLE `jobs`' in queries
    failures = [line for line in capsys.readouterr().out.splitlines() if line.startswith('  x ')]
    assert failures == ['  x ready in 65.0s (budget 30s)']
