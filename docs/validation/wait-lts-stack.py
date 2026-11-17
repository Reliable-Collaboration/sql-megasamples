import json,os,subprocess,time
from pathlib import Path
assert os.environ.get('COMPOSE_PROJECT_NAME')=='megasamples-upgrade'
names=['megasamples-'+n for n in ['mysql','postgres','sqlite','landing','adminer','phpmyadmin','dbgate','cloudbeaver']]
end=time.monotonic()+360
while time.monotonic()<end:
 result=subprocess.run(['docker','inspect',*names],capture_output=True,text=True)
 if result.returncode==0:
  records=json.loads(result.stdout)
  assert all((r['Config'].get('Labels') or {}).get('com.docker.compose.project')=='megasamples-upgrade' for r in records)
  if all(r['State']['Running'] and (not r['State'].get('Health') or r['State']['Health']['Status']=='healthy') for r in records):
   print('Passed: all eight isolated services running, all configured health checks healthy');break
 time.sleep(2)
else:raise SystemExit('Isolated services did not become running/healthy within 360 seconds')
