"""Record the four existing translator refusals against the 9.7 LTS hub."""
import datetime
import json
import os
from pathlib import Path
import subprocess
from megasamples import datasets
from megasamples.port import ddl, model, record
from megasamples.engines.mysql import server

assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
assert subprocess.check_output(['docker','info','--format','{{.DockerRootDir}}'],text=True).strip().startswith('/home/rcc-vstudio/working/sql-megasamples-upgrade-env/')
assert server.rows('SELECT VERSION()')[0][0] == '9.7.4'
results = {}
for name in ['bts_ontime', 'wideworldimporters']:
    database = model.extract(datasets.load(name)['database'])
    for engine in ['postgres', 'sqlite']:
        try:
            ddl.render(database, engine, record.read_result_sets(name))
        except ddl.UnportableColumn as error:
            results[engine+':'+name] = dict(status='Unsupported', reason=str(error), read_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        else:
            raise AssertionError(name+' unexpectedly passed the existing generated-expression guard')
        print(engine, name, results[engine+':'+name]['status'], flush=True)
(Path('build/lts-audit')/'unsupported-pairs.json').write_text(json.dumps(results,indent=2)+'\n')
