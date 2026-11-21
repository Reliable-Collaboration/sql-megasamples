"""One cold-copy rule and an independent server-readiness gate for every image.

Copy/run includes runtime provisioning into a fresh volume. The server clock starts
when detached run returns, so a long copy cannot consume its query window.
"""
import math
import time

SERVER_BUDGET_SECONDS = 30
# Observed maxima, seconds; see docs/history/cold-readiness-evidence.md for measurements.
# Six fresh-volume starts per measured image; maxima include both main and PR #11
# where compared. Recorded in docs/validation/cold-readiness-2026-11-17.json.
OBSERVED_COPY_MAX_SECONDS = {'mysql': 83.76201439800207, 'postgres': 85.27370424906258, 'sqlite': 71.86194443202112}


def cold_copy_budget(engine):
    """Twice the measured maximum, rounded up to a multiple of ten seconds."""
    return math.ceil(2 * OBSERVED_COPY_MAX_SECONDS[engine] / 10) * 10


def check_startup(checks, engine, provisioned, ready):
    budget = cold_copy_budget(engine)
    checks.expect(provisioned <= budget,
                  f"cold copy/run in {provisioned:.1f}s (budget {budget}s)")
    server = ready - provisioned if ready is not None else None
    checks.expect(server is not None and 0 <= server <= SERVER_BUDGET_SECONDS,
                  f"query ready {server:.1f}s after run returned (budget {SERVER_BUDGET_SECONDS}s)"
                  if server is not None else "server never answered a query")


def probe_startup(checks, engine, started, provisioned, query):
    """Still inspect data after a late copy, but fail either exceeded budget."""
    ready = None
    deadline = started + provisioned + SERVER_BUDGET_SECONDS
    while time.monotonic() < deadline:
        if query().returncode == 0:
            ready = time.monotonic() - started
            break
        time.sleep(.2)
    checks.expect(ready is not None, "container answers a real query")
    check_startup(checks, engine, provisioned, ready)
    return ready
