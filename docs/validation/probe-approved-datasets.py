"""Verify/reset the owner-approved datasets in the isolated rehearsal only.

Run through the locked tools container after sourcing the isolated env.sh:
  .venv/bin/python docs/validation/probe-approved-datasets.py verify
  .venv/bin/python docs/validation/probe-approved-datasets.py reset
Results and command logs remain private under build/dataset-upgrade-evidence/.
"""
import contextlib
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml

from megasamples import config, datasets, verify
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import server as pg
from megasamples.engines.sqlite import adapter as sqlite_adapter
from megasamples.reset import sqlite_connections_closed

ROOT = Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
OUT = ROOT / 'build/dataset-upgrade-evidence'
NAMES = ['bts_ontime', 'wideworldimporters', 'wideworldimporters_dw']
assert Path.cwd() == ROOT
assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF'] == str(ROOT.parent / 'sql-megasamples-upgrade-env/storage.conf')
assert os.environ['DOCKER_HOST'] == 'unix://' + str(ROOT.parent / 'sql-megasamples-upgrade-env/podman.sock')
assert subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip().startswith(str(ROOT.parent / 'sql-megasamples-upgrade-env/'))
secret = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines() if line and not line.startswith('#'))
mysql.NAME = 'megasamples-mysql'
mysql.PW = secret['MYSQL_ROOT_PASSWORD']
pg.NAME = 'megasamples-postgres'
CFG = config.load()
PAIRS = [(engine, name) for engine in CFG.engines for name in NAMES if name in CFG.datasets(engine)]


def command(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def query(engine, name, sql, shared=False):
    if engine == 'mysql':
        return mysql.rows(sql, name)
    if engine == 'postgres':
        return pg.rows(sql, name)
    folder = '/shared' if shared else '/data'
    output = command(['docker', 'exec', 'megasamples-sqlite', 'sqlite3', '-tabs', f'{folder}/{name}.sqlite', sql])
    return list(csv.reader(io.StringIO(output), delimiter='\t'))


def sqlite_hash(name, folder):
    return command(['docker', 'exec', 'megasamples-sqlite', 'sha256sum', f'{folder}/{name}.sqlite']).split()[0]


def foreign_keys(engine, name):
    if engine == 'mysql':
        return query(engine, name, f"""SELECT k.constraint_name, k.table_name,
          k.ordinal_position, k.column_name, k.referenced_table_schema,
          k.referenced_table_name, k.referenced_column_name, r.update_rule, r.delete_rule
          FROM information_schema.key_column_usage k
          JOIN information_schema.referential_constraints r
            ON r.constraint_schema=k.constraint_schema AND r.constraint_name=k.constraint_name
          WHERE k.constraint_schema='{name}' AND k.referenced_table_name IS NOT NULL
          ORDER BY k.constraint_name,k.ordinal_position""")
    if engine == 'postgres':
        return query(engine, name, "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace ORDER BY conname")
    tables = query(engine, name, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    return [[table, *fk] for (table,) in tables
            for fk in query(engine, name, 'PRAGMA foreign_key_list("' + table.replace('"', '""') + '")')]


def verify_running(label):
    runtime = OUT / f'{label}-sqlite'
    runtime.mkdir(exist_ok=True)
    for engine, name in PAIRS:
        if engine != 'sqlite':
            continue
        target = runtime / name
        target.mkdir(exist_ok=True)
        subprocess.run(['docker', 'cp', f'megasamples-sqlite:/data/{name}.sqlite', str(target / f'{name}.sqlite')], check=True, capture_output=True)
        for filename in ['model.json', 'dropped.txt']:
            src = ROOT / 'build/sqlite' / name / filename
            if src.exists():
                shutil.copy2(src, target / filename)
        expected_hash = hashlib.sha256((ROOT / 'build/sqlite' / name / f'{name}.sqlite').read_bytes()).hexdigest()
        assert sqlite_hash(name, '/data') == expected_hash == sqlite_hash(name, '/shared')
    sqlite_adapter.engine_build_dir = lambda _: str(runtime)
    result = {}
    for engine, name in PAIRS:
        expected = yaml.safe_load((ROOT / 'datasets' / name / 'tests/expected_counts.yaml').read_text())
        if engine == 'mysql':
            registered = mysql.rows(f"SELECT CAST(row_counts AS CHAR) FROM megasamples.datasets WHERE name='{name}'")
        elif engine == 'postgres':
            registered = pg.rows(f"SELECT row_counts::text FROM datasets WHERE name='{name}'", 'megasamples')
        else:
            registered = query(engine, 'megasamples', f"SELECT row_counts FROM datasets WHERE name='{name}'")
        assert len(registered) == 1 and json.loads(registered[0][0]) == expected, f'{engine}:{name} registry differs'
        started = time.monotonic()
        with (OUT / f'{label}-{engine}-{name}.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            rc = verify.verify(name, engine=engine)
        result[f'{engine}:{name}'] = dict(status='Passed' if rc == 0 else 'Failed', failures=rc, seconds=round(time.monotonic() - started, 2))
        (OUT / f'{label}-results.json').write_text(json.dumps(result, indent=2) + '\n')
        print(engine, name, result[f'{engine}:{name}'], flush=True)
    assert all(r['status'] == 'Passed' for r in result.values())


def reset_pairs():
    # Change a real value without changing row counts, and add an object that must disappear.
    probes = {'bts_ontime': ('l_airport', 'description', "code='ATL'"),
              'wideworldimporters': ('application_people', 'fullname', 'personid=1'),
              'wideworldimporters_dw': ('dimension_city', 'city', 'city_key=0')}
    results = {}
    definitions = {}
    for engine, name in PAIRS:
        table, column, where = probes[name]
        baseline = query(engine, name, f'SELECT {column} FROM {table} WHERE {where}')
        assert len(baseline) == 1
        fks_before = foreign_keys(engine, name)
        hashes = {folder: sqlite_hash(name, folder) for folder in ['/data', '/shared']} if engine == 'sqlite' else {}
        guard = sqlite_connections_closed() if engine == 'sqlite' else contextlib.nullcontext()
        with guard:
            for shared in ([False, True] if engine == 'sqlite' else [False]):
                query(engine, name, f"UPDATE {table} SET {column}='DATASET_RESET_PROBE' WHERE {where}", shared)
                query(engine, name, 'CREATE TABLE dataset_upgrade_reset_probe (id INT)', shared)
                assert query(engine, name, f'SELECT {column} FROM {table} WHERE {where}', shared) != baseline
            started = time.monotonic()
            with (OUT / f'reset-{engine}-{name}.log').open('w') as log:
                rc = subprocess.run(['make', 'reset', 'PY=' + sys.executable, f'R={engine}:{name}'], stdout=log, stderr=subprocess.STDOUT).returncode
            assert rc == 0, f'{engine}:{name} reset failed'
            assert query(engine, name, f'SELECT {column} FROM {table} WHERE {where}') == baseline
            if engine == 'mysql':
                remaining = query(engine, name, f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='{name}' AND table_name='dataset_upgrade_reset_probe'")
            elif engine == 'postgres':
                remaining = query(engine, name, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='dataset_upgrade_reset_probe'")
            else:
                remaining = query(engine, name, "SELECT COUNT(*) FROM sqlite_master WHERE name='dataset_upgrade_reset_probe'")
                for folder, expected in hashes.items():
                    assert sqlite_hash(name, folder) == expected
            assert remaining == [['0']]
            fks_after = foreign_keys(engine, name)
            assert fks_after == fks_before, f'{engine}:{name} foreign key definitions differ after reset'
        definitions[f'{engine}:{name}'] = dict(before=fks_before, after=fks_after)
        (OUT / 'reset-foreign-keys.json').write_text(json.dumps(definitions, indent=2) + '\n')
        result = dict(status='Passed', returncode=rc, seconds=round(time.monotonic() - started, 2), same_count_value_restored=True, added_object_removed=True, sqlite_bytes_restored=bool(hashes), foreign_key_definitions_restored=True, foreign_key_definition_rows=len(fks_before))
        results[f'{engine}:{name}'] = result
        (OUT / 'reset-results.json').write_text(json.dumps(results, indent=2) + '\n')
        print(engine, name, result, flush=True)
    verify_running('post-reset')


if __name__ == '__main__':
    if sys.argv[1:] == ['verify']:
        verify_running('runtime')
    elif sys.argv[1:] == ['reset']:
        reset_pairs()
    else:
        raise SystemExit('Specify verify or reset')
