"""Cold cluster materialization must not hide slow or absent server readiness."""
import pytest

from megasamples.engines.postgres import image_test


@pytest.mark.parametrize('provisioned,ready,passes', [
    (44, 45, True),       # full cluster copy, promptly answering server
    (2, 33, False),       # server itself exceeds the existing 30-second limit
    (101, 102, False),    # cold provisioning still has a finite end-to-end limit
    (40, None, False),    # no query ever succeeds
])
def test_cold_start_and_server_readiness_have_separate_limits(provisioned, ready, passes):
    checks = image_test.Checks()
    image_test.check_startup(checks, provisioned, ready)
    assert (not checks.failures) is passes
