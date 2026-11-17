import hashlib,json,os,subprocess,tempfile,urllib.request
from pathlib import Path
assert Path('/run/.containerenv').exists() or Path('/.dockerenv').exists(),'Container-only setup'
assert os.environ['COMPOSE_PROJECT_NAME']=='megasamples-upgrade'
pin={'source': 'https://apt.postgresql.org/pub/repos/apt/dists/trixie-pgdg/main/binary-amd64/Packages.gz', 'read_at': '2026-11-17T04:09:43.044818+00:00', 'package': {'Package': 'libpq5', 'Version': '18.7-1.pgdg13+2', 'Filename': 'pool/main/p/postgresql-18/libpq5_18.7-1.pgdg13+2_amd64.deb', 'SHA256': 'bfd1d4e64e1a87c637a84e8a712a517ae8059ec969ba57fe402b259ede61e2b8'}, 'url': 'https://apt.postgresql.org/pub/repos/apt/pool/main/p/postgresql-18/libpq5_18.7-1.pgdg13+2_amd64.deb'}
with tempfile.TemporaryDirectory() as temp:
 path=Path(temp)/'libpq5.deb'
 with urllib.request.urlopen(pin['url'],timeout=60) as r:path.write_bytes(r.read())
 assert hashlib.sha256(path.read_bytes()).hexdigest()==pin['package']['SHA256']
 subprocess.run(['apt-get','update','-qq'],check=True)
 subprocess.run(['apt-get','install','-y','--no-install-recommends',str(path)],check=True)
installed=subprocess.check_output(['dpkg-query','-W','-f=${Version}','libpq5'],text=True).strip()
assert installed==pin['package']['Version'],installed
print('Installed verified libpq package',installed,'inside isolated tools container only')
