"""Cold cluster materialization must not hide slow or absent server readiness."""
import pytest

from megasamples.engines.postgres import image_test
from megasamples.engines.image_startup import check_startup, cold_copy_budget


@pytest.mark.parametrize('provisioned,ready,passes', [
    (44, 45, True),       # full cluster copy, promptly answering server
    (cold_copy_budget('postgres') - 5, cold_copy_budget('postgres') + 15, True),
                         # independent copy and server budgets, not a combined cap
    (2, 33, False),       # server itself exceeds the existing 30-second limit
    (1000, 1001, False),  # cold provisioning still has a finite limit
    (40, None, False),    # no query ever succeeds
])
def test_cold_start_and_server_readiness_have_separate_limits(provisioned, ready, passes):
    checks = image_test.Checks()
    check_startup(checks, 'postgres', provisioned, ready)
    assert (not checks.failures) is passes
