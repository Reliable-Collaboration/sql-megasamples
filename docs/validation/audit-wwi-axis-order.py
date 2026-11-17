"""Prove WWI's historical spatial pins used the earlier canonical axis order.

Run against the isolated MySQL build server. --write refreshes only spatial fingerprints,
provided the historical expression reproduces every old pin exactly. No data is changed.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

import yaml
from megasamples import canon, verify
from megasamples.engines.mysql.adapter import MySQLAdapter
from megasamples.engines.mysql import server

assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['DOCKER_HOST'] == 'unix:///home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock'
BASE = 'd97445d2c9d9d4b0c81697f5acb7408b7ae6364e'
out = Path('build/dataset-upgrade-evidence')
results = {}
ad = MySQLAdapter()
for name in ['wideworldimporters', 'wideworldimporters_dw']:
    path = f'datasets/{name}/tests/checksums.yaml'
    old = yaml.safe_load(subprocess.check_output(['git', 'show', f'{BASE}:{path}'], text=True))
    updated = yaml.safe_load(Path(path).read_text())
    changes = {}
    for table, expected in old.items():
        columns = ad.columns(name, table)
        spatial = [c for c, t in columns if t in {'geometry', 'point', 'polygon', 'multipolygon', 'linestring', 'multilinestring', 'multipoint', 'geometrycollection'}]
        if not spatial:
            assert updated[table] == expected
            continue
        sql = canon.fingerprint_sql(name, table, columns)
        historical = sql.replace(", 'axis-order=long-lat'", '')
        assert historical != sql
        before = dict(zip(['n', 'x', 's'], map(int, server.rows(historical)[0])))
        assert before == {k: expected[k] for k in before}, f'{name}.{table}: historical digest did not reproduce'
        after = dict(zip(['n', 'x', 's'], map(int, server.rows(sql)[0])))
        assert before['n'] == after['n']
        assert [c for c, t in columns if t not in canon.EXCLUDED] == expected['columns']
        changes[table] = {'before': before, 'after': after, 'spatial_columns': spatial}
        updated[table].update(after)
    results[name] = {'status': 'Passed', 'historical_pins_reproduced': True, 'changes': changes}
    if sys.argv[1:] == ['--write']:
        verify.dump_yaml(path, updated, '# S4: canonical per-table fingerprint (count, BIT_XOR, SUM mod 2^64) over the\n# row digest defined in megasamples/canon.py. float/double/json columns are excluded.')
result = {'status': 'Passed', 'read_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'source_change': 'https://github.com/Reliable-Collaboration/sql-megasamples/commit/39a100ba42bdeb2f7fa87dc4809f5c8567832ee2',
          'vendor_source': 'https://dev.mysql.com/doc/refman/26.10/en/gis-format-conversion-functions.html',
          'vendor_read_at': (json.loads((out / 'geometry-vendor-read.json').read_text())['read_at'] if (out / 'geometry-vendor-read.json').exists() else 'Not run in this invocation'),
          'scope': 'Existing canonical WKB axis-order correction; every historical spatial pin reproduced on these exact loaded rows. Counts, column sets, exclusions and non-spatial fingerprints unchanged.',
          'datasets': results}
(out / 'wwi-axis-order.json').write_text(json.dumps(result, indent=2) + '\n')
print('Passed: historical spatial pins reproduced; current canonical fingerprints recorded for', {n: len(r['changes']) for n, r in results.items()}, flush=True)
