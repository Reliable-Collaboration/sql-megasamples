"""Check publication text against both existing private canary sets, without outputting values.

Uses the repository's own password parser with standard-library dependencies;
no host package installation or new credential generation is needed.
"""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path.cwd()
assert ROOT==Path('/home/rcc-vstudio/working/sql-megasamples-upgrade')
OUTPUT=ROOT/'docs/validation/strict-read-publication-canaries.json'
KEYS={'DEMO_PASSWORD','ADMIN_PASSWORD','MYSQL_ROOT_PASSWORD','POSTGRES_PASSWORD'}
source=ROOT/'megasamples/config.py'
module=ast.parse(source.read_text())
function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='passwords')
namespace={'os':os,'re':re,'PASSWORD_DEFAULTS':dict.fromkeys(KEYS),'ROOT':str(ROOT)}
# Execute only the same parser used by the native clients, not config.load/yaml.
exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),str(source),'exec'),namespace)
values=set()
try:
    for directory in [ROOT,ROOT/'build/strict-read/rotation-choice']:
        namespace['ROOT']=str(directory)
        row=namespace['passwords']()
        assert set(row)==KEYS
        assert all(isinstance(v,str) and len(v)>=16 for v in row.values())
        values.update(row.values())
    assert len(values)==8
except BaseException:
    print('Failed: private canary parsing; details suppressed to protect values')
    raise SystemExit(1)
if '--preflight' in sys.argv:
    print('Passed: both existing canary sets parsed privately using repository code')
    raise SystemExit(0)
paths={ROOT/p for p in subprocess.check_output(['git','diff','--name-only','main'],text=True).splitlines()}
paths.update(ROOT/p for p in ['docs/strict-read-evidence.md','docs/validation/strict-read-2026-11-18.json','build/strict-read/pr-body.md'])
paths.discard(OUTPUT)
assert paths and all(p.is_file() for p in paths)
findings=[];records=[]
for path in sorted(paths):
    raw=path.read_bytes()
    if any(v.encode() in raw for v in values):findings.append(str(path.relative_to(ROOT)))
    records.append({'path':str(path.relative_to(ROOT)),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
receipt={'status':'Passed' if not findings else 'Failed','read_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'scope':'Configured private canaries in publication text; published-bootstrap output failures are recorded separately',
         'canary_sets':2,'distinct_canary_values_checked':len(values),'files_checked':len(records),'files':records,'matched_paths':findings,
         'parser_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'self_payload_checked':True}
payload=json.dumps(receipt,indent=2)+'\n'
assert not any(v in payload for v in values),'publication receipt contains a canary'
OUTPUT.write_text(payload)
print(receipt['status']+': publication canary scan; no values emitted')
raise SystemExit(1 if findings else 0)
