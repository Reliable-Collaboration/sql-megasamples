"""The common policy retains independent, finite copy and server limits."""
from types import SimpleNamespace

import pytest

from megasamples.engines import image_startup
from megasamples.engines.mysql.image_test import Checks


@pytest.mark.parametrize('engine', ['mysql', 'postgres', 'sqlite'])
@pytest.mark.parametrize('scenario,passes', [
    ('both-at-limit', True),
    ('copy-over-limit', False),
    ('server-over-limit', False),
    ('no-query', False),
])
def test_independent_limits(engine, scenario, passes):
    budget = image_startup.cold_copy_budget(engine)
    provisioned = budget + (.01 if scenario == 'copy-over-limit' else 0)
    ready = provisioned + (30.01 if scenario == 'server-over-limit' else 30)
    if scenario == 'no-query':
        ready = None
    checks = Checks()
    assert image_startup.SERVER_BUDGET_SECONDS == 30
    image_startup.check_startup(checks, engine, provisioned, ready)
    assert (not checks.failures) is passes


@pytest.mark.parametrize('engine', ['mysql', 'postgres', 'sqlite'])
def test_absent_server_gets_only_thirty_seconds_even_after_late_copy(monkeypatch, engine):
    clock = [1000.0]
    attempts = []

    def query():
        attempts.append(clock[0])
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(image_startup.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(image_startup.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    checks = Checks()
    assert image_startup.probe_startup(checks, engine, 0, 1000, query) is None
    assert attempts[0] == 1000
    assert attempts[-1] < 1030 <= clock[0]
    assert any('cold copy/run' in failure for failure in checks.failures)
    assert 'server never answered a query' in checks.failures
