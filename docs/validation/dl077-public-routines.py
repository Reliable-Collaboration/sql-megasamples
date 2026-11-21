"""Publish every routine demo may execute in a candidate PostgreSQL image, with its reason.

    DL077_GATE_TARGET=MANIFEST python3 docs/validation/dl077-public-routines.py

MANIFEST names a task-owned container from the candidate (tests/gates/native.py). Every connectable
database except the suites' v1_ scratch databases is read, and the sets must be identical. Writes only
v1's own docs/validation/dl-077-v1-public-routines.{json,md}; PR #14's strict-read-executable-routines.*
are that PR's evidence and are never rewritten (round 8, the P2).
"""
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests/gates"))
from docs.validation.routine_reasons import publication  # noqa: E402
from native import Target  # noqa: E402

target = Target()
container = target.container("postgres")


def rows(database, sql):
    result = subprocess.run(target.podman_args("exec", "-i", container, "psql", "-XqAt", "-F", "\t", "-v",
                                               "ON_ERROR_STOP=1", "-U", "postgres", "-d", database),
                            input=sql, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise SystemExit(f"{database}: {result.stderr.strip()[:300]}")
    return [line.split("\t") for line in result.stdout.splitlines() if line]


operators = {r[0] for r in rows("postgres", "SELECT DISTINCT p.oid::regprocedure::text FROM pg_proc p JOIN pg_operator o "
                                            "ON o.oprcode=p.oid WHERE o.oid<16384 AND p.oid<16384")}
casts = {r[0] for r in rows("postgres", "SELECT DISTINCT p.oid::regprocedure::text FROM pg_proc p JOIN pg_cast c "
                                        "ON c.castfunc=p.oid WHERE c.oid<16384 AND p.oid<16384")}
databases = [r[0] for r in rows("postgres", "SELECT datname FROM pg_database WHERE datallowconn "
                                            "AND datname NOT LIKE 'v1\\_%' ORDER BY 1")]
observed = {}
for database in databases:
    observed[database] = [dict(zip(("signature", "name", "namespace", "kind", "volatility"), r)) for r in rows(database, """
        SELECT p.oid::regprocedure::text, p.proname, n.nspname, p.prokind, p.provolatile FROM pg_proc p
        JOIN pg_namespace n ON n.oid=p.pronamespace WHERE has_function_privilege('demo', p.oid, 'EXECUTE') ORDER BY 1""")]
now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
try:
    inventory, markdown = publication(observed, operators, casts, now)
except ValueError as refused:
    raise SystemExit(str(refused))
out = ROOT / "docs/validation"
(out / "dl-077-v1-public-routines.json").write_text(json.dumps(inventory, indent=2) + "\n")
(out / "dl-077-v1-public-routines.md").write_text(markdown)
print(f"published {inventory['count']} signatures from {len(databases)} databases at {now}")
