"""Why each routine demo may execute is read-only: one source for every inventory generator."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = dict(re.findall(r"\('([^']+)','([^']+)'\)", (ROOT / 'engines/postgres/init/read-routine-names.sql').read_text()))
# Design 4.2's named exceptions, by exact signature: P-3's three built-ins and P-8's direct grant.
NAMED = {
    'pg_export_snapshot()': 'Publishes a snapshot that another session can import while the exporting transaction lives (design 4.2, P-3 and P-5)',
    'pg_current_snapshot()': 'Returns the current snapshot without assigning a transaction ID (design 4.2, P-3)',
    'pg_database_size(oid)': "Reads the database size using the caller's existing access (design 4.2, P-3)",
    'megasamples_policy_loaded()': "Reports whether the read_policy library was preloaded; a direct grant to demo, the healthcheck's account (design 4.2, P-8)",
}


def reason(routine, operators, casts):
    signature, namespace, name = routine['signature'], routine['namespace'], routine['name']
    if signature in NAMED:
        return NAMED[signature]
    if namespace == 'information_schema' and name.startswith('_pg_'):
        return 'Upstream information-schema helper: expands supplied arrays or reads type and index metadata'
    if signature in operators:
        return 'Implements an initdb operator: compares or computes supplied values without changing stored state'
    if signature in casts:
        return 'Implements an initdb cast: converts supplied values without changing stored state'
    if namespace == 'pg_catalog':
        return NAMES.get(name, 'NOT in explicit read policy')
    return 'NOT in explicit read policy'
