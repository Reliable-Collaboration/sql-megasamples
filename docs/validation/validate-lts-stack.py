"""DL-074: verify actual isolated engine contents, retaining counts and fingerprints.

Run inside the locked tools container, after sourcing the supplied env.sh. The
SQLite file used for canonical hashing must have the same SHA-256 as both shipped
runtime copies. Live-feed observations are frozen, never re-pinned by this probe.
"""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import yaml
from megasamples import config, datasets, registry, verify
from megasamples.engines import unique_databases
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import server as pg

ROOT = Path.cwd()
OUT = ROOT / 'build/lts-audit'
assert ROOT == Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://' + str(ROOT.parent / 'sql-megasamples-upgrade-env/podman.sock')
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'


def command(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE).strip()


assert command('info', '--format', '{{.DockerRootDir}}').startswith(str(ROOT.parent / 'sql-megasamples-upgrade-env/'))
engine = sys.argv[1]
assert engine in ['mysql', 'postgres', 'sqlite']
cfg = config.load()
secret = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if line and not line.startswith('#'))
mysql.NAME, mysql.PW = 'megasamples-mysql', secret['MYSQL_ROOT_PASSWORD']
pg.NAME = 'megasamples-postgres'
frozen = {name: yaml.safe_load((ROOT / 'build/live' / f'{name}.observed.yaml').read_text())
          for name in cfg.datasets(engine) if datasets.load(name).get('live')}


def frozen_hub(spec, ad, stage, observed, result):
    name = spec.get('name') or spec['database']
    expected = frozen[name].get(stage)
    if expected is None:
        result.fail(f'{name}: no frozen {stage} record')
        return None
    if ad.name == 'mysql':
        if {key: observed.get(key) for key in expected} != expected:
            result.fail(f'{name}: contents differ from frozen build record for {stage}')
        return None
    return expected


verify.live_hub_observed = frozen_hub
sqlite_hashes = {}
if engine == 'sqlite':
    for database in unique_databases(cfg.datasets(engine)):
        path = ROOT / 'build/sqlite' / database / f'{database}.sqlite'
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                h.update(block)
        values = {'verified_build': h.hexdigest()}
        for directory in ['/data', '/shared']:
            values[directory] = command('exec', 'megasamples-sqlite', 'sha256sum', f'{directory}/{database}.sqlite').split()[0]
        assert len(set(values.values())) == 1, database + ': SQLite bytes differ'
        sqlite_hashes[database] = values

rows = registry_rows = None
if engine == 'mysql':
    rows = mysql.rows('SELECT name,CAST(row_counts AS CHAR) FROM megasamples.datasets ORDER BY name')
elif engine == 'postgres':
    rows = pg.rows('SELECT name,row_counts::text FROM datasets ORDER BY name', 'megasamples')
else:
    text = command('exec', 'megasamples-sqlite', 'sqlite3', '-tabs', '/data/megasamples.sqlite', 'SELECT name,row_counts FROM datasets ORDER BY name')
    rows = [line.split('\t', 1) for line in text.splitlines()]
registry_rows = {name: json.loads(counts) for name, counts in rows}
expected = {}
for name in cfg.datasets(engine):
    expected.setdefault(datasets.load(name)['database'], {}).update(registry.image_counts(name))
assert registry_rows == expected, engine + ': registry differs from verified data'

# Class-level wrappers preserve the receiver of MySQL's with_clock() shallow
# copies. Instance closures would accidentally query through the unfrozen receiver.
original_adapter = verify.adapter_for
adapter_class = type(original_adapter(engine, cfg.datasets(engine)[0]))
original_count, original_fingerprint = adapter_class.count, adapter_class.fingerprint


def capture_count(self, schema, table):
    value = original_count(self, schema, table)
    observed['counts'][table] = value
    return value


def capture_fingerprint(self, schema, table, columns):
    value = original_fingerprint(self, schema, table, columns)
    observed['fingerprints'].append(dict(table=table, columns=[col for col, _ in columns],
                                         n=value[0], x=value[1], s=value[2]))
    return value


adapter_class.count, adapter_class.fingerprint = capture_count, capture_fingerprint
results = {}
for name in cfg.datasets(engine):
    observed = {'counts': {}, 'fingerprints': []}
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    started = time.monotonic()
    with (OUT / f'runtime-{engine}-{name}.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            failures = verify.verify(name, engine=engine)
        except (Exception, SystemExit) as exc:
            print(type(exc).__name__, str(exc))
            failures = 1
    results[f'{engine}:{name}'] = dict(status='Passed' if failures == 0 else 'Failed', failures=failures,
                                     started_at=started_at, seconds=time.monotonic()-started, **observed)
    value = dict(engine=engine, results=results, registry_counts=registry_rows, sqlite_hashes=sqlite_hashes,
                 frozen_live_records=frozen)
    (OUT / f'runtime-{engine}.json').write_text(json.dumps(value, indent=2)+'\n')
    print(engine, name, results[f'{engine}:{name}']['status'], f'{time.monotonic()-started:.2f}s', flush=True)
assert all(result['status'] == 'Passed' for result in results.values())
